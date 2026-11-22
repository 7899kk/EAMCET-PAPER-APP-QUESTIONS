"""Direct Add Text: contextual formatting, drag, resize, copy/delete and reopen."""
import asyncio,json,os,shutil,sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from playwright.async_api import async_playwright,expect
from backend.layers import inspect_layers
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3022')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Loopback tests only')
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':1000},is_mobile=mobile,has_touch=mobile,accept_downloads=True)
   page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto(BASE);await page.get_by_role('button',name='Start with a blank PDF',exact=True).click()
   surface=page.locator('.pdf-surface');await expect(surface).to_be_visible(timeout=25000)
   await page.wait_for_function("()=>document.querySelector('canvas[data-rendered-page=\"0\"]')")
   async def at(x,y):
    z=(await surface.bounding_box())['width']/595
    await page.locator('.canvas-scroll').evaluate('(e,y)=>e.scrollTop=Math.max(0,y-e.clientHeight/2)',y*z)
    r=await surface.bounding_box();await page.mouse.click(r['x']+x*z,r['y']+y*z)
   async def drag(name,dx,dy):
    handle=page.get_by_role('button',name=name,exact=True);await handle.scroll_into_view_if_needed();r=await handle.bounding_box();z=(await surface.bounding_box())['width']/595
    await page.mouse.move(r['x']+r['width']/2,r['y']+r['height']/2);await page.mouse.down();await page.mouse.move(r['x']+r['width']/2+dx*z,r['y']+r['height']/2+dy*z,steps=12);await page.mouse.up()
   field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True)
   await at(50,130);await expect(field).to_be_focused(timeout=20000);await field.fill('First direct text box')
   assert await page.get_by_role('button',name='Move / resize / style box',exact=True).count()==0
   assert await page.get_by_role('button',name='Apply layer changes',exact=True).count()==0
   # Change properties while the first text save is pending.
   async def delay(route):
    response=await route.fetch();await asyncio.sleep(.7);await route.fulfill(response=response)
   await page.route('**/api/document/inline-edit',delay)
   await page.get_by_label('Text box font',exact=True).select_option('cour')
   await page.get_by_label('Text box font size',exact=True).fill('24')
   await page.get_by_role('button',name='Bold text',exact=True).click()
   await drag('Move text box',30,35)
   await drag('Resize text box',-60,10)
   await expect(page.get_by_label('Text box font size',exact=True)).to_have_value('24')
   # Copy and delete directly, without changing tools.
   await page.get_by_role('button',name='Duplicate text box',exact=True).click()
   await expect(field).to_be_focused(timeout=20000)
   await expect(page.locator('.editing-guide [role=status]')).to_have_text('All changes saved',timeout=30000)
   await page.get_by_role('button',name='Delete text box',exact=True).click()
   await expect(field).to_have_count(0,timeout=25000)
   await page.unroute('**/api/document/inline-edit',delay)
   # Two more independent placements; no Apply or Layers dialog.
   await at(50,330);await expect(field).to_be_focused(timeout=20000);await field.fill('Second direct text box')
   await at(50,450);await expect(field).to_be_focused(timeout=20000);await field.fill('Third direct text box')
   # Select a saved added box directly, then format it in place.
   target=page.get_by_role('textbox',name='Edit paragraph: First direct text box',exact=True)
   await target.click();await expect(field).to_be_focused(timeout=20000)
   await expect(page.get_by_label('Text box font',exact=True)).to_have_value('cobo')
   await page.get_by_label('Text box font',exact=True).select_option('tiro')
   await page.get_by_role('button',name='Italic text',exact=True).click()
   await page.get_by_label('Text box font size',exact=True).fill('20')
   await page.get_by_label('Text box colour',exact=True).fill('#cc3333')
   await page.screenshot(path=str(OUT/f'direct-text-{mobile}.png'))
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'direct-text-{mobile}.pdf';await(await dl.value).save_as(output)
   objects=inspect_layers(output.read_bytes(),0);assert len(objects)==3,objects
   first=next(o for o in objects if o['text']=='First direct text box')
   assert first['font']=='tiit' and first['size']==20 and first['color']=='#cc3333',first
   assert first['rect'][0]>75 and first['rect'][1]>160 and first['rect'][2]-first['rect'][0]<290,first
   with fitz.open(output) as d:
    text=' '.join(d[0].get_text().split());assert all(x in text for x in ['First direct text box','Second direct text box','Third direct text box'])
    spans=[s for b in d[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']]
    assert any('LiberationSerif-Italic'==s['font'] and s['size']==20 for s in spans)
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'direct_typing':True,'contextual_formatting':True,'drag_resize_without_mode_switch':True,'copy_delete':True,'repeat_boxes':True,'delayed_save':True,'real_fonts_and_geometry_reopened':True}),flush=True)
   await ctx.close()
  await browser.close()
if __name__=='__main__':asyncio.run(main())
