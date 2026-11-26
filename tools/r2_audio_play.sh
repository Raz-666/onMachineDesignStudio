#!/usr/bin/env bash
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Raz-666 and contributors
# =====================================================================================
#  r2_audio_play.sh - R286 L1: REAL audio playback for the Raspberry host output.
#
#  Called from the M300 macro via the shell-command extension when
#  save_variables.audio_source is 'klinke' or 'hdmi' (the MCU piezo path is
#  left for 'beep'):
#
#     RUN_SHELL_COMMAND CMD=R2_AUDIO_PLAY PARAMS="1568 40 1245 30 0 150"
#
#  PARAMS = a list of "frequency_hz duration_ms" pairs. A frequency of 0 means
#  a pause of that many ms (matching the _SOUND_LIB tune format
#  "freq:dur,freq:dur,...").  The SAME tunes the piezo beeper plays are used -
#  only the modulation is replaced by real 8-bit audio playback.
#
#  What it does:
#    1) synthesizes an 8-bit (unsigned PCM) WAV from the frequency/duration
#       list - a square wave with a short attack/decay envelope (click-free,
#       classic 8-bit character), mono, 22050 Hz.
#    2) plays it through the Pi's audio output (aplay first, then paplay,
#       then ffplay as fallbacks). If no player is available it falls back
#       to writing the WAV so the file exists, and reports the reason.
#
#  Location independence: derives its own directory; the caller passes the
#  absolute command path via [gcode_shell_command R2_AUDIO_PLAY] (setup.sh
#  bakes it in - same pattern as R2_PERSIST).
#
#  Safety: PARAMS are whitelisted numbers only; no shell injection surface.
# =====================================================================================
set -u

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WAV_DIR="${SELF_DIR}/.audio_cache"
mkdir -p "$WAV_DIR" 2>/dev/null || true

# --- parse PARAMS (from the 1st CLI arg, or stdin) --------------------------------
ARGS="${1:-}"
if [ -z "$ARGS" ]; then
    ARGS="$(cat 2>/dev/null)"
fi
# split on whitespace
read -r -a TOKENS <<< "$ARGS"

if [ "${#TOKENS[@]}" -eq 0 ]; then
    echo "[R2_AUDIO_PLAY] no frequency/duration pairs given - nothing to play"
    exit 0
fi

# validate: every token must be a non-negative integer (no injection)
for t in "${TOKENS[@]}"; do
    case "$t" in
        ''|*[!0-9]*)
            echo "[R2_AUDIO_PLAY] invalid token '$t' - refusing (must be a number)"
            exit 1
            ;;
    esac
done

# --- synthesize the 8-bit WAV with python3 (stdlib only) -------------------------
# build the token list as python ints
PY_TOKENS=""
for t in "${TOKENS[@]}"; do
    PY_TOKENS="${PY_TOKENS} ${t}"
done

WAV_PATH="${WAV_DIR}/r2_tone.wav"
python3 - "$PY_TOKENS" "$WAV_PATH" <<'PYEOF'
import sys, wave, math, struct

tokens = [int(x) for x in sys.argv[1].split()]
out = sys.argv[2]
SR = 22050            # sample rate
# iterate pairs (freq, dur_ms); a trailing odd token is treated as dur with freq 0
pairs = []
i = 0
while i < len(tokens):
    f = tokens[i]
    d = tokens[i + 1] if i + 1 < len(tokens) else 0
    pairs.append((f, d))
    i += 2

samples = []
envelope_attack = 40      # samples (attack to avoid click)
envelope_release = 60     # samples (release)
for f, d in pairs:
    n = int(SR * d / 1000.0)
    if f <= 0:
        # pause: silence
        samples.extend([0] * n)
        continue
    period = max(1, int(SR / f))
    half = period // 2
    for s in range(n):
        # square wave: +127 / -127 (unsigned 8-bit centered)
        phase = (s % period) < half
        val = 127 if phase else -127
        # simple envelope on the start/end of each tone for click-free edges
        if s < envelope_attack:
            val = int(val * s / envelope_attack)
        elif s >= n - envelope_release:
            k = n - s
            if k <= envelope_release:
                val = int(val * k / envelope_release)
        samples.append(val)

with wave.open(out, 'wb') as w:
    w.setnchannels(1)
    w.setsampwidth(1)       # 8-bit
    w.setframerate(SR)
    frames = bytearray(len(samples))
    for i, v in enumerate(samples):
        # 8-bit unsigned: 0..255, center 128
        frames[i] = 128 + max(-128, min(127, v))
    w.writeframes(bytes(frames))
PYEOF

if [ ! -s "$WAV_PATH" ]; then
    echo "[R2_AUDIO_PLAY] WAV synthesis failed - no audio"
    exit 1
fi

# --- play it (try players in order) ----------------------------------------------
played=0
if command -v aplay >/dev/null 2>&1; then
    aplay -q "$WAV_PATH" >/dev/null 2>&1 && played=1
fi
if [ "$played" -ne 1 ] && command -v paplay >/dev/null 2>&1; then
    paplay "$WAV_PATH" >/dev/null 2>&1 && played=1
fi
if [ "$played" -ne 1 ] && command -v ffplay >/dev/null 2>&1; then
    ffplay -nodisp -autoexit -loglevel quiet "$WAV_PATH" >/dev/null 2>&1 && played=1
fi

if [ "$played" -eq 1 ]; then
    echo "[R2_AUDIO_PLAY] played ${#TOKENS[@]} values via host audio"
else
    echo "[R2_AUDIO_PLAY] WAV written to ${WAV_PATH} but no audio player (aplay/paplay/ffplay) found - install alsa-utils or pulseaudio-utils"
fi
exit 0
