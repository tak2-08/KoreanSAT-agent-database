#!/usr/bin/env python3
"""Offline, read-only quality coverage report for user-owned combined item DB."""
from __future__ import annotations

import argparse
import json
import pathlib
import sqlite3


def report(db):
    db_path = pathlib.Path(db).resolve()
    c = sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True)
    count = c.execute("SELECT COUNT(*) FROM question_items").fetchone()[0]
    flags = {
        "stem_20_chars": "LENGTH(TRIM(COALESCE(stem_text,'')))>=20",
        "solution_20_chars": "LENGTH(TRIM(COALESCE(solution_text,'')))>=20",
        "has_answer": "answer IS NOT NULL",
        "has_correct_rate": "correct_rate IS NOT NULL",
        "megastudy_sample_rate": "correct_rate_source='megastudy'",
    }
    result = {"question_items": count,
              "exams": c.execute("SELECT COUNT(*) FROM exams").fetchone()[0]}
    for name, sql in flags.items():
        n = c.execute("SELECT COUNT(*) FROM question_items WHERE " + sql).fetchone()[0]
        result[name] = {"count": n, "share": round(n / count, 4) if count else 0}
    c.close()
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True)
    a = ap.parse_args()
    print(json.dumps(report(a.db), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
