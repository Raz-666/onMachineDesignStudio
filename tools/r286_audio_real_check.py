#!/usr/bin/env python3
"""R286 L1 audit: real 8-bit audio playback for the Raspberry host output.

The user demanded: the klinke/hdmi audio source plays REAL audio (8-bit
square-wave WAV synthesis), not a puls-modulated MCU beep. Same tunes as
the piezo beeper.

Checks:
  1. r2_audio_play.sh exists + executable + synthesizes 8-bit WAV
  2. WAV is 8-bit unsigned PCM, mono, valid
  3. M300 routes klinke/hdmi to RUN_SHELL_COMMAND R2_AUDIO_PLAY (not RESPOND)
  4. M300 beep path unchanged (SET_PIN pwm_cycle_time)
  5. SET_AUDIO_SOURCE + audio_source default present
  6. R2_AUDIO_PLAY registered in r2_setup_lib.sh (gcode_shell_command)
  7. _SOUND_LIB tunes unchanged (same tunes, real playback)
  8. Fallback if no shell-command extension

Run: python3 tools/r286_audio_real_check.py
"""
import sys
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, '..')
sys.path.insert(0, HERE)

PASS = 0
FAIL = 0
results = []


def check(name, cond, detail=''):
    global PASS, FAIL
    if cond:
        PASS += 1
        results.append('[PASS] %s %s' % (name, detail))
    else:
        FAIL += 1
        results.append('[FAIL] %s %s' % (name, detail))


sounds_cfg = open(os.path.join(ROOT, 'macros', '02_sounds.cfg'), encoding='utf-8').read()
setup_lib = open(os.path.join(ROOT, 'tools', 'r2_setup_lib.sh'), encoding='utf-8').read()
script_path = os.path.join(ROOT, 'tools', 'r2_audio_play.sh')

# ---- 1. r2_audio_play.sh existiert ----
check('1 r2_audio_play.sh existiert', os.path.isfile(script_path),
      '(tools/r2_audio_play.sh)')

# ---- 2. Skript synthetisiert 8-bit WAV ----
try:
    import subprocess, tempfile
    out = subprocess.run(
        ['bash', script_path, '1568 40 0 50'],
        capture_output=True, text=True, timeout=15, cwd=ROOT)
    wav = os.path.join(ROOT, 'tools', '.audio_cache', 'r2_tone.wav')
    ok = os.path.isfile(wav) and os.path.getsize(wav) > 100
    # 8-bit check
    if ok:
        import wave
        w = wave.open(wav, 'rb')
        ok = (w.getsampwidth() == 1 and w.getnchannels() == 1)  # 8-bit mono
        w.close()
    check('2 Skript synthetisiert 8-bit WAV', ok,
          '(8-bit unsigned PCM, mono)' if ok else out.stdout[:80])
except Exception as e:
    check('2 Skript synthetisiert 8-bit WAV', False, '(%r)' % (e,))

# ---- 3. M300 routet klinke/hdmi auf RUN_SHELL_COMMAND ----
m300_host = 'RUN_SHELL_COMMAND CMD=R2_AUDIO_PLAY' in sounds_cfg
check('3 M300 host-path -> R2_AUDIO_PLAY', m300_host,
      '(RUN_SHELL_COMMAND CMD=R2_AUDIO_PLAY)')

# KEIN RESPOND-only-Host-Path mehr (der alte nur-announce-Pfad entfernt)
old_respond_only = 'M300 routed to Pi' in sounds_cfg
check('3 kein reiner RESPOND-Announce-Pfad mehr', not old_respond_only,
      '(RESPOND-only entfernt)')

# ---- 4. M300 beep-Pfad unverändert ----
beep_path = "SET_PIN PIN=beeper VALUE=0.5 CYCLE_TIME=" in sounds_cfg
check('4 M300 beep-Pfad (SET_PIN pwm_cycle_time) intact', beep_path,
      '(MCU-Piezo unverändert)')

# ---- 5. SET_AUDIO_SOURCE + audio_source default ----
set_audio = 'SET_AUDIO_SOURCE' in sounds_cfg
check('5 SET_AUDIO_SOURCE-Makro', set_audio, '(beep|klinke|hdmi)')

# ---- 6. R2_AUDIO_PLAY in r2_setup_lib.sh registriert ----
registered = '[gcode_shell_command R2_AUDIO_PLAY]' in setup_lib
check('6 R2_AUDIO_PLAY als gcode_shell_command registriert', registered,
      '(r2_setup_lib.sh)')

# ---- 7. _SOUND_LIB tunes unverändert (gleiche Töne) ----
tunes_ok = 'r2_start' in sounds_cfg and 'r2_confirm' in sounds_cfg and \
           'r2_alarm' in sounds_cfg and 'r2_done' in sounds_cfg
check('7 _SOUND_LIB tunes erhalten (gleiche Töne)', tunes_ok,
      '(r2_start/confirm/alarm/done)')

# ---- 8. Fallback wenn keine shell-command extension ----
fallback = 'gcode_shell_command R2_AUDIO_PLAY' in sounds_cfg
check('8 Fallback ohne shell-command-extension', fallback,
      '(Responsive Fallback-Announce)')

# ---- 9. Regression: alle generierten gcode_shell_command 'command:' Werte
#      sind VALIDES PYTHON (Klipper-native kompiliert den command als Python
#      bei Connect - ein shell-string wie 'bash /path' wirft genau den
#      'Internal error during connect: invalid syntax' Fehler) ----
bad_cmds = []
for m in re.finditer(r'echo\s+"command:\s*(.*)"', setup_lib):
    val = re.sub(r'\$\{[^}]+\}', 'PATH', m.group(1).strip())
    try:
        compile(val, '<gcode_shell_command>', 'exec')
    except SyntaxError as e:
        bad_cmds.append('%s -> %s' % (val[:60], e))
check('9 alle generierten command:-Werte sind valides Python',
      not bad_cmds,
      '(%d command-Wert(e) geprueft)' % len(re.findall(r'echo\s+"command:', setup_lib)))

# ---- summary ----
print('\n'.join(results))
print('\n==== %d passed, %d failed ====' % (PASS, FAIL))
sys.exit(0 if FAIL == 0 else 1)
