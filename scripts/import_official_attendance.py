#!/usr/bin/env python3
"""Import an officially downloaded KICE attendance CSV into a LOCAL research catalog.

Never equate applicants with sitters, or infer current-student ability. Two 1994
sessions remain distinct. Official dataset is KOGL Type 2 (attribution + NC).
"""
from __future__ import annotations

import argparse
import csv
import io
import pathlib
import re
import sqlite3

SOURCE = "https://www.data.go.kr/data/15098904/fileData.do"
RIGHTS = "KOGL-2-attribution-noncommercial"


def read_rows(path):
    raw = pathlib.Path(path).read_bytes()
    for encoding in ("utf-8-sig", "cp949"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSV encoding must be UTF-8 or CP949")
    return list(csv.DictReader(io.StringIO(decoded)))


def normalized(row):
    return {re.sub(r"[\s()（）]", "", (k or "")): (v or "").strip()
            for k, v in row.items()}


def number(value, field):
    clean = str(value).replace(",", "").replace(" ", "").strip()
    if not re.fullmatch(r"\d+", clean):
        raise ValueError(f"{field}: expected nonnegative integer, got {value!r}")
    return int(clean)


def import_csv(connection, rows, apply=False):
    connection.execute("""CREATE TABLE IF NOT EXISTS official_attendance (
        observation_id INTEGER PRIMARY KEY,
        admission_year INTEGER NOT NULL,
        exam_session TEXT NOT NULL,
        applicants INTEGER NOT NULL,
        examinees INTEGER NOT NULL,
        reported_turnout_pct REAL,
        source_url TEXT NOT NULL,
        license_code TEXT NOT NULL,
        UNIQUE(admission_year,exam_session))""")
    connection.execute("CREATE INDEX IF NOT EXISTS idx_attendance_year ON official_attendance(admission_year)")
    count = 0
    years = set()
    seen = set()
    for raw in rows:
        r = normalized(raw)
        year = number(r.get("학년도", ""), "학년도")
        if not 1994 <= year <= 2028:
            raise ValueError(f"Out-of-scope academic year: {year}")
        session = r.get("시험일정", "")
        if not session:
            raise ValueError(f"Missing exam session/date for {year}")
        key = (year, session)
        if key in seen:
            raise ValueError(f"Duplicate exam session within CSV: {key}")
        seen.add(key)
        applicants = number(r.get("지원인원명", ""), "지원인원(명)")
        examinees = number(r.get("응시인원명", ""), "응시인원(명)")
        if applicants <= 0 or examinees > applicants:
            raise ValueError(f"Invalid applicants/examinees: {key}")
        turnout_text = r.get("응시율퍼센트", "").replace("%", "").strip()
        turnout = float(turnout_text) if turnout_text else None
        if turnout is not None and (not 0 <= turnout <= 100 or abs(100 * examinees / applicants - turnout) > 1):
            raise ValueError(f"Inconsistent reported turnout: {key}")
        connection.execute("""INSERT INTO official_attendance
          (admission_year,exam_session,applicants,examinees,reported_turnout_pct,source_url,license_code)
          VALUES(?,?,?,?,?,?,?)
          ON CONFLICT(admission_year,exam_session) DO UPDATE SET
          applicants=excluded.applicants,examinees=excluded.examinees,
          reported_turnout_pct=excluded.reported_turnout_pct""",
          (year, session, applicants, examinees, turnout, SOURCE, RIGHTS))
        years.add(year)
        count += 1
    # Only single-session academic years can update the existing one-row-per-year
    # cohort table. In particular, 1994 must NEVER be silently summed.
    if connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='cohort_years'").fetchone():
        for year in years:
            stats = connection.execute(
                "SELECT applicants,examinees FROM official_attendance WHERE admission_year=?", (year,)
            ).fetchall()
            if year == 1994 or len(stats) != 1:
                continue
            app, takers = stats[0]
            old = connection.execute(
                "SELECT candidate_count,actual_test_takers FROM cohort_years WHERE admission_year=?", (year,)
            ).fetchone()
            if old is not None:
                if old[0] not in (None, app) or old[1] not in (None, takers):
                    raise ValueError(f"Existing cohort totals conflict with official source: {year}")
                connection.execute("""UPDATE cohort_years
                    SET candidate_count=?,actual_test_takers=? WHERE admission_year=?""",
                    (app, takers, year))
    if apply:
        connection.commit()
    else:
        connection.rollback()
    return {"observations": count, "academic_years": len(years), "committed": apply}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", required=True, help="local research_catalog.sqlite")
    ap.add_argument("--csv", required=True, help="downloaded official KICE CSV")
    ap.add_argument("--apply", action="store_true", help="commit; default is rollback dry run")
    args = ap.parse_args()
    with sqlite3.connect(args.catalog) as conn:
        print(import_csv(conn, read_rows(args.csv), args.apply))


if __name__ == "__main__":
    main()
