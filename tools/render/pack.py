"""Готовит спрайты для игры из рендеров Blender.

Запуск: python3 tools/render/pack.py <папка рендеров>
Пишет в Sortelier/Resources/Sprites. Палитру не урезаем: на градиентах это дает полосы.
"""
import glob
import os
import sys

from PIL import Image, ImageEnhance

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DST = os.path.join(ROOT, "Sortelier", "Resources", "Sprites")
SATURATION = 1.2


def finish(path_in, path_out, size, boost=True):
    im = Image.open(path_in).convert("RGBA")
    if boost:
        alpha = im.getchannel("A")
        rgb = ImageEnhance.Color(im.convert("RGB")).enhance(SATURATION)
        im = rgb.convert("RGBA")
        im.putalpha(alpha)
    if im.size != size:
        im = im.resize(size, Image.LANCZOS)
    im.save(path_out, optimize=True)


def main():
    src = sys.argv[1]
    os.makedirs(DST, exist_ok=True)
    for f in glob.glob(os.path.join(src, "*.png")):
        name = os.path.basename(f)
        if name.startswith("shelf"):
            w, h = Image.open(f).size
            finish(f, os.path.join(DST, name), (600, int(600 * h / w)), boost=False)
        elif name.startswith("dish_"):
            finish(f, os.path.join(DST, name), (400, 400))
        else:
            finish(f, os.path.join(DST, name), (288, 288))
    for f in glob.glob(os.path.join(src, "*_spin", "*.png")):
        finish(f, os.path.join(DST, os.path.basename(f)), (288, 288))
    print("sprites:", len(os.listdir(DST)))


if __name__ == "__main__":
    main()
