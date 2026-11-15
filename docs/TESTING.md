# Verification report

Release `inline-paragraphs-5`, checked on 2026-11-15.

## Current inline editor checks

The canonical current browser suite is `scripts/check_browser_inline.py`. It passed desktop and mobile layout checks for direct typing without underlines or a Save popup, pending-draft save on download/page change, direct Add text, original-image deletion, brush and ellipse export, real searchable/editable OCR and editing its output. Both layouts edited the private supplied nine-page PDF, downloaded it and independently reopened it with Poppler and MuPDF; image counts and page count were preserved. No private fixture is committed.

## Engine checks and previous-release browser history

- **72 Python tests passed with the optional provided-document check** against the real PDF engine and FastAPI API. The production React/Vite build passed.
- Generated fixtures cover selectable text, scanned pages, embedded images, multiple pages, standard and embedded fonts, formatting, repeated words, fragmented words, kerning, spacing and unsupported structures.
- Existing-word edits survive later additions, compression and metadata updates. MuPDF and independent Poppler text extraction reopen exported PDFs. Tests assert the old text is absent and no replacement cover rectangles were introduced.
- Rectangle, ellipse, line and arrow are actual PDF annotations. Tests cover geometry, border/fill/width, moving, resizing, deletion, undo/redo, export, stable identity across content rewrites, invalid input and horizontal lines. Independent Poppler rendering checks that the saved annotation appearance is visible.
- Chromium browser tests passed at desktop 1440×960 and phone 390×844. The shapes workflow uses actual touch events on the phone viewport. The browser uploads the generated sample, replaces just `brown` with `red`, draws all four shapes, selects/moves/resizes/styles/deletes shapes, checks undo/redo, downloads, independently reopens, reuploads the actual download and selects its saved ellipse again. No JavaScript errors occurred.
- Browser assertions verify **Edit text** and **Edit existing text** remain in the viewport after PDF scrolling and shape edits. The desktop grid previously let the entire workspace scroll its toolbar away; the canvas grid item now permits its own scroll area to shrink.
- The prior upload regression still passes: credential-containing login URL, signed HTTP-only cookie, cookie-only subsequent upload, existing text edit and download. Desktop also adds text, deletes a page, rotates another page and verifies saved changes.
- A generated sample was actually edited and downloaded through Sejda, then independently reopened. See [editor guide](EDITOR_GUIDE.md). This established its user interaction, not its proprietary processing internals.

Browser workflows use the real local backend with the same authentication and processing code as the Render image. Render deployment status and the public capability/release endpoint are checked separately. A generated sample passing does not establish compatibility with every user PDF.

## Reproduce

Install Python requirements, Tesseract English, Poppler utilities and DejaVuSans (the embedded-font fixture expects `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`).

```bash
.venv/bin/pip install -r requirements-dev.txt -r requirements-browser.txt
.venv/bin/python -m pytest -q
cd frontend
npm ci
npm run build
cd ..
```

Use installed Chromium/Chrome, or install it with `python -m playwright install chromium`. Start a local test server:

```bash
PORT=3015 FOLIO_PREVIEW_PASSWORD=browser-test-only .venv/bin/python serve.py
```

In another terminal:

```bash
FOLIO_TEST_URL=http://127.0.0.1:3015 .venv/bin/python scripts/check_browser_upload.py
FOLIO_TEST_URL=http://127.0.0.1:3015 .venv/bin/python scripts/check_browser_shapes.py
```

Screenshots and downloaded PDFs are written to `tests/artifacts/browser/` and excluded from source control. These scripts are for loopback test servers and generated fixtures, not arbitrary third-party documents. In the managed execution environment, the API TestClient's event loop required running tests outside the command sandbox; ordinary local terminals do not need that escalation.

## Remaining manual coverage

Safari, Firefox, native iOS/Android file pickers, assistive technology, very large documents and arbitrary third-party fonts are not exhaustively tested. A scanned image cannot be truly word-edited. Font/encoding failures must remain explicit rather than falling back to overlays. Review important output in another PDF reader. Compression can increase file size. Crop is not redaction; verify sensitive redactions independently and close the session to remove undo history.

## Previous-release fast word editing

Current-page previews replace full-document browser reloads. `words_only=true` avoids legacy detection, text inspection excludes image bytes, and server-generated word targets are reused when saving. The server caches up to four current-revision pages within a 4 MB per-session analysis budget included in the overall memory limit. Changes and history invalidate caches. Browser word caches are cleared on close/replacement, bounded to four pages and prefetch only the next page. Only visible/nearby thumbnails are requested.

Still-applicable API tests cover cache reuse during word replacement, invalidation after edit/undo/redo, session isolation, memory accounting/eviction, full-document export and one-page previews with shapes/rotation. Desktop and phone browser checks cover Tab, Shift+Tab, navigation buttons, avoiding revisions for unchanged words, preserving rejected drafts, blocking download for an invalid draft, saving a valid draft on Download, and keeping the mobile property panel out of the way.

A deterministic 40-page PDF with 532 words on its first page and unique embedded images measured 11,175,471 bytes in full, versus 282,145 bytes for the current-page preview: **97.48% less preview data**. In the local Chromium test, upload-to-editable-and-rendered took approximately **1.44 seconds**, and saving-to-next-word-and-rendered took approximately **319 ms**. Only three thumbnails were requested initially, and returning to a visited page reused the text cache. These are local measurements, not promised Render/mobile/internet timings. Font complexity, device, network and free-host wakeups affect actual latency. Existing unsupported-font and scanned-text limits remain.

Reproduce after starting the local test server (set its PORT and the URL below consistently):

```bash
.venv/bin/python scripts/benchmark_editor.py
FOLIO_TEST_URL=http://127.0.0.1:3015 .venv/bin/python scripts/check_browser_fast.py tests/artifacts/browser/performance/large-40.pdf
```

The benchmark also reports median word-only versus combined legacy/word analysis timings for the current machine. It uses generated sample data only.

## Readable replacements, layers, brush and OCR

The reported short-name/long-message case is covered by `tests/test_readable_layers.py`: replace Kartik with Ashok plus a multi-word, multi-paragraph message, verify the original source text is absent, the font stays readable, the box wraps, nearby text is not covered and exported text survives independent Poppler reopening. A phrase that fits stays a direct operand edit. The current UI accepts spaces/newlines and never uses the legacy squeeze-to-fit option.

Added text, image and brush objects are saved as real vector/raster Form objects with private edit metadata. Tests cover text editing, movement, natural-size reflow on resize, expansion around following content, image resizing/removal (including unused image objects), transparent highlighter strokes, deletion, crop coordinate changes and removal of managed editing metadata during redaction. Existing-text source edits still survive compression and other operations. Managed text is edited as a layer rather than through individual glyph targets inside its Form.

Actual Tesseract jobs cover searchable and text-only editable reconstruction, progress, cancellation, missing languages, conflicting edits, unchanged source after cancellation, PDF download and independent extraction. Editable OCR copy words are then genuinely replaced. Its loss of original graphics/fonts/formatting is explicitly labelled.

`check_browser_layers.py` passes at desktop and phone touch sizes: long replacement including spaces/newlines, text-box addition, editing/moving/resizing, image upload/move/resize/delete/undo, brush drawing/delete/undo, download and reopening with layer selection retained. A browser also runs both real OCR modes, searches the searchable result, changes ASHOK to JOHN in the reconstructed copy, downloads and independently reopens it. No mocked engine responses are used. Previous word-only validation expectations were updated because spaces are now valid.

```bash
FOLIO_TEST_URL=http://127.0.0.1:3015 .venv/bin/python scripts/check_browser_layers.py
```

Screenshots and generated/downloaded PDFs remain under ignored `tests/artifacts/browser/`. This verifies generated fixtures; arbitrary original fonts, full paragraph reflow, editing scanned pixels and reconstructing arbitrary flattened artwork are not promised.

Text-box fonts are unmodified, explicitly licensed Unicode-capable assets in `backend/fonts/`; punctuation and canonical spaces are checked to prevent silent question-mark or nonbreaking-space substitutions during export.

## Current inline interaction

`tests/test_inline_blocks.py` adds six tests for source-font retention, same-frame wrapping/auto-fit, source-character removal, no-cover-rectangle preview masking, overflow/stale-input protection, original image occurrence deletion/movement, font/preview/auto-save API export/undo, and the optional private document. With the supplied document configured, the full suite passes 72 tests; without it, 71 pass and that one private-file check is skipped. The input PDF is not part of the repository.

`check_browser_inline.py` is the current browser regression; older runner names forward to it because their manual word-popup UI was deliberately replaced. It tests desktop/mobile direct typing, no underlines/Save popup, immediate download and page navigation waiting for saves, direct text addition, original image deletion, brush/shapes, and OCR-to-direct-edit/export. The optional PDF argument tests the provided nine-page document locally at both viewport sizes and verifies its edited download with Poppler and MuPDF. All images were preserved. A separate 144 dpi comparison found zero changed pixels outside the edited paragraph area.

```bash
FOLIO_SAMPLE_PDF=/path/to/private-sample.pdf .venv/bin/python -m pytest -q
FOLIO_TEST_URL=http://127.0.0.1:3015 .venv/bin/python scripts/check_browser_inline.py /path/to/private-sample.pdf
```

Source-font data is used only inside the user's edited PDF and the authenticated browser font response. No source font or input PDF is written into the public repository. Previous results above describe the earlier UI revisions; the inline runner is authoritative for the current UI.
