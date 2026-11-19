#!/usr/bin/env python3
"""Draw the MetaboKG logo in Art Techno and write every size the repo uses.

The mark is the cycle: eight compounds on an octagon in the manner of the TCA
cycle, flux running clockwise in gold arrowheads, and the enzyme die at the
center reaching four of them. The palette, drawing helpers and outlined
lettering come from the Art Techno brand build, so the SVGs render the same
everywhere.

Usage::

    python scripts/build_logo.py

Needs ``fonttools`` and Pillow, Google Chrome for the PNG renders, and a clone
of https://github.com/Flux-Frontiers/art_techno beside this repo. Set ``CHROME``
to the browser binary if it is not at the default macOS path.

Writes:

- ``assets/metabokg_logo.svg`` and ``assets/metabokg_logo.png``: the square
  mark (1024 px PNG)
- ``assets/metabokg_icon.svg``: the mark reduced for 64 px and below
- ``assets/metabokg_banner.svg`` and ``assets/metabokg_banner.png``
- ``assets/logo-md-256x256.png`` (read by ``scripts/generate_wiki.py``) from
  the mark
"""

import importlib.util
import math
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
AT_BUILD = ROOT.parent / "art_techno" / "docs" / "brand" / "build.py"

_spec = importlib.util.spec_from_file_location("at_build", AT_BUILD)
at = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(at)

f, line, pad, via, diamond, clipped_rect = (
    at.f,
    at.line,
    at.pad,
    at.via,
    at.diamond,
    at.clipped_rect,
)
OBSIDIAN, PANEL, COPPER, GOLD, GREEN, MINT, SILK = (
    at.OBSIDIAN,
    at.PANEL,
    at.COPPER,
    at.GOLD,
    at.GREEN,
    at.MINT,
    at.SILK,
)

NAME = "METABOKG"
PART = "METABOLISM AS A GRAPH"


def rect(
    x: float, y: float, w: float, h: float, fill: str, stroke: str = "", width: float = 0
) -> str:
    s = f' stroke="{stroke}" stroke-width="{f(width)}"' if stroke else ""
    return f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" fill="{fill}"{s}/>'


def package(x: float, y: float, r: float, c: float, width: float) -> str:
    """A chip package: a dark square with 45-degree corners in a gold line.

    :param x: Center x.
    :param y: Center y.
    :param r: Half the side length.
    :param c: Corner cut.
    :param width: Stroke width.
    """
    return (
        f'<path d="{clipped_rect(x - r, y - r, 2 * r, 2 * r, c)}" fill="{PANEL}" '
        f'stroke="{GOLD}" stroke-width="{f(width)}"/>'
    )


def die(x: float, y: float, s: float, core: str) -> str:
    """A square green die in a gold line, centered on ``x, y``.

    :param x: Center x.
    :param y: Center y.
    :param s: Side length.
    :param core: Color of the square at its center.
    """
    return rect(x - s / 2, y - s / 2, s, s, GREEN, GOLD, s / 9) + rect(
        x - s / 6, y - s / 6, s / 3, s / 3, core
    )


def node(x: float, y: float, r: float) -> str:
    """A compound the enzyme reaches: a gold pad with a green core."""
    return pad(x, y, r, GOLD) + pad(x, y, r * 0.44, GREEN)


def arrowhead(x: float, y: float, angle: float, size: float, color: str, width: float) -> str:
    """An open arrowhead at ``x, y`` pointing along ``angle`` degrees (SVG: 0 is right, 90 down)."""
    a = math.radians(angle)
    p, q = (
        (x + size * math.cos(a + math.radians(d)), y + size * math.sin(a + math.radians(d)))
        for d in (135, -135)
    )
    d = f"M{f(p[0])} {f(p[1])}L{f(x)} {f(y)}L{f(q[0])} {f(q[1])}"
    return (
        f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{f(width)}" '
        f'stroke-linejoin="miter"/>'
    )


def cycle() -> str:
    """Eight compounds on an octagon, flux clockwise, the enzyme die at the center."""
    out = []
    cx, cy, r = 256, 212, 136
    pts = [
        (
            cx + r * math.cos(math.radians(-90 + 45 * k)),
            cy + r * math.sin(math.radians(-90 + 45 * k)),
        )
        for k in range(8)
    ]
    for k in range(8):
        a, b = pts[k], pts[(k + 1) % 8]
        out.append(line([a, b], COPPER, 5))
        heading = math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))
        out.append(arrowhead((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, heading, 11, GOLD, 4))
    for k in (0, 2, 4, 6):
        x, y = pts[k]
        out.append(line([(cx, cy), (cx + (x - cx) * 0.8, cy + (y - cy) * 0.8)], GOLD, 5))
    for k, (x, y) in enumerate(pts):
        out.append(node(x, y, 14) if k % 2 == 0 else via(x, y, 9, COPPER))
    out.append(die(cx, cy, 60, SILK))
    return "".join(out)


def cycle_small() -> str:
    """The cycle reduced for 64 px and below: four compounds on a diamond and the die."""
    out = []
    cx, cy, r = 32, 32, 22
    pts = [
        (
            cx + r * math.cos(math.radians(-90 + 90 * k)),
            cy + r * math.sin(math.radians(-90 + 90 * k)),
        )
        for k in range(4)
    ]
    for k in range(4):
        out.append(line([pts[k], pts[(k + 1) % 4]], COPPER, 2.6))
    for x, y in pts:
        out.append(pad(x, y, 4.4, GOLD))
    out.append(die(cx, cy, 15, GOLD))
    return "".join(out)


def frame(w: float, h: float, inset: float, c: float, heavy: float) -> str:
    """Double frame with 45-degree corners and a green diamond at each corner.

    :param w: Canvas width.
    :param h: Canvas height.
    :param inset: Distance of the heavy line from the canvas edge.
    :param c: Corner cut of the heavy line.
    :param heavy: Stroke width of the heavy line.
    """
    out = [
        f'<path d="{clipped_rect(inset, inset, w - 2 * inset, h - 2 * inset, c)}" fill="none" stroke="{GOLD}" stroke-width="{f(heavy)}"/>',
        f'<path d="{clipped_rect(inset * 1.9, inset * 1.9, w - 3.8 * inset, h - 3.8 * inset, c * 0.75)}" fill="none" stroke="{GOLD}" stroke-width="{f(heavy * 0.4)}" stroke-opacity=".6"/>',
    ]
    d = inset * 1.45 + c * 0.4375
    for cx, cy in ((d, d), (w - d, d), (d, h - d), (w - d, h - d)):
        out.append(diamond(cx, cy, inset * 0.5, GREEN))
    return "".join(out)


def svg(w: int, h: int, title: str, body: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
        f"<title>{title}</title>"
        f'<rect width="{w}" height="{h}" fill="{OBSIDIAN}"/>{body}</svg>\n'
    )


def mark(display, mono) -> str:
    """512 square mark: the cycle, the name and the part line beneath."""
    body = frame(512, 512, 10, 26, 5) + cycle()
    body += display.path(NAME, 256, 430, 40, 0.2, "middle", GOLD)
    body += mono.path(PART, 256, 462, 13.5, 0.3, "middle", MINT)
    return svg(512, 512, "MetaboKG mark, Art Techno", body)


def icon() -> str:
    """64 icon: the reduced cycle in one heavy frame, no lettering."""
    body = f'<path d="{clipped_rect(2.5, 2.5, 59, 59, 7.5)}" fill="none" stroke="{GOLD}" stroke-width="3"/>'
    return svg(64, 64, "MetaboKG icon, Art Techno", body + cycle_small())


def banner(display, mono) -> str:
    """1280 x 320 banner: the cycle left, the name and part line right.

    The name is set as large as the room right of the cycle allows, and the
    pair is centered on the banner's height.
    """
    s = 0.78
    body = frame(1280, 320, 10, 18, 3)
    body += (
        f'<g transform="translate({f(230 - 256 * s)} {f(160 - 212 * s)}) scale({s})">{cycle()}</g>'
    )
    cx, room, gap = 820, 760, 34
    size = min(120, 120 * room / display.width(NAME, 120, 0.2))
    part = min(26, 26 * room / mono.width(PART, 26, 0.3))
    cap = display.cap * size / display.upm
    pcap = mono.cap * part / mono.upm
    base = (320 - (cap + gap + pcap)) / 2 + cap
    body += display.path(NAME, cx, base, size, 0.2, "middle", GOLD)
    body += mono.path(PART, cx, base + gap + pcap, part, 0.3, "middle", MINT)
    return svg(1280, 320, "MetaboKG banner, Art Techno", body)


def render(src: Path, out: Path, w: int, h: int) -> None:
    """Render the SVG ``src`` to ``out`` at ``w`` x ``h`` px with headless Chrome.

    :param src: SVG file; its ``width`` attribute sets the CSS width.
    :param out: PNG to write.
    :param w: Output width in px.
    :param h: Output height in px.
    """
    svg_w = int(src.read_text().split('width="', 1)[1].split('"', 1)[0])
    subprocess.run(
        [
            at.CHROME,
            "--headless",
            "--disable-gpu",
            "--hide-scrollbars",
            f"--window-size={svg_w},{svg_w * h // w}",
            f"--force-device-scale-factor={w / svg_w}",
            f"--screenshot={out}",
            src.as_uri(),
        ],
        check=True,
        capture_output=True,
    )


def resized(master: Path, dest: Path, px: int) -> None:
    Image.open(master).convert("RGB").resize((px, px), Image.LANCZOS).save(dest, optimize=True)


def main() -> None:
    at.fetch_fonts()
    display = at.Face(at.CACHE / "JosefinSans.ttf", weight=600)
    mono = at.Face(at.CACHE / "IBMPlexMono-Medium.ttf")

    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    mark_svg = assets / "metabokg_logo.svg"
    icon_svg = assets / "metabokg_icon.svg"
    banner_svg = assets / "metabokg_banner.svg"
    mark_svg.write_text(mark(display, mono))
    icon_svg.write_text(icon())
    banner_svg.write_text(banner(display, mono))

    mark_png = mark_svg.with_suffix(".png")
    render(mark_svg, mark_png, 1024, 1024)
    render(banner_svg, banner_svg.with_suffix(".png"), 2560, 640)
    resized(mark_png, assets / "logo-md-256x256.png", 256)


if __name__ == "__main__":
    main()
