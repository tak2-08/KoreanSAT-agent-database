#!/usr/bin/env python3
import argparse,hashlib,sqlite3,time
from concurrent.futures import ThreadPoolExecutor,as_completed
from pathlib import Path
import requests

def now():
 from datetime import datetime,timezone
 return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
def is_network_error(err):
 if not err:return False
 return not (str(err).startswith('HTTP 404') or 'HTTP 404' in str(err))
def fetch(row,root,attempts,timeout):
 aid,paper,typ,url,year,title=row;last=''
 for k in range(attempts):
  try:
   r=requests.get(url,headers={'User-Agent':'Mozilla/5.0 (compatible; EBSi-public-archive/1.2)'},timeout=(20,timeout));data=r.content
   if r.status_code!=200 or len(data)<100:raise RuntimeError(f'HTTP {r.status_code}, bytes={len(data)}')
   folder=Path(root)/'files'/str(year or 'unknown')
   folder.mkdir(parents=True,exist_ok=True);ext=Path(url.split('?')[0]).suffix or '.bin';path=folder/f'{typ}_{paper}{ext}';path.write_bytes(data)
   return aid,str(path),r.status_code,r.headers.get('content-type'),len(data),hashlib.sha256(data).hexdigest(),None
  except Exception as e:last=str(e);time.sleep(1+k)
 return aid,None,None,None,None,None,last
def main(a):
 root=Path(a.out);db=root/'ebsi_suneung.sqlite';c=sqlite3.connect(db,timeout=60);c.execute('PRAGMA journal_mode=WAL')
 rows=c.execute("SELECT a.asset_id,a.paper_no,a.asset_type,a.url,p.year,p.title FROM assets a JOIN papers p ON p.paper_no=a.paper_no WHERE a.error IS NOT NULL AND a.error NOT LIKE '%HTTP 404%' AND a.error NOT LIKE '%HTTP 404,%'").fetchall()
 print(f'[retry-start] network_errors={len(rows)}',flush=True);ok=bad=0
 with ThreadPoolExecutor(max_workers=a.workers) as ex:
  fs=[ex.submit(fetch,r,root,a.attempts,a.timeout) for r in rows]
  for i,f in enumerate(as_completed(fs),1):
   aid,path,status,ct,n,h,e=f.result();c.execute('UPDATE assets SET local_path=?,http_status=?,content_type=?,bytes=?,sha256=?,downloaded_at=?,error=? WHERE asset_id=?',(path,status,ct,n,h,now(),e,aid))
   ok+=not bool(e);bad+=bool(e)
   if i%10==0 or i==len(rows):c.commit();print(f'[retry] {i}/{len(rows)} ok={ok} errors={bad}',flush=True)
 c.commit();print('[retry-complete]',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--out',default='workspace/data');p.add_argument('--workers',type=int,default=20);p.add_argument('--attempts',type=int,default=3);p.add_argument('--timeout',type=int,default=45);main(p.parse_args())
