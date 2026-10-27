"""Иконка приложения: бургер на теплом градиенте. Запуск: python3 tools/render/icon.py <папка рендеров>"""
import os
import sys

from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OUT = os.path.join(ROOT, "Sortelier", "Resources", "Assets.xcassets", "AppIcon.appiconset", "AppIcon.png")

W = 1024
bg = Image.new("RGB", (W, W))
d = ImageDraw.Draw(bg)
for y in range(W):
    t = y / W
    d.line([(0, y), (W, y)], fill=(int(255 - 20 * t), int(190 - 70 * t), int(80 - 45 * t)))
glow = Image.new("L", (W, W), 0)
ImageDraw.Draw(glow).ellipse((160, 150, 864, 854), fill=190)
glow = glow.filter(ImageFilter.GaussianBlur(100))
bg = Image.composite(Image.new("RGB", (W, W), (255, 236, 185)), bg, glow)
burger = Image.open(os.path.join(sys.argv[1], "dish_burger.png")).convert("RGBA")
alpha = burger.getchannel("A")
burger = ImageEnhance.Color(burger.convert("RGB")).enhance(1.2).convert("RGBA")
burger.putalpha(alpha)
burger = burger.resize((900, 900), Image.LANCZOS)
icon = bg.convert("RGBA")
icon.alpha_composite(burger, (62, 80))
icon.convert("RGB").save(OUT)
print("icon saved")
