#!/usr/bin/env python3
"""Build a reproducible rights-aware CSAT research database.

Reads *only* bibliographic fields and external links from the supplied original
.skill zip. Does NOT publish question text, source PDFs, explanations, metrics
or session credentials. The archive is never copied into the result.
"""
from __future__ import annotations
import argparse,csv,json,sqlite3,zipfile,tempfile,os,pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]

def rows(path):
 with (ROOT/'research'/path).open('r',encoding='utf8',newline='') as f:yield from csv.DictReader(f)

def build(out,source_skill=None):
 out=pathlib.Path(out);out.parent.mkdir(parents=True,exist_ok=True)
 if out.exists():out.unlink()
 c=sqlite3.connect(out);c.execute('PRAGMA foreign_keys=ON')
 c.executescript('''
 CREATE TABLE source_registry(source_id TEXT PRIMARY KEY,organization TEXT,source_url TEXT NOT NULL,role TEXT,rights_note TEXT,accessed TEXT);
 CREATE TABLE curricula(curriculum_id TEXT PRIMARY KEY,announced_year INTEGER,name TEXT,overview TEXT,source_id TEXT,first_full_csat_admission_year INTEGER,FOREIGN KEY(source_id) REFERENCES source_registry(source_id));
 CREATE TABLE csat_regimes(regime_id TEXT PRIMARY KEY,start_admission_year INTEGER,end_admission_year INTEGER,description TEXT,verification_status TEXT,features TEXT,source_id TEXT,FOREIGN KEY(source_id) REFERENCES source_registry(source_id));
 CREATE TABLE policy_events(policy_id INTEGER PRIMARY KEY,announcement_subject_year INTEGER,event TEXT,effective_admission_year INTEGER,scope TEXT,curriculum_id TEXT,published_date TEXT,source_id TEXT,details TEXT,FOREIGN KEY(source_id) REFERENCES source_registry(source_id));
 CREATE TABLE cohort_years(admission_year INTEGER PRIMARY KEY,test_calendar_year INTEGER,nominal_full_time_cohort_birth_year INTEGER,candidate_count INTEGER,actual_test_takers INTEGER,current_students INTEGER,repeat_test_takers INTEGER,current_student_share REAL,score_distribution_source TEXT,relative_ability TEXT,notes TEXT,regime TEXT,evidence_id TEXT,FOREIGN KEY(regime) REFERENCES csat_regimes(regime_id));
 CREATE TABLE csat_subject_scope(scope_id INTEGER PRIMARY KEY,from_admission_year INTEGER,to_admission_year INTEGER,area TEXT,selection_rule TEXT,subjects TEXT,source_id TEXT,FOREIGN KEY(source_id) REFERENCES source_registry(source_id));
 CREATE TABLE exam_catalog(exam_id INTEGER PRIMARY KEY,host_provider TEXT NOT NULL,source_page TEXT,record_id TEXT,calendar_year INTEGER,admission_year INTEGER,exam_month TEXT,grade TEXT,area TEXT,subject TEXT,title TEXT,host_record_url TEXT,original_rights_holder TEXT,exam_type TEXT,validation_status TEXT,rights_status TEXT);
 CREATE TABLE pdf_source_assets(asset_id INTEGER PRIMARY KEY,exam_id INTEGER,asset_type TEXT,remote_url TEXT,original_rights_holder TEXT,hosting_platform TEXT,rights_status TEXT,sha256 TEXT,FOREIGN KEY(exam_id) REFERENCES exam_catalog(exam_id));
 CREATE TABLE official_document_catalog(document_id INTEGER PRIMARY KEY,document_kind TEXT,title TEXT,year INTEGER,detail_url TEXT,file_url TEXT,publisher TEXT,rights_status TEXT);
 CREATE TABLE image_assets(image_id INTEGER PRIMARY KEY,exam_id INTEGER,question_no INTEGER,asset_kind TEXT,source_pdf_url TEXT,pdf_page_zero_based INTEGER,x0_norm REAL,y0_norm REAL,x1_norm REAL,y1_norm REAL,local_image_path TEXT,sha256 TEXT,rights_status TEXT NOT NULL,review_status TEXT NOT NULL DEFAULT 'pending',FOREIGN KEY(exam_id) REFERENCES exam_catalog(exam_id));
 CREATE INDEX idx_exam ON exam_catalog(admission_year,exam_month,grade,subject);
 CREATE INDEX idx_image_question ON image_assets(exam_id,question_no,asset_kind);
 CREATE INDEX idx_pdf_exam ON pdf_source_assets(exam_id);
 ''')
 with c:
  for r in json.loads((ROOT/'research'/'source_registry.json').read_text(encoding='utf8'))['sources']:
   c.execute('INSERT INTO source_registry VALUES(?,?,?,?,?,?)',(r['id'],r['organization'],r['url'],r['role'],r.get('rights_note'),r['accessed']))
  for r in rows('curricula.csv'):
   c.execute('INSERT INTO curricula VALUES(?,?,?,?,?,?)',(r['curriculum_id'],int(r['announced_year']),r['name'],r['overview'],r['source_id'],int(r['first_full_csAT_admission_year']) if r['first_full_csAT_admission_year'] else None))
  for r in rows('csat_regimes.csv'):
   c.execute('INSERT INTO csat_regimes VALUES(?,?,?,?,?,?,?)',(r['regime_id'],int(r['start_admission_year']),int(r['end_admission_year']),r['description'],r['verification_status'],r['features'],r['source_id']))
  for r in rows('policy_events.csv'):
   c.execute('INSERT INTO policy_events(announcement_subject_year,event,effective_admission_year,scope,curriculum_id,published_date,source_id,details) VALUES(?,?,?,?,?,?,?,?)',(int(r['announcement_subject_year']),r['event'],int(r['effective_admission_year']),r['scope'],r['curriculum_id'],r['published_date'],r['source_id'],r['details']))
  for r in rows('cohorts.csv'):
   c.execute('INSERT INTO cohort_years VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)',(int(r['admission_year']),int(r['test_calendar_year']),int(r['nominal_full_time_cohort_birth_year']),None,None,None,None,None,None,None,r['notes'],r['regime'],r['evidence_id']))
  for r in rows('csat_subject_scope.csv'):
   c.execute('INSERT INTO csat_subject_scope(from_admission_year,to_admission_year,area,selection_rule,subjects,source_id) VALUES(?,?,?,?,?,?)',(int(r['from_admission_year']),int(r['to_admission_year']),r['area'],r['selection_rule'],r['subjects'],r['source_id']))
 if source_skill:
  with zipfile.ZipFile(source_skill) as z:
   for f in ['data/ebsi_suneung.sqlite','data/official_kice.sqlite']:
    if f not in z.namelist():raise ValueError('Missing source archive member: '+f)
   with tempfile.TemporaryDirectory() as d:
    for src,dst in [('data/ebsi_suneung.sqlite','ebsi.sqlite'),('data/official_kice.sqlite','kice.sqlite')]:
     with z.open(src) as inf,open(pathlib.Path(d)/dst,'wb') as outfp:
      import shutil;shutil.copyfileobj(inf,outfp)
    eb=sqlite3.connect(str(pathlib.Path(d)/'ebsi.sqlite'))
    kc=sqlite3.connect(str(pathlib.Path(d)/'kice.sqlite'))
    with c:
     for rec in eb.execute('SELECT paper_no,record_id,year,month,grade,subject_group,subject,title,source_url FROM papers ORDER BY paper_no'):
      no,rid,year,month,grade,area,subj,title,url=rec
      # Header titles can describe a local education-authority paper too;
      # never infer KICE solely from its EBSi platform.
      kind=('모의평가' if ('모평' in (title or '') or '모의평가' in (title or '')) else ('대학수학능력시험' if '수능' in (title or '') else '학력평가/기타'))
      rights='KICE (subject to exam identification)' if ('평가원' in (title or '') or ('수능' in (title or '') and '모평' not in (title or ''))) else 'Original exam issuer (unverified)'
      c.execute('INSERT INTO exam_catalog(host_provider,source_page,record_id,calendar_year,admission_year,exam_month,grade,area,subject,title,host_record_url,original_rights_holder,exam_type,validation_status,rights_status) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',('EBSi','https://www.ebsi.co.kr/ebs/xip/xipc/previousPaperList.ebs?targetCd=D300',str(no),year,year+1 if year else None,month,grade,area,subj,title,url,rights,kind,'bibliography_only','source_rights_reserved'))
      exam_id=c.execute('SELECT last_insert_rowid()').fetchone()[0]
      for typ,src_url,sha in eb.execute('SELECT asset_type,url,sha256 FROM assets WHERE paper_no=?',(no,)):
       if not src_url or not src_url.startswith(('https://','http://')):continue
       c.execute('INSERT INTO pdf_source_assets(exam_id,asset_type,remote_url,original_rights_holder,hosting_platform,rights_status,sha256) VALUES(?,?,?,?,?,?,?)',(exam_id,typ,src_url,rights,'EBSi','external_link_only',sha))
     for typ,title,dt,fu,year in kc.execute('SELECT source_type,title,detail_url,file_url,year FROM documents'):
      c.execute('INSERT INTO official_document_catalog(document_kind,title,year,detail_url,file_url,publisher,rights_status) VALUES(?,?,?,?,?,?,?)',(typ,title,year,dt,fu,'KICE','external_link_only'))
    eb.close();kc.close()
 c.execute('PRAGMA optimize');c.close()
 print('Built:',out)
 c=sqlite3.connect(out)
 for table in ['source_registry','curricula','csat_regimes','policy_events','cohort_years','csat_subject_scope','exam_catalog','pdf_source_assets','official_document_catalog','image_assets']:
  print(table,c.execute('SELECT COUNT(*) FROM '+table).fetchone()[0])
 c.close()
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--source-skill',help='Original local skill zip for bibliographic ONLY import; never published');ap.add_argument('--out',default='workspace/research_catalog.sqlite');a=ap.parse_args();build(a.out,a.source_skill)
