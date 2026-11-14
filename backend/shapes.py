"""Editable PDF shape annotations, persisted in the document itself."""
import math
import pymupdf as fitz

KINDS = {fitz.PDF_ANNOT_SQUARE: 'rectangle', fitz.PDF_ANNOT_CIRCLE: 'ellipse', fitz.PDF_ANNOT_LINE: 'line'}

def hex_color(values):
    if not values:
        return None
    if len(values) == 1:
        values = values * 3
    if len(values) != 3:
        return '#263449'
    return '#' + ''.join(f'{round(max(0, min(1, v))*255):02x}' for v in values)

def identify(annot):
    return annot.info.get('id') or f'xref:{annot.xref}'

def describe(page):
    result = []
    for annot in page.annots() or []:
        kind = KINDS.get(annot.type[0])
        if not kind:
            continue
        points = annot.vertices if kind == 'line' else None
        if kind == 'line' and annot.line_ends and annot.line_ends[1] == fitz.PDF_ANNOT_LE_CLOSED_ARROW:
            kind = 'arrow'
        rect = list(annot.rect)
        if annot.rect_delta:
            rect = [v+d for v,d in zip(rect,annot.rect_delta)]
        if points:
            rect = [min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points)]
        result.append({'id': identify(annot), 'type': kind, 'rect': rect, 'points': points,
                       'color': hex_color(annot.colors.get('stroke')) or '#263449',
                       'fill': hex_color(annot.colors.get('fill')), 'width': annot.border.get('width', 2),
                       'editable': not bool(page.rotation), 'reason': 'Rotate the page to 0° before editing shapes.' if page.rotation else ''})
    return result

def inspect_shapes(data, page_index):
    with fitz.open(stream=data, filetype='pdf') as doc:
        if not 0 <= page_index < len(doc):
            raise ValueError('Invalid page.')
        return describe(doc[page_index])

def apply(page, operation, args, rgb):
    if page.rotation:
        raise ValueError('Rotate this page to 0° before editing shapes.')
    existing = None
    if operation != 'shape-add':
        existing = next((a for a in page.annots() or [] if identify(a) == str(args.get('id')) and a.type[0] in KINDS), None)
        if existing is None:
            raise ValueError('This shape no longer exists. Select it again.')
        if operation == 'shape-delete':
            page.delete_annot(existing)
            return
    kind = args.get('type', 'rectangle')
    if kind not in ('rectangle', 'ellipse', 'line', 'arrow'):
        raise ValueError('Choose a rectangle, ellipse, line or arrow.')
    coords = args.get('rect', [])
    if len(coords) != 4 or not all(isinstance(v, (float, int)) and math.isfinite(v) for v in coords):
        raise ValueError('Invalid shape coordinates.')
    x0, y0, x1, y1 = coords
    if x1 < x0 or y1 < y0 or x0 < 0 or y0 < 0 or x1 > page.rect.width or y1 > page.rect.height:
        raise ValueError('Keep the shape inside the page.')
    if max(x1-x0, y1-y0) < 3 or (kind in ('rectangle', 'ellipse') and min(x1-x0, y1-y0) < 3):
        raise ValueError('Draw a larger shape.')
    width = float(args.get('width', 2))
    if not math.isfinite(width) or not .5 <= width <= 12:
        raise ValueError('Border width must be 0.5–12 pt.')
    color = rgb(args.get('color', '#263449'))
    fill = rgb(args['fill']) if args.get('fill') else None
    points = args.get('points')
    if kind in ('line', 'arrow'):
        points = points or [[x0, y0], [x1, y1]]
        if len(points) != 2 or any(len(p) != 2 or any(not isinstance(v, (int, float)) or not math.isfinite(v) for v in p) or not page.rect.contains(fitz.Point(p)) for p in points):
            raise ValueError('Keep line endpoints inside the page.')
        if abs(min(p[0] for p in points)-x0) > .1 or abs(max(p[0] for p in points)-x1) > .1 or abs(min(p[1] for p in points)-y0) > .1 or abs(max(p[1] for p in points)-y1) > .1:
            raise ValueError('Line endpoints must match its rectangle.')
    old_id = identify(existing) if existing else None
    if existing:
        page.delete_annot(existing)
    if kind == 'rectangle':
        annot = page.add_rect_annot(fitz.Rect(coords))
    elif kind == 'ellipse':
        annot = page.add_circle_annot(fitz.Rect(coords))
    else:
        annot = page.add_line_annot(fitz.Point(points[0]), fitz.Point(points[1]))
        if kind == 'arrow':
            annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_CLOSED_ARROW)
    annot.set_colors(stroke=color, fill=fill)
    annot.set_border(width=width)
    annot.set_flags(fitz.PDF_ANNOT_IS_PRINT)
    annot.update()
    if kind in ('rectangle', 'ellipse'):
        # MuPDF updates /RD with the new border width. Reapply the inner geometry
        # after that update so styling never changes the shape's size or position.
        annot.set_rect(fitz.Rect(coords))
        annot.update()
    if old_id:
        page.parent.xref_set_key(annot.xref, 'NM', fitz.get_pdf_str(old_id))
