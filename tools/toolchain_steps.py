#!/usr/bin/env python3
# ============================================================================
# toolchain_steps.py — die ECHTEN System-Werkzeuge als step_runner (Phase 2b/1)
# ============================================================================
# Jeder Adapter ruft die echte Engine des Systems und überführt deren Ausgabe
# auf den vom PLAN geforderten Ausgabe-Pfad:
#
#   range   -> r2_postproc.make_range (r2_postproc.py:1937, Rückgabe out,n)
#   scale   -> r2_postproc.apply_scale (:23861, Prozent -> Faktor, sxt/syt-
#              Taper, E wird je Zug mitgerechnet, auf dem Bett zentriert)
#   twist   -> r2_postproc.apply_twist (:24186, Grad um Z)
#   mirror  -> r2_postproc.apply_mirror (:24442, Achse; LCD-Index 0=X, 1=Y —
#              lcd_menues.cfg:3981)
#   texture -> r2_texture.apply_texture (r2_texture.py:672, BUMPS-Modus mit
#              Muster/Skalen/Tiefe/Richtung/Seed; zsize=0 -> None wie im
#              Watcher, r2_postproc.py:28276)
#
# Die Engines benennen ihre Ausgaben selbst (z. B. <stem>_L10-40.gcode) —
# der Plan diktiert Vnn_<stem>.gcode. Der Adapter verschiebt (os.replace,
# gleiches Dateisystem: out_dir == Workspace des Schritts). Engine-Metadaten
# (_meta_finalize-Sidecars) entstehen pro Zwischenstand und sind für die
# Kette bedeutungslos; die ENDAUSGabe bekommt ihre Meta in Phase 2b/2 vom
# Watcher-Verbund (dokumentiert, hier nicht erfunden).
#
# Bewusst NICHT drin (Phase 2b/2): Watcher-Nonce, Makro, LCD, _spawn_job,
# Moonraker-Meldungen, Ausgabemodus-Registrierung. Diese Adapter sind die
# offline prüfbare Brücke zwischen run_chain() und dem System.
#
# Import der Engines ist LAZY (R91-Regel) und per importlib aus dem Repo-Pfad
# (Muster: tools/v1_range_cause_check.py::load_pp) — kein Paket nötig.
# ============================================================================

import importlib.util
import os

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PP = None
_TEX = None

# Werkzeuge, für die es echte Adapter gibt (cake bleibt gesperrt: 2 Ausgaben;
# mold R270: Ketten sind einseitig - part=BOTH lehnt der Adapter ab, das
# LCD-Menü des Generators liegt in __gen __mold, nicht in __mods).
SYSTEM_TOOLS = ('range', 'scale', 'texture', 'twist', 'mirror', 'mold')


def _engines():
    """Lazy-Import der aktiven Engines (kostet nichts, solange nicht gebraucht)."""
    global _PP, _TEX
    if _PP is None:
        spec = importlib.util.spec_from_file_location(
            'r2_postproc_steps', os.path.join(_ROOT, 'tools', 'r2_postproc.py'))
        _PP = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(_PP)
        spec2 = importlib.util.spec_from_file_location(
            'r2_texture_steps', os.path.join(_ROOT, 'tools', 'r2_texture.py'))
        _TEX = importlib.util.module_from_spec(spec2)
        spec2.loader.exec_module(_TEX)
    return _PP, _TEX


def _pick(params, *names, default=None):
    """Akzeptiert Anker-Namen (start) UND Menü-Namen (range_start)."""
    for name in names:
        if name in params and params[name] is not None:
            return params[name]
    return default


def _relocate(engine_out, out_path):
    """Engine-Ausgabe -> Plan-Pfad (Verschieben, kein Kopieren)."""
    if os.path.abspath(engine_out) != os.path.abspath(out_path):
        os.replace(engine_out, out_path)
    return out_path


def system_step_runner(tool, params, bed=None):
    """Baut einen step_runner(step, in_path, out_path) für ein echtes Werkzeug.

    bed=(x0, y0, x1, y1) ist optional — ohne Angabe fragt der Adapter
    _bed_limits am Eingabepfad (Kette aus printer.cfg / Ender-3-Default,
    r2_postproc.py:6010). Fehler der Engine (ValueError mit Ursache/Abhilfe)
    fliegen weiter — run_chain macht daraus einen fehlgeschlagenen Schritt
    mit nachvollziehbarem Zwischenstand.
    """
    if tool not in SYSTEM_TOOLS:
        raise ValueError('kein System-Adapter fuer %r (verfuegbar: %s)'
                         % (tool, ', '.join(SYSTEM_TOOLS)))
    pp, tex = _engines()

    def runner(step, in_path, out_path):
        workspace = os.path.dirname(os.path.abspath(out_path))
        limits = bed or pp._bed_limits(in_path)

        if tool == 'range':
            out, _layers = pp.make_range(
                in_path,
                int(_pick(params, 'start', 'range_start')),
                int(_pick(params, 'end', 'range_end')),
                floor=int(_pick(params, 'floor', 'range_floor', default=0) or 0),
                top=int(_pick(params, 'top', 'range_top', default=0) or 0),
                brim=int(_pick(params, 'brim', 'range_brim', default=0) or 0),
                out_dir=workspace)
            _relocate(out, out_path)

        elif tool == 'scale':
            sx = float(_pick(params, 'x', 'scale_x', default=100)) / 100.0
            sy = float(_pick(params, 'y', 'scale_y', default=100)) / 100.0
            sxt = float(_pick(params, 'top_x', 'scale_top_x',
                              default=0) or 0) / 100.0
            syt = float(_pick(params, 'top_y', 'scale_top_y',
                              default=0) or 0) / 100.0
            out, _info = pp.apply_scale(
                in_path, sx=sx, sy=sy,
                sxt=sxt if sxt else None, syt=syt if syt else None,
                out_dir=workspace, bed=limits)
            _relocate(out, out_path)

        elif tool == 'twist':
            out, _info = pp.apply_twist(
                in_path,
                deg=float(_pick(params, 'deg', 'twist_deg', default=30.0)),
                out_dir=workspace, bed=limits)
            _relocate(out, out_path)

        elif tool == 'mirror':
            axis = _pick(params, 'axis', 'mirror_axis', default='x')
            if isinstance(axis, bool):
                raise ValueError('mirror: Achse ist X oder Y (oder LCD-Index '
                                 '0/1), kein Boolean')
            if isinstance(axis, int):
                # LCD-Index: 0 = X, 1 = Y (menus/lcd_menues.cfg:3981)
                axis = ('x', 'y')[axis] if axis in (0, 1) else 'x'
            out, _info = pp.apply_mirror(
                in_path, axis=str(axis).lower(),
                out_dir=workspace, bed=limits)
            _relocate(out, out_path)

        elif tool == 'mold':
            # R270 (J2): the casting mold around the CURRENT file. Chains
            # are single-sided: part=BOTH writes TWO files (bottom + top)
            # and stays refused - the cake rule; the standalone LCD path
            # (mold_nonce via the __gen menu) does BOTH.
            part = str(_pick(params, 'part', 'mold_part',
                             default='TOP') or 'TOP').upper()
            if part == 'BOTH':
                raise ValueError('mold: part=BOTH schreibt ZWEI Dateien '
                                 '(Unten + Oben) und bleibt in Ketten '
                                 'gesperrt - part TOP oder BOTTOM waehlen '
                                 '(beide Haelften: das Generator-Menue)')
            funnel = str(_pick(params, 'funnel', 'mold_funnel',
                               default='CONICAL') or 'CONICAL').upper()
            plane = str(_pick(params, 'plane', 'mold_plane',
                              default='AUTO') or 'AUTO').upper()
            out, _info = pp.make_mold(
                in_path,
                wall=float(_pick(params, 'wall', 'mold_wall', default=5.0)),
                gap=float(_pick(params, 'gap', 'mold_gap', default=0.15)),
                pour_d=float(_pick(params, 'pour', 'mold_pour',
                                   default=8.0)),
                funnel='NONE' if funnel == 'NONE' else 'CONICAL',
                vent_d=float(_pick(params, 'vent', 'mold_vent',
                                   default=2.5)),
                pin_d=float(_pick(params, 'pin', 'mold_pin', default=3.0)),
                draft=float(_pick(params, 'draft', 'mold_draft',
                                  default=0.0)),
                part=part,
                plane=('OFF' if plane == 'OFF'
                       else ('MID' if plane == 'MID' else 'AUTO')),
                z_off=float(_pick(params, 'zoff', 'mold_zoff', default=0.0)),
                out_dir=workspace, bed=limits)
            _relocate(out, out_path)

        elif tool == 'texture':
            zsize = _pick(params, 'zsize_mm', 'texture_zsize', default=0)
            out, _info = tex.apply_texture(
                in_path,
                out_dir=workspace,
                mode='BUMPS',
                bump_pattern=str(_pick(params, 'pattern', 'bump_pattern',
                                       default='GRID')).upper(),
                bump_scale=float(_pick(params, 'scale_mm', 'texture_scale',
                                       default=10.0)),
                bump_amp=float(_pick(params, 'depth_mm', 'texture_amp',
                                     default=0.35)),
                direction=str(_pick(params, 'direction', 'texture_dir',
                                    default='OUT')).upper(),
                seed=int(float(_pick(params, 'seed', 'texture_seed',
                                     default=91))),
                zsize=float(zsize) if zsize else None,
                bed=limits)
            _relocate(out, out_path)

        return None

    return runner


def system_runner_for_plan(plan, bed=None):
    """Bequemlichkeit: step_runner-Map fuer einen Plan (je Schritt ein Adapter)."""
    runners = {}
    for step in plan['steps']:
        runners[step['job']] = system_step_runner(
            step['tool'], step.get('params', {}), bed=bed)
    return runners


def plan_step_runner(plan, bed=None):
    """R259 (Phase 2b/2): EIN step_runner fuer den GESAMTEN Plan.

    run_chain(step, in_path, out_path) verlangt ein einzelnes Callable —
    hier wird je Schritt auf den Adapter seines Werkzeugs weitergeleitet
    (gemischte Ketten: Scale -> Twist -> Mirror -> ...). bed=(x0,y0,x1,y1)
    wird EINMAL von aussen uebergeben (der Watcher misst es am ORIGINAL-
    Eingabepfad) und gilt fuer alle Schritte.
    """
    runners = system_runner_for_plan(plan, bed=bed)

    def runner(step, in_path, out_path):
        return runners[step['job']](step, in_path, out_path)

    return runner
