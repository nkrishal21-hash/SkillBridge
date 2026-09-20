"""
generate_logo_assets.py — One-off script to derive logo assets from
app/static/images/logo-source.png using Pillow + LANCZOS resampling.

Run once from the project root:
    ./venv/bin/python scripts/generate_logo_assets.py

Generates:
    app/static/images/favicon.ico        — multi-size ICO (16, 32, 48, 64 px)
    app/static/images/favicon-32.png     — 32x32 PNG fallback
    app/static/images/apple-touch-icon.png — 180x180 PNG (iOS home-screen)
    app/static/images/logo-navbar.png    — 88x88 PNG (2× for 44 px CSS height, retina)
    app/static/images/logo-large.png     — 512x512 PNG (footer / landing page)
"""

from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "app" / "static" / "images" / "logo-source.png"
OUT = ROOT / "app" / "static" / "images"

assert SRC.exists(), f"Source file not found: {SRC}"

img = Image.open(SRC).convert("RGBA")
print(f"Source: {SRC.name}  {img.size}  mode={img.mode}")

# ── Helper ────────────────────────────────────────────────────────────────────

def save_png(size: tuple[int, int], name: str) -> None:
    resized = img.resize(size, Image.LANCZOS)
    dest = OUT / name
    resized.save(dest, format="PNG", optimize=True)
    kb = dest.stat().st_size / 1024
    print(f"  ✅ {name:<32} {size[0]}x{size[1]}  {kb:.1f} KB")


# ── Derivatives ───────────────────────────────────────────────────────────────

# favicon.ico — multi-resolution ICO
ico_sizes = [(16, 16), (32, 32), (48, 48), (64, 64)]
ico_frames = [img.resize(s, Image.LANCZOS).convert("RGBA") for s in ico_sizes]
ico_path = OUT / "favicon.ico"
ico_frames[0].save(
    ico_path,
    format="ICO",
    sizes=ico_sizes,
    append_images=ico_frames[1:],
)
kb = ico_path.stat().st_size / 1024
print(f"  ✅ {'favicon.ico':<32} multi ({', '.join(str(s[0]) for s in ico_sizes)}px)  {kb:.1f} KB")

# favicon-32.png
save_png((32, 32), "favicon-32.png")

# apple-touch-icon.png — 180x180 (iOS adds its own rounding/gloss)
save_png((180, 180), "apple-touch-icon.png")

# logo-navbar.png — 88x88 (2× for 44 px retina CSS display)
save_png((88, 88), "logo-navbar.png")

# logo-large.png — 512x512 (footer / landing page)
save_png((512, 512), "logo-large.png")

print("\nDone — all logo assets written to app/static/images/")
