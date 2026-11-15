# Existing-text editing

See [the current editor guide](EDITOR_GUIDE.md) for the complete interaction.

Spaces and paragraphs are accepted. Short replacements use original encoded operands and retain their font/position where supported. Larger replacements remove the selected original characters and create a readable vector text layer, with wrapping, a movable/resizable box and disclosed font fallback. They do not use a whiteout or retain hidden original text. Automatic surrounding-paragraph reflow is unsupported; a text box can be placed in free space instead.

Legacy API `replace-word` still accepts its optional fit flag for compatibility; the editor uses `replace-readable` and does not condense text by default. Text boxes remain editable through Layers after download/reupload. Scans require either searchable OCR or the explicitly lossy editable text-copy mode. Unsupported source fonts/encodings, complex scripts, reused Form objects and transformations can remain read-only.

Public professional-editor references: [Sejda](https://www.sejda.com/pdf-editor) and [iLovePDF](https://www.ilovepdf.com/edit-pdf). Their proprietary implementations were not reused. The implementation uses local open-source PDF processing.
