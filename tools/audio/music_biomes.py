"""Музыка биомов 2 и 3: японская и итальянская кухни, в том же спокойном настроении, что и первая.

Японская: кото (щипковые струны), бамбуковая флейта, пэд, тихие деревянные ударные,
пентатоника. Итальянская: нейлоновая гитара в ритме босса-новы, мандолина с тремоло,
аккордеон, контрабас и щетки. Оба трека склеены в бесшовный цикл.

Запуск: python3 tools/audio/music_biomes.py <папка вывода> [japan|italy]
Пишет music_japan.m4a и music_italy.m4a (нужен ffmpeg).
"""
import math
import os
import subprocess
import sys

import numpy as np
from scipy import signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import (SR, add_at, apply_reverb, bandpass, bass_note, env_adsr, highpass, kick, lowpass,  # noqa: E402
                   midi_freq, normalize, pad_note, pan, write_wav)


# MARK: - Инструменты

def pluck(freq, dur, vel=0.7, bright=0.5, rng=None, decay=0.996):
    """Щипковая струна (Карплус-Стронг) с дробной задержкой через фазовращатель.

    bright: 0 - мягкий нейлон, 1 - звонкая сталь. decay - потери за период.
    """
    rng = rng or np.random.default_rng(0)
    n = int((dur + 1.2) * SR)
    period = SR / freq
    # усреднение дает задержку 0.5, фазовращатель - остаток
    N = int(math.floor(period - 0.5 - 0.1))
    delta = period - 0.5 - N
    c = (1 - delta) / (1 + delta)
    burst = rng.uniform(-1, 1, N + 2)
    burst = lowpass(burst, 1200 + 7000 * bright, 1)
    x = np.zeros(n)
    x[:len(burst)] = burst
    g = decay
    # y(1 + c z^-1) = x(1 + c z^-1) + g/2 z^-N (c + (1+c) z^-1 + z^-2) y
    a = np.zeros(N + 3)
    a[0] = 1
    a[1] = c
    a[N] -= g / 2 * c
    a[N + 1] -= g / 2 * (1 + c)
    a[N + 2] -= g / 2
    b = np.array([1.0, c])
    y = signal.lfilter(b, a, x)
    t = np.arange(n) / SR
    # глушение струны после длительности ноты
    damp = np.where(t > dur, np.exp(-(t - dur) / 0.12), 1.0)
    y = y * damp
    m = np.max(np.abs(y))
    return y / m * vel if m > 0 else y


def flute(freq, dur, vel=0.5, rng=None):
    """Бамбуковая флейта: синус с вибрато, дыхание шумом, мягкая атака."""
    rng = rng or np.random.default_rng(2)
    n = int((dur + 0.5) * SR)
    t = np.arange(n) / SR
    vib_depth = 0.006 * np.clip((t - 0.25) / 0.4, 0, 1)
    f = freq * (1 + vib_depth * np.sin(2 * math.pi * 5.0 * t + rng.uniform(0, 6)))
    ph = 2 * math.pi * np.cumsum(f) / SR
    tone = np.sin(ph) + 0.18 * np.sin(2 * ph) + 0.06 * np.sin(3 * ph)
    breath = bandpass(rng.normal(0, 1, n), freq * 0.8, min(freq * 4, 12000)) * 0.12
    # чуть больше дыхания на атаке, как у сякухати
    breath *= 1 + 2.5 * np.exp(-t / 0.08)
    e = env_adsr(n, a=0.09, d=0.2, s=0.8, r=0.35, hold=dur)
    return (tone + breath) * e * vel


def accordion(freq, dur, vel=0.4, rng=None):
    """Аккордеон: три язычка с легкой расстройкой (мюзет), прямоугольник через фильтр."""
    rng = rng or np.random.default_rng(3)
    n = int((dur + 0.4) * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for cents in (-7, 0, 7):
        f = freq * 2 ** (cents / 1200)
        x += signal.square(2 * math.pi * f * t + rng.uniform(0, 6), duty=0.42)
    x = lowpass(x / 3, 1800, 2)
    swell = 1 + 0.08 * np.sin(2 * math.pi * 0.7 * t)
    e = env_adsr(n, a=0.12, d=0.3, s=0.8, r=0.3, hold=dur)
    return x * e * swell * vel


def mandolin(freq, dur, vel=0.5, rng=None, tremolo=False):
    """Мандолина: парные струны; длинные ноты - тремоло медиатором."""
    rng = rng or np.random.default_rng(4)
    if not tremolo:
        a = pluck(freq, dur, vel, bright=0.85, rng=rng, decay=0.993)
        b = pluck(freq * 1.002, dur, vel * 0.8, bright=0.85, rng=rng, decay=0.993)
        n = max(len(a), len(b))
        out = np.zeros(n)
        out[:len(a)] += a
        out[:len(b)] += b
        return out * 0.6
    step = 60 / 76 / 4  # шестнадцатые
    n = int((dur + 1.0) * SR)
    out = np.zeros(n)
    k = 0
    while k * step < dur:
        v = vel * (0.75 + 0.25 * (k % 2 == 0)) * rng.uniform(0.85, 1.0)
        note = pluck(freq * (1 + rng.uniform(-0.001, 0.001)), step * 1.4, v, bright=0.85, rng=rng, decay=0.992)
        add_at(out, note, int(k * step * SR))
        k += 1
    return out * 0.55


def woodblock(vel=0.5, pitch=620):
    n = int(0.15 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * math.pi * pitch * t) * np.exp(-t / 0.03) + 0.4 * np.sin(2 * math.pi * pitch * 2.3 * t) * np.exp(-t / 0.012)
    return x * vel


def shaker(vel=0.3, seed=0):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(seed).normal(0, 1, n)
    env = np.clip(t / 0.02, 0, 1) * np.exp(-t / 0.04)
    return bandpass(noise, 5000, 12000) * env * vel


def brush(vel=0.4, seed=0, length=0.35):
    """Щетка по малому барабану: мягкий шорох."""
    n = int(length * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(seed).normal(0, 1, n)
    env = np.clip(t / 0.03, 0, 1) * np.exp(-t / (length / 3))
    return bandpass(noise, 1800, 9000) * env * vel


def upright(freq, dur, vel=0.7):
    """Контрабас: мягкий бас с щипком."""
    x = bass_note(freq, dur, vel)
    p = pluck(freq, dur, vel * 0.35, bright=0.2, decay=0.995)
    n = max(len(x), len(p))
    out = np.zeros(n)
    out[:len(x)] += x
    out[:len(p)] += p
    return out


# MARK: - Японская кухня

def japan():
    bpm = 66
    beat = 60 / bpm
    bar = 4 * beat
    swing = 0.56
    # аккорды по тактам: голоса MIDI, бас MIDI
    A = [
        ([55, 59, 62, 66, 69], 43),  # Gmaj9
        ([57, 61, 64, 66, 71], 42),  # F#m11
        ([55, 59, 62, 66], 40),      # Em9
        ([57, 62, 64, 69], 45),      # Asus4
        ([55, 59, 62, 66, 69], 43),  # Gmaj9
        ([57, 61, 62, 66], 47),      # Bm9
        ([55, 59, 62, 66], 40),      # Em9
        ([57, 61, 64, 69], 45),      # A
    ]
    melody = [
        (0, 0.0, 81, 2.0), (0, 2.0, 79, 1.0), (0, 3.0, 76, 1.0),
        (1, 0.0, 76, 3.0),
        (2, 0.5, 74, 1.0), (2, 1.5, 76, 0.5), (2, 2.0, 79, 2.0),
        (3, 0.0, 76, 1.0), (3, 1.0, 74, 1.0), (3, 2.0, 69, 2.0),
        (4, 0.0, 71, 1.0), (4, 1.0, 74, 1.0), (4, 2.0, 79, 1.5), (4, 3.5, 81, 0.5),
        (5, 0.0, 83, 2.5), (5, 2.5, 81, 0.5), (5, 3.0, 78, 1.0),
        (6, 0.0, 79, 1.5), (6, 1.5, 76, 0.5), (6, 2.0, 74, 2.0),
        (7, 0.0, 76, 3.5),
    ]
    # (имя, тактов, арпеджио, бас, ударные, пэд, мелодия: None / koto / flute / both)
    sections = [
        ("intro", 4, 0.9, False, 0.0, 0.8, None),
        ("a", 8, 1.0, True, 0.8, 0.4, None),
        ("a2", 8, 1.0, True, 1.0, 0.4, "koto"),
        ("b", 8, 0.8, True, 1.0, 0.8, "flute"),
        ("a3", 8, 1.0, True, 0.9, 0.6, "both"),
        ("outro", 4, 0.7, True, 0.3, 0.7, None),
    ]
    rng = np.random.default_rng(21)
    total = sum(s[1] for s in sections)
    length = int(total * bar * SR)
    tail = int(4.5 * SR)
    n = length + tail
    strings = np.zeros((n, 2))
    lead = np.zeros((n, 2))
    low = np.zeros((n, 2))
    pads = np.zeros((n, 2))
    perc = np.zeros((n, 2))

    def at(b, bt):
        return int((b * bar + bt * beat) * SR)

    pattern = [0, 2, 1, 3, 2, 4, 3, 1]
    b0 = 0
    for name, bars, arp, bass_on, drums, pad_level, mel in sections:
        for i in range(bars):
            b = b0 + i
            voices, root = A[i % len(A)]
            # кото: арпеджио восьмыми со свингом, октавой выше
            notes = [v + 12 for v in voices]
            for k, idx in enumerate(pattern):
                pos = k // 2 + (swing if k % 2 else 0)
                m = notes[idx % len(notes)]
                v = arp * (0.42 if k % 2 == 0 else 0.3) * rng.uniform(0.8, 1.0)
                x = pluck(midi_freq(m), 0.9 * beat, v, bright=0.55, rng=rng, decay=0.998)
                add_at(strings, pan(x, -0.3 + 0.15 * (k % 4)), at(b, pos) + int(rng.uniform(-0.006, 0.006) * SR))
            if bass_on:
                add_at(low, pan(upright(midi_freq(root), 1.8 * beat, 0.7), 0), at(b, 0))
                add_at(low, pan(upright(midi_freq(root + 7), 1.2 * beat, 0.5), 0), at(b, 2.5))
            if pad_level > 0:
                for k, m in enumerate(voices[:4]):
                    x = pad_note(midi_freq(m - 12 if k == 0 else m), 4 * beat, 0.32 * pad_level, rng)
                    add_at(pads, pan(x, -0.5 + 0.33 * k), at(b, 0))
            if drums > 0:
                add_at(perc, pan(kick(0.55 * drums), 0), at(b, 0))
                if i % 2 == 1:
                    add_at(perc, pan(kick(0.35 * drums), 0), at(b, 2.5))
                add_at(perc, pan(woodblock(0.32 * drums, 560), 0.25), at(b, 2))
                if i % 4 == 3:
                    add_at(perc, pan(woodblock(0.22 * drums, 760), -0.25), at(b, 3.5))
                for k in range(8):
                    pos = k // 2 + (swing if k % 2 else 0)
                    add_at(perc, pan(shaker((0.22 if k % 2 else 0.14) * drums, seed=int(rng.integers(1000))), 0.35),
                           at(b, pos))
            if mel:
                for mb, bt, m, dur in melody:
                    if mb != i % 8:
                        continue
                    if mel in ("koto", "both"):
                        x = pluck(midi_freq(m - (12 if mel == "both" else 0)), dur * beat, 0.55, bright=0.7, rng=rng,
                                  decay=0.9975)
                        add_at(lead, pan(x, 0.25), at(b, bt))
                    if mel in ("flute", "both"):
                        x = flute(midi_freq(m), dur * beat * 0.95, 0.27, rng)
                        add_at(lead, pan(x, -0.1), at(b, bt))
        b0 += bars

    breeze = lowpass(highpass(rng.normal(0, 1, n), 400), 2500) * 0.006
    wet = apply_reverb(strings * 1.1 + lead * 0.85 + pads * 0.3, mix=0.4, seconds=3.0)[:n]
    dry = low * 0.24 + apply_reverb(perc * 0.4, mix=0.2, seconds=1.4)[:n]
    mix = wet + dry + pan(breeze, 0)
    mix = lowpass(mix, 11500, 2)
    mix = np.tanh(mix * 1.1) / 1.1
    out = mix[:length].copy()
    out[:tail] += mix[length:length + tail]
    return normalize(out, 0.8)


# MARK: - Итальянская кухня

def italy():
    bpm = 76
    beat = 60 / bpm
    bar = 4 * beat
    A = [
        ([55, 60, 64, 71], 45),  # Am9
        ([53, 57, 60, 64], 38),  # Dm9
        ([53, 59, 64], 43),      # G13
        ([52, 59, 62, 67], 36),  # Cmaj9
        ([52, 57, 60, 65], 41),  # Fmaj7
        ([53, 57, 62, 71], 47),  # Bm7b5
        ([52, 56, 62, 65], 40),  # E7b9
        ([55, 60, 64, 71], 45),  # Am9
    ]
    melody = [
        (0, 0.5, 76, 1.0), (0, 1.5, 72, 0.5), (0, 2.0, 74, 1.0), (0, 3.0, 76, 1.0),
        (1, 0.0, 77, 2.0), (1, 2.0, 76, 0.5), (1, 2.5, 74, 1.5),
        (2, 0.0, 71, 1.0), (2, 1.0, 74, 1.0), (2, 2.0, 77, 1.0), (2, 3.0, 76, 1.0),
        (3, 0.0, 79, 2.0), (3, 2.0, 76, 2.0),
        (4, 0.5, 72, 1.0), (4, 1.5, 76, 0.5), (4, 2.0, 81, 2.0),
        (5, 0.0, 77, 1.0), (5, 1.0, 74, 1.0), (5, 2.0, 77, 1.0), (5, 3.0, 81, 1.0),
        (6, 0.0, 80, 2.0), (6, 2.0, 77, 1.0), (6, 3.0, 74, 1.0),
        (7, 0.0, 76, 3.5),
    ]
    # (имя, тактов, гитара, бас, ударные, аккордеон, мелодия: None / mandolin / accordion)
    sections = [
        ("intro", 4, 1.0, False, 0.0, 0.3, None),
        ("a", 8, 1.0, True, 0.8, 0.0, None),
        ("a2", 8, 1.0, True, 1.0, 0.0, "mandolin"),
        ("b", 8, 0.9, True, 1.0, 0.7, "accordion"),
        ("a3", 8, 1.0, True, 0.9, 0.4, "mandolin"),
        ("outro", 4, 0.8, True, 0.3, 0.5, None),
    ]
    rng = np.random.default_rng(33)
    total = sum(s[1] for s in sections)
    length = int(total * bar * SR)
    tail = int(4.0 * SR)
    n = length + tail
    guitar = np.zeros((n, 2))
    lead = np.zeros((n, 2))
    low = np.zeros((n, 2))
    acc = np.zeros((n, 2))
    perc = np.zeros((n, 2))

    def at(b, bt):
        return int((b * bar + bt * beat) * SR)

    # босса-нова: удары гитары по долям такта
    comp = [(0.0, 0.9, 1.0), (1.5, 0.6, 0.75), (2.5, 0.6, 0.8), (3.5, 0.4, 0.6)]
    b0 = 0
    for name, bars, gtr, bass_on, drums, acc_level, mel in sections:
        for i in range(bars):
            b = b0 + i
            voices, root = A[i % len(A)]
            for pos, dur, v in comp:
                for k, m in enumerate(voices):
                    x = pluck(midi_freq(m), dur * beat, 0.32 * gtr * v * rng.uniform(0.85, 1.0), bright=0.3, rng=rng,
                              decay=0.997)
                    add_at(guitar, pan(x, -0.25 + 0.12 * k), at(b, pos) + int(k * 0.014 * SR))
            if bass_on:
                fifth = root + 7
                for pos, m, dur, v in ((0.0, root, 1.4, 0.75), (1.5, fifth, 0.45, 0.5), (2.0, fifth, 1.4, 0.6),
                                       (3.5, root, 0.45, 0.45)):
                    add_at(low, pan(upright(midi_freq(m), dur * beat, v), 0), at(b, pos))
            if acc_level > 0:
                for k, m in enumerate(voices):
                    x = accordion(midi_freq(m + 12), 3.8 * beat, 0.16 * acc_level, rng)
                    add_at(acc, pan(x, 0.3 - 0.2 * k), at(b, 0))
            if drums > 0:
                add_at(perc, pan(kick(0.45 * drums), 0), at(b, 0))
                add_at(perc, pan(kick(0.3 * drums), 0), at(b, 2))
                for bt in (1, 3):
                    add_at(perc, pan(brush(0.35 * drums, seed=int(rng.integers(1000))), 0.15), at(b, bt))
                # клаве 3-2 римшотом
                clave = [0, 1.5, 3] if i % 2 == 0 else [1, 2]
                for bt in clave:
                    add_at(perc, pan(woodblock(0.18 * drums, 900), -0.3), at(b, bt))
                for k in range(8):
                    add_at(perc, pan(shaker((0.16 if k % 2 else 0.1) * drums, seed=int(rng.integers(1000))), 0.35),
                           at(b, k / 2))
            if mel:
                for mb, bt, m, dur in melody:
                    if mb != i % 8:
                        continue
                    if mel == "mandolin":
                        x = mandolin(midi_freq(m), dur * beat, 0.42, rng, tremolo=dur >= 1.5)
                        add_at(lead, pan(x, 0.2), at(b, bt))
                    else:
                        x = accordion(midi_freq(m), dur * beat * 0.95, 0.24, rng)
                        add_at(lead, pan(x, -0.15), at(b, bt))
        b0 += bars

    wet = apply_reverb(guitar * 1.0 + lead * 0.8 + acc * 0.5, mix=0.3, seconds=2.2)[:n]
    dry = low * 0.26 + apply_reverb(perc * 0.4, mix=0.15, seconds=1.1)[:n]
    mix = wet + dry
    mix = lowpass(mix, 11000, 2)
    mix = np.tanh(mix * 1.1) / 1.1
    out = mix[:length].copy()
    out[:tail] += mix[length:length + tail]
    return normalize(out, 0.8)


def main():
    out_dir = sys.argv[1]
    which = sys.argv[2:] or ["japan", "italy"]
    os.makedirs(out_dir, exist_ok=True)
    for name in which:
        x = {"japan": japan, "italy": italy}[name]()
        wav = os.path.join(out_dir, f"music_{name}.wav")
        write_wav(wav, x)
        m4a = os.path.join(out_dir, f"music_{name}.m4a")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", "112k", m4a], check=True)
        print("music:", m4a, os.path.getsize(m4a) // 1024, "KB", f"{len(x) / SR:.0f}s")


if __name__ == "__main__":
    main()
