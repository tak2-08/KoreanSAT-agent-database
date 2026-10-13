#!/usr/bin/env python3
"""Download public EBSi historical papers and normalize metadata/statistics.

Uses EBSi's public list/Ajax endpoints and file URLs exposed by the website.
It does not bypass authentication or protected resources. The SQLite manifest
makes the large download resumable and records HTTP status/checksums.
"""
from __future__ import annotations
import argparse, hashlib, json, re, sqlite3, sys, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin
import requests
from bs4 import BeautifulSoup

BASE='https://www.ebsi.co.kr'
FILE_BASE='https://wdown.ebsi.co.kr/W61001/01exam'
LIST_PAGE='/ebs/xip/xipc/previousPaperList.ebs?targetCd={target}'
LIST_AJAX='/ebs/xip/xipc/previousPaperListAjax.ajax'
GRD_AJAX='/ebs/xip/xipc/previousGrdCutPopupListAjax.ajax'
WRONG_AJAX='/ebs/xip/xipc/previousWrongRatePopupList.ajax'

def now(): return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
def sha(b): return hashlib.sha256(b).hexdigest()
def clean(s): return re.sub(r'\s+',' ',(s or '').replace('\xa0',' ')).strip()
def j(v): return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'))
def file_url(path): return FILE_BASE + path if path.startswith('/') else urljoin(FILE_BASE+'/',path)

def schema(c):
 c.executescript('''
 CREATE TABLE IF NOT EXISTS runs(run_id TEXT PRIMARY KEY,started_at TEXT,finished_at TEXT,status TEXT,args_json TEXT);
 CREATE TABLE IF NOT EXISTS papers(paper_no TEXT PRIMARY KEY,record_id TEXT,year INTEGER,month TEXT,grade TEXT,subject_group TEXT,subject TEXT,title TEXT,exam_date TEXT,source_url TEXT,metadata_json TEXT,first_seen_at TEXT,last_seen_at TEXT);
 CREATE TABLE IF NOT EXISTS assets(asset_id INTEGER PRIMARY KEY AUTOINCREMENT,paper_no TEXT,asset_type TEXT,url TEXT,local_path TEXT,http_status INTEGER,content_type TEXT,bytes INTEGER,sha256 TEXT,downloaded_at TEXT,error TEXT,UNIQUE(paper_no,asset_type,url));
 CREATE TABLE IF NOT EXISTS grade_cuts(id INTEGER PRIMARY KEY AUTOINCREMENT,paper_no TEXT,exam_code TEXT,subject_code TEXT,grade_flag TEXT,year INTEGER,title TEXT,subject TEXT,html TEXT,text TEXT,fetched_at TEXT,UNIQUE(paper_no,subject_code));
 CREATE TABLE IF NOT EXISTS wrong_rates(id INTEGER PRIMARY KEY AUTOINCREMENT,paper_no TEXT,record_id TEXT,year INTEGER,title TEXT,html TEXT,text TEXT,fetched_at TEXT,UNIQUE(paper_no));
 CREATE TABLE IF NOT EXISTS reviews(id INTEGER PRIMARY KEY AUTOINCREMENT,record_id TEXT,target_cd TEXT,year INTEGER,title TEXT,url TEXT,html TEXT,text TEXT,fetched_at TEXT,UNIQUE(record_id,target_cd));
 CREATE TABLE IF NOT EXISTS crawl_errors(id INTEGER PRIMARY KEY AUTOINCREMENT,run_id TEXT,stage TEXT,key_value TEXT,error TEXT,occurred_at TEXT);
 CREATE INDEX IF NOT EXISTS idx_papers_exam ON papers(year,month,grade,subject);
 CREATE INDEX IF NOT EXISTS idx_assets_type ON assets(asset_type);
 '''); c.commit()

def parse_call(x, fn):
 m=re.search(rf'{fn}\((.*?)\)',x or '')
 if not m:return []
 # quoted strings, including URLs, and unquoted scalar values
 return [v1 or v2 for v1,v2 in re.findall(r"'([^']*)'|\"([^\"]*)\"|([^,]+)",m.group(1))]

def call_args(x,fn):
 m=re.search(rf'{fn}\((.*?)\)',x or '')
 if not m:return []
 parts=[]; cur=''; quote=None
 for ch in m.group(1):
  if ch in "'\"": quote=None if quote==ch else (ch if quote is None else quote)
  if ch==',' and quote is None: parts.append(cur.strip().strip("'\""));cur=''
  else:cur+=ch
 parts.append(cur.strip().strip("'\"")); return parts

def parse_items(html, target, source_url):
 s=BeautifulSoup(html,'html.parser'); out=[]
 for a in s.select('[onclick*="goDownLoadP("]'):
  p=call_args(a.get('onclick'),'goDownLoadP')
  if len(p)<9: continue
  box=a.find_parent(class_='qus_box') or a.find_parent('li') or a.parent
  txt=clean(box.get_text(' ',strip=True))
  title=clean((box.select_one('.qus_tit').get_text(' ',strip=True) if box.select_one('.qus_tit') else txt))
  # metadata from visible flag fields
  flags=[clean(x.get_text(' ',strip=True)) for x in box.select('.qus_flag span')]
  yr=int(flags[0]) if flags and flags[0].isdigit() else None
  month=flags[1] if len(flags)>1 else None
  subject_group=flags[2] if len(flags)>2 else None
  # p: path, save folder, record id, ar order, subject code, level, base, paper id
  cut_args=[]; wrong_args=[]
  for node in box.select('[onclick]'):
   oc=node.get('onclick','')
   if 'showGrdCutPopup' in oc: cut_args=call_args(oc,'showGrdCutPopup')
   if 'showWrongRatePopup' in oc: wrong_args=call_args(oc,'showWrongRatePopup')
  item={'paper_no':p[8],'record_id':p[2],'year':yr,'month':month,'grade':('고3' if '고3' in title else '고2' if '고2' in title else '고1' if '고1' in title else None),'subject_group':subject_group,'subject':title.split()[-1] if title else None,'title':title,'exam_date':None,'source_url':source_url,'metadata':{'flags':flags,'text':txt,'download_args':p,'grade_cut_args':cut_args,'wrong_rate_args':wrong_args}}
  assets={'problem':file_url(p[0])}
  # nearby buttons contain answer/explanation
  for node in box.select('[onclick]'):
   oc=node.get('onclick',''); label=clean(node.get_text(' ',strip=True))
   if 'goDownLoadJ(' in oc:
    q=call_args(oc,'goDownLoadJ');
    if q: assets['answer']=q[0]
   elif 'goDownLoadH(' in oc:
    q=call_args(oc,'goDownLoadH');
    if q: assets['explanation']=file_url(q[0])
  item['assets']=assets; out.append(item)
 # unique by paper no
 return {x['paper_no']:x for x in out}

def upsert_paper(c,item):
 t=now(); c.execute('''INSERT INTO papers VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(paper_no) DO UPDATE SET
 record_id=excluded.record_id,year=excluded.year,month=excluded.month,grade=excluded.grade,subject_group=excluded.subject_group,subject=excluded.subject,title=excluded.title,source_url=excluded.source_url,metadata_json=excluded.metadata_json,last_seen_at=excluded.last_seen_at''',
 (item['paper_no'],item['record_id'],item['year'],item['month'],item['grade'],item['subject_group'],item['subject'],item['title'],item['exam_date'],item['source_url'],j(item['metadata']),t,t))
 for typ,u in item['assets'].items():
  c.execute('INSERT OR IGNORE INTO assets(paper_no,asset_type,url) VALUES(?,?,?)',(item['paper_no'],typ,u))

def download(c,item,out,session,delay):
 for typ,u in item['assets'].items():
  row=c.execute('SELECT asset_id,local_path,sha256 FROM assets WHERE paper_no=? AND asset_type=? AND url=?',(item['paper_no'],typ,u)).fetchone()
  if row and row[1] and row[2] and Path(row[1]).exists(): continue
  try:
   time.sleep(delay); r=session.get(u,timeout=60,stream=True); data=r.content
   ext=Path(u.split('?')[0]).suffix or '.bin'; folder=out/'files'/str(item['year'] or 'unknown')/re.sub(r'[^\w.-]+','_',item['title'][:80])
   folder.mkdir(parents=True,exist_ok=True); path=folder/f'{typ}_{item["paper_no"]}{ext}'; path.write_bytes(data)
   c.execute('UPDATE assets SET local_path=?,http_status=?,content_type=?,bytes=?,sha256=?,downloaded_at=?,error=NULL WHERE paper_no=? AND asset_type=? AND url=?',(str(path),r.status_code,r.headers.get('content-type'),len(data),sha(data),now(),item['paper_no'],typ,u)); c.commit()
  except Exception as e:
   c.execute('UPDATE assets SET error=?,downloaded_at=? WHERE paper_no=? AND asset_type=? AND url=?',(str(e),now(),item['paper_no'],typ,u)); c.commit()

def fetch_stats(c,items,session,delay):
 for idx,item in enumerate(items.values(),1):
  m=item['metadata']; ca=m.get('grade_cut_args',[]); wa=m.get('wrong_rate_args',[])
  try:
   if len(ca)>=6:
    r=session.post(BASE+GRD_AJAX,data={'examCd':ca[0],'naatSubjCd':ca[1],'stdntGrd':ca[2],'title':ca[4],'subjNm':ca[5]},timeout=45); h=r.text; s=BeautifulSoup(h,'html.parser'); c.execute('INSERT OR REPLACE INTO grade_cuts(paper_no,exam_code,subject_code,grade_flag,year,title,subject,html,text,fetched_at) VALUES(?,?,?,?,?,?,?,?,?,?)',(item['paper_no'],ca[0],ca[1],ca[2],item['year'],ca[4],ca[5],h,clean(s.get_text(' ',strip=True)),now()))
   if len(wa)>=5:
    r=session.post(BASE+WRONG_AJAX,data={'irecord':wa[0],'paperId':wa[1],'year':wa[2],'title':wa[4]},timeout=45); h=r.text; s=BeautifulSoup(h,'html.parser'); c.execute('INSERT OR REPLACE INTO wrong_rates(paper_no,record_id,year,title,html,text,fetched_at) VALUES(?,?,?,?,?,?,?)',(item['paper_no'],item['record_id'],item['year'],wa[4],h,clean(s.get_text(' ',strip=True)),now()))
  except Exception as e: c.execute('INSERT INTO crawl_errors VALUES(NULL,?,?,?,?,?)',(None,'stats',item['paper_no'],str(e),now()))
  c.commit()
  if idx==1 or idx%100==0: print(f'[stats] {idx}/{len(items)}',flush=True)

def fetch_reviews(c,items,session,delay):
 seen=set()
 for item in items.values():
  key=(item['record_id'], 'D300' if item['grade']=='고3' else 'D200' if item['grade']=='고2' else 'D100')
  if key in seen: continue
  seen.add(key); record,target=key
  try:
   time.sleep(delay); u=BASE+f'/ebs/xip/xipa/retrieveSCVMainInfo.ebs?irecord={record}&targetCd={target}'; r=session.get(u,timeout=45); h=r.text; s=BeautifulSoup(h,'html.parser'); c.execute('INSERT OR REPLACE INTO reviews(record_id,target_cd,year,title,url,html,text,fetched_at) VALUES(?,?,?,?,?,?,?,?)',(record,target,item['year'],item['title'],u,h,clean(s.get_text(' ',strip=True)),now()))
  except Exception as e: c.execute('INSERT INTO crawl_errors VALUES(NULL,?,?,?,?,?)',(None,'review',record,str(e),now()))
  c.commit()

def main(a):
 out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True); db=out/'ebsi_suneung.sqlite'; c=sqlite3.connect(db); schema(c)
 run=hashlib.sha1(f'{time.time()}'.encode()).hexdigest();c.execute('INSERT INTO runs VALUES(?,?,?,?,?)',(run,now(),None,'running',j(vars(a))));c.commit()
 s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; EBSi-public-archive/1.0)','Referer':BASE+'/ebs/xip/xipc/previousPaperList.ebs?targetCd=D300'})
 all_items={}; targets=[('D300','고3'),('D200','고2'),('D100','고1')]
 try:
  for target,_grade in targets:
   # HTML page supplies stable filter form defaults.
   page=s.get(BASE+LIST_PAGE.format(target=target),timeout=45).text; ps=BeautifulSoup(page,'html.parser'); form=ps.select_one('form[name=paperListFrm]')
   base={'targetCd':target,'yearList':','.join(x.get('value','') for x in ps.select('input[name=year]')),'monthList':','.join(x.get('value','') for x in ps.select('input[name=month]')),'arOrd':'1,2,3,4,5,,6,7,8','subjIdList':'firstEnter','sort':'recent','paperId':'','paperNo':'','lvl':''}
   # Iterate until no records. EBSi currently reports 4950+ records; each page is small.
   for page_no in range(1,a.max_pages+1):
    payload={**base,'currentPage':str(page_no)}; time.sleep(a.delay); r=s.post(BASE+LIST_AJAX,data=payload,timeout=60); html=r.text; items=parse_items(html,target,BASE+LIST_PAGE.format(target=target));
    if not items: break
    before=len(all_items);all_items.update(items)
    if page_no==1 or page_no%25==0: print(f'[list] target={target} page={page_no} page_items={len(items)} unique={len(all_items)}',flush=True)
    # Stop when page repeats no new item or page clearly lacks records.
    if len(all_items)==before: break
   
  print(f'[inventory] unique_papers={len(all_items)}',flush=True)
  for idx,item in enumerate(all_items.values(),1):
   upsert_paper(c,item)
   if not a.metadata_only: download(c,item,out,s,a.delay)
   if idx==1 or idx%25==0 or idx==len(all_items): print(f'[assets] {idx}/{len(all_items)}',flush=True)
  if not a.metadata_only:
   fetch_stats(c,all_items,s,a.delay)
   fetch_reviews(c,all_items,s,a.delay)
  c.execute('UPDATE runs SET finished_at=?,status=? WHERE run_id=?',(now(),'completed',run));c.commit()
 except Exception as e:
  c.execute('UPDATE runs SET finished_at=?,status=? WHERE run_id=?',(now(),'failed',run));c.execute('INSERT INTO crawl_errors VALUES(NULL,?,?,?,?,?)',(run,'main','',str(e),now()));c.commit();raise
 finally:c.close()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default='workspace/data');p.add_argument('--delay',type=float,default=.25);p.add_argument('--max-pages',type=int,default=1000);p.add_argument('--metadata-only',action='store_true');main(p.parse_args())
