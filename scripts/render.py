"""Render a carousel (list of slide dicts) into 1080x1350 JPEGs with Pillow.

Slide types:
  cover  - full-bleed Tessa photo, dark gradient, big white title + amber subtitle
  text   - cream card: optional kicker, title, body
  prompt - cream card: kicker, title, white "COPY THIS PROMPT" card
  cta    - cream card: title, body, "Link in bio" footer
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "assets" / "fonts"

W, H, M = 1080, 1350, 88
CREAM = (251, 249, 247)
INK = (43, 36, 32)
INK_SOFT = (70, 62, 57)
MUTED = (150, 140, 132)
AMBER = (190, 84, 110)
WARM_YELLOW = (255, 220, 158)
WHITE = (255, 255, 255)
HANDLE = "@tessa_turing"


def font(weight: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONTS / f"Poppins-{weight}.ttf"), size)


def wrap(text: str, f: ImageFont.FreeTypeFont, width: int) -> list[str]:
    """Greedy word wrap that also respects explicit newlines."""
    lines: list[str] = []
    for para in text.split("\n"):
        words = para.split(" ")
        if para.strip() == "":
            lines.append("")
            continue
        cur = ""
        for w in words:
            trial = w if not cur else f"{cur} {w}"
            if f.getlength(trial) <= width:
                cur = trial
            else:
                if cur:
                    lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def block_height(lines: list[str], f: ImageFont.FreeTypeFont, spacing: float) -> int:
    line_h = int(f.size * spacing)
    return line_h * len(lines)


def draw_lines(d: ImageDraw.ImageDraw, lines, f, color, x, y, spacing, align="left", width=None) -> int:
    line_h = int(f.size * spacing)
    for ln in lines:
        lx = x
        if align == "right" and width:
            lx = x + width - f.getlength(ln)
        d.text((lx, y), ln, font=f, fill=color)
        y += line_h
    return y


BLUSH = (247, 222, 226)
SAGE = (214, 228, 216)
SKY = (220, 232, 246)
ROSE = (190, 84, 110)
PAPER = (252, 250, 248)


def graphic_cover(slide: dict, page: str) -> Image.Image:
    """Bright text-only cover: soft color shapes, a label pill, a big title."""
    img = Image.new("RGB", (W, H), PAPER)
    d = ImageDraw.Draw(img)
    d.ellipse((W - 520, -260, W + 260, 520), fill=BLUSH)
    d.ellipse((-300, H - 560, 420, H + 160), fill=SAGE)
    d.ellipse((W - 260, H - 420, W + 120, H - 40), fill=SKY)

    small = font("SemiBold", 28)
    d.text((M, 70), HANDLE, font=small, fill=MUTED)
    d.text((W - M - small.getlength(page), 70), page, font=small, fill=MUTED)

    tw = W - 2 * M
    label = (slide.get("kicker") or "AI shortcut").upper()
    lf = font("Bold", 30)
    while lf.getlength(label) > tw - 64 and lf.size > 20:
        lf = font("Bold", lf.size - 2)
    tf, sf = font("ExtraBold", 92), font("SemiBold", 44)
    t_lines = wrap(slide["title"], tf, tw)
    while len(t_lines) > 4 and tf.size > 64:
        tf = font("ExtraBold", tf.size - 6)
        t_lines = wrap(slide["title"], tf, tw)
    s_lines = wrap(slide.get("subtitle", ""), sf, tw) if slide.get("subtitle") else []
    pill_h = lf.size + 36
    total = pill_h + 44 + block_height(t_lines, tf, 1.08) + (28 + block_height(s_lines, sf, 1.3) if s_lines else 0)
    y = (H - total) // 2
    d.rounded_rectangle((M, y, M + lf.getlength(label) + 64, y + pill_h), radius=pill_h // 2, fill=INK)
    d.text((M + 32, y + 16), label, font=lf, fill=WHITE)
    y += pill_h + 44
    y = draw_lines(d, t_lines, tf, INK, M, y, 1.08)
    if s_lines:
        draw_lines(d, s_lines, sf, ROSE, M, y + 28, 1.3)
    sw = font("SemiBold", 30)
    d.text((W - M - sw.getlength("swipe  >"), H - 120), "swipe  >", font=sw, fill=INK_SOFT)
    return img


def cover(slide: dict, page: str) -> Image.Image:
    if not slide.get("photo"):
        return graphic_cover(slide, page)
    photo = Image.open(ROOT / slide["photo"]).convert("RGB")
    scale = max(W / photo.width, H / photo.height)
    photo = photo.resize((round(photo.width * scale), round(photo.height * scale)), Image.LANCZOS)
    left = (photo.width - W) // 2
    top = int((photo.height - H) * 0.2)
    img = photo.crop((left, top, left + W, top + H))

    # Bottom gradient for legibility.
    grad = Image.new("L", (1, H), 0)
    start = int(H * 0.45)
    for y in range(H):
        a = 0 if y < start else int(215 * ((y - start) / (H - start)) ** 1.1)
        grad.putpixel((0, y), a)
    shade = Image.new("RGB", (W, H), (0, 0, 0))
    img = Image.composite(shade, img, grad.resize((W, H)))

    d = ImageDraw.Draw(img)
    tw = W - 2 * M
    tf, sf = font("ExtraBold", 76), font("SemiBold", 40)
    t_lines = wrap(slide["title"], tf, tw)
    s_lines = wrap(slide.get("subtitle", ""), sf, tw) if slide.get("subtitle") else []
    th = block_height(t_lines, tf, 1.12)
    sh = block_height(s_lines, sf, 1.3)
    y = H - 140 - th - (sh + 18 if s_lines else 0)
    y = draw_lines(d, t_lines, tf, WHITE, M, y, 1.12) + 18
    if s_lines:
        draw_lines(d, s_lines, sf, (255, 214, 224), M, y, 1.3)
    small = font("SemiBold", 28)
    d.text((M, H - 90), HANDLE, font=small, fill=(235, 230, 225))
    d.text((W - M - small.getlength(page), H - 90), page, font=small, fill=(235, 230, 225))
    return img


def card_slide(slide: dict, page: str) -> Image.Image:
    img = Image.new("RGB", (W, H), CREAM)
    d = ImageDraw.Draw(img)
    tw = W - 2 * M
    small = font("SemiBold", 28)
    d.text((M, 70), HANDLE, font=small, fill=MUTED)
    d.text((W - M - small.getlength(page), 70), page, font=small, fill=MUTED)

    kind = slide["type"]
    pad, label_h = 52, 58
    kf = font("Bold", 30)
    title_size = 72 if kind == "cta" else (58 if kind == "prompt" else 66)
    tf = font("Bold", title_size)
    bf = font("Medium", 42)
    pf = font("Medium", 38)

    blocks = []  # (kind, lines, font, color, spacing, gap_after)
    if slide.get("kicker"):
        blocks.append(("kicker", wrap(slide["kicker"].upper(), kf, tw), kf, AMBER, 1.3, 22))
    if slide.get("title"):
        blocks.append(("title", wrap(slide["title"], tf, tw), tf, INK, 1.18, 30))
    if slide.get("body"):
        blocks.append(("body", wrap(slide["body"], bf, tw), bf, INK_SOFT, 1.55, 30))
    if kind == "prompt" and slide.get("prompt"):
        blocks.append(("card", wrap(slide["prompt"], pf, tw - 2 * pad), pf, INK, 1.55, 0))

    def h_of(b):
        h = block_height(b[1], b[2], b[4])
        return h + 2 * pad + label_h if b[0] == "card" else h

    total = sum(h_of(b) for b in blocks) + sum(b[5] for b in blocks[:-1])
    y = max(180, 150 + (H - 300 - total) // 2)
    if blocks and blocks[0][0] == "kicker":
        d.rounded_rectangle((M, y - 34, M + 72, y - 26), radius=4, fill=AMBER)

    for b in blocks:
        if b[0] == "card":
            ch = h_of(b)
            d.rounded_rectangle((M, y + 8, M + tw, y + ch + 8), radius=34, fill=(244, 222, 228))
            d.rounded_rectangle((M, y, M + tw, y + ch), radius=34, fill=WHITE)
            d.text((M + pad, y + pad - 6), "COPY THIS PROMPT", font=font("Bold", 26), fill=AMBER)
            draw_lines(d, b[1], b[2], b[3], M + pad, y + pad + label_h, b[4])
            y += ch + b[5]
        else:
            y = draw_lines(d, b[1], b[2], b[3], M, y, b[4]) + b[5]

    if kind == "cta":
        d.text((M, H - 150), "Link in bio", font=font("Bold", 36), fill=AMBER)
    else:
        sw = font("SemiBold", 30)
        label = "swipe  >"
        d.text((W - M - sw.getlength(label), H - 120), label, font=sw, fill=MUTED)
    return img


def render(slides: list[dict], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    n = len(slides)
    for i, s in enumerate(slides, 1):
        page = f"{i}/{n}"
        img = cover(s, page) if s["type"] == "cover" else card_slide(s, page)
        p = out_dir / f"{i:02d}.jpg"
        img.save(p, "JPEG", quality=92, optimize=True)
        paths.append(p)
    return paths


if __name__ == "__main__":
    import json

    post = json.loads(Path(sys.argv[1]).read_text())
    for p in render(post["slides"], Path(sys.argv[2])):
        print(p)
