#!/usr/bin/env python3
import argparse,sqlite3,re,json

def norm(s):
 s=(s or '').lower().replace(' ','').replace('·','').replace('ㆍ','')
 for a,b in [('Ⅰ','i'),('Ⅱ','ii'),('Ⅲ','iii'),('Ⅳ','iv'),('Ⅴ','v'),('Ⅵ','vi')]:s=s.replace(a,b)
 return s
ALIASES={'화법과작문':'작문','언어와매체':'매체','확률과통계':'통계','사회문화':'사회문화','사회·문화':'사회문화','생활과윤리':'생활과윤리','생명과학i':'생명과학i','생명과학ii':'생명과학ii','물리학i':'물리학i','물리학ii':'물리학ii','지구과학i':'지구과학i','지구과학ii':'지구과학ii','화학i':'화학i','화학ii':'화학ii','한문i':'한문i'}
def subj(s):
 n=norm(s);return ALIASES.get(n,n)
def month(s):
 s=s or ''
 dm=re.search(r'^\d{4}[-./](\d{1,2})',s)
 if dm:return int(dm.group(1))
 m=re.search(r'(\d{1,2})',s);return int(m.group(1)) if m else None
def main(a):
 out=sqlite3.connect(a.out,timeout=120);mega=sqlite3.connect(a.mega,timeout=60)
 out.execute('PRAGMA journal_mode=WAL')
 out.executescript('''CREATE TABLE IF NOT EXISTS mega_exams(exam_seq INTEGER PRIMARY KEY,grade_flag TEXT,grade_name TEXT,exam_name TEXT,exam_date TEXT,exam_kind TEXT,first_seen_at TEXT,last_seen_at TEXT);CREATE TABLE IF NOT EXISTS mega_answer_rates(exam_seq INTEGER,tab_no INTEGER,tab_name TEXT,subject_group TEXT,subject_name TEXT,subject_code TEXT,question_no INTEGER,correct_answer TEXT,difficulty TEXT,points REAL,correct_rate_pct REAL,choice_rates_json TEXT,raw_cells_json TEXT,source_url TEXT,fetched_at TEXT,PRIMARY KEY(exam_seq,tab_no,subject_name,question_no));CREATE TABLE IF NOT EXISTS mega_cut_scores(exam_seq INTEGER,tab_no INTEGER,tab_name TEXT,subject_name TEXT,grade_label TEXT,original_score REAL,standard_score REAL,percentile REAL,cumulative_pct REAL,raw_cells_json TEXT,source_url TEXT,fetched_at TEXT,PRIMARY KEY(exam_seq,tab_no,subject_name,grade_label));CREATE TABLE IF NOT EXISTS megastudy_exam_links(exam_seq INTEGER,exam_id INTEGER,match_key TEXT,confidence REAL,PRIMARY KEY(exam_seq,exam_id));CREATE TABLE IF NOT EXISTS cut_scores(exam_seq INTEGER,exam_id INTEGER,tab_no INTEGER,tab_name TEXT,subject_name TEXT,grade_label TEXT,original_score REAL,standard_score REAL,percentile REAL,cumulative_pct REAL,raw_cells_json TEXT,source_url TEXT,fetched_at TEXT,source TEXT,PRIMARY KEY(exam_seq,tab_no,subject_name,grade_label));''')
 for r in mega.execute('select * from exams'):out.execute('insert or replace into mega_exams values(?,?,?,?,?,?,?,?)',r)
 for r in mega.execute('select * from answer_rates'):out.execute('insert or replace into mega_answer_rates values(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',r)
 for r in mega.execute('select * from cut_scores'):out.execute('insert or replace into mega_cut_scores values(?,?,?,?,?,?,?,?,?,?,?,?)',r)
 # Preserve provenance on question rows.
 for col in ['answer_source','correct_rate_source','mega_exam_seq']:
  try:out.execute(f'alter table question_items add column {col} TEXT')
  except sqlite3.OperationalError:pass
 # Map EBSi exam to Mega by year/month/grade/subject canonical. Use exact date month and grade.
 papers=out.execute('select exam_id,year,month,grade,subject from exams').fetchall()
 mex=out.execute('select exam_seq,grade_name,exam_date,exam_kind from mega_exams').fetchall()
 links=[]
 for eid,y,mo,g,s in papers:
  mm=month(mo); cand=[x for x in mex if str(y)==(x[2] or '')[:4] and month(x[2])==mm and (not g or x[1]==g)]
  # An EBSi paper subject is a subtest; link to candidate exam, subject match is applied later.
  for seq,gg,dt,kind in cand:
   links.append((seq,eid,f'{y}-{mm}-{g}',0.8))
 for r in links:out.execute('insert or replace into megastudy_exam_links values(?,?,?,?)',r)
 # Build lookup of EBSi exam IDs by candidate mega exam and normalized subject.
 eidx={}
 for seq,eid,_,_ in links:
  y,mo,g,s=out.execute('select year,month,grade,subject from exams where exam_id=?',(eid,)).fetchone()
  eidx[(seq,subj(s))]=eid
 # Update answers/rates only on a unique subject match.
 updated=0
 for r in out.execute('select exam_seq,subject_name,question_no,correct_answer,correct_rate_pct from mega_answer_rates'):
  seq,sn,qn,ans,rate=r;eid=eidx.get((seq,subj(sn)))
  if not eid:continue
  out.execute('''update question_items set answer=coalesce(?,answer),correct_rate=coalesce(?,correct_rate),answer_source=case when ? is not null then 'megastudy' else answer_source end,correct_rate_source=case when ? is not null then 'megastudy' else correct_rate_source end,mega_exam_seq=? where exam_id=? and question_no=?''',(ans,rate,ans,rate,seq,eid,qn));updated+=out.total_changes
 # Normalize cut scores and link when subject maps.
 for r in out.execute('select exam_seq,tab_no,tab_name,subject_name,grade_label,original_score,standard_score,percentile,cumulative_pct,raw_cells_json,source_url,fetched_at from mega_cut_scores'):
  seq,tab,tn,sn,gl,oscore,ss,perc,cum,raw,url,ft=r
  eid=eidx.get((seq,subj(sn)))
  out.execute('insert or replace into cut_scores values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)',(seq,eid,tab,tn,sn,gl,oscore,ss,perc,cum,raw,url,ft,'megastudy'))
 out.commit();print('mega_exams',out.execute('select count(*) from mega_exams').fetchone()[0]);print('mega_answer_rates',out.execute('select count(*) from mega_answer_rates').fetchone()[0]);print('mega_cut_scores',out.execute('select count(*) from mega_cut_scores').fetchone()[0]);print('links',out.execute('select count(*) from megastudy_exam_links').fetchone()[0]);print('question answers',out.execute("select count(*) from question_items where answer_source='megastudy'").fetchone()[0]);print('question rates',out.execute("select count(*) from question_items where correct_rate_source='megastudy'").fetchone()[0]);print('linked cuts',out.execute('select count(*) from cut_scores where exam_id is not null').fetchone()[0]);out.close();mega.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default='workspace/suneung_agent.sqlite');p.add_argument('--mega',default='workspace/megastudy/megastudy_suneung_tutor.sqlite');main(p.parse_args())
