"""Small generated example used by the actual upload/edit/download workflow."""
import pymupdf as fitz

def sample_pdf():
    with fitz.open() as doc:
        page = doc.new_page(width=595, height=842)
        page.insert_text((52, 70), 'Try editing this PDF', fontsize=24, color=(.09,.35,.25))
        page.insert_text((52, 120), 'The quick brown fox jumps over the lazy dog.', fontsize=16)
        page.insert_text((52, 158), '1. Click a paragraph and type. Changes save automatically.', fontsize=12)
        page.insert_text((52, 185), '2. Open Shapes. Choose an ellipse and drag on the page.', fontsize=12)
        page.insert_text((52, 212), '3. Select the shape to move, resize, recolour or delete it.', fontsize=12)
        page.insert_text((52, 239), '4. Download the PDF and reopen it to check your changes.', fontsize=12)
        page.insert_text((52, 300), 'Space for your shapes:', fontsize=14)
        doc.set_metadata({'title': 'Edit karo editable sample', 'author': 'Edit karo'})
        return doc.tobytes(garbage=4, deflate=True)
