# Sejda longer-text comparison, 2026-11-17

A generated 420 × 500 pt PDF with 18 pt selectable Helvetica text was uploaded to Sejda's public editor using Chromium. It contained `Link-`, `I'm feeling happy Today`, a separate paragraph, and a separate multiline paragraph. No user document was sent to Sejda.

Replacing just `feeling` with `Enthusiam` kept the computed font size at 56.3571 px at the editor's current zoom. The editable line widened from 593.203125 px to 693.359375 px, moving `happy Today` right. Its height stayed 60.359375 px. The editor used `white-space: pre` and `overflow: visible`.

Replacing that line with `I'm feeling really enthusiastic and happy Today and ready to make this type of video.` widened the editable element to 2102.8125 px at the same font size and height. The downloaded result retained 18 pt text. It did not automatically wrap that single-line replacement: text extended beyond the 420 pt page and part of the replacement was outside the visible/extractable area. The separate paragraphs stayed at their original positions.

These observations describe this controlled example, not every Sejda editing mode or PDF structure. The first automated attempt timed out waiting for the uploaded text; retrying with an upload-readiness delay completed editing, Apply changes, download and independent MuPDF inspection successfully.

Folio matches fixed-size typing and movement of following words. It additionally wraps at the available paragraph/page boundary and grows downward into free space. It refuses overflow into other detected page objects rather than shrinking automatically or silently losing off-page text. It does not claim identical proprietary internals or full-document word-processor layout.
