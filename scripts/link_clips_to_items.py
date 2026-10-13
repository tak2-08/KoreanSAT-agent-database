#!/usr/bin/env python3
"""Verify and link manually approved PRIVATE PDF crops to question_items.

Join by stable original EBSi paper_no + question_no, not unrelated SQLite IDs.
This only creates local links; it never grants a public image license.
"""
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sqlite3
from datetime import datetime, timezone


def link(catalog_path, agent_path, apply=False):
    cat = sqlite3.connect(catalog_path)
    agent = sqlite3.connect(f"file:{pathlib.Path(agent_path).resolve().as_posix()}?mode=ro", uri=True)
    cat.execute("""CREATE TABLE IF NOT EXISTS question_clip_links(
      link_id INTEGER PRIMARY KEY,
      image_id INTEGER UNIQUE NOT NULL,
      original_paper_no TEXT NOT NULL,
      agent_item_id INTEGER NOT NULL,
      asset_kind TEXT NOT NULL,
      local_image_path TEXT NOT NULL,
      source_pdf_url TEXT NOT NULL,
      image_sha256 TEXT NOT NULL,
      validated_at TEXT NOT NULL,
      publication_status TEXT NOT NULL DEFAULT 'private_not_redistributable',
      FOREIGN KEY(image_id) REFERENCES image_assets(image_id))""")
    counts = {"linked": 0, "unreviewed": 0, "missing_image": 0,
              "hash_mismatch": 0, "missing_paper": 0,
              "missing_question": 0, "ambiguous_question": 0}
    rows = cat.execute("""SELECT i.image_id, e.record_id, i.question_no, i.asset_kind,
      i.local_image_path, i.source_pdf_url, i.sha256, i.review_status, i.rights_status
      FROM image_assets i JOIN exam_catalog e ON e.exam_id=i.exam_id""").fetchall()
    for image_id, paper_no, question_no, kind, path, src, digest, review, rights in rows:
        if review != "approved" or not rights.startswith("private_copy"):
            counts["unreviewed"] += 1
            continue
        if not paper_no or not src or not src.startswith("https://"):
            counts["missing_paper"] += 1
            continue
        p = pathlib.Path(path)
        if not p.is_file():
            counts["missing_image"] += 1
            continue
        if not digest or hashlib.sha256(p.read_bytes()).hexdigest() != digest:
            counts["hash_mismatch"] += 1
            continue
        matches = agent.execute("""SELECT q.item_id FROM question_items q
            JOIN exams e ON e.exam_id=q.exam_id
            WHERE CAST(e.paper_no AS TEXT)=? AND q.question_no=?""",
            (str(paper_no), question_no)).fetchall()
        if not matches:
            counts["missing_question"] += 1
            continue
        if len(matches) != 1:
            counts["ambiguous_question"] += 1
            continue
        cat.execute("""INSERT INTO question_clip_links
            (image_id,original_paper_no,agent_item_id,asset_kind,local_image_path,
             source_pdf_url,image_sha256,validated_at)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(image_id) DO UPDATE SET
            agent_item_id=excluded.agent_item_id,local_image_path=excluded.local_image_path,
            image_sha256=excluded.image_sha256,validated_at=excluded.validated_at""",
            (image_id, str(paper_no), matches[0][0], kind, str(p), src, digest,
             datetime.now(timezone.utc).isoformat()))
        counts["linked"] += 1
    if apply:
        cat.commit()
    else:
        cat.rollback()
    cat.close()
    agent.close()
    return {**counts, "committed": apply}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", required=True)
    ap.add_argument("--agent-db", required=True, help="local suneung_agent.sqlite; read-only")
    ap.add_argument("--apply", action="store_true", help="commit; otherwise dry run")
    a = ap.parse_args()
    print(link(a.catalog, a.agent_db, a.apply))


if __name__ == "__main__":
    main()
