"""Лист для проверки рендеров: картинки сеткой на кремовом фоне с подписями.

Запуск: python3 tools/render/sheet.py <вывод.png> <png или папка> [...] [--cell 180] [--cols 6]
Картинки подгоняются под ячейку как в игре: продукт стоит на нижнем крае.
"""
import argparse
import glob
import os

from PIL import Image, ImageDraw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--cell", type=int, default=180)
    ap.add_argument("--cols", type=int, default=6)
    args = ap.parse_args()
    files = []
    for p in args.paths:
        if os.path.isdir(p):
            files += sorted(glob.glob(os.path.join(p, "*.png")))
        else:
            files.append(p)
    files = [f for f in files if "_spin_" not in os.path.basename(f) or f.endswith("_00.png")]
    c, cols = args.cell, args.cols
    rows = max(1, (len(files) + cols - 1) // cols)
    out = Image.new("RGB", (cols * c, rows * (c + 18)), (245, 232, 210))
    d = ImageDraw.Draw(out)
    for i, f in enumerate(files):
        im = Image.open(f).convert("RGBA")
        box = im.getchannel("A").point(lambda v: 255 if v > 12 else 0).getbbox()
        if box:
            im = im.crop(box)
        im.thumbnail((c - 16, c - 16), Image.LANCZOS)
        x = (i % cols) * c + (c - im.width) // 2
        y = (i // cols) * (c + 18) + (c - 8 - im.height)
        out.paste(im, (x, y), im)
        name = os.path.splitext(os.path.basename(f))[0]
        d.text(((i % cols) * c + 6, (i // cols) * (c + 18) + c), name[:26], fill=(90, 60, 40))
    out.save(args.out)
    print(args.out, len(files))


if __name__ == "__main__":
    main()
