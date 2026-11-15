"""Browser proof: sample upload, word editing and selectable persisted PDF shapes."""
import asyncio,json,os,shutil,subprocess
from pathlib import Path
import pymupdf as fitz
from playwright.async_api import async_playwright,expect
from check_browser_upload import settled

OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser'
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3015')

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
  for mobile in [False,True]:
   context=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':'browser-test-only'})
   page=await context.new_page();errors=[];requests=[]
   page.on('pageerror',lambda e:errors.append(str(e)))
   page.on('response',lambda r:requests.append(r) if r.url.endswith('/operation') else None)
   await page.goto(BASE)
   await page.get_by_role('button',name='Try sample PDF',exact=True).click()
   await expect(page.get_by_role('button',name='Edit existing text',exact=True)).to_be_visible()
   await expect(page.get_by_role('button',name='Edit text',exact=True)).to_be_in_viewport()
   await settled(page)
   await page.get_by_role('button',name='Edit word: brown',exact=True).first.click()
   await expect(page.get_by_role('textbox',name='Edit selected word',exact=True)).to_have_value('brown')
   await page.get_by_role('textbox',name='Edit selected word',exact=True).fill('red')
   await page.get_by_role('button',name='Save word',exact=True).click()
   await expect(page.get_by_role('button',name='Edit word: red',exact=True).first).to_be_visible()
   await settled(page)
   await page.screenshot(path=str(OUT/f'word-proof-{mobile}.png'))
   await page.get_by_role('button',name='Shapes',exact=True).click()
   await expect(page.get_by_role('button',name='Ellipse',exact=True)).to_be_visible()
   surface=page.locator('.pdf-surface')
   async def drag(start,end):
    if mobile:
     cdp=await context.new_cdp_session(page)
     await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':start[0],'y':start[1]}]})
     for i in range(1,9):
      await cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':start[0]+(end[0]-start[0])*i/8,'y':start[1]+(end[1]-start[1])*i/8}]})
      await page.wait_for_timeout(25)
     await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]})
     await cdp.detach()
    else:
     await page.mouse.move(*start);await page.mouse.down();await page.mouse.move(*end,steps=10);await page.wait_for_timeout(50);await page.mouse.up()
    await expect(page.locator('.busy-layer')).to_have_count(0,timeout=15000)
    await settled(page)
   async def draw(kind,rect):
    await page.get_by_role('button',name=kind,exact=True).click()
    await surface.scroll_into_view_if_needed()
    box=await surface.bounding_box();z=box['width']/595
    await drag((box['x']+rect[0]*z,box['y']+rect[1]*z),(box['x']+rect[2]*z,box['y']+rect[3]*z))
   await draw('Ellipse',[80,340,220,420])
   target=page.get_by_role('button',name='Select ellipse 1',exact=True)
   await expect(target).to_be_visible(timeout=10000)
   await expect(page.locator('.shape-selected')).to_have_count(1)
   box=await target.bounding_box()
   # Move by dragging with a real pointer/touch gesture.
   await drag((box['x']+box['width']/2,box['y']+box['height']/2),(box['x']+box['width']/2+18,box['y']+box['height']/2+12))
   before=await target.bounding_box()
   assert before['x']>box['x']+10
   corner=await page.get_by_role('button',name='Resize selected shape',exact=True).bounding_box()
   await drag((corner['x']+corner['width']/2,corner['y']+corner['height']/2),(corner['x']+corner['width']/2+20,corner['y']+corner['height']/2+15))
   after=await target.bounding_box();assert after['width']>before['width']+10
   await page.get_by_label('Shape border colour',exact=True).fill('#ff0000')
   await page.get_by_label('Shape border width',exact=True).fill('4')
   await page.get_by_role('checkbox',name='Fill shape',exact=True).check()
   await page.get_by_label('Shape fill colour',exact=True).fill('#ffeecc')
   await page.get_by_role('button',name='Apply style',exact=True).click()
   await expect(page.locator('.busy-layer')).to_have_count(0)
   await settled(page)
   await expect(page.get_by_role('button',name='Edit existing text',exact=True)).to_be_in_viewport()
   await expect(page.get_by_role('button',name='Edit text',exact=True)).to_be_in_viewport()
   assert await page.locator('.editing').evaluate('el=>el.scrollTop')==0
   await page.screenshot(path=str(OUT/f'shape-proof-{mobile}.png'))
   await draw('Rectangle',[270,340,370,410])
   await expect(page.locator('.shape-object')).to_have_count(2)
   await page.get_by_role('button',name='Select shapes',exact=True).click()
   await target.click()
   await expect(page.locator('.shape-selected')).to_have_count(1)
   # Existing shape can be deleted; undo/redo persist its PDF annotation.
   await page.get_by_role('button',name='Delete shape',exact=True).click()
   await expect(page.locator('.shape-object')).to_have_count(1)
   await page.get_by_role('button',name='Undo',exact=True).click()
   await expect(page.locator('.shape-object')).to_have_count(2)
   await page.get_by_role('button',name='Redo',exact=True).click()
   await expect(page.locator('.shape-object')).to_have_count(1)
   await page.get_by_role('button',name='Undo',exact=True).click()
   await expect(page.locator('.shape-object')).to_have_count(2)
   await draw('Line',[80,465,220,465])
   await expect(page.locator('.shape-object')).to_have_count(3)
   corner=await page.get_by_role('button',name='Resize selected shape',exact=True).bounding_box()
   await drag((corner['x']+corner['width']/2,corner['y']+corner['height']/2),(corner['x']+corner['width']/2+12,corner['y']+corner['height']/2+8))
   await expect(page.locator('.shape-object')).to_have_count(3)
   await draw('Arrow',[270,450,390,490])
   await expect(page.locator('.shape-object')).to_have_count(4)
   await page.get_by_role('button',name='Edit existing text',exact=True).click()
   await expect(page.get_by_role('button',name='Edit word: red',exact=True).first).to_be_visible()
   async with page.expect_download() as dl:
    await page.get_by_role('button',name='Download PDF',exact=True).click()
   output=OUT/f'words-shapes-{mobile}.pdf';await(await dl.value).save_as(output)
   with fitz.open(output) as doc:
    text=' '.join(doc[0].get_text().split());assert 'quick red fox' in text and 'quick brown fox' not in text
    saved_page=doc[0];shapes=list(saved_page.annots());assert len(shapes)==4
    ellipse=next(a for a in shapes if a.type[0]==fitz.PDF_ANNOT_CIRCLE)
    assert ellipse.border['width']==4 and ellipse.colors['stroke']==[1,0,0]
   independent=subprocess.check_output(['pdftotext',str(output),'-'],text=True)
   assert 'quick red' in independent and 'brown fox' not in independent
   # Reupload the actual downloaded result and reselect its saved shapes.
   await page.locator('input[type=file]').first.set_input_files(output)
   await settled(page)
   await page.get_by_role('button',name='Shapes',exact=True).click()
   await page.get_by_role('button',name='Select shapes',exact=True).click()
   await expect(page.locator('.shape-object')).to_have_count(4)
   await page.get_by_role('button',name='Select ellipse 1',exact=True).click()
   await expect(page.get_by_label('Shape border width',exact=True)).to_have_value('4')
   assert not errors,errors
   for response in requests:assert response.ok,await response.text()
   print(json.dumps({'viewport':'mobile touch' if mobile else 'desktop','sample':'passed','word_replacement':'passed','shape_types_move_resize_style_delete_undo':'passed','download_reopen_reselect':'passed','browser_errors':errors}),flush=True)
   await context.close()
  await browser.close()

if __name__=='__main__':
 import runpy
 print('Running the current inline UI regression; legacy popup interactions were replaced.',flush=True)
 runpy.run_path(str(Path(__file__).resolve().parent/'check_browser_inline.py'),run_name='__main__')
