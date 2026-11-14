# Verification report

Actual checks performed in the supplied environment:

- **24 Python engine/API/static-serving tests passed**, using PyMuPDF 1.28.2, pikepdf 10.5.0 / qpdf 12.3.2. A second run from a clean virtual environment installed from the supplied requirements also passed.
- **Production React/Vite build passed.** PDF.js worker, fonts, character maps, and WASM are copied locally.
- **npm audit: zero known vulnerabilities** in the final resolved frontend dependency tree at the time checked. This is not a security guarantee.
- Downloaded API output reopened with MuPDF; text independently extracted with **Poppler `pdftotext`**. It contained the replacement and added text, omitted the replaced text, and retained two pages with the requested rotation.

## Required input categories

| Input | Actual verification |
|---|---|
| Selectable text | Actual Tj/TJ operands changed; original text absent; no covering drawings added |
| Scanned PDF | No selectable spans initially; Tesseract English OCR produced searchable recognized text |
| PDF with images | Raster image embedded; embedded-image export produced actual image bytes |
| Multiple pages | Merge, insert, reorder, duplicate, remove, rotate, split, extract, download/reopen |
| Different fonts and formatting | Helvetica, Times, Courier, bold, differing sizes; real replacement retained font; embedded DejaVuSans ToUnicode / Identity-H font also tested |

`tests/artifacts/` contains selectable, scanned/image, searchable, mixed-font, embedded-font, workflow, and downloaded-result PDFs. Tests generate/rewrite several artifacts. These are generated fixtures, not a claim of broad compatibility with arbitrary vendor PDFs.

## Workflow that passed

Upload real PDF → retrieve rendered text spans → replace an existing text operand → add new text → delete page → rotate another page → undo → redo → export PDF → independently reopen downloaded bytes → assert modified text, absent original text, page count, and rotation. This ran through the actual FastAPI endpoints, not mock processing responses.

The suite also exercises shape/line drawing, annotations, crop, stamps, page numbers, watermark, metadata, compression, supported find/replace, image insertion, image-to-PDF, text and PNG exports, passwords/decryption, redaction, upload validation, cross-origin write rejection, session deletion, and stripping active document actions.

## Verification limit

**Interactive browser testing and visual desktop/mobile inspection were not performed.** This managed environment did not expose the required browser-control tool; the [Sites skill](skill://plugin_connector_1p_689987207de08191979cf68eca2941c6/sites/SKILL.md) says: “If `cua_repl.js` is unavailable, skip browser QA: do not start a preview server, install a browser, or improvise another browser-control path.” That tool was unavailable. No screenshot, browser click-through, accessibility audit, or live public deployment is claimed. React compilation and backend tests do not establish that every UI gesture works correctly in every browser. Run the manual checklist below on your target browser before production use.

## Reproduce

Install `requirements-dev.txt`; ensure Tesseract English, Poppler `pdftotext`, and DejaVuSans are installed, then:

```bash
.venv/bin/python -m pytest -q
cd frontend && npm ci && npm run build
```

In this hosted execution environment the API TestClient's event-loop communication required running the tests outside the command sandbox. In a normal local terminal no sandbox escalation is needed. Two dependency deprecation warnings are emitted by the available test tools; tests pass.

## Manual browser checklist still to perform

1. Start the app and upload `tests/artifacts/selectable.pdf`.
2. Select “Original contract” with Edit text. Replace it and apply; check the render.
3. Add text by entering a line and clicking the page; verify placement.
4. Delete page 2, rotate the remaining second page, undo, redo.
5. Download, open in a separate PDF viewer, then re-upload the download.
6. Confirm page count, rotation, replacement text, added text, and absence of the old text.
7. Try the scanned, image, formatted, and embedded-font artifacts. Confirm read-only/OCR limitations are clear.
8. Test the same flow at a 390 px mobile viewport; open the page panel, zoom, scroll, and edit using the properties panel.
9. Test an unsupported font/glyph, wrong password, invalid upload, and a document too large to ensure errors are readable and prior work remains recoverable.
10. Review redacted output in an independent viewer, including text extraction; inspect compression size before/after. Do not treat a crop box as a redaction.

## Hosting preparation checks

After adding optional password protection and trusted hosted-origin handling, all **26 tests passed**. A Docker image containing both the built frontend and actual PDF backend was built successfully with Tesseract. The latest image refresh (hosting wording only) hit the environment disk limit; the task-specific build cache was removed to restore disk capacity. The normal public-host Dockerfile requires no session-specific CA: the cloud build used a temporary CA secret solely for this environment’s outbound HTTPS proxy. No hosting provider deployment or live public URL has been created; Render is awaiting an account connection.

The successfully built container also passed a live loopback smoke test: HTTP password protection, frontend delivery, Tesseract availability, source download, UID 10001 execution, upload, direct text replacement, new text insertion, deletion, rotation, export, and independent MuPDF/Poppler verification. The temporary test container was removed afterward.

## Browser upload regression fix

Reproduced an actual browser failure: when a page is opened using a URL containing HTTP login credentials, a relative `fetch('/api/documents')` is rejected before the server receives it. API requests now resolve against the clean origin and explicitly send same-origin credentials. A successful HTTP login also issues a one-hour signed, HTTP-only, SameSite=Strict cookie (Secure on the hosted HTTPS instance), so browser API calls work when Basic credentials are omitted. Wrong credentials, tampered/expired cookies, password changes, and cross-origin writes remain rejected.

File inputs now keep their selection until processing finishes, and uploads are snapshotted into readable file bytes before the request starts. This avoids depending on a mobile file-provider handle throughout the upload. Unreadable files and network/authentication failures have separate messages. POST requests are not automatically retried, preventing duplicate edits.

All **28 Python tests passed**, and the production React build passed. Chromium browser checks passed at desktop 1440×960 and mobile 390×844: credential-URL login/upload, cookie-only upload, selecting and replacing actual text, download, and independent MuPDF/Poppler reopen. Desktop also checked new text, deletion, and rotation through the UI. No JavaScript errors were recorded. These browser runs used the real local backend with the same password gate, not mocked PDF responses. Previous statements that browser testing was unavailable describe the original build; the installed Chromium runner was available for this later Render-debugging task.

Reproduce the optional browser regression with `pip install -r requirements-browser.txt`. Use an installed Chromium/Chrome, or run `python -m playwright install chromium`. Start a local server in one terminal:

```bash
FOLIO_PREVIEW_PASSWORD=browser-test-only .venv/bin/python -m uvicorn backend.app:app --host 127.0.0.1 --port 3013
```

Then run `.venv/bin/python scripts/check_browser_upload.py` in another terminal. It refuses non-loopback destinations and writes screenshots and downloaded test PDFs under `tests/artifacts/browser/`. Override the test URL/password using `FOLIO_TEST_URL` and `FOLIO_TEST_PASSWORD` only for your local test server.
