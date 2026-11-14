# Editing individual existing words

1. Upload a selectable PDF. The editor starts in **Edit text** mode.
2. Click one underlined word. The on-page input selects only that word, not its sentence.
3. Type the replacement. Press **Enter** or **Save**. Press **Esc** to cancel.
4. Download the PDF and open it in another viewer.

Use **Word properties** for size/colour. On phones, use the properties icon on the small on-page editor. The original font family is retained. Fit-to-space is on by default: longer replacements are condensed horizontally so the next word stays in its original place. Turning Fit off permits natural width, which can overlap adjacent content. Empty the input to remove the selected word while keeping its layout space. Paragraph reflow is not implemented.

The input is a browser editing control. The saved PDF changes actual encoded text operands. No white rectangle, redaction replacement, or added text overlay is used. Repeated words and compatible words fragmented across multiple text instructions are identified by character positions, not a document-wide string search.

Grey words explain why they cannot be edited safely. Unsupported cases include certain fonts/encodings or missing glyphs, complex scripts needing shaping, mixed styles within one word, reused Form XObjects, overlapping glyphs, and rotated/outlined text. A scanned page is an image: it has no existing text word to change. OCR adds searchability; it does not reconstruct editable scanned text. These limitations are shown in the editor.

## Professional-editor references

Reviewed on 2026-11-14:

- [Sejda’s PDF editor](https://www.sejda.com/pdf-editor) documents selecting its Text tool and clicking existing text to edit. It also explicitly lists missing font characters, complex-script limitations, and unsupported editing of scanned text.
- [iLovePDF’s PDF editor](https://www.ilovepdf.com/edit-pdf) describes adding text, shapes, comments, and highlights. Those additions are distinct from replacing original PDF content.

These public feature descriptions informed the interaction design. No claim is made about the private implementation of either service, and no proprietary editor code was reused. The implementation remains local/open-source Python processing with PDF.js rendering.
