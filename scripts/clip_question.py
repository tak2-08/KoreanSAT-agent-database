#!/usr/bin/env python3
"""Rights-gated PDF crop with exact page/bounds, image hash, source URL link.

Use only with a PDF you are authorized to reproduce in the chosen context.
Resulting third-party images MUST stay in the private `workspace/` directory;
this tool does not grant public redistribution rights.
"""
from __future__ import annotations
import argparse,hashlib,os,sqlite3,pathlib,re
try: import fitz
except ImportError: raise SystemExit('Install PyMuPDF: pip install pymupdf')

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--db',required=True,help='local research_catalog.sqlite')
 ap.add_argument('--pdf',required=True,help='legally acquired local original PDF')
 ap.add_argument('--exam-id',type=int,required=True)
 ap.add_argument('--question',type=int,required=True)
 ap.add_argument('--kind',choices=['question','explanation','answer'],required=True)
 ap.add_argument('--page',type=int,required=True,help='1-indexed PDF page')
 ap.add_argument('--bbox',type=float,nargs=4,required=True,metavar=('X0','Y0','X1','Y1'),help='normalized coordinates [0..1] of exact region')
 ap.add_argument('--source-url',required=True)
 ap.add_argument('--out-root',default='workspace/private_clips')
 ap.add_argument('--rights-confirmed',action='store_true',help='Confirm that your local copying is authorized; does NOT authorize public redistribution')
 ap.add_argument('--dpi',type=int,default=180)
 a=ap.parse_args()
 if not a.rights_confirmed:ap.error('Must confirm right to make this local copy with --rights-confirmed')
 x0,y0,x1,y1=a.bbox
 if not all(0<=v<=1 for v in a.bbox) or x0>=x1 or y0>=y1:ap.error('--bbox must be normalized 0..1 and x0<x1, y0<y1')
 if not a.source_url.startswith('https://'):ap.error('--source-url must be https')
 pdf=fitz.open(a.pdf)
 if not (1<=a.page<=len(pdf)):ap.error('Page out of bounds')
 page=pdf[a.page-1]
 r=page.rect
 clip=fitz.Rect(r.x0+x0*r.width,r.y0+y0*r.height,r.x0+x1*r.width,r.y0+y1*r.height)
 px=page.get_pixmap(matrix=fitz.Matrix(a.dpi/72,a.dpi/72),clip=clip,alpha=False)
 output=pathlib.Path(a.out_root)/f'exam-{a.exam_id}'/f'q{a.question:02d}_{a.kind}_p{a.page}.png'
 output.parent.mkdir(parents=True,exist_ok=True)
 px.save(output);sha=hashlib.sha256(output.read_bytes()).hexdigest()
 c=sqlite3.connect(a.db)
 if not c.execute('select 1 from exam_catalog where exam_id=?',(a.exam_id,)).fetchone():ap.error('Exam ID not found in catalog')
 # linking is explicit; image is always private/unverified even if copy is locally authorized
 c.execute('''INSERT INTO image_assets(exam_id,question_no,asset_kind,source_pdf_url,pdf_page_zero_based,x0_norm,y0_norm,x1_norm,y1_norm,local_image_path,sha256,rights_status,review_status)
 VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',(a.exam_id,a.question,a.kind,a.source_url,a.page-1,x0,y0,x1,y1,str(output),sha,'private_copy_not_for_redistribution','pending_manual_visual_review'))
 c.commit();print('Saved private crop:',output,'SHA256',sha,'linked row',c.execute('select last_insert_rowid()').fetchone()[0]);c.close()
if __name__=='__main__':main()
