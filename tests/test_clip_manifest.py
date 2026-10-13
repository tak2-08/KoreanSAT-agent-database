import pathlib
import sys
import tempfile
import unittest

sys.path.insert(0, str(pathlib.Path(__file__).parents[1] / "scripts"))
from batch_clip_manifest import validate_row, run


class TestClipManifest(unittest.TestCase):
    def sample(self, pdf):
        return dict(exam_id="1", paper_no="TEST_PAPER", question_no="2",
                    kind="question", pdf_path=str(pdf), source_url="https://example.org/a.pdf",
                    page="1", x0="0.1", y0="0.2", x1="0.5", y1="0.8")

    def test_bounds_reject(self):
        with tempfile.TemporaryDirectory() as td:
            pdf = pathlib.Path(td) / "a.pdf"
            pdf.write_bytes(b"not rendered in dry run")
            record = self.sample(pdf)
            self.assertEqual(validate_row(record)[0], 1)
            record["x1"] = "0.01"
            with self.assertRaises(ValueError):
                validate_row(record)

    def test_never_apply_without_copy_right(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                run("catalog.sqlite", "manifest.csv", apply=True, rights_confirmed=False)


if __name__ == "__main__":
    unittest.main()
