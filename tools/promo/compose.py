"""Рекламные ролики Sortelier для TikTok, YouTube Shorts и YouTube.

Запуск: python3 tools/promo/compose.py <папка записей> <папка выхода> [--only ru,en] [--ads sort,market,tour] [--formats v,h]
Записи берутся из ветки ci-promo (workflow "Promo videos"): <язык>_<сцена>.mp4, .start (время первого кадра)
и .log (строки "SFX <время> <звук> <громкость>" из отладочной сборки с -uiSfxLog).

Форматы: v - 1080x1920 (TikTok, Reels, Shorts), h - 1920x1080 (YouTube, превью и In-Stream).
Звук собирается здесь: в записи симулятора его нет, поэтому эффекты кладутся по логу, плюс музыка кухни.
"""
import argparse
import json
import math
import os
import random
import subprocess
import tempfile

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
FONT = os.path.join(ROOT, "Sortelier", "Resources", "Fonts", "Nunito-Black.ttf")
AUDIO = os.path.join(ROOT, "Sortelier", "Resources", "Audio")
SPRITES = os.path.join(ROOT, "Sortelier", "Resources", "Sprites")
ICON = os.path.join(ROOT, "Sortelier", "Resources", "Assets.xcassets", "AppIcon.appiconset", "AppIcon.png")
SCRIPT = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "script.json")))
FPS = 30
SR = 44100
SIZES = {"v": (1080, 1920), "h": (1920, 1080)}
# 9:16: высота полосы с подписью и ширина игры (по бокам и сверху - размытый фон)
V_BAND = 360
V_GAME_W = 1000


def run(cmd):
    r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if r.returncode:
        raise SystemExit("ffmpeg failed: " + " ".join(cmd) + "\n" + r.stderr.decode()[-3000:])
    return r.stdout


def probe(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height:format=duration",
               "-of", "json", path])
    j = json.loads(out)
    return j["streams"][0]["width"], j["streams"][0]["height"], float(j["format"]["duration"])


# ---------- Картинки: подписи, фон, концовка ----------

def font(size):
    return ImageFont.truetype(FONT, size)


def wrap(draw, text, size, max_w, max_lines=3):
    """Самый крупный кегль, при котором текст влезает в max_lines строк шириной max_w."""
    while size > 30:
        f = font(size)
        lines, cur = [], ""
        for word in text.split(" "):
            trial = (cur + " " + word).strip()
            if draw.textlength(trial, font=f) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = word
        lines.append(cur)
        if len(lines) <= max_lines and max(draw.textlength(l, font=f) for l in lines) <= max_w:
            return f, lines
        size -= 4
    return font(size), [text]


def text_block(im, text, cx, y, size, max_w, fill=(255, 255, 255), stroke=(70, 35, 20), max_lines=3, highlight=None):
    """Крупный текст с обводкой и тенью, как в игре. highlight - слово, которое красится в желтый."""
    d = ImageDraw.Draw(im)
    f, lines = wrap(d, text, size, max_w, max_lines)
    sw = max(6, f.size // 9)
    shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    yy = y
    boxes = []
    for line in lines:
        w = d.textlength(line, font=f)
        boxes.append((line, cx - w / 2, yy))
        sd.text((cx - w / 2, yy + f.size * 0.09), line, font=f, fill=(0, 0, 0, 120), stroke_width=sw, stroke_fill=(0, 0, 0, 120))
        yy += f.size * 1.08
    im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(f.size / 10)))
    for line, x, ly in boxes:
        if highlight and highlight in line:
            # слово-акцент другим цветом: рисуем по кускам
            before, _, after = line.partition(highlight)
            for part, color in ((before, fill), (highlight, (255, 214, 64)), (after, fill)):
                if part:
                    d.text((x, ly), part, font=f, fill=color, stroke_width=sw, stroke_fill=stroke)
                    x += d.textlength(part, font=f)
        else:
            d.text((x, ly), line, font=f, fill=fill, stroke_width=sw, stroke_fill=stroke)
    return yy


def gradient(size, top, bottom):
    w, h = size
    col = np.linspace(0, 1, h)[:, None]
    arr = np.array(top)[None, :] * (1 - col) + np.array(bottom)[None, :] * col
    arr = np.repeat(arr[:, None, :], w, axis=1).astype(np.uint8)
    im = Image.fromarray(arr, "RGB").convert("RGBA")
    rng = random.Random(7)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(16):
        r = rng.randint(60, 240)
        x, y = rng.randint(-100, w + 100), rng.randint(-100, h + 100)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(14, 30)))
    return Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(30)))


def sprite(name, size, rot=0):
    path = os.path.join(SPRITES, name + ".png")
    if not os.path.exists(path):
        return None
    sp = Image.open(path).convert("RGBA").resize((size, size), Image.LANCZOS)
    return sp.rotate(rot, resample=Image.BICUBIC, expand=True)


def paste_sprite(im, name, cx, cy, size, rot=0):
    sp = sprite(name, size, rot)
    if sp is None:
        return
    sh = Image.new("RGBA", sp.size, (0, 0, 0, 0))
    sh.putalpha(sp.getchannel("A").point(lambda a: a * 0.35))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (int(cx - sp.width / 2 + 8), int(cy - sp.height / 2 + 14)))
    im.alpha_composite(sp, (int(cx - sp.width / 2), int(cy - sp.height / 2)))


def rounded(im, radius):
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.width - 1, im.height - 1), radius, fill=255)
    out = im.copy()
    out.putalpha(mask)
    return out


def caption_overlay(fmt, caption, highlight, style, phone_box):
    """Слой поверх видео: для v - подпись сверху прямо на игре, для h - фон, телефон-рамка и подпись справа."""
    W, H = SIZES[fmt]
    if fmt == "v":
        # сверху полоса под подпись, игра ниже (см. V_BAND); фон - размытая та же запись
        im = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        if caption:
            d = ImageDraw.Draw(im)
            f, lines = wrap(d, caption, 104, W - 90, 2)
            block = len(lines) * f.size * 1.08
            text_block(im, caption, W / 2, (V_BAND - block) / 2 + 6, 104, W - 90, highlight=highlight, max_lines=2)
        return im
    top, bottom = style
    im = gradient((W, H), top, bottom)
    x0, y0, x1, y1 = phone_box
    bezel = 18
    d = ImageDraw.Draw(im)
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0 - bezel + 10, y0 - bezel + 24, x1 + bezel + 10, y1 + bezel + 24), 90, fill=(0, 0, 0, 110))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(24)))
    d.rounded_rectangle((x0 - bezel, y0 - bezel, x1 + bezel, y1 + bezel), 90, fill=(28, 28, 34, 255))
    # окно экрана прозрачное: видео подкладывается снизу
    hole = Image.new("L", (W, H), 255)
    ImageDraw.Draw(hole).rounded_rectangle((x0, y0, x1, y1), 72, fill=0)
    alpha = np.minimum(np.array(im.getchannel("A")), np.array(hole))
    im.putalpha(Image.fromarray(alpha))
    if caption:
        tx = (x1 + bezel + W) / 2
        text_block(im, caption, tx, 360, 120, W - x1 - 200, highlight=highlight, max_lines=3)
    return im


def endcard_frames(fmt, lang, style, n):
    """Концовка: иконка выпрыгивает, название, кнопка "Играть бесплатно" пульсирует."""
    W, H = SIZES[fmt]
    t = SCRIPT["texts"][lang]
    base = gradient((W, H), *style)
    icon = rounded(Image.open(ICON).convert("RGBA").resize((400, 400), Image.LANCZOS), 90)
    deco = ["dish_burger", "dish_sushi", "dish_pizza", "dish_taco", "dish_croissant", "tomato"]
    if fmt == "v":
        spots = [(150, 330, -14), (930, 420, 12), (130, 1560, 10), (950, 1640, -10)]
        icon_c, title_y, sub_y, btn_y = (W / 2, 640), 900, 1090, 1300
    else:
        spots = [(200, 200, -14), (1720, 230, 12), (230, 860, 10), (1700, 880, -10)]
        icon_c, title_y, sub_y, btn_y = (W / 2, 270), 470, 640, 740
    static = base.copy()
    for name, (x, y, r) in zip(deco, spots):
        paste_sprite(static, name, x, y, 230, r)
    text_block(static, t["name"], W / 2, title_y, 120, W - 160, max_lines=2)
    text_block(static, t["tagline"], W / 2, sub_y, 70, W - 200, fill=(255, 240, 200), max_lines=2)
    frames = []
    for i in range(n):
        im = static.copy()
        k = min(1, i / 9)
        s = 1 + 0.25 * math.sin(k * math.pi) if k < 1 else 1  # прыжок иконки
        s = s * (0.4 + 0.6 * k)
        ic = icon.resize((int(400 * s), int(400 * s)), Image.LANCZOS)
        im.alpha_composite(ic, (int(icon_c[0] - ic.width / 2), int(icon_c[1] - ic.height / 2)))
        # кнопка
        pulse = 1 + 0.05 * math.sin(i / FPS * 2 * math.pi * 1.4)
        bw, bh = int(640 * pulse), int(150 * pulse)
        bx, by = int(W / 2 - bw / 2), int(btn_y - bh / 2 + 60)
        d = ImageDraw.Draw(im)
        d.rounded_rectangle((bx, by + 12, bx + bw, by + bh + 12), bh // 2, fill=(40, 120, 30))
        d.rounded_rectangle((bx, by, bx + bw, by + bh), bh // 2, fill=(110, 210, 70), outline=(255, 255, 255), width=6)
        f = font(int(64 * pulse))
        label = t["cta"]
        lw = d.textlength(label, font=f)
        d.text((W / 2 - lw / 2, by + bh / 2 - f.size * 0.62), label, font=f, fill=(255, 255, 255), stroke_width=5,
               stroke_fill=(40, 110, 30))
        f2 = font(54)
        store = t["store"]
        sw_ = d.textlength(store, font=f2)
        d.text((W / 2 - sw_ / 2, by + bh + 36), store, font=f2, fill=(255, 255, 255), stroke_width=4, stroke_fill=(60, 40, 30))
        frames.append(im.convert("RGB"))
    return frames


# ---------- Видео ----------

def phone_box(fmt):
    W, H = SIZES[fmt]
    if fmt != "h":
        return None
    h = H - 110
    w = round(h * 1320 / 2868)
    x0 = 330
    return (x0, 55, x0 + w, 55 + h)


def render_segment(src, seg, fmt, overlay_png, out, clip_size):
    W, H = SIZES[fmt]
    t0, dur, speed = seg["t0"], seg["dur"], seg.get("speed", 1.0)
    cw, ch = clip_size
    zoom = seg.get("zoom", 1.0)
    if fmt == "v":
        # игра шириной V_GAME_W под полосой подписи, окно по высоте начинается с доли "y" от верха записи
        gw = V_GAME_W
        gh = H - V_BAND
        sh = int(ch * gw / cw) // 2 * 2
        y = min(int(sh * seg.get("y", 0.055)), sh - gh)
        trim = f"trim=start={t0}:duration={dur * speed},setpts=(PTS-STARTPTS)/{speed},fps={FPS}"
        vf = (f"[0:v]{trim},split[a][b];"
              f"[a]scale={W}:-2,crop={W}:{H}:0:(ih-{H})/2,gblur=sigma=40,eq=brightness=-0.12:saturation=1.2[bg];"
              f"[b]scale={gw}:{sh}:flags=lanczos,crop={gw}:{gh}:0:{y}[g];"
              f"[bg][g]overlay={(W - gw) // 2}:{V_BAND}[c];[c][1:v]overlay=0:0,format=yuv420p[o]")
    else:
        x0, y0, x1, y1 = phone_box(fmt)
        pw, ph = x1 - x0, y1 - y0
        vf = (f"color=c=black:s={W}x{H}:r={FPS}:d={dur}[bg];"
              f"[0:v]trim=start={t0}:duration={dur * speed},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
              f"scale={pw}:{ph}:flags=lanczos[g];[bg][g]overlay={x0}:{y0}[b];[b][1:v]overlay=0:0,format=yuv420p[o]")
    run(["ffmpeg", "-y", "-v", "error", "-i", src, "-loop", "1", "-i", overlay_png, "-filter_complex", vf, "-map", "[o]",
         "-t", f"{dur:.3f}", "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-an", out])


def frames_to_video(frames, out):
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s",
                          f"{frames[0].width}x{frames[0].height}", "-r", str(FPS), "-i", "-", "-c:v", "libx264",
                          "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", out], stdin=subprocess.PIPE)
    for f in frames:
        p.stdin.write(f.tobytes())
    p.stdin.close()
    p.wait()


# ---------- Звук ----------

_cache = {}


def load_audio(path):
    if path not in _cache:
        raw = run(["ffmpeg", "-v", "error", "-i", path, "-f", "f32le", "-ac", "2", "-ar", str(SR), "-"])
        _cache[path] = np.frombuffer(raw, dtype=np.float32).reshape(-1, 2).copy()
    return _cache[path]


def sfx_events(rec_dir, name):
    start = float(open(os.path.join(rec_dir, name + ".start")).read().strip())
    events = []
    log = os.path.join(rec_dir, name + ".log")
    if os.path.exists(log):
        for line in open(log, errors="ignore"):
            parts = line.split()
            if len(parts) == 4 and parts[0] == "SFX":
                events.append((float(parts[1]) - start, parts[2], float(parts[3])))
    return events


def mix_audio(total, placed, music, music_vol, out):
    buf = np.zeros((int(total * SR) + SR, 2), dtype=np.float32)
    last = {}
    for t, effect, vol in sorted(placed):
        if t < 0 or t >= total:
            continue
        # каскады "3 в ряд" дают десятки одинаковых звуков подряд: не чаще раза в 60 мс
        if t - last.get(effect, -1) < 0.06:
            continue
        last[effect] = t
        path = os.path.join(AUDIO, f"sfx_{effect}.wav")
        if not os.path.exists(path):
            continue
        a = load_audio(path) * vol * 0.75
        i = int(t * SR)
        n = min(len(a), len(buf) - i)
        buf[i:i + n] += a[:n]
    if music:
        m = load_audio(os.path.join(AUDIO, music + ".m4a"))
        reps = int(math.ceil(len(buf) / len(m)))
        m = np.tile(m, (reps, 1))[:len(buf)] * music_vol
        fade = int(1.2 * SR)
        end = int(total * SR)
        m[end - fade:end] *= np.linspace(1, 0, fade)[:, None]
        m[end:] = 0
        buf += m
    buf = np.tanh(buf[:int(total * SR)] * 1.1) * 0.95
    p = subprocess.Popen(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ac", "2", "-ar", str(SR), "-i", "-",
                          "-c:a", "aac", "-b:a", "192k", out], stdin=subprocess.PIPE)
    p.stdin.write(buf.astype(np.float32).tobytes())
    p.stdin.close()
    p.wait()


# ---------- Сборка ролика ----------

def build(rec_dir, out_dir, lang, ad_key, fmt, work):
    ad = SCRIPT["ads"][ad_key]
    style = SCRIPT["styles"][ad.get("style", "teal")]
    parts, placed = [], []
    clock = 0.0
    for i, seg in enumerate(ad["segments"]):
        name = f"{lang}_{seg['clip']}"
        src = os.path.join(rec_dir, name + ".mp4")
        cw, ch, _ = probe(src)
        cap = SCRIPT["captions"].get(seg.get("caption", ""), {}).get(lang, "")
        hl = SCRIPT["captions"].get(seg.get("caption", ""), {}).get(lang + "_hl")
        png = os.path.join(work, f"{ad_key}_{fmt}_{i}.png")
        caption_overlay(fmt, cap, hl, style, phone_box(fmt)).save(png)
        mp4 = os.path.join(work, f"{lang}_{ad_key}_{fmt}_{i}.mp4")
        render_segment(src, seg, fmt, png, mp4, (cw, ch))
        parts.append(mp4)
        speed = seg.get("speed", 1.0)
        for t, effect, vol in sfx_events(rec_dir, name):
            if seg["t0"] <= t < seg["t0"] + seg["dur"] * speed:
                placed.append((clock + (t - seg["t0"]) / speed, effect, vol))
        clock += seg["dur"]
    end_len = ad.get("end", 3.0)
    end_mp4 = os.path.join(work, f"{lang}_{ad_key}_{fmt}_end.mp4")
    frames_to_video(endcard_frames(fmt, lang, style, int(end_len * FPS)), end_mp4)
    parts.append(end_mp4)
    placed += [(clock + 0.05, "swoosh", 0.9), (clock + 0.3, "win", 0.8)]
    total = clock + end_len
    lst = os.path.join(work, f"{lang}_{ad_key}_{fmt}.txt")
    with open(lst, "w") as f:
        for p in parts:
            f.write(f"file '{p}'\n")
    silent = os.path.join(work, f"{lang}_{ad_key}_{fmt}_v.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst, "-c", "copy", silent])
    wav = os.path.join(work, f"{lang}_{ad_key}_{fmt}.m4a")
    mix_audio(total, placed, ad.get("music", "music_kitchen"), ad.get("music_vol", 0.45), wav)
    tag = {"v": "9x16", "h": "16x9"}[fmt]
    out = os.path.join(out_dir, f"sortelier_{ad_key}_{lang}_{tag}.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", silent, "-i", wav, "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "copy",
         "-shortest", "-movflags", "+faststart", out])
    print(out, f"{total:.1f}s")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("recordings")
    ap.add_argument("out")
    ap.add_argument("--only", default="ru,en")
    ap.add_argument("--ads", default=",".join(SCRIPT["ads"].keys()))
    ap.add_argument("--formats", default="v,h")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="promo_")
    for lang in args.only.split(","):
        for ad in args.ads.split(","):
            for fmt in args.formats.split(","):
                build(args.recordings, args.out, lang, ad, fmt, work)


if __name__ == "__main__":
    main()
