#!/usr/bin/env python3
"""Render a code-derived preview matrix for the selected texture looks.

This visualizes the exact periodic height-field functions in r2_texture.py on
an unwrapped cylinder. It is an algorithm diagnostic, NOT a photo or a claim
about a printed result. Run: python3 tools/texture_matrix_preview.py [output.png]
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import r2_texture  # noqa: E402

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

MATERIALS = (
    ('BARK', 'Bark: fissures + ridges'),
    ('PLANKS', 'Boards: grooves + joints'),
    ('BRICKS', 'Brick: staggered mortar'),
    ('WAVES', 'Wave: diagonal relief'),
    ('HONEYCOMB', 'Honeycomb: cell walls'),
    ('BASKET', 'Basket: over / under'),
    ('ROPE', 'Rope: three strands'),
    ('PLUSH', 'Plush: fine grain'),
    ('SCALES', 'Scales: domed shingles'),
    ('FLUTED', 'Fluted: axial ribs'),
    ('STONEWALL', 'Stone wall: bed + joint mortar'),
    ('RUBBLE', 'Rubble: voronoi boulders'),
    ('TILES', 'Tiles: chamfer + grout lines'),
    ('PARQUET', 'Parquet: chevron planks'),
    ('LAMINATE', 'Laminate: V-bevel planks'),
    ('HILBERT', 'Hilbert: real order-3 curve'),
    ('MAZE', 'Maze: spanning-tree labyrinth'),
    ('PERFORATION', 'Perforation: staggered round holes'),
    ('VENT', 'Vent: staggered square recesses'),
    ('CARBON', 'Carbon: 2/2 twill weave'),
    ('PINDOTS', 'Pindots: hemisphere knob matrix'),
    ('OCTAGONS', 'Octagons: octagon + square trays'),
    ('CHAINLINK', 'Chainlink: woven 45-degree wires'),
    ('NETGRID', 'Netgrid: threads, knots, meshes'),
)


def render(path, materials=None):
    mats = list(MATERIALS if materials is None else materials)
    width, label_h = 320, 26
    # keep the classic 2-col layout for small sets, grow for the full library
    cols = 2 if len(mats) <= 10 else (3 if len(mats) <= 18 else 4)
    panel_rows = (len(mats) + cols - 1) // cols
    pad, gap = 14, 12
    head_h = 46
    k, n = 18, 12
    rows_per_period = max(2, int(round(2.0 * n / (3.0 ** 0.5))))
    if rows_per_period & 1:
        rows_per_period += 1
    height = int(round((width - 18) * rows_per_period * (3.0 ** 0.5)
                       / (2.0 * k)))
    cell_h = height + label_h
    out = Image.new('RGB', (pad * 2 + cols * width + gap,
                            head_h + pad + panel_rows * (cell_h + gap)), '#f4f2ed')
    draw = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 13)
        small = ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf', 10)
    except OSError:
        font = small = ImageFont.load_default()
    draw.text((pad, 10), 'Texture library — code-derived height fields', fill='#18232c', font=font)
    draw.text((pad, 29), 'Unwrapped cylinder samples; grayscale = signed displacement. Simulation only, not a print guarantee.',
              fill='#53616b', font=small)
    # ar in pixels = (height/n)/(width/k): previews must show the SAME
    # plank/slat shapes the printer raises (R265.2 form truth)
    _ar = (height / 12.0) / (width / 18.0)
    patterns = r2_texture._build_patterns(18, 12, 37, None, ar=_ar)
    for idx, (name, label) in enumerate(mats):
        col, row = idx % cols, idx // cols
        x0 = pad + col * (width + gap)
        y0 = head_h + pad + row * (cell_h + gap)
        draw.rounded_rectangle((x0, y0, x0 + width, y0 + cell_h), radius=5,
                               fill='#ffffff', outline='#d2d7d7')
        draw.text((x0 + 9, y0 + 6), label, fill='#18232c', font=font)
        field = Image.new('L', (width - 18, height))
        px = field.load()
        fn = patterns[name]
        for y in range(height):
            t = y / float(height)
            for x in range(width - 18):
                s = x / float(width - 18)
                v = max(-1.0, min(1.0, fn(s, t)))
                px[x, y] = int(round((v + 1.0) * 127.5))
        out.paste(field.convert('RGB'), (x0 + 9, y0 + label_h))
    out.save(path, optimize=True)
    return out.size, os.path.getsize(path)


if __name__ == '__main__':
    arg = sys.argv[1] if len(sys.argv) > 1 else None
    if arg == 'all':
        # the IST matrix: EVERY procedural pattern of the library, straight
        # from _build_patterns() - no curation, no description gloss.
        # (MAP is image-based, not a closed-form height field - skip.)
        mats = [(name, name) for name in r2_texture.PATTERN_NAMES
                if name != 'MAP']
        target = os.path.join(HERE, '..', 'docs', 'textur-matrix-ist.png')
        size, nbytes = render(target, mats)
    else:
        target = arg or os.path.join(
            HERE, '..', 'docs', 'textur-matrix-soll.png')
        size, nbytes = render(target)
    print('wrote %s (%dx%d, %d bytes)' % (target, size[0], size[1], nbytes))
