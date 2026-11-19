"""Real sign-in gate, fixed-font wrapping, continuous scrolling and export."""
import asyncio,os,shutil,sys,re,json,subprocess
from pathlib import Path
from playwright.async_api import async_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from backend import layers
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3018')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Loopback test server only.')
def generate():
 with fitz.open() as d:
  for i in range(3):
   p=d.new_page();p.insert_text((45,90),'Page '+str(i+1)+' editable sentence.',fontsize=18);p.insert_text((45,370),'Separate paragraph remains here.',fontsize=16)
  data=d.tobytes()
 data=layers.add(data,1,{'type':'text','font':'helv','text':'Ashok','rect':[45,160,95,190],'size':16,'fixed_frame':True,'max_size':16})
 path=OUT/'account-scroll-source.pdf';path.write_bytes(data);return path
async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True)
   page=await ctx.new_page();errors=[];uploads=[];page.on('pageerror',lambda e:errors.append(str(e)));page.on('request',lambda r:uploads.append(r) if r.url.endswith('/api/documents') else None)
   response=await page.goto(BASE);assert response.status==200 and 'www-authenticate' not in await response.all_headers()
   await page.get_by_role('button',name='Choose PDF file',exact=True).click();await expect(page.get_by_role('dialog')).to_be_visible();assert page.url.endswith('/signin') and not uploads
   await page.get_by_label('Username',exact=True).fill('folio');await page.get_by_label('Password',exact=True).fill(os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only'))
   await page.get_by_role('dialog').get_by_role('button',name='Sign in',exact=True).click();await expect(page.get_by_role('dialog')).to_have_count(0)
   await page.locator('input[type=file]').first.set_input_files(generate())
   await page.get_by_role('textbox',name='Edit paragraph: Page 1 editable sentence.',exact=True).click(timeout=30000)
   field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True);await expect(field).to_be_focused(timeout=15000)
   long='Page one contains more text now. '+('Additional words should wrap onto the next line without a scrolling text box. '*2)
   await field.fill(long)
   assert await field.evaluate("e=>getComputedStyle(e).overflowY")=='visible'
   assert await field.evaluate("e=>e.getBoundingClientRect().height")>30
   # Scroll naturally to the next page. No Next/thumbnail click is used.
   await page.locator('.canvas-scroll').evaluate("el=>{el.scrollTop=el.querySelector('[data-index=\"1\"]').offsetTop+30}")
   await page.wait_for_function("()=>document.querySelector('.pdf-surface')?.dataset.page==='1'",timeout=20000)
   await page.get_by_role('textbox',name='Edit paragraph: Ashok',exact=True).click(timeout=25000);await expect(field).to_be_focused(timeout=15000)
   await field.fill('Ashok one two three four five six seven eight nine ten.')
   assert await field.evaluate("e=>getComputedStyle(e).overflowY")=='visible'
   assert await field.evaluate("e=>parseFloat(e.style.width)")>150
   async with page.expect_download() as dl:
    await page.get_by_role('button',name='Download PDF',exact=True).click();await expect(page.locator('.download-progress')).to_be_visible(timeout=5000)
   output=OUT/f'account-scroll-{mobile}.pdf';await(await dl.value).save_as(output)
   text=' '.join(subprocess.check_output(['pdftotext',str(output),'-'],text=True).split());assert long.strip() in text and 'Ashok one two three' in text
   with fitz.open(output) as d:assert len(d)==3 and 'Separate paragraph remains here.' in d[0].get_text()
   await page.reload();await expect(page.get_by_role('button',name='Choose PDF file',exact=True)).to_be_visible()
   await page.get_by_role('button',name='Workspace member',exact=True).click();await expect(page.get_by_role('dialog')).to_be_visible();await page.get_by_role('button',name='Close document and sign out',exact=True).click()
   await page.get_by_role('button',name='Choose PDF file',exact=True).click();await expect(page.get_by_role('dialog')).to_be_visible()
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'signin_gate':True,'no_native_password_popup':True,'remembered_on_reload':True,'no_inner_scrollbar':True,'longer_text_saved':True,'automatic_next_page':True,'download_animation':True,'download_reopened':True,'logout':True}),flush=True)
   await ctx.close()
  await browser.close()
if __name__=='__main__':asyncio.run(main())
