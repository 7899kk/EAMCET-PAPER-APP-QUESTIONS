# Folio PDF editor

A local React + PDF.js workspace backed by real FastAPI, pikepdf/qpdf, PyMuPDF/MuPDF, and optional Tesseract processing. No paid API, subscription, external document service, or fake processing.

**This is a working editor with documented limits, not a complete Sejda replacement.** Existing-text edits modify actual PDF text operands. They do not cover the old text or add a replacement overlay.

## Start locally for ₹0

Requires Python 3.12+, Node 22+, npm, and an ordinary computer. On Debian/Ubuntu, install `python3-venv`, `tesseract-ocr`, and optionally `poppler-utils` for independent verification. Other platforms can install Tesseract separately and put it on PATH. OCR is unavailable without Tesseract; other tools still work.

```bash
cd /workspace/pdf-studio  # or the extracted project directory
./start.sh
```

Open **http://127.0.0.1:8000**. The first run downloads free dependencies; later runs reuse installed packages. Run one backend worker because sessions are held in that process's memory. No Docker required. The Python package wheels contain qpdf and MuPDF; no Java or Stirling service is needed.

Manual setup, including Windows:

```bash
python3 -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
cd frontend
npm ci
npm run build
cd ..
python -m uvicorn backend.app:app --host 127.0.0.1 --port 8000 --workers 1
```

For development, run the backend above and `cd frontend && npm run dev` in a second terminal. Vite proxies `/api` to port 8000. Use the Vite URL printed in the terminal. Vite and the backend listen on loopback by default.

## Primary workflow

1. Upload a selectable PDF (or use `tests/artifacts/selectable.pdf`).
2. Choose **Edit text**, hover a line, and select a supported text run. Green outlines indicate editable text; unsupported text has grey outlines.
3. Edit its text in the right panel and apply. Size and colour are supported; the original font is retained.
4. Choose **Add text**, enter text, and click the page to place it. This is explicitly new content.
5. Delete a page from its thumbnail and rotate another page.
6. Each operation immediately saves an actual PDF revision in server memory. Undo and redo retain up to 12 versions.
7. Click **Download PDF**, then reopen the downloaded file. Save the download before closing or restarting the server.

On phones, open thumbnails with the menu button. Properties appear when a tool or text is selected. The PDF canvas scrolls in both directions; use zoom or Fit width for smaller screens.

## Implemented

- Real upload, PDF.js rendering, thumbnails, zoom, text search, actual PDF download, undo/redo, loading/error feedback.
- Direct existing text operand replacement for supported horizontal, uniquely matched Tj/TJ text; supports simple standard fonts and compatible single-width ToUnicode / Identity-H fonts. Existing font size and fill colour can change.
- New text with four standard font choices; raster images / signature images; rectangular outlines, lines, rectangular highlights, comments, text stamps, page numbers, translucent text watermarks.
- Merge, insert another PDF, delete, rotate, reorder with up/down controls, duplicate, split each selected page to ZIP, extract selected pages to PDF.
- PDF → PNG ZIP; PNG/JPEG/WebP → PDF; PDF → plain text; embedded raster-image extraction.
- Tesseract OCR with installed language packs; metadata editing; PDF stream compression; AES-256 protection; opening/decrypting with the known password; permanent area redaction; crop.
- Find and replace within supported editable text runs. It skips unsupported spans; font encoding failures roll back the entire operation.

## Limitations — read before relying on output

- PDF is not a word processor format. Existing text must match one unique horizontal rendered span and one supported text-showing instruction. Repeated identical text, character fragments, rotated text, outlined text, text in Form XObjects, vertical writing, complex encoding, and unsupported font metrics are read-only. No automatic paragraph reflow, font-family replacement, or arbitrary glyph insertion. Longer replacement text can overlap nearby content; inspect the result. Original TJ internal kerning is replaced with standard glyph advances while the following text position is retained.
- Scanned PDFs have no text to select. OCR creates a searchable image-based PDF; it does **not** reconstruct directly editable paragraphs. OCR flattens vector content/annotations and can make recognition errors. This editor does not offer true editing of scanned text.
- Moving/resizing/removing existing images or arbitrary existing objects is not implemented. New images are placed in a default rectangle; arbitrary drag/resize is not implemented. Highlights are rectangular annotations, not semantic text-range highlights. Stamps are text. Signature images are not cryptographic signatures.
- Word/Excel export, table reconstruction, digital signature validation/signing, form filling, accessibility-tag preservation, complex-script new text, and editing password-restricted documents without the known password are unsupported.
- New text supports Western Latin only. Most new content tools require page rotation 0°. Compression rewrites/deflates streams and drops unused objects; it does not aggressively downsample images and may increase size.
- Upload sanitization removes forms, active actions, embedded attachments, and portfolios; it can change or flatten no form content, so don't use this tool to preserve interactive forms. Edits invalidate existing cryptographic signatures. Bookmarks and advanced document structures may change during page organization.
- Redaction removes selected text, intersecting vector graphics, and selected image pixels from the current rewritten PDF. Undo history keeps prior versions until you close the session. Redaction is not a full document sanitization/audit: metadata and information outside the region can remain. Crop hides content outside a crop box; **crop is not redaction**.
- Maximum upload 25 MB, 300 pages, page dimensions 10–2000 pt, processed result 50 MB, all documents/history 200 MB per server. Export at most 50 PNGs per request. Large OCR jobs may take minutes. Sessions expire after one idle hour.

## Architecture, privacy, licences

The frontend sends actual operation requests to Python; it does not simulate processing. The backend returns real rewritten PDF bytes. PDFs/history live in server memory; OCR temporary files are deleted using `TemporaryDirectory`. Close & remove deletes the session immediately; background cleanup runs every minute. Restart clears all sessions. No persistent document database or external PDF service is used. OS/process memory and swap are outside app control.

See [licence audit](docs/LICENSES.md), [API](docs/API.md), [test report](docs/TESTING.md), and [deployment](docs/DEPLOYMENT.md). The app is offered under AGPL-3.0-or-later to accommodate the AGPL PDF engine. Keep third-party notices. A network deployment needs to offer corresponding source to its users.

## Test

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest -q
cd frontend && npm run build
```

Full tests need Tesseract English, `pdftotext` (Poppler), and DejaVuSans at `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`. Generated PDFs and the independently reopened download are in `tests/artifacts/`. These tests are an engineering regression suite, not a guarantee of compatibility with all PDFs.
