#!/usr/bin/env python3
"""Validate catalog SQLite referential integrity, cohort years, source provenance."""
import argparse,sqlite3,sys

def verify(db):
 c=sqlite3.connect(db)
 if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise AssertionError('SQLite corrupt')
 if c.execute('PRAGMA foreign_key_check').fetchall():raise AssertionError('Foreign key violation')
 for y in range(1994,2029):
  a=c.execute('SELECT admission_year,test_calendar_year,regime FROM cohort_years WHERE admission_year=?',(y,)).fetchone()
  assert a and a[1]==y-1,('missing/misaligned academic year',y)
 assert c.execute('SELECT COUNT(*) FROM cohort_years').fetchone()[0]==35
 assert c.execute('SELECT COUNT(*) FROM csat_subject_scope WHERE from_admission_year=2028').fetchone()[0]>=4
 assert c.execute('SELECT COUNT(*) FROM curricula').fetchone()[0]>=6
 assert c.execute('SELECT COUNT(*) FROM policy_events').fetchone()[0]>=6
 # year-to-year ability assumptions prohibited without grounded sources
 assert c.execute('SELECT COUNT(*) FROM cohort_years WHERE relative_ability IS NOT NULL').fetchone()[0]==0
 assert c.execute("SELECT COUNT(*) FROM pdf_source_assets WHERE rights_status!='external_link_only'").fetchone()[0]==0
 assert c.execute("SELECT COUNT(*) FROM image_assets WHERE rights_status NOT LIKE 'private_copy%'").fetchone()[0]==0
 for table in ['cohort_years','exam_catalog','pdf_source_assets','official_document_catalog']:
  print(table,c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0])
 print('PASS: integrity, provenance, full academic-year coverage and policy checks')
 c.close()
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--catalog',required=True);a=ap.parse_args();verify(a.catalog)
