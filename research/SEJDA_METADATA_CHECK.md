# Metadata comparison — 2026-11-22

A generated two-page PDF was used in both tools. No private user PDF was uploaded to Sejda. It contains eight standard Info properties, a custom CustomNote property, catalog XMP with deliberately conflicting title/author/subject values, page text/vector artwork and a comment by “Sample reviewer.”

## Observed Sejda workflow

The official tool is https://www.sejda.com/edit-pdf-metadata. After upload it offers “Change metadata” and “Remove all metadata.” Change metadata displays existing fields, including custom fields, and an Add new field control. Update PDF Metadata produces a download. Remove all metadata produces its own download. The guessed /remove-pdf-metadata URL returned 404; clearing is part of the metadata tool.

Both Sejda outputs were actually downloaded and independently inspected.

## Same-input results

| Check | Sejda | Edit karo |
|---|---|---|
| Title, Author, Subject, Keywords, Creator and Producer edited | Passed | Passed |
| Custom property retained during standard edits | Passed | Passed |
| Info and XMP title/author/subject agree after editing | Original XMP values remained in this sample | Updated in both locations |
| Standard/custom properties and XMP cleared | Passed | Passed |
| Page count, extracted text and rendered pixels unchanged | Passed | Passed |
| Comment and comment author preserved | Passed | Passed |
| Creation/modification instants retained | Passed; serialized with +01:00 | Passed; shown in UTC |

The XMP result applies to this deliberately conflicting test file, not every Sejda document. Sejda updated XMP Keywords, CreatorTool and Producer; dc:title, dc:creator and dc:description retained their original values.

Edit karo additionally tests custom-property editing/removal, dates, XMP-only properties, object/page XMP clearing, validation, Undo/Redo, export and reupload on desktop/mobile.

## Scope

Clear Metadata removes Info and document/page/object XMP associations from a fully rewritten PDF. It preserves visible content, comments and managed editable objects. It does not delete sensitive page text, comment authors or every possible application-specific hidden structure. Session Undo retains earlier versions until removed/expired; those versions are not embedded in the cleared download.

The output bundle contains the generated original, both tools' edited/cleared PDFs and an independently extracted JSON report. No user document or credentials are included.
