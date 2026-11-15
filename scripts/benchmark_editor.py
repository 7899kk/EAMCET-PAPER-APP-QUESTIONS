"""Generate a larger real PDF and measure text analysis / preview payloads locally."""
import argparse,io,json,random,statistics,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from PIL import Image
from backend.content import inspect
from backend.words import inspect_words
from backend.app import Session,page_words

def generate(path,pages):
    with fitz.open() as doc:
        for index in range(pages):
            page=doc.new_page()
            for row in range(38):
                page.insert_text((40,48+row*17),f'Page {index+1} line {row+1}: The quick brown fox needs a small edit.',fontsize=10)
            image=Image.frombytes('RGB',(300,300),random.Random(index).randbytes(270000))
            stream=io.BytesIO();image.save(stream,format='PNG')
            page.insert_image((450,710,550,810),stream=stream.getvalue())
        doc.save(path,deflate=True)

def measure(fn,repeat=5):
    samples=[]
    for _ in range(repeat):
        start=time.perf_counter();fn();samples.append((time.perf_counter()-start)*1000)
    return round(statistics.median(samples),3)

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--pages',type=int,default=40);parser.add_argument('--output',default='tests/artifacts/browser/performance')
    args=parser.parse_args()
    if not 1<=args.pages<=80:parser.error('Choose 1–80 pages for this local benchmark.')
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    path=output/f'large-{args.pages}.pdf'
    if not path.exists():generate(path,args.pages)
    data=path.read_bytes();session=Session([data]);words=page_words(session,0)
    with fitz.open(stream=data,filetype='pdf') as doc,fitz.open() as preview:
        preview.insert_pdf(doc,from_page=0,to_page=0,links=False,widgets=False)
        page_data=preview.tobytes(garbage=3,deflate=True)
    result={'fixture':str(path.resolve()),'pages':args.pages,'words_first_page':len(words),'full_pdf_bytes':len(data),'page_preview_bytes':len(page_data),'transfer_reduction_percent':round((1-len(page_data)/len(data))*100,2),'legacy_and_word_analysis_ms':measure(lambda:(inspect(data,0),inspect_words(data,0))),'words_only_analysis_ms':measure(lambda:inspect_words(data,0)),'cached_analysis_ms':measure(lambda:page_words(session,0))}
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
