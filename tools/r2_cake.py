#!/usr/bin/env python3
"""R177 (.130 wish list): the cake cut - split a print with a plane.

The plane's normal is set by angles in ALL THREE axes in 0.5 degree steps
(the LCD inputs enforce the grid):

    yaw   - rotation around Z (where the tilt points)
    pitch - rotation around Y (front/back tilt)
    roll  - rotation around X (left/right tilt)
    n = Rz(yaw) . Ry(pitch) . Rx(roll) . (0,0,1)

The plane passes through (bed_center_x, bed_center_y, Z_OFFSET). With all
angles 0 it is the plain horizontal cut at Z = offset. Both halves become
standalone files (part UPPER / LOWER / BOTH):

  - LOWER keeps its coordinates (it already stands on the bed)
  - UPPER is moved down so its lowest point sits at the file's own first
    layer height, centered on the bed - or with REORIENT=1 rotated so the
    CUT FACE lies flat on the bed (the natural way to print a top piece)

Every move is split exactly at the plane, E splits by length share, arcs
flatten first (a rotation/skew would break them anyway), non-move lines
(header, temps, PRINT_END) go to BOTH files, and each output stream gets
an explicit positioning move whenever the input jumped across the plane.
"""
import math
import os
import re

_CMD_RE = re.compile(r'^(G1|G0)\b')
_TOK_RE = {t: re.compile(r'(?:^|\s)' + t + r'(-?[\d.]+)')
           for t in ('X', 'Y', 'Z', 'E', 'I', 'J', 'R', 'F')}
_TYPE = re.compile(r'^;TYPE:(.+)')
_MIN_E = 0.0002


def _tok(body, t):
    m = _TOK_RE[t].search(body)
    return float(m.group(1)) if m else None


def _parse_move(ls):
    body = ls.split(';', 1)[0]
    if not _CMD_RE.match(body):
        return None
    return ('G1' if body.startswith('G1') else 'G0',
            _tok(body, 'X'), _tok(body, 'Y'), _tok(body, 'Z'), _tok(body, 'E'))


def _parse_arc(ls):
    body = ls.split(';', 1)[0]
    m = re.match(r'^(G[23])\b', body)
    if not m:
        return None
    return (m.group(1), _tok(body, 'X'), _tok(body, 'Y'), _tok(body, 'Z'),
            _tok(body, 'I'), _tok(body, 'J'), _tok(body, 'R'),
            _tok(body, 'E'), _tok(body, 'F'))


def _arc_points(x0, y0, x1, y1, i=None, j=None, rr=None, cw=True,
                chord=0.35):
    """Points of a G2/G3 arc (same flattening the texture/scale use)."""
    cx = cy = None
    if i is not None and j is not None:
        cx, cy = x0 + i, y0 + j
    elif rr is not None and rr != 0:
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        d = math.hypot(x1 - x0, y1 - y0) / 2.0
        if d > abs(rr):
            return None
        h = math.sqrt(max(0.0, rr * rr - d * d))
        ux, uy = (y1 - y0), -(x1 - x0)
        if not (rr < 0) == cw:
            ux, uy = -ux, -uy
        cx, cy = mx + ux / (2 * d + 1e-12) * h, my + uy / (2 * d + 1e-12) * h
    else:
        return None
    r = math.hypot(x0 - cx, y0 - cy)
    r2 = math.hypot(x1 - cx, y1 - cy)
    if r < 1e-6 or abs(r - r2) > max(0.05, r * 0.01):
        return None
    a0 = math.atan2(y0 - cy, x0 - cx)
    a1 = math.atan2(y1 - cy, x1 - cx)
    sweep = (a0 - a1) % (2 * math.pi) if cw else (a1 - a0) % (2 * math.pi)
    if sweep < 1e-9:
        sweep = 2 * math.pi
    n = max(2, min(int(math.ceil(sweep * r / max(chord, 0.05))), 720))
    return [(cx + r * math.cos(a0 + (-sweep if cw else sweep) * k / float(n)),
             cy + r * math.sin(a0 + (-sweep if cw else sweep) * k / float(n)))
            for k in range(1, n + 1)]


def _normal(yaw, pitch, roll):
    """n = Rz(yaw) . Ry(pitch) . Rx(roll) . z (degrees in, unit vector out)."""
    y, p, r = (math.radians(float(v)) for v in (yaw, pitch, roll))
    # Rx(roll) . z
    v = (0.0, -math.sin(r), math.cos(r))
    # Ry(pitch) . v
    v = (v[0] * math.cos(p) + v[2] * math.sin(p), v[1],
         -v[0] * math.sin(p) + v[2] * math.cos(p))
    # Rz(yaw) . v
    return (v[0] * math.cos(y) - v[1] * math.sin(y),
            v[0] * math.sin(y) + v[1] * math.cos(y), v[2])


def _rot_about(v, axis, cost, sint):
    """Rodrigues rotation of v around a unit axis."""
    dot = axis[0] * v[0] + axis[1] * v[1] + axis[2] * v[2]
    cross = (axis[1] * v[2] - axis[2] * v[1],
             axis[2] * v[0] - axis[0] * v[2],
             axis[0] * v[1] - axis[1] * v[0])
    return tuple(v[k] * cost + cross[k] * sint + axis[k] * dot * (1 - cost)
                 for k in range(3))


def cut_cake(src, out_dir=None, yaw=0.0, pitch=0.0, roll=0.0, z_offset=0.0,
             part='BOTH', reorient=False, bed=None):
    """Returns (paths, info). paths = list of the written files."""
    part = str(part).upper()
    if part not in ('UPPER', 'LOWER', 'BOTH'):
        raise ValueError("part must be UPPER, LOWER or BOTH (got %r)" % part)
    yaw = round(float(yaw) * 2) / 2.0
    pitch = round(float(pitch) * 2) / 2.0
    roll = round(float(roll) * 2) / 2.0
    z_offset = float(z_offset)
    if not (-180 <= yaw <= 180 and -90 <= pitch <= 90 and -90 <= roll <= 90):
        raise ValueError('angles: yaw -180..180, pitch/roll -90..90 (0.5 '
                         'degree steps)')
    if abs(yaw) + abs(pitch) + abs(roll) < 1e-9 and z_offset == 0.0:
        raise ValueError('a plane at z=0 with no tilt cuts nothing - set an '
                         'angle or a Z offset')
    if not os.path.isfile(src):
        raise ValueError('source file not found: %s' % src)
    base = os.path.basename(src)
    stem = os.path.splitext(base)[0]
    out_dir = out_dir or os.path.dirname(os.path.abspath(src))
    if bed is None:
        bed = (0.0, 0.0, 220.0, 220.0)
    bx0, by0, bx1, by1 = (float(v) for v in bed)
    bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0

    n = _normal(yaw, pitch, roll)
    p0 = (bcx, bcy, z_offset)

    def w_of(x, y, z):
        return (n[0] * (x - p0[0]) + n[1] * (y - p0[1])
                + n[2] * (z - p0[2]))

    # ---- pass 1: bbox of everything / upper / lower --------------------
    min_all = [1e9, 1e9, 1e9]
    max_all = [-1e9, -1e9, -1e9]
    min_up = [1e9, 1e9, 1e9]
    max_up = [-1e9, -1e9, -1e9]
    min_lo = [1e9, 1e9, 1e9]
    max_lo = [-1e9, -1e9, -1e9]
    px, py, cur_z = None, None, None
    n_seg = 0
    n_cross = 0
    with open(src, errors='replace') as fi:
        for line in fi:
            ls = line.split(';', 1)[0]
            g = _parse_move(ls)
            pts = []
            if g is not None:
                if g[3] is not None:
                    cur_z = g[3]
                if g[1] is not None:
                    pts = [(g[1], g[2] if g[2] is not None else py)]
            else:
                ga = _parse_arc(ls)
                if ga is not None:
                    if ga[3] is not None:
                        cur_z = ga[3]
                    if ga[1] is not None and px is not None:
                        ay = ga[2] if ga[2] is not None else py
                        if ay is not None:
                            pts = _arc_points(px, py, ga[1], ay, i=ga[4],
                                              j=ga[5], rr=ga[6],
                                              cw=(ga[0] == 'G2')) or []
            for x, y in pts:
                z = cur_z if cur_z is not None else 0.0
                min_all[0] = min(min_all[0], x)
                min_all[1] = min(min_all[1], y)
                min_all[2] = min(min_all[2], z)
                max_all[0] = max(max_all[0], x)
                max_all[1] = max(max_all[1], y)
                max_all[2] = max(max_all[2], z)
                w = w_of(x, y, z)
                tgt = min_up if w >= 0 else min_lo
                tgt2 = max_up if w >= 0 else max_lo
                for k in range(3):
                    v = (x, y, z)[k]
                    tgt[k] = min(tgt[k], v)
                    tgt2[k] = max(tgt2[k], v)
                n_seg += 1
            if pts:
                px, py = pts[-1]
            elif g is not None and g[1] is not None:
                px, py = g[1], g[2]
    if min_all[0] > max_all[0]:
        raise ValueError('no moves with X/Y in %s - nothing to cut' % base)
    if min_up[2] > max_up[2]:
        raise ValueError('the plane is below the whole object - there is no '
                         'UPPER part (lower the Z offset or tilt)')
    if min_lo[2] > max_lo[2]:
        raise ValueError('the plane is above the whole object - there is no '
                         'LOWER part (raise the Z offset or tilt)')

    z_first = max(min_all[2], 0.0)      # the file's own first layer height

    want_up = part in ('UPPER', 'BOTH')
    want_lo = part in ('LOWER', 'BOTH')

    # ---- the transform for the UPPER part -------------------------------
    if reorient:
        # rotate so the cut-face normal points DOWN onto the bed
        c = -(n[0] * 0 + n[1] * 0 + n[2] * 1)        # n . (0,0,-1)
        s = math.sqrt(max(0.0, 1.0 - c * c))
        axis = (n[1] * (-1) - n[2] * 0, n[2] * 0 - n[0] * (-1),
                n[0] * 0 - n[1] * 0)                  # n x (0,0,-1)
        alen = math.hypot(*axis)
        if alen < 1e-9:
            axis, cost, sint = (1.0, 0.0, 0.0), 1.0, 0.0
        else:
            axis = tuple(a / alen for a in axis)
            cost, sint = c, s

        def trans(p):
            v = _rot_about((p[0] - bcx, p[1] - bcy, p[2]), axis, cost, sint)
            return (v[0] + bcx, v[1] + bcy, v[2])
    else:
        def trans(p):
            return (p[0], p[1], p[2])

    # upper bbox AFTER the transform (for the final placement)
    tb_min = [1e9, 1e9, 1e9]
    tb_max = [-1e9, -1e9, -1e9]
    px, py, cur_z = None, None, None
    with open(src, errors='replace') as fi:
        for line in fi:
            ls = line.split(';', 1)[0]
            g = _parse_move(ls)
            pts = []
            if g is not None:
                if g[3] is not None:
                    cur_z = g[3]
                if g[1] is not None:
                    pts = [(g[1], g[2] if g[2] is not None else py)]
            else:
                ga = _parse_arc(ls)
                if ga is not None:
                    if ga[3] is not None:
                        cur_z = ga[3]
                    if ga[1] is not None and px is not None:
                        ay = ga[2] if ga[2] is not None else py
                        if ay is not None:
                            pts = _arc_points(px, py, ga[1], ay, i=ga[4],
                                              j=ga[5], rr=ga[6],
                                              cw=(ga[0] == 'G2')) or []
            for x, y in pts:
                z = cur_z if cur_z is not None else 0.0
                if w_of(x, y, z) >= 0:
                    q = trans((x, y, z))
                    for k in range(3):
                        tb_min[k] = min(tb_min[k], q[k])
                        tb_max[k] = max(tb_max[k], q[k])
            if pts:
                px, py = pts[-1]
            elif g is not None and g[1] is not None:
                px, py = g[1], g[2]
    if tb_min[0] > tb_max[0]:
        tb_min, tb_max = list(min_up), list(max_up)
    up_w, up_h = tb_max[0] - tb_min[0], tb_max[1] - tb_min[1]
    if up_w > (bx1 - bx0) + 0.5 or up_h > (by1 - by0) + 0.5:
        raise ValueError('the UPPER part needs %.0f x %.0f mm after the '
                         'transform - the bed has %.0f x %.0f mm'
                         % (up_w, up_h, bx1 - bx0, by1 - by0))
    shift = (bcx - (tb_min[0] + tb_max[0]) / 2.0,
             bcy - (tb_min[1] + tb_max[1]) / 2.0,
             z_first - tb_min[2])

    def trans_final(p):
        q = trans(p)
        return (q[0] + shift[0], q[1] + shift[1], q[2] + shift[2])

    if not want_up:
        # LOWER only: nothing is ever transformed, skip the upper checks
        shift = (0.0, 0.0, 0.0)

        def trans_final(p):
            return p

    # ---- pass 2: write the parts ----------------------------------------
    def fname(tag):
        f = '%s_CUT-%s.gcode' % (stem, tag)
        k = 2
        while os.path.exists(os.path.join(out_dir, f)):
            f = '%s_CUT-%s_%d.gcode' % (stem, tag, k)
            k += 1
        return f

    paths = []
    fo_up = open(os.path.join(out_dir, fname('U')), 'w') if want_up else None
    fo_lo = open(os.path.join(out_dir, fname('L')), 'w') if want_lo else None
    if fo_up:
        paths.append(os.path.abspath(fo_up.name))
    if fo_lo:
        paths.append(os.path.abspath(fo_lo.name))

    hdr = ('; R177 cake cut: plane yaw %.1f pitch %.1f roll %.1f through '
           'z %.1f (bed center x/y) - normal (%.3f, %.3f, %.3f)\n'
           % (yaw, pitch, roll, z_offset, n[0], n[1], n[2]))
    for fo in (fo_up, fo_lo):
        if fo:
            fo.write(hdr)
            fo.write('; UPPER = the side the normal points to. %s\n'
                     % ('The cut face was rotated flat onto the bed '
                        '(reorient) and the part centered.'
                        if reorient and fo is fo_up else
                        ('Moved down to the first layer height and '
                         'centered on the bed.' if fo is fo_up else
                         'Keeps its original place (it already stands).')))
            fo.write('; E splits at the plane by length share, arcs are '
                     'flattened, every line is a standalone file.\n')

    e_rel = False
    last_e = None
    e_up = 0.0        # absolute E counter of the UPPER stream
    e_lo = 0.0        # absolute E counter of the LOWER stream
    px = py = None
    cur_z = None
    up_pos = [None, None, None]
    lo_pos = [None, None, None]
    segs_up = segs_lo = 0

    def emit(fo, pos_ref, x0, y0, z0, x1, y1, z1, d_e, f_val, cmd):
        """Write one (sub)segment into one stream. d_e = E delta share."""
        nonlocal e_up, e_lo
        tf = trans_final if fo is fo_up else (lambda p: p)
        # reposition explicitly when this stream last ended elsewhere
        if pos_ref[0] is not None:
            q0 = tf((x0, y0, z0))
            qp = tf(tuple(pos_ref))
            parts = ['G0']
            if abs(qp[0] - q0[0]) > 1e-4:
                parts.append('X%.3f' % q0[0])
            if abs(qp[1] - q0[1]) > 1e-4:
                parts.append('Y%.3f' % q0[1])
            if abs(qp[2] - q0[2]) > 1e-4:
                parts.append('Z%.3f' % q0[2])
            if len(parts) > 1:
                fo.write(' '.join(parts) + '\n')
        tx1, ty1, tz1 = tf((x1, y1, z1))
        parts = [cmd, 'X%.3f' % tx1, 'Y%.3f' % ty1]
        if tz1 is not None:
            parts.append('Z%.3f' % tz1)
        if d_e is not None and d_e > 0:
            if e_rel:
                parts.append('E%.5f' % d_e)
            else:
                parts.append('E%.5f' % ((e_up if fo is fo_up else e_lo)
                                        + d_e))
        if f_val:
            parts.append('F%g' % f_val)
        fo.write(' '.join(parts) + '\n')
        pos_ref[0], pos_ref[1], pos_ref[2] = x1, y1, z1
        if d_e is not None and d_e > 0:
            if fo is fo_up:
                e_up += d_e
            else:
                e_lo += d_e

    def seg(x0, y0, z0, x1, y1, z1, d_e, f_val, cmd):
        """One input segment, split at the plane."""
        nonlocal segs_up, segs_lo
        w0 = w_of(x0, y0, z0)
        w1 = w_of(x1, y1, z1)
        if w0 >= 0 and w1 >= 0:
            if fo_up:
                emit(fo_up, up_pos, x0, y0, z0, x1, y1, z1, d_e, f_val, cmd)
                segs_up += 1
        elif w0 < 0 and w1 < 0:
            if fo_lo:
                emit(fo_lo, lo_pos, x0, y0, z0, x1, y1, z1, d_e, f_val, cmd)
                segs_lo += 1
        else:
            t = w0 / (w0 - w1) if abs(w0 - w1) > 1e-12 else 0.5
            t = min(1.0, max(0.0, t))
            sx = x0 + (x1 - x0) * t
            sy = y0 + (y1 - y0) * t
            sz = z0 + (z1 - z0) * t
            da = d_e * t if d_e else d_e
            db = (d_e - da) if d_e else d_e
            if w0 >= 0:      # starts upper, ends lower
                if fo_up:
                    emit(fo_up, up_pos, x0, y0, z0, sx, sy, sz, da, f_val,
                         cmd)
                    segs_up += 1
                if fo_lo:
                    emit(fo_lo, lo_pos, sx, sy, sz, x1, y1, z1, db, f_val,
                         cmd)
                    segs_lo += 1
            else:            # starts lower, ends upper
                if fo_lo:
                    emit(fo_lo, lo_pos, x0, y0, z0, sx, sy, sz, da, f_val,
                         cmd)
                    segs_lo += 1
                if fo_up:
                    emit(fo_up, up_pos, sx, sy, sz, x1, y1, z1, db, f_val,
                         cmd)
                    segs_up += 1

    with open(src, errors='replace') as fi:
        for line in fi:
            ls = line.rstrip('\n')
            if ls == 'M83':
                e_rel = True
                for fo in (fo_up, fo_lo):
                    if fo:
                        fo.write(ls + '\n')
                continue
            if ls == 'M82':
                e_rel = False
                for fo in (fo_up, fo_lo):
                    if fo:
                        fo.write(ls + '\n')
                continue
            if ls.startswith('G92'):
                m92 = re.match(r'^G92(?:\s+E(-?[\d.]+))?', ls)
                if m92 and m92.group(1) is not None:
                    last_e = float(m92.group(1))
                    e_up = e_lo = last_e
                for fo in (fo_up, fo_lo):
                    if fo:
                        fo.write(ls + '\n')
                continue
            g = _parse_move(ls)
            if g is not None:
                z_prev = cur_z
                if g[3] is not None:
                    cur_z = g[3]
                x1, y1 = g[1], g[2]
                if x1 is None and y1 is None:
                    d_e = None
                    if g[4] is not None:
                        d_e = g[4] if e_rel else (
                            g[4] - (last_e if last_e is not None else g[4]))
                        last_e = g[4] if not e_rel else last_e
                    z_here = cur_z if cur_z is not None else 0.0
                    if px is not None and g[3] is not None:
                        # vertical hop (layer change): a real segment,
                        # it can cross the plane too
                        z0 = z_prev if z_prev is not None else 0.0
                        seg(px, py, z0, px, py, z_here, d_e, None, g[0])
                    elif px is not None:
                        # E-only move (prime/purge in place): follows the
                        # position's side
                        w = w_of(px, py, z_here)
                        tgt = fo_up if w >= 0 else fo_lo
                        ref = up_pos if w >= 0 else lo_pos
                        if tgt:
                            emit(tgt, ref, px, py, z_here, px, py, z_here,
                                 d_e, None, g[0])
                    continue
                yy1 = y1 if y1 is not None else py
                xx1 = x1
                if xx1 is None:
                    xx1 = px
                z1 = cur_z if cur_z is not None else 0.0
                d_e = None
                if g[4] is not None:
                    if e_rel:
                        d_e = g[4]
                    else:
                        d_e = g[4] - (last_e if last_e is not None
                                      else g[4])
                    if not e_rel:
                        last_e = g[4]
                if px is not None and yy1 is not None:
                    z_start = cur_z if g[3] is None else g[3]
                    z_start = z_start if z_start is not None else 0.0
                    seg(px, py, z_start, xx1, yy1, z1, d_e, None, g[0])
                elif yy1 is not None:
                    # first move ever (G0 to start): classify by target
                    w = w_of(xx1, yy1, z1)
                    if w >= 0 and fo_up:
                        emit(fo_up, up_pos, xx1, yy1, z1, xx1, yy1, z1,
                             None, None, g[0])
                    elif w < 0 and fo_lo:
                        emit(fo_lo, lo_pos, xx1, yy1, z1, xx1, yy1, z1,
                             None, None, g[0])
                if xx1 is not None and yy1 is not None:
                    px, py = xx1, yy1
                continue
            ga = _parse_arc(ls)
            if ga is not None and ga[1] is not None and px is not None:
                ay = ga[2] if ga[2] is not None else py
                if ay is not None:
                    pts = _arc_points(px, py, ga[1], ay, i=ga[4], j=ga[5],
                                      rr=ga[6], cw=(ga[0] == 'G2'))
                    z1 = ga[3] if ga[3] is not None else cur_z
                    z1 = z1 if z1 is not None else 0.0
                    if pts:
                        chain = [(px, py)] + pts
                        lens = [math.hypot(b[0] - a[0], b[1] - a[1])
                                for a, b in zip(chain, chain[1:])]
                        tot = sum(lens) or 1.0
                        d_arc = None
                        if ga[7] is not None and ga[7] > _MIN_E:
                            if e_rel:
                                d_arc = ga[7]
                            else:
                                d_arc = ga[7] - (last_e if last_e is not None
                                                 else ga[7])
                                last_e = ga[7]
                        done = 0.0
                        for (ax, ayv), (bx, byv), ln in zip(chain,
                                                            chain[1:], lens):
                            frac = ln / tot
                            d_part = (d_arc * frac) if d_arc else None
                            seg(ax, ayv, z1, bx, byv, z1, d_part, ga[8],
                                'G1')
                            if d_arc:
                                done += d_part
                        px, py = ga[1], ay
                        continue
            for fo in (fo_up, fo_lo):
                if fo:
                    fo.write(ls + '\n')
    for fo in (fo_up, fo_lo):
        if fo:
            fo.close()
    info = {'file': [os.path.basename(p) for p in paths],
            'src': base, 'yaw': yaw, 'pitch': pitch, 'roll': roll,
            'z_offset': z_offset, 'normal': n, 'part': part,
            'reorient': bool(reorient),
            'segments_upper': segs_up, 'segments_lower': segs_lo,
            'upper_size': (max_up[0] - min_up[0], max_up[1] - min_up[1],
                           max_up[2] - min_up[2]),
            'lower_size': (max_lo[0] - min_lo[0], max_lo[1] - min_lo[1],
                           max_lo[2] - min_lo[2]),
            'first_layer_z': z_first}
    return paths, info
