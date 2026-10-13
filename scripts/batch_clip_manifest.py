#!/usr/bin/env python3
"""Rights-gated batch PDF crop builder from human-reviewed page coordinates.

This NEVER publishes images, never guesses coordinates, and never grants
redistribution rights. Review status is always pending_manual_visual_review.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import pathlib
import sqlite3
from urllib.parse import urlparse

KINDS = {"question", "explanation", "answer"}
FIELDS = {"exam_id", "paper_no", "question_no", "kind", "pdf_path",
          "source_url", "page", "x0", "y0", "x1", "y1"}


def validate_row(row):
    missing = FIELDS - set(row)
    if missing:
        raise ValueError(f"Missing columns: {sorted(missing)}")
    eid, number, page = (int(row[k]) for k in ("exam_id", "question_no", "page"))
    if eid < 1 or not 1 <= number <= 60 or page < 1:
        raise ValueError("Invalid exam, question, or page")
    if row["kind"] not in KINDS:
        raise ValueError("Unsupported kind")
    if not row["paper_no"].strip():
        raise ValueError("Original paper number required for stable linking")
    if urlparse(row["source_url"]).scheme != "https":
        raise ValueError("HTTPS source link required")
    coords = tuple(float(row[k]) for k in ("x0", "y0", "x1", "y1"))
    a, b, c, d = coords
    if not (0 <= a < c <= 1 and 0 <= b < d <= 1):
        raise ValueError("Bounding box must be normalized in [0,1]")
    pdf = pathlib.Path(row["pdf_path"])
    if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
        raise ValueError(f"PDF missing or wrong extension: {pdf}")
    return eid, number, page, coords, pdf


def run(catalog, manifest, out_root="workspace/private_clips", apply=False,
        rights_confirmed=False, dpi=180):
    if apply and not rights_confirmed:
        raise ValueError("Confirm legally authorized local copying with --rights-confirmed")
    if not 72 <= dpi <= 600:
        raise ValueError("DPI must be in [72,600]")
    with open(manifest, encoding="utf-8-sig", newline="") as f:
        source_rows = list(csv.DictReader(f))
    if not source_rows:
        raise ValueError("Empty manifest")
    rows = [(row, validate_row(row)) for row in source_rows]
    if not apply:
        return {"validated": len(rows), "cropped": 0, "committed": False}
    try:
        import fitz
    except ImportError as e:
        raise RuntimeError("Install pymupdf to generate local crops") from e
    cat = sqlite3.connect(catalog)
    cat.execute("PRAGMA foreign_keys=ON")
    out = pathlib.Path(out_root)
    # Protect against accidentally pushing images: enforce private workspace target.
    if not ("workspace" in out.parts and "private_clips" in out.parts):
        raise ValueError("--out-root must be inside workspace/private_clips (gitignored)")
    docs = {}
    processed = 0
    try:
        for row, (eid, qn, page_no, (x0, y0, x1, y1), pdfpath) in rows:
            exam = cat.execute(
                "SELECT record_id FROM exam_catalog WHERE exam_id=?", (eid,)
            ).fetchone()
            if not exam or str(exam[0]) != row["paper_no"].strip():
                raise ValueError(f"Catalog exam ID / paper number mismatch: {eid}")
            key = str(pdfpath.resolve())
            if key not in docs:
                docs[key] = fitz.open(key)
            doc = docs[key]
            if page_no > len(doc):
                raise ValueError(f"Page out of range: {pdfpath}: {page_no}")
            page = doc[page_no - 1]
            rect = page.rect
            bounds = fitz.Rect(rect.x0 + x0 * rect.width, rect.y0 + y0 * rect.height,
                               rect.x0 + x1 * rect.width, rect.y0 + y1 * rect.height)
            # Hash the complete placement to avoid overwriting multiple regions.
            identity = repr((eid, qn, row["kind"], page_no, (x0, y0, x1, y1), row["source_url"]))
            suffix = hashlib.sha256(identity.encode()).hexdigest()[:14]
            destination = out / f"exam-{eid}" / f"q{qn:02d}_{row['kind']}_p{page_no}_{suffix}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72),
                                  clip=bounds, alpha=False)
            pix.save(destination)
            digest = hashlib.sha256(destination.read_bytes()).hexdigest()
            earlier = cat.execute("""SELECT image_id FROM image_assets
                WHERE exam_id=? AND question_no=? AND asset_kind=? AND
                source_pdf_url=? AND pdf_page_zero_based=?
                AND x0_norm=? AND y0_norm=? AND x1_norm=? AND y1_norm=?""",
                (eid, qn, row["kind"], row["source_url"], page_no - 1,
                 x0, y0, x1, y1)).fetchall()
            if len(earlier) > 1:
                raise ValueError(f"Ambiguous duplicate image rows: {eid}, question {qn}")
            if earlier:
                cat.execute("""UPDATE image_assets SET local_image_path=?,sha256=?,
                    review_status='pending_manual_visual_review',
                    rights_status='private_copy_not_for_redistribution'
                    WHERE image_id=?""", (str(destination), digest, earlier[0][0]))
            else:
                cat.execute("""INSERT INTO image_assets(exam_id,question_no,asset_kind,
                    source_pdf_url,pdf_page_zero_based,x0_norm,y0_norm,x1_norm,y1_norm,
                    local_image_path,sha256,rights_status,review_status)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (eid, qn, row["kind"], row["source_url"], page_no - 1,
                     x0, y0, x1, y1, str(destination), digest,
                     "private_copy_not_for_redistribution", "pending_manual_visual_review"))
            processed += 1
        cat.commit()
    except Exception:
        cat.rollback()
        raise
    finally:
        for doc in docs.values():
            doc.close()
        cat.close()
    return {"validated": len(rows), "cropped": processed, "committed": True,
            "review_status": "pending_manual_visual_review"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--catalog", required=True)
    p.add_argument("--manifest", required=True, help="CSV with manual page bounds")
    p.add_argument("--out-root", default="workspace/private_clips")
    p.add_argument("--dpi", type=int, default=180)
    p.add_argument("--apply", action="store_true")
    p.add_argument("--rights-confirmed", action="store_true")
    a = p.parse_args()
    print(run(a.catalog, a.manifest, a.out_root, a.apply, a.rights_confirmed, a.dpi))


if __name__ == "__main__":
    main()
