#!/usr/bin/env python3
import argparse,re,sqlite3,subprocess,os,json
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path

def text_of(path):
 try:
  if not path or not os.path.exists(path) or not path.lower().endswith('.pdf'): return ''
  r=subprocess.run(['pdftotext','-layout',path,'-'],capture_output=True,text=True,timeout=90)
  return r.stdout if r.returncode==0 else ''
 except Exception:return ''
def answers(text):
 out={}
 # Restrict parsing to the compact answer-key area near the beginning;
 # later solution headings and choices must not overwrite the key.
 for line in text[:8000].splitlines():
  ms=list(re.finditer(r'(?<!\d)(\d{1,2})\s*[.)]\s*([①②③④⑤]|[1-5])',line))
  if len(ms)<3: continue
  for m in ms:
   n=int(m.group(1)); a=m.group(2); a=str('①②③④⑤'.index(a)+1) if a in '①②③④⑤' else a
   if 1<=n<=60 and n not in out: out[n]=a
 return out
def segments(text):
 # Keep bounded chunks beginning at question labels. Layout is source-dependent,
 # so retain source text rather than hallucinating a cleaner stem.
 ms=list(re.finditer(r'(?m)^\s*(\d{1,2})\s*[.)]\s+',text))
 out={}
 for i,m in enumerate(ms):
  n=int(m.group(1))
  if not 1<=n<=60:continue
  end=ms[i+1].start() if i+1<len(ms) else min(len(text),m.start()+5000)
  chunk=re.sub(r'\s+',' ',text[m.start():end]).strip()
  if len(chunk)>30 and n not in out:out[n]=chunk[:5000]
 return out
def parse(row):
 paper,year,subject,title,prob,expl,purl,eurl=row
 pt=text_of(prob);et=text_of(expl);aa=answers(et);ps=segments(pt);es=segments(et)
 nums=sorted(set(aa)|set(ps)|set(es));return paper,year,subject,title,purl,eurl,[(n,aa.get(n),ps.get(n,''),es.get(n,'')) for n in nums]
def main(a):
 root=Path(a.root);src=root/'data/ebsi_suneung.sqlite';db=root/'suneung_agent.sqlite';c=sqlite3.connect(src,timeout=60)
 rows=c.execute('''SELECT p.paper_no,p.year,p.subject,p.title,
 max(CASE WHEN a.asset_type='problem' THEN a.local_path END),
 max(CASE WHEN a.asset_type='explanation' THEN a.local_path END),
 max(CASE WHEN a.asset_type='problem' THEN a.url END),
 max(CASE WHEN a.asset_type='explanation' THEN a.url END)
 FROM papers p JOIN assets a ON a.paper_no=p.paper_no
 WHERE a.local_path IS NOT NULL GROUP BY p.paper_no
 HAVING max(CASE WHEN a.asset_type='problem' THEN a.local_path END) IS NOT NULL
     OR max(CASE WHEN a.asset_type='explanation' THEN a.local_path END) IS NOT NULL''').fetchall();c.close()
 print('[parse-start]',len(rows),flush=True);out=sqlite3.connect(db,timeout=60);out.execute('PRAGMA journal_mode=WAL');out.execute('BEGIN')
 total=0;done=0
 with ThreadPoolExecutor(max_workers=a.workers) as ex:
  fs=[ex.submit(parse,r) for r in rows]
  for f in as_completed(fs):
   paper,year,subject,title,purl,eurl,items=f.result();er=out.execute('select exam_id from exams where paper_no=?',(paper,)).fetchone();
   if not er:continue
   eid=er[0]
   for n,ans,stem,sol in items:
    out.execute('''INSERT INTO question_items(exam_id,question_no,subquestion_no,domain,stem_text,choices_json,answer,correct_rate,difficulty,solution_text,source_url,source_id)
                    VALUES(?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(exam_id,question_no,subquestion_no) DO UPDATE SET stem_text=excluded.stem_text,answer=excluded.answer,solution_text=excluded.solution_text,source_url=excluded.source_url''',
                (eid,n,'',subject,stem,'',ans,None,None,sol,purl or eurl,1));total+=1
   done+=1
   if done%a.commit_every==0:out.commit();print(f'[parse] exams={done}/{len(rows)} items={total}',flush=True)
 out.commit();print('[parse-complete]',done,total,flush=True);out.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='workspace');p.add_argument('--workers',type=int,default=8);p.add_argument('--commit-every',type=int,default=25);main(p.parse_args())
