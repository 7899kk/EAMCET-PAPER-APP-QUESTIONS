"""Real desktop/touch regression for the reported readable-text/layer/OCR bugs."""
import asyncio,io,json,os,shutil,subprocess,sys
from pathlib import Path
import pymupdf as fitz
from PIL import Image
from playwright.async_api import async_playwright,expect
from check_browser_upload import settled
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
from backend.layers import inspect_layers
from tests.test_readable_layers import scanned

OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser'
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3017')
PHRASE='Ashok one two three four five six seven eight nine ten.\nThis is a longer message with spaces that must stay readable.'

async def main():
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox'])
  for mobile in [False,True]:
   context=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':960},is_mobile=mobile,has_touch=mobile,accept_downloads=True,http_credentials={'username':'folio','password':'browser-test-only'})
   page=await context.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
   await page.goto(BASE);await page.get_by_role('button',name='Try sample PDF',exact=True).click();await settled(page)
   toolbar=page.get_by_role('toolbar',name='PDF editing tools')
   async def tool(name):await toolbar.get_by_role('button',name=name,exact=True).click()
   async def point(x,y):
    surface=page.locator('.pdf-surface');box=await surface.bounding_box();z=box['width']/595
    await page.locator('.canvas-scroll').evaluate('(el,args)=>{el.scrollTop=Math.max(0,args.y*args.z-el.clientHeight/2)}',{'y':y,'z':z})
    box=await surface.bounding_box();return (box['x']+x*z,box['y']+y*z)
   async def drag(start,end):
    if mobile:
     cdp=await context.new_cdp_session(page)
     await cdp.send('Input.dispatchTouchEvent',{'type':'touchStart','touchPoints':[{'x':start[0],'y':start[1]}]})
     for i in range(1,9):
      await cdp.send('Input.dispatchTouchEvent',{'type':'touchMove','touchPoints':[{'x':start[0]+(end[0]-start[0])*i/8,'y':start[1]+(end[1]-start[1])*i/8}]});await page.wait_for_timeout(25)
     await cdp.send('Input.dispatchTouchEvent',{'type':'touchEnd','touchPoints':[]});await cdp.detach()
    else:
     await page.mouse.move(*start);await page.mouse.down();await page.mouse.move(*end,steps=10);await page.wait_for_timeout(40);await page.mouse.up()
    await expect(page.locator('.busy-layer')).to_have_count(0,timeout=20000);await settled(page)
   async def download(name):
    async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
    path=OUT/name;await(await dl.value).save_as(path);return path
   await page.get_by_role('button',name='Edit word: brown',exact=True).first.click()
   await page.get_by_role('textbox',name='Edit selected word',exact=True).fill(PHRASE)
   await page.get_by_role('button',name='Save word',exact=True).click()
   layer_text=page.get_by_role('textbox',name='Layer text',exact=True)
   await expect(layer_text).to_have_value(PHRASE);await settled(page)
   await page.screenshot(path=str(OUT/f'readable-replacement-{mobile}.png'))
   target=page.get_by_role('button',name='Select text layer 1',exact=True);await target.scroll_into_view_if_needed();box=await target.bounding_box()
   await drag((box['x']+10,box['y']+10),(box['x']+25,box['y']+25))
   moved=await target.bounding_box();assert moved['x']>box['x']+8
   corner=page.get_by_role('button',name='Resize selected layer',exact=True);await corner.scroll_into_view_if_needed();box=await corner.bounding_box()
   await drag((box['x']+box['width']/2,box['y']+box['height']/2),(box['x']+box['width']/2-50,box['y']+box['height']/2+10))
   await page.get_by_label('Layer font size',exact=True).fill('18');await page.get_by_role('button',name='Apply layer changes',exact=True).click();await expect(page.locator('.busy-layer')).to_have_count(0);await settled(page)
   # A blank Add text action opens a real on-page composer rather than an error.
   await tool('Add text');xy=await point(45,550);await page.mouse.click(*xy)
   await expect(page.get_by_role('textbox',name='New text box content',exact=True)).to_be_visible()
   await page.get_by_role('textbox',name='New text box content',exact=True).fill('Additional text with spaces\nand a second line.')
   await page.get_by_role('button',name='Add text box',exact=True).click();await expect(layer_text).to_have_value('Additional text with spaces\nand a second line.');await settled(page)
   image=OUT/f'layer-image-{mobile}.png';Image.new('RGB',(120,80),'red').save(image)
   async with page.expect_file_chooser() as chooser:await tool('Image')
   await(await chooser.value).set_files(image)
   target=page.get_by_role('button',name='Select image layer 3',exact=True);await expect(target).to_be_visible();await settled(page);await target.scroll_into_view_if_needed();box=await target.bounding_box()
   await drag((box['x']+12,box['y']+12),(box['x']+42,box['y']+52))
   await corner.scroll_into_view_if_needed();box=await corner.bounding_box();await drag((box['x']+box['width']/2,box['y']+box['height']/2),(box['x']+box['width']/2-25,box['y']+box['height']/2-15))
   await page.get_by_role('button',name='Delete layer',exact=True).click();await expect(target).to_have_count(0)
   await page.get_by_role('button',name='Undo',exact=True).click();await expect(target).to_have_count(1)
   await page.get_by_role('button',name='Redo',exact=True).click();await expect(target).to_have_count(0)
   # Brush follows a nonrectangular mouse/finger path and saves transparency.
   await tool('Highlight');await page.get_by_label('Highlight brush size',exact=True).fill('20')
   start=await point(55,118);surface=await page.locator('.pdf-surface').bounding_box();z=surface['width']/595
   await drag(start,(start[0]+240*z,start[1]+7*z))
   await tool('Layers');target=page.get_by_role('button',name='Select brush layer 3',exact=True);await target.click();await expect(page.get_by_role('button',name='Delete layer',exact=True)).to_be_visible()
   await page.get_by_role('button',name='Delete layer',exact=True).click();await expect(target).to_have_count(0)
   await page.get_by_role('button',name='Undo',exact=True).click();await expect(target).to_have_count(1)
   await settled(page);await page.screenshot(path=str(OUT/f'layers-brush-{mobile}.png'))
   output=await download(f'readable-layers-{mobile}.pdf');data=output.read_bytes();objects=inspect_layers(data,0)
   assert len(objects)==3 and [o['type'] for o in objects]==['text','text','brush']
   assert objects[0]['size']==18 and objects[0]['text']==PHRASE
   with fitz.open(output) as doc:
    text=' '.join(doc[0].get_text().split());assert 'Ashok one two three four' in text and 'Additional text with spaces' in text and 'quick brown fox' not in text
    assert not doc[0].get_images()
    strokes=doc[0].get_drawings();assert any(d['stroke_opacity']<.5 for d in strokes)
   extracted=subprocess.check_output(['pdftotext',str(output),'-'],text=True);assert 'Ashok one two' in extracted
   await page.locator('input[type=file]').first.set_input_files(output);await settled(page);await tool('Layers')
   await page.get_by_role('button',name='Select text layer 1',exact=True).click();await expect(layer_text).to_have_value(PHRASE)
   assert not errors,errors
   print(json.dumps({'viewport':'mobile touch' if mobile else 'desktop','long_replacement_spaces_no_squash':'passed','add_edit_move_resize_text':'passed','image_move_resize_delete_undo':'passed','brush_delete_undo':'passed','download_reopen_layers':'passed','browser_errors':errors}),flush=True)
   await context.close()
  # Actual OCR UI, not mocked API responses.
  context=await browser.new_context(viewport={'width':1440,'height':960},accept_downloads=True,http_credentials={'username':'folio','password':'browser-test-only'})
  page=await context.new_page();await page.goto(BASE);scan=OUT/'ocr-source.pdf';scan.write_bytes(scanned());await page.locator('input[type=file]').first.set_input_files(scan);await settled(page)
  toolbar=page.get_by_role('toolbar',name='PDF editing tools')
  for mode in ['searchable','editable']:
   await toolbar.get_by_role('button',name='OCR',exact=True).click();await page.get_by_label('OCR output mode',exact=True).select_option(mode);await page.get_by_role('button',name='Start OCR',exact=True).click()
   await expect(page.locator('.busy-layer')).to_have_count(0,timeout=45000);await expect(page.get_by_role('alert')).to_have_count(0);await settled(page)
   if mode=='searchable':
    await page.get_by_role('button',name='Search PDF text',exact=True).click();await page.get_by_placeholder('Find text in your PDF…').fill('ASHOK');await page.get_by_role('button',name='Search',exact=True).click();await expect(page.locator('.search-results button')).to_have_count(1)
    await page.get_by_role('button',name='Close search',exact=True).click()
  await page.get_by_role('button',name='Edit word: ASHOK',exact=True).click();await page.get_by_role('textbox',name='Edit selected word',exact=True).fill('JOHN');await page.get_by_role('button',name='Save word',exact=True).click();await expect(page.get_by_role('button',name='Edit word: JOHN',exact=True)).to_be_visible();await settled(page)
  async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
  output=OUT/'ocr-edited-copy.pdf';await(await dl.value).save_as(output)
  with fitz.open(output) as doc:assert 'JOHN' in doc[0].get_text() and 'ASHOK' not in doc[0].get_text() and not doc[0].get_images()
  await page.screenshot(path=str(OUT/'ocr-edited-copy.png'))
  print('PASS: real OCR searchable output, search, editable reconstruction, text edit, download and independent reopen',flush=True)
  await context.close();await browser.close()

if __name__=='__main__':asyncio.run(main())
