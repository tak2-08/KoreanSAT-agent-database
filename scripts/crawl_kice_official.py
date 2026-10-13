#!/usr/bin/env python3
import argparse,hashlib,re,sqlite3,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
from urllib.parse import urljoin,urlparse
import requests
from bs4 import BeautifulSoup

BASE='https://www.suneung.re.kr'
BOARDS=[
 ('press_releases','1500230','0302','수능 보도자료'),
 ('reports','1500233','0402','수능관련 보고서'),
 ('papers_current','1500234','0403','대학수학능력시험 기출문제'),
 ('papers_old','1500235','0403','수능 2004학년도 이전'),
 ('mock_papers','1500236','0403','수능 모의평가'),
 ('plans_old','5000103','0406','수능시행계획 2001학년도 이전'),
]
RESOURCES=[('study_guides','https://www.suneung.re.kr/sub/info.do?m=0401&s=suneung','수험자료')]
def clean(x):return re.sub(r'\s+',' ',(x or '').replace('\xa0',' ')).strip()
def now():
 from datetime import datetime,timezone
 return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
def init(c):
 c.executescript('''CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY AUTOINCREMENT,source_type TEXT,title TEXT,detail_url TEXT,file_url TEXT,year INTEGER,description TEXT,metadata_json TEXT,discovered_at TEXT,UNIQUE(source_type,title,detail_url,file_url));CREATE TABLE IF NOT EXISTS files(id INTEGER PRIMARY KEY AUTOINCREMENT,document_id INTEGER,file_url TEXT,local_path TEXT,status INTEGER,content_type TEXT,bytes INTEGER,sha256 TEXT,error TEXT,downloaded_at TEXT,UNIQUE(file_url));CREATE TABLE IF NOT EXISTS pages(source_type TEXT,url TEXT,html TEXT,fetched_at TEXT,UNIQUE(source_type,url));CREATE INDEX IF NOT EXISTS idx_documents_type ON documents(source_type);''');c.commit()
def page_url(board,m,pg):return f'{BASE}/boardCnts/list.do?boardID={board}&m={m}&s=suneung&searchStr=&pg={pg}'
def parse_page(html,source,url):
 s=BeautifulSoup(html,'html.parser'); out=[]
 for a in s.select('a[href*="fileDown.do"]'):
  fu=urljoin(BASE,a.get('href','')); title=''; node=a
  for _ in range(5):
   node=node.parent if node else None
   if not node:break
   t=clean(node.get_text(' ',strip=True))
   if len(t)>10:title=t;break
  if not title:title=clean(a.get('title',''))
  # remove generic labels
  title=re.sub(r'PDF 보기|다운로드|첨부파일','',title).strip()
  out.append({'source_type':source,'title':title[:500],'detail_url':url,'file_url':fu,'description':clean(s.get_text(' ',strip=True))[:1000]})
 # Many KICE boards expose attachments only on the detail page.
 for a in s.select('a[onclick*="goView"]'):
  oc=a.get('onclick',''); m=re.search(r"goView\('([^']+)'\s*,\s*'([^']+)'[^)]*\)",oc)
  if m:
   detail=urljoin(BASE,f'/boardCnts/view.do?boardID={m.group(1)}&boardSeq={m.group(2)}&lev=0&m={"0302" if source=="press_releases" else "0402"}&searchType=S&statusYN=N&page=1&s=suneung')
   out.append({'source_type':source,'title':clean(a.get_text(' ',strip=True))[:500],'detail_url':detail,'file_url':'','description':''})
 return out
def parse_detail(html,source,url,title):
 s=BeautifulSoup(html,'html.parser');out=[]
 for a in s.select('a[href*="fileDown.do"]'):
  out.append({'source_type':source,'title':title or clean(a.get_text(' ',strip=True)),'detail_url':url,'file_url':urljoin(BASE,a.get('href','')),'description':clean(s.get_text(' ',strip=True))[:1000]})
 return out
def discover_board(source,board,m,max_pages,delay):
 s=requests.Session();s.headers['User-Agent']='Mozilla/5.0 (compatible; KICE-public-archive/1.0)'; docs=[];seen=set(); empty=0
 for pg in range(1,max_pages+1):
  u=page_url(board,m,pg)
  try:r=s.get(u,timeout=20,verify=True);h=r.text
  except Exception as e:print('[page-error]',source,pg,e,flush=True);continue
  items=parse_page(h,source,u); detail_items=[x for x in items if not x['file_url']]
  for di in detail_items:
   try:
    dh=s.get(di['detail_url'],timeout=20,verify=True).text; items.extend(parse_detail(dh,source,di['detail_url'],di['title']))
   except Exception as e: print('[detail-error]',source,e,flush=True)
  sig=tuple(x['file_url'] for x in items if x['file_url'])
  if not items:empty+=1
  else:empty=0
  for x in items:
   if x['file_url'] and x['file_url'] not in seen:seen.add(x['file_url']);docs.append(x)
  if pg==1 or pg%10==0:print(f'[discover] {source} page={pg} page_docs={len(items)} unique={len(docs)}',flush=True)
  if empty>=2 or (pg>1 and sig and sig==lastsig):break
  lastsig=sig;time.sleep(delay)
 return docs
def discover_resource(source,url,title):
 s=requests.Session();s.headers['User-Agent']='Mozilla/5.0';r=s.get(url,timeout=20,verify=True); soup=BeautifulSoup(r.text,'html.parser');out=[]
 for a in soup.select('a[href*="fileDown.do"]'):
  fu=urljoin(BASE,a.get('href','')); out.append({'source_type':source,'title':clean(a.get_text(' ',strip=True)) or title,'detail_url':url,'file_url':fu,'description':clean(a.parent.get_text(' ',strip=True))[:1000]})
 return out
def dl(row,root,attempts):
 fid,docid,fu=row
 for k in range(attempts):
  try:
   r=requests.get(fu,headers={'User-Agent':'Mozilla/5.0 (compatible; KICE-public-archive/1.0)'},timeout=90);data=r.content
   if r.status_code!=200 or len(data)<100:raise RuntimeError(f'HTTP {r.status_code} bytes={len(data)}')
   ext=Path(urlparse(fu).path).suffix or '.bin'; folder=Path(root)/'files';folder.mkdir(parents=True,exist_ok=True);path=folder/f'kice_{docid}_{fid}{ext}';path.write_bytes(data)
   return fid,str(path),r.status_code,r.headers.get('content-type'),len(data),hashlib.sha256(data).hexdigest(),None
  except Exception as e:err=str(e);time.sleep(1+k)
 return fid,None,None,None,None,None,err
def main(a):
 root=Path(a.out).resolve();root.mkdir(parents=True,exist_ok=True);db=root/'official_kice.sqlite';c=sqlite3.connect(db,timeout=60);init(c);docs=[]
 for x in BOARDS:docs+=discover_board(*x[:3],a.max_pages,a.delay)
 for x in RESOURCES:docs+=discover_resource(*x)
 print('[discovery-final]',len(docs),flush=True)
 for d in docs:
  c.execute('INSERT OR IGNORE INTO documents(source_type,title,detail_url,file_url,description,discovered_at) VALUES(?,?,?,?,?,?)',(d['source_type'],d['title'],d['detail_url'],d['file_url'],d['description'],now()))
 c.commit();
 rows=c.execute('SELECT f.id,d.id,f.file_url FROM files f JOIN documents d ON d.id=f.document_id WHERE f.local_path IS NULL').fetchall()
 # create file rows for documents
 for d in c.execute('SELECT id,file_url FROM documents').fetchall():c.execute('INSERT OR IGNORE INTO files(document_id,file_url) VALUES(?,?)',(d[0],d[1]))
 c.commit();rows=c.execute('SELECT f.id,f.document_id,f.file_url FROM files f WHERE f.local_path IS NULL').fetchall();print('[download-start]',len(rows),flush=True)
 with ThreadPoolExecutor(max_workers=a.workers) as ex:
  fs=[ex.submit(dl,r,root,a.attempts) for r in rows]
  for i,f in enumerate(as_completed(fs),1):
   fid,path,status,ct,n,h,e=f.result();c.execute('UPDATE files SET local_path=?,status=?,content_type=?,bytes=?,sha256=?,error=?,downloaded_at=? WHERE id=?',(path,status,ct,n,h,e,now(),fid))
   if i%25==0 or i==len(rows):c.commit();print(f'[download] {i}/{len(rows)} errors={c.execute("select count(*) from files where error is not null").fetchone()[0]}',flush=True)
 c.commit();print('[done]',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default='workspace/data');p.add_argument('--workers',type=int,default=20);p.add_argument('--attempts',type=int,default=2);p.add_argument('--max-pages',type=int,default=300);p.add_argument('--delay',type=float,default=.1);main(p.parse_args())
