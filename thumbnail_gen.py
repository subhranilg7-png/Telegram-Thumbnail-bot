"""
Composites the final thumbnail image, matching the reference templates.

Two layout modes, chosen automatically:
  - WITH season text: full blurred/darkened background panel on the left,
    title, "SEASON X" line, "SYNOPSIS" heading, wrapped synopsis.
  - WITHOUT season text: lightly darkened background with a rounded gray
    "chip" panel sized to hug just the title+synopsis block.

Right side (both modes): full-bleed poster image, circular scene inset with
white ring border, bottom-right repeated title (+season), bottom-left
watermark tag box.
"""

import os
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance, ImageFont

CANVAS_W, CANVAS_H = 1280, 720
LEFT_W = 853
RIGHT_X = LEFT_W
CIRCLE_DIAMETER = 420
CIRCLE_CENTER = (LEFT_W, CANVAS_H // 2 + 10)
MARGIN_X = 36

ACCENT_COLOR = (77, 217, 232)
WHITE = (255, 255, 255)
SHADOW = (0, 0, 0)
CHIP_FILL = (60, 60, 60, 130)

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
FONT_EXTRABOLD = os.path.join(FONT_DIR, "Poppins-ExtraBold.ttf")
FONT_BOLD = os.path.join(FONT_DIR, "Poppins-Bold.ttf")
FONT_SEMIBOLD = os.path.join(FONT_DIR, "Poppins-SemiBold.ttf")


def _font(path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(path, size)
    except OSError:
        return ImageFont.load_default()


# --------------------------------------------------------------- imaging ---
def fit_and_crop(img: Image.Image, target_w: int, target_h: int) -> Image.Image:
    img = img.convert("RGB")
    src_w, src_h = img.size
    scale = max(target_w / src_w, target_h / src_h)
    new_w, new_h = round(src_w * scale), round(src_h * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top = (new_h - target_h) // 2
    return img.crop((left, top, left + target_w, top + target_h))


def blurred_background(img: Image.Image, w: int, h: int, blur_radius: int = 14, darken: float = 0.45) -> Image.Image:
    bg = fit_and_crop(img, w, h)
    bg = bg.filter(ImageFilter.GaussianBlur(blur_radius))
    bg = ImageEnhance.Brightness(bg).enhance(darken)
    bg = ImageEnhance.Contrast(bg).enhance(1.05)
    return bg


def light_background(img: Image.Image, w: int, h: int, blur_radius: int = 4, darken: float = 0.7) -> Image.Image:
    """Softer treatment used behind the chip panel (no-season mode)."""
    bg = fit_and_crop(img, w, h)
    bg = bg.filter(ImageFilter.GaussianBlur(blur_radius))
    bg = ImageEnhance.Brightness(bg).enhance(darken)
    return bg


def circular_crop(img: Image.Image, diameter: int) -> Image.Image:
    img = fit_and_crop(img, diameter, diameter)
    mask = Image.new("L", (diameter, diameter), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, diameter, diameter), fill=255)
    out = Image.new("RGBA", (diameter, diameter), (0, 0, 0, 0))
    out.paste(img, (0, 0), mask)
    return out


# ------------------------------------------------------------------ text ---
def draw_text_shadow(draw, xy, text, font, fill=WHITE, shadow=SHADOW, offset=2, anchor=None):
    x, y = xy
    draw.text((x + offset, y + offset), text, font=font, fill=shadow, anchor=anchor)
    draw.text((x, y), text, font=font, fill=fill, anchor=anchor)


def draw_letterspaced(draw, xy, text, font, fill, spacing=6, anchor_center_x=None, shadow=None):
    widths = [draw.textlength(ch, font=font) for ch in text]
    total_w = sum(widths) + spacing * (len(text) - 1)
    x, y = xy
    if anchor_center_x is not None:
        x = anchor_center_x - total_w / 2
    for ch, w in zip(text, widths):
        if shadow:
            draw.text((x + 2, y + 2), ch, font=font, fill=shadow)
        draw.text((x, y), ch, font=font, fill=fill)
        x += w + spacing
    return total_w


def wrap_text(draw, text: str, font, max_width: int, max_lines: int) -> list[str]:
    words = text.split()
    lines, current = [], ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines:
        words_used = sum(len(l.split()) for l in lines)
        if words_used < len(words):
            last = lines[-1]
            while draw.textlength(last + "...", font=font) > max_width and " " in last:
                last = last.rsplit(" ", 1)[0]
            lines[-1] = last + "..."
    return lines


def fit_title(draw, text: str, max_width: int, font_path: str,
              start_size: int = 48, min_size: int = 26, max_lines: int = 2):
    """Shrink font size until the title wraps into <= max_lines at max_width."""
    for size in range(start_size, min_size - 1, -2):
        font = _font(font_path, size)
        lines = wrap_text(draw, text, font, max_width, max_lines)
        # Accept if every word made it onto a line without excessive truncation
        rejoined_words = sum(len(l.rstrip(".").split()) for l in lines)
        if rejoined_words >= len(text.split()) or size == min_size:
            return font, lines, size
    font = _font(font_path, min_size)
    return font, wrap_text(draw, text, font, max_width, max_lines), min_size


def draw_dot_grid(draw, top_left, rows, cols, spacing=22, radius=2, color=(255, 255, 255, 160)):
    x0, y0 = top_left
    for r in range(rows):
        for c in range(cols):
            cx, cy = x0 + c * spacing, y0 + r * spacing
            draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)


def rounded_rect(draw, box, radius, fill):
    draw.rounded_rectangle(box, radius=radius, fill=fill)


# --------------------------------------------------------------- render ---
def generate_thumbnail(
    title: str,
    synopsis: str,
    watermark: str,
    background_img: Image.Image,
    poster_img: Image.Image,
    circle_img: Image.Image,
    season_text: str | None = None,
) -> Image.Image:
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H))
    has_season = bool(season_text and season_text.strip())

    # --- Right poster (full bleed) ---
    poster = fit_and_crop(poster_img, CANVAS_W - RIGHT_X, CANVAS_H)
    canvas.paste(poster, (RIGHT_X, 0))

    # --- Left background ---
    if has_season:
        bg = blurred_background(background_img, LEFT_W, CANVAS_H)
    else:
        bg = light_background(background_img, LEFT_W, CANVAS_H)
    canvas.paste(bg, (0, 0))

    draw = ImageDraw.Draw(canvas, "RGBA")
    max_text_width = LEFT_W - (MARGIN_X * 2) - 40

    # --- Title (auto-wrap + auto-shrink) ---
    title_font, title_lines, title_size = fit_title(
        draw, title, max_text_width, FONT_EXTRABOLD, start_size=46, min_size=28, max_lines=2
    )
    title_line_h = int(title_size * 1.18)

    # --- Pre-measure synopsis body (fixed size) to know total content height ---
    body_font = _font(FONT_BOLD, 20)
    body_lines = wrap_text(draw, synopsis, body_font, max_text_width, max_lines=9)
    body_line_h = 30

    season_font = _font(FONT_SEMIBOLD, 24)
    heading_font = _font(FONT_SEMIBOLD, 22)

    top_y = 56
    content_top = top_y

    # --- Chip background (no-season mode): draw before text, sized to content ---
    if not has_season:
        est_height = (
            len(title_lines) * title_line_h + 14
            + 26  # SYNOPSIS heading
            + len(body_lines) * body_line_h + 40
        )
        chip_box = (18, top_y - 20, LEFT_W - 30, top_y - 20 + est_height)
        rounded_rect(draw, chip_box, radius=34, fill=CHIP_FILL)

    # --- Draw title lines ---
    y = top_y
    for line in title_lines:
        draw_text_shadow(draw, (MARGIN_X, y), line, title_font, offset=2)
        y += title_line_h

    # --- Season line (left-aligned under title, condensed/letter-spaced) ---
    if has_season:
        draw_letterspaced(draw, (MARGIN_X, y + 4), season_text.upper(), season_font,
                           WHITE, spacing=5, shadow=SHADOW)
        y += 40

    y += 14

    # --- SYNOPSIS heading (centered) ---
    draw_letterspaced(draw, (0, y), "SYNOPSIS", heading_font, ACCENT_COLOR,
                       spacing=8, anchor_center_x=LEFT_W // 2)
    y += 46

    # --- Synopsis body (centered lines) ---
    for line in body_lines:
        w = draw.textlength(line, font=body_font)
        x = (LEFT_W - w) / 2
        draw_text_shadow(draw, (x, y), line, body_font, offset=1)
        y += body_line_h

    # --- Decorative dot grids ---
    draw_dot_grid(draw, (LEFT_W - 420, 20), rows=2, cols=17, spacing=22)
    draw_dot_grid(draw, (30, 664), rows=2, cols=17, spacing=22)

    # --- Circular inset image with white ring ---
    ring_r = CIRCLE_DIAMETER // 2 + 8
    cx, cy = CIRCLE_CENTER
    draw.ellipse((cx - ring_r, cy - ring_r, cx + ring_r, cy + ring_r), fill=(255, 255, 255, 255))
    circle = circular_crop(circle_img, CIRCLE_DIAMETER)
    canvas.paste(circle, (cx - CIRCLE_DIAMETER // 2, cy - CIRCLE_DIAMETER // 2), circle)

    draw = ImageDraw.Draw(canvas, "RGBA")

    # --- Bottom-left watermark tag box ---
    tag_font = _font(FONT_BOLD, 26)
    tag_w = draw.textlength(watermark, font=tag_font) + 50
    draw.rectangle((0, CANVAS_H - 60, tag_w, CANVAS_H), fill=ACCENT_COLOR)
    draw.text((25, CANVAS_H - 48), watermark, font=tag_font, fill=(20, 20, 20))

    # --- Bottom-right repeated title (+season), right-aligned, wrap/shrink ---
    br_max_width = CANVAS_W - RIGHT_X - 60
    br_font, br_lines, br_size = fit_title(
        draw, title, br_max_width, FONT_EXTRABOLD, start_size=30, min_size=18, max_lines=2
    )
    br_line_h = int(br_size * 1.2)
    total_br_h = len(br_lines) * br_line_h + (24 if has_season else 0)
    y = CANVAS_H - 24 - total_br_h
    for line in br_lines:
        w = draw.textlength(line, font=br_font)
        draw_text_shadow(draw, (CANVAS_W - w - 30, y), line, br_font, offset=2)
        y += br_line_h
    if has_season:
        br_season_font = _font(FONT_SEMIBOLD, 16)
        sw = draw.textlength(season_text.upper(), font=br_season_font) + 5 * (len(season_text) - 1)
        draw_letterspaced(draw, (CANVAS_W - sw - 30, y), season_text.upper(), br_season_font,
                           WHITE, spacing=5, shadow=SHADOW)

    return canvas
