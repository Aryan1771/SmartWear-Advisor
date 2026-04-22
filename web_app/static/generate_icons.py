# web_app/static/generate_icons.py
# Run this ONCE locally to generate the PWA icon files.
# Requires Pillow: pip install Pillow
#
# Usage:
#   cd web_app/static
#   python generate_icons.py
#
# Produces:
#   icons/icon-192.png
#   icons/icon-512.png

from pathlib import Path
try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    raise SystemExit("Install Pillow first:  pip install Pillow")

ICONS_DIR = Path(__file__).parent / "icons"
ICONS_DIR.mkdir(exist_ok=True)

BG_COLOR   = (35, 134, 54)    # matches --bg-accent (#238636)
TEXT_COLOR = (255, 255, 255)

def make_icon(size: int):
    img  = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Rounded-rect background
    radius = size // 5
    draw.rounded_rectangle([(0, 0), (size - 1, size - 1)],
                            radius=radius, fill=BG_COLOR)

    # Eye emoji / simple eye shape as icon
    cx, cy = size // 2, size // 2

    # Outer eye ellipse
    ew, eh = int(size * 0.62), int(size * 0.38)
    draw.ellipse(
        [(cx - ew//2, cy - eh//2), (cx + ew//2, cy + eh//2)],
        fill=TEXT_COLOR,
    )

    # Iris
    ir = int(size * 0.18)
    draw.ellipse(
        [(cx - ir, cy - ir), (cx + ir, cy + ir)],
        fill=BG_COLOR,
    )

    # Pupil
    pr = int(size * 0.09)
    draw.ellipse(
        [(cx - pr, cy - pr), (cx + pr, cy + pr)],
        fill=(10, 15, 20),
    )

    # "SW" text label at bottom
    font_size = max(size // 9, 12)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
                                  font_size)
    except Exception:
        font = ImageFont.load_default()

    text = "SW"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw   = bbox[2] - bbox[0]
    th   = bbox[3] - bbox[1]
    draw.text(
        (cx - tw // 2, cy + int(size * 0.28) - th // 2),
        text, fill=TEXT_COLOR, font=font,
    )

    out = ICONS_DIR / f"icon-{size}.png"
    img.save(out, "PNG")
    print(f"  ✓ {out}")

print("Generating PWA icons…")
make_icon(192)
make_icon(512)
print("Done.")
