"""Готовит спрайты для игры из рендеров Blender.

Запуск: python3 tools/render/pack.py <папка рендеров>
Пишет в Sortelier/Resources/Sprites. Палитру не урезаем: на градиентах это дает полосы.
"""
import glob
import os
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DST = os.path.join(ROOT, "Sortelier", "Resources", "Sprites")
SATURATION = 1.2
# Продукт в кадре: стоит на нижнем крае (поле снизу BOTTOM), заполняет до FILL_W x FILL_H.
# Так все продукты одинаково стоят на полке и одинаково заметны. Сцена ставит тень на 0.06 от низа.
BOTTOM, FILL_W, FILL_H = 0.06, 0.9, 0.84


def stand(im):
    alpha = im.getchannel("A").point(lambda v: 255 if v > 12 else 0)
    box = alpha.getbbox()
    if not box:
        return im
    obj = im.crop(box)
    side = im.width
    k = min(FILL_W * side / obj.width, FILL_H * side / obj.height)
    obj = obj.resize((max(1, round(obj.width * k)), max(1, round(obj.height * k))), Image.LANCZOS)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(obj, ((side - obj.width) // 2, side - round(BOTTOM * side) - obj.height))
    return out


def clean_shadow(im):
    """Тень от ловца тени: убираем слабую дымку по всему кадру, контактную тень оставляем мягче."""
    import numpy as np
    a = np.array(im).astype(np.float32)
    alpha = a[..., 3]
    shadow = (alpha < 250) & (a[..., :3].max(-1) < 40)
    t = np.clip((alpha - 30) / 50, 0, 1)
    fade = t * t * (3 - 2 * t)
    # к краям кадра тень плавно сходит на нет, иначе виден обрез рамки
    h, w = alpha.shape
    yy, xx = np.mgrid[0:h, 0:w]
    edge = np.minimum(np.minimum(xx, w - 1 - xx), np.minimum(yy, h - 1 - yy)) / (0.14 * min(w, h))
    edge = np.clip(edge, 0, 1)
    fade = fade * edge * edge * (3 - 2 * edge)
    alpha[shadow] = alpha[shadow] * fade[shadow] * 0.85
    a[..., 3] = alpha
    return Image.fromarray(a.astype(np.uint8), "RGBA")


def fit(im, size, pad=0.04):
    """Объект по центру кадра с небольшим полем (для иконок)."""
    box = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
    if not box:
        return im
    obj = im.crop(box)
    side = round(im.width * (1 - 2 * pad))
    k = min(side / obj.width, side / obj.height)
    obj = obj.resize((max(1, round(obj.width * k)), max(1, round(obj.height * k))), Image.LANCZOS)
    out = Image.new("RGBA", im.size, (0, 0, 0, 0))
    out.alpha_composite(obj, ((im.width - obj.width) // 2, (im.height - obj.height) // 2))
    return out


def finish(path_in, path_out, size, boost=True, standing=False, shadow=False, centered=False):
    im = Image.open(path_in).convert("RGBA")
    if shadow:
        im = clean_shadow(im)
    if centered:
        im = fit(im, size)
    if standing:
        im = stand(im)
    if boost:
        alpha = im.getchannel("A")
        rgb = ImageEnhance.Color(im.convert("RGB")).enhance(SATURATION)
        im = rgb.convert("RGBA")
        im.putalpha(alpha)
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    im.save(path_out, optimize=True)


def background(path_in, path_out):
    """Фон сцены: легкое размытие (продукты на его фоне остаются резкими), виньетка, JPEG."""
    im = Image.open(path_in).convert("RGB")
    im = im.filter(ImageFilter.GaussianBlur(im.width / 600))
    im = ImageEnhance.Color(im).enhance(1.1)
    w, h = im.size
    mask = Image.new("L", (w // 8, h // 8), 0)
    ImageDraw.Draw(mask).ellipse((-w // 16, -h // 40, w // 8 + w // 16, h // 8 + h // 40), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(w // 40)).resize((w, h), Image.BILINEAR)
    dark = ImageEnhance.Brightness(im).enhance(0.8)
    im = Image.composite(im, dark, mask)
    im.save(path_out, quality=86, optimize=True, progressive=True)


def main():
    src = sys.argv[1]
    os.makedirs(DST, exist_ok=True)
    for f in glob.glob(os.path.join(src, "*.png")):
        name = os.path.basename(f)
        if name.endswith("_preview.png"):
            continue
        if name.startswith("bg_"):
            background(f, os.path.join(DST, name[:-4] + ".jpg"))
        elif name.startswith("counter"):
            w, h = Image.open(f).size
            finish(f, os.path.join(DST, name), (780, round(780 * h / w)), boost=True)
        elif name.startswith("customer_"):
            finish(f, os.path.join(DST, name), (200, 200), boost=False)
        elif name.startswith("shelf"):
            w, h = Image.open(f).size
            finish(f, os.path.join(DST, name), (600, int(600 * h / w)), boost=False)
        elif name.startswith("dish_") or name.startswith("chest_"):
            finish(f, os.path.join(DST, name), (400, 400))
        elif name.startswith("icon_"):
            finish(f, os.path.join(DST, name), (192, 192), centered=True)
        elif name.startswith("m3_"):
            # фишки "Рынка" стоят по центру клетки
            finish(f, os.path.join(DST, name), (288, 288), centered=True)
        elif name == "coin_icon.png":
            finish(f, os.path.join(DST, name), (128, 128), centered=True)
        elif name.startswith("coins_"):
            finish(f, os.path.join(DST, name), (288, 288), standing=True, shadow=True)
        else:
            finish(f, os.path.join(DST, name), (288, 288), standing=True)
    for f in glob.glob(os.path.join(src, "*_spin", "*.png")):
        finish(f, os.path.join(DST, os.path.basename(f)), (288, 288))
    print("sprites:", len(os.listdir(DST)))


if __name__ == "__main__":
    main()
