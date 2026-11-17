#!/usr/bin/env python3
"""R177 (.130 wish list) / H2: the cake cut - split a print with a plane.

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

Every move is split exactly at the plane (including sloped/spiral Z moves and
helical G2/G3 arcs), E splits by length share, modal feedrates and retracts
are preserved across splits, and each half receives accurate per-half
;LAYER_CHANGE / LAYER_MARK / ;Z: markers plus truthful TOTAL_LAYERS metadata
written atomically so downstream tools (make_range, preview, Live > Layer)
work directly on cut halves.
"""
import math
import os
import re
import statistics
import tempfile

_CMD_RE = re.compile(r'^\s*(G0|G1)\b', re.I)
_ARC_RE = re.compile(r'^\s*(G2|G3)\b', re.I)
_MODE_RE = re.compile(r'^\s*(G90|G91|M82|M83|G92)\b', re.I)
_TOK_RE = {
    t: re.compile(r'(?:^|\s)' + t + r'([+-]?(?:\d+(?:\.\d*)?|\.\d+))', re.I)
    for t in ('X', 'Y', 'Z', 'E', 'I', 'J', 'R', 'F')
}
_TYPE_RE = re.compile(r'^;TYPE:(.+)')
_APPLY_RE = re.compile(r'^\s*APPLY_TYPE\b.*\bTYPE=(\S+)')
_STALE_LAYER_COMMENT_RE = re.compile(
    r'^\s*;\s*(?:'
    r'LAYER_CHANGE\b|BEFORE_LAYER_CHANGE\b|AFTER_LAYER_CHANGE\b|'
    r'CHANGE_LAYER\b|LAYER\s*:\s*-?\d+\b|layer\s+\d+(?:\s*,|\s*$)|'
    r'Z\s*:\s*[+-]?[\d.]+|Z_HEIGHT\s*:\s*[+-]?[\d.]+|'
    r'LAYER_HEIGHT\s*:\s*[+-]?[\d.]+'
    r')',
    re.I,
)
_STALE_LAYER_CMD_RE = re.compile(
    r'^\s*(?:'
    r'LAYER_MARK\b|'
    r'SET_PRINT_STATS_INFO\b(?=.*\bCURRENT_LAYER=)(?!.*\bTOTAL_LAYER=)|'
    r'_PROGRESS_LAYER\b'
    r')'
)
_LH_MACRO_RE = re.compile(r'\bLAYER_HEIGHT=([0-9]*\.?[0-9]+)')
_LH_COMMENT_RE = re.compile(
    r'^\s*;\s*(?:layer_height\s*=|Layer height\s*:)\s*([0-9]*\.?[0-9]+)'
)
_TOTAL_LAYERS_KV_RE = re.compile(r'\bTOTAL_LAYERS=\d+')
_STATS_TOTAL_RE = re.compile(r'\bTOTAL_LAYER=\d+')
_STATS_CUR_RE = re.compile(r'\s*\bCURRENT_LAYER=\d+')
_CURA_COUNT_RE = re.compile(r'^(\s*;LAYER_COUNT:\s*)\d+')
_PRUSA_COUNT_RE = re.compile(r'^(\s*;\s*total layers count\s*=\s*)\d+', re.I)
_TYPES_KV_RE = re.compile(r'\bTYPES=(\S+)')
_MIN_E = 0.0002
_DISC_LAYER_MIN_DZ = 0.039   # just below 0.04 mm ultra-fine discrete layers


def _tok(body, t):
    m = _TOK_RE[t].search(body)
    if not m:
        return None
    v = float(m.group(1))
    return v if math.isfinite(v) else None


def _parse_move(ls):
    body = ls.split(';', 1)[0]
    m = _CMD_RE.match(body)
    if not m:
        return None
    return (m.group(1).upper(),
            _tok(body, 'X'), _tok(body, 'Y'), _tok(body, 'Z'),
            _tok(body, 'E'), _tok(body, 'F'))


def _parse_arc(ls):
    body = ls.split(';', 1)[0]
    m = _ARC_RE.match(body)
    if not m:
        return None
    return (m.group(1).upper(),
            _tok(body, 'X'), _tok(body, 'Y'), _tok(body, 'Z'),
            _tok(body, 'I'), _tok(body, 'J'), _tok(body, 'R'),
            _tok(body, 'E'), _tok(body, 'F'))


def _parse_mode(ls):
    body = ls.split(';', 1)[0].strip()
    m = _MODE_RE.match(body)
    if not m:
        return None, body
    return m.group(1).upper(), body


def _arc_points(x0, y0, x1, y1, i=None, j=None, rr=None, cw=True,
                chord=0.35):
    """Points of a G2/G3 arc (same flattening the texture/scale use)."""
    cx = cy = None
    if i is not None or j is not None:
        cx, cy = x0 + (i or 0.0), y0 + (j or 0.0)
    elif rr is not None and rr != 0:
        if abs(x1 - x0) < 1e-9 and abs(y1 - y0) < 1e-9:
            return None   # full circle with R is geometrically undefined
        mx, my = (x0 + x1) / 2.0, (y0 + y1) / 2.0
        d = math.hypot(x1 - x0, y1 - y0) / 2.0
        if d > abs(rr) * (1.0 + 1e-6):
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
    pts = [(cx + r * math.cos(a0 + (-sweep if cw else sweep) * k / float(n)),
            cy + r * math.sin(a0 + (-sweep if cw else sweep) * k / float(n)))
           for k in range(1, n)]
    pts.append((x1, y1))
    return pts


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


def _is_stale_layer_line(ls):
    return bool(_STALE_LAYER_COMMENT_RE.match(ls)
                or _STALE_LAYER_CMD_RE.match(ls))


def _rewrite_metadata_line(line, n_layers, used_types):
    """Rewrite header/footer layer-count and _FILE_INFO TYPES claims."""
    if _TOTAL_LAYERS_KV_RE.search(line):
        line = _TOTAL_LAYERS_KV_RE.sub('TOTAL_LAYERS=%d' % n_layers, line)
    if line.lstrip().startswith('_FILE_INFO') and used_types:
        m = _TYPES_KV_RE.search(line)
        if m:
            orig = [t for t in m.group(1).split(',') if t]
            kept = [t for t in orig if t in used_types]
            for t in used_types:
                if t not in kept:
                    kept.append(t)
            if kept:
                line = (line[:m.start()] + 'TYPES=' + ','.join(kept)
                        + line[m.end():])
    if line.lstrip().startswith('SET_PRINT_STATS_INFO'):
        if _STATS_TOTAL_RE.search(line):
            line = _STATS_TOTAL_RE.sub('TOTAL_LAYER=%d' % n_layers, line)
            line = _STATS_CUR_RE.sub('', line)
    line = _CURA_COUNT_RE.sub(r'\g<1>%d' % n_layers, line)
    line = _PRUSA_COUNT_RE.sub(r'\g<1>%d' % n_layers, line)
    return line


def _finalize_atomic(body_tmp, dst_path, meta_line, n_layers, used_types):
    """Stream body_tmp into dst_path atomically with patched layer metadata."""
    out_dir = os.path.dirname(os.path.abspath(dst_path))
    fd, final_tmp = tempfile.mkstemp(prefix='.r2cake_', suffix='.tmp',
                                     dir=out_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out, \
                open(body_tmp, 'r', encoding='utf-8', errors='replace') as inp:
            for idx, raw in enumerate(inp):
                if idx == 3 and meta_line:
                    out.write(meta_line)
                if raw.endswith('\n'):
                    out.write(_rewrite_metadata_line(
                        raw[:-1], n_layers, used_types) + '\n')
                else:
                    out.write(_rewrite_metadata_line(
                        raw, n_layers, used_types))
            out.flush()
            os.fsync(out.fileno())
        os.replace(final_tmp, dst_path)
    except Exception:
        try:
            os.unlink(final_tmp)
        except OSError:
            pass
        raise


def _resolve_axis(cur, val, rel):
    if val is None:
        return cur
    if rel:
        return (cur if cur is not None else 0.0) + val
    return val


def _iter_source_pts(src):
    """Yield (x, y, z) move points with G90/G91/G92 and helical arc support,
    plus collect layer-height hints on the side via a returned helper."""
    raise NotImplementedError   # kept inline for speed and single state


def _scan_geometry(src, w_of, trans=None):
    """Scan source moves honoring G90/G91, M82/M83, G92, sloped Z, and arcs."""
    min_all = [1e9, 1e9, 1e9]
    max_all = [-1e9, -1e9, -1e9]
    min_up = [1e9, 1e9, 1e9]
    max_up = [-1e9, -1e9, -1e9]
    min_lo = [1e9, 1e9, 1e9]
    max_lo = [-1e9, -1e9, -1e9]
    tb_min = [1e9, 1e9, 1e9]
    tb_max = [-1e9, -1e9, -1e9]
    px = py = cur_z = None
    xyz_rel = False
    e_rel = False
    last_e = None
    lh_hint = None
    flat_ext_z = None
    flat_dzs = []

    def _acc_pt(x, y, z):
        min_all[0] = min(min_all[0], x)
        min_all[1] = min(min_all[1], y)
        min_all[2] = min(min_all[2], z)
        max_all[0] = max(max_all[0], x)
        max_all[1] = max(max_all[1], y)
        max_all[2] = max(max_all[2], z)
        w = w_of(x, y, z)
        tgt, tgt2 = (min_up, max_up) if w >= 0 else (min_lo, max_lo)
        for k, v in enumerate((x, y, z)):
            tgt[k] = min(tgt[k], v)
            tgt2[k] = max(tgt2[k], v)
        if trans is not None and w >= 0:
            q = trans((x, y, z))
            for k in range(3):
                tb_min[k] = min(tb_min[k], q[k])
                tb_max[k] = max(tb_max[k], q[k])

    def _acc_seg(x0, y0, z0, x1, y1, z1):
        _acc_pt(x1, y1, z1)
        # Include the exact plane intersection so transformed UPPER bbox
        # reflects cut-face points even on long sloped/diagonal segments.
        w0 = w_of(x0, y0, z0)
        w1 = w_of(x1, y1, z1)
        if (w0 >= 0) != (w1 >= 0) and abs(w0 - w1) > 1e-12:
            t = min(1.0, max(0.0, w0 / (w0 - w1)))
            sx = x0 + (x1 - x0) * t
            sy = y0 + (y1 - y0) * t
            sz = z0 + (z1 - z0) * t
            if trans is not None:
                q = trans((sx, sy, sz))
                for k in range(3):
                    tb_min[k] = min(tb_min[k], q[k])
                    tb_max[k] = max(tb_max[k], q[k])

    with open(src, errors='replace') as fi:
        for line in fi:
            if lh_hint is None:
                mh = _LH_MACRO_RE.search(line) or _LH_COMMENT_RE.match(line)
                if mh:
                    vh = float(mh.group(1))
                    if 0.02 <= vh <= 2.0:
                        lh_hint = vh
            mode, mbody = _parse_mode(line)
            if mode == 'G90':
                xyz_rel = False
                continue
            if mode == 'G91':
                xyz_rel = True
                continue
            if mode == 'M82':
                e_rel = False
                continue
            if mode == 'M83':
                e_rel = True
                continue
            if mode == 'G92':
                for ax_name, cur_name in (('X', 'x'), ('Y', 'y'),
                                          ('Z', 'z'), ('E', 'e')):
                    tv = _tok(mbody, ax_name)
                    if tv is not None:
                        if cur_name == 'x':
                            px = tv
                        elif cur_name == 'y':
                            py = tv
                        elif cur_name == 'z':
                            cur_z = tv
                        else:
                            last_e = tv
                continue
            g = _parse_move(line)
            if g is not None:
                z_prev = cur_z
                nz = _resolve_axis(cur_z, g[3], xyz_rel)
                cur_z = nz
                nx = _resolve_axis(px, g[1], xyz_rel)
                ny = _resolve_axis(py, g[2], xyz_rel)
                eff_erel = e_rel or xyz_rel
                d_e = 0.0
                if g[4] is not None:
                    if eff_erel:
                        d_e = g[4]
                        if not e_rel and last_e is not None:
                            last_e += d_e
                    else:
                        d_e = g[4] - (last_e if last_e is not None else g[4])
                        last_e = g[4]
                if (g[1] is not None or g[2] is not None) \
                        and nx is not None and ny is not None:
                    z1 = nz if nz is not None else 0.0
                    z0 = z_prev if z_prev is not None else z1
                    if px is not None and py is not None:
                        _acc_seg(px, py, z0, nx, ny, z1)
                    else:
                        _acc_pt(nx, ny, z1)
                    if (d_e > _MIN_E and abs(z1 - z0) <= 1e-4
                            and len(flat_dzs) < 400):
                        if flat_ext_z is not None:
                            dz = z1 - flat_ext_z
                            if _DISC_LAYER_MIN_DZ <= dz <= 1.2:
                                flat_dzs.append(round(dz, 4))
                        if flat_ext_z is None or abs(z1 - flat_ext_z) > 1e-3:
                            flat_ext_z = z1
                    px, py = nx, ny
                continue
            ga = _parse_arc(line)
            if ga is not None and px is not None and py is not None:
                z_prev = cur_z
                nz = _resolve_axis(cur_z, ga[3], xyz_rel)
                cur_z = nz
                ax = _resolve_axis(px, ga[1], xyz_rel)
                ay = _resolve_axis(py, ga[2], xyz_rel)
                pts = _arc_points(px, py, ax, ay, i=ga[4], j=ga[5],
                                  rr=ga[6], cw=(ga[0] == 'G2'))
                if pts:
                    z1 = nz if nz is not None else 0.0
                    z0 = z_prev if z_prev is not None else z1
                    chain = [(px, py)] + pts
                    lens = [math.hypot(b[0] - a[0], b[1] - a[1])
                            for a, b in zip(chain, chain[1:])]
                    tot = sum(lens) or 1.0
                    cum = 0.0
                    za = z0
                    for (x0, y0), (x1, y1), ln in zip(chain, chain[1:], lens):
                        cum += ln
                        zb = z0 + (z1 - z0) * (cum / tot)
                        _acc_seg(x0, y0, za, x1, y1, zb)
                        za = zb
                    px, py = ax, ay
    if lh_hint is None:
        lh_hint = statistics.median(flat_dzs) if flat_dzs else 0.2
    lh_hint = min(max(float(lh_hint), 0.04), 2.0)
    return min_all, max_all, min_up, max_up, min_lo, max_lo, tb_min, tb_max, lh_hint


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
    os.makedirs(out_dir, exist_ok=True)
    if bed is None:
        bed = (0.0, 0.0, 220.0, 220.0)
    bx0, by0, bx1, by1 = (float(v) for v in bed)
    bcx, bcy = (bx0 + bx1) / 2.0, (by0 + by1) / 2.0

    n = _normal(yaw, pitch, roll)
    p0 = (bcx, bcy, z_offset)

    def w_of(x, y, z):
        return (n[0] * (x - p0[0]) + n[1] * (y - p0[1])
                + n[2] * (z - p0[2]))

    # ---- transform for the UPPER part -----------------------------------
    if reorient:
        # Rotate UPPER so its cut face (w = 0, outward normal -n) lies flat on
        # the bed (outward normal -> (0,0,-1), inward normal +n -> (0,0,+1)),
        # so w >= 0 maps directly to height above z_first (bottom-to-top).
        c = n[2]                                      # n . (0,0,+1)
        s = math.sqrt(max(0.0, 1.0 - c * c))
        axis = (n[1], -n[0], 0.0)                     # n x (0,0,+1)
        alen = math.hypot(*axis)
        if alen < 1e-9:
            axis, cost, sint = (1.0, 0.0, 0.0), (1.0 if c >= 0 else -1.0), 0.0
        else:
            axis = tuple(a / alen for a in axis)
            cost, sint = c, s

        def trans(p):
            v = _rot_about((p[0] - bcx, p[1] - bcy, p[2]), axis, cost, sint)
            return (v[0] + bcx, v[1] + bcy, v[2])
    else:
        def trans(p):
            return (p[0], p[1], p[2])

    want_up = part in ('UPPER', 'BOTH')
    want_lo = part in ('LOWER', 'BOTH')

    # ---- pass 1: bbox of everything / upper / lower + transformed upper -
    (min_all, max_all, min_up, max_up, min_lo, max_lo,
     tb_min, tb_max, lh) = _scan_geometry(
        src, w_of, trans=trans if want_up else None)

    if min_all[0] > max_all[0]:
        raise ValueError('no moves with X/Y in %s - nothing to cut' % base)
    if min_up[2] > max_up[2]:
        raise ValueError('the plane is below the whole object - there is no '
                         'UPPER part (lower the Z offset or tilt)')
    if min_lo[2] > max_lo[2]:
        raise ValueError('the plane is above the whole object - there is no '
                         'LOWER part (raise the Z offset or tilt)')

    z_first = max(min_all[2], 0.0)      # the file's own first layer height

    if want_up:
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
    else:
        shift = (0.0, 0.0, 0.0)

        def trans_final(p):
            return p

    # ---- pass 2: write the parts to streaming temp files, finalize atomic
    def fname(tag):
        f = '%s_CUT-%s.gcode' % (stem, tag)
        k = 2
        while os.path.exists(os.path.join(out_dir, f)):
            f = '%s_CUT-%s_%d.gcode' % (stem, tag, k)
            k += 1
        return f

    dst_up = os.path.abspath(os.path.join(out_dir, fname('U'))) if want_up else None
    dst_lo = os.path.abspath(os.path.join(out_dir, fname('L'))) if want_lo else None
    paths = [p for p in (dst_up, dst_lo) if p]

    tmp_up = tmp_lo = None
    fo_up = fo_lo = None
    try:
        if want_up:
            fd_u, tmp_up = tempfile.mkstemp(prefix='.r2cake_u_',
                                            suffix='.body', dir=out_dir)
            fo_up = os.fdopen(fd_u, 'w', encoding='utf-8')
        if want_lo:
            fd_l, tmp_lo = tempfile.mkstemp(prefix='.r2cake_l_',
                                            suffix='.body', dir=out_dir)
            fo_lo = os.fdopen(fd_l, 'w', encoding='utf-8')

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
                         'flattened, layer markers are rebuilt per half.\n')

        xyz_rel = False
        e_rel = False
        last_e = None
        cur_f = None
        src_ret = 0.0
        px = py = None
        cur_z = None
        segs_up = segs_lo = 0
        cur_type_line = None
        cur_apply_line = None
        cur_apply_key = None

        st = {
            'U': {'fo': fo_up, 'tf': trans_final, 'reorient': bool(reorient),
                  'pos': [None, None, None], 'e': 0.0, 'ret': 0.0,
                  'last_f': None, 'g90_sent': False, 'lay_z': None,
                  'band_lo': None, 'band_hi': None,
                  'layers': 0, 'feat': (None, None), 'types': []},
            'L': {'fo': fo_lo, 'tf': (lambda p: p), 'reorient': False,
                  'pos': [None, None, None], 'e': 0.0, 'ret': 0.0,
                  'last_f': None, 'g90_sent': False, 'lay_z': None,
                  'band_lo': None, 'band_hi': None,
                  'layers': 0, 'feat': (None, None), 'types': []},
        }

        def _ensure_g90(s):
            if not s['g90_sent']:
                s['fo'].write('G90\n')
                s['g90_sent'] = True

        def _write_e_delta(s, delta, f_use):
            if abs(delta) <= _MIN_E:
                return
            if e_rel:
                ep = 'E%.5f' % delta
            else:
                s['e'] += delta
                ep = 'E%.5f' % s['e']
            parts = ['G1', ep]
            if f_use and (s['last_f'] is None
                          or abs(s['last_f'] - f_use) > 1e-4):
                parts.append('F%g' % f_use)
                s['last_f'] = f_use
            s['fo'].write(' '.join(parts) + '\n')

        def _maybe_layer_mark(s, tz0, tz1):
            flat = (not s['reorient']) and abs(tz1 - tz0) <= 1e-4
            prev_z = s['lay_z']
            z_mark = None
            if prev_z is None:
                z_mark = tz0 if not flat else tz1
                s['band_lo'] = s['band_hi'] = z_mark
            elif flat:
                if tz1 <= prev_z - max(0.35, 1.8 * lh):
                    # Sequential print unit restart (e.g. second object on bed)
                    z_mark = tz1
                    s['band_lo'] = s['band_hi'] = z_mark
                elif tz1 >= prev_z + _DISC_LAYER_MIN_DZ:
                    z_mark = tz1
                    s['band_hi'] = max(s['band_hi'], z_mark)
            else:
                zhi = max(tz0, tz1)
                zlo = min(tz0, tz1)
                band = max(0.04, lh)
                if zhi >= s['band_hi'] + band - 1e-4:
                    z_mark = zhi
                    s['band_hi'] = zhi
                elif s['reorient'] and zlo <= s['band_lo'] - band + 1e-4:
                    z_mark = zlo
                    s['band_lo'] = zlo
            if z_mark is not None:
                s['fo'].write(';LAYER_CHANGE\nLAYER_MARK\n;Z:%.3f\n' % z_mark)
                s['lay_z'] = z_mark
                s['layers'] += 1

        def _maybe_feature(s):
            pair = (cur_type_line, cur_apply_line)
            if pair == s['feat']:
                return
            if cur_type_line:
                s['fo'].write(cur_type_line + '\n')
            if cur_apply_line:
                s['fo'].write(cur_apply_line + '\n')
                if cur_apply_key and cur_apply_key not in s['types']:
                    s['types'].append(cur_apply_key)
            s['feat'] = pair

        def emit(side, x0, y0, z0, x1, y1, z1, d_e, f_val, cmd, e_only=False):
            """Write one (sub)segment into stream 'U' or 'L'."""
            s = st[side]
            fo = s['fo']
            if fo is None:
                return
            _ensure_g90(s)
            tf = s['tf']
            q0 = tf((x0, y0, z0))
            tx1, ty1, tz1 = tf((x1, y1, z1))
            f_use = (f_val if (f_val is not None and f_val > 0)
                     else cur_f)

            if e_only:
                if d_e is not None and d_e < -_MIN_E:
                    s['ret'] += -d_e
                    _write_e_delta(s, d_e, f_use)
                elif d_e is not None and d_e > _MIN_E:
                    _write_e_delta(s, d_e, f_use)
                return

            printing = (d_e is not None and d_e > _MIN_E)
            if printing:
                _maybe_layer_mark(s, q0[2], tz1)

            # Reposition explicitly when this stream last ended elsewhere
            pos_ref = s['pos']
            if pos_ref[0] is not None:
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

            if printing:
                _maybe_feature(s)
                if s['ret'] > _MIN_E:
                    # Recover an earlier retract whose matching unretract fell
                    # on the other side of the cutting plane.
                    rec = s['ret']
                    s['ret'] = 0.0
                    _write_e_delta(s, rec, f_use)

            parts = [cmd, 'X%.3f' % tx1, 'Y%.3f' % ty1]
            if tz1 is not None:
                parts.append('Z%.3f' % tz1)
            if printing:
                if e_rel:
                    parts.append('E%.5f' % d_e)
                else:
                    s['e'] += d_e
                    parts.append('E%.5f' % s['e'])
            elif d_e is not None and d_e < -_MIN_E:
                # Wipe-retract move (XY travel combined with negative E)
                s['ret'] += -d_e
                if e_rel:
                    parts.append('E%.5f' % d_e)
                else:
                    s['e'] += d_e
                    parts.append('E%.5f' % s['e'])
            if f_use and ((f_val is not None and f_val > 0)
                          or s['last_f'] is None
                          or abs(s['last_f'] - f_use) > 1e-4):
                parts.append('F%g' % f_use)
                s['last_f'] = f_use
            fo.write(' '.join(parts) + '\n')
            pos_ref[0], pos_ref[1], pos_ref[2] = x1, y1, z1

        def seg(x0, y0, z0, x1, y1, z1, d_e, f_val, cmd):
            """One input segment, split accurately at the cutting plane."""
            nonlocal segs_up, segs_lo
            w0 = w_of(x0, y0, z0)
            w1 = w_of(x1, y1, z1)
            if w0 >= 0 and w1 >= 0:
                if fo_up:
                    emit('U', x0, y0, z0, x1, y1, z1, d_e, f_val, cmd)
                    segs_up += 1
            elif w0 < 0 and w1 < 0:
                if fo_lo:
                    emit('L', x0, y0, z0, x1, y1, z1, d_e, f_val, cmd)
                    segs_lo += 1
            else:
                t = w0 / (w0 - w1) if abs(w0 - w1) > 1e-12 else 0.5
                t = min(1.0, max(0.0, t))
                sx = x0 + (x1 - x0) * t
                sy = y0 + (y1 - y0) * t
                sz = z0 + (z1 - z0) * t
                da = d_e * t if d_e is not None else None
                db = (d_e - da) if d_e is not None else None
                f_split = (f_val if (f_val is not None and f_val > 0)
                           else cur_f)
                if w0 >= 0:      # starts upper, ends lower
                    if fo_up:
                        emit('U', x0, y0, z0, sx, sy, sz, da, f_split, cmd)
                        segs_up += 1
                    if fo_lo:
                        emit('L', sx, sy, sz, x1, y1, z1, db, f_split, cmd)
                        segs_lo += 1
                else:            # starts lower, ends upper
                    if fo_lo:
                        emit('L', x0, y0, z0, sx, sy, sz, da, f_split, cmd)
                        segs_lo += 1
                    if fo_up:
                        emit('U', sx, sy, sz, x1, y1, z1, db, f_split, cmd)
                        segs_up += 1

        with open(src, errors='replace') as fi:
            for line in fi:
                ls = line.rstrip('\r\n')
                if _is_stale_layer_line(ls):
                    continue
                if _TYPE_RE.match(ls):
                    cur_type_line = ls
                    cur_apply_line = None
                    cur_apply_key = None
                    continue
                ma = _APPLY_RE.match(ls)
                if ma:
                    cur_apply_line = ls
                    cur_apply_key = ma.group(1)
                    continue
                mode, mbody = _parse_mode(ls)
                if mode == 'M83':
                    e_rel = True
                    for s in st.values():
                        if s['fo']:
                            s['fo'].write('M83\n')
                    continue
                if mode == 'M82':
                    e_rel = False
                    for s in st.values():
                        if s['fo']:
                            s['fo'].write('M82\n')
                    continue
                if mode == 'G90':
                    xyz_rel = False
                    for s in st.values():
                        if s['fo']:
                            s['fo'].write('G90\n')
                            s['g90_sent'] = True
                    continue
                if mode == 'G91':
                    # Decode relative source coordinates internally; output
                    # streams always emit absolute XYZ coordinates (G90).
                    xyz_rel = True
                    continue
                if mode == 'G92':
                    gx = _tok(mbody, 'X')
                    gy = _tok(mbody, 'Y')
                    gz = _tok(mbody, 'Z')
                    ge = _tok(mbody, 'E')
                    if gx is not None:
                        px = gx
                    if gy is not None:
                        py = gy
                    if gz is not None:
                        cur_z = gz
                    if ge is not None:
                        last_e = ge
                        src_ret = 0.0
                        for s in st.values():
                            s['e'] = ge
                            s['ret'] = 0.0
                            if s['fo']:
                                s['fo'].write('G92 E%g\n' % ge)
                    continue

                g = _parse_move(ls)
                if g is not None:
                    z_prev = cur_z
                    nz = _resolve_axis(cur_z, g[3], xyz_rel)
                    cur_z = nz
                    f_in = g[5]
                    if f_in is not None and f_in > 0:
                        cur_f = f_in
                    eff_erel = e_rel or xyz_rel
                    d_e = None
                    if g[4] is not None:
                        if eff_erel:
                            d_e = g[4]
                            if not e_rel and last_e is not None:
                                # Klipper G91 with M82: E is relative for the
                                # move and advances the logical E coordinate.
                                last_e += d_e
                        else:
                            d_e = g[4] - (last_e if last_e is not None
                                          else g[4])
                            last_e = g[4]

                    has_x = g[1] is not None
                    has_y = g[2] is not None
                    has_z = g[3] is not None
                    if not has_x and not has_y:
                        z_here = nz if nz is not None else 0.0
                        if px is not None and py is not None and has_z:
                            z0 = z_prev if z_prev is not None else z_here
                            if d_e is not None and d_e < -_MIN_E:
                                src_ret += -d_e
                            elif d_e is not None and d_e > _MIN_E and src_ret > _MIN_E:
                                rec = min(d_e, src_ret)
                                src_ret = max(0.0, src_ret - rec)
                            seg(px, py, z0, px, py, z_here, d_e, f_in, g[0])
                        elif px is not None and py is not None and d_e is not None:
                            side = 'U' if w_of(px, py, z_here) >= 0 else 'L'
                            s = st[side]
                            if d_e < -_MIN_E:
                                src_ret += -d_e
                                emit(side, px, py, z_here, px, py, z_here,
                                     d_e, f_in, g[0], e_only=True)
                            elif d_e > _MIN_E:
                                src_rec = min(d_e, src_ret)
                                src_ret = max(0.0, src_ret - src_rec)
                                prime = d_e - src_rec
                                use_rec = min(src_rec, s['ret'])
                                s['ret'] = max(0.0, s['ret'] - src_rec)
                                use_e = use_rec + prime
                                if use_e > _MIN_E:
                                    emit(side, px, py, z_here, px, py, z_here,
                                         use_e, f_in, g[0], e_only=True)
                        continue

                    xx1 = _resolve_axis(px, g[1], xyz_rel)
                    yy1 = _resolve_axis(py, g[2], xyz_rel)
                    z1 = nz if nz is not None else 0.0
                    if d_e is not None and d_e < -_MIN_E:
                        src_ret += -d_e
                    elif d_e is not None and d_e > _MIN_E:
                        src_ret = 0.0
                    if px is not None and py is not None \
                            and xx1 is not None and yy1 is not None:
                        z_start = z_prev if z_prev is not None else z1
                        seg(px, py, z_start, xx1, yy1, z1, d_e, f_in, g[0])
                    elif xx1 is not None and yy1 is not None:
                        side = 'U' if w_of(xx1, yy1, z1) >= 0 else 'L'
                        emit(side, xx1, yy1, z1, xx1, yy1, z1,
                             None, f_in, g[0])
                    if xx1 is not None:
                        px = xx1
                    if yy1 is not None:
                        py = yy1
                    continue

                ga = _parse_arc(ls)
                if ga is not None and px is not None and py is not None:
                    z_prev = cur_z
                    nz = _resolve_axis(cur_z, ga[3], xyz_rel)
                    ax = _resolve_axis(px, ga[1], xyz_rel)
                    ay = _resolve_axis(py, ga[2], xyz_rel)
                    f_in = ga[8]
                    if f_in is not None and f_in > 0:
                        cur_f = f_in
                    pts = _arc_points(px, py, ax, ay, i=ga[4], j=ga[5],
                                      rr=ga[6], cw=(ga[0] == 'G2'))
                    if pts:
                        cur_z = nz
                        z1 = nz if nz is not None else 0.0
                        z0 = z_prev if z_prev is not None else z1
                        chain = [(px, py)] + pts
                        lens = [math.hypot(b[0] - a[0], b[1] - a[1])
                                for a, b in zip(chain, chain[1:])]
                        tot = sum(lens) or 1.0
                        eff_erel = e_rel or xyz_rel
                        d_arc = None
                        if ga[7] is not None:
                            if eff_erel:
                                raw_de = ga[7]
                                if not e_rel and last_e is not None:
                                    last_e += raw_de
                            else:
                                raw_de = ga[7] - (last_e if last_e is not None
                                                  else ga[7])
                                last_e = ga[7]
                            if abs(raw_de) > _MIN_E:
                                d_arc = raw_de
                                if d_arc > _MIN_E:
                                    src_ret = 0.0
                                else:
                                    src_ret += -d_arc
                        cum = 0.0
                        za = z0
                        f_arc = f_in if (f_in is not None and f_in > 0) else cur_f
                        for idx, ((ax0, ay0), (bx1, by1), ln) in enumerate(
                                zip(chain, chain[1:], lens)):
                            cum += ln
                            zb = z0 + (z1 - z0) * (cum / tot)
                            frac = ln / tot
                            d_part = (d_arc * frac) if d_arc is not None else None
                            seg(ax0, ay0, za, bx1, by1, zb, d_part,
                                f_arc if idx == 0 else None, 'G1')
                            za = zb
                        px, py = ax, ay
                        continue

                for s in st.values():
                    if s['fo']:
                        s['fo'].write(ls + '\n')

        if fo_up:
            fo_up.close()
            fo_up = None
        if fo_lo:
            fo_lo.close()
            fo_lo = None

        if want_up:
            meta_u = ('; R2-CAKE: PART=UPPER LAYERS=%d LAYER_HEIGHT=%.3f\n'
                      % (st['U']['layers'], lh))
            _finalize_atomic(tmp_up, dst_up, meta_u,
                             st['U']['layers'], st['U']['types'])
        if want_lo:
            meta_l = ('; R2-CAKE: PART=LOWER LAYERS=%d LAYER_HEIGHT=%.3f\n'
                      % (st['L']['layers'], lh))
            _finalize_atomic(tmp_lo, dst_lo, meta_l,
                             st['L']['layers'], st['L']['types'])
    finally:
        for fo in (fo_up, fo_lo):
            if fo is not None:
                try:
                    fo.close()
                except OSError:
                    pass
        for tp in (tmp_up, tmp_lo):
            if tp is not None and os.path.exists(tp):
                try:
                    os.unlink(tp)
                except OSError:
                    pass

    info = {'file': [os.path.basename(p) for p in paths],
            'src': base, 'yaw': yaw, 'pitch': pitch, 'roll': roll,
            'z_offset': z_offset, 'normal': n, 'part': part,
            'reorient': bool(reorient),
            'segments_upper': segs_up, 'segments_lower': segs_lo,
            'layers_upper': st['U']['layers'],
            'layers_lower': st['L']['layers'],
            'upper_size': (max_up[0] - min_up[0], max_up[1] - min_up[1],
                           max_up[2] - min_up[2]),
            'lower_size': (max_lo[0] - min_lo[0], max_lo[1] - min_lo[1],
                           max_lo[2] - min_lo[2]),
            'first_layer_z': z_first}
    return paths, info
