"""Материалы для App Store: тексты по языкам и скриншоты с подписями.

Запуск: python3 tools/appstore/build.py <папка снимков симулятора> [--only en,ru] [--fonts art/fonts]
Снимки берутся из ветки ci-store (workflow "Store screenshots"): <язык>_<экран>.png.
Пишет appstore/metadata/<локаль>/*.txt (формат fastlane deliver) и appstore/screenshots/<локаль>/NN_<экран>.png
размером 1290x2796 (iPhone 6.9"). Подписи - из appstore/source.json (en, ru) и appstore/translations/<код>.json.
"""
import argparse
import json
import math
import os
import random

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
STORE = os.path.join(ROOT, "appstore")
SPRITES = os.path.join(ROOT, "Sortelier", "Resources", "Sprites")
W, H = 1290, 2796

# язык игры -> локали App Store Connect (испанский один на Испанию и Мексику)
LOCALES = {
    "en": ["en-US"], "ru": ["ru"], "es": ["es-ES", "es-MX"], "pt-BR": ["pt-BR"], "de": ["de-DE"], "fr": ["fr-FR"],
    "it": ["it"], "tr": ["tr"], "pl": ["pl"], "id": ["id"], "vi": ["vi"], "th": ["th"], "hi": ["hi"], "ar": ["ar-SA"],
    "ja": ["ja"], "ko": ["ko"], "zh-Hans": ["zh-Hans"], "zh-Hant": ["zh-Hant"],
}
SHOTS = ["recipes", "customers", "kitchens", "events", "twists", "collect"]

# фон кадра: градиент сверху вниз и продукты-украшения вокруг подписи
STYLE = {
    "recipes": (((255, 150, 60), (240, 80, 90)), ["bun", "patty", "lettuce", "dish_burger"]),
    "customers": (((40, 190, 170), (30, 120, 160)), ["dish_taco", "nachos", "lime", "churros"]),
    "kitchens": (((90, 140, 250), (130, 80, 220)), ["dish_sushi", "dish_pizza", "dish_croissant", "dish_taco"]),
    "events": (((140, 70, 200), (250, 120, 40)), ["pumpkin", "candy_corn", "ghost_cookie", "caramel_apple"]),
    "twists": (((70, 90, 210), (40, 170, 230)), ["macaron", "dish_eclair", "strawberry", "chocolate"]),
    "collect": (((255, 190, 50), (245, 120, 50)), ["dish_pancakes", "dish_ramen", "dish_tart", "dish_pasta"]),
}


def font_for(lang, fonts, size):
    nunito = os.path.join(ROOT, "Sortelier", "Resources", "Fonts", "Nunito-Black.ttf")
    table = {
        "th": ("Mitr-Bold.ttf", None), "hi": ("Baloo2[wght].ttf", b"ExtraBold"),
        "ar": ("BalooBhaijaan2[wght].ttf", b"ExtraBold"), "ja": ("MPLUSRounded1c-ExtraBold.ttf", None),
        "ko": ("Jua-Regular.ttf", None), "zh-Hans": ("NotoSansSC[wght].ttf", b"Black"),
        "zh-Hant": ("NotoSansTC[wght].ttf", b"Black"),
    }
    if lang not in table:
        return ImageFont.truetype(nunito, size)
    name, variation = table[lang]
    f = ImageFont.truetype(os.path.join(fonts, name), size)
    if variation:
        try:
            f.set_variation_by_name(variation)
        except Exception:
            pass
    return f


def texts(lang):
    src = json.load(open(os.path.join(STORE, "source.json")))
    if lang in ("en", "ru"):
        out = {k: src[k][lang] for k in ("name", "subtitle", "keywords", "promo", "description", "release_notes")}
        out["captions"] = {k: v[lang] for k, v in src["captions"].items()}
        return out
    return json.load(open(os.path.join(STORE, "translations", lang + ".json")))


def gradient(top, bottom):
    im = Image.new("RGB", (W, H))
    d = ImageDraw.Draw(im)
    for y in range(H):
        t = y / (H - 1)
        d.line([(0, y), (W, y)], fill=tuple(round(a + (b - a) * t) for a, b in zip(top, bottom)))
    return im.convert("RGBA")


def sparkles(im, seed):
    """Мягкие светлые круги на фоне: глубина без лишних деталей."""
    rng = random.Random(seed)
    layer = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    for _ in range(14):
        r = rng.randint(60, 220)
        x, y = rng.randint(-100, W + 100), rng.randint(-100, H + 100)
        d.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255, rng.randint(14, 30)))
    return Image.alpha_composite(im, layer.filter(ImageFilter.GaussianBlur(30)))


def fit_lines(draw, text, lang, fonts, size, max_w, max_lines):
    """Подбирает размер шрифта и переносы, чтобы текст влез по ширине."""
    rtl = lang == "ar"
    while size > 30:
        f = font_for(lang, fonts, size)
        words = text.split(" ")
        lines, cur = [], ""
        for w in words:
            trial = (cur + " " + w).strip()
            if draw.textlength(trial, font=f, direction="rtl" if rtl else None) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
        widest = max(draw.textlength(l, font=f, direction="rtl" if rtl else None) for l in lines)
        if len(lines) <= max_lines and widest <= max_w:
            return f, lines
        size = int(size * 0.92)
    return font_for(lang, fonts, size), [text]


def draw_centered(im, lines, font, y, fill, stroke, stroke_w, lang, gap=1.12):
    d = ImageDraw.Draw(im)
    rtl = lang == "ar"
    for line in lines:
        box = d.textbbox((0, 0), line, font=font, stroke_width=stroke_w, direction="rtl" if rtl else None)
        w, h = box[2] - box[0], box[3] - box[1]
        # тень под текстом
        shadow = Image.new("RGBA", im.size, (0, 0, 0, 0))
        ImageDraw.Draw(shadow).text(((W - w) / 2 - box[0], y - box[1] + 10), line, font=font, fill=(0, 0, 0, 90),
                                    stroke_width=stroke_w, stroke_fill=(0, 0, 0, 90), direction="rtl" if rtl else None)
        im.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(8)))
        d.text(((W - w) / 2 - box[0], y - box[1]), line, font=font, fill=fill, stroke_width=stroke_w, stroke_fill=stroke,
               direction="rtl" if rtl else None)
        y += int(font.size * gap)
    return y


def phone(shot):
    """Снимок в рамке телефона: скругленный экран, темная рамка, мягкая тень."""
    sw = 1010
    sh = round(shot.height * sw / shot.width)
    screen = shot.convert("RGBA").resize((sw, sh), Image.LANCZOS)
    radius = 118
    mask = Image.new("L", (sw, sh), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, sw - 1, sh - 1), radius, fill=255)
    bezel = 26
    fw, fh = sw + 2 * bezel, sh + 2 * bezel
    frame = Image.new("RGBA", (fw + 120, fh + 120), (0, 0, 0, 0))
    shadow = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rounded_rectangle((60, 80, 60 + fw, 80 + fh), radius + bezel, fill=(0, 0, 0, 110))
    frame.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(28)))
    d = ImageDraw.Draw(frame)
    d.rounded_rectangle((60, 60, 60 + fw, 60 + fh), radius + bezel, fill=(28, 28, 34, 255))
    d.rounded_rectangle((63, 63, 57 + fw, 57 + fh), radius + bezel - 3, outline=(90, 90, 100, 255), width=3)
    frame.paste(screen, (60 + bezel, 60 + bezel), mask)
    return frame


def decorations(im, names, seed):
    rng = random.Random(seed)
    # по бокам телефона, слегка заходя на рамку: подпись остается чистой
    spots = [(105, 1250, -12), (W - 105, 2050, 12)]
    for name, (x, y, rot) in zip(names, spots):
        path = os.path.join(SPRITES, name + ".png")
        if not os.path.exists(path):
            continue
        sp = Image.open(path).convert("RGBA")
        size = 250 if name.startswith("dish_") else 210
        sp = sp.resize((size, size), Image.LANCZOS).rotate(rot + rng.uniform(-4, 4), resample=Image.BICUBIC, expand=True)
        sh = Image.new("RGBA", sp.size, (0, 0, 0, 0))
        sh.putalpha(sp.getchannel("A").point(lambda a: a * 0.35))
        im.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)), (int(x - sp.width / 2 + 8), int(y - sp.height / 2 + 14)))
        im.alpha_composite(sp, (int(x - sp.width / 2), int(y - sp.height / 2)))


def compose(lang, key, shot_path, fonts, index):
    (top, bottom), deco = STYLE[key]
    im = sparkles(gradient(top, bottom), index)
    t = texts(lang)["captions"][key]
    d = ImageDraw.Draw(im)
    tf, tl = fit_lines(d, t[0], lang, fonts, 128, W - 220, 2)
    y = draw_centered(im, tl, tf, 150, (255, 255, 255, 255), (60, 30, 20, 255), 9, lang)
    sf, sl = fit_lines(d, t[1], lang, fonts, 66, W - 200, 2)
    y = draw_centered(im, sl, sf, y + 26, (255, 246, 228, 255), (60, 30, 20, 200), 5, lang)
    shot = Image.open(shot_path)
    frame = phone(shot)
    top_y = max(y + 40, 600)
    im.alpha_composite(frame, ((W - frame.width) // 2, top_y - 60))
    decorations(im, deco, index)
    return im.convert("RGB")


def write_metadata(lang):
    t = texts(lang)
    files = {"name.txt": t["name"], "subtitle.txt": t["subtitle"], "keywords.txt": t["keywords"],
             "promotional_text.txt": t["promo"], "description.txt": t["description"], "release_notes.txt": t["release_notes"]}
    limits = {"name.txt": 30, "subtitle.txt": 30, "keywords.txt": 100, "promotional_text.txt": 170}
    for loc in LOCALES[lang]:
        out = os.path.join(STORE, "metadata", loc)
        os.makedirs(out, exist_ok=True)
        for name, text in files.items():
            if name in limits and len(text) > limits[name]:
                print(f"! {loc} {name}: {len(text)} > {limits[name]}")
            with open(os.path.join(out, name), "w") as f:
                f.write(text.strip() + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("shots")
    ap.add_argument("--only", default="")
    ap.add_argument("--fonts", default=os.path.join(ROOT, "art", "fonts"))
    args = ap.parse_args()
    langs = [l for l in args.only.split(",") if l] or list(LOCALES)
    for lang in langs:
        write_metadata(lang)
        for i, key in enumerate(SHOTS):
            src = os.path.join(args.shots, f"{lang}_{key}.png")
            if not os.path.exists(src):
                print("no shot", src)
                continue
            im = compose(lang, key, src, args.fonts, i)
            for loc in LOCALES[lang]:
                out = os.path.join(STORE, "screenshots", loc)
                os.makedirs(out, exist_ok=True)
                im.save(os.path.join(out, f"{i + 1:02d}_{key}.png"), optimize=True)
        print("done", lang, flush=True)


if __name__ == "__main__":
    main()
