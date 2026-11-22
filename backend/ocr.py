"""Cancellable local Tesseract OCR, with searchable and explicit text-copy output."""
import csv,io,math,subprocess,tempfile,time,collections
from PIL import Image,ImageDraw
from pathlib import Path
import pymupdf as fitz
from .layers import font_buffer,insert_unicode_font

class Cancelled(Exception):pass

def reconstruct(target,pix,rows,dpi,preserve_artwork=True):
    """Lossy scan-to-editable conversion; original scan bytes are not retained.

    Keep raster artwork outside recognized glyph regions, erase recognized pixels
    using their sampled local paper colour, then insert real selectable line text.
    """
    image=Image.frombytes('RGB',(pix.width,pix.height),pix.samples) if preserve_artwork else None
    draw=ImageDraw.Draw(image) if image else None
    lines=collections.defaultdict(list)
    for row in rows:
        if float(row.get('conf',0))<25:continue
        text=row['text'].strip()
        try:text.encode('cp1252')
        except UnicodeError:raise ValueError('Editable OCR reconstruction currently supports Western Latin text. Choose searchable output for other scripts.')
        lines[(row['block_num'],row['par_num'],row['line_num'])].append(row)
        if not preserve_artwork:continue
        x,y,w,h=[int(row[k]) for k in ('left','top','width','height')]
        pad=2;box=(max(0,x-pad),max(0,y-pad),min(image.width,x+w+pad),min(image.height,y+h+pad))
        # Sample only outside the recognized pixels. Flat paper backgrounds are
        # retained; textured/photo text backgrounds are explicitly approximate.
        pixels=[]
        for yy in (max(0,box[1]-2),min(image.height-1,box[3]+2)):
            pixels.extend(image.getpixel((xx,yy)) for xx in range(box[0],box[2],max(1,w//40)))
        colour=collections.Counter(pixels).most_common(1)[0][0] if pixels else (255,255,255)
        draw.rectangle(box,fill=colour)
    if preserve_artwork:
        buf=io.BytesIO();image.save(buf,format='PNG');target.insert_image(target.rect,stream=buf.getvalue())
    font=fitz.Font(fontbuffer=font_buffer('helv'));insert_unicode_font(target)
    for items in lines.values():
        items.sort(key=lambda r:int(r['left']));text=' '.join(r['text'].strip() for r in items)
        x=min(int(r['left']) for r in items);y=min(int(r['top']) for r in items)
        right=max(int(r['left'])+int(r['width']) for r in items);bottom=max(int(r['top'])+int(r['height']) for r in items)
        scale=72/dpi;x,y,right,bottom=[v*scale for v in (x,y,right,bottom)]
        size=min(72,max(4,min((bottom-y)/.72,(right-x)/max(font.text_length(text,fontsize=1),.01))))
        target.insert_text((x,min(target.rect.height-2,bottom)),text,fontname='FolioText',fontsize=size)
    return len(lines)

def process(data,languages='eng',mode='searchable',indices=None,progress=lambda *args:None,cancel=None):
    if mode not in ('searchable','editable','layout'):raise ValueError('Choose searchable PDF or editable text copy.')
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
            if existing and mode=='searchable' and not page.get_image_info():
                output.insert_pdf(source,from_page=i,to_page=i);recognized+=len(existing.split())
            else:
                dpi=max(72,min(180,int(72*math.sqrt(8_000_000/page.rect.get_area()))))
                pix=page.get_pixmap(dpi=dpi,alpha=False)
                with tempfile.TemporaryDirectory(prefix='folio-ocr-') as folder:
                    image=Path(folder)/'page.png';pix.save(image);dest=Path(folder)/'result'
                    command=['tesseract',str(image),str(dest),'-l',languages,'--dpi',str(dpi)]+(['pdf','tsv'] if mode=='searchable' else ['tsv'])
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
                    elif mode=='layout':
                        target=output.new_page(width=page.rect.width,height=page.rect.height);reconstruct(target,pix,rows,dpi)
                    else:
                        target=output.new_page(width=page.rect.width,height=page.rect.height);reconstruct(target,pix,rows,dpi,preserve_artwork=False)
                del pix
            completed+=1;progress(completed,len(selected),f'Processed {completed} of {len(selected)} pages')
        check()
        if not recognized:raise ValueError('No text was recognized. Try rotating the page, cropping to the text, or using a clearer scan.')
        return output.tobytes(garbage=4,deflate=True),{'words':recognized,'pages':completed,'mode':mode}
