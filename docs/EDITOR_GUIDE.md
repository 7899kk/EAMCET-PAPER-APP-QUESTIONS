# Direct PDF editing

Release `fixed-size-flow-6`.

## Click text and type

Upload a PDF, choose **Edit text**, and click a supported paragraph. Type directly on the page. There are no persistent word underlines and no floating text-entry/Save dialog. Changes save automatically after a short typing pause. Download, changing pages and switching tools wait for pending text changes before continuing.

The original font size stays fixed while typing. On a supported single line, following words shift to the right into available space. At the available boundary, words wrap onto the next line. Multiline paragraphs keep their column width and reflow their following lines. The text area grows downward into free space; shortening the text can reduce its height again. No automatic font-size reduction or horizontal squeezing occurs.

The original embedded TrueType/OpenType font, colour, starting position and line spacing are retained where supported. Standard fonts without embedded data use bundled compatible free fonts. Page edges, detected neighbouring text, images, graphics and containing panels limit expansion. If there is no room, saving fails explicitly and preserves your draft and the previous PDF. Resize/move the saved layer, manually choose a smaller size under Layers, or shorten the text. Separate paragraphs/images are not automatically pushed onto another page. Escape restores the last saved text; Ctrl/Cmd+Enter finishes editing. Enter inserts a line break.

During editing, a temporary page preview removes the original paragraph's encoded characters so the live browser text does not overlap its old image. This is not a white rectangle or a raster replacement. On automatic save, the old characters are genuinely removed and a vector text object is written into the same frame. The document is still a real PDF and exported changes survive reopening.

**Add text** also works directly: choose the tool, click a blank area, and type. It saves automatically. Use **Layers** for advanced font/colour changes, movement, resizing or deletion of saved text objects. Imported paragraphs keep their embedded font available in the layer controls.

## Images and other content

PDF.js displays the original embedded images. **Layers** also detects directly embedded, supported raster-image occurrences in an uploaded PDF. Delete removes only the selected occurrence, even if the same image is used elsewhere. Moving/resizing an original image converts it into a managed rectangular image layer; original clipping effects are not retained, and this is disclosed. Added images and saved text/brush objects remain movable, resizable and deletable after downloading/reuploading.

Text baked into an image is not native editable text. Use OCR to make scans searchable or create an explicitly lossy editable text copy. Image rendering/detection is not a claim to duplicate ChatGPT's image-understanding capabilities.

**Highlight** remains a transparent freehand brush with size/colour/opacity controls. **Shapes** has separate rectangle, ellipse, line and arrow controls. Comments, page operations and other processing tools remain available.

## Limits

Shadowed/overlapping decorative text, Type 3 or outlined fonts, non-web-compatible embedded fonts, complex scripts, text inside reused external objects and unsupported transformations may be read-only. This is intentional: the editor does not pretend to change one visible copy while leaving another behind. Full document-wide paragraph reflow, arbitrary flattened artwork reconstruction and certificate signing are not implemented. Rotate to 0° before native/layer edits.

OCR is local, shows progress and supports cancellation. Searchable output preserves scan appearance; editable-copy mode reconstructs recognized Western Latin text and loses original images/fonts/exact formatting. Recognition errors still need review. Only installed languages are offered.

## Verification with the provided document

The supplied nine-page guide was tested locally. A phrase on page 2 was changed from “the whole video” to “this type of video.” It stayed in the same paragraph area, kept the Hind font and original colour/size, preserved all embedded images and passed independent PDF text extraction. A pixel comparison found no changes outside that paragraph area. The file and extracted fonts were not committed to source control or uploaded to a third-party editor.

See [testing](TESTING.md) and [API](API.md).

## Sejda comparison

A generated sample was edited and downloaded from Sejda on 2026-11-17. Replacing `feeling` with `Enthusiam` retained its 18 pt size and moved following words right. In this example Sejda did not wrap an excessively long single-line replacement; its export extended beyond the page. Folio keeps the fixed-size behavior and adds safe wrapping instead of off-page clipping. See [comparison observations](../research/SEJDA_REFLOW_CHECK.md).
