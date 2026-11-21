"""Save latency, OCR output modes, Add Text and actual auto-fit regressions."""
import asyncio,json,os,re,shutil,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from playwright.async_api import async_playwright,expect
from browser_helpers import sign_in
from check_browser_multiple import generate
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser'
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3018')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Loopback server only.')
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True)
   await sign_in(ctx,BASE);page=await ctx.new_page();errors=[];requests=[]
   page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:requests.append(r.url))
   await page.goto(BASE);await page.locator('input[type=file]').first.set_input_files(generate())
   target=page.get_by_role('textbox',name="Edit paragraph: I'm feeling happy Today",exact=True)
   await expect(target).to_be_visible(timeout=30000)
   surface=page.locator('.pdf-surface')
   sizes=await page.locator('.canvas-scroll').evaluate("e=>({available:e.clientWidth-parseFloat(getComputedStyle(e).paddingLeft)-parseFloat(getComputedStyle(e).paddingRight),page:e.querySelector('.page-slot').getBoundingClientRect().width})")
   assert 0<=sizes['available']-sizes['page']<=12,sizes
   await page.get_by_role('button',name='Zoom out',exact=True).click();await page.get_by_role('button',name='Fit page width',exact=True).click()
   sizes2=await surface.bounding_box();assert abs(sizes2['width']-sizes['page'])<2
   await target.click();field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True);await expect(field).to_be_focused(timeout=20000)
   await page.wait_for_function("()=>document.querySelector('.pdf-surface').dataset.prepared==='true'")
   revision=await surface.get_attribute('data-revision');patch=await page.locator('.edit-background-patch').get_attribute('src');count=len(requests)
   async def delayed(route):
    response=await route.fetch();await asyncio.sleep(.9);await route.fulfill(response=response)
   await page.route('**/api/document/inline-edit',delayed)
   first="I'm feeling enthusiastic Today."
   final="I'm feeling enthusiastic Today and I can keep typing while the server saves this sentence."
   async with page.expect_request('**/api/document/inline-edit'):await field.fill(first)
   await field.fill(final)
   await expect(page.locator('.editing-guide [role=status]')).to_have_text('All changes saved',timeout=25000)
   assert await field.inner_text()==final
   await expect(field).to_be_focused()
   assert await surface.get_attribute('data-revision')==revision,'Autosave reloaded the canvas'
   assert await page.locator('.edit-background-patch').get_attribute('src')==patch,'Autosave replaced the text background'
   assert not any('/edit-patch?' in u or u.endswith('/pdf') for u in requests[count:]),requests[count:]
   # Add text, type through a delayed first save, then download immediately.
   await page.get_by_role('toolbar').get_by_role('button',name='Add text',exact=True).click()
   await expect(surface).to_have_class(re.compile('tool-text'))
   await page.locator('.canvas-scroll').evaluate("e=>{const s=e.querySelector('.pdf-surface');e.scrollTop=s.offsetTop+500*s.getBoundingClientRect().width/595-e.clientHeight/2}")
   box=await surface.bounding_box();z=box['width']/595;await page.mouse.click(box['x']+45*z,box['y']+500*z)
   await expect(field).to_be_focused(timeout=20000)
   async with page.expect_request('**/api/document/inline-edit'):await field.fill('Added text with spaces')
   added='Added text with spaces and a second line.\nFinal added sentence.'
   await field.fill(added)
   async with page.expect_download() as download:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'stable-save-{mobile}.pdf';await(await download.value).save_as(output)
   independent=' '.join(subprocess.check_output(['pdftotext',str(output),'-'],text=True).split())
   assert final in independent and 'Final added sentence.' in independent
   await page.unroute('**/api/document/inline-edit',delayed)
   # Searchable OCR must offer conversion; both editable OCR outputs must allow repeated edits.
   if mobile:await page.get_by_role('button',name='Toggle page panel',exact=True).click()
   await page.get_by_role('button',name='Open page 2',exact=True).click()
   if mobile and 'mobile-open' in (await page.locator('.pages-panel').get_attribute('class')):await page.get_by_role('button',name='Toggle page panel',exact=True).click()
   for mode in ['searchable','editable','layout']:
    await page.get_by_role('toolbar').get_by_role('button',name='OCR',exact=True).click()
    await page.get_by_label('OCR output mode',exact=True).select_option(mode)
    await page.get_by_label('OCR pages',exact=True).select_option('current')
    await page.get_by_role('button',name='Start OCR',exact=True).click();await expect(page.locator('.busy-layer')).to_have_count(0,timeout=60000)
    if mode=='searchable':
     await expect(page.get_by_role('button',name='Make scanned text editable',exact=True)).to_be_visible(timeout=30000);continue
    target=page.get_by_role('textbox',name=re.compile('^Edit paragraph: Ashok feels happy today'))
    await target.click(timeout=30000);await expect(field).to_be_focused(timeout=20000)
    await field.fill('Kartik feels enthusiastic today.')
    await expect(page.locator('.editing-guide [role=status]')).to_have_text('All changes saved',timeout=25000)
    await field.fill('Ashok feels happy today. The scanned text can be edited twice.')
    async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
    output=OUT/f'stable-ocr-{mode}-{mobile}.pdf';await(await dl.value).save_as(output)
    with fitz.open(output) as d:assert 'The scanned text can be edited twice.' in ' '.join(d[1].get_text().split())
    # Restore the original scan for the next distinct OCR mode.
    if mode=='editable':
     await page.reload();await page.locator('input[type=file]').first.set_input_files(generate())
     if mobile:await page.get_by_role('button',name='Toggle page panel',exact=True).click()
     await page.get_by_role('button',name='Open page 2',exact=True).click()
     if mobile and 'mobile-open' in (await page.locator('.pages-panel').get_attribute('class')):await page.get_by_role('button',name='Toggle page panel',exact=True).click()
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'delayed_saves_keep_latest_text':True,'no_canvas_or_patch_reload_while_typing':True,'add_text_saved_during_pending_request':True,'fit_actual_workspace':True,'searchable_to_editable':True,'both_editable_ocr_modes_reopened':True}),flush=True)
   await ctx.close()
  await browser.close()
if __name__=='__main__':asyncio.run(main())
