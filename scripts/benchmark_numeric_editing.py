"""Compare page analysis/save CPU time against a source checkout (no network)."""
import sys,json,time,statistics
from pathlib import Path
source_root=sys.argv[1] if len(sys.argv)>1 else str(Path(__file__).resolve().parent.parent)
sys.path.insert(0,source_root)
import pymupdf as fitz
from backend import blocks,layers
with fitz.open() as doc:
 p=doc.new_page();xref=p.insert_font(fontname='body',fontbuffer=layers.font_buffer('hebo'));layers.normalize_space_map(doc,xref)
 for i in range(28):p.insert_text((40,45+i*24),'Invoice amount 12345 and account number 98765.',fontname='body',fontsize=12)
 source=doc.tobytes()
# Warm library code and measure independent edits of the same source.
analysis=[];saves=[]
for i in range(15):
 t=time.perf_counter();targets=blocks.inspect_blocks(source,0);analysis.append((time.perf_counter()-t)*1000)
 b=targets[0];t=time.perf_counter();blocks.replace_block(source,0,{'id':b['id'],'original':b['text'],'text':b['text'].replace('12345','54321')},targets);saves.append((time.perf_counter()-t)*1000)
print(json.dumps({'source':source_root,'analysis_median_ms':round(statistics.median(analysis[2:]),2),'save_median_ms':round(statistics.median(saves[2:]),2),'repetitions':13}))
