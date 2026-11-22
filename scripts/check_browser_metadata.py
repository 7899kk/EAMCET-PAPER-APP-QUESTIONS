"""Real Edit/Clear Metadata UI and exported Info/XMP checks."""
import asyncio,json,os,shutil,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz,pikepdf
from playwright.async_api import async_playwright,expect
from tests.test_metadata import source,VALUES,assert_pages_equal
from backend import metadata
OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3024')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')):raise RuntimeError('Loopback only')
async def main():
 sample=OUT/'metadata-source.pdf';sample.write_bytes(source())
 async with async_playwright() as p:
  browser=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
  for mobile in [False,True]:
   ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':1000},is_mobile=mobile,has_touch=mobile,accept_downloads=True)
   page=await ctx.new_page();errors=[];page.on('pageerror',lambda e:errors.append(str(e)));await page.goto(BASE);await page.locator('input[type=file]').first.set_input_files(sample)
   await expect(page.locator('.pdf-surface')).to_be_visible(timeout=25000)
   await page.get_by_role('button',name='Edit Metadata',exact=True).click()
   dialog=page.get_by_role('dialog')
   await expect(page.get_by_label('Metadata title',exact=True)).to_have_value('Original title')
   for key,label in [('title','title'),('author','author'),('subject','subject'),('keywords','keywords')]:await page.get_by_label('Metadata '+label,exact=True).fill(VALUES[key])
   await dialog.locator('summary').filter(has_text='Advanced properties').click()
   for key,label in [('creator','creator'),('producer','producer'),('creationDate','creation date'),('modDate','modified date')]:await page.get_by_label('Metadata '+label,exact=True).fill(VALUES[key])
   await dialog.locator('summary').filter(has_text='Custom properties').click()
   await page.get_by_role('button',name='Remove custom property CustomNote',exact=True).click()
   await page.get_by_label('Custom property name',exact=True).fill('Department');await page.get_by_label('Custom property value',exact=True).fill('Creative');await page.get_by_role('button',name='Add custom property',exact=True).click()
   await page.get_by_role('button',name='Save metadata',exact=True).click();await expect(dialog).to_have_count(0,timeout=20000)
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   edited=OUT/f'metadata-edited-{mobile}.pdf';await(await dl.value).save_as(edited)
   state=metadata.inspect(edited.read_bytes());assert state['fields']==VALUES and state['custom']=={'Department':'Creative'},state
   assert_pages_equal(sample.read_bytes(),edited.read_bytes())
   with pikepdf.open(edited) as pdf:
    xmp=pdf.open_metadata(set_pikepdf_as_editor=False);assert str(xmp['dc:title'])==VALUES['title'] and list(xmp['dc:creator'])==[VALUES['author']]
   # Clear has its own All tools action.
   await page.get_by_role('toolbar',name='PDF editing tools').get_by_role('button',name='All tools',exact=True).click()
   await dialog.get_by_role('button',name='Clear Metadata',exact=True).click();await expect(dialog.get_by_role('heading',name='Clear Metadata')).to_be_visible(timeout=15000)
   await page.get_by_role('button',name='Clear metadata now',exact=True).click();await expect(dialog).to_have_count(0,timeout=20000)
   async with page.expect_download() as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
   cleared=OUT/f'metadata-cleared-{mobile}.pdf';await(await dl.value).save_as(cleared)
   state=metadata.inspect(cleared.read_bytes());assert not any(state['fields'].values()) and state['custom']=={} and state['xmp_packets']==0,state
   assert_pages_equal(edited.read_bytes(),cleared.read_bytes())
   with pikepdf.open(cleared) as pdf:assert '/Info' not in pdf.trailer and '/Metadata' not in pdf.Root
   await page.get_by_role('button',name='Undo',exact=True).click();await expect(page.locator('.busy-layer')).to_have_count(0,timeout=20000)
   await page.get_by_role('button',name='Edit Metadata',exact=True).click();await expect(page.get_by_label('Metadata title',exact=True)).to_have_value(VALUES['title'])
   await page.screenshot(path=str(OUT/f'metadata-ui-{mobile}.png'));await page.get_by_role('button',name='Close dialog',exact=True).click()
   # Reupload the actual cleared download and inspect its empty properties.
   await page.reload();await page.locator('input[type=file]').first.set_input_files(cleared)
   await page.get_by_role('button',name='Edit Metadata',exact=True).click();await expect(page.get_by_label('Metadata title',exact=True)).to_have_value('')
   assert not errors,errors
   print(json.dumps({'mobile':mobile,'edit_standard_custom_dates':True,'Info_XMP_synced':True,'clear_document_metadata':True,'pages_pixels_unchanged':True,'undo':True,'download_reupload_verified':True}),flush=True)
   await ctx.close()
  await browser.close()
if __name__=='__main__':asyncio.run(main())
