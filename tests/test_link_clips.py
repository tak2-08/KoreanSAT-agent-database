import hashlib
import pathlib
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "scripts"))
from link_clips_to_items import link


class TestClipLink(unittest.TestCase):
    def test_safe_stable_join(self):
        with tempfile.TemporaryDirectory() as td:
            root = pathlib.Path(td)
            image = root / "local.png"
            image.write_bytes(b"private test bytes")
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            cpath, apath = root / "catalog.sqlite", root / "agent.sqlite"
            c = sqlite3.connect(cpath)
            c.executescript("""CREATE TABLE exam_catalog(exam_id INTEGER PRIMARY KEY,record_id TEXT);
               CREATE TABLE image_assets(image_id INTEGER PRIMARY KEY,exam_id INTEGER,
                 question_no INTEGER,asset_kind TEXT,local_image_path TEXT,source_pdf_url TEXT,
                 sha256 TEXT,review_status TEXT,rights_status TEXT);""")
            c.execute("INSERT INTO exam_catalog VALUES(1,'paper-x')")
            c.execute("INSERT INTO image_assets VALUES(1,1,7,'question',?,?,?,'approved','private_copy_not_for_redistribution')",
                      (str(image), "https://example.org/paper.pdf", digest))
            c.commit()
            c.close()
            a = sqlite3.connect(apath)
            a.executescript("""CREATE TABLE exams(exam_id INTEGER PRIMARY KEY,paper_no TEXT);
                CREATE TABLE question_items(item_id INTEGER PRIMARY KEY,exam_id INTEGER,question_no INTEGER);""")
            a.execute("INSERT INTO exams VALUES(88,'paper-x')")
            a.execute("INSERT INTO question_items VALUES(3,88,7)")
            a.commit()
            a.close()
            self.assertEqual(link(cpath, apath, False)["committed"], False)
            self.assertEqual(link(cpath, apath, True)["linked"], 1)
            c = sqlite3.connect(cpath)
            self.assertEqual(c.execute("SELECT agent_item_id FROM question_clip_links").fetchone()[0], 3)
            c.close()


if __name__ == "__main__":
    unittest.main()
