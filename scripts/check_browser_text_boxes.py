"""Blank PDF, consecutive text boxes, font/size/move/resize and image OCR."""
import asyncio,json,os,shutil,sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from playwright.async_api import async_playwright,expect
from browser_helpers import sign_in
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3018')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Loopback only')
def image_fixture():
    with fitz.open() as d:
        p=d.new_page(width=420,height=150);p.insert_text((25,70),'IMAGE WORDS 87453',fontsize=25);p.get_pixmap(dpi=180).save(OUT/'box-ocr.png')
    return OUT/'box-ocr.png'
async def main():
 async with async_playwright() as p:
  b=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await b.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':1000},is_mobile=mobile,has_touch=mobile,accept_downloads=True)

   if os.environ.get('FOLIO_TEST_PUBLIC')!='1':await sign_in(ctx,BASE)
   page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));await page.goto(BASE)
   assert 'Edit karo' in await page.title()
   await page.get_by_role('button',name='Start with a blank PDF',exact=True).click()
   surface=page.locator('.pdf-surface');await expect(surface).to_have_class(re.compile('tool-text'),timeout=20000)
   await page.wait_for_function("()=>document.querySelector('canvas[data-rendered-page=\"0\"]')")
   async def at(x,y):
    z=(await surface.bounding_box())['width']/595
    await page.locator('.canvas-scroll').evaluate('(e,y)=>e.scrollTop=Math.max(0,y-e.clientHeight/2)',y*z)
    box=await surface.bounding_box();await page.mouse.click(box['x']+x*z,box['y']+y*z)
   f=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True)
   await page.get_by_label('New text font',exact=True).select_option('tiro')
   await at(50,80);await expect(f).to_be_focused(timeout=15000);await f.fill('First independent text box')
   # Place again immediately, before the first autosave timer fires.
   await at(50,180);await expect(f).to_be_focused(timeout=20000);await f.fill('Second independent text box')
   await page.get_by_role('button',name='Move / resize / style box',exact=True).click()
   await expect(page.locator('.inline-text')).to_have_count(0,timeout=20000)
   await expect(page.get_by_label('Layer font',exact=True)).to_be_visible()
   await expect(page.get_by_label('Select PDF layer').locator('option')).to_have_count(3)
   await page.get_by_label('Layer font',exact=True).select_option('cour')
   await page.get_by_label('Layer font size',exact=True).fill('24')
   await page.get_by_role('button',name='Apply layer changes',exact=True).click();await expect(page.locator('.busy-layer')).to_have_count(0,timeout=20000)
   await expect(page.get_by_label('Layer font size',exact=True)).to_have_value('24')
   box=page.locator('.object-selected');await box.scroll_into_view_if_needed();r=await box.bounding_box();z=(await surface.bounding_box())['width']/595
   await page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);await page.mouse.down();await page.mouse.move(r['x']+r['width']/2+20*z,r['y']+r['height']/2+30*z,steps=8);await page.mouse.up()
   await expect(page.locator('.busy-layer')).to_have_count(0,timeout=20000)
   handle=page.get_by_role('button',name='Resize selected layer',exact=True);await expect(handle).to_be_enabled();await handle.scroll_into_view_if_needed();r=await handle.bounding_box()
   await page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);await page.mouse.down();await page.mouse.move(r['x']+r['width']/2+35*z,r['y']+r['height']/2+25*z,steps=8);await page.mouse.up()
   await expect(page.locator('.busy-layer')).to_have_count(0,timeout=20000)
   await expect(page.get_by_role('button',name='Resize selected layer',exact=True)).to_be_enabled();await page.get_by_label('Layer font size',exact=True).fill('12');await page.get_by_role('button',name='Apply layer changes',exact=True).click();await expect(page.locator('.busy-layer')).to_have_count(0,timeout=20000)
   await page.get_by_role('button',name='Add another text box',exact=True).click();await page.get_by_label('New text font',exact=True).select_option('hebo')
   await at(50,350);await expect(f).to_be_focused(timeout=20000);await f.fill('Third independent text box')
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   out=OUT/f'text-boxes-{mobile}.pdf';await(await dl.value).save_as(out)
   from backend.layers import inspect_layers
   objects=inspect_layers(out.read_bytes(),0);assert len(objects)==3,objects
   second=next(o for o in objects if o['text'].startswith('Second'));assert second['font']=='cour' and second['size']==12 and second['rect'][0]>60 and second['rect'][1]>195,second
   assert next(o for o in objects if o['text'].startswith('Third'))['font']=='hebo'
   with fitz.open(out) as d:assert all(t in d[0].get_text() for t in ['First independent','Second independent','Third independent'])
   await page.screenshot(path=str(OUT/f'text-boxes-{mobile}.png'))
   # Insert a real image into the blank-origin document, then OCR its text.
   async with page.expect_file_chooser() as chooser:await page.get_by_role('toolbar').get_by_role('button',name='Image',exact=True).click()
   await(await chooser.value).set_files(image_fixture());await expect(page.locator('.busy-layer')).to_have_count(0,timeout=20000)
   await page.get_by_role('toolbar').get_by_role('button',name='OCR',exact=True).click();await page.get_by_label('OCR output mode').select_option('layout');await page.get_by_role('button',name='Start OCR',exact=True).click();await expect(page.locator('.busy-layer')).to_have_count(0,timeout=60000)
   target=page.get_by_role('textbox',name=re.compile('^Edit paragraph: IMAGE WORDS'))
   await target.click(timeout=30000);await expect(f).to_be_focused(timeout=20000);await f.fill('IMAGE WORDS ARE EDITED')
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   out=OUT/f'text-boxes-image-ocr-{mobile}.pdf';await(await dl.value).save_as(out)
   with fitz.open(out) as d:assert 'IMAGE WORDS ARE EDITED' in ' '.join(d[0].get_text().split())
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'blank_pdf':True,'three_independent_boxes':True,'font_and_size':True,'drag_and_resize':True,'download_reopened':True,'inserted_image_ocr_edited':True}),flush=True)
   await ctx.close()
  await b.close()
if __name__=='__main__':asyncio.run(main())
