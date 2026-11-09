"""Рекламные ролики Sortelier для TikTok, YouTube Shorts и YouTube.

Запуск: python3 tools/promo/compose.py <папка записей> <папка выхода> [--only ru,en] [--ads sort,market,tour] [--formats v,h]
Записи берутся из ветки ci-promo (workflow "Promo videos"): <язык>_<сцена>.mp4, .start (время первого кадра)
и .log (строки "SFX <время> <звук> <громкость>" из отладочной сборки с -uiSfxLog).

Форматы: v - 1080x1920 (TikTok, Reels, Shorts), h - 1920x1080 (обычный YouTube), у темы в script.json поле formats.
Рядом с каждым роликом json с заголовком, подписью и хэштегами, как у роликов Harvest Hollow.
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


CREAM = (255, 246, 228)
BROWN = (74, 44, 26)


def rays(size, style, center=None, seed=3):
    """Фон как у Harvest Hollow: градиент, лучи из центра и мягкие пятна."""
    W, H = size
    im = gradient(size, *style)
    cx, cy = center or (W / 2, H * 0.42)
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    R = max(W, H) * 1.5
    n = 18
    for i in range(n):
        if i % 2:
            continue
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        d.polygon([(cx, cy), (cx + R * math.cos(a0), cy + R * math.sin(a0)), (cx + R * math.cos(a1), cy + R * math.sin(a1))],
                  fill=(255, 255, 255, 30))
    im.alpha_composite(layer)
    return im


def hook_card(im, text, highlight, box, size):
    """Хук на светлой плашке с коричневой рамкой, как в роликах Harvest Hollow."""
    x0, y0, x1, y1 = box
    d = ImageDraw.Draw(im)
    f, lines = wrap(d, text, size, x1 - x0 - 70, 3)
    lh = f.size * 1.16
    hgt = len(lines) * lh + 56
    cy = (y0 + y1) / 2
    top = cy - hgt / 2
    sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0 + 6, top + 14, x1 + 6, top + hgt + 14), 34, fill=(0, 0, 0, 90))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(12)))
    d.rounded_rectangle((x0, top, x1, top + hgt), 34, fill=CREAM, outline=BROWN, width=7)
    y = top + 28
    for line in lines:
        w = d.textlength(line, font=f)
        x = (x0 + x1) / 2 - w / 2
        if highlight and highlight in line:
            before, _, after = line.partition(highlight)
            for part, color in ((before, BROWN), (highlight, (226, 92, 30)), (after, BROWN)):
                if part:
                    d.text((x, y), part, font=f, fill=color)
                    x += d.textlength(part, font=f)
        else:
            d.text((x, y), line, font=f, fill=BROWN)
        y += lh


def game_box(fmt):
    """Где стоит запись игры: v - под плашкой хука, h - слева."""
    W, H = SIZES[fmt]
    if fmt == "v":
        x0, y0 = 110, 380
        w = W - 2 * x0
        return (x0, y0, x0 + w, H - 60)
    h = H - 110
    w = round(h * 0.56)
    return (300, 55, 300 + w, 55 + h)


def caption_overlay(fmt, hook, highlight, style):
    """Слой поверх видео: фон с лучами, рамка игры (окно прозрачное) и хук."""
    W, H = SIZES[fmt]
    x0, y0, x1, y1 = game_box(fmt)
    im = rays((W, H), style, center=((x0 + x1) / 2, (y0 + y1) / 2))
    b = 12
    sh = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle((x0 - b + 8, y0 - b + 20, x1 + b + 8, y1 + b + 20), 56, fill=(0, 0, 0, 110))
    im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((x0 - b, y0 - b, x1 + b, y1 + b), 56, fill=BROWN)
    d.rounded_rectangle((x0 - b + 4, y0 - b + 4, x1 + b - 4, y1 + b - 4), 52, outline=(140, 96, 60), width=3)
    hole = Image.new("L", (W, H), 255)
    ImageDraw.Draw(hole).rounded_rectangle((x0, y0, x1, y1), 44, fill=0)
    im.putalpha(Image.fromarray(np.minimum(np.array(im.getchannel("A")), np.array(hole))))
    if hook:
        if fmt == "v":
            hook_card(im, hook, highlight, (50, 40, W - 50, 330), 74)
        else:
            hook_card(im, hook, highlight, (x1 + 110, 200, W - 110, 880), 84)
    return im


def endcard_frames(fmt, lang, style, n):
    """Концовка: иконка выпрыгивает, название, кнопка "Играй бесплатно на iPhone" пульсирует, "Ссылка в профиле"."""
    W, H = SIZES[fmt]
    t = SCRIPT["texts"][lang]
    if fmt == "v":
        icon_size, icon_c, title_y, btn_y, deco_y = 440, (W / 2, 560), 860, 1270, (300, 1560)
    else:
        icon_size, icon_c, title_y, btn_y, deco_y = 330, (W / 2, 250), 450, 790, (190, 880)
    base = rays((W, H), style, center=icon_c)
    icon = rounded(Image.open(ICON).convert("RGBA").resize((icon_size, icon_size), Image.LANCZOS), icon_size // 4.5)
    static = base.copy()
    deco = ["dish_burger", "dish_sushi", "dish_pizza", "dish_taco"]
    spots = [(W * 0.14, deco_y[0], -14), (W * 0.86, deco_y[0] + 80, 12), (W * 0.14, deco_y[1], 10), (W * 0.86, deco_y[1] + 60, -10)]
    for name, (x, y, r) in zip(deco, spots):
        paste_sprite(static, name, x, y, 220, r)
    text_block(static, t["name"], W / 2, title_y, 170, W - 140, fill=(255, 214, 64), stroke=BROWN, max_lines=1)
    frames = []
    for i in range(n):
        im = static.copy()
        k = min(1, i / 9)
        s = (1 + 0.22 * math.sin(k * math.pi) if k < 1 else 1) * (0.4 + 0.6 * k)
        ic = icon.resize((int(icon_size * s), int(icon_size * s)), Image.LANCZOS)
        sh = Image.new("RGBA", im.size, (0, 0, 0, 0))
        sh.paste((0, 0, 0, 100), (int(icon_c[0] - ic.width / 2 + 8), int(icon_c[1] - ic.height / 2 + 16)), ic.getchannel("A"))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(14)))
        im.alpha_composite(ic, (int(icon_c[0] - ic.width / 2), int(icon_c[1] - ic.height / 2)))
        pulse = 1 + 0.04 * math.sin(i / FPS * 2 * math.pi * 1.3)
        d = ImageDraw.Draw(im)
        f = font(int(62 * pulse))
        label = t["cta"]
        bw = int(d.textlength(label, font=f) + 120 * pulse)
        bh = int(140 * pulse)
        bx, by = int(W / 2 - bw / 2), int(btn_y - bh / 2)
        d.rounded_rectangle((bx, by + 12, bx + bw, by + bh + 12), bh // 2, fill=(40, 120, 30))
        d.rounded_rectangle((bx, by, bx + bw, by + bh), bh // 2, fill=(96, 200, 64), outline=(40, 120, 30), width=5)
        d.rounded_rectangle((bx + 18, by + 10, bx + bw - 18, by + bh * 0.42), bh // 4, fill=(140, 225, 100))
        lw = d.textlength(label, font=f)
        d.text((W / 2 - lw / 2, by + bh / 2 - f.size * 0.6), label, font=f, fill=(255, 255, 255), stroke_width=4,
               stroke_fill=(40, 110, 30))
        f2 = font(58)
        link = t["link"]
        lw2 = d.textlength(link, font=f2)
        d.text((W / 2 - lw2 / 2, by + bh + 50), link, font=f2, fill=(255, 255, 255), stroke_width=5, stroke_fill=BROWN)
        frames.append(im.convert("RGB"))
    return frames


# ---------- Видео ----------

def render_segment(src, seg, fmt, overlay_png, out, clip_size):
    """Кусок записи в окне рамки: по ширине окна, по высоте окно начинается с доли "y" от верха записи."""
    W, H = SIZES[fmt]
    t0, dur, speed = seg["t0"], seg["dur"], seg.get("speed", 1.0)
    cw, ch = clip_size
    x0, y0, x1, y1 = game_box(fmt)
    gw, gh = x1 - x0, y1 - y0
    sh = int(ch * gw / cw) // 2 * 2
    y = max(0, min(int(sh * seg.get("y", 0.05)), sh - gh))
    vf = (f"color=c=black:s={W}x{H}:r={FPS}:d={dur}[bg];"
          f"[0:v]trim=start={t0}:duration={dur * speed},setpts=(PTS-STARTPTS)/{speed},fps={FPS},"
          f"scale={gw}:{sh}:flags=lanczos,crop={gw}:{gh}:0:{y}[g];[bg][g]overlay={x0}:{y0}[b];"
          f"[b][1:v]overlay=0:0,format=yuv420p[o]")
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
    work = os.path.join(work, f"{lang}_{ad_key}_{fmt}")
    os.makedirs(work, exist_ok=True)
    parts, placed = [], []
    clock = 0.0
    for i, seg in enumerate(ad["segments"]):
        name = f"{lang}_{seg['clip']}"
        src = os.path.join(rec_dir, name + ".mp4")
        cw, ch, _ = probe(src)
        png = os.path.join(work, f"{lang}_{ad_key}_{fmt}.png")
        if not os.path.exists(png):
            hook = ad["hook"][lang]
            caption_overlay(fmt, hook, ad["hook"].get(lang + "_hl"), style).save(png)
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
    # имена как у роликов Harvest Hollow: <тема>_<язык>.mp4 и рядом json для публикации
    stem = f"{ad_key}_{lang}" + ("" if fmt == "v" else "_16x9")
    out = os.path.join(out_dir, stem + ".mp4")
    tags = SCRIPT["hashtags"][lang]
    title = ad["title"][lang]
    meta = {"id": ad_key, "lang": lang, "file": stem + ".mp4", "title": title,
            "caption": f"{title}. {SCRIPT['texts'][lang]['free']} " + " ".join(tags), "hashtags": tags}
    with open(os.path.join(out_dir, stem + ".json"), "w") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
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
    ap.add_argument("--formats", default="")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    work = tempfile.mkdtemp(prefix="promo_")
    for lang in args.only.split(","):
        for ad in args.ads.split(","):
            fmts = args.formats.split(",") if args.formats else SCRIPT["ads"][ad].get("formats", ["v"])
            for fmt in fmts:
                build(args.recordings, args.out, lang, ad, fmt, work)


if __name__ == "__main__":
    main()
