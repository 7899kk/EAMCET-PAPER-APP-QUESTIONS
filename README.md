# Folio PDF editor

A local React + PDF.js workspace backed by real FastAPI, pikepdf/qpdf, PyMuPDF/MuPDF, and optional Tesseract processing. No paid API, subscription, external document service, or fake processing.

**This is a working editor with documented limits, not a complete Sejda replacement.** Short edits change actual PDF text operands. Inline edits remove the original paragraph characters and write readable vector text into the same area, with fixed-size wrapping. No whiteout hides the old text. See the [current editor guide](docs/EDITOR_GUIDE.md).

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

1. Upload a PDF or choose **Try sample PDF**.
2. Select **Edit text**, click a supported paragraph and type directly on the PDF. No word underlines or floating Save dialog are shown.
3. Text wraps and grows into available space at the same font size; a usable embedded font, colour and line spacing are preserved. Changes save after a short pause.
4. **Download PDF** waits for pending text edits. Reopen the download to check the result.
5. **Add text** lets you click a blank area and type directly. **Layers** provides advanced move/resize/font/delete controls for saved text and images.
6. **Layers** can also select supported original embedded-image occurrences. Deletion affects that occurrence only; moving an original image converts it to a rectangular managed layer, with clipping limitations disclosed.
7. Undo/redo keeps up to 12 actual PDF versions. Download before closing/restarting the server.

See [the current guide](docs/EDITOR_GUIDE.md) for text-flow limits, font support, images and OCR. On phones use zoom/Fit width and the page-panel toggle. Native OS keyboards and every browser/font combination are not exhaustively tested.

## Implemented

- Fast current-page PDF previews, word-only detection, a bounded current-revision text cache, next-page text prefetch and thumbnails loaded as they become visible. Downloads retain all document pages. See [performance checks](docs/TESTING.md#fast-word-editing).

- Real upload, PDF.js rendering, thumbnails, zoom, text search, actual PDF download, undo/redo, loading/error feedback.
- Direct existing word replacement using glyph positions and encoded PDF operands (Tj/TJ and supported quote operators); supports simple standard fonts and compatible single-width ToUnicode / Identity-H fonts. Existing font size and fill colour can change.
- Editable wrapped text boxes, image/signature-image layers, a freehand highlighter brush with size/colour/opacity, layer selection/movement/resizing/deletion, comments, stamps, page numbers and watermarks. Layer metadata survives download/reupload.
- A **Shapes** picker with rectangle, ellipse, line and arrow. Added shapes are real PDF annotations: select, drag to move, resize from the corner, change border/fill/width, delete, undo/redo, download and reselect after reopening. Supported imported shape annotations work too; flattened page artwork is not selectable.
- Merge, insert another PDF, delete, rotate, reorder with up/down controls, duplicate, split each selected page to ZIP, extract selected pages to PDF.
- PDF → PNG ZIP; PNG/JPEG/WebP → PDF; PDF → plain text; embedded raster-image extraction.
- Tesseract OCR with installed language packs, progress/cancellation and searchable or editable text-copy output; metadata editing; PDF stream compression; AES-256 protection; opening/decrypting with the known password; permanent area redaction; crop.
- Find and replace within supported editable text runs. It skips unsupported spans; font encoding failures roll back the entire operation.

## Limitations — read before relying on output

- PDF is not a word processor format. Existing words are matched by their encoded characters and positions. Repeated words/lines and supported words split across multiple PDF text instructions are editable. Rotated or outlined text, text in Form XObjects, overlapping glyphs, mixed styles inside one word, vertical writing, complex scripts/encoding, and unsupported font metrics can remain read-only. The current UI retains the original paragraph area and embedded font, wrapping at the same font size and growing downward into available space. It cannot push surrounding paragraphs down. Unsupported glyphs and structures remain explicit. Legacy API fit behaviour remains for compatibility only. A word edit preserves the original byte strings and TJ kerning outside the selected range. The replacement uses standard glyph advances, and following text keeps its position.
- Scanned PDFs have no text to select. Searchable OCR retains the scan with recognized search text. The separate editable text-copy mode reconstructs recognized words into native PDF text, losing original graphics/fonts/exact formatting. It is an explicitly lossy reconstruction, not editing of scanned pixels. OCR has progress/cancellation and can make recognition errors.
- Supported direct embedded raster images can be selected, deleted, moved or resized. Moving an original image converts it to a rectangular layer and loses original clipping effects. Nested images and arbitrary existing objects are not all editable. Added images, text boxes and brush highlights have movable/resizable/deletable layers. Arbitrary pre-existing flattened content is not reconstructed as editable objects. Highlights are freehand transparent strokes, not semantic text-range selections. Stamps are text. Signature images are not cryptographic signatures.
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
