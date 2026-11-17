"""Real browser fixed-size reflow, save, download and reupload regression."""
import asyncio,json,os,re,shutil,sys,subprocess
from pathlib import Path
from playwright.async_api import async_playwright,expect
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from backend import layers
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3018')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Use a loopback test server.')

def sample():
 path=OUT/'fixed-size-source.pdf'
 with fitz.open() as doc:
  p=doc.new_page(width=420,height=500);xref=p.insert_font(fontname='body',fontbuffer=layers.font_buffer('helv'));layers.normalize_space_map(doc,xref)
  for y,text in [(55,'Link-'),(90,"I'm feeling happy Today"),(210,'Keep this separate paragraph.')]:p.insert_text((45,y),text,fontname='body',fontsize=18)
  doc.save(path)
 return path

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':os.environ.get('FOLIO_TEST_PASSWORD','browser-test-only')})
   page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto(BASE);await page.locator('input[type=file]').first.set_input_files(sample())
   await page.get_by_role('textbox',name=re.compile("^Edit paragraph: I'm feeling")).click()
   field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True);await expect(field).to_be_focused(timeout=20000)
   original_size=await field.evaluate('el=>parseFloat(getComputedStyle(el).fontSize)')
   await field.evaluate("""el=>{const n=el.firstChild,i=n.textContent.indexOf('feeling'),r=document.createRange();r.setStart(n,i);r.setEnd(n,i+7);const s=window.getSelection();s.removeAllRanges();s.addRange(r)}""")
   async with page.expect_response(lambda r:r.url.endswith('/inline-edit') and r.request.method=='POST') as pending:await page.keyboard.insert_text('Enthusiam')
   response=await(await pending.value).json();assert response['inline_block']['size']==18
   assert await field.inner_text()=="I'm Enthusiam happy Today"
   assert await field.evaluate('el=>parseFloat(getComputedStyle(el).fontSize)')==original_size
   text="I'm feeling really enthusiastic and happy Today and ready to make this type of video."
   async with page.expect_response(lambda r:r.url.endswith('/inline-edit') and r.request.method=='POST') as pending:await field.fill(text)
   response=await(await pending.value).json();assert response['inline_block']['size']==18
   assert response['inline_block']['rect'][3]>110
   assert await field.evaluate('el=>parseFloat(getComputedStyle(el).fontSize)')==original_size
   await page.screenshot(path=str(OUT/f'fixed-size-{mobile}.png'))
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'fixed-size-{mobile}.pdf';await(await dl.value).save_as(output)
   independent=' '.join(subprocess.check_output(['pdftotext',str(output),'-'],text=True).split());assert text in independent
   with fitz.open(output) as doc:
    spans=[s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans']];assert all(s['size']==18 for s in spans)
    words=[w for w in doc[0].get_text('words') if 65<w[1]<180];assert len({round(w[1],1) for w in words})>=2
    assert all(w[2]<=375.02 for w in words) and 'Keep this separate paragraph.' in doc[0].get_text()
   await page.locator('input[type=file]').first.set_input_files(output)
   await page.get_by_role('textbox',name=re.compile("^Edit paragraph: I'm feeling really")).click();await expect(field).to_be_focused(timeout=20000)
   await field.fill("I'm Enthusiam happy Today")
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   reopened=OUT/f'fixed-size-reopened-{mobile}.pdf';await(await dl.value).save_as(reopened)
   with fitz.open(reopened) as doc:assert "I'm Enthusiam happy Today" in doc[0].get_text()
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'inline_font_unchanged':True,'word_replacement':True,'following_words_reflow':True,'wraps_within_page':True,'download_independent_reopen':True,'reuploaded_text_editable':True}),flush=True)
   await ctx.close()
  await browser.close()
if __name__=='__main__':asyncio.run(main())
