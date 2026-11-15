# Readable text, layers, brush highlights and OCR

Release `readable-layers-4`.

## Replace a short name with a longer message

1. Open a PDF or choose **Try sample PDF**.
2. Choose **Edit existing text** and click an underlined word.
3. Type a word, a phrase with spaces, or paragraphs. **Shift+Enter** inserts a line; Enter or Save applies it.
4. Short replacements that fit modify the original PDF text operands directly. Longer replacements remove the original encoded characters and create a vector text box at the chosen font size. Letters are not condensed into the old word width.
5. The box expands/wraps into available space. If it would cover existing content, the editor places it in a free area and explains that placement. It does not automatically push the surrounding paragraphs down. If the page has no room, the operation fails with the original text preserved.
6. The new text box is selected under **Layers**. Drag it to move, drag the corner to resize, or edit its text, font, size and colour, then **Apply layer changes**. Narrowing the box reflows text instead of stretching glyphs. When text is expanded, the editor avoids covering following content where room is available.
7. Download PDF includes saved changes and also saves the currently edited text/layer draft.

Short replacements retain the original font where supported. Text boxes use compatible standard fonts; a fallback to Helvetica is disclosed if the source font cannot be reused. Complex-script insertion, arbitrary embedded-font changes and automatic document-wide paragraph reflow are not implemented. Text boxes accept up to 4000 characters and must fit on a page. Rotate pages to 0° before editing native text or layers.

## Add text, images and highlight strokes

- **Add text:** click the page, type into the on-page text box composer, then choose **Add text box**. Spaces and new lines work. The result is a real PDF text layer you can move, resize, edit and delete.
- **Image / Signature:** choose an image. It is inserted and selected as a layer. Drag to move, drag its corner to resize while keeping the aspect ratio, or **Delete layer**. Transparent image backgrounds are retained.
- **Highlight:** choose brush size, colour and opacity. Drag a mouse or finger over the page to paint. Each stroke is a transparent vector layer. Use **Layers** to move, resize, recolour or delete it.
- **Layers:** select a layer directly on the page or in the selector. These are objects added/converted by this application. Their edit data is saved inside the PDF and survives downloading/reuploading. Arbitrary pre-existing flattened artwork/images are not automatically reconstructed as editable layers.
- **Shapes:** rectangle, ellipse, line and arrow use the separate Shapes → Select shapes controls.

Undo/redo restores real PDF versions. Deletion removes the object drawing and resource from the current exported PDF, rather than hiding it. The in-memory undo history retains earlier versions until the document is closed or expires.

## OCR

Choose **OCR**, an installed language and current/all pages. Progress is shown and **Cancel OCR** preserves the previous PDF. OCR runs locally on this server; documents are not sent to another service.

- **Searchable PDF:** preserves scanned appearance and adds recognized search text. Already searchable pages retain their vector quality. Scanned pixels are still not directly editable. Use Search to find the recognized words.
- **Editable text copy:** reconstructs recognized words into a new text-based PDF. This copy can be edited, but it loses original images, graphics, fonts and exact formatting. Review recognition/layout errors. Undo restores the source. Currently supports Western Latin reconstruction; searchable output can use installed OCR languages.

A blank/unclear image can produce no recognized text; the editor reports that failure and keeps the original. Recognition depends on resolution, orientation and language. OCR is limited to one job at a time on this free server to control memory, with a per-page timeout. Changes are blocked while OCR runs; cancel or wait before editing.

## Verification

Generated name-replacement, multi-paragraph, image and scan documents were processed through the real backend and desktop/mobile browser UI. Exports were reopened with MuPDF and independent Poppler tools. See [testing](TESTING.md) and [API](API.md).

Earlier comparison: on 2026-11-14 a generated sample was actually uploaded to Sejda, edited from brown to red, downloaded and independently reopened. No user files or proprietary editor code were used. Folio does not claim full Sejda compatibility or its proprietary paragraph-layout features.
