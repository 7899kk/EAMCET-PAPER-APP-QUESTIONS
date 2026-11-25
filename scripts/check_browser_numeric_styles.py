"""Exercise mixed-style numbers, first-save formatting and actual PDF downloads."""
import asyncio,json,os,shutil,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent))
import pymupdf as fitz
from playwright.async_api import async_playwright,expect
from backend import blocks
from tests.test_numeric_styles import numeric_pdf

OUT=Path(__file__).resolve().parent.parent/'tests/artifacts/browser';OUT.mkdir(parents=True,exist_ok=True)
BASE=os.environ.get('FOLIO_TEST_URL','http://127.0.0.1:3025')
if not BASE.startswith(('http://127.0.0.1:','http://localhost:')) and os.environ.get('FOLIO_ALLOW_GENERATED_LIVE_TEST')!='1':
    raise RuntimeError('Enable live checks explicitly; only generated fixtures are used.')

async def main():
    sample=OUT/'numeric-styles-source.pdf';sample.write_bytes(numeric_pdf())
    async with async_playwright() as p:
        browser=await p.chromium.launch(executable_path=shutil.which('chromium'),args=['--no-sandbox'])
        for mobile in [False,True]:
            ctx=await browser.new_context(viewport={'width':390,'height':844} if mobile else {'width':1440,'height':1000},is_mobile=mobile,has_touch=mobile,accept_downloads=True)
            page=await ctx.new_page();errors=[];tokens=set()
            page.on('request',lambda r:tokens.add(r.headers['x-session']) if 'x-session' in r.headers else None)
            page.on('pageerror',lambda e:errors.append(str(e)));await page.goto(BASE)
            started=time.perf_counter()
            await page.locator('input[type=file]').first.set_input_files(sample)
            number=page.get_by_role('textbox',name='Edit paragraph: Invoice total: 12345',exact=True)
            await expect(number).to_be_visible(timeout=30000);upload_ms=round((time.perf_counter()-started)*1000)
            await page.get_by_role('textbox',name='Edit paragraph: 24680',exact=True).click()
            await expect(page.get_by_role('button',name='Bold text',exact=True)).to_have_attribute('aria-pressed','true')
            started=time.perf_counter();await number.click()
            field=page.get_by_role('textbox',name='Edit text directly on PDF',exact=True)
            await expect(field).to_be_focused(timeout=20000);click_ms=round((time.perf_counter()-started)*1000)
            await expect(page.get_by_role('button',name='Bold text',exact=True)).to_have_attribute('aria-pressed','false')
            await expect(page.get_by_label('Text box font size',exact=True)).to_have_value('18')
            assert await field.locator('span').count()==2
            assert (await field.locator('span').last.inner_text())=='12345'
            await field.press('Control+End');await field.press('Control+Shift+ArrowLeft')
            assert await page.evaluate('window.getSelection().toString()')=='12345'
            await page.keyboard.insert_text('98765.00')
            async with page.expect_download(timeout=30000) as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
            output=OUT/f'numeric-styles-{mobile}.pdf';await(await dl.value).save_as(output)
            changed=output.read_bytes();source=sample.read_bytes()
            original=next(b for b in blocks.inspect_blocks(source,0) if '12345' in b['text'])
            edited=next(b for b in blocks.inspect_blocks(changed,0) if '98765.00' in b['text'])
            assert blocks.font_for_block(source,0,original,original['style_runs'][-1]['font_key'])==blocks.font_for_block(changed,0,edited,edited['style_runs'][-1]['font_key'])
            assert edited['size']==18 and edited['style_runs'][-1]['color']==original['style_runs'][-1]['color'] and edited['font']==original['font']
            with fitz.open(output) as doc:assert '12345' not in doc[0].get_text() and 'Invoice total:' in doc[0].get_text()
            # Copy/delete must keep the original mixed-font object intact.
            await page.get_by_role('textbox',name='Edit paragraph: Invoice total: 98765.00',exact=True).click()
            await page.get_by_role('button',name='Duplicate text box',exact=True).click()
            await expect(field).to_be_focused(timeout=20000)
            await page.get_by_role('button',name='Delete text box',exact=True).click()
            await expect(field).to_have_count(0,timeout=20000)
            # The first save of a native object must apply properties, even
            # when its text has not changed and no managed layer exists yet.
            await page.get_by_role('textbox',name='Edit paragraph: Unchanged body and image area.',exact=True).click()
            await expect(field).to_be_focused(timeout=20000)
            await expect(page.get_by_role('button',name='Bold text',exact=True)).to_have_attribute('aria-pressed','false')
            await page.get_by_label('Text box font',exact=True).select_option('heit')
            await page.get_by_label('Text box font size',exact=True).fill('17')
            await page.get_by_label('Text box colour',exact=True).fill('#336699')
            async with page.expect_download(timeout=30000) as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
            formatted=OUT/f'numeric-formatting-{mobile}.pdf';await(await dl.value).save_as(formatted)
            with fitz.open(formatted) as doc:
                label=next(s for b in doc[0].get_text('dict')['blocks'] for l in b.get('lines',[]) for s in l['spans'] if 'Unchanged body' in s['text'])
                assert label['font']=='LiberationSans-Italic' and label['size']==17 and label['color']==0x336699,label
            # Open the downloaded file as a new document and edit the amount again.
            await page.reload();await page.locator('input[type=file]').first.set_input_files(formatted)
            await page.get_by_role('textbox',name='Edit paragraph: Invoice total: 98765.00',exact=True).click(timeout=30000)
            await expect(field).to_be_focused(timeout=20000)
            await expect(page.get_by_role('button',name='Bold text',exact=True)).to_have_attribute('aria-pressed','false')
            async def delayed_save(route):
                response=await route.fetch();await asyncio.sleep(.7);await route.fulfill(response=response)
            await page.route('**/api/document/inline-edit',delayed_save)
            async with page.expect_request('**/api/document/inline-edit'):
                await field.fill('Invoice total: 55555.99')
            await field.press('Control+End');await field.press('Enter')
            await page.keyboard.insert_text('Next line with spaces')
            await expect(field).to_have_text('Invoice total: 55555.99\nNext line with spaces')
            await page.screenshot(path=str(OUT/f'numeric-styles-{mobile}.png'))
            async with page.expect_download(timeout=30000) as dl:await page.get_by_role('button',name='Download PDF',exact=True).click()
            reopened=OUT/f'numeric-reopened-{mobile}.pdf';await(await dl.value).save_as(reopened)
            final=next(b for b in blocks.inspect_blocks(reopened.read_bytes(),0) if '55555.99' in b['text'])
            assert blocks.font_for_block(reopened.read_bytes(),0,final,final['style_runs'][-1]['font_key'])==blocks.font_for_block(source,0,original,original['style_runs'][-1]['font_key'])
            assert final['size']==18 and final['style_runs'][-1]['color']==original['style_runs'][-1]['color']
            with fitz.open(reopened) as doc:assert 'Next line with spaces' in doc[0].get_text()
            await page.unroute('**/api/document/inline-edit',delayed_save)
            assert not errors,errors
            for token in tokens:
                status=await page.evaluate("async token=>(await fetch('/api/document',{method:'DELETE',headers:{'X-Session':token}})).status",token)
                assert status in (200,404)
            print(json.dumps({'mobile':mobile,'mixed_line_numeric_font_bytes_preserved':True,'original_bold_control_correct':True,'first_native_save_formats_without_text_change':True,'download_reupload_repeat_edit':True,'upload_to_editable_ms':upload_ms,'click_to_typing_ms':click_ms,'browser_errors':errors}),flush=True)
            await ctx.close()
        await browser.close()

if __name__=='__main__':asyncio.run(main())
