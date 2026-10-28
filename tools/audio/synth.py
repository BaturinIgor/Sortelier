"""Простой синтезатор для музыки и звуков Sortelier: numpy, без внешних сэмплов.

Все звуки собираются из синусов, шума, огибающих и фильтров, поэтому права на них
целиком наши. Частота дискретизации общая для всех модулей.
"""
import math

import numpy as np
from scipy import signal

SR = 44100


def note_freq(name):
    """'A4' -> 440.0, поддерживает диезы и бемоли: 'C#5', 'Bb3'."""
    names = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
    base = names[name[0]]
    rest = name[1:]
    if rest.startswith("#"):
        base += 1
        rest = rest[1:]
    elif rest.startswith("b"):
        base -= 1
        rest = rest[1:]
    octave = int(rest)
    midi = 12 * (octave + 1) + base
    return 440.0 * 2 ** ((midi - 69) / 12)


def midi_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


def t_axis(dur):
    return np.arange(int(dur * SR)) / SR


def env_adsr(n, a=0.01, d=0.2, s=0.6, r=0.3, hold=None):
    """Огибающая ADSR длиной n отсчетов; hold - длительность до отпускания."""
    t = np.arange(n) / SR
    hold = hold if hold is not None else max(0.0, n / SR - r)
    e = np.zeros(n)
    e = np.where(t < a, t / max(a, 1e-6), e)
    dd = (t >= a) & (t < a + d)
    e = np.where(dd, 1 - (1 - s) * (t - a) / max(d, 1e-6), e)
    sus = (t >= a + d) & (t < hold)
    e = np.where(sus, s, e)
    rel = t >= hold
    level = s if hold >= a + d else (1 - (1 - s) * (hold - a) / max(d, 1e-6) if hold > a else hold / max(a, 1e-6))
    e = np.where(rel, level * np.exp(-(t - hold) / max(r / 4, 1e-6)), e)
    return e


def env_exp(n, attack=0.004, decay=0.5):
    t = np.arange(n) / SR
    att = np.clip(t / max(attack, 1e-6), 0, 1)
    return att * np.exp(-t / max(decay, 1e-6))


def lowpass(x, cutoff, order=2):
    b, a = signal.butter(order, min(cutoff, SR / 2 * 0.99) / (SR / 2), "low")
    return signal.lfilter(b, a, x, axis=0)


def highpass(x, cutoff, order=2):
    b, a = signal.butter(order, cutoff / (SR / 2), "high")
    return signal.lfilter(b, a, x, axis=0)


def bandpass(x, lo, hi, order=2):
    b, a = signal.butter(order, [lo / (SR / 2), min(hi, SR / 2 * 0.99) / (SR / 2)], "band")
    return signal.lfilter(b, a, x, axis=0)


def ep_note(freq, dur, vel=0.8, rng=None):
    """Электропиано в духе Rhodes: FM с затухающим индексом и легкий молоточек."""
    rng = rng or np.random.default_rng(0)
    n = int((dur + 1.6) * SR)
    t = np.arange(n) / SR
    detune = 1 + rng.uniform(-0.0015, 0.0015)
    f = freq * detune
    index = (1.6 + 1.4 * vel) * np.exp(-t / 0.45) + 0.25
    mod = np.sin(2 * math.pi * f * t) * index
    tine = np.sin(2 * math.pi * f * t + mod)
    bark = 0.07 * vel * np.sin(2 * math.pi * f * 14 * t) * np.exp(-t / 0.025)
    amp = env_exp(n, 0.007, 1.8 + 0.5 * (1 - min(freq, 800) / 800))
    # медленное тремоло, как у настоящего Rhodes
    amp = amp * (1 - 0.12 + 0.12 * np.sin(2 * math.pi * 4.2 * t + rng.uniform(0, 6.28)))
    # отпускание клавиши
    rel = t > dur
    amp = np.where(rel, amp * np.exp(-(t - dur) / 0.18), amp)
    return (tine + bark) * amp * vel


def bass_note(freq, dur, vel=0.8):
    n = int((dur + 0.4) * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * math.pi * freq * t) + 0.25 * np.sin(4 * math.pi * freq * t) + 0.08 * np.sin(6 * math.pi * freq * t)
    e = env_adsr(n, a=0.012, d=0.25, s=0.7, r=0.25, hold=dur)
    return np.tanh(1.3 * x * e) * vel


def pad_note(freq, dur, vel=0.5, rng=None):
    """Мягкий пэд: расстроенные пилы через фильтр с медленной атакой."""
    rng = rng or np.random.default_rng(1)
    n = int((dur + 1.5) * SR)
    t = np.arange(n) / SR
    x = np.zeros(n)
    for k in range(5):
        det = 1 + (k - 2) * 0.004 + rng.uniform(-0.001, 0.001)
        ph = rng.uniform(0, 1)
        x += signal.sawtooth(2 * math.pi * (freq * det * t + ph))
    x /= 5
    x = lowpass(x, 1400, 2)
    e = env_adsr(n, a=0.9, d=0.5, s=0.85, r=1.4, hold=dur)
    return x * e * vel


def bell_note(freq, dur=1.2, vel=0.7):
    """Колокольчик/калимба: синус с негармоническими обертонами, быстрое затухание."""
    n = int(dur * SR)
    t = np.arange(n) / SR
    x = (np.sin(2 * math.pi * freq * t) * np.exp(-t / (dur * 0.45))
         + 0.35 * np.sin(2 * math.pi * freq * 2.76 * t) * np.exp(-t / (dur * 0.12))
         + 0.18 * np.sin(2 * math.pi * freq * 5.4 * t) * np.exp(-t / (dur * 0.06)))
    att = np.clip(t / 0.003, 0, 1)
    return x * att * vel


def kick(vel=1.0):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 42 + 70 * np.exp(-t / 0.035)
    ph = 2 * math.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t / 0.22)
    click = np.random.default_rng(3).normal(0, 1, n) * np.exp(-t / 0.004) * 0.15
    return np.tanh(1.5 * (body + lowpass(click, 3000))) * vel


def snare(vel=1.0, seed=4):
    n = int(0.35 * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(seed).normal(0, 1, n)
    nz = bandpass(noise, 1200, 6500) * np.exp(-t / 0.07)
    body = np.sin(2 * math.pi * 185 * t) * np.exp(-t / 0.05) * 0.6
    return (nz * 0.8 + body) * vel


def rim(vel=1.0):
    n = int(0.12 * SR)
    t = np.arange(n) / SR
    x = np.sin(2 * math.pi * 820 * t) * np.exp(-t / 0.012) + 0.5 * np.sin(2 * math.pi * 1650 * t) * np.exp(-t / 0.008)
    return x * vel


def hat(vel=1.0, open_=False, seed=5):
    n = int((0.3 if open_ else 0.08) * SR)
    t = np.arange(n) / SR
    noise = np.random.default_rng(seed).normal(0, 1, n)
    x = highpass(noise, 7000, 2) * np.exp(-t / (0.09 if open_ else 0.018))
    return x * vel


def reverb_ir(seconds=1.8, seed=7, damp=5000):
    """Синтетический импульсный отклик комнаты: стерео шум с экспоненциальным затуханием."""
    n = int(seconds * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(seed)
    ir = rng.normal(0, 1, (n, 2)) * np.exp(-t / (seconds / 6.5))[:, None]
    ir = lowpass(ir, damp, 1)
    ir[: int(0.012 * SR)] = 0  # предзадержка
    ir /= np.sqrt(np.sum(ir ** 2, axis=0, keepdims=True))
    return ir


def apply_reverb(x, mix=0.25, seconds=1.8):
    """x: (n, 2). Возвращает сигнал с хвостом той же длины + хвост."""
    ir = reverb_ir(seconds)
    wet = np.stack([signal.fftconvolve(x[:, c], ir[:, c]) for c in range(2)], axis=1)
    out = np.zeros_like(wet)
    out[: len(x)] += x * (1 - mix * 0.5)
    out += wet * mix
    return out


def pan(mono, p):
    """p: -1 лево, +1 право, равная мощность."""
    a = (p + 1) * math.pi / 4
    return np.stack([mono * math.cos(a), mono * math.sin(a)], axis=1)


def add_at(buf, x, start):
    """Добавляет x (n,) или (n,2) в buf с позиции start (в отсчетах)."""
    if start >= len(buf):
        return
    if start < 0:
        x = x[-start:]
        start = 0
    end = min(len(buf), start + len(x))
    if x.ndim == 1 and buf.ndim == 2:
        x = np.stack([x, x], axis=1)
    buf[start:end] += x[: end - start]


def normalize(x, peak=0.89):
    m = np.max(np.abs(x))
    return x * (peak / m) if m > 0 else x


def write_wav(path, x):
    from scipy.io import wavfile
    y = np.clip(x, -1, 1)
    wavfile.write(path, SR, (y * 32767).astype(np.int16))
