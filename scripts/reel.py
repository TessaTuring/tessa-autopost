"""Turn a day's carousel slides into a vertical Reel (1080x1920, MP4, silent audio track).

Usage: python scripts/reel.py YYYY-MM-DD      -> writes drafts/<date>/reel.mp4
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

from common import DRAFTS, ROOT

W, H = 1080, 1920
PAPER = (252, 250, 248)
ROSE = (190, 84, 110)
MUTED = (150, 140, 132)
FONTS = ROOT / "assets" / "fonts"
COVER_SECONDS, SLIDE_SECONDS, LAST_SECONDS = 3, 5, 4


def frame(slide: Path, top: str, bottom: str) -> Image.Image:
    img = Image.new("RGB", (W, H), PAPER)
    s = Image.open(slide).convert("RGB")
    s = s.resize((W, round(W * s.height / s.width)), Image.LANCZOS)
    y = (H - s.height) // 2
    img.paste(s, (0, y))
    d = ImageDraw.Draw(img)
    f_top = ImageFont.truetype(str(FONTS / "Poppins-SemiBold.ttf"), 40)
    f_bot = ImageFont.truetype(str(FONTS / "Poppins-Bold.ttf"), 46)
    if top:
        d.text(((W - d.textlength(top, font=f_top)) / 2, y / 2 - 26), top, font=f_top, fill=MUTED)
    d.text(((W - d.textlength(bottom, font=f_bot)) / 2, y + s.height + (H - y - s.height) / 2 - 30),
           bottom, font=f_bot, fill=ROSE)
    return img


def make_reel(day: str) -> Path:
    folder = DRAFTS / day
    post = json.loads((folder / "post.json").read_text())
    slides = [ROOT / p for p in post["images"]]
    out = folder / "reel.mp4"
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        lines = []
        for i, path in enumerate(slides):
            bottom = "Save this for later" if i < len(slides) - 1 else "Follow for more"
            f = tmp / f"f{i:02d}.png"
            frame(path, "", bottom).save(f)
            secs = COVER_SECONDS if i == 0 else LAST_SECONDS if i == len(slides) - 1 else SLIDE_SECONDS
            lines += [f"file '{f.as_posix()}'", f"duration {secs}"]
        lines.append(f"file '{(tmp / f'f{len(slides) - 1:02d}.png').as_posix()}'")  # concat needs the last frame twice
        (tmp / "list.txt").write_text("\n".join(lines) + "\n")
        subprocess.run(
            [imageio_ffmpeg.get_ffmpeg_exe(), "-y", "-loglevel", "error",
             "-f", "concat", "-safe", "0", "-i", str(tmp / "list.txt"),
             "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
             "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium", "-crf", "21",
             "-c:a", "aac", "-b:a", "128k", "-shortest", "-movflags", "+faststart", str(out)],
            check=True,
        )
    return out


if __name__ == "__main__":
    print(make_reel(sys.argv[1]))
