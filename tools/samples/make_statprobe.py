#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Erzeugt den Beispielkoerper fuer die PDF-Messwerte.

Der Korpus ist absichtlich ein *Slicer-Nachbau*: reine G0/G1-Wege mit den
Kommentaren, die ein Slicer schreibt (;TYPE:..., ;LAYER_CHANGE, ;Z:...).
Damit laesst sich der echte Postprozessor darueber laufen lassen, ohne eine
fremde Datei zu brauchen:

    python3 tools/samples/make_statprobe.py
    python3 tools/r2_postproc.py --watch tools/samples --once

Ergebnis: statprobe.gcode (getaggt, mit APPLY_TYPE/LAYER_MARK/_FILE_INFO).
Die Zahlen in PREPRINT_LIVETUNING.pdf und POSTPROCESSING.pdf stammen aus
genau diesem Lauf.
"""
import math
import os

H = 0.2
LAYERS = 30
EPM = 0.2 * 0.45 / (math.pi * (1.75 / 2.0) ** 2)      # mm Filament je mm Weg


def move(x1, y1, f=9000):
    return ['G0 X%.3f Y%.3f F%d' % (x1, y1, f)]


def rect(cx, cy, s, e_per_mm, f=3600):
    pts = [(cx - s / 2, cy - s / 2), (cx + s / 2, cy - s / 2),
           (cx + s / 2, cy + s / 2), (cx - s / 2, cy + s / 2),
           (cx - s / 2, cy - s / 2)]
    g = move(pts[0][0], pts[0][1])
    px, py = pts[0]
    for (nx, ny) in pts[1:]:
        d = math.hypot(nx - px, ny - py)
        g.append('G1 X%.3f Y%.3f E%.5f F%d' % (nx, ny, d * e_per_mm, f))
        px, py = nx, ny
    return g


def build(out):
    o = []
    o.append('; synthetic sample - slicer-like ;TYPE: comments, 30 layers')
    o.append(';FLAVOR:Marlin')
    o.append('_FILE_INFO NAME=statprobe LY=0.2 W=0.45 NOZ=0.4 HOT=210 BED=60 MAT=PLA')
    o.append('M83')
    o.append('G90')
    o.append('G28')
    for L in range(LAYERS):
        z = 0.2 + L * H
        o.append('G1 Z%.2f F600' % z)
        o.append(';LAYER_CHANGE')
        o.append(';Z:%.2f' % z)
        o.append('LAYER_MARK LAYER=%d Z=%.2f' % (L + 1, z))
        if L == 0:
            o.append(';TYPE:Skirt')
            o += rect(125, 125, 46, EPM * 0.9, 3000)
        o.append(';TYPE:Outer wall')
        o += rect(125, 125, 40, EPM * 1.0, 3600)
        o.append(';TYPE:Inner wall')
        o += rect(125, 125, 38, EPM * 1.0, 3600)
        o += rect(125, 125, 36, EPM * 1.0, 3600)
        o.append(';TYPE:Sparse infill')
        for i in range(6):
            yy = 108 + i * 6
            o += move(105, yy)
            o.append('G1 X145 Y%.3f E%.5f F4800' % (yy, 40 * EPM))
        if L >= 24:
            o.append(';TYPE:Top surface')
            for i in range(4):
                yy = 110 + i * 4
                o += move(106, yy)
                o.append('G1 X144 Y%.3f E%.5f F2400' % (yy, 38 * EPM))
        if L in (10, 11):
            o.append(';TYPE:Bridge')
            o += move(110, 120, 6000)
            o.append('G1 X150 Y120 E%.5f F1800' % (40 * EPM))
        if 6 <= L < 10:
            o.append(';TYPE:Support material')
            o += rect(140, 140, 10, EPM, 3000)
        if L == LAYERS - 1:
            o.append(';TYPE:Ironing')
            for i in range(20):
                yy = 107 + i * 2
                o += move(105, yy)
                o.append('G1 X145 Y%.3f E%.5f F1200' % (yy, 0.9))
    open(out, 'w').write('\n'.join(o) + '\n')
    print('%s: %d Zeilen' % (out, len(o)))


if __name__ == '__main__':
    build(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       'statprobe.gcode'))
