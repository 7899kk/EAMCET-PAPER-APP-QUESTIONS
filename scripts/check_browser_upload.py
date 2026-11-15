"""Real local browser regression; see docs/TESTING.md for commands."""
import asyncio,json,subprocess,os,sys,shutil
from urllib.parse import urlsplit,quote
from pathlib import Path
from playwright.async_api import async_playwright,expect
import pymupdf as fitz

ROOT=Path(__file__).resolve().parent.parent
sys.path.insert(0,str(ROOT))
OUTPUT=ROOT/'tests/artifacts/browser'
OUTPUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3013').rstrip('/')
PASSWORD=os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only')
if urlsplit(BASE).hostname not in ('localhost','127.0.0.1','::1'):
 raise RuntimeError('This regression script is for a local test server only.')
FIXTURE=ROOT/'tests/artifacts/selectable.pdf'
if not FIXTURE.exists():
 from tests.test_engine import fixture
 FIXTURE.parent.mkdir(parents=True,exist_ok=True);FIXTURE.write_bytes(fixture())

async def settled(page):
 await page.wait_for_function('''()=>{
  const surface=document.querySelector('.pdf-surface');const canvas=surface?.querySelector('canvas');
  return canvas && canvas.dataset.renderedRevision===surface.dataset.revision && canvas.dataset.renderedPage===surface.dataset.page;
 }''',timeout=20000)

async def upload(page):
 await page.locator('input[type=file]').first.set_input_files(FIXTURE)
 await expect(page.get_by_role('button',name='Edit word: Original',exact=True)).to_be_visible(timeout=20000)
 await expect(page.get_by_role('alert')).to_have_count(0)
 await settled(page)

async def main():
 async with async_playwright() as p:
  executable=os.environ.get('FOLIO_CHROMIUM') or shutil.which('chromium') or shutil.which('google-chrome')
  browser=await p.chromium.launch(**({'executable_path':executable} if executable else {}),headless=True,args=['--no-sandbox'])
  # Reproduce the original failing credential-URL case with the fixed client.
  context=await browser.new_context(viewport={'width':1440,'height':960})
  page=await context.new_page();errors=[]
  page.on('pageerror',lambda e:errors.append(str(e)))
  parts=urlsplit(BASE)
  login_url=parts._replace(netloc='folio:'+quote(PASSWORD,safe='')+'@'+parts.netloc).geturl()
  await page.goto(login_url,wait_until='networkidle')
  await upload(page)
  assert not errors,errors
  cookies=await context.cookies()
  cookie=next(c for c in cookies if c['name']=='folio_preview_auth')
  assert cookie['httpOnly'] and cookie['sameSite']=='Strict'
  await context.close()
  print('PASS: upload after credential-URL login; signed HTTP-only cookie issued',flush=True)
  # A fresh browser context has no Basic credentials, only the signed cookie.
  for mobile in [False,True]:
   context=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True)
   await context.add_cookies(cookies)
   page=await context.new_page();errors=[];failed=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('requestfailed',lambda r:failed.append(r.failure))
   await page.goto(BASE,wait_until='networkidle')
   await upload(page)
   await page.get_by_role('button',name='Edit word: Original',exact=True).click()
   if mobile:
    await page.get_by_role('button',name='Show word properties',exact=True).click()
    await expect(page.get_by_role('textbox',name='Replacement word',exact=True)).to_have_value('Original')
    await page.get_by_role('button',name='Back to word editor',exact=True).click()
   await expect(page.get_by_role('textbox',name='Edit selected word',exact=True)).to_have_value('Original')
   await page.get_by_role('textbox',name='Edit selected word',exact=True).fill('Revised')
   await page.get_by_role('textbox',name='Edit selected word',exact=True).press('Enter')
   await expect(page.get_by_role('button',name='Edit word: Revised',exact=True)).to_be_visible()
   if not mobile:
    await page.get_by_role('button',name='Add text',exact=True).click()
    await page.locator('.properties-panel textarea').fill('Browser added note')
    await page.locator('.pdf-surface').click(position={'x':80,'y':180})
    await expect(page.locator('.busy-layer')).to_have_count(0)
    await page.get_by_role('button',name='Edit text',exact=True).click()
    await expect(page.get_by_role('button',name='Select text layer 1',exact=True)).to_be_visible()
    await page.get_by_role('button',name='Delete page 2',exact=True).click()
    await expect(page.locator('.page-card')).to_have_count(2)
    await page.get_by_role('button',name='Open page 2',exact=True).click()
    await page.get_by_role('button',name='Rotate current page clockwise',exact=True).click()
    await expect(page.locator('.busy-layer')).to_have_count(0)
   await settled(page)
   await page.wait_for_load_state('networkidle')
   await page.screenshot(path=str(OUTPUT/('fixed-mobile.png' if mobile else 'fixed-desktop.png')),full_page=True)
   async with page.expect_download() as downloaded:
    await page.get_by_role('button',name='Download PDF',exact=True).click()
   download=await downloaded.value
   dest=OUTPUT/('mobile-downloaded.pdf' if mobile else 'desktop-downloaded.pdf')
   await download.save_as(dest)
   with fitz.open(dest) as doc:
    text=''.join(p.get_text() for p in doc)
    assert 'Revised contract' in text and 'Original contract' not in text
    if not mobile:assert len(doc)==2 and doc[1].rotation==90 and 'Browser added note' in text
   independent=subprocess.check_output(['pdftotext',str(dest),'-'],text=True)
   assert 'Revised contract' in independent and 'Original contract' not in independent
   assert not errors,errors
   assert not [e for e in failed if e!='net::ERR_ABORTED'],failed
   print(json.dumps({'viewport':'mobile' if mobile else 'desktop','upload':'passed','cookie_only_login':'passed','existing_text_edit':'passed','download_reopen':'passed','browser_errors':errors}),flush=True)
   await context.close()
  await browser.close()

if __name__=='__main__':asyncio.run(main())
