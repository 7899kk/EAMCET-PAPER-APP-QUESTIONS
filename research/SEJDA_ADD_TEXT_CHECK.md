# Sejda Add Text observation — 2026-11-22

A generated one-page PDF headed “Add text interaction sample” was uploaded to Sejda's ordinary online PDF editor. No private user PDF was sent.

Observed and exercised:

- Text mode is active by default. Clicking an empty page area creates an inline “Type your text” field.
- A toolbar beside the active text exposes bold, italic, size, family, colour, link, Move, Duplicate and Delete.
- Move changes the element out of content-editing mode and enables dragging. A drag changed its CSS position from [585.5,304.531] to [655.5,349.531].
- Bold was applied. Duplicate created a second object; Delete removed the selected copy.
- Apply changes and Download produced a real PDF. Independent MuPDF extraction found the added words once, in Helvetica-Bold at 10 pt, with the original heading preserved.

The ordinary added-text UI did not expose a frame-resize handle in the observed state. Edit karo retains its explicit frame handle as an additional feature; resizing reflows text at its chosen size. This does not establish identical internals or all Sejda functionality.

Edit karo removes the separate Move / resize / style activation and text-property textarea/Apply step for Add Text. Formatting and movement operate on the active on-page text and autosave through the PDF backend. Existing-text editing and advanced Layers remain separate.
