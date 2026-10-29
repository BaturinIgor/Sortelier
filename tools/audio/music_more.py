"""Музыка кухонь 4 и 5 в том же спокойном настроении.

Мексиканская: болеро на нейлоновых гитарах (аккомпанемент и мелодия-рекинто), маримба с тремоло на длинных нотах,
контрабас как гитаррон, маракасы и клаве. Французская пекарня: вальс-мюзет на 3/4, аккордеон ведет мелодию,
"ум-па-па" басом и гитарой, музыкальная шкатулка на подголосках. Оба трека склеены в бесшовный цикл.

Запуск: python3 tools/audio/music_more.py <папка вывода> [mexico|bakery]
Пишет music_mexico.m4a и music_bakery.m4a (нужен ffmpeg).
"""
import math
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import SR, add_at, apply_reverb, kick, lowpass, midi_freq, normalize, pan, write_wav  # noqa: E402
from music_biomes import accordion, brush, pluck, shaker, upright, woodblock  # noqa: E402


# MARK: - Инструменты

def marimba(freq, dur, vel=0.5, rng=None, roll=False):
    """Маримба: деревянный брусок (основной тон и 4-й обертон с быстрым затуханием), мягкий молоточек.

    Длинные ноты играются тремоло, как на настоящей маримбе.
    """
    rng = rng or np.random.default_rng(5)

    def hit(v):
        n = int(1.4 * SR)
        t = np.arange(n) / SR
        decay = 0.55 * (440 / freq) ** 0.3
        x = np.sin(2 * math.pi * freq * t) * np.exp(-t / decay)
        x += 0.35 * np.sin(2 * math.pi * freq * 3.9 * t) * np.exp(-t / (decay * 0.18))
        x += 0.12 * np.sin(2 * math.pi * freq * 9.2 * t) * np.exp(-t / 0.012)
        att = np.clip(t / 0.002, 0, 1)
        return x * att * v

    if not roll:
        return hit(vel)
    step = 0.085
    n = int((dur + 1.4) * SR)
    out = np.zeros(n)
    k = 0
    while k * step < dur:
        add_at(out, hit(vel * (0.55 + 0.15 * (k % 2)) * rng.uniform(0.9, 1.0)), int(k * step * SR))
        k += 1
    return out * 0.8


def music_box(freq, vel=0.4):
    """Музыкальная шкатулка: звонкий язычок с негармоничными обертонами и долгим хвостом."""
    n = int(2.2 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * math.pi * freq * t) * np.exp(-t / 0.9)
    x += 0.4 * np.sin(2 * math.pi * freq * 2.76 * t) * np.exp(-t / 0.35)
    x += 0.2 * np.sin(2 * math.pi * freq * 5.4 * t) * np.exp(-t / 0.12)
    return x * np.clip(t / 0.001, 0, 1) * vel


def seamless(parts, length, tail, reverb_mix=0.3, seconds=2.2, dry=None, peak=0.8):
    n = length + tail
    wet = apply_reverb(parts, mix=reverb_mix, seconds=seconds)[:n]
    mix = wet + (dry if dry is not None else 0)
    mix = lowpass(mix, 11000, 2)
    mix = np.tanh(mix * 1.1) / 1.1
    out = mix[:length].copy()
    out[:tail] += mix[length:length + tail]
    return normalize(out, peak)


# MARK: - Мексиканская кухня

def mexico():
    bpm = 84
    beat = 60 / bpm
    bar = 4 * beat
    # G - Em - Am7 - D7 - G - C - Am7 D7 - G (болеро в соль мажоре)
    A = [
        ([55, 59, 62, 67], 43),  # G
        ([52, 55, 59, 64], 40),  # Em
        ([57, 60, 64, 67], 45),  # Am7
        ([54, 57, 60, 62], 38),  # D7
        ([55, 59, 62, 67], 43),  # G
        ([55, 60, 64, 67], 36),  # C
        ([54, 57, 60, 62], 38),  # D7
        ([55, 59, 62, 67], 43),  # G
    ]
    melody = [
        (0, 0.0, 74, 1.5), (0, 1.5, 72, 0.5), (0, 2.0, 71, 1.0), (0, 3.0, 72, 1.0),
        (1, 0.0, 74, 2.0), (1, 2.0, 71, 1.0), (1, 3.0, 67, 1.0),
        (2, 0.0, 69, 1.5), (2, 1.5, 71, 0.5), (2, 2.0, 72, 1.0), (2, 3.0, 76, 1.0),
        (3, 0.0, 74, 3.0), (3, 3.0, 72, 1.0),
        (4, 0.0, 71, 1.5), (4, 1.5, 72, 0.5), (4, 2.0, 74, 1.0), (4, 3.0, 79, 1.0),
        (5, 0.0, 76, 2.0), (5, 2.0, 72, 1.0), (5, 3.0, 76, 1.0),
        (6, 0.0, 74, 1.0), (6, 1.0, 72, 1.0), (6, 2.0, 69, 1.0), (6, 3.0, 66, 1.0),
        (7, 0.0, 67, 3.5),
    ]
    # (имя, тактов, гитара, бас, ударные, мелодия: None / marimba / requinto)
    sections = [
        ("intro", 4, 1.0, False, 0.0, None),
        ("a", 8, 1.0, True, 0.8, "marimba"),
        ("a2", 8, 1.0, True, 1.0, "requinto"),
        ("rest", 8, 0.9, True, 0.6, None),
        ("a3", 8, 1.0, True, 1.0, "marimba"),
        ("a4", 8, 0.9, True, 0.9, "requinto"),
        ("outro", 4, 0.8, True, 0.4, None),
    ]
    rng = np.random.default_rng(41)
    total = sum(s[1] for s in sections)
    length = int(total * bar * SR)
    tail = int(4.0 * SR)
    n = length + tail
    guitar = np.zeros((n, 2))
    lead = np.zeros((n, 2))
    low = np.zeros((n, 2))
    perc = np.zeros((n, 2))

    def at(b, bt):
        return int((b * bar + bt * beat) * SR)

    # болеро: удар на раз, два коротких на "два-и", удары на три и четыре
    comp = [(0.0, 0.9, 1.0), (1.5, 0.35, 0.6), (2.0, 0.6, 0.85), (3.0, 0.6, 0.75)]
    b0 = 0
    for name, bars, gtr, bass_on, drums, mel in sections:
        for i in range(bars):
            b = b0 + i
            voices, root = A[i % len(A)]
            for pos, dur, v in comp:
                down = pos in (0.0, 2.0)
                order = voices if down else voices[::-1]
                for k, m in enumerate(order):
                    x = pluck(midi_freq(m), dur * beat, 0.3 * gtr * v * rng.uniform(0.85, 1.0), bright=0.35, rng=rng,
                              decay=0.997)
                    add_at(guitar, pan(x, -0.3 + 0.12 * k), at(b, pos) + int(k * 0.012 * SR))
            if bass_on:
                fifth = root + 7 if root + 7 < 50 else root - 5
                for pos, m, dur, v in ((0.0, root, 1.6, 0.75), (2.0, fifth, 1.6, 0.6)):
                    add_at(low, pan(upright(midi_freq(m), dur * beat, v), 0), at(b, pos))
            if drums > 0:
                add_at(perc, pan(kick(0.35 * drums), 0), at(b, 0))
                # клаве сон 2-3
                for bt in ([1, 2] if i % 2 == 0 else [0, 1.5, 3]):
                    add_at(perc, pan(woodblock(0.16 * drums, 1050), -0.35), at(b, bt))
                for k in range(8):
                    add_at(perc, pan(shaker((0.18 if k % 2 else 0.11) * drums, seed=int(rng.integers(1000))), 0.4),
                           at(b, k / 2))
            if mel:
                for mb, bt, m, dur in melody:
                    if mb != i % 8:
                        continue
                    if mel == "marimba":
                        x = marimba(midi_freq(m), dur * beat, 0.4, rng, roll=dur >= 1.5)
                        add_at(lead, pan(x, 0.2), at(b, bt))
                    else:
                        # рекинто: звонкая гитара с терцией ниже
                        x = pluck(midi_freq(m), dur * beat, 0.42, bright=0.7, rng=rng, decay=0.996)
                        y = pluck(midi_freq(m - 4 if m % 12 in (11, 4) else m - 3), dur * beat, 0.25, bright=0.6, rng=rng,
                                  decay=0.996)
                        add_at(lead, pan(x, 0.15), at(b, bt))
                        add_at(lead, pan(y, -0.1), at(b, bt) + int(0.01 * SR))
        b0 += bars

    dry = low * 0.26 + apply_reverb(perc * 0.4, mix=0.15, seconds=1.1)[:n]
    return seamless(guitar * 1.0 + lead * 0.85, length, tail, dry=dry)


# MARK: - Французская пекарня

def bakery():
    bpm = 116  # спокойный вальс: три доли в такте
    beat = 60 / bpm
    bar = 3 * beat
    # Am - Dm - E7 - Am - F - Dm - E7 - Am, вторая часть в до мажоре
    A = [([57, 60, 64], 45), ([57, 62, 65], 38), ([56, 59, 62, 64], 40), ([57, 60, 64], 45),
         ([57, 60, 65], 41), ([57, 62, 65], 38), ([56, 59, 62, 64], 40), ([57, 60, 64], 45)]
    B = [([55, 60, 64], 36), ([57, 60, 64], 45), ([57, 62, 65], 38), ([55, 59, 62, 65], 43),
         ([55, 60, 64], 36), ([57, 60, 65], 41), ([55, 59, 62, 65], 43), ([55, 60, 64], 36)]
    mel_a = [
        (0, 0, 76, 1), (0, 1, 75, 1), (0, 2, 76, 1), (1, 0, 77, 2), (1, 2, 74, 1),
        (2, 0, 71, 1), (2, 1, 74, 1), (2, 2, 77, 1), (3, 0, 76, 3),
        (4, 0, 72, 1), (4, 1, 74, 1), (4, 2, 77, 1), (5, 0, 81, 2), (5, 2, 77, 1),
        (6, 0, 76, 1), (6, 1, 74, 1), (6, 2, 71, 1), (7, 0, 69, 3),
    ]
    mel_b = [
        (0, 0, 79, 2), (0, 2, 76, 1), (1, 0, 72, 2), (1, 2, 76, 1),
        (2, 0, 77, 2), (2, 2, 74, 1), (3, 0, 79, 3),
        (4, 0, 79, 1), (4, 1, 81, 1), (4, 2, 79, 1), (5, 0, 77, 2), (5, 2, 74, 1),
        (6, 0, 71, 1), (6, 1, 74, 1), (6, 2, 77, 1), (7, 0, 76, 3),
    ]
    # (имя, тактов, гармония, мелодия, громкость шкатулки, ударные)
    sections = [
        ("intro", 4, A, None, 0.8, 0.0),
        ("a", 8, A, mel_a, 0.0, 0.6),
        ("b", 8, B, mel_b, 0.5, 0.8),
        ("a2", 8, A, mel_a, 0.6, 0.8),
        ("rest", 8, B, None, 0.9, 0.4),
        ("b2", 8, B, mel_b, 0.4, 0.8),
        ("a3", 8, A, mel_a, 0.0, 0.7),
        ("outro", 4, A, None, 0.8, 0.3),
    ]
    rng = np.random.default_rng(57)
    total = sum(s[1] for s in sections)
    length = int(total * bar * SR)
    tail = int(4.0 * SR)
    n = length + tail
    comp = np.zeros((n, 2))
    lead = np.zeros((n, 2))
    low = np.zeros((n, 2))
    box = np.zeros((n, 2))
    perc = np.zeros((n, 2))

    def at(b, bt):
        return int((b * bar + bt * beat) * SR)

    b0 = 0
    for name, bars, harmony, mel, box_level, drums in sections:
        for i in range(bars):
            b = b0 + i
            voices, root = harmony[i % len(harmony)]
            # ум: бас на раз, па-па: короткие аккорды гитарой на два и три
            add_at(low, pan(upright(midi_freq(root if i % 2 == 0 else root + 7 - (12 if root + 7 > 47 else 0)),
                                    0.9 * beat, 0.7), 0), at(b, 0))
            for bt in (1, 2):
                for k, m in enumerate(voices):
                    x = pluck(midi_freq(m), 0.32 * beat, 0.22 * rng.uniform(0.85, 1.0), bright=0.45, rng=rng, decay=0.994)
                    add_at(comp, pan(x, -0.25 + 0.15 * k), at(b, bt) + int(k * 0.008 * SR))
            if drums > 0:
                add_at(perc, pan(brush(0.3 * drums, seed=int(rng.integers(1000)), length=0.25), 0.1), at(b, 1))
                add_at(perc, pan(brush(0.25 * drums, seed=int(rng.integers(1000)), length=0.25), 0.1), at(b, 2))
            if mel:
                for mb, bt, m, dur in mel:
                    if mb != i % 8:
                        continue
                    x = accordion(midi_freq(m), dur * beat * 0.95, 0.26, rng)
                    add_at(lead, pan(x, -0.1), at(b, bt))
            else:
                # без мелодии аккордеон держит аккорд мягко
                for k, m in enumerate(voices):
                    add_at(lead, pan(accordion(midi_freq(m + 12), 2.8 * beat, 0.09, rng), 0.2 - 0.15 * k), at(b, 0))
            if box_level > 0:
                # шкатулка: арпеджио аккорда двумя октавами выше
                arp = [voices[0] + 24, voices[1] + 24, voices[-1] + 24]
                for bt, m in zip((0, 1, 2), arp if i % 2 == 0 else arp[::-1]):
                    add_at(box, pan(music_box(midi_freq(m), 0.12 * box_level), 0.35), at(b, bt))
        b0 += bars

    dry = low * 0.24 + apply_reverb(perc * 0.35, mix=0.15, seconds=1.0)[:n]
    return seamless(comp * 1.0 + lead * 0.8 + box * 0.7, length, tail, reverb_mix=0.28, dry=dry)


def main():
    out_dir = sys.argv[1]
    which = sys.argv[2:] or ["mexico", "bakery"]
    os.makedirs(out_dir, exist_ok=True)
    for name in which:
        x = {"mexico": mexico, "bakery": bakery}[name]()
        wav = os.path.join(out_dir, f"music_{name}.wav")
        write_wav(wav, x)
        m4a = os.path.join(out_dir, f"music_{name}.m4a")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", "112k", m4a], check=True)
        print("music:", m4a, os.path.getsize(m4a) // 1024, "KB", f"{len(x) / SR:.0f}s")


if __name__ == "__main__":
    main()
