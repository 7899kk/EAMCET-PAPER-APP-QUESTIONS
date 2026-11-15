# Direct PDF editing

Release `inline-paragraphs-5`.

## Click text and type

Upload a PDF, choose **Edit text**, and click a supported paragraph. Type directly on the page. There are no persistent word underlines and no floating text-entry/Save dialog. Changes save automatically after a short typing pause. Download, changing pages and switching tools wait for pending text changes before continuing.

The paragraph stays in its original area. Words wrap inside that area, and the font size gently reduces when needed (down to 65% of the original size, with a 4 pt floor). Shortening the text can restore the original size. The original embedded TrueType/OpenType font, colour and line spacing are retained where supported. Standard fonts without embedded data use the bundled compatible free fonts. Very large additions that cannot fit produce an error and preserve the draft/source rather than covering adjacent content. Escape restores the last saved text; Ctrl/Cmd+Enter finishes editing. Enter inserts a paragraph line break.

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
