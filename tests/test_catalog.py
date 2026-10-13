import unittest, tempfile, pathlib, sys,sqlite3
sys.path.insert(0,str(pathlib.Path(__file__).parents[1]/'scripts'))
from build_research_catalog import build
from validate_research import verify
class TestCatalog(unittest.TestCase):
 def test_empty_and_research(self):
  with tempfile.TemporaryDirectory() as d:
   path=pathlib.Path(d)/'catalog.sqlite'
   build(path)
   verify(path)
   c=sqlite3.connect(path)
   self.assertEqual(c.execute('SELECT COUNT(*) FROM source_registry').fetchone()[0],11)
   self.assertEqual(c.execute('SELECT regime FROM cohort_years WHERE admission_year=2027').fetchone()[0],'common_plus_elective')
   self.assertEqual(c.execute('SELECT regime FROM cohort_years WHERE admission_year=2028').fetchone()[0],'integrated')
   c.close()
if __name__=='__main__':unittest.main()
