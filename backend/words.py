"""Map rendered words to encoded PDF operands and edit only their source ranges.

The UI word boxes are controls; no redaction, cover rectangle, or text overlay
is used to save a word edit. Unsupported transformations fail conservatively.
"""
import collections
import io
import math
import re
import unicodedata

import pikepdf
import pymupdf as fitz
from .content import cmap, font_width

WORD_PATTERN = re.compile(r"\w+(?:['’\-]\w+)*|[^\w\s]+", re.UNICODE)


def _instruction(args, operator):
    return pikepdf.ContentStreamInstruction(args, pikepdf.Operator(operator))


def _glyphs(font, mapping, raw):
    width = len(next(iter(mapping)))
    if len(raw) % width:
        raise ValueError('Invalid character encoding.')
    for offset in range(0, len(raw), width):
        code = raw[offset:offset + width]
        yield code, mapping[code]


def _word_spaces(raw, mapping):
    return raw.count(b' ') if len(next(iter(mapping))) == 1 else 0


def source_runs(pdf, page_index, page_transform):
    """Track text matrices and individual encoded glyph origins, in draw order."""
    page = pdf.pages[page_index]
    instructions = list(pikepdf.parse_content_stream(page))
    fonts = page.Resources.get('/Font', {})
    state = {'font': None, 'size': 12., 'spacing': 0., 'wordspacing': 0.,
             'render': 0, 'hscale': 100., 'rise': 0., 'leading': 0.,
             'ctm': fitz.Matrix(1, 0, 0, 1, 0, 0),
             'fill_space': pikepdf.Name('/DeviceGray'), 'fill_restore': [_instruction([0], 'g')]}
    stack, output = [], []
    mapping_cache, width_cache = {}, {}
    tm = lm = fitz.Matrix(1, 0, 0, 1, 0, 0)
    known = True
    for index, instruction in enumerate(instructions):
        args, op = instruction.operands, str(instruction.operator)
        prelude = []
        if op == 'q':
            stack.append(state.copy())
        elif op == 'Q' and stack:
            state = stack.pop()
        elif op in ('g', 'rg', 'k'):
            state['fill_space'] = pikepdf.Name({'g':'/DeviceGray','rg':'/DeviceRGB','k':'/DeviceCMYK'}[op])
            state['fill_restore'] = [_instruction(list(args), op)]
        elif op == 'cs':
            state['fill_space'] = args[0]
            state['fill_restore'] = None
        elif op in ('sc', 'scn'):
            state['fill_restore'] = [_instruction([state['fill_space']], 'cs'), _instruction(list(args), op)]
        elif op == 'gs':
            graphics = page.Resources.get('/ExtGState', {}).get(str(args[0]), {})
            if '/Font' in graphics:
                state['font'] = None
        elif op == 'cm':
            state['ctm'] = fitz.Matrix(*map(float, args)) * state['ctm']
        elif op == 'BT':
            tm = lm = fitz.Matrix(1, 0, 0, 1, 0, 0)
            known = True
        elif op == 'Tf':
            state['font'], state['size'] = str(args[0]), float(args[1])
        elif op in ('Tc', 'Tw', 'Tr', 'Tz', 'Ts', 'TL'):
            key = {'Tc': 'spacing', 'Tw': 'wordspacing', 'Tr': 'render',
                   'Tz': 'hscale', 'Ts': 'rise', 'TL': 'leading'}[op]
            state[key] = float(args[0])
        elif op == 'Tm':
            tm = lm = fitz.Matrix(*map(float, args))
            known = True
        elif op in ('Td', 'TD', 'T*', "'", '"'):
            if op == 'TD':
                state['leading'] = -float(args[1])
            if op == '"':
                state['wordspacing'], state['spacing'] = float(args[0]), float(args[1])
            if op in ("'", '"'):
                prelude = ([_instruction([args[0]], 'Tw'), _instruction([args[1]], 'Tc')] if op == '"' else []) + [_instruction([], 'T*')]
            tx, ty = (float(args[0]), float(args[1])) if op in ('Td', 'TD') else (0., -state['leading'])
            lm = fitz.Matrix(1, 0, 0, 1, tx, ty) * lm
            tm, known = fitz.Matrix(lm), True
        if op not in ('Tj', 'TJ', "'", '"'):
            continue
        font = fonts.get(state['font']) if state['font'] else None
        if state['font'] not in mapping_cache:
            mapping_cache[state['font']] = cmap(font) if font is not None else None
        mapping = mapping_cache[state['font']]
        if not mapping or not known or state['size'] <= 0 or state['hscale'] <= 0:
            known = False
            continue
        parts = list(args[0]) if op == 'TJ' else [args[-1]]
        offset, characters, glyphs, raw_parts, advance = 0, [], [], [], 0.
        matrix = tm * state['ctm'] * page_transform
        horizontal = (abs(matrix.b) < .0001 and abs(matrix.c) < .0001
                      and matrix.a > 0 and matrix.d < 0 and state['render'] == 0)
        try:
            for part in parts:
                if not isinstance(part, pikepdf.String):
                    advance -= float(part) * state['size'] / 1000
                    continue
                raw = bytes(part)
                raw_parts.append(raw)
                for code, char in _glyphs(font, mapping, raw):
                    origin = fitz.Point(advance * state['hscale'] / 100, state['rise']) * matrix
                    glyphs.append({'char': char, 'start': offset, 'end': offset + len(char),
                                   'origin': (origin.x, origin.y), 'code': code})
                    characters.append(char)
                    offset += len(char)
                    width_key = (state['font'], code)
                    if width_key not in width_cache:
                        width_cache[width_key] = font_width(font, code, mapping)
                    advance += width_cache[width_key] * state['size'] / 1000
                    advance += state['spacing']
                    if len(code) == 1 and code == b' ':
                        advance += state['wordspacing']
        except (ValueError, KeyError, TypeError, OverflowError):
            known = False
            continue
        if op in ('Tj', 'TJ', "'", '"'):
            output.append({**state, 'id': index, 'fontobj': font, 'mapping': mapping,
                           'text': ''.join(characters), 'glyphs': glyphs, 'parts': parts, 'prelude': prelude,
                           'horizontal': horizontal, 'xscale': matrix.a, 'yscale': abs(matrix.d)})
        tm = fitz.Matrix(1, 0, 0, 1, advance * state['hscale'] / 100, 0) * tm
    return instructions, output


def _cell(origin):
    return math.floor(origin[0] * 5), math.floor(origin[1] * 5)


def _word_map(data, page_index):
    with pikepdf.open(io.BytesIO(data)) as pdf, fitz.open(stream=data, filetype='pdf') as doc:
        page = doc[page_index]
        _, runs = source_runs(pdf, page_index, page.transformation_matrix)
        by_position = collections.defaultdict(list)
        by_id = {run['id']: run for run in runs}
        for run in runs:
            for glyph in run['glyphs']:
                if len(glyph['char']) == 1:
                    by_position[_cell(glyph['origin'])].append((run, glyph))
        words = []
        # Word detection never needs embedded image bytes (especially costly on scans).
        for block in page.get_text('rawdict', flags=fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES)['blocks']:
            for line in block.get('lines', []):
                chars = [{**char, 'style': span} for span in line['spans'] for char in span['chars']]
                text = ''.join(char['c'] for char in chars)
                # MuPDF usually emits one Unicode scalar per char. Ligatures with
                # multiple Unicode scalars need a separate shaping implementation.
                if any(len(char['c']) != 1 for char in chars):
                    continue
                for match in WORD_PATTERN.finditer(text):
                    selected = chars[match.start():match.end()]
                    bounds = fitz.Rect(selected[0]['bbox'])
                    mapped = []
                    for char in selected:
                        bounds |= fitz.Rect(char['bbox'])
                        cell = _cell(char['origin'])
                        candidates = []
                        for x in range(cell[0] - 1, cell[0] + 2):
                            for y in range(cell[1] - 1, cell[1] + 2):
                                for run, glyph in by_position.get((x, y), []):
                                    if (glyph['char'] == char['c'] and
                                        abs(glyph['origin'][0] - char['origin'][0]) < .08 and
                                        abs(glyph['origin'][1] - char['origin'][1]) < .08):
                                        candidates.append((run, glyph))
                        mapped.append(candidates[0] if len(candidates) == 1 else None)
                    parts, compatible = [], bool(mapped and all(mapped))
                    first = mapped[0][0] if compatible else None
                    if compatible:
                        for run, glyph in mapped:
                            if (not run['horizontal'] or run['font'] != first['font'] or
                                any(abs(run[key] - first[key]) > .001 for key in
                                    ('size', 'spacing', 'wordspacing', 'hscale', 'yscale', 'xscale'))):
                                compatible = False
                            if parts and parts[-1]['id'] == run['id'] and parts[-1]['end'] == glyph['start']:
                                parts[-1]['end'] = glyph['end']
                            else:
                                parts.append({'id': run['id'], 'start': glyph['start'], 'end': glyph['end']})
                        if any(parts[i]['id'] >= parts[i + 1]['id'] for i in range(len(parts) - 1)):
                            compatible = False
                        if len(parts) > 1:
                            if parts[0]['end'] != len(by_id[parts[0]['id']]['text']) or parts[-1]['start'] != 0:
                                compatible = False
                            if any(part['start'] != 0 or part['end'] != len(by_id[part['id']]['text']) for part in parts[1:-1]):
                                compatible = False
                        # A change of style inside a word is not silently flattened.
                        if any(char['style']['font'] != selected[0]['style']['font'] or
                               char['style']['color'] != selected[0]['style']['color'] for char in selected):
                            compatible = False
                    complex_script = any(unicodedata.bidirectional(c) in ('R', 'AL', 'AN') or 0x0900 <= ord(c) <= 0x109f for c in match.group())
                    editable = bool(not complex_script and compatible and tuple(line['dir']) == (1., 0.) and page.rotation == 0)
                    style = selected[0]['style']
                    identity = ';'.join(f"{part['id']}:{part['start']}:{part['end']}" for part in parts)
                    words.append({'id': identity if editable else 'readonly-' + str(len(words)),
                                  'text': match.group(), 'bbox': list(bounds), 'size': first['size'] * first['yscale'] if editable else style['size'],
                                  'font': style['font'], 'color': f"#{style['color']:06x}",
                                  'editable': editable, 'parts': parts if editable else [],
                                  'reason': None if editable else 'This word uses an unsupported font or complex script, a reused object, overlapping glyphs, mixed styles, or transformed text. Its original content cannot be safely replaced here.'})
        return words


def inspect_words(data, page_index):
    return _word_map(data, page_index)


def _split_parts(run, start, end):
    """Keep byte strings and TJ kerning outside the selected range unchanged."""
    prefix, selected, suffix = [], [], []
    offset = 0
    for part in run['parts']:
        if not isinstance(part, pikepdf.String):
            (prefix if offset <= start else selected if offset < end else suffix).append(part)
            continue
        buckets = [bytearray(), bytearray(), bytearray()]
        for code, char in _glyphs(run['fontobj'], run['mapping'], bytes(part)):
            next_offset = offset + len(char)
            if offset < start < next_offset or offset < end < next_offset:
                raise ValueError('The word boundary splits a font ligature.')
            bucket = 0 if next_offset <= start else 2 if offset >= end else 1
            buckets[bucket].extend(code)
            offset = next_offset
        for target, raw in zip((prefix, selected, suffix), buckets):
            if raw:
                target.append(pikepdf.String(bytes(raw)))
    return prefix, selected, suffix


def _replace_range(run, start, end, text, size, color, available_width, fit):
    prefix, removed, suffix = _split_parts(run, start, end)
    original = b''.join(bytes(x) for x in removed if isinstance(x, pikepdf.String))
    adjustments = sum(float(x) for x in removed if not isinstance(x, pikepdf.String))
    reverse = {char: code for code, char in run['mapping'].items() if len(char) == 1}
    try:
        encoded = b''.join(reverse[char] for char in text)
    except KeyError as exc:
        raise ValueError(f'The original font does not contain {exc.args[0]!r}. This word cannot use that character without changing its font.')
    old_count = sum(1 for _ in _glyphs(run['fontobj'], run['mapping'], original))
    old_advance = ((font_width(run['fontobj'], original, run['mapping']) - adjustments) * run['size'] / 1000
                   + old_count * run['spacing'] + _word_spaces(original, run['mapping']) * run['wordspacing'])
    new_size = float(size) / run['yscale'] if size is not None else run['size']
    if not 1 <= new_size <= 1000:
        raise ValueError('Font size is outside the supported range.')
    natural_advance = (font_width(run['fontobj'], encoded, run['mapping']) * new_size / 1000
                       + len(text) * run['spacing'] + _word_spaces(encoded, run['mapping']) * run['wordspacing'])
    visual_width = natural_advance * run['hscale'] / 100 * run['xscale']
    factor = min(1., available_width / visual_width) if fit and visual_width > 0 else 1.
    if factor <= 0:
        raise ValueError('This word has no editable space.')
    adjustment = (natural_advance - old_advance / factor) * 1000 / new_size
    output = list(run.get('prelude', []))
    if prefix:
        output.append(_instruction([pikepdf.Array(prefix)], 'TJ'))
    output.append(_instruction([pikepdf.Name(run['font']), new_size], 'Tf'))
    if color:
        if run['fill_restore'] is None:
            raise ValueError('This word’s colour space cannot be safely restored. Keep its original colour.')
        if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            raise ValueError('Invalid colour.')
        output.append(_instruction([int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)], 'rg'))
    if factor != 1:
        output.append(_instruction([run['hscale'] * factor], 'Tz'))
    output.append(_instruction([pikepdf.Array([pikepdf.String(encoded), adjustment])], 'TJ'))
    output.append(_instruction([pikepdf.Name(run['font']), run['size']], 'Tf'))
    if factor != 1:
        output.append(_instruction([run['hscale']], 'Tz'))
    if color:
        output.extend(run['fill_restore'])
    if suffix:
        output.append(_instruction([pikepdf.Array(suffix)], 'TJ'))
    return output


def replace_word(data, page_index, identity, original, text, size=None, color=None, fit=True, word_targets=None):
    if not isinstance(text, str) or len(text) > 200 or any(c.isspace() for c in text):
        raise ValueError('Edit one word at a time (up to 200 characters, without spaces).')
    words = inspect_words(data, page_index) if word_targets is None else word_targets
    word = next((word for word in words if word['id'] == identity and word['editable']), None)
    if word is None or word['text'] != original:
        raise ValueError('This word changed or is not editable. Select it again.')
    if size is not None and not 4 <= float(size) <= 144:
        raise ValueError('Font size must be 4–144 pt.')
    with pikepdf.open(io.BytesIO(data)) as pdf, fitz.open(stream=data, filetype='pdf') as doc:
        instructions, records = source_runs(pdf, page_index, doc[page_index].transformation_matrix)
        runs = {run['id']: run for run in records}
        if color == word['color']:
            color = None
        first = word['parts'][0]
        first_glyph = next(g for g in runs[first['id']]['glyphs'] if g['start'] == first['start'])
        available_width = word['bbox'][2] - first_glyph['origin'][0]
        replacements = []
        for part in word['parts']:
            run = runs[part['id']]
            replacement = _replace_range(run, part['start'], part['end'], text if part is first else '',
                                         size if part is first else None, color if part is first else None,
                                         available_width, fit if part is first else False)
            replacements.append((part['id'], replacement))
        for index, replacement in sorted(replacements, reverse=True):
            instructions[index:index + 1] = replacement
        pdf.pages[page_index].Contents = pdf.make_stream(pikepdf.unparse_content_stream(instructions))
        output = io.BytesIO()
        pdf.save(output)
        return output.getvalue()
