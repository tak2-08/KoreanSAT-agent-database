#!/usr/bin/env python3
import argparse,json,sqlite3,shutil
from pathlib import Path
from datetime import datetime,timezone

def now():return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')
def main(a):
 root=Path(a.root);out=root/'suneung_agent.sqlite';ebsi=root/'data/ebsi_suneung.sqlite';kice=root/'data/kice_official/official_kice.sqlite'
 if out.exists():out.unlink()
 c=sqlite3.connect(out);c.executescript('''PRAGMA journal_mode=WAL;CREATE TABLE sources(source_id INTEGER PRIMARY KEY,source_name TEXT UNIQUE,authority TEXT,base_url TEXT);CREATE TABLE exams(exam_id INTEGER PRIMARY KEY,source_id INTEGER,paper_no TEXT,year INTEGER,month TEXT,grade TEXT,subject_group TEXT,subject TEXT,title TEXT,exam_date TEXT,source_url TEXT,metadata_json TEXT);CREATE TABLE assets(asset_id INTEGER PRIMARY KEY,exam_id INTEGER,source_id INTEGER,asset_type TEXT,url TEXT,local_path TEXT,http_status INTEGER,content_type TEXT,bytes INTEGER,sha256 TEXT,error TEXT);CREATE TABLE question_items(item_id INTEGER PRIMARY KEY,exam_id INTEGER NOT NULL,question_no INTEGER NOT NULL,subquestion_no TEXT,domain TEXT,stem_text TEXT,choices_json TEXT,answer TEXT,correct_rate REAL,difficulty TEXT,solution_text TEXT,source_url TEXT,source_id INTEGER,UNIQUE(exam_id,question_no,subquestion_no));CREATE TABLE official_docs(doc_id INTEGER PRIMARY KEY,source_id INTEGER,source_type TEXT,title TEXT,detail_url TEXT,file_url TEXT,local_path TEXT,content_type TEXT,bytes INTEGER,sha256 TEXT,error TEXT,description TEXT);CREATE TABLE relations(relation_id INTEGER PRIMARY KEY,from_type TEXT,from_id INTEGER,rel TEXT,to_type TEXT,to_id INTEGER,confidence REAL,notes TEXT);CREATE TABLE texts(text_id INTEGER PRIMARY KEY,entity_type TEXT,entity_id INTEGER,title TEXT,body TEXT,source_id INTEGER);CREATE VIRTUAL TABLE texts_fts USING fts5(title,body,content=texts,content_rowid=text_id);CREATE INDEX idx_exams_year_subject ON exams(year,subject);CREATE INDEX idx_assets_exam ON assets(exam_id);CREATE INDEX idx_items_exam_no ON question_items(exam_id,question_no);CREATE INDEX idx_items_rate ON question_items(correct_rate);CREATE INDEX idx_docs_type ON official_docs(source_type);''')
 c.execute("insert into sources values(1,'EBSi','EBSi','https://www.ebsi.co.kr'),(2,'KICE','한국교육과정평가원','https://www.suneung.re.kr'),(3,'Megastudy','메가스터디','https://www.megastudy.net')")
 ec=sqlite3.connect(ebsi);km=sqlite3.connect(kice)
 exam_map={}
 for r in ec.execute('select paper_no,year,month,grade,subject_group,subject,title,exam_date,source_url,metadata_json from papers'):
  cur=c.execute('insert into exams(source_id,paper_no,year,month,grade,subject_group,subject,title,exam_date,source_url,metadata_json) values(1,?,?,?,?,?,?,?,?,?,?)',r);exam_map[r[0]]=cur.lastrowid
 for r in ec.execute('select asset_id,paper_no,asset_type,url,local_path,http_status,content_type,bytes,sha256,error from assets'):
  c.execute('insert into assets(asset_id,exam_id,source_id,asset_type,url,local_path,http_status,content_type,bytes,sha256,error) values(?,?,?,?,?,?,?,?,?,?,?)',(r[0],exam_map.get(r[1]),1,*r[2:]))
 for r in km.execute('''select d.id,d.source_type,d.title,d.detail_url,d.file_url,f.local_path,f.content_type,f.bytes,f.sha256,f.error,d.description from documents d left join files f on f.document_id=d.id'''):
  c.execute('insert into official_docs(doc_id,source_id,source_type,title,detail_url,file_url,local_path,content_type,bytes,sha256,error,description) values(?,?,?,?,?,?,?,?,?,?,?,?)',(r[0],2,*r[1:]))
 # searchable text from compact metadata and official titles/descriptions
 for eid,r in enumerate(c.execute('select exam_id,title,subject,metadata_json from exams'),1):
  body=' '.join(str(x or '') for x in r[2:]);c.execute('insert into texts(text_id,entity_type,entity_id,title,body,source_id) values(?,?,?,?,?,1)',(eid,'exam',r[0],r[1],body))
 for r in c.execute('select doc_id,title,description,source_type from official_docs'):
  tid=1000000+r[0];c.execute('insert into texts(text_id,entity_type,entity_id,title,body,source_id) values(?,?,?,?,?,2)',(tid,'official_doc',r[0],r[1],r[2] or ''))
 c.execute("insert into texts_fts(rowid,title,body) select text_id,title,body from texts")
 c.execute("insert into relations(from_type,from_id,rel,to_type,to_id,confidence,notes) select 'exam',exam_id,'has_asset','asset',asset_id,1.0,'EBSi linked asset' from assets where exam_id is not null")
 c.execute("insert into relations(from_type,from_id,rel,to_type,to_id,confidence,notes) select 'official_doc',doc_id,'official_attachment','file',doc_id,1.0,'KICE official attachment' from official_docs where local_path is not null")
 c.execute('create view search_help as select t.entity_type,t.entity_id,t.title,t.body from texts t')
 c.execute('create table meta(key text primary key,value text)');c.executemany('insert into meta values(?,?)',[('created_at',now()),('schema_version','1.0'),('purpose','Korean CSAT agent retrieval database'),('ebsi_db',str(ebsi)),('kice_db',str(kice))]);c.commit();c.execute('vacuum');c.close();ec.close();km.close()
 # compact JSONL index for agent runtimes
 with sqlite3.connect(out) as q, open(root/'suneung_agent_index.jsonl','w',encoding='utf-8') as f:
  for row in q.execute('select entity_type,entity_id,title,body from texts'):
   f.write(json.dumps({'type':row[0],'id':row[1],'title':row[2],'text':row[3]},ensure_ascii=False)+'\n')
 print(out)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--root',default='workspace');main(p.parse_args())
