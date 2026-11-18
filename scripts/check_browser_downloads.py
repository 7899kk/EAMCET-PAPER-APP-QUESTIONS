"""Slow-network preparation, repeated clicks, persistent download and retry."""
import asyncio,json,os,re,shutil,sys,subprocess
from pathlib import Path
from playwright.async_api import async_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3018')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Loopback tests only.')
def source():
 path=OUT/'download-source.pdf'
 with fitz.open() as d:
  p=d.new_page();p.insert_text((45,90),'First editable paragraph.',fontsize=18);p.insert_text((45,170),'Second editable paragraph.',fontsize=18);d.save(path)
 return path
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only')})
   page=await ctx.new_page();errors=[];calls=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:calls.append(r.url))
   async def slow(route):await asyncio.sleep(.12);await route.continue_()
   await page.route('**/api/**',slow);await page.goto(BASE)
   assert await page.get_by_role('button',name='Download PDF',exact=True).count()==0
   assert await page.locator('.page-preparing,.busy-layer').count()==0
   await page.locator('input[type=file]').first.set_input_files(source())
   await expect(page.locator('.page-preparing')).to_be_visible(timeout=10000);await expect(page.locator('.page-preparing')).to_have_count(0,timeout=40000)
   def editing_requests():return [u for u in calls if any(v in u for v in ['/font?','/edit-patch?','/pdf','/blocks']) and '/thumbnail' not in u]
   before=len(editing_requests())
   await page.get_by_role('textbox',name='Edit paragraph: First editable paragraph.',exact=True).click()
   field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True);await expect(field).to_be_focused(timeout=3000)
   await page.get_by_role('textbox',name='Edit paragraph: Second editable paragraph.',exact=True).click();await expect(field).to_be_focused(timeout=3000)
   assert len(editing_requests())==before,'Prepared paragraph clicks must not fetch/render another PDF or font.'
   assert await page.locator('.page-preparing,.busy-layer').count()==0
   await field.fill('Second paragraph edited and downloaded.')
   # Simulate a browser blocking asynchronous programmatic downloads.
   await page.evaluate("""()=>{HTMLAnchorElement.prototype.click=function(){if(!this.href.startsWith('blob:'))HTMLElement.prototype.click.call(this)}}""")
   await page.get_by_role('button',name='Download PDF',exact=True).click()
   saved=page.get_by_role('link',name='Save file',exact=True);await expect(saved).to_be_visible(timeout=30000)
   await page.wait_for_timeout(2500) # Prior implementation revoked the URL at 1500ms.
   async with page.expect_download() as dl:await saved.click()
   output=OUT/f'persistent-download-{mobile}.pdf';await(await dl.value).save_as(output)
   text=subprocess.check_output(['pdftotext',str(output),'-'],text=True);assert 'Second paragraph edited and downloaded.' in text and 'First editable paragraph.' in text and 'Second editable paragraph.' not in text
   # A failed export must stop loading, show an error and permit retry.
   async def fail_once(route):await route.fulfill(status=503,content_type='application/json',body='{"detail":"Temporary export failure. Retry download."}')
   await page.route('**/api/document/export',fail_once,times=1)
   button=page.get_by_role('button',name='Download PDF',exact=True);await button.click();await expect(page.get_by_role('alert')).to_contain_text('Temporary export failure');await expect(button).to_be_enabled()
   await button.click();await expect(saved).to_be_visible(timeout=20000);await expect(page.get_by_role('alert')).to_have_count(0)
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'no_loading_before_upload':True,'upfront_preparation':True,'zero_click_time_edit_requests':True,'blocked_auto_download_recovered':True,'download_survives_2500ms':True,'real_pdf_reopened':True,'failed_export_retry':True}),flush=True)
   await ctx.close()
  await browser.close()
if __name__=='__main__':asyncio.run(main())
