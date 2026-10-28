"""Звуки действий Sortelier, синтезированные с нуля.

Запуск: python3 tools/audio/sfx.py <папка вывода>
Пишет sfx_<имя>.wav (моно, 44.1 кГц, 16 бит).
"""
import math
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from synth import SR, add_at, bandpass, bell_note, env_exp, highpass, lowpass, midi_freq, normalize, write_wav  # noqa: E402


def buf(seconds):
    return np.zeros(int(seconds * SR))


def tone(freq, dur, decay, attack=0.002, harmonics=((1, 1.0),), sweep=0.0):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = freq * (1 + sweep * t / dur)
    ph = 2 * math.pi * np.cumsum(f) / SR
    x = sum(a * np.sin(h * ph) for h, a in harmonics)
    return x * env_exp(n, attack, decay)


def pick():
    """Взял продукт: мягкий пузырьковый "поп" вверх."""
    x = tone(520, 0.12, 0.035, 0.002, ((1, 1.0), (2, 0.25)), sweep=0.7)
    return normalize(lowpass(x, 5000), 0.5)


def place():
    """Поставил на полку: деревянный "ток"."""
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(2).normal(0, 1, n)
    knock = bandpass(noise, 600, 2400) * np.exp(-t / 0.012) * 0.6
    body = (np.sin(2 * math.pi * 330 * t) * np.exp(-t / 0.035) + 0.5 * np.sin(2 * math.pi * 760 * t) * np.exp(-t / 0.02))
    return normalize(knock + body, 0.55)


def invalid():
    """Нельзя: глухой короткий звук вниз."""
    x = tone(210, 0.2, 0.06, 0.003, ((1, 1.0), (2, 0.15)), sweep=-0.35)
    return normalize(lowpass(x, 1500), 0.45)


def triple():
    """Тройка: три быстрые ноты колокольчика вверх."""
    out = buf(0.9)
    for i, m in enumerate((79, 83, 86)):
        add_at(out, bell_note(midi_freq(m), 0.7, 0.8 - 0.1 * i), int(i * 0.06 * SR))
    return normalize(out, 0.6)


def dish():
    """Блюдо: искристое арпеджио и шелест блесток."""
    out = buf(1.4)
    for i, m in enumerate((72, 76, 79, 84, 88)):
        add_at(out, bell_note(midi_freq(m), 0.9, 0.7), int(i * 0.07 * SR))
    n = int(1.0 * SR)
    t = np.arange(n) / SR
    shimmer = highpass(np.random.default_rng(5).normal(0, 1, n), 6000) * np.exp(-t / 0.35) * 0.18
    shimmer *= 0.5 + 0.5 * np.sin(2 * math.pi * 18 * t)
    add_at(out, shimmer, int(0.15 * SR))
    return normalize(out, 0.65)


def coin():
    """Монеты: двойной звон."""
    out = buf(0.5)
    add_at(out, tone(midi_freq(83), 0.25, 0.07, 0.001, ((1, 1.0), (2.01, 0.3), (3, 0.15))), 0)
    add_at(out, tone(midi_freq(88), 0.4, 0.14, 0.001, ((1, 1.0), (2.01, 0.3), (3, 0.15))), int(0.07 * SR))
    return normalize(out, 0.45)


def combo():
    """Серия: восходящий свист."""
    x = tone(600, 0.35, 0.18, 0.01, ((1, 1.0), (2, 0.2)), sweep=1.2)
    return normalize(lowpass(x, 6000), 0.4)


def star(i):
    """Звезда после уровня: каждая следующая выше."""
    m = (79, 83, 86)[i]
    out = buf(1.0)
    add_at(out, bell_note(midi_freq(m), 0.9, 0.8), 0)
    add_at(out, bell_note(midi_freq(m + 12), 0.5, 0.25), int(0.03 * SR))
    return normalize(out, 0.55)


def win():
    """Победа: короткий джингл."""
    out = buf(2.2)
    seq = [(72, 0.0), (76, 0.12), (79, 0.24), (84, 0.38)]
    for m, s in seq:
        add_at(out, bell_note(midi_freq(m), 1.4, 0.7), int(s * SR))
    for m in (60, 64, 67, 72):
        add_at(out, tone(midi_freq(m), 1.6, 0.6, 0.01, ((1, 1.0), (2, 0.2))) * 0.25, int(0.38 * SR))
    return normalize(out, 0.6)


def button():
    """Кнопка: тихий клик."""
    x = tone(1400, 0.05, 0.01, 0.0005, ((1, 1.0),))
    return normalize(x, 0.3)


def chest():
    """Сундук: стук крышки и блестки."""
    out = buf(1.4)
    add_at(out, place() * 1.2, 0)
    add_at(out, dish() * 0.8, int(0.12 * SR))
    return normalize(out, 0.6)


def customer():
    """Покупатель доволен: ласковое "динь-динь"."""
    out = buf(0.6)
    add_at(out, bell_note(midi_freq(88), 0.5, 0.5), 0)
    add_at(out, bell_note(midi_freq(91), 0.5, 0.45), int(0.09 * SR))
    return normalize(out, 0.42)


def unlock():
    """Открытие: мягкий подъем аккорда."""
    out = buf(1.6)
    for i, m in enumerate((67, 72, 76, 79, 84)):
        add_at(out, bell_note(midi_freq(m), 1.2, 0.6), int(i * 0.09 * SR))
    return normalize(out, 0.6)


SOUNDS = {
    "pick": pick, "place": place, "invalid": invalid, "triple": triple, "dish": dish, "coin": coin,
    "combo": combo, "star1": lambda: star(0), "star2": lambda: star(1), "star3": lambda: star(2),
    "win": win, "button": button, "chest": chest, "customer": customer, "unlock": unlock,
}


def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    for name, fn in SOUNDS.items():
        x = fn()
        # короткий фейд в конце, чтобы не щелкало
        fade = min(len(x), int(0.01 * SR))
        x[-fade:] *= np.linspace(1, 0, fade)
        write_wav(os.path.join(out_dir, f"sfx_{name}.wav"), x)
    print("sfx:", len(SOUNDS))


if __name__ == "__main__":
    main()
