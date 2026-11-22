# API

Base URL: `http://127.0.0.1:8000/api`. Machine-readable schema: `GET /openapi.json`. No service key. Upload returns a random session token; subsequent calls must send `X-Session: <token>`. Treat it as a bearer secret. Never place it in a URL or logs. Responses are `Cache-Control: no-store`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Engine health, installed OCR languages, upload/page limits |
| GET | `/sample.pdf` | Generated editable sample PDF; uses the normal upload workflow |
| POST | `/documents` | Multipart `file` PDF, optional `password`; returns token and document info |
| POST | `/documents/blank` | Creates a real blank A4 PDF session; authentication required when enabled |
| POST | `/images-to-pdf` | Multipart repeated `files`; returns a new document token |
| GET | `/document` | Page dimensions/rotation, metadata, bytes, undo/redo availability |
| GET | `/document/pdf` | Current actual PDF bytes |
| GET | `/document/page/{page}/pdf` | Lightweight one-page preview; full exports still contain the whole edited document |
| GET | `/document/page/{zero-based-page}/text` | Rendered spans plus word targets with bounding boxes, string IDs, source parts and `editable` flags / reasons |
| GET | `/document/page/{page}/thumbnail` | PNG thumbnail |
| GET | `/document/page/{page}/shapes` | Supported Square/Circle/Line annotations with IDs, geometry, style and editability |
| GET | `/document/page/{page}/layers` | Persisted editable text/image/brush Form objects, IDs, geometry and style |
| POST | `/document/ocr` | Start cancellable local OCR: `{ "args": {"languages":"eng", "mode":"searchable", "scope":"all", "page":0} }` |
| GET | `/document/ocr` | Job state/progress; complete jobs include summary and new document info |
| DELETE | `/document/ocr` | Request cancellation; original PDF remains unchanged unless the job already completed |
| POST | `/document/operation` | JSON `{ "operation": "...", "args": {...} }`; commits an actual PDF version |
| POST | `/document/file-operation` | Multipart `operation`, `args` JSON, and `file`; merge/insert/image |
| POST | `/document/history/undo` | Restore earlier PDF bytes |
| POST | `/document/history/redo` | Restore later PDF bytes |
| POST | `/document/export` | JSON `{ "kind": "pdf", "args": {} }`; downloadable binary/text response |
| GET | `/document/search?q=...` | Matching pages and rectangles |
| DELETE | `/document` | Remove session/history from memory |

Every page index is **zero-based**. Coordinates are PDF points (72 pt = one inch) measured from the rendered page's top-left. New content generally requires rotation 0°. Each operation is atomic: failures preserve the preceding PDF version. Up to 12 versions are retained. Document info responses include `undo` and `redo` flags.

The text endpoint accepts `?words_only=true` to skip legacy span detection. Current-revision word detection is cached per session (at most four pages / 4 MB of estimated analysis memory, counted in the global memory budget). Successful edits and undo/redo invalidate it; close and expiry discard it. A word edit validates against these server-produced targets under the same session lock. No client-supplied cache can bypass validation.

## JSON operations

| Operation | Args |
|---|---|
| `replace-readable` | `page`, current word `id`, expected `original`, `text` up to 4000 characters including spaces/newlines, optional `size`, `color`. Direct natural-width replacement if safe; otherwise remove original and create a readable wrapped text layer in free space. No horizontal condensation. |
| `layer-update` | `page`, `id`, optional `rect`, `text`, standard `font`, `size`, `color`, brush `width` / `opacity`; text reflows rather than stretching |
| `layer-delete` | `page`, `id`; remove drawing instruction and resource, including editing metadata |
| `brush` | `page`, `points: [[x,y], ...]` (2–2000 points), `width` 0.5–60 pt, `opacity` 0.05–0.8, `color`; transparent vector highlight layer |
| `replace-word` | `page`, string `id` from the latest `words` array, `original` selected word, replacement `text`, optional `size`, `color`, `fit` (default true) |
| `shape-add` | `page`, `type` (`rectangle`, `ellipse`, `line`, `arrow`), `rect`, optional `points` for directed lines, `color`, `fill` hex or null, `width` 0.5–12 pt |
| `shape-update` | `page`, latest shape `id`, and full geometry/type/style fields from `shape-add` |
| `shape-delete` | `page`, shape `id` |
| `replace` | `page`, text run `id` from the latest text endpoint, `text`, optional `size`, `color` |
| `find-replace` | `find`, `replacement`; supported spans only across all pages |
| `text`, `stamp` | `page`, `text` including spaces/newlines, `x`, `y` (box top-left), optional `width` or `rect`, `size` 4–144, `color`, standard `font`; returns a wrapped editable vector layer |
| `pages` | `indices`: desired page order; repeat indices to duplicate, omit to delete |
| `rotate` | `page`, `angle` (default 90) |
| `rectangle`, `line`, `highlight`, `redact`, `crop` | `page`, `rect: [x0,y0,x1,y1]`; optional `color` for non-redaction tools |
| `comment` | `page`, `x`, `y`, `text` |
| `numbers` | optional `color`; every page |
| `watermark` | `text`, `size`, `color`; every page |
| `metadata` | `metadata: {title,author,subject,keywords,creator,producer}` |
| `compress` | none; rewrite with garbage collection and deflated streams |
| `ocr` | `languages: "eng"`, or installed Tesseract codes joined by `+` |

Word IDs identify source instruction/character ranges; IDs and the expected `original` word must come from the latest response. Word edits replace that occurrence only, preserve adjacent operands/kerning and positions, and support repeated words and compatible words split across instructions. A blank replacement removes the word while keeping its layout space. Fit condenses a longer replacement to the original word width. No paragraph reflow is performed.

That optional fit behaviour belongs to the legacy `replace-word` endpoint. The legacy word UI used `replace-readable`: natural-size words/phrases when they fit, otherwise a wrapped text layer. Existing encoded source characters are removed, not covered. Font fallback and placement in free space are reported. Full paragraph reflow is unsupported. If there is no space on the page, replacement fails atomically. Responses that create/select a managed object include `active_layer`, and may include a `notice`. This metadata is persisted in the object's Form XObject, not a separate permanent server database.

Image file operations also create managed layers. Use `layer-update` to move/resize and `layer-delete` to remove them. Cropping is reflected in layer coordinates. Redaction removes intersected managed layers completely, including their private text editing metadata, before redacting the original page content; this can remove more than the exact rectangle. Undo retains prior versions until close/expiry.

OCR mode `searchable` preserves scan appearance and search text; already searchable pages retain vector quality. Mode `layout` reconstructs recognized text as editable native lines and retains rendered raster artwork outside erased recognized-word regions. Paper colour is sampled locally; original fonts, vector structure and textured/photo backgrounds in reconstructed areas may change. It is explicitly lossy. Mode `editable` reconstructs recognized Western Latin text into a text-only PDF and loses original images/graphics/fonts/exact formatting. Scope is `all` or `current`. Poll until `complete`, `cancelled` or `failed`; failed/cancelled jobs preserve the previous version. One OCR job runs per server, with a 90-second per-page deadline. Edits/history are rejected with 409 while the session job runs. OCR progress, cancellation and output do not require a paid service. Only installed languages are accepted. The legacy synchronous `ocr` operation remains compatible but the browser uses the job API.

Legacy text run IDs depend on current content-stream instruction offsets. Fetch them again after every operation/undo/redo. Replacement glyphs must exist in the font. Repeated/ambiguous spans are read-only. No overlay fallback is performed.

File operations: `merge` appends all pages; `insert` accepts `at` (0-based insertion position); both accept known `password` if the attached PDF requires it. `image` accepts `page` and `rect` and re-encodes supported PNG/JPEG/WebP images into PNG before embedding. Original image proportion is retained.

## Exports

- `pdf`: current bytes, all pages.
- `text`: UTF-8 plain text.
- `images`: ZIP of rendered PNG pages, maximum 50 selected pages.
- `extract-images`: ZIP of unique embedded raster images. Vector illustrations and inline-image extraction are not supported.
- `split`: ZIP with one PDF per selected page.
- `extract`: one PDF containing selected pages in the requested order.
- `protect`: AES-256 PDF; `args.password` must have at least six characters. This encrypts the **downloaded copy**, not the in-memory working session.

For selected-page exports, supply `args.indices`. It defaults to all pages. An unsupported export kind returns 422.

## Example

```bash
curl -F file=@document.pdf http://127.0.0.1:8000/api/documents
# Use the returned token without committing it to source control.
curl -H 'X-Session: TOKEN' http://127.0.0.1:8000/api/document/page/0/text
curl -H 'X-Session: TOKEN' -H 'Content-Type: application/json' \
  -d '{"operation":"replace","args":{"page":0,"id":4,"text":"Updated contract"}}' \
  http://127.0.0.1:8000/api/document/operation
curl -H 'X-Session: TOKEN' -H 'Content-Type: application/json' \
  -d '{"kind":"pdf"}' http://127.0.0.1:8000/api/document/export -o edited.pdf
```

Error JSON uses `detail`. Common codes: 422 invalid/unsupported operation or file/password; 404 expired/missing session; 413 oversized upload; 403 cross-origin write; 503 exhausted global memory. Request model errors use FastAPI's standard detail array. No permissive cross-origin API access is enabled. The local app does not authenticate users beyond possession of a session token.

## Inline paragraph editor (current UI)

- `GET /document/page/{page}/blocks`: current paragraph targets, source font/style, area, editability and reason.
- `GET /document/page/{page}/font?block=ID`: authenticated original embedded font bytes for in-page typing. `block=new` uses the bundled free Sans font. No document font is published as a site asset.
- `GET /document/page/{page}/pdf?exclude_block=ID`: temporary preview without the selected source paragraph, for live DOM typing without doubled glyphs. Does not commit changes.
- `POST /document/inline-edit`: `{ "operation":"replace-block", "args":{"page":0,"id":"ID","original":"current text","text":"replacement"} }`. Validates the current source under the session lock, removes original source characters and inserts vector text with the original embedded font in the same frame. Returns document info and `inline_block`. New text uses `id:"new"` and a `rect`.

Text keeps its font size and wraps within the server-computed `flow_rect`. Single lines can widen into available horizontal space; multiline paragraphs keep their width. Saved layers grow vertically as needed and can shorten again. Overflow and stale-source errors leave the saved PDF unchanged. Legacy auto-fit layers restore their saved original maximum size on direct edit. Font size changes require an explicit Layers operation. Font/structure limitations are returned explicitly. Autosave is a frontend behavior; this endpoint commits actual PDF bytes. Full-page reflow is unsupported.

Layers also return supported direct native raster image occurrences with `image:` IDs. `layer-delete` removes that occurrence. `layer-update` moves/resizes it by converting to a managed rectangular layer; original clipping is not preserved. Other uses of the same image resource remain unchanged.

### Broader native text support

The blocks response includes `font_notice`, `font_key`, and `ocr_recommended`. Direct source operands remain the preferred removal method. Other horizontal native text, including nested Form content, uses text-only glyph-region removal with image/graphics removal disabled and no cover fill. Hidden OCR search text is not represented as visible native editing. Font tables are repacked for browser compatibility; new characters absent from a subset font can trigger a compatible full font at the same point size. The notice is returned and saved with the text layer. The font endpoint accepts `compatible=true` for a browser font-decoding fallback; inline edits send `font_fallback:true` when this path is needed.

### Prepared display resources

`GET /document/page/{page}/edit-patch?block=ID` returns a PNG of the selected text area's real background with original text removed. `X-Patch-Rect` contains its page-point rectangle. No PDF commit or history change occurs; the image is bounded to four million pixels. The frontend prepares these patches and font faces up front, reuses them across paragraph selections, and invalidates them for unrelated document operations/history. Browser preview cache is bounded to 96 entries / 16 MB; prepared font faces to 32 entries / 24 MB except an actively used face. Caches are per-document and cleared on close/replacement.

## Accounts and continuous pages

- `GET /api/auth/status`: public authentication mode, public Supabase configuration when enabled, and current user status. Never returns a secret/service-role key.
- `POST /api/auth/login`: private workspace `{username,password,remember}`. Sets a signed HTTP-only SameSite=Strict cookie, for 30 days when remembered. Incorrect credentials are rejected and repeated failed attempts are limited.
- `POST /api/auth/logout`: clears the private session and prevents cached browser Basic credentials from signing straight back in.
- Supabase signup/sign-in/refresh use the official browser SDK. API requests send its access token as Bearer. The server verifies it against the configured project's user endpoint, caches verified identities briefly without retaining raw tokens, and binds document sessions to the verified user. Another user cannot read, edit, export or delete those documents even with their session token.
- `GET /document/page/{page}/view`: bounded lazy PNG page preview for the continuous reader; it does not alter the PDF.

`/signin` and `/signup` serve the app's account UI. The latter offers actual public registration only when Supabase is configured. Local mode without authentication variables remains usable for free on a developer's own machine.

New inline text accepts a validated `font` code from the bundled 12 font/style choices. `GET /document/page/{page}/font?block=new&font=tiro` returns the matching browser font. Existing text editing keeps its original font handling.
