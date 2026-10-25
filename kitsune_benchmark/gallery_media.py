"""Deterministic multimodal media for the gallery track. No model calls.

Answers exist only in pixels or audio: callers must never put them in HTML,
URLs, file names or alt text. Images use Pillow; video/audio encoding uses
ffmpeg (libvpx/libopus) and speech uses espeak. Missing tools raise
MediaUnavailable so callers can skip media tasks explicitly.
"""
from __future__ import annotations

from io import BytesIO
import math
import random
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

# Unambiguous glyphs only (no 0/O, 1/I/L, 2/Z, 5/S, 8/B).
CODE_ALPHABET = "ACDEFHJKMNPRTUVWXY34679"
FONT_CANDIDATES = (
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Supplemental/Verdana Bold.ttf",
    "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
)
KOREAN_FONTS = ("/System/Library/Fonts/AppleSDGothicNeo.ttc", "/System/Library/Fonts/Supplemental/AppleGothic.ttf")


class MediaUnavailable(RuntimeError):
    pass


def font(size: int, korean: bool = False, index: int = 0) -> ImageFont.FreeTypeFont:
    candidates = [p for p in ((KOREAN_FONTS if korean else ()) + FONT_CANDIDATES) if Path(p).is_file()]
    if candidates:
        return ImageFont.truetype(candidates[index % len(candidates)], size)
    return ImageFont.load_default(size=size)


def png(image: Image.Image) -> bytes:
    out = BytesIO()
    image.save(out, format="PNG", optimize=True)
    return out.getvalue()


def random_code(rng: random.Random, length: int = 6) -> str:
    return "".join(rng.choice(CODE_ALPHABET) for _ in range(length))


def distorted_code(code: str, seed: int, size: tuple[int, int] = (420, 140)) -> bytes:
    """CAPTCHA-style text: per-glyph rotation/scale/colour, wave warp, clutter lines and noise."""
    rng = random.Random(seed)
    width, height = size
    bg = (rng.randint(215, 240), rng.randint(210, 235), rng.randint(200, 230))
    canvas = Image.new("RGB", size, bg)
    draw = ImageDraw.Draw(canvas)
    for _ in range(160):  # background speckle
        x, y = rng.randrange(width), rng.randrange(height)
        draw.ellipse((x, y, x + rng.randint(1, 4), y + rng.randint(1, 4)),
                     fill=tuple(c - rng.randint(20, 70) for c in bg))
    x = 22
    for index, char in enumerate(code):
        glyph_font = font(rng.randint(56, 74), index=rng.randrange(3))
        glyph = Image.new("RGBA", (100, 110), (0, 0, 0, 0))
        ImageDraw.Draw(glyph).text((14, 4), char, font=glyph_font,
                                   fill=(rng.randint(20, 110), rng.randint(20, 90), rng.randint(40, 120), 255))
        glyph = glyph.rotate(rng.uniform(-28, 28), resample=Image.BICUBIC, expand=False)
        canvas.paste(glyph, (x, rng.randint(2, 26)), glyph)
        x += rng.randint(54, 64)
    # Sinusoidal warp: shift each column vertically and each row horizontally.
    amp_y, freq_y, phase = rng.uniform(5, 9), rng.uniform(0.018, 0.03), rng.uniform(0, math.pi)
    warped = Image.new("RGB", size, bg)
    for column in range(width):
        offset = int(amp_y * math.sin(freq_y * column + phase))
        warped.paste(canvas.crop((column, 0, column + 1, height)), (column, offset))
    rows = Image.new("RGB", size, bg)
    amp_x, freq_x = rng.uniform(2, 5), rng.uniform(0.05, 0.09)
    for row in range(height):
        rows.paste(warped.crop((0, row, width, row + 1)), (int(amp_x * math.sin(freq_x * row)), row))
    draw = ImageDraw.Draw(rows)
    for _ in range(4):  # strike-through clutter
        points = [(px, rng.randint(15, height - 15)) for px in range(0, width + 60, 60)]
        draw.line(points, fill=(rng.randint(30, 120), rng.randint(30, 120), rng.randint(30, 120)), width=rng.randint(2, 3))
    for _ in range(900):
        x, y = rng.randrange(width), rng.randrange(height)
        rows.putpixel((x, y), tuple(rng.randint(0, 255) for _ in range(3)))
    return png(rows.filter(ImageFilter.GaussianBlur(0.6)))


def product_label(product: str, fields: list[tuple[str, str]], seed: int, size: tuple[int, int] = (480, 300)) -> bytes:
    """Photo of a printed product label: clean text fields and a decorative barcode, slightly rotated."""
    rng = random.Random(seed)
    width, height = size
    bg = (rng.randint(150, 180), rng.randint(130, 160), rng.randint(105, 135))  # cardboard
    label = Image.new("RGB", (380, 230), (250, 250, 246))
    draw = ImageDraw.Draw(label)
    draw.rectangle((0, 0, 379, 229), outline=(40, 40, 40), width=3)
    draw.text((18, 12), product, font=font(24), fill=(20, 20, 20))
    for row, (name, value) in enumerate(fields):
        draw.text((18, 50 + 28 * row), f"{name}: {value}", font=font(19), fill=(25, 25, 25))
    x = 18
    while x < 300:  # barcode stripes encode nothing
        bar = rng.randint(1, 4)
        draw.rectangle((x, 172, x + bar - 1, 214), fill=(15, 15, 15))
        x += bar + rng.randint(1, 4)
    label = label.rotate(rng.uniform(-3, 3), resample=Image.BICUBIC, expand=True, fillcolor=bg)
    photo = Image.new("RGB", size, bg)
    photo.paste(label, ((width - label.width) // 2, (height - label.height) // 2))
    return png(photo)


SHAPES = ("triangle", "circle", "square", "diamond")


def shape_tile(shape: str, seed: int, size: int = 120) -> bytes:
    """One grid tile: a noisy, rotated outline/filled shape among clutter."""
    rng = random.Random(seed)
    bg = (rng.randint(170, 235), rng.randint(170, 235), rng.randint(170, 235))
    tile = Image.new("RGB", (size, size), bg)
    draw = ImageDraw.Draw(tile)
    for _ in range(rng.randint(6, 10)):  # clutter strokes and blobs
        a = (rng.randrange(size), rng.randrange(size)); b = (rng.randrange(size), rng.randrange(size))
        draw.line((a, b), fill=tuple(rng.randint(90, 200) for _ in range(3)), width=rng.randint(1, 3))
    color = tuple(rng.randint(20, 140) for _ in range(3))
    cx, cy, r = size / 2 + rng.uniform(-14, 14), size / 2 + rng.uniform(-14, 14), rng.uniform(26, 38)
    angle = rng.uniform(0, 2 * math.pi)
    def poly(n, start):
        return [(cx + r * math.cos(start + 2 * math.pi * k / n), cy + r * math.sin(start + 2 * math.pi * k / n)) for k in range(n)]
    filled = rng.random() < 0.5
    if shape == "circle":
        box = (cx - r, cy - r * rng.uniform(0.85, 1.0), cx + r, cy + r * rng.uniform(0.85, 1.0))
        draw.ellipse(box, fill=color if filled else None, outline=color, width=4)
    elif shape == "triangle":
        draw.polygon(poly(3, angle), fill=color if filled else None, outline=color, width=4)
    elif shape == "square":
        draw.polygon(poly(4, angle), fill=color if filled else None, outline=color, width=4)
    elif shape == "diamond":
        pts = poly(4, angle)
        pts = [(cx + (x - cx) * 0.6, y) for x, y in pts]  # squashed rhombus, not a square
        draw.polygon(pts, fill=color if filled else None, outline=color, width=4)
    else:
        raise ValueError(shape)
    for _ in range(500):
        tile.putpixel((rng.randrange(size), rng.randrange(size)), tuple(rng.randint(0, 255) for _ in range(3)))
    return png(tile.filter(ImageFilter.GaussianBlur(0.5)))


def bar_chart(labels: list[str], values: list[int], seed: int, size: tuple[int, int] = (560, 320)) -> bytes:
    """Unlabelled-value bar chart: month labels and axis ticks drawn in pixels only."""
    rng = random.Random(seed)
    width, height = size
    chart = Image.new("RGB", size, (250, 250, 252))
    draw = ImageDraw.Draw(chart)
    left, bottom, top = 56, height - 46, 24
    peak = max(values) * 1.15
    tick_font = font(13)
    for k in range(6):
        value = peak * k / 5
        y = bottom - (bottom - top) * k / 5
        draw.line((left, y, width - 16, y), fill=(225, 225, 232), width=1)
        draw.text((8, y - 8), f"{value:,.0f}", font=tick_font, fill=(110, 110, 120))
    slot = (width - left - 24) / len(values)
    label_font = font(16, korean=True)
    for index, (label, value) in enumerate(zip(labels, values)):
        x0 = left + slot * index + slot * 0.18
        x1 = x0 + slot * 0.64
        y = bottom - (bottom - top) * value / peak
        shade = rng.randint(70, 110)
        draw.rectangle((x0, y, x1, bottom), fill=(shade, 120 + rng.randint(-15, 15), 190))
        draw.text((x0 + 6, bottom + 10), label, font=label_font, fill=(60, 60, 70))
    draw.line((left, bottom, width - 16, bottom), fill=(90, 90, 100), width=2)
    return png(chart)


def _require(*tools: str) -> None:
    missing = [tool for tool in tools if shutil.which(tool) is None]
    if missing:
        raise MediaUnavailable("Missing media tools: " + ", ".join(missing))


def color_video(segments: list[tuple[tuple[int, int, int], str]], seed: int, seconds_each: float = 1.6,
                fps: int = 10, size: tuple[int, int] = (320, 180)) -> bytes:
    """WebM (VP8): consecutive coloured screens, each showing a large number."""
    _require("ffmpeg")
    rng = random.Random(seed)
    number_font = font(84)
    frames = []
    for color, number in segments:
        for frame in range(int(seconds_each * fps)):
            image = Image.new("RGB", size, color)
            draw = ImageDraw.Draw(image)
            jitter = rng.randint(-3, 3)
            draw.text((size[0] / 2 - 52 + jitter, size[1] / 2 - 52), number, font=number_font, fill=(255, 255, 255))
            draw.rectangle((0, size[1] - 6, int(size[0] * (frame + 1) / (seconds_each * fps)), size[1]), fill=(30, 30, 30))
            frames.append(png(image))
    with tempfile.TemporaryDirectory(prefix="bmb-media-") as folder:
        out = Path(folder) / "video.webm"
        process = subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "image2pipe", "-framerate", str(fps),
             "-i", "-", "-c:v", "libvpx", "-b:v", "300k", "-pix_fmt", "yuv420p", "-an", str(out)],
            input=b"".join(frames), capture_output=True, timeout=120)
        if process.returncode or not out.is_file():
            raise MediaUnavailable("ffmpeg could not encode the video.")
        return out.read_bytes()


def spoken_digits(digits: str, seed: int) -> bytes:
    """WebM (Opus): espeak digits with pauses, mixed with pink noise."""
    _require("ffmpeg", "espeak")
    rng = random.Random(seed)
    with tempfile.TemporaryDirectory(prefix="bmb-media-") as folder:
        speech, out = Path(folder) / "speech.wav", Path(folder) / "audio.webm"
        text = ", ".join(digits)
        steps = [["espeak", "-v", "en", "-s", str(rng.randint(105, 125)), "-p", str(rng.randint(35, 60)), text, "-w", str(speech)],
                 ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(speech), "-f", "lavfi", "-t", "12",
                  "-i", f"anoisesrc=color=pink:amplitude={rng.uniform(0.05, 0.09):.3f}:seed={seed % 100000}",
                  "-filter_complex", "[0:a][1:a]amix=inputs=2:duration=first:normalize=0", "-c:a", "libopus", "-b:a", "32k", str(out)]]
        for argv in steps:
            result = subprocess.run(argv, capture_output=True, timeout=60)
            if result.returncode:
                raise MediaUnavailable(f"{argv[0]} failed while generating audio.")
        return out.read_bytes()
