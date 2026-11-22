# Direct PDF editing

Release `text-boxes-11` — Edit karo.

## Click text and type

Upload a PDF, choose **Edit text**, and click a supported paragraph. Type directly on the page. There are no persistent word underlines and no floating text-entry/Save dialog. Changes save automatically after a short typing pause. Download, changing pages and switching tools wait for pending text changes before continuing.

The original font size stays fixed while typing. On a supported single line, following words shift to the right into available space. At the available boundary, words wrap onto the next line. Multiline paragraphs keep their column width and reflow their following lines. The text area grows downward into free space; shortening the text can reduce its height again. No automatic font-size reduction or horizontal squeezing occurs.

The original embedded TrueType/OpenType font, colour, starting position and line spacing are retained where supported. Standard fonts without embedded data use bundled compatible free fonts. Page edges, detected neighbouring text, images, graphics and containing panels limit expansion. If there is no room, saving fails explicitly and preserves your draft and the previous PDF. Resize/move the saved layer, manually choose a smaller size under Layers, or shorten the text. Separate paragraphs/images are not automatically pushed onto another page. Escape restores the last saved text; Ctrl/Cmd+Enter finishes editing. Enter inserts a line break.

Reading and editing become available once the current page is rendered and its text is detected. Font faces and small text-free background patches warm up progressively in the background. Selecting a prepared paragraph reuses those resources instead of fetching and rendering the whole page again. Preparation is cached per document. It no longer blocks the first page until every preview has been prepared; longer or more complex pages can still take more time. Fonts and preview resources stay only in bounded per-document browser memory and are cleared when the document is closed or replaced.

Background patches retain the original page's images, colours and graphics with just the selected source characters removed. They are temporary display resources, not white rectangles or substitutes for PDF processing. Autosave commits real vector text into the actual PDF without reloading the canvas or regenerating the background while you type. Finishing editing refreshes the rendered page. Speculative preview preparation is limited to eight paragraphs so it competes less with active saves.

**Download PDF** first saves pending text. If automatic downloading is blocked, use the persistent **Save file** link or **Open file** to open the prepared download. Links remain valid until dismissed, replaced, or invalidated by a new edit/document. Failed exports show an error and permit retry; they do not claim that a file was saved to your device.

**Add text** also works directly: choose the tool, click a blank area, and type. An empty typing area shows “Type here…” and saves automatically. New text starts with a single-line minimum height and grows only as needed. Use **Layers** for advanced font/colour changes, movement, resizing or deletion of saved text objects. Imported paragraphs keep their embedded font available in the layer controls.

## Images and other content

PDF.js displays the original embedded images. **Layers** also detects directly embedded, supported raster-image occurrences in an uploaded PDF. Delete removes only the selected occurrence, even if the same image is used elsewhere. Moving/resizing an original image converts it into a managed rectangular image layer; original clipping effects are not retained, and this is disclosed. Added images and saved text/brush objects remain movable, resizable and deletable after downloading/reuploading.

Text baked into an image is not native editable text. Use OCR to make scans searchable or create an explicitly lossy editable text copy. Image rendering/detection is not a claim to duplicate ChatGPT's image-understanding capabilities.

**Highlight** remains a transparent freehand brush with size/colour/opacity controls. **Shapes** has separate rectangle, ellipse, line and arrow controls. Comments, page operations and other processing tools remain available.

## Limits

Horizontal native text inside nested objects and many decorative/Type 3 fonts can now be rebuilt. Original fonts are retained when compatible; font-decoding or missing-glyph problems use a disclosed compatible font at the same point size. Outlined artwork with no characters, complex scripts and unsupported transformations still need reconstruction or remain unsupported. This is intentional: the editor does not pretend to change one visible copy while leaving another behind. Full document-wide paragraph reflow, arbitrary flattened artwork reconstruction and certificate signing are not implemented. Rotate to 0° before native/layer edits.

OCR is local, shows progress and supports cancellation. Searchable output preserves scan appearance; editable-copy mode reconstructs recognized Western Latin text and loses original images/fonts/exact formatting. Recognition errors still need review. Only installed languages are offered.

## Verification with the provided document

The supplied nine-page guide was tested locally. A phrase on page 2 was changed from “the whole video” to “this type of video.” It stayed in the same paragraph area, kept the Hind font and original colour/size, preserved all embedded images and passed independent PDF text extraction. A pixel comparison found no changes outside that paragraph area. The file and extracted fonts were not committed to source control or uploaded to a third-party editor.

See [testing](TESTING.md) and [API](API.md).

## Sejda comparison

A generated sample was edited and downloaded from Sejda on 2026-11-17. Replacing `feeling` with `Enthusiam` retained its 18 pt size and moved following words right. In this example Sejda did not wrap an excessively long single-line replacement; its export extended beyond the page. Folio keeps the fixed-size behavior and adds safe wrapping instead of off-page clipping. See [comparison observations](../research/SEJDA_REFLOW_CHECK.md).

## Scanned words and repeated edits

Click **Make scanned text editable** on a scanned page, review the reconstruction notice, and start local OCR. The editable scan mode keeps raster artwork outside recognized text regions, replaces original recognized text pixels with sampled paper colour and inserts real editable text. Original fonts and textured/photo backgrounds are approximate. This differs from searchable OCR, which leaves scanned pixels unchanged, and the older text-only reconstruction, which discards artwork. Undo restores the original.

Clicking another paragraph now waits for its predecessor's pending save, resolves current source IDs and preserves focus. Double-click selects a word; drag selects a range. See the [same-PDF Sejda comparison](../research/SEJDA_COMPARISON_2026_11_18.md).

## Natural wrapping and continuous pages

Text fields have no internal vertical scrollbar. Longer text wraps and expands visibly. Mixed-font segments at the same point size are combined into a line, with a notice that reflow uses its main font. Legacy narrow inline layers can widen into available space. Explicitly resized layers retain their chosen width. Nearby unrelated content and page boundaries still limit safe saving; a draft that cannot fit is retained with an error, rather than silently overlapping content.

Scroll through the continuous page stack to see the next page automatically. Distant pages use lazy image previews; the active visible page loads the actual PDF and editable text. Pending edits are saved before activating another page. Download shows an indeterminate preparation animation, then starts the real file download and retains Save/Open links.

## Sign-in and sign-up

The landing page is public. Protected PDF tools require sign-in when authentication is configured. Private workspaces use a normal web form and an optional 30-day HTTP-only cookie; browser-native Basic password challenges are removed. Public email/password accounts use Supabase once the project URL and public key are configured. See [account setup](ACCOUNTS.md). No user account database is stored on Render's ephemeral filesystem.

## Zoom and OCR output

New documents automatically fit the actual available workspace width. Fit page width uses that same container measurement. Manual plus/minus choices remain until Fit page width or another document is opened.

For changing words in a scan, use **Editable scan** (approximate artwork retention) or **Editable text copy** (text only). Both outputs group recognized words into editable lines. **Searchable PDF** deliberately retains the scanned image and adds invisible search text; after it finishes, use **Make scanned text editable** to reconstruct visible editable text. Reconstruction supports Western Latin text; other scripts may remain searchable only.

## Blank documents and text boxes

The landing page keeps the normal uploader and adds a small **Start with a blank PDF** link. It creates a real blank A4 PDF on the processing backend. Insert images, add text or use other tools, then download normally.

Add Text remains selected after placement. Click an empty area, type, then click another empty area to create a separate box, including before the first autosave finishes. The **Next text box** toolbar offers 12 bundled font/style choices, size and colour. It sets the style for the next placement. Existing boxes have independent properties.

Choose **Move / resize / style box** above the active box to save it and reveal its selection controls. Drag the saved box to move it, drag its corner to resize the frame, or change font and size using **Apply layer changes**. Frame resizing reflows text; font size changes enlarge or shrink the letters. Both are saved in the PDF. Select another saved box or use **Add another text box** to place more.

OCR scans pages containing both native text and images; searchable mode no longer skips an entire image-containing page just because it already has a selectable heading. Mixed-page searchable conversion rasterizes the rendered appearance and supplies a recognized text layer; review recognition, since it does not retain that page's original text/font structures. Editable scan reconstruction also has the disclosed artwork/font limitations. No OCR engine can guarantee recognition of every glyph in a blurry or low-resolution image.
