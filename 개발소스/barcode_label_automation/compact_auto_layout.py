"""Measured automatic layout for labels exceeding the native text-row budget.

The source data, complete barcode quiet zones and HRI are preserved. Images are
rendered at device DPI; symbols are never stretched to an arbitrary rectangle.
"""
from dataclasses import replace
from PIL import Image, ImageDraw


def _points(points, dpi):
    return max(1, round(points * dpi / 72))


def _text_box(font, text):
    return ImageDraw.Draw(Image.new('L', (1, 1), 255)).textbbox((0, 0), text, font=font)


def _text_width(font, text):
    box = _text_box(font, text)
    return box[2] - box[0]


def _pack_fields(lines, font, width, gap):
    """Keep input order, pairing at most two complete fields on a row."""
    packed = []
    for text in lines:
        needed = _text_width(font, text)
        if needed > width:
            return None
        if packed and len(packed[-1]) == 1 and packed[-1][0][1] + gap + needed <= width:
            packed[-1].append((text, needed))
        else:
            packed.append([(text, needed)])
    return packed


def render_compact_page(row, width_mm, height_mm, dpi, config, language):
    from .templates import (_display_text_lines, _encoder_settings, _is_one_d,
                            _auto_label_layout, _load_label_font, _max_text_lines, mm_to_dots)
    from .barcode_engine import render_barcode
    from .barcode_catalog import GS1_TYPES
    from .sanitizer import sanitize_barcode
    width, height = mm_to_dots(width_mm, dpi), mm_to_dots(height_mm, dpi)
    margin = max(2, mm_to_dots(.8, dpi))
    gap = max(2, mm_to_dots(.6, dpi))
    line_gap = max(1, mm_to_dots(.25, dpi))
    available_width, available_height = width - 2 * margin, height - 2 * margin
    if available_width < 1 or available_height < 1:
        raise ValueError("자동 배치 공간이 부족합니다. 용지 크기를 확인하세요.")
    lines = _display_text_lines(row, lambda text: text, None)
    value = sanitize_barcode(row.barcode)
    one_d = _is_one_d(config)
    base_layout = _auto_label_layout(width, height, config, value, min(len(lines), _max_text_lines(height_mm)))
    # Retain the former automatic bar height, then fit the text around it.
    base = replace(config, one_d_height=base_layout['barcode_height']) if one_d else config
    options = _encoder_settings(base)
    # Automatic 1D width still uses whole dot modules. Prefer the configured
    # module width and only use the existing auto-layout freedom when needed.
    symbol = render_barcode(config.barcode_type, value, options).convert('RGB')
    if one_d and 'module_width' not in config.encoder_options:
        preferred_module = max(1, round(config.one_d_narrow*dpi/203))
        for module in range(preferred_module, 0, -1):
            candidate = render_barcode(config.barcode_type, value,
                _encoder_settings(replace(base, one_d_narrow=module))).convert('RGB')
            if candidate.width <= available_width:
                symbol = candidate
                break
    if config.rotation not in {0, 90, 180, 270}:
        raise ValueError("바코드 회전은 0, 90, 180, 270도여야 합니다.")
    hri_text = value
    if config.barcode_type in GS1_TYPES:
        from .gs1 import build_gs1, parse_gs1
        hri_text = build_gs1(parse_gs1(value)).hri
    hri_font = _load_label_font(_points(6, dpi))
    show_hri = one_d and bool(options.get('human_readable', config.one_d_human_readable))
    if show_hri:
        hri_box = _text_box(hri_font, hri_text)
        hri_width = hri_box[2] - hri_box[0]
        hri_height = hri_box[3] - hri_box[1]
        combined_width = max(symbol.width, hri_width)
        if combined_width > available_width:
            raise ValueError("표시문자가 라벨 폭을 넘습니다. 용지 폭 또는 저장 도안을 확인하세요.")
        combined = Image.new('RGB', (combined_width, symbol.height + gap + hri_height), 'white')
        combined.paste(symbol, ((combined_width-symbol.width)//2, 0))
        ImageDraw.Draw(combined).text(((combined_width-hri_width)//2-hri_box[0], symbol.height+gap-hri_box[1]),
                                     hri_text, font=hri_font, fill='black')
        symbol = combined
    if config.rotation:
        symbol = symbol.rotate(-config.rotation, expand=True)
    if symbol.width > available_width or symbol.height > available_height:
        raise ValueError("바코드와 필수 여백이 라벨 영역을 넘습니다. 용지 또는 바코드 설정을 확인하세요.")
    # Stacked placement keeps 1D bars across the label. 2D tries a side panel
    # first so text does not force a configured square symbol to shrink.
    placements = ['stacked'] if one_d else ['side', 'stacked']
    for placement in placements:
        text_width = available_width if placement == 'stacked' else available_width-symbol.width-gap
        text_height = available_height-symbol.height-gap if placement == 'stacked' else available_height
        if text_width <= 0 or text_height <= 0:
            continue
        for half_points in range(16, 9, -1):  # 8pt down to the physical 5pt floor
            font = _load_label_font(_points(half_points / 2, dpi))
            packed = _pack_fields(lines, font, text_width, gap)
            if not packed:
                continue
            row_heights = [max(_text_box(font, text)[3]-_text_box(font, text)[1] for text,_ in group)
                           for group in packed]
            used = sum(row_heights) + line_gap*(len(packed)-1)
            if used > text_height:
                continue
            page = Image.new('RGB', (width, height), 'white')
            draw = ImageDraw.Draw(page)
            rectangles = []
            y = margin
            for group, ink_height in zip(packed, row_heights):
                x = margin
                for text, measured_width in group:
                    box = _text_box(font, text)
                    draw.text((x-box[0], y-box[1]), text, font=font, fill='black')
                    rectangles.append((x, y, measured_width, ink_height))
                    x += measured_width+gap
                y += ink_height+line_gap
            x = (width-symbol.width)//2 if placement=='stacked' else width-margin-symbol.width
            y = height-margin-symbol.height if placement=='stacked' else margin+(available_height-symbol.height)//2
            page.paste(symbol, (x, y))
            page.info['protected_bounds'] = [(x,y,symbol.width,symbol.height)]
            page.info['automatic_layout'] = {'mode':'compact', 'placement':placement, 'fields':lines,
                'font_pt':half_points/2, 'field_bounds':rectangles, 'symbol_bounds':(x,y,symbol.width,symbol.height),
                'human_readable':hri_text if show_hri else ''}
            return page
    raise ValueError("자동 배치할 공간이 부족합니다. 모든 값을 보존하고 글자 5pt 이상과 바코드 여백을 유지하려면 용지 크기 또는 저장 도안을 조정하세요.")
