import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "scripts"))
from import_official_attendance import import_csv


class TestAttendance(unittest.TestCase):
    def sample(self):
        return [
            {"학년도": "1994", "시험일정": "1993-08-20",
             "지원인원(명)": "700,000", "응시인원(명)": "650,000",
             "응시율(퍼센트)": "92.9"},
            {"학년도": "1994", "시험일정": "1993-11-16",
             "지원인원(명)": "690000", "응시인원(명)": "660000",
             "응시율(퍼센트)": "95.7"},
            {"학년도": "2026", "시험일정": "2025-11-13",
             "지원인원(명)": "550000", "응시인원(명)": "500000",
             "응시율(퍼센트)": "90.9"},
        ]

    def test_distinct_1994_and_update_only_single(self):
        c = sqlite3.connect(":memory:")
        c.execute("""CREATE TABLE cohort_years(
          admission_year INTEGER PRIMARY KEY,
          candidate_count INTEGER,actual_test_takers INTEGER)""")
        c.executemany("INSERT INTO cohort_years(admission_year) VALUES(?)", [(1994,), (2026,)])
        result = import_csv(c, self.sample(), apply=True)
        self.assertEqual(result["observations"], 3)
        self.assertEqual(c.execute("SELECT COUNT(*) FROM official_attendance WHERE admission_year=1994").fetchone()[0], 2)
        self.assertEqual(c.execute("SELECT candidate_count FROM cohort_years WHERE admission_year=1994").fetchone()[0], None)
        self.assertEqual(c.execute("SELECT actual_test_takers FROM cohort_years WHERE admission_year=2026").fetchone()[0], 500000)

    def test_bad_rate_rejected(self):
        c = sqlite3.connect(":memory:")
        bad = self.sample()[2].copy()
        bad["응시율(퍼센트)"] = "2.1"
        with self.assertRaises(ValueError):
            import_csv(c, [bad], apply=False)


if __name__ == "__main__":
    unittest.main()
