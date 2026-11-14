# Verification report

Release `word-shapes-2`, checked on 2026-11-14.

## Results

- **52 Python tests passed** against the real PDF engine and FastAPI API. The production React/Vite build passed.
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
