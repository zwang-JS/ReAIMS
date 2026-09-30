#!/usr/bin/env python3
"""Generate the ReAIMS extension's PNG icon set.

Design brief: "a registry ledger, set well". The mark is a miniature data
table -- a brand magenta rounded square carrying three white horizontal rules
of varying width (one heavier header rule plus two lighter data rules). Sober,
tabular, restrained; no text, no gradients, no gloss.

Every icon is drawn at 4x its target size and downsampled with
``Image.LANCZOS`` so that the 16px member of the set still has clean,
anti-aliased edges.

Usage (works from any working directory):

    python tools/gen_icons.py

Writes ``icons/icon{16,24,32,48,128}.png`` next to the repository root.
Requires Pillow only -- no network, no external assets, no fonts.
"""

from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover - environment guard
    sys.exit("Pillow is required to generate icons: pip install Pillow")


# --- constants ---------------------------------------------------------------

#: Icon sizes Chrome's manifest asks for.
SIZES = (16, 24, 32, 48, 128)

#: Supersampling factor. Draw big, shrink down -- this is what keeps 16px crisp.
SUPERSAMPLE = 4

BRAND_MAGENTA = (165, 11, 94, 255)  # #A50B5E

RULE_WHITE = (255, 255, 255, 255)

#: Transparent margin around the rounded square, as a fraction of icon size.
#: A hair of breathing room stops the LANCZOS kernel from clipping the edge.
INSET = 0.02

#: Corner radius of the rounded square, as a fraction of icon size.
CORNER_RADIUS = 0.22

#: Where the rules start, as a fraction of the square's width. Rules are
#: left-aligned so the ragged right edge reads as rows of ledger entries.
RULE_LEFT = 0.20

#: The three rules, as (centre y, width, thickness) -- each a fraction of the
#: rounded square's own width/height. The first is the heavier header rule.
#: The spacing is deliberately generous: at 16px these leave ~2px of magenta
#: between rules, which is the minimum for the three bars to read as separate.
RULES = (
    (0.300, 0.62, 0.105),
    (0.515, 0.42, 0.085),
    (0.730, 0.52, 0.085),
)

#: Pillow 9.1+ moved the resampling enums but kept the short aliases.
_LANCZOS = getattr(Image, "LANCZOS", None) or Image.Resampling.LANCZOS


# --- drawing -----------------------------------------------------------------

def render_icon(size: int) -> Image.Image:
    """Return a finished ``size`` x ``size`` RGBA icon.

    Everything is laid out on a ``size * SUPERSAMPLE`` canvas and then shrunk,
    so callers only ever deal with the final pixel dimensions.
    """
    canvas = size * SUPERSAMPLE
    img = Image.new("RGBA", (canvas, canvas), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # The rounded square. Everything else is positioned inside this box.
    box_left = INSET * canvas
    box_right = canvas - 1 - INSET * canvas
    box_top = INSET * canvas
    box_bottom = canvas - 1 - INSET * canvas
    box_w = box_right - box_left
    box_h = box_bottom - box_top

    radius = CORNER_RADIUS * canvas
    draw.rounded_rectangle(
        [box_left, box_top, box_right, box_bottom],
        radius=radius,
        fill=BRAND_MAGENTA,
    )

    # The ledger rules.
    for centre_y, width_frac, thickness_frac in RULES:
        left = box_left + RULE_LEFT * box_w
        right = left + width_frac * box_w
        thickness = thickness_frac * box_h
        top = box_top + centre_y * box_h - thickness / 2.0
        draw.rectangle([left, top, right, top + thickness], fill=RULE_WHITE)

    return img.resize((size, size), _LANCZOS)


# --- entry point -------------------------------------------------------------

def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "icons"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"ReAIMS icon generator -> {out_dir}")
    for size in SIZES:
        icon = render_icon(size)
        path = out_dir / f"icon{size}.png"
        icon.save(path, "PNG", optimize=True)
        written = path.stat().st_size
        print(f"  wrote {path.name:<12} {icon.size[0]}x{icon.size[1]}px  {written:,} bytes")

    print(f"Done: {len(SIZES)} icons written.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
