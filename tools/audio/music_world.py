"""Музыка кухонь 6-10 в том же спокойном настроении, что и остальные треки.

Китайская: гучжэн (звонкие щипки с подтяжкой), флейта дицзы, деревянная коробочка, пентатоника.
Индийская: бурдон тампуры, ситар (щипок с "жужжанием" и скольжением), табла и шейкер, лад кафи.
Корейская: каягым и тэгым на пентатонике в качающемся размере 12/8, чангу.
Испанская: гитара фламенко во фригийском ладу (Am - G - F - E), кахон и пальмас.
Греческая: бузуки с тремоло, гитара, контрабас, сиртаки в неспешном темпе.

Каждый трек - бесшовный цикл. Запуск: python3 tools/audio/music_world.py <папка вывода> [china india korea spain greece]
Пишет music_<кухня>.m4a (нужен ffmpeg).
"""
import math
import os
import subprocess
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import SR, add_at, apply_reverb, kick, midi_freq, write_wav  # noqa: E402
from music_biomes import brush, flute, mandolin, pluck, shaker, upright, woodblock  # noqa: E402
from music_more import seamless  # noqa: E402


# MARK: - Инструменты

def bend_pluck(freq, dur, vel, rng, bright=0.8, bend=0.0, decay=0.996):
    """Щипок с подтяжкой высоты (гучжэн, ситар): пересэмплируем струну по огибающей высоты."""
    x = pluck(freq, dur, vel, bright=bright, rng=rng, decay=decay)
    if not bend:
        return x
    n = len(x)
    t = np.arange(n) / SR
    ratio = 1 + bend * np.clip((t - 0.12) / 0.18, 0, 1)
    pos = np.cumsum(ratio)
    pos = pos[pos < n - 1]
    return np.interp(pos, np.arange(n), x)


def sitar(freq, dur, vel, rng, bend=0.0):
    """Ситар: яркая струна, "джавари" (мягкое насыщение) и тихие симпатические струны октавой выше."""
    x = bend_pluck(freq, dur, vel, rng, bright=0.95, bend=bend, decay=0.998)
    x = np.tanh(x * 2.2) / 2.2 * 1.4
    y = pluck(freq * 2, dur, vel * 0.18, bright=0.9, rng=rng, decay=0.999)
    n = max(len(x), len(y))
    out = np.zeros(n)
    out[:len(x)] += x
    out[:len(y)] += y
    return out


def tabla(vel=0.5, pitch=300, dayan=True):
    """Табла: правый барабан звенит тоном, левый (баян) - низкий гул со скольжением вниз."""
    n = int(0.6 * SR)
    t = np.arange(n) / SR
    if dayan:
        x = np.sin(2 * math.pi * pitch * t) * np.exp(-t / 0.18) + 0.5 * np.sin(2 * math.pi * pitch * 2.0 * t) * np.exp(-t / 0.06)
    else:
        f = 90 * (1 + 0.6 * np.exp(-t / 0.08))
        x = np.sin(2 * math.pi * np.cumsum(f) / SR) * np.exp(-t / 0.25)
    return x * np.clip(t / 0.002, 0, 1) * vel


def drone(freqs, length, vel=0.12, rng=None):
    """Тампура: мягкие щипки по кругу Па - Са - Са - Са' весь трек."""
    rng = rng or np.random.default_rng(9)
    out = np.zeros(length + int(3 * SR))
    step = 1.1
    k = 0
    while k * step * SR < length:
        f = freqs[k % len(freqs)]
        add_at(out, pluck(f, 2.6, vel, bright=0.25, rng=rng, decay=0.9993), int(k * step * SR))
        k += 1
    return out[:length + int(3 * SR)]


def stereo(x, p):
    left = x * math.cos((p + 1) * math.pi / 4)
    right = x * math.sin((p + 1) * math.pi / 4)
    return np.stack([left, right], axis=1)


# MARK: - Общая раскладка трека

def arrange(bpm, beats_per_bar, chords, melody, sections, comp, lead, perc, seed, bass=True, extra=None):
    """chords: [(голоса аккомпанемента, бас)], melody: [(такт, доля, нота, длительность)] на цикл аккордов.

    comp(voices, b, rng) -> [(доля, нота, длительность, громкость)], lead(note, dur, rng) -> звук,
    perc(bar_index, level, rng) -> [(доля, звук, панорама)]. sections: [(тактов, громкость аккомпанемента, ударные, мелодия)].
    """
    beat = 60 / bpm
    bar = beats_per_bar * beat
    rng = np.random.default_rng(seed)
    total = sum(s[0] for s in sections)
    length = int(total * bar * SR)
    tail = int(4.0 * SR)
    n = length + tail
    acc, top, low, drums = (np.zeros((n, 2)) for _ in range(4))

    def at(b, bt):
        return int((b * bar + bt * beat) * SR)

    b0 = 0
    for bars, gtr, level, mel in sections:
        for i in range(bars):
            b = b0 + i
            voices, root = chords[i % len(chords)]
            for k, (pos, m, dur, v) in enumerate(comp(voices, i, rng)):
                x = pluck(midi_freq(m), dur * beat, 0.28 * gtr * v * rng.uniform(0.85, 1.0), bright=0.45, rng=rng,
                          decay=0.997)
                add_at(acc, stereo(x, -0.35 + 0.1 * (k % 5)), at(b, pos))
            if bass and gtr > 0:
                add_at(low, stereo(upright(midi_freq(root), 1.6 * beat, 0.7), 0), at(b, 0))
                if beats_per_bar >= 4:
                    fifth = root + 7 if root + 7 < 50 else root - 5
                    add_at(low, stereo(upright(midi_freq(fifth), 1.4 * beat, 0.55), 0), at(b, beats_per_bar / 2))
            if level > 0:
                for bt, x, p in perc(i, level, rng):
                    add_at(drums, stereo(x, p), at(b, bt))
            if mel:
                for mb, bt, m, dur in melody:
                    if mb == i % (max(x[0] for x in melody) + 1):
                        add_at(top, stereo(lead(m, dur * beat, rng), 0.15), at(b, bt))
        b0 += bars
    if extra is not None:
        e = extra(length, tail)
        acc[:len(e)] += stereo(e[:n], 0.0)[:n]
    dry = low * 0.26 + apply_reverb(drums * 0.4, mix=0.15, seconds=1.1)[:n]
    return seamless(acc + top * 0.85, length, tail, dry=dry)


STD = [(4, 1.0, 0.0, False), (8, 1.0, 0.8, True), (8, 1.0, 1.0, True), (8, 0.9, 0.6, False), (8, 1.0, 1.0, True),
       (8, 0.9, 0.9, True), (4, 0.8, 0.4, False)]


def arp(pattern):
    """Аккомпанемент перебором: pattern = [(доля, номер голоса, длительность, громкость)]."""
    def comp(voices, i, rng):
        return [(pos, voices[k % len(voices)], dur, v) for pos, k, dur, v in pattern]
    return comp


# MARK: - Китай

def china():
    # пентатоника ре: D E F# A B
    chords = [([62, 66, 69, 74], 38), ([59, 62, 66, 71], 47), ([57, 62, 66, 69], 45), ([62, 66, 69, 74], 38),
              ([55, 59, 62, 67], 43), ([57, 61, 64, 69], 45), ([59, 62, 66, 71], 47), ([62, 66, 69, 74], 38)]
    melody = [(0, 0, 78, 1.5), (0, 1.5, 76, 0.5), (0, 2, 74, 2), (1, 0, 71, 1), (1, 1, 74, 1), (1, 2, 76, 2),
              (2, 0, 78, 1), (2, 1, 81, 1), (2, 2, 78, 1), (2, 3, 76, 1), (3, 0, 74, 4),
              (4, 0, 71, 1.5), (4, 1.5, 74, 0.5), (4, 2, 76, 2), (5, 0, 78, 1), (5, 1, 76, 1), (5, 2, 73, 2),
              (6, 0, 71, 1), (6, 1, 69, 1), (6, 2, 71, 2), (7, 0, 74, 4)]

    def lead(m, dur, rng):
        if dur >= 1.5:
            return flute(midi_freq(m), dur, 0.32, rng)
        return bend_pluck(midi_freq(m), dur, 0.45, rng, bright=0.85, bend=0.03 if dur >= 1 else 0.0)

    def perc(i, level, rng):
        out = [(0, kick(0.25 * level), 0)]
        out += [(bt, woodblock(0.14 * level, 900), -0.4) for bt in (1, 2.5, 3)]
        return out
    comp = arp([(0, 0, 1, 0.9), (0.5, 1, 0.5, 0.5), (1, 2, 1, 0.6), (1.5, 3, 0.5, 0.5), (2, 1, 1, 0.7), (3, 2, 1, 0.6)])
    return arrange(80, 4, chords, melody, STD, comp, lead, perc, 61)


# MARK: - Индия

def india():
    # лад кафи от ре, аккомпанемент - ситар перебором, бурдон Ре-Ля
    chords = [([62, 69, 74], 38), ([62, 69, 74], 38), ([60, 67, 72], 36), ([62, 69, 74], 38),
              ([62, 69, 74], 38), ([65, 69, 72], 41), ([60, 67, 72], 36), ([62, 69, 74], 38)]
    melody = [(0, 0, 74, 1), (0, 1, 76, 0.5), (0, 1.5, 77, 0.5), (0, 2, 79, 2), (1, 0, 77, 1), (1, 1, 76, 1),
              (1, 2, 74, 2), (2, 0, 72, 1), (2, 1, 74, 1), (2, 2, 76, 1), (2, 3, 77, 1), (3, 0, 76, 3),
              (4, 0, 81, 1.5), (4, 1.5, 79, 0.5), (4, 2, 77, 2), (5, 0, 79, 1), (5, 1, 77, 1), (5, 2, 76, 2),
              (6, 0, 74, 1), (6, 1, 72, 1), (6, 2, 74, 2), (7, 0, 74, 4)]

    def lead(m, dur, rng):
        return sitar(midi_freq(m), dur, 0.42, rng, bend=0.06 if dur >= 2 else 0.0)

    def perc(i, level, rng):
        # теку: дха дхин дхин дха | дха тин тин та
        out = []
        for k in range(8):
            bt = k / 2
            ring = k in (0, 3, 4) or (k % 2 == 1 and rng.random() < 0.4)
            out.append((bt, tabla(0.13 * level, 320 if k % 4 else 280), 0.25))
            if ring:
                out.append((bt, tabla(0.16 * level, dayan=False), -0.1))
        out += [(k / 4, shaker(0.06 * level, seed=int(rng.integers(999))), 0.5) for k in range(16)]
        return out
    comp = arp([(0, 0, 2, 0.6), (2, 1, 2, 0.4)])

    def extra(length, tail):
        return drone([midi_freq(45), midi_freq(50), midi_freq(50), midi_freq(38)], length + tail, 0.1)
    x = arrange(76, 4, chords, melody, STD, comp, lead, perc, 71, bass=False, extra=extra)
    # щипки ситара дают острые пики: мягко сжимаем, чтобы трек звучал так же громко, как соседние
    return np.tanh(x * 2.2) / math.tanh(2.2) * 0.8


# MARK: - Корея

def korea():
    # пентатоника соль в качающемся размере: 4 доли по 3 восьмых
    chords = [([55, 62, 67], 43), ([57, 64, 69], 45), ([52, 59, 64], 40), ([55, 62, 67], 43),
              ([60, 67, 72], 48), ([57, 64, 69], 45), ([62, 69, 74], 38), ([55, 62, 67], 43)]
    third = 1 / 3
    melody = [(0, 0, 74, 1 + 2 * third), (0, 1 + 2 * third, 76, third), (0, 2, 79, 2), (1, 0, 76, 1), (1, 1, 74, 1),
              (1, 2, 71, 2), (2, 0, 69, 1), (2, 1, 71, 1), (2, 2, 74, 1), (2, 3, 76, 1), (3, 0, 74, 4),
              (4, 0, 79, 1), (4, 1, 81, 1), (4, 2, 79, 2), (5, 0, 76, 1 + 2 * third), (5, 1 + 2 * third, 74, third),
              (5, 2, 71, 2), (6, 0, 69, 1), (6, 1, 74, 1), (6, 2, 71, 2), (7, 0, 67, 4)]

    def lead(m, dur, rng):
        if dur >= 2:
            return flute(midi_freq(m), dur, 0.3, rng)
        return bend_pluck(midi_freq(m), dur, 0.42, rng, bright=0.6, bend=-0.025 if dur >= 1 else 0.0, decay=0.995)

    def perc(i, level, rng):
        out = [(0, kick(0.28 * level), 0), (2, kick(0.18 * level), 0)]
        for k in range(4):
            out.append((k + 2 * third, woodblock(0.12 * level, 700), -0.3))
        return out
    comp = arp([(0, 0, 1, 0.8), (2 * third, 1, third, 0.5), (1, 2, 1, 0.6), (2, 0, 1, 0.7), (2 + 2 * third, 1, third, 0.5),
                (3, 2, 1, 0.6)])
    return arrange(70, 4, chords, melody, STD, comp, lead, perc, 81)


# MARK: - Испания

def spain():
    # фригийская каденция ля: Am - G - F - E, мягкое расгеадо
    chords = [([57, 64, 69, 72], 45), ([55, 62, 67, 71], 43), ([53, 60, 65, 69], 41), ([52, 59, 64, 68], 40),
              ([57, 64, 69, 72], 45), ([55, 62, 67, 71], 43), ([53, 60, 65, 69], 41), ([52, 59, 64, 68], 40)]
    melody = [(0, 0, 76, 1), (0, 1, 77, 0.5), (0, 1.5, 76, 0.5), (0, 2, 74, 2), (1, 0, 74, 1), (1, 1, 72, 1),
              (1, 2, 71, 2), (2, 0, 72, 1), (2, 1, 74, 1), (2, 2, 72, 1), (2, 3, 71, 1), (3, 0, 68, 3), (3, 3, 71, 1),
              (4, 0, 72, 1.5), (4, 1.5, 74, 0.5), (4, 2, 76, 2), (5, 0, 77, 1), (5, 1, 76, 1), (5, 2, 74, 2),
              (6, 0, 72, 1), (6, 1, 71, 1), (6, 2, 69, 2), (7, 0, 68, 2), (7, 2, 64, 2)]

    def lead(m, dur, rng):
        x = pluck(midi_freq(m), dur, 0.45, bright=0.55, rng=rng, decay=0.996)
        return x

    def perc(i, level, rng):
        out = [(0, kick(0.32 * level), 0), (2.5, kick(0.18 * level), 0)]
        out += [(bt, brush(0.18 * level, seed=int(rng.integers(999)), length=0.2), 0.3) for bt in (1, 3)]
        out += [(bt, shaker(0.14 * level, seed=int(rng.integers(999))), -0.4) for bt in (1.5, 2, 3.5)]
        return out

    def comp(voices, i, rng):
        # расгеадо: веер вниз на раз и три, короткие удары между
        out = []
        for pos, v in ((0, 1.0), (1.5, 0.5), (2, 0.8), (3, 0.5), (3.5, 0.4)):
            for k, m in enumerate(voices):
                out.append((pos + k * 0.025, m, 0.9, v))
        return out
    return arrange(88, 4, chords, melody, STD, comp, lead, perc, 91)


# MARK: - Греция

def greece():
    # ре минор сиртаки: Dm - Gm - A7 - Dm, бузуки ведет мелодию тремоло
    chords = [([62, 65, 69], 38), ([62, 65, 69], 38), ([55, 62, 67, 70], 43), ([57, 61, 64, 67], 45),
              ([62, 65, 69], 38), ([60, 64, 67], 48), ([57, 61, 64, 67], 45), ([62, 65, 69], 38)]
    melody = [(0, 0, 74, 1), (0, 1, 76, 1), (0, 2, 77, 1), (0, 3, 79, 1), (1, 0, 81, 2), (1, 2, 77, 2),
              (2, 0, 79, 1), (2, 1, 77, 1), (2, 2, 74, 2), (3, 0, 76, 1), (3, 1, 73, 1), (3, 2, 76, 2),
              (4, 0, 74, 1), (4, 1, 76, 1), (4, 2, 77, 1), (4, 3, 74, 1), (5, 0, 72, 2), (5, 2, 76, 2),
              (6, 0, 73, 1), (6, 1, 76, 1), (6, 2, 79, 1), (6, 3, 76, 1), (7, 0, 74, 4)]

    def lead(m, dur, rng):
        return mandolin(midi_freq(m), dur, 0.42, rng, tremolo=dur >= 2)

    def perc(i, level, rng):
        out = [(0, kick(0.3 * level), 0), (2, kick(0.2 * level), 0)]
        out += [(bt, brush(0.14 * level, seed=int(rng.integers(999)), length=0.18), 0.3) for bt in (1, 3)]
        return out
    comp = arp([(0, 0, 0.5, 0.4), (1, 0, 0.5, 0.8), (1, 1, 0.5, 0.6), (1, 2, 0.5, 0.6), (2, 0, 0.5, 0.4),
                (3, 0, 0.5, 0.8), (3, 1, 0.5, 0.6), (3, 2, 0.5, 0.6)])
    return arrange(92, 4, chords, melody, STD, comp, lead, perc, 101)


TRACKS = {"china": china, "india": india, "korea": korea, "spain": spain, "greece": greece}


def main():
    out_dir = sys.argv[1]
    which = sys.argv[2:] or list(TRACKS)
    os.makedirs(out_dir, exist_ok=True)
    for name in which:
        x = TRACKS[name]()
        wav = os.path.join(out_dir, f"music_{name}.wav")
        write_wav(wav, x)
        m4a = os.path.join(out_dir, f"music_{name}.m4a")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", wav, "-c:a", "aac", "-b:a", "112k", m4a], check=True)
        print("music:", m4a, os.path.getsize(m4a) // 1024, "KB", f"{len(x) / SR:.0f}s")


if __name__ == "__main__":
    main()
