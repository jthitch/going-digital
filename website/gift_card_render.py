"""Render gift voucher cards by overlaying details on admin-uploaded designs."""
import io
from datetime import date, datetime
from pathlib import Path

from django.conf import settings
from PIL import Image, ImageDraw, ImageFont


def _font_candidates(*, bold=False, mono=False):
    if mono:
        return [
            Path('C:/Windows/Fonts/consola.ttf'),
            Path('C:/Windows/Fonts/Courier New.ttf'),
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'),
            Path('/System/Library/Fonts/Supplemental/Courier New.ttf'),
        ]
    if bold:
        return [
            Path('C:/Windows/Fonts/arialbd.ttf'),
            Path('C:/Windows/Fonts/segoeuib.ttf'),
            Path(settings.BASE_DIR) / 'static' / 'fonts' / 'DejaVuSans-Bold.ttf',
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'),
            Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'),
        ]
    return [
        Path(settings.BASE_DIR) / 'static' / 'fonts' / 'DejaVuSans.ttf',
        Path('C:/Windows/Fonts/arial.ttf'),
        Path('C:/Windows/Fonts/segoeui.ttf'),
        Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
        Path('/System/Library/Fonts/Supplemental/Arial.ttf'),
    ]


def _load_font(size, *, bold=False, mono=False):
    size = max(int(size), 12)
    for path in _font_candidates(bold=bold, mono=mono):
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _parse_color(hex_color, fallback=(26, 26, 26)):
    value = (hex_color or '').lstrip('#')
    if len(value) == 6:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return fallback


def _format_expiry(expiry):
    if not expiry:
        return ''
    if isinstance(expiry, datetime):
        expiry = expiry.date()
    if isinstance(expiry, date):
        return expiry.strftime('%d %B %Y')
    try:
        return datetime.fromisoformat(str(expiry)[:10]).strftime('%d %B %Y')
    except (TypeError, ValueError):
        return str(expiry)


def _format_amount(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return f'£{value}'
    if number == int(number):
        return f'£{int(number)}'
    return f'£{number:g}'


def _text_width(draw, text, font):
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0]


def _text_height(draw, text, font):
    if not text:
        return 0
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[3] - bbox[1]


def _wrap_text(draw, text, font, max_width):
    words = (text or '').split()
    if not words:
        return []
    lines = []
    current = words[0]
    for word in words[1:]:
        trial = f'{current} {word}'
        if _text_width(draw, trial, font) <= max_width:
            current = trial
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def _line_height(draw, text, font, gap_factor=0.2):
    if not text:
        return 0
    return _text_height(draw, text, font) + max(int(font.size * gap_factor), 4)


def _block_height(draw, lines, font, gap=None):
    if not lines:
        return 0
    line_gap = gap if gap is not None else max(int(font.size * 0.25), 6)
    total = 0
    for line in lines:
        total += _text_height(draw, line, font) + line_gap
    return total


def _draw_centered_line(draw, text, center_x, y, font, color):
    if not text:
        return y
    line_width = _text_width(draw, text, font)
    draw.text((center_x - line_width // 2, y), text, font=font, fill=color)
    return y + _line_height(draw, text, font)


def _draw_centered_block(draw, lines, center_x, y, font, color, line_gap=None):
    if not lines:
        return y
    gap = line_gap if line_gap is not None else max(int(font.size * 0.25), 6)
    for line in lines:
        line_width = _text_width(draw, line, font)
        draw.text((center_x - line_width // 2, y), line, font=font, fill=color)
        y += _text_height(draw, line, font) + gap
    return y


def _load_logo():
    for name in ('logo-dark.png', 'logo.png'):
        path = Path(settings.BASE_DIR) / 'static' / 'img' / 'logo' / name
        if path.exists():
            with path.open('rb') as logo_file:
                return Image.open(logo_file).convert('RGBA')
    return None


def _logo_height(logo, max_width):
    if logo is None:
        return 0
    ratio = max_width / logo.width
    return max(int(logo.height * ratio), 1)


def _paste_logo(overlay, logo, center_x, y, max_width):
    if logo is None:
        return y
    ratio = max_width / logo.width
    logo_height = max(int(logo.height * ratio), 1)
    logo_width = max(int(logo.width * ratio), 1)
    resized = logo.resize((logo_width, logo_height), Image.Resampling.LANCZOS)
    overlay.paste(resized, (center_x - logo_width // 2, y), resized)
    return y + logo_height


def build_voucher_card_context(basket_data, voucher_code, voucher_value, expiry_date):
    """Build text fields for overlay from basket + voucher row."""
    recipient = (basket_data.get('recipient_name') or '').strip()
    purchaser = (basket_data.get('purchaser_name') or '').strip()
    message = (basket_data.get('gift_message') or '').strip()
    quantity = basket_data.get('quantity') or 1
    try:
        quantity = int(quantity)
    except (TypeError, ValueError):
        quantity = 1

    amount_each = _format_amount(voucher_value)
    if quantity > 1:
        value_line = f'{amount_each} each × {quantity}'
    else:
        value_line = amount_each

    expiry_label = _format_expiry(expiry_date)
    return {
        'title': 'Photography Course Gift voucher',
        'value': value_line,
        'code': voucher_code,
        'recipient': recipient,
        'purchaser': purchaser,
        'message': message,
        'expiry': expiry_label,
        'redeem_line': 'Redeem when booking at goingdigital.co.uk',
        'validity_line': 'Valid for 9 months on any Going Digital photography course',
    }


def _measure_layout(draw, fields, width, panel_width, panel_padding, content_width, logo, scale=1.0):
    logo_width = max(int(panel_width * 0.30 * scale), 1)
    logo_h = _logo_height(logo, logo_width)

    title_font = _load_font(width * 0.030 * scale)
    amount_font = _load_font(width * 0.12 * scale, bold=True)
    message_font = _load_font(width * 0.034 * scale)
    label_font = _load_font(width * 0.026 * scale)
    code_font = _load_font(width * 0.055 * scale, bold=True, mono=True)
    detail_font = _load_font(width * 0.024 * scale)
    small_font = _load_font(width * 0.020 * scale)

    message_lines = []
    validity_lines = []
    redeem_lines = []
    if fields['message']:
        message_lines = _wrap_text(
            draw, f'"{fields["message"]}"', message_font, content_width,
        )
    validity_lines = _wrap_text(draw, fields['validity_line'], small_font, content_width)
    redeem_lines = _wrap_text(draw, fields['redeem_line'], small_font, content_width)

    gap = lambda fraction: max(int(width * fraction * scale), 4)

    height = panel_padding
    height += logo_h + gap(0.018)
    height += _line_height(draw, fields['title'], title_font)
    height += gap(0.012)
    height += _line_height(draw, fields['value'], amount_font)
    height += gap(0.02)

    if fields['recipient']:
        height += _line_height(draw, f"To: {fields['recipient']}", label_font)
        height += gap(0.008)

    if message_lines:
        height += _block_height(draw, message_lines, message_font)
        height += gap(0.015)

    height += gap(0.008) + gap(0.025)  # divider spacing

    if fields['purchaser']:
        height += _line_height(draw, f"From: {fields['purchaser']}", detail_font)

    height += _line_height(draw, 'Voucher code', label_font)
    height += _line_height(draw, fields['code'], code_font)
    height += gap(0.01)

    if fields['expiry']:
        height += _line_height(draw, f"Expiry date: {fields['expiry']}", detail_font)

    height += _block_height(draw, validity_lines, small_font)
    height += _block_height(draw, redeem_lines, small_font)
    height += panel_padding

    fonts = {
        'title': title_font,
        'amount': amount_font,
        'message': message_font,
        'label': label_font,
        'code': code_font,
        'detail': detail_font,
        'small': small_font,
    }
    blocks = {
        'message_lines': message_lines,
        'validity_lines': validity_lines,
        'redeem_lines': redeem_lines,
    }
    return height, fonts, blocks, logo_width


def render_gift_card_png(design, basket_data, voucher_code, voucher_value, expiry_date):
    """
    Composite voucher details onto design.image. Returns PNG bytes.

    Layout scales with the background image size: logo, large amount, personal
    message, recipient, voucher code, and expiry inside a readable panel.
    """
    with design.image.open('rb') as image_file:
        base = Image.open(image_file).convert('RGBA')

    width, height = base.size
    fields = build_voucher_card_context(basket_data, voucher_code, voucher_value, expiry_date)
    logo = _load_logo()

    overlay = Image.new('RGBA', base.size, (255, 255, 255, 0))
    measure_draw = ImageDraw.Draw(overlay)

    panel_width = int(width * 0.88)
    panel_x = (width - panel_width) // 2
    panel_padding = max(int(panel_width * 0.07), 24)
    content_width = panel_width - (panel_padding * 2)
    center_x = panel_x + panel_width // 2

    panel_height, fonts, blocks, logo_width = _measure_layout(
        measure_draw, fields, width, panel_width, panel_padding, content_width, logo,
    )
    max_panel_height = int(height * 0.97)
    if panel_height > max_panel_height:
        scale = max_panel_height / panel_height
        panel_height, fonts, blocks, logo_width = _measure_layout(
            measure_draw, fields, width, panel_width, panel_padding, content_width, logo,
            scale=scale,
        )
    panel_y = max(int(height * 0.015), (height - panel_height) // 2)

    draw = ImageDraw.Draw(overlay)
    draw.rounded_rectangle(
        [panel_x, panel_y, panel_x + panel_width, panel_y + panel_height],
        radius=max(int(width * 0.02), 12),
        fill=(255, 255, 255, 165),
        outline=(220, 220, 220, 255),
        width=max(int(width * 0.002), 2),
    )

    title_color = _parse_color(design.recipient_color, (80, 80, 80))
    amount_color = _parse_color(design.value_color, (20, 20, 20))
    message_color = _parse_color(design.message_color, (45, 45, 45))
    label_color = _parse_color(design.recipient_color, (70, 70, 70))
    code_color = _parse_color(design.code_color, (15, 15, 15))
    detail_color = _parse_color(design.expiry_color, (60, 60, 60))
    muted_color = (100, 100, 100)

    y = panel_y + panel_padding
    y = _paste_logo(overlay, logo, center_x, y, max_width=logo_width)
    gap = lambda fraction: max(int(width * fraction), 4)
    y += gap(0.018)

    y = _draw_centered_line(
        draw, fields['title'], center_x, y, fonts['title'], title_color,
    )
    y += int(width * 0.012)
    y = _draw_centered_line(
        draw, fields['value'], center_x, y, fonts['amount'], amount_color,
    )
    y += int(width * 0.02)

    if fields['recipient']:
        y = _draw_centered_line(
            draw, f"To: {fields['recipient']}", center_x, y, fonts['label'], label_color,
        )
        y += int(width * 0.008)

    if blocks['message_lines']:
        y = _draw_centered_block(
            draw, blocks['message_lines'], center_x, y, fonts['message'], message_color,
        )
        y += int(width * 0.015)

    divider_y = y + int(width * 0.008)
    draw.line(
        [
            (panel_x + panel_padding, divider_y),
            (panel_x + panel_width - panel_padding, divider_y),
        ],
        fill=(210, 210, 210, 255),
        width=max(int(width * 0.0015), 1),
    )
    y = divider_y + int(width * 0.025)

    if fields['purchaser']:
        y = _draw_centered_line(
            draw, f"From: {fields['purchaser']}", center_x, y, fonts['detail'], detail_color,
        )

    y = _draw_centered_line(
        draw, 'Voucher code', center_x, y, fonts['label'], label_color,
    )
    y = _draw_centered_line(
        draw, fields['code'], center_x, y, fonts['code'], code_color,
    )
    y += int(width * 0.01)

    if fields['expiry']:
        y = _draw_centered_line(
            draw, f"Expiry date: {fields['expiry']}", center_x, y, fonts['detail'], detail_color,
        )

    y = _draw_centered_block(
        draw, blocks['validity_lines'], center_x, y, fonts['small'], muted_color,
    )
    _draw_centered_block(
        draw, blocks['redeem_lines'], center_x, y, fonts['small'], muted_color,
    )

    result = Image.alpha_composite(base, overlay).convert('RGB')
    buffer = io.BytesIO()
    result.save(buffer, format='PNG', optimize=True)
    return buffer.getvalue()


def shrink_png_bytes(png_bytes, max_width=1200):
    """Return a smaller PNG for in-browser preview."""
    with Image.open(io.BytesIO(png_bytes)) as image:
        if image.width <= max_width:
            return png_bytes
        ratio = max_width / image.width
        resized = image.resize(
            (max_width, max(int(image.height * ratio), 1)),
            Image.Resampling.LANCZOS,
        )
        buffer = io.BytesIO()
        resized.save(buffer, format='PNG', optimize=True)
        return buffer.getvalue()
