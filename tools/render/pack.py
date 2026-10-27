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


def finish(path_in, path_out, size, boost=True, standing=False):
    im = Image.open(path_in).convert("RGBA")
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
        elif name.startswith("shelf"):
            w, h = Image.open(f).size
            finish(f, os.path.join(DST, name), (600, int(600 * h / w)), boost=False)
        elif name.startswith("dish_"):
            finish(f, os.path.join(DST, name), (400, 400))
        else:
            finish(f, os.path.join(DST, name), (288, 288), standing=True)
    for f in glob.glob(os.path.join(src, "*_spin", "*.png")):
        finish(f, os.path.join(DST, os.path.basename(f)), (288, 288))
    print("sprites:", len(os.listdir(DST)))


if __name__ == "__main__":
    main()
