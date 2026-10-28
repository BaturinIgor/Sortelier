"""Покупатели Sortelier: аватары по пояс в стиле продуктов, 4 настроения.

Запуск: python customers.py <папка вывода> [--only 0,3] [--size 256]
Выход: customer_<n>_<mood>.png, mood: happy, wait, upset, joy.
"""
import argparse
import math
import os
import sys

import bpy
from mathutils import Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models as M  # noqa: E402
import render as R  # noqa: E402

MOODS = ("happy", "wait", "upset", "joy")

SKIN = {
    "light": (1.0, 0.86, 0.75),
    "fair": (0.98, 0.79, 0.66),
    "olive": (0.92, 0.73, 0.55),
    "tan": (0.86, 0.63, 0.45),
    "brown": (0.68, 0.46, 0.31),
    "dark": (0.48, 0.32, 0.22),
}

# кожа, прическа, цвет волос, одежда, аксессуар
CUSTOMERS = [
    ("fair", "short", (0.36, 0.22, 0.12), (0.26, 0.56, 0.95), None),
    ("light", "bob", (0.95, 0.72, 0.30), (0.95, 0.40, 0.52), None),
    ("brown", "curly", (0.16, 0.10, 0.07), (1.0, 0.78, 0.20), None),
    ("tan", "bun", (0.20, 0.12, 0.08), (0.36, 0.78, 0.52), "glasses"),
    ("olive", "cap", (0.30, 0.18, 0.10), (0.95, 0.35, 0.25), None),
    ("dark", "short", (0.10, 0.07, 0.05), (0.62, 0.42, 0.92), "glasses"),
    ("fair", "beanie", (0.62, 0.30, 0.12), (0.20, 0.70, 0.78), None),
    ("light", "pony", (0.72, 0.36, 0.14), (1.0, 0.62, 0.22), None),
    ("tan", "bangs", (0.12, 0.08, 0.06), (0.92, 0.28, 0.42), None),
    ("brown", "bald", (0.10, 0.07, 0.05), (0.32, 0.46, 0.72), "moustache"),
    # гурман: цилиндр, монокль, усы, бабочка, фрак
    ("fair", "tophat", (0.82, 0.80, 0.78), (0.10, 0.10, 0.13), "gourmet"),
]

HEAD_Z = 1.25


def head_surface_y(x, dz, r=1.0):
    """Где передняя поверхность головы (y < 0) для точки (x, dz)."""
    return -math.sqrt(max(0.0, r * r - x * x - dz * dz))


def at_face(ob, x, dz, inset=0.0):
    y = head_surface_y(x, dz) * 0.97 + inset
    ob.location = (x, y, HEAD_Z + dz)
    return ob


def ellipsoid(name, scale, mat, segs=32, rings=20):
    ob = M.sphere(name, 1.0, segs, rings)
    ob.scale = scale
    M.apply_transform(ob)
    M.smooth(ob)
    M.assign(ob, mat)
    return ob


def arc_tube(name, cx, cz, width, bend, radius, mat, y_off=-0.02, n=16):
    """Дуга рта или брови на лице: bend > 0 - улыбка (концы вверх)."""
    pts = []
    for i in range(n):
        t = -1 + 2 * i / (n - 1)
        x = cx + t * width / 2
        z = cz + bend * t * t
        y = head_surface_y(x, z - HEAD_Z) * 0.985 + y_off
        pts.append((x, y, z))
    ob = M.tube(name, pts, radius, taper=(0.7, 0.7))
    # концы чуть тоньше середины
    M.smooth(ob)
    M.assign(ob, mat)
    return ob


def hair_shell(name, mat, low=-0.32, front_cut=0.32, r=1.07):
    ob = M.sphere(name, r, 64, 40)
    ob.location = (0, 0, HEAD_Z)
    M.apply_transform(ob)
    M.bisect(ob, (0, 0, HEAD_Z + low), (0, 0, -1), fill=False)
    # лицо открыто: срезаем передне-нижнюю часть наклонной плоскостью
    M.bisect(ob, (0, -0.55, HEAD_Z + front_cut), (0, -0.62, -0.78), fill=False)
    M.solidify(ob, 0.06, 1.0)
    M.subdivide(ob, 1)
    M.push_normals(ob, lambda co, n: 0.012 * M.fbm(co * 4))
    M.smooth(ob)
    M.assign(ob, mat)
    return ob


def build(spec, mood):
    skin_key, style, hair_col, shirt_col, acc = spec
    skin = SKIN[skin_key]
    darker = tuple(c * 0.86 for c in skin)
    skin_mat = M.material("Skin", [(0.0, darker), (0.6, skin), (1.0, tuple(min(1, c * 1.04) for c in skin))],
                          coord="z", lo=0.3, hi=2.2, rough=0.42, sss=0.35, sss_radius=(1, 0.55, 0.4), coat=0.15)
    hair_mat = M.material("Hair", [(0.0, tuple(c * 0.7 for c in hair_col)), (1.0, tuple(min(1, c * 1.25) for c in hair_col))],
                          coord="z", lo=HEAD_Z - 0.6, hi=HEAD_Z + 1.1, rough=0.3, coat=0.5, coat_rough=0.12,
                          bump=0.05, bump_scale=18)
    shirt_mat = M.material("Shirt", [(0.0, tuple(c * 0.75 for c in shirt_col)), (1.0, shirt_col)], coord="z",
                           lo=-0.6, hi=0.6, rough=0.45, coat=0.2, sheen=0.3)
    dark = M.flat("Eye", (0.12, 0.08, 0.07), rough=0.15, coat=0.8)
    white = M.flat("White", (1.0, 1.0, 1.0), rough=0.1)
    brow_mat = M.flat("Brow", tuple(c * 0.75 for c in hair_col) if style != "bald" else (0.16, 0.1, 0.07), rough=0.4)
    lip = M.flat("Mouth", (0.52, 0.16, 0.14), rough=0.35, coat=0.3)
    blush = M.flat("Blush", (1.0, 0.52, 0.56), rough=0.5, sss=0.3)
    parts = []

    head = M.sphere("Head", 1.0, 64, 48)
    M.deform(head, lambda co: Vector((co.x * 1.0, co.y * 0.96, co.z * 0.98)))
    head.location = (0, 0, HEAD_Z)
    M.apply_transform(head)
    M.smooth(head)
    M.assign(head, skin_mat)
    parts.append(head)
    for side in (-1, 1):
        ear = ellipsoid(f"Ear{side}", (0.09, 0.14, 0.2), skin_mat)
        ear.location = (side * 0.97, 0.05, HEAD_Z - 0.02)
        parts.append(ear)
    neck = M.cylinder("Neck", 0.32, 0.5, 32)
    neck.location = (0, 0.05, 0.5)
    M.smooth(neck)
    M.assign(neck, skin_mat)
    parts.append(neck)
    body = M.sphere("Body", 1.0, 64, 40)
    M.deform(body, lambda co: Vector((co.x * 1.38, co.y * 0.82, co.z * 0.78)))
    body.location = (0, 0.1, -0.2)
    M.apply_transform(body)
    M.smooth(body)
    M.assign(body, shirt_mat)
    parts.append(body)
    collar = M.torus("Collar", 0.36, 0.07, 48, 16)
    collar.location = (0, 0.05, 0.52)
    M.smooth(collar)
    M.assign(collar, M.flat("CollarMat", tuple(min(1, c * 1.15) for c in shirt_col), rough=0.45))
    parts.append(collar)

    # глаза
    eye_dz = 0.02
    for side in (-1, 1):
        x = side * 0.34
        if mood == "joy":
            # зажмуренные от радости глаза: дуга концами вниз
            parts.append(arc_tube(f"JoyEye{side}", x, HEAD_Z + eye_dz + 0.03, 0.22, -0.07, 0.03, dark, y_off=-0.01))
        else:
            eye = ellipsoid(f"Eye{side}", (0.105, 0.06, 0.145), dark)
            at_face(eye, x, eye_dz, 0.02)
            parts.append(eye)
            hl = ellipsoid(f"Highlight{side}", (0.035, 0.02, 0.04), white, 16, 10)
            hl.location = (x + 0.035, head_surface_y(x + 0.035, eye_dz + 0.06) * 0.97 - 0.05, HEAD_Z + eye_dz + 0.06)
            parts.append(hl)
        # брови
        tilt = {"happy": 0.0, "joy": 0.0, "wait": 0.06, "upset": -0.07}[mood]
        bz = HEAD_Z + 0.27
        pts = []
        for i in range(10):
            t = i / 9
            xx = x - side * 0.11 + side * 0.22 * t
            zz = bz + 0.03 * math.sin(math.pi * t) + tilt * (1 - t) * (1 if side else 1)
            pts.append((xx, head_surface_y(xx, zz - HEAD_Z) * 0.99 - 0.015, zz))
        brow = M.tube(f"Brow{side}", pts, 0.028, taper=(1.0, 0.75))
        M.smooth(brow)
        M.assign(brow, brow_mat)
        parts.append(brow)
        cheek = ellipsoid(f"Cheek{side}", (0.13, 0.03, 0.08), blush, 24, 12)
        at_face(cheek, side * 0.56, -0.2, 0.025)
        parts.append(cheek)
    nose = ellipsoid("Nose", (0.075, 0.06, 0.065), skin_mat, 24, 16)
    at_face(nose, 0.0, -0.12, -0.03)
    parts.append(nose)

    # рот
    mz = HEAD_Z - 0.36
    if mood == "happy":
        parts.append(arc_tube("Mouth", 0.0, mz, 0.34, 0.07, 0.03, lip))
    elif mood == "wait":
        parts.append(arc_tube("Mouth", 0.0, mz, 0.2, 0.0, 0.026, lip))
    elif mood == "upset":
        parts.append(arc_tube("Mouth", 0.0, mz - 0.03, 0.28, -0.06, 0.03, lip))
    else:
        open_mouth = M.sphere("Mouth", 1.0, 32, 20)
        M.deform(open_mouth, lambda co: Vector((co.x * 0.2, co.y * 0.06, min(co.z, 0.25) * 0.16)))
        at_face(open_mouth, 0.0, -0.36, 0.02)
        M.smooth(open_mouth)
        M.assign(open_mouth, lip)
        parts.append(open_mouth)
        tongue = ellipsoid("Tongue", (0.1, 0.04, 0.05), M.flat("TongueMat", (1.0, 0.45, 0.45), rough=0.4), 24, 12)
        at_face(tongue, 0.0, -0.43, -0.0)
        parts.append(tongue)

    # прическа и аксессуары
    if style in ("short", "bun", "pony", "bangs"):
        parts.append(hair_shell("Hair", hair_mat, low=-0.3, front_cut=0.32))
    if style == "bob":
        parts.append(hair_shell("Hair", hair_mat, low=-0.75, front_cut=0.3, r=1.1))
    if style in ("short", "bob", "pony"):
        for i, (x, dz, rot) in enumerate(((-0.46, 0.42, 35), (-0.16, 0.47, 22), (0.16, 0.46, 12), (0.44, 0.41, -20))):
            f = ellipsoid(f"Fringe{i}", (0.24, 0.1, 0.15), hair_mat)
            f.rotation_euler = (0, math.radians(rot), 0)
            at_face(f, x, dz, -0.06)
            parts.append(f)
    if style == "bun":
        b = ellipsoid("Bun", (0.36, 0.36, 0.34), hair_mat)
        b.location = (0, 0.25, HEAD_Z + 1.05)
        parts.append(b)
    if style == "pony":
        for side in (-1, 1):
            pt = M.capsule(f"Pony{side}", 0.7, 0.17, 32, 24)
            pt.rotation_euler = (0, math.radians(90 + side * 18), 0)
            pt.location = (side * 0.98, 0.25, HEAD_Z - 0.15)
            M.smooth(pt)
            M.assign(pt, hair_mat)
            parts.append(pt)
    if style == "bangs":
        for i, x in enumerate((-0.45, -0.15, 0.15, 0.45)):
            f = ellipsoid(f"Bang{i}", (0.2, 0.1, 0.16), hair_mat)
            at_face(f, x, 0.62 - 0.05 * abs(x), -0.02)
            parts.append(f)
    if style == "curly":
        base = hair_shell("Hair", hair_mat, low=-0.2, front_cut=0.36, r=1.08)
        parts.append(base)

        def make(i, rnd):
            c = M.sphere(f"Curl{i}", 1.0, 20, 12)
            c.scale = (0.24, 0.24, 0.24)
            M.assign(M.smooth(c), hair_mat)
            return c
        M.scatter_on(base, 34, make, seed=11, area=1.05, zmin=HEAD_Z + 0.1, spacing=0.2)
    if style == "cap":
        parts.append(hair_shell("Hair", hair_mat, low=-0.3, front_cut=0.25))
        cap_mat = M.material("CapMat", [(0.0, tuple(c * 0.7 for c in shirt_col)), (1.0, shirt_col)], coord="z",
                             lo=HEAD_Z, hi=HEAD_Z + 1.1, rough=0.4, coat=0.3)
        crown = M.sphere("Crown", 1.17, 64, 32)
        crown.location = (0, 0.02, HEAD_Z + 0.02)
        M.apply_transform(crown)
        M.bisect(crown, (0, 0, HEAD_Z + 0.28), (0, 0, -1))
        M.smooth(crown)
        M.assign(crown, cap_mat)
        brim = M.sphere("Brim", 1.0, 48, 16)
        # козырек наклонен вниз, чтобы его было видно спереди
        M.deform(brim, lambda co: Vector((co.x * 0.78, co.y * 0.5 - 0.92, co.z * 0.05 + HEAD_Z + 0.36 + 0.35 * (co.y * 0.5))))
        M.smooth(brim)
        M.assign(brim, cap_mat)
        parts += [crown, brim]
    if style == "beanie":
        parts.append(hair_shell("Hair", hair_mat, low=-0.3, front_cut=0.2))
        knit = M.material("Knit", [(0.0, tuple(c * 0.75 for c in shirt_col)), (1.0, shirt_col)], coord="z",
                          lo=HEAD_Z, hi=HEAD_Z + 1.3, rough=0.6, bump=0.25, bump_scale=24)
        crown = M.sphere("Beanie", 1.19, 64, 32)
        crown.location = (0, 0.02, HEAD_Z + 0.06)
        M.apply_transform(crown)
        M.bisect(crown, (0, 0, HEAD_Z + 0.38), (0, 0, -1))
        M.smooth(crown)
        M.assign(crown, knit)
        cuff = M.torus("Cuff", 1.1, 0.13, 64, 16)
        cuff.location = (0, 0.02, HEAD_Z + 0.42)
        M.smooth(cuff)
        M.assign(cuff, knit)
        pom = ellipsoid("Pom", (0.22, 0.22, 0.22), M.flat("PomMat", (1.0, 0.98, 0.95), rough=0.7))
        pom.location = (0, 0.02, HEAD_Z + 1.2)
        parts += [crown, cuff, pom]
    if style == "tophat":
        parts.append(hair_shell("Hair", hair_mat, low=-0.3, front_cut=0.2))
        felt = M.material("Felt", [(0.0, (0.05, 0.05, 0.07)), (1.0, (0.16, 0.16, 0.20))], coord="z",
                          lo=HEAD_Z + 0.5, hi=HEAD_Z + 1.9, rough=0.35, coat=0.5, coat_rough=0.2, sheen=0.4)
        brim = M.cylinder("HatBrim", 1.25, 0.06, 64)
        brim.location = (0, 0.04, HEAD_Z + 0.62)
        brim.rotation_euler = (math.radians(-8), 0, 0)
        M.apply_transform(brim)
        M.bevel(brim, 0.03, 3, 30)
        M.smooth(brim, 40)
        M.assign(brim, felt)
        crown = M.cylinder("HatCrown", 0.78, 0.95, 64)
        crown.location = (0, 0.1, HEAD_Z + 1.12)
        crown.rotation_euler = (math.radians(-8), 0, 0)
        M.apply_transform(crown)
        M.bevel(crown, 0.06, 4, 30)
        M.smooth(crown, 40)
        M.assign(crown, felt)
        band = M.cylinder("HatBand", 0.815, 0.17, 64)
        band.location = (0, 0.085, HEAD_Z + 0.8)
        band.rotation_euler = (math.radians(-8), 0, 0)
        M.apply_transform(band)
        M.smooth(band, 40)
        M.assign(band, M.flat("BandMat", (0.80, 0.10, 0.12), rough=0.4, sheen=0.4))
        parts += [brim, crown, band]
    if acc == "gourmet":
        gold = M.material("Monocle", [(0.0, (0.80, 0.55, 0.12)), (1.0, (1.0, 0.85, 0.40))], coord="z",
                          lo=HEAD_Z - 0.2, hi=HEAD_Z + 0.3, rough=0.2, metal=1.0)
        ring = M.torus("MonocleRing", 0.19, 0.03, 48, 12)
        ring.rotation_euler = (math.radians(90), 0, 0)
        at_face(ring, 0.34, 0.02, -0.08)
        M.smooth(ring)
        M.assign(ring, gold)
        chain = M.tube("MonocleChain", [(0.5, -0.82, HEAD_Z - 0.05), (0.62, -0.7, HEAD_Z - 0.45), (0.6, -0.62, HEAD_Z - 0.8)],
                       0.012)
        M.assign(M.smooth(chain), gold)
        mus = arc_tube("Moustache", 0.0, HEAD_Z - 0.25, 0.5, 0.09, 0.06, hair_mat, y_off=-0.05)
        bow_mat = M.flat("BowMat", (0.80, 0.10, 0.12), rough=0.35, sheen=0.4)
        bow = []
        for side in (-1, 1):
            w = M.sphere(f"Bow{side}", 1.0, 32, 16)
            M.deform(w, lambda co, side=side: Vector((co.x * 0.2 * (1 + 0.5 * side * co.x), co.y * 0.08, co.z * 0.13 * (1 + 0.6 * side * co.x))))
            w.location = (side * 0.17, -0.77, 0.24)
            M.apply_transform(w)
            M.assign(M.smooth(w), bow_mat)
            bow.append(w)
        knot = ellipsoid("BowKnot", (0.07, 0.07, 0.08), bow_mat)
        knot.location = (0, -0.82, 0.24)
        shirt_front = M.sphere("ShirtFront", 1.0, 32, 20)
        M.deform(shirt_front, lambda co: Vector((co.x * 0.4, co.y * 0.1, co.z * 0.5)))
        shirt_front.location = (0, -0.6, -0.1)
        M.apply_transform(shirt_front)
        M.assign(M.smooth(shirt_front), M.flat("ShirtWhite", (0.97, 0.97, 0.97), rough=0.5))
        parts += [ring, chain, mus, knot, shirt_front] + bow
    if acc == "glasses":
        frame = M.flat("Frame", (0.15, 0.12, 0.12), rough=0.25, coat=0.6)
        for side in (-1, 1):
            ring = M.torus(f"Lens{side}", 0.17, 0.025, 48, 12)
            ring.rotation_euler = (math.radians(90), 0, 0)
            at_face(ring, side * 0.34, 0.02, -0.07)
            M.smooth(ring)
            M.assign(ring, frame)
            parts.append(ring)
        bridge = M.capsule("Bridge", 0.2, 0.02, 16, 8)
        at_face(bridge, 0.0, 0.06, -0.09)
        M.smooth(bridge)
        M.assign(bridge, frame)
        parts.append(bridge)
    if acc == "moustache":
        mus = arc_tube("Moustache", 0.0, HEAD_Z - 0.25, 0.42, -0.05, 0.065, hair_mat, y_off=-0.05)
        parts.append(mus)
    return parts


def render(index, mood, out_dir, size=256, samples=64):
    scene = M.reset_scene(samples)
    build(CUSTOMERS[index], mood)
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi, pts = R.bounds(meshes)
    # кадр: голова целиком и плечи, низ туловища обрезан
    frame = [p for p in pts if p.z > -0.25] + [Vector((-1.25, 0, -0.25)), Vector((1.25, 0, -0.25))]
    center = Vector((0, 0, (max(p.z for p in frame) + min(p.z for p in frame)) / 2))
    R.add_camera(scene, center, frame, azimuth=math.radians(8), elevation=math.radians(6), margin=1.04)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.filepath = os.path.join(out_dir, f"customer_{index}_{mood}.png")
    bpy.ops.render.render(write_still=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--moods", default=",".join(MOODS))
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    ids = [int(x) for x in args.only.split(",") if x] or list(range(len(CUSTOMERS)))
    for i in ids:
        for mood in args.moods.split(","):
            render(i, mood, args.out, args.size, args.samples)
            print("rendered", i, mood, flush=True)


if __name__ == "__main__":
    main()
