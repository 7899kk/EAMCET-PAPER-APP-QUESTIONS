"""Current inline editor regression. Optional PDF argument stays local/private."""
import asyncio,json,os,re,shutil,subprocess,sys
from pathlib import Path
from playwright.async_api import async_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from PIL import Image
from backend import layers

OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser'
OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3018')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Local test servers only; user files must not be uploaded to another service.')

async def settled(page):
 await page.wait_for_function("()=>{const s=document.querySelector('.pdf-surface'),c=s?.querySelector('canvas');return c&&c.dataset.renderedRevision===s.dataset.revision&&c.dataset.renderedPage===s.dataset.page}",timeout=30000)

def generate():
 path=OUT/'inline-source.pdf'
 with fitz.open() as doc:
  for index,text in enumerate(['So with this we can make this video.','Page two can be edited directly.']):
   p=doc.new_page();xref=p.insert_font(fontname='body',fontbuffer=layers.font_buffer('helv'));layers.normalize_space_map(doc,xref)
   p.insert_text((60,90),text,fontname='body',fontsize=16)
   p.insert_text((60,260),'Leave this separate paragraph unchanged.',fontname='body',fontsize=16)
   if index==0:
    import io
    image=Image.new('RGB',(80,60),'red');buf=io.BytesIO();image.save(buf,'PNG')
    p.insert_image((60,330,180,420),stream=buf.getvalue());p.insert_image((300,330,420,420),stream=buf.getvalue())
  doc.save(path)
 return path

async def main():
 private=Path(sys.argv[1]) if len(sys.argv)>1 else None
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only')})
   page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto(BASE);await page.locator('input[type=file]').first.set_input_files(generate())
   target=page.get_by_role('textbox',name=re.compile('^Edit paragraph: So with this'))
   await expect(target).to_be_visible(timeout=30000);await target.click()
   field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True)
   await expect(field).to_be_focused(timeout=20000)
   assert await page.locator('.text-target,.word-target').count()==0
   assert await page.get_by_role('button',name='Save word',exact=True).count()==0
   replacement='So with this we can make this type of video.'
   # Export immediately: download must await pending automatic save.
   await field.fill(replacement)
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'inline-{mobile}.pdf';await(await dl.value).save_as(output)
   with fitz.open(output) as doc:
    assert replacement in ' '.join(doc[0].get_text().split())
    assert 'Leave this separate paragraph unchanged.' in doc[0].get_text()
   # Edit again, then change pages without a separate Save action.
   await expect(page.locator('.inline-text')).to_have_count(0,timeout=20000)
   await page.get_by_role('textbox',name=re.compile('^Edit paragraph: So with this')).click();await expect(field).to_be_focused()
   # A pause after clearing a paragraph must leave the typing surface available.
   await field.fill('');await page.wait_for_timeout(800);await expect(field).to_be_focused()
   final='We can make this type of video.';await field.fill(final)
   if mobile:await page.get_by_role('button',name='Toggle page panel',exact=True).click()
   await page.get_by_role('button',name='Open page 2',exact=True).click();await settled(page)
   if mobile:await page.get_by_role('button',name='Toggle page panel',exact=True).click()
   await page.get_by_role('button',name='Open page 1',exact=True).click();await expect(page.get_by_role('textbox',name=re.compile('^Edit paragraph: We can make'))).to_be_visible(timeout=20000)
   await settled(page);await page.screenshot(path=str(OUT/f'inline-editor-{mobile}.png'))
   # Add text directly, also without a composer or Save button.
   toolbar=page.get_by_role('toolbar',name='PDF editing tools')
   await toolbar.get_by_role('button',name='Add text',exact=True).click()
   surface=page.locator('.pdf-surface');box=await surface.bounding_box();z=box['width']/595
   await page.locator('.canvas-scroll').evaluate('(el,z)=>el.scrollTop=500*z-el.clientHeight/2',z)
   box=await surface.bounding_box();await page.mouse.click(box['x']+45*z,box['y']+500*z)
   await expect(field).to_be_focused(timeout=20000);await field.fill('Text added directly on the PDF.')
   await toolbar.get_by_role('button',name='Layers',exact=True).click()
   await expect(page.get_by_label('Select PDF layer',exact=True)).to_be_visible()
   options=page.get_by_label('Select PDF layer',exact=True).locator('option')
   native=await options.evaluate_all("els=>els.find(e=>e.value.startsWith('image:')).value")
   await page.get_by_label('Select PDF layer',exact=True).select_option(native)
   await page.get_by_role('button',name='Delete layer',exact=True).click()
   await settled(page)
   # The exported result proves real original-image deletion and new text persistence.
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'inline-tools-{mobile}.pdf';await(await dl.value).save_as(output)
   with fitz.open(output) as doc:
    assert len(doc[0].get_image_info())==1
    assert 'Text added directly on the PDF.' in doc[0].get_text()
   # Existing brush and shape tools still work after an inline save.
   async def stroke(start,end):
    await page.mouse.move(*start);await page.mouse.down();await page.mouse.move(*end,steps=10);await page.wait_for_timeout(40);await page.mouse.up()
    await expect(page.locator('.busy-layer')).to_have_count(0);await settled(page)
   async def coordinates(x,y):
    box=await surface.bounding_box();z=box['width']/595
    await page.locator('.canvas-scroll').evaluate('(el,args)=>el.scrollTop=Math.max(0,args.y*args.z-el.clientHeight/2)',{'y':y,'z':z})
    box=await surface.bounding_box();return box['x']+x*z,box['y']+y*z
   await toolbar.get_by_role('button',name='Highlight',exact=True).click()
   start=await coordinates(60,90);end=(start[0]+100*z,start[1]+3*z);await stroke(start,end)
   await toolbar.get_by_role('button',name='Shapes',exact=True).click();await page.get_by_role('button',name='Ellipse',exact=True).click()
   start=await coordinates(300,450);await stroke(start,(start[0]+80*z,start[1]+45*z))
   await expect(page.get_by_role('button',name=re.compile('^Select ellipse '))).to_be_visible()
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'inline-brush-shapes-{mobile}.pdf';await(await dl.value).save_as(output)
   with fitz.open(output) as doc:
    p0=doc[0];assert any(d['stroke_opacity']<.5 for d in p0.get_drawings());assert any(a.type[0]==fitz.PDF_ANNOT_CIRCLE for a in p0.annots())
   assert not errors,errors
   print(json.dumps({'viewport':'mobile' if mobile else 'desktop','no_underlines_or_save_popup':True,'inline_typing_and_auto_fit':'passed','download_flushes_draft':'passed','page_change_flushes_draft':'passed','add_text_without_popup':'passed','original_image_delete':'passed','browser_errors':errors}),flush=True)
   await ctx.close()
  # OCR's editable reconstruction uses the same direct editor.
  ctx=await browser.new_context(viewport={'width':1440,'height':960},accept_downloads=True,http_credentials={'username':'folio','password':os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only')})
  page=await ctx.new_page();await page.goto(BASE)
  with fitz.open() as doc:
   p0=doc.new_page();p0.insert_text((60,100),'ASHOK INVOICE',fontsize=30);pix=p0.get_pixmap(dpi=180)
  with fitz.open() as doc:
   doc.new_page().insert_image((0,0,595,842),stream=pix.tobytes('png'));scan=OUT/'inline-ocr-source.pdf';doc.save(scan)
  await page.locator('input[type=file]').first.set_input_files(scan);await settled(page)
  for mode in ['searchable','editable']:
   await page.get_by_role('toolbar',name='PDF editing tools').get_by_role('button',name='OCR',exact=True).click()
   await page.get_by_label('OCR output mode',exact=True).select_option(mode);await page.get_by_role('button',name='Start OCR',exact=True).click()
   await expect(page.locator('.busy-layer')).to_have_count(0,timeout=45000);await expect(page.get_by_role('alert')).to_have_count(0);await settled(page)
  await page.get_by_role('textbox',name=re.compile('^Edit paragraph: ASHOK')).click()
  field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True);await expect(field).to_be_focused(timeout=20000)
  await field.fill((await field.inner_text()).replace('ASHOK','JOHN'))
  async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
  output=OUT/'inline-ocr-edited.pdf';await(await dl.value).save_as(output)
  with fitz.open(output) as doc:assert 'JOHN' in doc[0].get_text() and 'ASHOK' not in doc[0].get_text() and not doc[0].get_images()
  print('PASS: searchable OCR, editable OCR copy, direct edit, autosaved download and reopen',flush=True)
  await ctx.close()
  if private:
   # The provided document is read/uploaded ONLY to the loopback test server.
   for mobile in [False,True]:
    ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only')})
    page=await ctx.new_page();await page.goto(BASE);await page.locator('input[type=file]').first.set_input_files(private)
    await expect(page.locator('.paragraph-hit')).not_to_have_count(0,timeout=30000)
    if mobile:await page.get_by_role('button',name='Toggle page panel',exact=True).click()
    await page.get_by_role('button',name='Open page 2',exact=True).click()
    await page.get_by_role('textbox',name=re.compile('^Edit paragraph: It writes the whole video')).click()
    field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True);await expect(field).to_be_focused(timeout=30000)
    await field.evaluate("""el=>{const node=el.firstChild,i=node.textContent.indexOf('the whole video');const r=document.createRange();r.setStart(node,i);r.setEnd(node,i+15);const s=window.getSelection();s.removeAllRanges();s.addRange(r)}""")
    async with page.expect_response(lambda r:r.url.endswith('/inline-edit') and r.request.method=='POST',timeout=30000):await page.keyboard.insert_text('this type of video')
    await expect(page.get_by_role('status').filter(has_text='All changes saved')).to_be_visible()
    await page.screenshot(path=str(OUT/f'provided-inline-{mobile}.png'))
    async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
    output=OUT/f'provided-inline-{mobile}.pdf';await(await dl.value).save_as(output)
    text=subprocess.check_output(['pdftotext',str(output),'-'],text=True)
    assert 'It writes this type of video as code.' in ' '.join(text.split()) and 'It writes the whole video as code.' not in ' '.join(text.split())
    with fitz.open(private) as before,fitz.open(output) as after:
     assert len(before)==len(after)
     for a,b in zip(before,after):assert len(a.get_image_info())==len(b.get_image_info())
    print(json.dumps({'provided_pdf':'passed','mobile':mobile,'actual_phrase_edit':'passed','images_preserved':True,'download_independent_reopen':'passed'}),flush=True)
    await ctx.close()
  await browser.close()

if __name__=='__main__':asyncio.run(main())
