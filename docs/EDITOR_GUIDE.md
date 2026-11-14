# Edit an existing word and select shapes

Release `word-shapes-2`. Open the current Render editor, refresh, then choose **Try sample PDF**. This is a generated real PDF sent through the same upload, font inspection and PDF-processing engine as an uploaded document.

1. **Edit existing text** is directly above the PDF. The adjacent count reports how many words can be edited.
2. Click **brown** in the sample's first sentence. Only that word appears in the on-page field.
3. Type **red**, then press Enter or Save. Download PDF writes the modified original PDF content.
4. Open **Shapes**, choose **Ellipse**, then drag across the blank part of the page.
5. The ellipse is selected automatically. Drag the ellipse to move it, or drag the corner handle to resize it.
6. Change Border, Fill or Width, then choose **Apply style**. **Delete shape**, Undo and Redo change actual document versions.
7. Choose **Select shapes** to select a previous shape. Download, reopen the downloaded file, then use Shapes → Select shapes to select the saved shape again.

The top toolbar remains visible while the PDF scrolls. On phones, the editing toolbar can scroll horizontally; the separate **Edit existing text** button and capability count remain visible without scrolling the toolbar. **How to edit** opens these instructions inside the editor.

Grey word targets explain unsupported fonts or document structures. Scans contain pixels rather than editable words; OCR can make them searchable. Flattened vector artwork and raster images are not supported shape annotations and cannot be selected with Select shapes. The original PDF text font is retained. A shorter replacement keeps its natural width and leaves layout space before the following word; longer words fit the original space by default. Paragraph reflow is unsupported.

## Sejda comparison actually performed

On 2026-11-14, a generated single-page PDF containing “The quick brown fox jumps over the lazy dog.” was uploaded to [Sejda](https://www.sejda.com/pdf-editor). Its **Text** tool was selected, the existing line clicked, and just the word **brown** selected inside the editable text field and replaced with **red**. **Apply changes → Download** produced a PDF independently reopened with MuPDF; the changed sentence was present and the original sentence was absent. The results page also rendered the edited PDF. Only generated sample material was uploaded, with no user documents or private files.

Sejda's line-based editable field allows selecting a word within a line. Folio explicitly targets each supported word and opens an input containing that word only. Folio does not claim Sejda's full font, paragraph or object-editing capabilities, or reuse its proprietary implementation.
