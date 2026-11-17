#!/usr/bin/env python3
"""Read-only Klipper machine-profile parser and G-code compatibility checker.

Parses a Klipper `printer.cfg` (with safe, root-contained `[include ...]`
expansion and `#*# SAVE_CONFIG` override tracking) into a deterministic
`r2-machine-profile/1` JSON structure, runs static config consistency checks
(axis bounds, probe-adjusted bed_mesh reach, thermal limits, dual-Z, R2 Studio
section prerequisites), and checks `r2-evidence/1` summaries against declared
machine capabilities and build volume.

Never modifies config files, never communicates with hardware/UART/Moonraker,
and never substitutes missing values with silent guesses.
"""
import argparse
import glob
import hashlib
import json
import math
from pathlib import Path
import re
import sys

SECTION_RE = re.compile(r'^\s*\[\s*([^\]]+?)\s*\]\s*(?:[#;].*)?$')
KV_RE = re.compile(r'^([A-Za-z0-9_]+)\s*[:=]\s*(.*)$')
SAVE_CFG_HDR = '#*# <---------------------- SAVE_CONFIG ---------------------->'
SAVE_CFG_PREFIX = '#*#'
MAX_INCLUDE_FILES = 128
MAX_CFG_BYTES = 8 * 1024 * 1024

R2_REQUIRED_CAPABILITIES = (
    'save_variables',
    'virtual_sdcard',
    'pause_resume',
    'respond',
    'exclude_object',
    'firmware_retraction',
)


def _strip_inline_comment(val):
    # Klipper treats unquoted '#' or ';' preceded by whitespace as inline comment.
    m = re.search(r'(?:^|\s)[#;]', val)
    if m:
        return val[:m.start()].strip()
    return val.strip()


def _parse_float(sec, key, raw, diagnostics):
    if raw is None:
        return None
    txt = _strip_inline_comment(str(raw))
    if not txt:
        return None
    try:
        v = float(txt)
    except ValueError:
        diagnostics.append({
            'severity': 'error',
            'code': 'INVALID_NUMBER',
            'section': sec,
            'key': key,
            'detail': f'cannot parse float from {txt!r}',
        })
        return None
    if not math.isfinite(v):
        diagnostics.append({
            'severity': 'error',
            'code': 'NONFINITE_NUMBER',
            'section': sec,
            'key': key,
            'detail': f'non-finite value {txt!r}',
        })
        return None
    return v


def _parse_xy_pair(sec, key, raw, diagnostics):
    if raw is None:
        return None
    txt = _strip_inline_comment(str(raw))
    parts = [p.strip() for p in txt.split(',')]
    if len(parts) != 2:
        diagnostics.append({
            'severity': 'error',
            'code': 'INVALID_PAIR',
            'section': sec,
            'key': key,
            'detail': f'expected "x, y" pair, got {txt!r}',
        })
        return None
    x = _parse_float(sec, key, parts[0], diagnostics)
    y = _parse_float(sec, key, parts[1], diagnostics)
    if x is None or y is None:
        return None
    return [x, y]


def _parse_int_pair(sec, key, raw, diagnostics):
    if raw is None:
        return None
    txt = _strip_inline_comment(str(raw))
    parts = [p.strip() for p in txt.split(',')]
    if len(parts) == 1 and parts[0].isdigit():
        n = int(parts[0])
        return [n, n] if n > 0 else None
    if len(parts) == 2 and all(p.isdigit() for p in parts):
        a, b = int(parts[0]), int(parts[1])
        if a > 0 and b > 0:
            return [a, b]
    diagnostics.append({
        'severity': 'error',
        'code': 'INVALID_PROBE_COUNT',
        'section': sec,
        'key': key,
        'detail': f'expected positive int or "nx, ny", got {txt!r}',
    })
    return None


def _parse_cfg_lines(lines, sections, *, is_save_cfg=False, save_keys=None,
                     on_include=None):
    cur_sec = None
    cur_key = None
    for raw in lines:
        line = raw.rstrip('\r\n')
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(('#', ';')):
            continue
        msec = SECTION_RE.match(line)
        if msec:
            sec_name = ' '.join(msec.group(1).strip().split())
            cur_key = None
            if not is_save_cfg and sec_name.lower().startswith('include '):
                pattern = sec_name.split(None, 1)[1].strip()
                cur_sec = None
                if on_include is not None:
                    on_include(pattern)
                continue
            cur_sec = sec_name
            sections.setdefault(cur_sec, {})
            continue
        if cur_sec is None:
            continue
        if line[0] in (' ', '\t'):
            if cur_key is not None:
                prev = sections[cur_sec].get(cur_key, '')
                sections[cur_sec][cur_key] = (
                    (prev + '\n' + stripped) if prev else stripped
                )
            continue
        mkv = KV_RE.match(line)
        if mkv:
            k = mkv.group(1).strip().lower()
            v = mkv.group(2).strip()
            sections[cur_sec][k] = v
            cur_key = k
            if is_save_cfg and save_keys is not None:
                save_keys.add((cur_sec, k))


def load_machine_profile(cfg_path, *, follow_includes=True, root_dir=None):
    """Read-only parse of a Klipper config into an `r2-machine-profile/1` dict."""
    entry = Path(cfg_path)
    if entry.is_symlink():
        raise ValueError(f'symlink config refused: {cfg_path}')
    entry_res = entry.resolve(strict=True)
    if not entry_res.is_file():
        raise ValueError(f'config is not a regular file: {cfg_path}')
    root = (Path(root_dir).resolve(strict=True)
            if root_dir is not None else entry_res.parent)
    try:
        entry_res.relative_to(root)
    except ValueError as exc:
        raise ValueError(f'config {entry_res} outside root {root}') from exc

    sections = {}
    save_cfg_lines = []
    save_keys = set()
    included_files = []
    diagnostics = []
    active_stack = []
    seen_total = 0
    total_bytes = 0

    def _read_one(fpath, is_entry=False):
        nonlocal seen_total, total_bytes
        if fpath in active_stack:
            raise ValueError(f'cyclic [include] detected: {fpath.name}')
        seen_total += 1
        if seen_total > MAX_INCLUDE_FILES:
            raise ValueError(f'exceeded max include file count ({MAX_INCLUDE_FILES})')
        raw_bytes = fpath.read_bytes()
        total_bytes += len(raw_bytes)
        if total_bytes > MAX_CFG_BYTES:
            raise ValueError('config tree exceeds 8 MiB safety limit')
        rel = fpath.relative_to(root).as_posix()
        included_files.append({
            'path': rel,
            'bytes': len(raw_bytes),
            'sha256': hashlib.sha256(raw_bytes).hexdigest(),
        })
        text = raw_bytes.decode('utf-8', errors='replace')
        normal_lines = []
        in_save = False
        for ln in text.splitlines():
            if is_entry and ln.strip() == SAVE_CFG_HDR:
                in_save = True
                continue
            if in_save:
                if ln.startswith(SAVE_CFG_PREFIX):
                    sub = ln[len(SAVE_CFG_PREFIX):]
                    if sub.startswith(' '):
                        sub = sub[1:]
                    save_cfg_lines.append(sub)
                continue
            normal_lines.append(ln)

        def _handle_include(pat):
            if not follow_includes:
                diagnostics.append({
                    'severity': 'info',
                    'code': 'INCLUDE_SKIPPED',
                    'section': f'include {pat}',
                    'key': None,
                    'detail': 'follow_includes=False; included file not read',
                })
                return
            if Path(pat).is_absolute() or '..' in Path(pat).parts:
                raise ValueError(f'unsafe [include] path refused: {pat!r}')
            glob_pat = str(fpath.parent / pat)
            matches = sorted(glob.glob(glob_pat))
            if not matches and not any(ch in pat for ch in '*?['):
                diagnostics.append({
                    'severity': 'warning',
                    'code': 'INCLUDE_MISSING',
                    'section': f'include {pat}',
                    'key': None,
                    'detail': f'included file not found: {pat}',
                })
                return
            for m in matches:
                mp = Path(m)
                if mp.is_symlink():
                    raise ValueError(f'symlink [include] refused: {pat!r}')
                mres = mp.resolve(strict=True)
                try:
                    mres.relative_to(root)
                except ValueError as exc:
                    raise ValueError(
                        f'[include] escapes config root: {pat!r}') from exc
                if mres.is_file():
                    _read_one(mres, is_entry=False)

        active_stack.append(fpath)
        try:
            _parse_cfg_lines(normal_lines, sections, is_save_cfg=False,
                             on_include=_handle_include)
        finally:
            active_stack.pop()

    _read_one(entry_res, is_entry=True)
    if save_cfg_lines:
        _parse_cfg_lines(save_cfg_lines, sections, is_save_cfg=True,
                         save_keys=save_keys)

    # Extract [printer]
    psec = sections.get('printer', {})
    kin_type = _strip_inline_comment(psec.get('kinematics', '')) or None
    kinematics = {
        'kinematics': kin_type,
        'max_velocity_mm_s': _parse_float('printer', 'max_velocity',
                                          psec.get('max_velocity'), diagnostics),
        'max_accel_mm_s2': _parse_float('printer', 'max_accel',
                                        psec.get('max_accel'), diagnostics),
        'max_z_velocity_mm_s': _parse_float('printer', 'max_z_velocity',
                                            psec.get('max_z_velocity'), diagnostics),
        'max_z_accel_mm_s2': _parse_float('printer', 'max_z_accel',
                                          psec.get('max_z_accel'), diagnostics),
        'square_corner_velocity_mm_s': _parse_float(
            'printer', 'square_corner_velocity',
            psec.get('square_corner_velocity'), diagnostics),
    }

    # Extract axes (never invent defaults for missing limits; Klipper defaults
    # position_min to 0.0 ONLY when stepper section exists and omits position_min)
    axes = {}
    build_volume = {}
    for ax in ('x', 'y', 'z'):
        sname = f'stepper_{ax}'
        if sname not in sections:
            axes[ax] = None
            build_volume[ax] = None
            continue
        s = sections[sname]
        has_pmin = 'position_min' in s
        pmin = (_parse_float(sname, 'position_min', s.get('position_min'), diagnostics)
                if has_pmin else 0.0)
        pmax = _parse_float(sname, 'position_max', s.get('position_max'), diagnostics)
        pend = _parse_float(sname, 'position_endstop', s.get('position_endstop'),
                            diagnostics)
        hspd = _parse_float(sname, 'homing_speed', s.get('homing_speed'), diagnostics)
        axes[ax] = {
            'position_min_mm': pmin,
            'position_min_explicit': has_pmin,
            'position_max_mm': pmax,
            'position_endstop_mm': pend,
            'homing_speed_mm_s': hspd,
        }
        if ax == 'z':
            axes[ax]['dual_z'] = ('stepper_z1' in sections)
        if pmin is not None and pmax is not None:
            if pmin >= pmax:
                diagnostics.append({
                    'severity': 'error',
                    'code': 'INVALID_AXIS_RANGE',
                    'section': sname,
                    'key': 'position_max',
                    'detail': f'position_min ({pmin}) >= position_max ({pmax})',
                })
                build_volume[ax] = None
            else:
                build_volume[ax] = [pmin, pmax]
        else:
            build_volume[ax] = None

    # Extract [extruder]
    esec = sections.get('extruder')
    extruder = None
    if esec is not None:
        noz = _parse_float('extruder', 'nozzle_diameter',
                           esec.get('nozzle_diameter'), diagnostics)
        fil = _parse_float('extruder', 'filament_diameter',
                           esec.get('filament_diameter'), diagnostics)
        tmin = _parse_float('extruder', 'min_temp', esec.get('min_temp'), diagnostics)
        tmax = _parse_float('extruder', 'max_temp', esec.get('max_temp'), diagnostics)
        temin = _parse_float('extruder', 'min_extrude_temp',
                             esec.get('min_extrude_temp'), diagnostics)
        extruder = {
            'nozzle_diameter_mm': noz,
            'filament_diameter_mm': fil,
            'min_temp_c': tmin,
            'max_temp_c': tmax,
            'min_extrude_temp_c': temin,
            'max_extrude_only_distance_mm': _parse_float(
                'extruder', 'max_extrude_only_distance',
                esec.get('max_extrude_only_distance'), diagnostics),
            'max_extrude_cross_section_mm2': _parse_float(
                'extruder', 'max_extrude_cross_section',
                esec.get('max_extrude_cross_section'), diagnostics),
            'pressure_advance': _parse_float(
                'extruder', 'pressure_advance',
                esec.get('pressure_advance'), diagnostics),
        }
        if noz is not None and noz <= 0:
            diagnostics.append({
                'severity': 'error', 'code': 'INVALID_NOZZLE_DIAMETER',
                'section': 'extruder', 'key': 'nozzle_diameter',
                'detail': f'nozzle_diameter must be > 0, got {noz}',
            })
        if fil is not None and fil <= 0:
            diagnostics.append({
                'severity': 'error', 'code': 'INVALID_FILAMENT_DIAMETER',
                'section': 'extruder', 'key': 'filament_diameter',
                'detail': f'filament_diameter must be > 0, got {fil}',
            })
        if noz is not None and fil is not None and noz > fil > 0:
            diagnostics.append({
                'severity': 'error', 'code': 'NOZZLE_EXCEEDS_FILAMENT',
                'section': 'extruder', 'key': 'nozzle_diameter',
                'detail': f'nozzle_diameter ({noz}) > filament_diameter ({fil})',
            })
        if tmin is not None and tmax is not None and tmin >= tmax:
            diagnostics.append({
                'severity': 'error', 'code': 'INVALID_TEMP_RANGE',
                'section': 'extruder', 'key': 'max_temp',
                'detail': f'min_temp ({tmin}) >= max_temp ({tmax})',
            })
        if temin is not None and tmax is not None and temin > tmax:
            diagnostics.append({
                'severity': 'error', 'code': 'INVALID_MIN_EXTRUDE_TEMP',
                'section': 'extruder', 'key': 'min_extrude_temp',
                'detail': f'min_extrude_temp ({temin}) > max_temp ({tmax})',
            })

    # Extract [heater_bed]
    bsec = sections.get('heater_bed')
    heater_bed = None
    if bsec is not None:
        btmin = _parse_float('heater_bed', 'min_temp', bsec.get('min_temp'), diagnostics)
        btmax = _parse_float('heater_bed', 'max_temp', bsec.get('max_temp'), diagnostics)
        heater_bed = {'min_temp_c': btmin, 'max_temp_c': btmax}
        if btmin is not None and btmax is not None and btmin >= btmax:
            diagnostics.append({
                'severity': 'error', 'code': 'INVALID_TEMP_RANGE',
                'section': 'heater_bed', 'key': 'max_temp',
                'detail': f'min_temp ({btmin}) >= max_temp ({btmax})',
            })

    # Extract probe ([bltouch] / [probe] / [smart_effector])
    probe = None
    for ptype in ('bltouch', 'probe', 'smart_effector'):
        if ptype in sections:
            ps = sections[ptype]
            xoff = (_parse_float(ptype, 'x_offset', ps.get('x_offset'), diagnostics)
                    if 'x_offset' in ps else 0.0)
            yoff = (_parse_float(ptype, 'y_offset', ps.get('y_offset'), diagnostics)
                    if 'y_offset' in ps else 0.0)
            zoff = _parse_float(ptype, 'z_offset', ps.get('z_offset'), diagnostics)
            probe = {
                'type': ptype,
                'x_offset_mm': xoff,
                'y_offset_mm': yoff,
                'z_offset_mm': zoff,
                'z_offset_source': ('save_config' if (ptype, 'z_offset') in save_keys
                                    else ('config' if zoff is not None else None)),
            }
            break

    # Extract [bed_mesh] and validate probe-offset nozzle reach!
    msec = sections.get('bed_mesh')
    bed_mesh = None
    if msec is not None:
        mmin = _parse_xy_pair('bed_mesh', 'mesh_min', msec.get('mesh_min'), diagnostics)
        mmax = _parse_xy_pair('bed_mesh', 'mesh_max', msec.get('mesh_max'), diagnostics)
        pcnt = _parse_int_pair('bed_mesh', 'probe_count', msec.get('probe_count'),
                               diagnostics)
        bed_mesh = {
            'mesh_min_mm': mmin,
            'mesh_max_mm': mmax,
            'probe_count': pcnt,
            'horizontal_move_z_mm': _parse_float(
                'bed_mesh', 'horizontal_move_z',
                msec.get('horizontal_move_z'), diagnostics),
            'fade_start_mm': _parse_float(
                'bed_mesh', 'fade_start', msec.get('fade_start'), diagnostics),
            'fade_end_mm': _parse_float(
                'bed_mesh', 'fade_end', msec.get('fade_end'), diagnostics),
        }
        if mmin and mmax:
            if mmin[0] >= mmax[0] or mmin[1] >= mmax[1]:
                diagnostics.append({
                    'severity': 'error', 'code': 'INVALID_MESH_BOUNDS',
                    'section': 'bed_mesh', 'key': 'mesh_max',
                    'detail': f'mesh_min {mmin} must be strictly less than mesh_max {mmax}',
                })
            elif probe and probe['x_offset_mm'] is not None and probe['y_offset_mm'] is not None:
                # Klipper moves nozzle to (mesh_coord - probe_offset) to place probe at mesh_coord.
                for idx, ax_name, off in ((0, 'x', probe['x_offset_mm']),
                                          (1, 'y', probe['y_offset_mm'])):
                    bv = build_volume.get(ax_name)
                    if not bv:
                        continue
                    noz_min = mmin[idx] - off
                    noz_max = mmax[idx] - off
                    if noz_min < bv[0] - 1e-6 or noz_max > bv[1] + 1e-6:
                        diagnostics.append({
                            'severity': 'error',
                            'code': 'MESH_OUT_OF_AXIS_RANGE',
                            'section': 'bed_mesh',
                            'key': f'mesh_{ax_name}',
                            'detail': (
                                f'probe-adjusted nozzle {ax_name} [{noz_min:.2f}, {noz_max:.2f}] '
                                f'exceeds stepper_{ax_name} [{bv[0]:.2f}, {bv[1]:.2f}]'
                            ),
                        })

    # Gantry leveling checks
    if 'z_tilt' in sections and 'stepper_z1' not in sections:
        diagnostics.append({
            'severity': 'warning',
            'code': 'Z_TILT_SINGLE_Z',
            'section': 'z_tilt',
            'key': None,
            'detail': '[z_tilt] declared without [stepper_z1]',
        })

    # Capabilities
    arc_sec = sections.get('gcode_arcs')
    fwret_sec = sections.get('firmware_retraction')
    capabilities = {
        'gcode_arcs': arc_sec is not None,
        'arc_resolution_mm': (
            _parse_float('gcode_arcs', 'resolution', arc_sec.get('resolution'),
                         diagnostics)
            if arc_sec and 'resolution' in arc_sec
            else (1.0 if arc_sec is not None else None)
        ),
        'firmware_retraction': fwret_sec is not None,
        'retract_length_mm': (
            _parse_float('firmware_retraction', 'retract_length',
                         fwret_sec.get('retract_length'), diagnostics)
            if fwret_sec else None
        ),
        'retract_speed_mm_s': (
            _parse_float('firmware_retraction', 'retract_speed',
                         fwret_sec.get('retract_speed'), diagnostics)
            if fwret_sec else None
        ),
        'exclude_object': 'exclude_object' in sections,
        'pause_resume': 'pause_resume' in sections,
        'respond': 'respond' in sections,
        'save_variables': 'save_variables' in sections,
        'virtual_sdcard': 'virtual_sdcard' in sections,
        'display': any(s == 'display' or s.startswith('display ')
                       for s in sections),
        'input_shaper': 'input_shaper' in sections,
        'z_tilt': 'z_tilt' in sections,
        'quad_gantry_level': 'quad_gantry_level' in sections,
        'screws_tilt_adjust': 'screws_tilt_adjust' in sections,
    }

    gcode_macros = sorted(
        s.split(None, 1)[1] for s in sections
        if s.lower().startswith('gcode_macro ') and ' ' in s
    )
    delayed_gcodes = sorted(
        s.split(None, 1)[1] for s in sections
        if s.lower().startswith('delayed_gcode ') and ' ' in s
    )
    missing_r2 = [k for k in R2_REQUIRED_CAPABILITIES if not capabilities.get(k)]

    return {
        'schema': 'r2-machine-profile/1',
        'files': included_files,
        'section_count': len(sections),
        'kinematics': kinematics,
        'axes': axes,
        'build_volume_mm': build_volume,
        'extruder': extruder,
        'heater_bed': heater_bed,
        'probe': probe,
        'bed_mesh': bed_mesh,
        'capabilities': capabilities,
        'macros': {
            'gcode_macro_count': len(gcode_macros),
            'delayed_gcode_count': len(delayed_gcodes),
            'gcode_macros': gcode_macros,
            'delayed_gcodes': delayed_gcodes,
        },
        'save_config_overrides': [
            {'section': sec, 'key': key}
            for sec, key in sorted(save_keys)
        ],
        'r2_studio_prerequisites': {
            'ok': not missing_r2,
            'missing': missing_r2,
        },
        'diagnostics': diagnostics,
        'valid': not any(d['severity'] == 'error' for d in diagnostics),
        'note': 'read-only static config profile; live runtime overrides and hardware state not queried',
    }


def check_evidence_against_profile(evidence, profile):
    """Compare an `r2-evidence/1` dict against an `r2-machine-profile/1` dict."""
    if evidence.get('schema') != 'r2-evidence/1':
        raise ValueError('expected r2-evidence/1 payload')
    if profile.get('schema') != 'r2-machine-profile/1':
        raise ValueError('expected r2-machine-profile/1 payload')

    violations = []
    advisories = []
    bv = profile.get('build_volume_mm') or {}
    caps = profile.get('capabilities') or {}
    kin_cfg = profile.get('kinematics') or {}
    ext_cfg = profile.get('extruder') or {}
    kin_ev = evidence.get('kinematics') or {}

    # 1. Build-volume bounds check over positive-extrusion footprints
    for fp in evidence.get('object_footprints') or ():
        label = fp.get('object_name') or '<unassigned>'
        bxy = fp.get('bounds_xy_mm')
        if bxy and len(bxy) == 4:
            for ax_name, lo_v, hi_v in (('x', bxy[0], bxy[2]),
                                        ('y', bxy[1], bxy[3])):
                lim = bv.get(ax_name)
                if lim and (lo_v < lim[0] - 1e-4 or hi_v > lim[1] + 1e-4):
                    violations.append({
                        'code': f'OUT_OF_BOUNDS_{ax_name.upper()}',
                        'object': label,
                        'detail': (
                            f'{label} extrusion {ax_name.upper()} [{lo_v:.3f}, {hi_v:.3f}] '
                            f'exceeds machine [{lim[0]:.3f}, {lim[1]:.3f}] mm'
                        ),
                    })
        zlim = bv.get('z')
        zmin, zmax = fp.get('z_min_mm'), fp.get('z_max_mm')
        if zlim and zmin is not None and zmax is not None:
            if zmin < zlim[0] - 1e-4 or zmax > zlim[1] + 1e-4:
                violations.append({
                    'code': 'OUT_OF_BOUNDS_Z',
                    'object': label,
                    'detail': (
                        f'{label} extrusion Z [{zmin:.3f}, {zmax:.3f}] '
                        f'exceeds machine [{zlim[0]:.3f}, {zlim[1]:.3f}] mm'
                    ),
                })

    # 2. Firmware feature capability checks
    arc_total = (int(kin_ev.get('arc_extruding_moves') or 0)
                 + int(kin_ev.get('arc_travel_moves') or 0))
    if arc_total > 0 and not caps.get('gcode_arcs'):
        violations.append({
            'code': 'MISSING_GCODE_ARCS',
            'object': None,
            'detail': f'G-code contains {arc_total} G2/G3 arc move(s) but [gcode_arcs] is not configured',
        })

    fw_ret_total = (int(kin_ev.get('firmware_retracts') or 0)
                    + int(kin_ev.get('firmware_deretracts') or 0))
    if fw_ret_total > 0 and not caps.get('firmware_retraction'):
        violations.append({
            'code': 'MISSING_FIRMWARE_RETRACTION',
            'object': None,
            'detail': f'G-code uses G10/G11 ({fw_ret_total} call(s)) but [firmware_retraction] is not configured',
        })

    if (evidence.get('objects') or ()) and not caps.get('exclude_object'):
        violations.append({
            'code': 'MISSING_EXCLUDE_OBJECT',
            'object': None,
            'detail': 'G-code uses EXCLUDE_OBJECT_* commands but [exclude_object] is not configured',
        })

    # 3. Filament diameter compatibility
    cfg_fil = ext_cfg.get('filament_diameter_mm')
    ev_fil = kin_ev.get('filament_diameter_mm')
    if (cfg_fil is not None and ev_fil is not None
            and kin_ev.get('filament_diameter_source') == 'header_comment'
            and abs(cfg_fil - ev_fil) > 0.1):
        violations.append({
            'code': 'FILAMENT_DIAMETER_MISMATCH',
            'object': None,
            'detail': (
                f'G-code filament_diameter ({ev_fil} mm) differs from '
                f'[extruder] filament_diameter ({cfg_fil} mm)'
            ),
        })

    # 4. Velocity clamp advisory (Klipper clamps feedrate to max_velocity)
    vmax = kin_cfg.get('max_velocity_mm_s')
    if vmax is not None:
        for field in ('print_speed_max_mm_s', 'travel_speed_max_mm_s'):
            sv = kin_ev.get(field)
            if sv is not None and sv > vmax + 1e-3:
                advisories.append({
                    'code': 'SPEED_EXCEEDS_MAX_VELOCITY',
                    'field': field,
                    'detail': (
                        f'{field}={sv:.1f} mm/s exceeds [printer] max_velocity={vmax:.1f} mm/s '
                        '(Klipper clamps at runtime)'
                    ),
                })

    return {
        'schema': 'r2-machine-check/1',
        'ok': not violations,
        'profile_valid': bool(profile.get('valid')),
        'violations': violations,
        'advisories': advisories,
        'note': 'logical G-code vs static config check; start macros, G92 offsets and hardware state not proven',
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='command', required=True)
    ins = sub.add_parser('inspect', help='parse a Klipper cfg into r2-machine-profile/1 JSON')
    ins.add_argument('config', help='path to printer.cfg')
    ins.add_argument('--no-includes', action='store_true',
                     help='do not expand [include ...] directives')
    ins.add_argument('--root', default=None,
                     help='explicit containment root for [include ...] expansion')
    args = ap.parse_args(argv)
    try:
        prof = load_machine_profile(
            args.config,
            follow_includes=not args.no_includes,
            root_dir=args.root,
        )
    except (OSError, ValueError) as exc:
        print(f'r2-machine: {exc}', file=sys.stderr)
        return 1
    print(json.dumps(prof, ensure_ascii=True, indent=2, sort_keys=True))
    return 0


if __name__ == '__main__':
    sys.exit(main())
