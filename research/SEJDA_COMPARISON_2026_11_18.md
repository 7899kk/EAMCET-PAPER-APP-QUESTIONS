# Same-PDF multi-edit comparison — 2026-11-18

A generated two-page PDF was uploaded to both Sejda's public PDF editor and the local Folio production build. Page 1 contained Helvetica paragraphs, nested Form text, an embedded subset font and an image. Page 2 was a raster scan with words and a separate coloured image. No user-provided document was uploaded to Sejda.

Four identical replacements were made consecutively in each editor:

| Original | Replacement |
|---|---|
| I'm feeling happy Today | I'm enthusiastic and happy Today |
| Ashok prepares the video. | Ashok prepares this type of video. |
| The meeting starts on Monday. | The meeting starts on Friday. |
| Please select this final sentence. | Please edit every word in this sentence. |

Before this fix, Folio failed to focus the second and fourth paragraphs: their editing fields closed before becoming ready. Sejda completed all four. After the fix, Folio completed the same four replacements on the same source PDF. Both downloads were reopened with MuPDF; all four replacement phrases were present and old phrases absent. Sejda's computed text size stayed 39.7815 px for the 18 pt line and 35.3613 px for the 16 pt lines at its zoom. Folio stayed 17.1 px and 15.2 px respectively at 95% zoom. Different zooms are not changes to PDF point size.

Neither editor's ordinary editing view exposed text-selection targets for `SCANNED INVOICE` on the raster page. This does not establish the capabilities of Sejda's separate OCR tools. The check did not use a paid OCR service.

Additional Folio regressions exercise six rapid consecutive edits (including nested content and subset-font new characters), double-click word selection, scanned-page OCR reconstruction, another edit to recognized text, full-document download and independent extraction. Desktop and mobile layouts are tested. The coloured artwork outside recognized scan text regions remains visible. Fonts keep their point sizes; fallback families are disclosed only when necessary.

The new OCR reconstruction is approximate: it replaces recognized raster text pixels using locally sampled paper colour and adds actual native text. It keeps raster artwork outside those regions, but does not retain original fonts, vector structure or texture within rebuilt text regions. It must not be described as lossless or as universal editing of every image/background/script.
