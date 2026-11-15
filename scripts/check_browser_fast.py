"""Real browser checks for saved keyboard navigation and lightweight previews."""
import asyncio,json,os,shutil,sys,time
from pathlib import Path
import pymupdf as fitz
from playwright.async_api import async_playwright,expect
from check_browser_upload import settled

ROOT=Path(__file__).resolve().parent.parent
OUT=ROOT/'tests/artifacts/browser'
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3016')

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
  for mobile in [False,True]:
   context=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':'browser-test-only'})
   page=await context.new_page();errors=[];requests=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('request',lambda r:requests.append(r.url))
   await page.goto(BASE)
   await page.get_by_role('button',name='Try sample PDF',exact=True).click()
   await settled(page)
   await page.get_by_role('button',name='Edit word: brown',exact=True).first.click()
   if mobile:await expect(page.locator('.properties-panel')).to_be_hidden()
   field=page.get_by_role('textbox',name='Edit selected word',exact=True)
   await field.fill('red');await field.press('Tab')
   await expect(field).to_have_value('fox')
   assert await field.evaluate('el=>document.activeElement===el')
   operations=lambda:len([u for u in requests if u.endswith('/operation')])
   assert operations()==1
   await page.get_by_role('button',name='Save and edit previous word',exact=True).click()
   await expect(field).to_have_value('red')
   await field.press('Shift+Tab');await expect(field).to_have_value('quick')
   assert operations()==1,'Unchanged words must not create PDF revisions'
   await field.fill('fast')
   await page.get_by_role('button',name='Save and edit next word',exact=True).click()
   await expect(field).to_have_value('red');assert operations()==2
   await field.fill('bad\x01text');await field.press('Tab')
   await expect(page.get_by_role('alert')).to_be_visible()
   await expect(field).to_have_value('bad\x01text')
   exports=len([u for u in requests if u.endswith('/export')])
   await page.get_by_role('button',name='Download PDF',exact=True).click()
   await expect(page.locator('.busy-layer')).to_have_count(0)
   await expect(field).to_have_value('bad\x01text')
   assert len([u for u in requests if u.endswith('/export')])==exports,'Invalid draft must block download'
   await field.fill('red');await field.press('Escape')
   await page.get_by_role('button',name='Dismiss error',exact=True).click()
   # Download must commit a draft without requiring a separate Save click.
   await page.get_by_role('button',name='Edit word: fox',exact=True).first.click()
   await field.fill('cat')
   async with page.expect_download() as dl:
    await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'fast-words-{mobile}.pdf';await(await dl.value).save_as(output)
   with fitz.open(output) as doc:
    saved=' '.join(doc[0].get_text().split())
    assert 'The fast red cat' in saved and 'quick brown fox' not in saved,saved
   assert not [u for u in requests if u.endswith('/api/document/pdf')]
   assert not errors,errors
   await settled(page)
   await page.get_by_role('button',name='Edit word: cat',exact=True).first.click()
   await page.screenshot(path=str(OUT/f'fast-word-editor-{mobile}.png'))
   print(json.dumps({'viewport':'mobile' if mobile else 'desktop','Tab_ShiftTab_buttons':'passed','unchanged_word_no_rewrite':'passed','invalid_word_preserved':'passed','download_saves_draft':'passed','page_only_previews':'passed','browser_errors':errors}),flush=True)
   await context.close()
  # A reproducible larger fixture can be provided without committing PDFs.
  if len(sys.argv)>1:
   fixture=Path(sys.argv[1]);context=await browser.new_context(viewport={'width':1440,'height':960},http_credentials={'username':'folio','password':'browser-test-only'})
   page=await context.new_page();requests=[];page.on('request',lambda r:requests.append(r.url));await page.goto(BASE)
   t=time.perf_counter();await page.locator('input[type=file]').first.set_input_files(fixture)
   await expect(page.get_by_role('button',name='Edit word: brown',exact=True).first).to_be_visible(timeout=30000);await settled(page)
   opened_ms=(time.perf_counter()-t)*1000
   await page.wait_for_timeout(700)
   thumbs=[u for u in requests if u.endswith('/thumbnail')]
   assert len(thumbs)<10,thumbs
   assert not [u for u in requests if u.endswith('/api/document/pdf')]
   t=time.perf_counter();await page.get_by_role('button',name='Edit word: brown',exact=True).first.click()
   field=page.get_by_role('textbox',name='Edit selected word',exact=True);await field.fill('red');await field.press('Tab');await expect(field).to_have_value('fox');await settled(page)
   saved_ms=(time.perf_counter()-t)*1000
   await field.press('Escape')
   await page.get_by_role('button',name='Open page 2',exact=True).click();await settled(page)
   await expect(page.get_by_role('button',name='Edit word: brown',exact=True).first).to_be_visible()
   await page.wait_for_timeout(500)
   before=len([u for u in requests if '/page/0/text?' in u])
   await page.get_by_role('button',name='Open page 1',exact=True).click();await settled(page)
   await expect(page.get_by_role('button',name='Edit word: red',exact=True).first).to_be_visible()
   assert len([u for u in requests if '/page/0/text?' in u])==before,'Revisited text should use current-revision cache'
   print(json.dumps({'large_pdf_bytes':fixture.stat().st_size,'upload_to_editable_and_rendered_ms':round(opened_ms),'save_to_next_word_and_rendered_ms':round(saved_ms),'initial_thumbnail_requests':len(thumbs),'return_to_page_uses_cache':True}),flush=True)
   await context.close()
  await browser.close()

if __name__=='__main__':asyncio.run(main())
