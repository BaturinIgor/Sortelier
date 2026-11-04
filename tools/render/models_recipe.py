"""Большой рецепт: гигантские блюда недели (основа без начинки) и начинки, которые ложатся на них.

Камера здесь смотрит почти сверху (62 градуса), чтобы начинки, разложенные по верху блюда в игре,
легли на него естественно. Запуск:
  /home/claude/venv-blender/bin/python tools/render/models_recipe.py art/new/recipe --size 300 --samples 40
"""
import math
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models as M  # noqa: E402
from models import *  # noqa: F401,F403,E402  помощники
from mathutils import Vector  # noqa: E402

sys.modules.setdefault("models", M)
import models_mexico as MX  # noqa: E402

TOP_ELEVATION = math.radians(62)


# MARK: - Основы блюд

def round_board(name="RBoard", r=1.32, h=0.14):
    wood = material(f"{name}Wood", [(0.0, (0.66, 0.42, 0.20)), (0.5, (0.84, 0.60, 0.34)), (1.0, (0.72, 0.48, 0.26))],
                    coord="x", lo=-1.4, hi=1.4, rough=0.5, coat=0.25, bump=0.12, bump_scale=5, vary=0.15, vary_scale=4)
    disc = rounded_disc(name, r, h, 6.0, 28)
    deform(disc, lambda co: Vector((co.x, co.y, co.z - h)))
    smooth(disc)
    assign(disc, wood)
    handle = capsule(f"{name}Handle", 0.5, 0.16, 32, 24)
    handle.scale = (1.0, 1.0, 0.45)
    handle.location = (r + 0.22, 0, -h / 2)
    apply_transform(handle)
    assign(smooth(handle), wood)
    return [disc, handle]


def recipe_pizza():
    parts = round_board()
    crust = torus("RPCrust", 1.08, 0.15, 160, 24)
    deform(crust, lambda co: Vector((co.x, co.y, co.z * 0.8 + 0.12 + 0.015 * math.sin(math.atan2(co.y, co.x) * 11))))
    push_normals(crust, lambda co, n: 0.02 * fbm(co * 5))
    smooth(crust)
    crust_mat = material("RPCrustMat", [(0.0, (0.80, 0.46, 0.16)), (0.6, (0.95, 0.70, 0.34)), (1.0, (0.72, 0.38, 0.13))],
                         coord="z", lo=0.0, hi=0.27, rough=0.45, sss=0.2, coat=0.3, vary=0.2, vary_scale=6)
    add_speckles(crust_mat, (0.45, 0.22, 0.08), scale=22, threshold=0.66, strength=0.7)
    assign(crust, crust_mat)
    base = cylinder("RPBase", 1.08, 0.1, 128)
    base.location = (0, 0, 0.05)
    apply_transform(base)
    assign(smooth(base, 50), crust_mat)
    sauce = cylinder("RPSauce", 0.98, 0.03, 128)
    sauce.location = (0, 0, 0.115)
    apply_transform(sauce)
    assign(smooth(sauce, 50), M.tomato_sauce_mat("RPSauceMat"))
    # расплавленный сыр: сплошной неровный слой с проплешинами соуса по краю
    melt = polar_disc("RPMelt", 40, 200, 0.9, 0.9)

    def melt_shape(co):
        a = math.atan2(co.y, co.x)
        r = math.hypot(co.x, co.y)
        edge = 0.86 + 0.06 * math.sin(a * 7) + 0.04 * math.sin(a * 13 + 1)
        k = min(1.0, edge / 0.9)
        return Vector((co.x * k, co.y * k, 0.14 + 0.02 * fbm(co * 4) + 0.012 * (1 - r)))
    deform(melt, melt_shape)
    solidify(melt, 0.02)
    smooth(melt)
    assign(melt, material("RPMeltMat", [(0.0, (0.98, 0.86, 0.52)), (0.7, (1.0, 0.94, 0.72)), (1.0, (0.96, 0.78, 0.40))],
                          coord="r", lo=0.0, hi=0.9, rough=0.22, sss=0.5, coat=0.6, bump=0.2, bump_scale=8, vary=0.12))
    parts += [crust, base, sauce, melt]
    return parts


def recipe_cake():
    stand_mat = M.material("RCStand", [(0.0, (0.86, 0.88, 0.94)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=-0.6, hi=0.0,
                           rough=0.12, coat=0.8, coat_rough=0.05)
    stand = lathe("RCStandBody", [(0.0, -0.62), (0.55, -0.62), (0.58, -0.58), (0.2, -0.48), (0.14, -0.2), (0.2, -0.1),
                                  (1.3, -0.06), (1.34, -0.02), (1.3, 0.0), (0.0, 0.0)], 128)
    subdivide(stand, 1)
    assign(smooth(stand, 50), stand_mat)
    sponge = lathe("RCSponge", [(0.0, 0.0), (1.08, 0.0), (1.12, 0.04), (1.12, 0.5), (1.08, 0.55), (0.0, 0.55)], 128)
    subdivide(sponge, 1)
    smooth(sponge, 50)
    assign(sponge, material("RCSpongeMat", [(0.0, (0.94, 0.60, 0.70)), (1.0, (0.98, 0.74, 0.80))], coord="z", lo=0.0, hi=0.55,
                            rough=0.35, sss=0.3, coat=0.3, bump=0.05, bump_scale=14))
    glaze = polar_disc("RCGlaze", 36, 192, 1.1, 1.1)
    deform(glaze, lambda co: Vector((co.x, co.y, 0.56 + 0.012 * fbm(co * 3))))
    solidify(glaze, 0.03)
    assign(smooth(glaze), material("RCGlazeMat", [(0.0, (1.0, 0.90, 0.78)), (0.8, (0.99, 0.86, 0.72)), (1.0, (0.96, 0.78, 0.64))],
                                   coord="r", lo=0.0, hi=1.1, rough=0.18, sss=0.4, coat=0.7))
    parts = [stand, sponge, glaze]
    # бордюр из кремовых розочек
    cream = material("RCCream", [(0.0, (0.92, 0.44, 0.58)), (1.0, (1.0, 0.68, 0.78))], coord="z", lo=0.55, hi=0.75,
                     rough=0.25, sss=0.4, coat=0.5)
    n = 22
    for i in range(n):
        a = 2 * math.pi * i / n
        b = sphere(f"RCRose{i}", 0.11, 24, 16)
        b.scale = (1.0, 1.0, 0.9)
        b.location = (1.0 * math.cos(a), 1.0 * math.sin(a), 0.62)
        apply_transform(b)
        deform(b, lambda co, c=Vector((math.cos(a), math.sin(a), 0)): co + Vector((0, 0, 0.03 * math.sin(6 * math.atan2(co.y - c.y, co.x - c.x)))))
        assign(smooth(b), cream)
        parts.append(b)
    # капли глазури по бокам
    drip = material("RCDrip", [(0.0, (0.95, 0.55, 0.66)), (1.0, (1.0, 0.75, 0.82))], coord="z", lo=0.2, hi=0.56, rough=0.12,
                    coat=0.8)
    rnd = random.Random(4)
    for i in range(16):
        a = 2 * math.pi * (i + rnd.uniform(-0.2, 0.2)) / 16
        L = rnd.uniform(0.12, 0.3)
        d = capsule(f"RCDrop{i}", L, 0.05, 16, 12)
        d.rotation_euler = (0, math.radians(90), 0)
        d.location = (1.13 * math.cos(a), 1.13 * math.sin(a), 0.54 - L / 2)
        apply_transform(d)
        assign(smooth(d), drip)
        parts.append(d)
    return parts


def recipe_salad():
    bowl = lathe("RSBowl", [(0.0, 0.0), (0.5, 0.0), (0.54, 0.03), (0.55, 0.08), (0.62, 0.1), (1.05, 0.32), (1.3, 0.56),
                            (1.36, 0.64), (1.34, 0.67), (1.3, 0.65), (1.24, 0.58), (1.0, 0.36), (0.6, 0.2), (0.0, 0.18)], 128)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = material("RSBowlOut", [(0.0, (0.24, 0.54, 0.80)), (1.0, (0.44, 0.74, 0.96))], coord="z", lo=0.0, hi=0.66,
                   rough=0.14, coat=0.8, coat_rough=0.05)
    inn = material("RSBowlIn", [(0.0, (0.92, 0.94, 0.97)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=0.66,
                   rough=0.14, coat=0.8, coat_rough=0.05)

    def inner(n, c):
        rr = Vector((c.x, c.y, 0))
        return rr.length > 1e-3 and n.dot(rr.normalized()) < -0.05
    assign_faces(bowl, out, [(inner, inn)])
    parts = [bowl]
    # подушка из салатных листьев
    bed = polar_disc("RSBed", 36, 180, 1.18, 1.18)
    deform(bed, lambda co: Vector((co.x, co.y, 0.5 + 0.06 * fbm(co * 2.5) - 0.08 * (math.hypot(co.x, co.y) / 1.18) ** 2)))
    solidify(bed, 0.05)
    assign(smooth(bed), material("RSBedMat", [(0.0, (0.62, 0.86, 0.30)), (1.0, (0.30, 0.64, 0.16))], coord="r", lo=0.0,
                                 hi=1.18, rough=0.3, sss=0.3, coat=0.4, bump=0.3, bump_scale=6, vary=0.2))
    parts.append(bed)
    rnd = random.Random(8)
    for i in range(11):
        a = 2 * math.pi * i / 11 + rnd.uniform(-0.2, 0.2)
        r = 0.82 + rnd.uniform(-0.05, 0.06)
        leaf = M.lettuce_leaf(f"RSLeaf{i}", rx=0.5, ry=0.32, cup=0.3, curl=0.15, ruffle=0.06, waves=12, seed=i)
        rotate_all(leaf, (math.radians(-12), 0, a + rnd.uniform(-0.5, 0.5)))
        for o in leaf:
            o.location = (r * math.cos(a), r * math.sin(a), 0.62)
        parts += leaf
    return parts


def recipe_paella():
    pan_mat = material("RPaPan", [(0.0, (0.10, 0.10, 0.12)), (1.0, (0.30, 0.30, 0.34))], coord="z", lo=0.0, hi=0.3,
                       rough=0.3, metal=0.8)
    pan = lathe("RPaPanBody", [(0.0, 0.0), (1.15, 0.0), (1.28, 0.22), (1.32, 0.28), (1.29, 0.29), (1.22, 0.2),
                               (1.12, 0.06), (0.0, 0.06)], 128)
    subdivide(pan, 1)
    assign(smooth(pan, 50), pan_mat)
    parts = [pan]
    for i, s in enumerate((-1, 1)):
        h = torus(f"RPaHandle{i}", 0.17, 0.04, 48, 12)
        h.scale = (1.0, 0.7, 1.0)
        h.location = (s * 1.42, 0, 0.24)
        apply_transform(h)
        assign(smooth(h), pan_mat)
        parts.append(h)
    rice = polar_disc("RPaRice", 40, 200, 1.18, 1.18)
    deform(rice, lambda co: Vector((co.x, co.y, 0.18 + 0.025 * fbm(co * 9) + 0.02 * fbm(co * 3))))
    solidify(rice, 0.04)
    rice_mat = material("RPaRiceMat", [(0.0, (0.96, 0.66, 0.16)), (0.6, (1.0, 0.80, 0.30)), (1.0, (0.92, 0.56, 0.12))],
                        coord="r", lo=0.0, hi=1.18, rough=0.35, sss=0.3, coat=0.3, bump=0.5, bump_scale=40, bump_detail=6,
                        vary=0.2, vary_scale=8)
    add_speckles(rice_mat, (1.0, 0.92, 0.6), scale=70, threshold=0.62, strength=0.6)
    assign(smooth(rice), rice_mat)
    parts.append(rice)
    # зеленый горошек и перец
    rnd = random.Random(11)
    pea = material("RPaPea", [(0.0, (0.30, 0.62, 0.16)), (1.0, (0.50, 0.82, 0.26))], coord="z", lo=0.18, hi=0.28,
                   rough=0.2, coat=0.6, sss=0.3)
    for i in range(26):
        a = rnd.uniform(0, 6.28)
        r = 1.05 * math.sqrt(rnd.random())
        p = sphere(f"RPaPeaB{i}", 0.04, 16, 10)
        p.location = (r * math.cos(a), r * math.sin(a), 0.23)
        apply_transform(p)
        assign(smooth(p), pea)
        parts.append(p)
    return parts


# MARK: - Начинки

def top_tomato():
    rind = material("TTRind", [(0.0, (0.80, 0.08, 0.05)), (1.0, (0.96, 0.22, 0.12))], coord="z", lo=-0.05, hi=0.05,
                    rough=0.15, sss=0.4, coat=0.8)
    disc = cylinder("TTSlice", 0.42, 0.08, 72)
    assign(smooth(disc, 50), rind)
    face = polar_disc("TTFace", 30, 160, 0.4, 0.4)

    def col(co, n):
        r = math.hypot(co.x, co.y) / 0.4
        a = math.atan2(co.y, co.x)
        f = (a / (2 * math.pi) * 5) % 1.0
        d = min(f, 1 - f) * 2 * math.pi * r / 5
        wall = max(M.smoothstep(0.03, 0.0, d) if r > 0.2 else 0.0, M.smoothstep(0.26, 0.18, r), M.smoothstep(0.78, 0.86, r))
        return MX.mix((0.90, 0.14, 0.09), (1.0, 0.46, 0.38), wall)
    MX.vcol(face, col)
    deform(face, lambda co: Vector((co.x, co.y, 0.042)))
    assign(smooth(face), MX.vmat("TTFaceMat", rough=0.1, sss=0.5, coat=0.9, coat_rough=0.04))
    parts = [disc, face]
    rnd = random.Random(3)
    seed_mat = flat("TTSeed", (1.0, 0.86, 0.50), rough=0.2, coat=0.6, sss=0.3)
    for k in range(5):
        a = 2 * math.pi * (k + 0.5) / 5
        for j in range(3):
            s = sphere(f"TTSeed{k}{j}", 0.025, 12, 8)
            s.scale = (1.3, 0.8, 0.5)
            rr = 0.17 + 0.06 * j + rnd.uniform(-0.01, 0.01)
            s.location = (rr * math.cos(a + rnd.uniform(-0.15, 0.15)), rr * math.sin(a + rnd.uniform(-0.15, 0.15)), 0.05)
            s.rotation_euler = (0, 0, a)
            apply_transform(s)
            assign(smooth(s), seed_mat)
            parts.append(s)
    return parts


def top_lime():
    return MX.lime_wheel("TLWheel", R=0.42, th=0.07)


def top_cheese():
    mat = material("TCMat", [(0.0, (0.98, 0.74, 0.18)), (1.0, (1.0, 0.86, 0.36))], coord="z", lo=-0.3, hi=0.3, rough=0.35,
                   sss=0.4, coat=0.3)
    cube = box_mesh("TCCube", 0.5, 0.5, 0.36, -0.18)
    bevel(cube, 0.06, 4, 30)
    holes = []
    for i, (x, y, z, r) in enumerate(((0.25, 0.05, 0.05, 0.08), (-0.08, -0.25, -0.06, 0.07), (0.05, 0.12, 0.18, 0.08))):
        h = sphere(f"TCHole{i}", r, 24, 16)
        h.location = (x, y, z)
        holes.append(h)
    boolean_cut(cube, holes)
    smooth(cube, 40)
    assign(cube, mat)
    return rotate_all([cube], (0, 0, math.radians(25)))


def top_grapes():
    mat = material("TGMat", [(0.0, (0.30, 0.10, 0.36)), (1.0, (0.56, 0.26, 0.62))], coord="z", lo=-0.2, hi=0.25,
                   rough=0.18, sss=0.5, sss_radius=(0.8, 0.3, 1.0), coat=0.7)
    parts = []
    for i, (x, y) in enumerate(((-0.17, -0.06), (0.17, -0.06), (0.0, 0.18))):
        g = sphere(f"TGGrape{i}", 0.2, 32, 20)
        g.scale = (1.0, 1.12, 0.9)
        g.location = (x, y, 0.0)
        apply_transform(g)
        assign(smooth(g), mat)
        parts.append(g)
    stem = tube("TGStem", [(0.0, 0.18, 0.18), (0.04, 0.28, 0.26), (0.1, 0.34, 0.3)], 0.03)
    assign(smooth(stem), flat("TGStemMat", (0.42, 0.30, 0.16), rough=0.5))
    parts.append(stem)
    return parts


def top_milk():
    """Шапочка взбитых сливок: молоко на блюде."""
    import models_bakery as BK
    mound = BK.cream_mound("TMCream", R=0.36, H=0.3, peaks=((0.0, 0.0, 0.16, 0.12, 0.06, 0.02),), folds=6)
    assign(mound, material("TMMat", [(0.0, (0.92, 0.88, 0.82)), (0.5, (0.99, 0.97, 0.93)), (1.0, (1.0, 1.0, 0.98))],
                           coord="z", lo=0.0, hi=0.45, rough=0.3, sss=0.5, coat=0.3))
    return [mound]


def top_carrot():
    parts = []
    skin = material("TKSkin", [(0.0, (0.90, 0.36, 0.04)), (1.0, (1.0, 0.52, 0.10))], coord="z", lo=-0.05, hi=0.05,
                    rough=0.3, sss=0.3, coat=0.5)
    for i, (x, y, z, tilt) in enumerate(((-0.14, -0.04, 0.0, 0), (0.16, 0.08, 0.06, 14))):
        c = cylinder(f"TKCoin{i}", 0.24, 0.08, 56)
        assign(smooth(c, 50), skin)
        face = polar_disc(f"TKFace{i}", 20, 120, 0.235, 0.235)

        def col(co, n):
            r = math.hypot(co.x, co.y) / 0.235
            if r < 0.45:
                return (1.0, 0.70, 0.30)
            if r < 0.55:
                return (1.0, 0.60, 0.20)
            return (0.98, 0.48, 0.08)
        MX.vcol(face, col)
        deform(face, lambda co: Vector((co.x, co.y, 0.041)))
        assign(smooth(face), MX.vmat(f"TKFaceMat{i}", rough=0.2, sss=0.4, coat=0.7))
        coin = [c, face]
        rotate_all(coin, (math.radians(tilt), 0, 0))
        for o in coin:
            o.location = (x, y, z)
        parts += coin
    return parts


RECIPE = {
    "recipe_pizza": recipe_pizza, "recipe_cake": recipe_cake, "recipe_salad": recipe_salad, "recipe_paella": recipe_paella,
    "top_tomato": top_tomato, "top_lime": top_lime, "top_cheese": top_cheese, "top_grapes": top_grapes,
    "top_milk": top_milk, "top_carrot": top_carrot,
}
M.MODELS.update(RECIPE)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--size", type=int, default=0)
    ap.add_argument("--samples", type=int, default=96)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    M.ELEVATION = TOP_ELEVATION
    M.AZIMUTH = 0.0
    for sid in [s for s in args.only.split(",") if s] or list(RECIPE):
        size = args.size or (640 if sid.startswith("recipe_") else 200)
        M.render(sid, args.out, size, samples=args.samples)
        print("rendered", sid, flush=True)


if __name__ == "__main__":
    main()
