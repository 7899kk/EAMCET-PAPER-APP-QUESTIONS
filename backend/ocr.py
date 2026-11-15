"""Cancellable local Tesseract OCR, with searchable and explicit text-copy output."""
import csv,io,math,subprocess,tempfile,time
from pathlib import Path
import pymupdf as fitz
from .layers import font_buffer,insert_unicode_font

class Cancelled(Exception):pass

def process(data,languages='eng',mode='searchable',indices=None,progress=lambda *args:None,cancel=None):
    if mode not in ('searchable','editable'):raise ValueError('Choose searchable PDF or editable text copy.')
    def check():
        if cancel and cancel.is_set():raise Cancelled('OCR cancelled. Your original PDF is unchanged.')
    with fitz.open(stream=data,filetype='pdf') as source,fitz.open() as output:
        selected=set(range(len(source)) if indices is None else indices)
        if not selected or any(type(i)!=int or not 0<=i<len(source) for i in selected):raise ValueError('Invalid OCR pages.')
        recognized=0;completed=0
        for i,page in enumerate(source):
            check()
            if i not in selected:
                output.insert_pdf(source,from_page=i,to_page=i);continue
            progress(completed,len(selected),f'Reading page {i+1} of {len(source)}…')
            existing=page.get_text().strip()
            if existing and mode=='searchable':
                output.insert_pdf(source,from_page=i,to_page=i);recognized+=len(existing.split())
            else:
                dpi=max(72,min(180,int(72*math.sqrt(8_000_000/page.rect.get_area()))))
                pix=page.get_pixmap(dpi=dpi,alpha=False)
                with tempfile.TemporaryDirectory(prefix='folio-ocr-') as folder:
                    image=Path(folder)/'page.png';pix.save(image);dest=Path(folder)/'result'
                    command=['tesseract',str(image),str(dest),'-l',languages,'--dpi',str(dpi),'pdf','tsv']
                    started=time.monotonic();child=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
                    try:
                        while True:
                            check()
                            if time.monotonic()-started>90:raise ValueError(f'OCR timed out on page {i+1}. Try processing one page at a time.')
                            try:
                                _,err=child.communicate(timeout=.25);break
                            except subprocess.TimeoutExpired:pass
                        if child.returncode:raise ValueError('Tesseract could not recognize this page. Check the installed language and document orientation.')
                    finally:
                        if child.poll() is None:child.terminate();child.wait(timeout=5)
                    rows=[r for r in csv.DictReader((dest.with_suffix('.tsv')).read_text().splitlines(),delimiter='\t') if r.get('level')=='5' and r.get('text','').strip()]
                    recognized+=len(rows)
                    if mode=='searchable':
                        with fitz.open(dest.with_suffix('.pdf')) as part:output.insert_pdf(part)
                    else:
                        target=output.new_page(width=page.rect.width,height=page.rect.height);font=fitz.Font(fontbuffer=font_buffer('helv'))
                        insert_unicode_font(target)
                        for row in rows:
                            text=row['text'].strip()
                            try:text.encode('cp1252')
                            except UnicodeError:raise ValueError('Editable OCR copies currently support Western Latin text. Choose searchable PDF to preserve other languages.')
                            x,y,w,h=[float(row[k])*72/dpi for k in ('left','top','width','height')]
                            size=min(72,max(4,min(h/.75,w/max(font.text_length(text,fontsize=1),.01))))
                            target.insert_text((x,min(target.rect.height-2,y+h-size*.1)),text,fontname='FolioText',fontsize=size)
                del pix
            completed+=1;progress(completed,len(selected),f'Processed {completed} of {len(selected)} pages')
        check()
        if not recognized:raise ValueError('No text was recognized. Try rotating the page, cropping to the text, or using a clearer scan.')
        return output.tobytes(garbage=4,deflate=True),{'words':recognized,'pages':completed,'mode':mode}
