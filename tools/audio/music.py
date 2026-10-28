"""Фоновая музыка Sortelier: спокойный lo-fi для американской кухни.

Электропиано с джазовыми аккордами, мягкий бас, тихие ударные со свингом, колокольчик
с мелодией, пэд и легкий треск пластинки. Трек склеен в бесшовный цикл.

Запуск: python3 tools/audio/music.py <папка вывода>
Пишет music_kitchen.wav и music_kitchen.m4a (нужен ffmpeg).
"""
import math
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import (SR, add_at, apply_reverb, bass_note, bell_note, ep_note, hat, highpass, kick, lowpass,  # noqa: E402
                   midi_freq, normalize, pad_note, pan, rim, write_wav)

BPM = 70
BEAT = 60 / BPM
BAR = 4 * BEAT
SWING = 0.58  # доля бита для второй восьмой

# Аккорды: (доля такта, где начинается, голоса MIDI, бас MIDI)
A = [
    [(0, [57, 60, 64, 67], 41)],                                   # Fmaj9
    [(0, [55, 59, 62, 64], 40), (2, [55, 61, 65, 67], 45)],        # Em7 -> A7(b13)
    [(0, [53, 57, 60, 64], 38)],                                   # Dm9
    [(0, [58, 62, 63, 67], 36), (2, [57, 62, 63, 67], 41)],        # Cm9 -> F13
    [(0, [57, 60, 62, 65], 34)],                                   # Bbmaj9
    [(0, [58, 61, 65, 67], 34)],                                   # Bbm6
    [(0, [60, 64, 67, 71], 45), (2, [60, 64, 66, 69], 38)],        # Am9 -> D9
    [(0, [58, 62, 65, 69], 43), (2, [58, 62, 64, 67], 36)],        # Gm9 -> C9
]
B = [
    [(0, [57, 60, 62, 65], 34)],                                   # Bbmaj9
    [(0, [60, 64, 67, 71], 45)],                                   # Am9
    [(0, [58, 62, 65, 69], 43)],                                   # Gm9
    [(0, [57, 60, 64, 67], 41)],                                   # Fmaj9
    [(0, [57, 60, 62, 65], 34)],                                   # Bbmaj9
    [(0, [60, 64, 67, 71], 45), (2, [60, 64, 66, 69], 38)],        # Am9 -> D9
    [(0, [58, 62, 65, 69], 43), (2, [58, 62, 64, 67], 36)],        # Gm9 -> C9
    [(0, [57, 60, 64, 67], 41), (2, [57, 60, 63, 67], 41)],        # Fmaj9 -> F7
]

# Мелодия колокольчика на 8 тактов: (такт, доля, MIDI, длительность в долях)
MELODY_A = [
    (0, 1.0, 76, 1.0), (0, 2.0, 72, 0.5), (0, 2.5, 74, 1.5),
    (1, 0.5, 74, 1.0), (1, 2.0, 73, 1.5),
    (2, 0.0, 69, 0.5), (2, 0.5, 72, 0.5), (2, 1.0, 76, 1.5), (2, 3.0, 74, 1.0),
    (3, 0.5, 70, 1.0), (3, 2.0, 69, 0.5), (3, 2.5, 67, 1.5),
    (4, 0.0, 69, 1.0), (4, 1.0, 72, 0.5), (4, 1.5, 74, 0.5), (4, 2.0, 77, 2.0),
    (5, 0.5, 79, 1.0), (5, 2.0, 77, 0.5), (5, 2.5, 73, 1.5),
    (6, 0.0, 76, 1.0), (6, 1.0, 72, 1.0), (6, 2.0, 78, 1.0), (6, 3.0, 74, 1.0),
    (7, 0.5, 74, 1.0), (7, 2.0, 72, 0.5), (7, 2.5, 76, 1.5),
]
MELODY_B = [
    (0, 0.0, 77, 1.5), (0, 2.0, 74, 1.0), (1, 0.5, 76, 2.0),
    (2, 0.0, 74, 1.0), (2, 1.5, 72, 1.0), (3, 0.0, 69, 3.0),
    (4, 0.0, 77, 1.0), (4, 1.0, 79, 1.0), (4, 2.0, 81, 2.0),
    (5, 0.5, 79, 1.0), (5, 2.0, 78, 1.5), (6, 0.0, 77, 1.0), (6, 2.0, 76, 1.5), (7, 0.0, 77, 3.0),
]

# Части трека: (аккорды, мелодия, барабаны 0..1, бас, пэд, сколько тактов)
SECTIONS = [
    ("intro", A[:4], None, 0.0, False, 0.6, 4),
    ("a", A, None, 1.0, True, 0.0, 8),
    ("a2", A, MELODY_A, 1.0, True, 0.3, 8),
    ("b", B, MELODY_B, 1.0, True, 1.0, 8),
    ("a3", A, MELODY_A, 0.85, True, 0.8, 8),
    ("outro", A[:4], None, 0.35, True, 0.6, 4),
]


def render(drums_on=True):
    rng = np.random.default_rng(11)
    total_bars = sum(s[6] for s in SECTIONS)
    length = int(total_bars * BAR * SR)
    tail = int(4.0 * SR)
    n = length + tail
    keys = np.zeros((n, 2))
    bass = np.zeros((n, 2))
    drums = np.zeros((n, 2))
    bells = np.zeros((n, 2))
    pads = np.zeros((n, 2))

    def at(bar, beat):
        return int((bar * BAR + beat * BEAT) * SR)

    bar0 = 0
    for name, chords, melody, drum_level, bass_on, pad_level, bars in SECTIONS:
        for b in range(bars):
            bar = bar0 + b
            prog = chords[b % len(chords)]
            for ci, (beat, voices, root) in enumerate(prog):
                half = len(prog) > 1
                # аккомпанемент: удар на долю и мягкий повтор на "и" второй доли
                hits = [(beat, 1.6 if half else 1.5, 0.72)]
                if not half:
                    hits.append((2.5, 1.2, 0.5))
                elif ci == 0:
                    hits = [(beat, 1.5, 0.7)]
                for hb, hd, hv in hits:
                    start = at(bar, hb) + int(rng.uniform(-0.008, 0.008) * SR)
                    for k, m in enumerate(voices):
                        v = hv * rng.uniform(0.85, 1.0) * (0.9 if k == 0 else 1.0)
                        x = ep_note(midi_freq(m), hd * BEAT, v, rng)
                        add_at(keys, pan(x, -0.35 + 0.25 * k), start + int(k * 0.012 * SR))
                if bass_on:
                    bstart = at(bar, beat)
                    add_at(bass, pan(bass_note(midi_freq(root), (1.4 if half else 1.6) * BEAT, 0.8), 0), bstart)
                    if not half:
                        fifth = root + 7 if b % 2 == 0 else root + 12
                        add_at(bass, pan(bass_note(midi_freq(fifth), 0.8 * BEAT, 0.55), 0), at(bar, 2.5))
                        if b % 4 == 3:
                            add_at(bass, pan(bass_note(midi_freq(root - 1), 0.4 * BEAT, 0.45), 0), at(bar, 3.5))
                if pad_level > 0:
                    dur = (2 if half else 4) * BEAT
                    for k, m in enumerate(voices[1:]):
                        x = pad_note(midi_freq(m - 12), dur, 0.5 * pad_level, rng)
                        add_at(pads, pan(x, -0.5 + 0.5 * k), at(bar, beat))
            if drums_on and drum_level > 0:
                lv = drum_level
                add_at(drums, pan(kick(0.9 * lv), 0), at(bar, 0))
                add_at(drums, pan(kick(0.65 * lv), 0), at(bar, 2.5))
                if b % 2 == 1:
                    add_at(drums, pan(kick(0.45 * lv), 0), at(bar, 1.75 + SWING - 0.5))
                for beat in (1, 3):
                    add_at(drums, pan(rim(0.55 * lv) * rng.uniform(0.85, 1), 0.15), at(bar, beat))
                for beat in range(4):
                    for half_ in (0, 1):
                        pos = beat + (SWING if half_ else 0)
                        v = (0.8 if half_ == 0 else 0.5) * rng.uniform(0.75, 1.0) * lv
                        open_ = (beat == 3 and half_ == 1 and b % 2 == 1)
                        add_at(drums, pan(hat(v, open_, seed=int(rng.integers(1000))), 0.3), at(bar, pos))
            if melody:
                for mb, beat, m, dur in melody:
                    if mb == b % 8:
                        x = bell_note(midi_freq(m), max(1.2, dur * BEAT * 1.6), 0.55)
                        add_at(bells, pan(x, 0.2), at(bar, beat))
        bar0 += bars

    # треск пластинки и шипение
    hiss = lowpass(highpass(rng.normal(0, 1, n), 2500), 9000) * 0.012
    clicks = np.zeros(n)
    for pos in rng.integers(0, n, int(n / SR * 9)):
        clicks[pos] = rng.uniform(0.2, 1.0) * rng.choice([-1, 1])
    clicks = lowpass(clicks, 4000) * 0.35
    crackle = pan(hiss + clicks, 0)

    wet_bus = apply_reverb(keys * 0.42 + bells * 0.30 + pads * 0.16, mix=0.34, seconds=2.4)[:n]
    dry_bus = bass * 0.5 + apply_reverb(drums * 0.36, mix=0.12, seconds=1.0)[:n]
    mix = wet_bus + dry_bus + crackle * 0.6
    # теплый "магнитофонный" тон: мягкий срез верхов и легкое насыщение
    mix = lowpass(mix, 11000, 2)
    mix = np.tanh(mix * 1.15) / 1.15
    # бесшовный цикл: хвост реверберации добавляем в начало
    out = mix[:length].copy()
    out[:tail] += mix[length:length + tail]
    return normalize(out, 0.8)


def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    wav = os.path.join(out_dir, "music_kitchen.wav")
    write_wav(wav, render())
    m4a = os.path.join(out_dir, "music_kitchen.m4a")
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", "112k", m4a], check=True)
    print("music:", m4a, os.path.getsize(m4a) // 1024, "KB")


if __name__ == "__main__":
    main()
