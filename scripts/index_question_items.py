#!/usr/bin/env python3
import argparse,json,sqlite3
from pathlib import Path

def main(a):
 p=Path(a.db); backup=p.with_suffix('.precompact.sqlite')
 if not backup.exists(): backup.write_bytes(p.read_bytes())
 c=sqlite3.connect(p,timeout=120);c.execute('PRAGMA journal_mode=WAL')
 # Remove duplicated full question bodies from the generic texts/FTS layer.
 ids=[r[0] for r in c.execute("select text_id from texts where entity_type='question'")]
 if ids:
  c.executemany('delete from texts_fts where rowid=?',[(x,) for x in ids]);c.execute("delete from texts where entity_type='question'")
 # Recreate a compact FTS table: metadata + a short stem prefix, never full solutions.
 c.execute('drop table if exists question_search')
 c.execute('''create virtual table question_search using fts5(
  year UNINDEXED, month UNINDEXED, subject UNINDEXED, question_no UNINDEXED,
  answer UNINDEXED, correct_rate UNINDEXED, body,
  tokenize='unicode61')''')
 rows=c.execute('''select q.item_id,e.year,e.month,e.subject,q.question_no,q.answer,q.correct_rate,q.difficulty,q.stem_text
                   from question_items q join exams e on e.exam_id=q.exam_id''').fetchall()
 for item,year,month,subject,no,ans,rate,diff,stem in rows:
  body=' '.join(str(x or '') for x in (subject,diff,stem[:600]))
  c.execute('insert into question_search(rowid,year,month,subject,question_no,answer,correct_rate,body) values(?,?,?,?,?,?,?,?)',(item,str(year or ''),str(month or ''),str(subject or ''),str(no),str(ans or ''),str(rate or ''),body))
 c.execute('create index if not exists idx_question_search_lookup on question_items(exam_id,question_no)')
 c.commit();c.execute('vacuum');c.commit()
 # Compact JSONL is metadata-first; retrieve full stem/solution from SQLite by item id.
 out=p.parent/'suneung_agent_index.jsonl'
 with out.open('w',encoding='utf-8') as f:
  for r in c.execute('''select q.item_id,q.exam_id,e.year,e.month,e.subject,e.title,q.question_no,q.answer,q.correct_rate,q.difficulty,q.answer_source,q.correct_rate_source
                        from question_items q join exams e on e.exam_id=q.exam_id order by q.item_id'''):
   f.write(json.dumps({'type':'question','id':r[0],'exam_id':r[1],'year':r[2],'month':r[3],'subject':r[4],'exam':r[5],'question_no':r[6],'answer':r[7],'correct_rate':r[8],'difficulty':r[9],'answer_source':r[10],'rate_source':r[11]},ensure_ascii=False,separators=(',',':'))+'\n')
 print('removed_question_texts',len(ids),'question_search',len(rows),'db_bytes',p.stat().st_size,'jsonl_bytes',out.stat().st_size)
 c.close()
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);main(p.parse_args())
