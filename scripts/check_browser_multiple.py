"""Multiple consecutive edits, selection, font subsets and editable scan regression."""
import asyncio,json,os,re,shutil,sys,subprocess
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from playwright.async_api import async_playwright,expect
from backend import layers
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3018')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Loopback test servers only.')
EDITS=[("I'm feeling happy Today","I'm enthusiastic and happy Today"),('Ashok prepares the video.','Ashok prepares this type of video.'),('The meeting starts on Monday.','The meeting starts on Friday.'),('Please select this final sentence.','Please edit every word in this sentence.'),('Nested text must also be editable.','Nested text is now truly edited.'),('ASHOK','Ashok one two three and new letters')]

def generate():
 path=OUT/'multiple-source.pdf'
 with fitz.open() as doc:
  p=doc.new_page()
  for y,text,size in [(65,'EDITOR COMPARISON',22),(110,EDITS[0][0],18),(175,EDITS[1][0],16),(235,EDITS[2][0],16),(295,EDITS[3][0],16)]:p.insert_text((45,y),text,fontsize=size)
  with fitz.open() as nested:
   nested.new_page(width=400,height=50).insert_text((0,28),EDITS[4][0],fontsize=16);p.show_pdf_page(fitz.Rect(45,340,445,390),nested,0)
  p.insert_font(fontname='subset',fontbuffer=layers.font_buffer('helv'));p.insert_text((45,610),'ASHOK',fontname='subset',fontsize=20)
  with fitz.open() as scan:
   q=scan.new_page();q.insert_text((45,90),'SCANNED INVOICE',fontsize=30);q.insert_text((45,150),'Ashok feels happy today.',fontsize=22);q.insert_text((45,210),'Invoice total 12345',fontsize=22)
   q.draw_rect((45,320,185,418),color=(.1,.3,.7),fill=(.1,.3,.7));pix=q.get_pixmap(dpi=180)
   q=doc.new_page();q.insert_image(q.rect,stream=pix.tobytes('png'))
  doc.subset_fonts();doc.save(path)
 return path

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':1000},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only')})
   page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto(BASE);await page.locator('input[type=file]').first.set_input_files(generate())
   field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True)
   # Cold double-click before any editing surface/font has been prepared.
   await expect(page.get_by_role('textbox',name='Edit paragraph: '+EDITS[0][0],exact=True)).to_be_visible(timeout=25000)
   with fitz.open(OUT/'multiple-source.pdf') as d:w=next(w for w in d[0].get_text('words') if w[4]=='feeling')
   surface=page.locator('.pdf-surface');box=await surface.bounding_box();z=box['width']/595
   await page.mouse.dblclick(box['x']+(w[0]+w[2])/2*z,box['y']+(w[1]+w[3])/2*z)
   await expect(field).to_be_focused(timeout=15000)
   await page.wait_for_function("()=>window.getSelection().toString().trim()==='feeling'",timeout=15000)
   for index,(before,after) in enumerate(EDITS):
    if index:
     target=page.get_by_role('textbox',name='Edit paragraph: '+before,exact=True);await expect(target).to_be_visible(timeout=25000);await target.click();await expect(field).to_be_focused(timeout=15000)
    start=await field.evaluate('e=>getComputedStyle(e).fontSize');await field.fill(after)
    # No pause between edits: clicking the next source must flush the prior save.
    assert await field.evaluate('e=>getComputedStyle(e).fontSize')==start
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'multiple-{mobile}.pdf';await(await dl.value).save_as(output)
   independent=' '.join(subprocess.check_output(['pdftotext',str(output),'-'],text=True).split())
   for old,new in EDITS:assert new in independent and old not in independent,(old,new,independent)
   with fitz.open(output) as d:
    spans=[s for b in d[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
    assert all(s['size']==16 for s in spans if 'Friday' in s['text'])
    assert all(s['size']==20 for s in spans if 'Ashok one' in s['text'])
   # Double-click a word and type a replacement, without filling the paragraph.
   target=page.get_by_role('textbox',name=re.compile('^Edit paragraph: The meeting starts on Friday'))
   await target.click();await expect(field).to_be_focused(timeout=15000)
   coords=await field.evaluate("""el=>{const n=el.firstChild,i=n.textContent.indexOf('Friday'),r=document.createRange();r.setStart(n,i);r.setEnd(n,i+6);const b=r.getBoundingClientRect();return {x:b.x+b.width/2,y:b.y+b.height/2}}""")
   await page.mouse.dblclick(coords['x'],coords['y']);assert (await page.evaluate('window.getSelection().toString()')).strip()=='Friday'
   await page.keyboard.insert_text('Sunday')
   if mobile:await page.get_by_role('button',name='Toggle page panel',exact=True).click()
   await page.get_by_role('button',name='Open page 2',exact=True).click()
   await page.get_by_role('button',name='Make scanned text editable',exact=True).click(timeout=20000)
   assert await page.get_by_label('OCR output mode',exact=True).input_value()=='layout'
   await page.get_by_role('button',name='Start OCR',exact=True).click();await expect(page.locator('.busy-layer')).to_have_count(0,timeout=60000)
   target=page.get_by_role('textbox',name=re.compile('^Edit paragraph: Ashok feels happy today'))
   await target.click(timeout=25000);await expect(field).to_be_focused(timeout=15000)
   await field.fill('Kartik feels enthusiastic today.')
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'multiple-with-ocr-{mobile}.pdf';await(await dl.value).save_as(output)
   with fitz.open(output) as d:
    assert 'Kartik feels enthusiastic today.' in ' '.join(d[1].get_text().split())
    assert 'Sunday' in d[0].get_text() and 'Friday' not in d[0].get_text()
    pix=d[1].get_pixmap(clip=fitz.Rect(60,335,170,400));assert any(pix.samples[i+2]>pix.samples[i]+70 for i in range(0,len(pix.samples),3))
   await page.screenshot(path=str(OUT/f'multiple-and-scan-{mobile}.png'))
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'consecutive_edits':6,'font_size_unchanged':True,'nested_text':True,'subset_new_letters':True,'double_click_word_selection':True,'ocr_scan_edited':True,'artwork_preserved':True,'independent_download_reopen':True}),flush=True)
   await ctx.close()
  await browser.close()
if __name__=='__main__':asyncio.run(main())
