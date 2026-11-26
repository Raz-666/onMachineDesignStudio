#!/usr/bin/env python3
"""R286 L1: MIDI/NOTE -> 8-bit WAV upsampling tool (offline, one-shot).

Why this exists: the live playback path (tools/r2_audio_play.sh) synthesizes
the 8-bit WAV on the fly whenever an M300 fires - a real-time square-wave
synthesizer in the shell, executed on the printing Pi. The R286 decision:
WAV is the resource-friendly format. For tunes that are played often (or
longer than a short beep), doing the synthesis ONCE offline and storing the
resulting 8-bit WAV removes the per-call synthesis cost from the live path:
the player then only plays a ready-made file (aplay/paplay), no real-time
synthesis at all.

This tool is the upsampling step. It is NOT part of the live pipeline - call
it during maintenance (or once after authoring a tune), then point the
playback at the produced .wav.

Inputs (auto-detected):
  1. freq:ms sequence   "440:250,523:250,0:100"   -> same format as _SOUND_LIB
  2. note:ms sequence   "A4:250,C#5:250,G4:500"  -> note names with duration
  3. a .mid file        (standard MIDI, first track; notes + tempo)

Output: 8-bit unsigned PCM WAV, mono, 22050 Hz - byte-compatible with what
r2_audio_play.sh synthesizes (square wave + short attack/decay envelope,
click-free classic 8-bit character).

Usage:
  r2_midi2wav.py INPUT OUTPUT.wav
  r2_midi2wav.py "440:250,523:250" tune.wav
  r2_midi2wav.py melody.mid melody.wav
  r2_midi2wav.py --list          (show supported note names)
"""
import os
import sys
import struct
import math

SAMPLE_RATE = 22050      # same as r2_audio_play.sh
AMPLITUDE = 120          # 8-bit amplitude (0..255) of the square wave
ATTACK_MS = 4.0          # envelope attack (click-free)
RELEASE_MS = 10.0        # envelope release tail

# note name -> frequency (equal temperament, A4=440)
_NOTE_BASE = {}
_SEMITONE = {
    'C': 0, 'C#': 1, 'Db': 1, 'D': 2, 'D#': 3, 'Eb': 3, 'E': 4,
    'F': 5, 'F#': 6, 'Gb': 6, 'G': 7, 'G#': 8, 'Ab': 8, 'A': 9,
    'A#': 10, 'Bb': 10, 'B': 11,
}
for _n, _s in _SEMITONE.items():
    for _oct in range(0, 9):
        # scientific pitch: C4 = middle C (261.63 Hz), A4 = 440 Hz
        _midi = 12 * (_oct + 1) + _s
        _freq = 440.0 * (2.0 ** ((_midi - 69) / 12.0))
        _NOTE_BASE[(_n, _oct)] = _freq


def _parse_note(name):
    """'A4' -> 440.0, 'C#5' -> 554.37, 'Gb3' -> 174.61. Returns None if invalid."""
    name = name.strip()
    if not name:
        return None
    # longest match on the note-name prefix (C# / Db are two chars)
    for nl in (2, 1):
        if len(name) > nl and name[:nl] in _SEMITONE:
            rest = name[nl:]
            if rest.isdigit():
                oct_ = int(rest)
                return _NOTE_BASE.get((name[:nl], oct_))
    return None


def _parse_tokens(text):
    """Parse a 'freq:ms,note:ms,...' or whitespace-separated list into a
    [(freq_hz_or_0, dur_ms), ...] sequence. 0 Hz = pause."""
    if not text:
        return []
    # accept both comma and whitespace separators
    raw = text.replace(',', ' ')
    seq = []
    for tok in raw.split():
        if not tok:
            continue
        if ':' not in tok:
            print('[r2_midi2wav] skipping token without : (got %r)' % tok)
            continue
        freq_s, dur_s = tok.split(':', 1)
        dur_s = dur_s.strip()
        try:
            dur = float(dur_s)
        except ValueError:
            print('[r2_midi2wav] bad duration %r in %r - skipping' % (dur_s, tok))
            continue
        freq_s = freq_s.strip()
        if freq_s.replace('.', '', 1).isdigit():
            freq = float(freq_s)
        else:
            freq = _parse_note(freq_s)
            if freq is None:
                print('[r2_midi2wav] bad note %r - skipping' % freq_s)
                continue
        if freq < 0:
            freq = 0.0
        seq.append((freq, dur))
    return seq


def _parse_midi(path):
    """Minimal standard-MIDI reader: header + first track, note on/off +
    tempo. Returns [(freq_hz, dur_ms), ...] as a sequential (non-overlapping)
    timeline. Overlapping notes are rare in R2 tunes; this keeps it simple."""
    with open(path, 'rb') as f:
        data = f.read()
    if len(data) < 14 or data[:4] != b'MThd':
        raise ValueError('not a valid MIDI file (missing MThd)')
    # header chunk length + format
    # MThd chunk layout: id(4) len(4) format(2) ntracks(2) division(2)
    hdr_len = struct.unpack('>I', data[4:8])[0]
    format_ = struct.unpack('>H', data[8:10])[0]
    division = struct.unpack('>H', data[12:14])[0]
    if format_ != 0:
        print('[r2_midi2wav] format-1 MIDI: only the first track is used')
    if division & 0x8000:
        raise ValueError('SMPTE division not supported (PPQN expected)')
    # MThd chunk = 4 (id) + 4 (len) + hdr_len data bytes -> first chunk after it
    pos = 8 + hdr_len
    tempo = 500000            # us per quarter note (120 bpm default)
    events = []
    track_end = len(data)
    # find the first MTrk chunk
    while pos < len(data):
        if data[pos:pos + 4] == b'MTrk':
            trk_len = struct.unpack('>I', data[pos + 4:pos + 8])[0]
            track_end = min(len(data), pos + 8 + trk_len)
            break
        pos += 1
    if pos >= len(data):
        raise ValueError('no MTrk chunk found')
    pos += 8
    ticks_per_quarter = max(1, division)
    running_status = 0
    now = 0
    notes = {}                  # note -> (start_time_us, freq)
    seq = []
    while pos < track_end:
        delta, pos = _read_varlen(data, pos)
        now += delta
        if pos >= track_end:
            break
        meta = data[pos]
        if meta == 0xFF:        # meta event
            pos += 1
            mtype = data[pos] if pos < track_end else 0
            mlen, pos = _read_varlen(data, pos + 1)
            payload = data[pos:pos + mlen]
            pos += mlen
            if mtype == 0x51 and len(payload) >= 3:   # set tempo
                tempo = struct.unpack('>I', b'\x00' + payload[:3])[0]
            elif mtype == 0x2F:                       # end of track
                break
        elif meta == 0xF0 or meta == 0xF7:   # sysex
            mlen, pos = _read_varlen(data, pos + 1)
            pos += mlen
        else:
            status = meta
            if 0x80 <= status < 0xF0:
                # explicit status byte at data[pos]; data bytes follow it
                running_status = status
                if status < 0xC0:
                    ev = (status, data[pos + 1] if pos + 1 < track_end else 0,
                          data[pos + 2] if pos + 2 < track_end else 0)
                    pos += 3
                else:
                    ev = (status, data[pos + 1] if pos + 1 < track_end else 0, 0)
                    pos += 2
            else:
                # running status: this byte is data, status = last seen
                status = running_status
                if pos < track_end and 0x80 <= status < 0xF0:
                    if status < 0xC0:
                        ev = (status, data[pos],
                              data[pos + 1] if pos + 1 < track_end else 0)
                        pos += 2
                    else:
                        ev = (status, data[pos], 0)
                        pos += 1
                else:
                    # no valid running status yet - skip defensively
                    pos += 1
                    continue
            # note on (velocity>0) / note off (velocity 0 or status 0x80)
            if ev[0] in (0x90, 0x80):
                note = ev[1]
                vel = ev[2] if len(ev) > 2 else 0
                oct_ = note // 12 - 1
                name = _NOTE_NAMES_INV.get(note % 12, 'C')
                freq = 440.0 * (2.0 ** ((note - 69) / 12.0))
                if ev[0] == 0x90 and vel > 0:
                    notes[note] = (now, freq)
                elif note in notes:
                    start, freq = notes.pop(note)
                    dur_us = (now - start) * tempo / ticks_per_quarter
                    if dur_us > 0:
                        seq.append((freq, dur_us / 1000.0))
    # leftover (unclosed) notes: emit at the end
    now_end = now
    for note, (start, freq) in notes.items():
        dur_us = (now_end - start) * tempo / ticks_per_quarter
        if dur_us > 0:
            seq.append((freq, dur_us / 1000.0))
    return seq


_NOTE_NAMES_INV = {0: 'C', 1: 'C#', 2: 'D', 3: 'Eb', 4: 'E', 5: 'F',
                   6: 'F#', 7: 'G', 8: 'Ab', 9: 'A', 10: 'Bb', 11: 'B'}


def _read_varlen(data, pos):
    """MIDI variable-length quantity -> (value, new_pos)."""
    value = 0
    while pos < len(data):
        b = data[pos]
        value = (value << 7) | (b & 0x7F)
        pos += 1
        if not (b & 0x80):
            return value, pos
    raise ValueError('truncated variable-length quantity')


def _synthesize(seq):
    """seq: [(freq_hz, dur_ms), ...] -> 8-bit unsigned PCM bytearray.
    Square wave + short attack/decay envelope (identical character to
    r2_audio_play.sh). 0 Hz = silence. Overlaps are summed with clipping."""
    n_total = 0
    for _f, d in seq:
        n_total += int(round(d * SAMPLE_RATE / 1000.0))
    if n_total <= 0:
        return bytearray(b'\x80') * 0, 0
    buf = bytearray(n_total)
    pos = 0
    attack = max(1, int(ATTACK_MS * SAMPLE_RATE / 1000.0))
    release = max(1, int(RELEASE_MS * SAMPLE_RATE / 1000.0))
    for freq, dur in seq:
        n = int(round(dur * SAMPLE_RATE / 1000.0))
        if n <= 0:
            pos += 0
            continue
        if freq <= 0:
            pos += n
            continue
        period = SAMPLE_RATE / freq
        half = max(1, int(round(period / 2.0)))
        i = 0
        while i < n and pos + i < len(buf):
            t = i
            env = 1.0
            if t < attack:
                env = t / attack
            elif t >= n - release:
                env = max(0.0, (n - t) / release)
            val = 128 + AMPLITUDE * env * (1 if (t % half) < half / 2.0 else -1)
            # 8-bit unsigned PCM, mid = 128
            v = int(round(val))
            if v < 0:
                v = 0
            elif v > 255:
                v = 255
            buf[pos + i] = v
            i += 1
        pos += n
    return buf, n_total


def _write_wav(path, pcm):
    """Write 8-bit unsigned PCM mono WAV (RIFF/WAVE)."""
    n = len(pcm)
    data_size = n
    header = b'RIFF' + struct.pack('<I', 36 + data_size) + b'WAVE'
    header += b'fmt ' + struct.pack('<IHHIIHH', 16, 1, 1, SAMPLE_RATE,
                                    SAMPLE_RATE, 1, 8)
    header += b'data' + struct.pack('<I', data_size)
    with open(path, 'wb') as f:
        f.write(header)
        f.write(bytes(pcm))
    return n


def _main(argv):
    if not argv or argv[0] in ('-h', '--help'):
        print(__doc__)
        return 0
    if argv[0] == '--list':
        print('Supported note names:')
        for (n, o), f in sorted(_NOTE_BASE.items(), key=lambda kv: (kv[0][1], kv[0][0])):
            print('  %s%d = %.2f Hz' % (n, o, f))
        return 0
    if len(argv) < 2:
        print('usage: r2_midi2wav.py INPUT OUTPUT.wav')
        return 1
    src, dst = argv[0], argv[1]
    if src.lower().endswith('.mid') or src.lower().endswith('.midi'):
        seq = _parse_midi(src)
        print('[r2_midi2wav] parsed %d note(s) from %s' % (len(seq), src))
    else:
        if os.path.isfile(src):
            with open(src) as f:
                text = f.read()
        else:
            text = src
        seq = _parse_tokens(text)
        print('[r2_midi2wav] parsed %d step(s) from input' % len(seq))
    if not seq:
        print('[r2_midi2wav] nothing to synthesize - empty sequence')
        return 1
    pcm, n = _synthesize(seq)
    n_written = _write_wav(dst, pcm)
    print('[r2_midi2wav] wrote %s (%d samples, %.2f s, 8-bit %d Hz mono)'
          % (dst, n_written, n_written / SAMPLE_RATE, SAMPLE_RATE))
    print('[r2_midi2wav] play with: aplay %s   (or via R2_AUDIO_PLAY of the wav)' % dst)
    return 0


if __name__ == '__main__':
    sys.exit(_main(sys.argv[1:]))
