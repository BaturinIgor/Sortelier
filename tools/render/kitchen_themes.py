"""Раскладки фонов кухни для остальных стилей: Мексика, пекарня, Хэллоуин, осень, сладости, барбекю, гурман,
персиковая и лавандовая кухни. Подключается из environment.py после kitchen.py и дополняет kitchen.DRESS и
kitchen.STYLE_EXTRA. Помощники, материалы и общие предметы - в kitchen.py, правила те же: предмет собирается в
начале координат (низ на z=0, лицом к камере по -Y) и ставится put()/L()/Cn().
"""
import math
import random

import bpy
from mathutils import Vector

import models as M
import icons as I
import models_events as EV
import models_remodel as RM
import kitchen as K
from kitchen import (CS, COUNTER_TOP, LEDGE_TOP, RAIL_Z, Cn, L, Sh, ceramic, glass_jar, glass_mat, glow_mat,
                     lathe_s, metal, mix_c, put, rbox, shell, wood_sh)

M.load_extensions()


# MARK: - Помощники

def prod(pid, s=0.2, rx=0.0, ry=0.0, rz=0.0):
    """Модель продукта из игры как предмет фона: низ на z=0, центр по XY в начале координат, масштаб s."""
    before = set(bpy.data.objects)
    M.MODELS[pid]()
    new = [o for o in bpy.data.objects if o not in before]
    for o in list(new):
        if o.type != "MESH" or o.get("no_bounds"):
            new.remove(o)
            bpy.data.objects.remove(o)
    put(new, 0, 0, 0, rx=rx, ry=ry, rz=rz)
    pts = [o.matrix_world @ Vector(c) for o in new for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    put(new, -(lo.x + hi.x) / 2, -(lo.y + hi.y) / 2, -lo.z)
    put(new, 0, 0, 0, s=s)
    return new


def gingham_mat(name, color, scale=9.0):
    sh = Sh(name, rough=0.65, sheen=0.4)
    x, y, z = sh.xyz()
    a = sh.math("GREATER_THAN", sh.math("PINGPONG", sh.math("MULTIPLY", x, scale), 0.5), 0.25)
    b = sh.math("GREATER_THAN", sh.math("PINGPONG", sh.math("MULTIPLY", sh.math("ADD", y, z), scale), 0.5), 0.25)
    sh.color(sh.ramp(sh.math("MULTIPLY", sh.math("ADD", a, b), 0.5),
                     [(0.0, (0.99, 0.97, 0.93)), (0.5, mix_c(color, (1, 1, 1), 0.45)), (1.0, color)], "CONSTANT"))
    sh.bump(sh.noise(None, 60.0, 2.0), 0.1, 0.003)
    return sh.mat


def along(pts, n, offset=0.5):
    """n точек равномерно по длине ломаной."""
    P = [Vector(p) for p in pts]
    cum = [0.0]
    for a, b in zip(P, P[1:]):
        cum.append(cum[-1] + (b - a).length)
    Ltot = cum[-1]
    out = []
    import bisect as _b
    for k in range(n):
        s = Ltot * (k + offset) / n
        i = min(max(_b.bisect_right(cum, s) - 1, 0), len(P) - 2)
        out.append(P[i].lerp(P[i + 1], (s - cum[i]) / max(1e-6, cum[i + 1] - cum[i])))
    return out


def swags(spans, z, sag, y, n=10):
    pts = []
    for k, (x0, x1) in enumerate(spans):
        pts += K.catenary(x0, x1, z, sag, y, n)[(1 if k else 0):]
    return pts


def ribbed(name, r, h, color, ribs=10, depth=0.06, rough=0.3, stem=True, stem_col=(0.42, 0.34, 0.16), stripes=None):
    """Тыква или тыквочка: дольки (ребра), ямка у хвостика, хвостик."""
    ob = M.sphere(name, 1.0, 96, 48)

    def f(co):
        a = math.atan2(co.y, co.x)
        rr = 1.0 - depth * (0.5 - 0.5 * math.cos(ribs * a)) ** 2 * math.sqrt(max(0.0, 1 - co.z * co.z))
        z = co.z * h / 2 - (0.12 * h if co.z > 0 else 0.0) * math.exp(-((co.x * co.x + co.y * co.y) / 0.08)) * (co.z > 0.85)
        return Vector((co.x * r * rr, co.y * r * rr, z + h / 2))
    M.deform(ob, f)
    M.smooth(ob)
    sh = Sh(name + "M", rough=rough, coat=0.5, sss=0.05)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    groove = sh.remap(sh.math("COSINE", sh.math("MULTIPLY", ang, float(ribs))), 0.6, 1.0)
    col = sh.ramp(sh.remap(z, 0.0, h, smooth=False), [(0.0, I.shade(color, 0.7)), (0.6, color),
                                                       (1.0, tuple(min(1.0, c * 1.1 + 0.04) for c in color))])
    col = sh.mix(sh.math("MULTIPLY", groove, 0.45), col, I.shade(color, 0.62))
    if stripes:
        col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.math("COSINE", sh.math("MULTIPLY", ang, float(ribs))), 0.75, 0.95), 0.9),
                     col, stripes)
    sh.color(col)
    sh.bump(sh.noise(None, 25.0, 3.0), 0.08, 0.004)
    parts = [M.assign(ob, sh.mat)]
    if stem:
        st = EV.sweep(name + "Stem", EV.spline([(0.0, 0.0, h * 0.86), (0.01, 0.0, h * 1.0), (0.04, 0.0, h * 1.12)], 5),
                      lambda t: 0.028 * r / 0.2 * (1 - 0.3 * t), segs=8)
        parts.append(M.assign(st, ceramic(name + "StemM", stem_col, rough=0.7, coat=0.0, mottle=0.1)))
    return parts


def vase_flowers(name, vase_col, flower_col, kind="tulip", n=5, seed=2, vase_mat=None):
    """Ваза с цветами: тюльпаны, бархатцы, лаванда или ромашки."""
    rnd = random.Random(seed)
    vm = vase_mat or ceramic(name + "Vase", vase_col, rough=0.14)
    vase = lathe_s(name, [(0.055, 0.0), (0.08, 0.03), (0.09, 0.1), (0.07, 0.18), (0.045, 0.23), (0.05, 0.26),
                          (0.058, 0.27)], 64, 4)
    parts = [M.assign(M.smooth(vase), vm)]
    green = I.toy(name + "Green", (0.30, 0.62, 0.22), rough=0.35, coat=0.4)
    fm = ceramic(name + "Flower", flower_col, rough=0.3, coat=0.4, mottle=0.08)
    for k in range(n):
        a = 2 * math.pi * k / n + rnd.uniform(-0.3, 0.3)
        lean = rnd.uniform(0.06, 0.16) if k else 0.0
        h = rnd.uniform(0.36, 0.48) if kind != "lavender" else rnd.uniform(0.4, 0.52)
        top = Vector((lean * math.cos(a), lean * math.sin(a) * 0.5, h))
        pts = EV.spline([(0.0, 0.0, 0.18), (top.x * 0.4, top.y * 0.4, h * 0.6), tuple(top)], 6)
        parts.append(M.assign(EV.sweep(f"{name}Stem{k}", pts, 0.008, segs=8), green))
        if kind == "tulip":
            head = lathe_s(f"{name}H{k}", [(0.0, -0.005), (0.03, 0.01), (0.04, 0.04), (0.034, 0.075), (0.026, 0.085)], 6, 4)
            M.deform(head, lambda co: co * (1 + 0.12 * math.cos(3 * math.atan2(co.y, co.x)) * min(1.0, co.z / 0.07)))
            M.smooth(head)
        elif kind == "marigold":
            head = M.sphere(f"{name}H{k}", 0.045, 32, 16)
            head.scale = (1.0, 1.0, 0.8)
            M.apply_transform(head)
            M.push_normals(head, lambda co, nn: 0.008 * M.fbm(co * 90))
            M.smooth(head)
        elif kind == "lavender":
            head = M.capsule(f"{name}H{k}", 0.13, 0.016, 16, 12)
            head.rotation_euler = (0, math.radians(90), 0)
            M.apply_transform(head)
            M.push_normals(head, lambda co, nn: 0.006 * (0.5 + 0.5 * math.sin(co.z * 180)))
            head.location.z += 0.06
            M.apply_transform(head)
            M.smooth(head)
        else:  # ромашка
            head = M.cylinder(f"{name}H{k}", 0.045, 0.01, 24)
            M.deform(head, lambda co: co * (1 + 0.25 * max(0.0, math.cos(12 * math.atan2(co.y, co.x)))))
            M.smooth(head)
        M.assign(head, fm)
        put([head], top.x, top.y, top.z, ry=lean * 2 * math.cos(a), rx=-lean * 2 * math.sin(a))
        parts.append(head)
        if kind == "daisy":
            eye = M.sphere(f"{name}E{k}", 0.016, 16, 8)
            put([eye], top.x, top.y - 0.004, top.z + 0.008)
            parts.append(M.assign(eye, ceramic(name + "Eye", (1.0, 0.80, 0.20))))
        if k < 3 and kind != "lavender":
            lf = EV.leaf(f"{name}Lf{k}", length=0.14, width=0.04, fold=0.2, curl=-0.1, thick=0.008, petiole=0.01)
            put(lf, 0, 0, 0, ry=math.radians(-60))
            put(lf, 0, 0, 0, rz=a + 0.5)
            put(lf, 0.0, 0.0, 0.22)
            parts += lf
    return parts


def teapot(name, color, ink=None, r=0.13):
    m = K.patterned_ceramic(name + "M", color, ink, "dots", 0.04, 0.16, 7) if ink else ceramic(name + "M", color)
    body = lathe_s(name, [(0.07, 0.0), (r * 0.95, 0.03), (r, 0.09), (r * 0.85, 0.16), (r * 0.55, 0.19)], 64, 5)
    lid = lathe_s(name + "Lid", [(r * 0.58, 0.185), (r * 0.5, 0.205), (r * 0.2, 0.215), (0.0, 0.216)], 48, 3)
    kn = M.sphere(name + "Kn", 0.02, 16, 8)
    kn.location = (0, 0, 0.23)
    M.apply_transform(kn)
    sp = EV.sweep(name + "Sp", EV.spline([(r * 0.8, 0.0, 0.06), (r * 1.25, 0.0, 0.11), (r * 1.55, 0.0, 0.19)], 6),
                  lambda t: 0.03 - 0.013 * t, segs=14)
    hd = EV.sweep(name + "Hd", [(-r * 0.85 - 0.06 * math.sin(math.pi * k / 14), 0.0, 0.16 - 0.11 * k / 14) for k in range(15)],
                  0.014, segs=12)
    plain = ceramic(name + "Plain", color)
    return [M.assign(M.smooth(body), m), M.assign(M.smooth(lid), plain), M.assign(M.smooth(kn), plain),
            M.assign(sp, plain), M.assign(hd, plain)]


def cup_saucer(name, color, rim=None):
    sauc = K.plate_obj(name + "Saucer", 0.09, ceramic(name + "S", color), ceramic(name + "SR", rim) if rim else None)
    cup = K.mug(name, color, r=0.05, h=0.07, fill=(0.62, 0.36, 0.16))
    put(cup, 0, 0, 0.02)
    return [sauc] + cup


def tea_set(name, color, ink=None):
    parts = teapot(name + "Pot", color, ink)
    parts += put(cup_saucer(name + "Cup1", color, ink), 0.3, -0.06, 0.0)
    parts += put(cup_saucer(name + "Cup2", color, ink), -0.28, -0.05, 0.0, rz=1.4)
    return parts


def bunting(name, pts, colors, kind="pennant", n=14, seed=3, string=(0.92, 0.86, 0.72)):
    """Гирлянда флажков: треугольники или папель пикадо (бумага с вырезанным узором)."""
    rnd = random.Random(seed)
    parts = [M.assign(EV.sweep(name + "Str", EV.spline(pts, 8), 0.006, segs=8),
                      ceramic(name + "StrM", string, rough=0.6, coat=0.0, mottle=0.0))]
    mats = []
    for k, c in enumerate(colors):
        if kind == "picado":
            sh = Sh(f"{name}P{k}", rough=0.6, sheen=0.3)
            x, y, z = sh.xyz()
            # узор: ряд ромбов и цветок посередине, вырезы прозрачные
            u = sh.math("MULTIPLY", x, 1.0)
            cut1 = sh.remap(sh.math("ADD", sh.math("ABSOLUTE", sh.math("SUBTRACT", sh.math("PINGPONG", sh.math("MULTIPLY", u, 18.0), 0.5), 0.25)),
                                    sh.math("ABSOLUTE", sh.math("MULTIPLY", sh.math("ADD", z, 0.04), 18.0))), 0.2, 0.16)
            rr = sh.vmath("LENGTH", sh.combine(x, sh.math("ADD", z, 0.11), 0.0))
            ang = sh.math("ARCTAN2", sh.math("ADD", z, 0.11), x)
            petal = sh.math("MULTIPLY", sh.math("ABSOLUTE", sh.math("COSINE", sh.math("MULTIPLY", ang, 3.0))), 0.045)
            cut2 = sh.math("MULTIPLY", sh.remap(sh.math("SUBTRACT", rr, petal), 0.004, -0.002), sh.remap(rr, 0.012, 0.016))
            holes = sh.math("MAXIMUM", cut1, cut2)
            sh.color(c)
            sh.set("Alpha", sh.math("SUBTRACT", 1.0, holes))
            mats.append(sh.mat)
        else:
            mats.append(ceramic(f"{name}F{k}", c, rough=0.5, coat=0.1, mottle=0.04))
    for k, p in enumerate(along(pts, n)):
        if kind == "picado":
            w, h = 0.17, 0.21
            outline = [(-w / 2, 0.0), (-w / 2, -h)] + [(-w / 2 + w * i / 12, -h - 0.012 * abs(math.sin(math.pi * i / 2))) for i in range(1, 12)] + [(w / 2, -h), (w / 2, 0.0)]
            fl = I.slab(f"{name}{k}", I.ccw(outline), 0.004, 0.0, mats[k % len(mats)])
        else:
            fl = I.slab(f"{name}{k}", I.ccw(I.round_corners([(-0.07, 0.0), (0.0, -0.16), (0.07, 0.0)], 0.012, 3)), 0.008,
                        0.003, mats[k % len(mats)])
        put([fl], p.x, p.y - 0.004, p.z + 0.004, rz=rnd.uniform(-0.15, 0.15), ry=rnd.uniform(-0.08, 0.08))
        parts.append(fl)
    return parts


def cobweb(name, cx, cz, radius, a0, a1, y=0.5, spokes=6, rings=5):
    """Паутина в углу: радиальные нити и провисающие поперечные дуги."""
    m = ceramic(name + "M", (0.86, 0.86, 0.92), rough=0.5, coat=0.0, mottle=0.0)
    b = m.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (0.7, 0.7, 0.8, 1)
    b.inputs["Emission Strength"].default_value = 0.25
    parts = []
    angs = [math.radians(a0 + (a1 - a0) * k / (spokes - 1)) for k in range(spokes)]
    for k, a in enumerate(angs):
        parts.append(EV.sweep(f"{name}S{k}", [(cx, y, cz), (cx + radius * math.cos(a), y, cz + radius * math.sin(a))], 0.0035,
                              segs=6))
    for j in range(1, rings + 1):
        rr = radius * j / (rings + 0.6)
        for k in range(spokes - 1):
            a, b_ = angs[k], angs[k + 1]
            pts = []
            for i in range(9):
                t = i / 8
                aa = a + (b_ - a) * t
                sag = 0.18 * rr * (1 - (2 * t - 1) ** 2)
                pts.append((cx + (rr - sag) * math.cos(aa), y, cz + (rr - sag) * math.sin(aa)))
            parts.append(EV.sweep(f"{name}R{j}{k}", pts, 0.0028, segs=6))
    for o in parts:
        M.assign(o, m)
    return parts


def bat(name, s=1.0):
    """Летучая мышь силуэтом: крылья с фестонами, ушки, оранжевые глазки."""
    pts = [(0.0, 0.05)]
    pts += [(0.02, 0.07), (0.03, 0.035), (0.06, 0.04), (0.12, 0.06), (0.2, 0.05), (0.26, 0.0)]
    for i in range(1, 4):
        x = 0.26 - 0.07 * i
        pts += [(x + 0.035, -0.035), (x, -0.012)]
    pts += [(0.04, -0.02), (0.0, -0.06)]
    mirror = [(-x, y) for x, y in reversed(pts[1:-1])]
    outline = I.ccw(pts + mirror)
    m = ceramic(name + "M", (0.12, 0.08, 0.16), rough=0.4, coat=0.4, mottle=0.0)
    ob = I.slab(name, outline, 0.02, 0.008, m)
    parts = [ob]
    for sx in (-1, 1):
        e = M.sphere(f"{name}E{sx}", 0.008, 12, 6)
        e.location = (sx * 0.014, -0.012, 0.035)
        M.apply_transform(e)
        parts.append(M.assign(e, glow_mat(name + "Eye", (1.0, 0.6, 0.1), 3.0)))
    thread = EV.sweep(name + "T", [(0.0, 0.0, 0.05), (0.0, 0.0, 0.5)], 0.002, segs=4)
    parts.append(M.assign(thread, ceramic(name + "TM", (0.2, 0.2, 0.2), rough=0.6, coat=0.0, mottle=0.0)))
    return put(parts, 0, 0, 0, s=s)


def carve_face(mat, r, h, light=4.0, teeth=True):
    """Вырезанное лицо тыквы-фонаря в ее материале: глаза-треугольники, нос, рот с зубцами светятся."""
    sh = RM.Sh.__new__(RM.Sh)
    sh.mat, sh.nodes, sh.links = mat, mat.node_tree.nodes, mat.node_tree.links
    sh.bsdf, sh._tc, sh._normal = sh.nodes["Principled BSDF"], None, None
    x, y, z = sh.xyz()
    front = sh.remap(y, -r * 0.3, -r * 0.6)
    zc = sh.math("SUBTRACT", z, h * 0.5)
    ax = sh.math("ABSOLUTE", x)
    ex = sh.math("SUBTRACT", ax, r * 0.36)
    ey = sh.math("SUBTRACT", zc, h * 0.12)
    tri = sh.math("SUBTRACT", sh.math("ABSOLUTE", ex), sh.math("MULTIPLY", sh.math("SUBTRACT", h * 0.11, ey), 0.6))
    eye = sh.math("MULTIPLY", sh.remap(tri, 0.004, -0.004),
                  sh.math("MULTIPLY", sh.remap(ey, -0.004, 0.004), sh.remap(ey, h * 0.11, h * 0.1)))
    my = sh.math("ADD", zc, h * 0.1)
    curve = sh.math("MULTIPLY", sh.math("MULTIPLY", x, x), 1.6 / r)
    top_edge = sh.math("SUBTRACT", my, sh.math("SUBTRACT", curve, h * 0.02))
    bot_edge = sh.math("SUBTRACT", my, sh.math("SUBTRACT", curve, h * 0.14))
    mouth = sh.math("MULTIPLY", sh.remap(top_edge, 0.004, -0.004), sh.remap(bot_edge, -0.004, 0.004))
    if teeth:
        tooth = sh.math("MULTIPLY", sh.math("PINGPONG", sh.math("MULTIPLY", sh.math("ADD", x, 0.5), 7.0 / r), 0.5), h * 0.1)
        mouth = sh.math("MULTIPLY", mouth, sh.remap(sh.math("SUBTRACT", top_edge, sh.math("MULTIPLY", tooth, -1.0)), -0.002, 0.004))
    mouth = sh.math("MULTIPLY", mouth, sh.remap(ax, r * 0.66, r * 0.58))
    noset = sh.math("SUBTRACT", ax, sh.math("MULTIPLY", sh.math("SUBTRACT", h * 0.04, zc), 0.6))
    nose = sh.math("MULTIPLY", sh.remap(noset, 0.004, -0.004),
                   sh.math("MULTIPLY", sh.remap(zc, -0.004, 0.004), sh.remap(zc, h * 0.04, h * 0.035)))
    mask = sh.math("MULTIPLY", sh.math("MAXIMUM", sh.math("MAXIMUM", eye, mouth), nose), front)
    out = sh.nodes["Material Output"]
    em = sh.nodes.new("ShaderNodeEmission")
    em.inputs["Color"].default_value = (1.0, 0.62, 0.16, 1)
    em.inputs["Strength"].default_value = light
    mix = sh.nodes.new("ShaderNodeMixShader")
    sh.links.new(mask, mix.inputs["Fac"])
    sh.links.new(sh.bsdf.outputs[0], mix.inputs[1])
    sh.links.new(em.outputs[0], mix.inputs[2])
    sh.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def jack_o_lantern(name, r=0.18, h=0.3, teeth=True, light=4.0):
    """Тыква-фонарь: ребристая тыква, вырезанное лицо светится, внутри теплый огонек."""
    parts = ribbed(name, r, h, (0.98, 0.50, 0.08), ribs=10, depth=0.08, rough=0.35)
    carve_face(parts[0].data.materials[0], r, h, light, teeth)
    lt = bpy.data.lights.new(name + "Light", type="POINT")
    lt.energy = 2.5
    lt.color = (1.0, 0.6, 0.25)
    lt.shadow_soft_size = 0.05
    lo = bpy.data.objects.new(name + "Light", lt)
    lo.location = (0, -r - 0.08, h * 0.5)
    bpy.context.scene.collection.objects.link(lo)
    parts.append(lo)
    return parts


def potion(name, liquid, shape="flask", h=0.3, glow=1.2, label=True):
    if shape == "flask":
        prof = [(0.03, 0.0), (0.09, 0.02), (0.11, 0.08), (0.09, 0.15), (0.03, 0.19), (0.026, h - 0.03), (0.032, h)]
        fill_prof = [(0.03, 0.01), (0.085, 0.025), (0.1, 0.08), (0.075, 0.13), (0.0, 0.135)]
    elif shape == "tall":
        prof = [(0.05, 0.0), (0.055, 0.02), (0.055, h * 0.6), (0.03, h * 0.75), (0.022, h - 0.02), (0.028, h)]
        fill_prof = [(0.045, 0.01), (0.048, 0.02), (0.048, h * 0.45), (0.0, h * 0.46)]
    else:  # кувшинчик-капля
        prof = [(0.03, 0.0), (0.07, 0.02), (0.08, 0.06), (0.05, 0.14), (0.022, h * 0.75), (0.03, h * 0.8)]
        fill_prof = [(0.03, 0.01), (0.065, 0.025), (0.072, 0.06), (0.0, 0.07)]
    gl = lathe_s(name, prof, 48, 4)
    M.assign(M.smooth(gl), glass_mat(name + "G", tint=mix_c(liquid, (1, 1, 1), 0.7), edge=mix_c(liquid, (1, 1, 1), 0.5)))
    gl.visible_shadow = False
    fl = lathe_s(name + "F", fill_prof, 48, 3)
    M.assign(M.smooth(fl), glow_mat(name + "L", liquid, glow))
    cork = M.cylinder(name + "Cork", 0.026, 0.05, 24)
    cork.location = (0, 0, h + 0.012)
    M.apply_transform(cork)
    M.bevel(cork, 0.006, 2, 30)
    parts = [gl, fl, M.assign(M.smooth(cork, 30), ceramic(name + "CorkM", (0.66, 0.46, 0.26), rough=0.7, coat=0.0))]
    if label and shape != "drop":
        parts.append(K.label_patch(name + "Lb", 0.112 if shape == "flask" else 0.058, 0.06, 0.11, 0.55,
                                   ceramic(name + "P", (0.92, 0.84, 0.62), rough=0.6, coat=0.0), ink=(0.40, 0.20, 0.30)))
    return parts


def cauldron(name):
    iron = K.iron_mat(name + "I", (0.14, 0.13, 0.14))
    pot = shell(name, [(0.1, 0.02), (0.2, 0.06), (0.24, 0.16), (0.22, 0.26), (0.2, 0.29), (0.215, 0.31), (0.19, 0.31),
                       (0.18, 0.28)], 64, 4)
    parts = [M.assign(M.smooth(pot), iron)]
    brew = M.cylinder(name + "Brew", 0.185, 0.01, 64)
    brew.location = (0, 0, 0.27)
    M.apply_transform(brew)
    parts.append(M.assign(brew, glow_mat(name + "BrewM", (0.40, 0.95, 0.30), 1.6)))
    rnd = random.Random(5)
    for k in range(7):
        b = M.sphere(f"{name}Bub{k}", rnd.uniform(0.015, 0.03), 16, 8)
        a = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0, 0.14)
        b.location = (rr * math.cos(a), rr * math.sin(a), 0.28)
        M.apply_transform(b)
        parts.append(M.assign(b, I.toy(name + "BubM", (0.50, 0.98, 0.42), rough=0.1, coat=1.0)))
    for k in range(3):
        a = math.radians(90 + 120 * k)
        lg = M.capsule(f"{name}Leg{k}", 0.08, 0.02, 12, 8)
        lg.rotation_euler = (0, math.radians(90), 0)
        lg.location = (0.15 * math.cos(a), 0.15 * math.sin(a), 0.02)
        M.apply_transform(lg)
        parts.append(M.assign(lg, iron))
    lt = bpy.data.lights.new(name + "Light", type="POINT")
    lt.energy = 3.0
    lt.color = (0.5, 1.0, 0.4)
    lo = bpy.data.objects.new(name + "Light", lt)
    lo.location = (0, -0.05, 0.36)
    bpy.context.scene.collection.objects.link(lo)
    parts.append(lo)
    return parts


def wrapped_candy(name, color, mat_cache={}):
    m = mat_cache.get(color) or I.toy(name + "M", color, rough=0.12, coat=1.0)
    mat_cache[color] = m
    body = M.capsule(name, 0.07, 0.022, 16, 10)
    parts = [M.assign(M.smooth(body), m)]
    for s in (-1, 1):
        w = M.lathe(f"{name}W{s}", [(0.0, 0.0), (0.008, 0.0), (0.022, 0.028), (0.0, 0.03)], 12)
        w.rotation_euler = (0, math.radians(90 * s), 0)
        w.location = (s * 0.03, 0, 0)
        M.apply_transform(w)
        parts.append(M.assign(w, m))
    return parts


def candy_bowl(name, bowl_col, rim_col, colors):
    parts = [K.bowl_obj(name, 0.3, 0.13, ceramic(name + "M", bowl_col), ceramic(name + "R", rim_col))]
    rnd = random.Random(7)
    for k in range(16):
        c = wrapped_candy(f"{name}C{k}", colors[k % len(colors)])
        a = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0.0, 0.2)
        put(c, 0, 0, 0, rz=rnd.uniform(0, 6.28), ry=rnd.uniform(-0.4, 0.4))
        put(c, rr * math.cos(a), rr * math.sin(a), 0.1 + 0.05 * (1 - rr / 0.2) + rnd.uniform(0, 0.04))
        parts += c
    return parts


# MARK: - Мексика

def cactus(name, r=0.1, h=0.22, flower=(0.98, 0.42, 0.62)):
    """Шаровидный кактус: ребра, белые точки-колючки по ребрам, розовый цветок на макушке."""
    ob = M.sphere(name, 1.0, 96, 48)
    ribs = 12

    def f(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 - 0.07 * (0.5 - 0.5 * math.cos(ribs * a))
        return Vector((co.x * r * k, co.y * r * k, co.z * h / 2 + h / 2))
    M.deform(ob, f)
    M.smooth(ob)
    sh = Sh(name + "M", rough=0.4, coat=0.3, sss=0.05)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    rib = sh.remap(sh.math("COSINE", sh.math("MULTIPLY", ang, float(ribs))), 0.4, 1.0)
    col = sh.mix(rib, (0.20, 0.46, 0.22), (0.36, 0.66, 0.30))
    spines = sh.math("MULTIPLY", sh.remap(sh.math("COSINE", sh.math("MULTIPLY", ang, float(ribs))), 0.93, 0.98),
                     sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", z, 30.0), 0.5), 0.12, 0.05))
    col = sh.mix(spines, col, (0.98, 0.96, 0.86))
    sh.color(col)
    parts = [M.assign(ob, sh.mat)]
    head = M.cylinder(name + "Fl", 0.035, 0.01, 24)
    M.deform(head, lambda co: co * (1 + 0.3 * max(0.0, math.cos(8 * math.atan2(co.y, co.x)))))
    head.location = (0, 0, h + 0.005)
    M.apply_transform(head)
    parts.append(M.assign(M.smooth(head), ceramic(name + "FlM", flower, rough=0.3)))
    eye = M.sphere(name + "FlE", 0.012, 12, 6)
    eye.location = (0, 0, h + 0.012)
    M.apply_transform(eye)
    parts.append(M.assign(eye, ceramic(name + "FlE", (1.0, 0.86, 0.3))))
    return parts


def potted_cactus(name, r=0.1, h=0.22, flower=(0.98, 0.42, 0.62), pot_r=0.11):
    parts = K.terracotta_pot(name + "Pot", pot_r, 0.17)
    parts += put(cactus(name, r, h, flower), 0, 0, 0.14)
    return parts


def cantaro(name):
    """Глиняный кувшин: круглое брюшко, горлышко, ручка, расписной поясок с точками."""
    sh = RM.terracotta_sh(name + "M", 0.0, 0.42, band=(0.2, 0.24), dots=(0.3, 10, 0.012))
    body = lathe_s(name, [(0.08, 0.0), (0.15, 0.04), (0.17, 0.14), (0.15, 0.25), (0.08, 0.32), (0.06, 0.38), (0.075, 0.42)],
                   64, 5)
    hd = EV.sweep(name + "Hd", EV.spline([(0.07, 0.0, 0.37), (0.16, 0.0, 0.38), (0.17, 0.0, 0.28), (0.14, 0.0, 0.22)], 6),
                  0.016, segs=12)
    return [M.assign(M.smooth(body), sh.mat), M.assign(hd, sh.mat)]


def talavera_mat(name, base=(0.97, 0.94, 0.86), ink=(0.10, 0.24, 0.66), accent=(0.98, 0.70, 0.12)):
    sh = Sh(name, rough=0.12, coat=0.8, coat_rough=0.05)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    ph = sh.math("PINGPONG", sh.math("MULTIPLY", ang, 8 / (2 * math.pi)), 0.5)
    zz = sh.math("PINGPONG", sh.math("MULTIPLY", z, 7.0), 0.5)
    petal = sh.remap(sh.vmath("LENGTH", sh.combine(sh.math("MULTIPLY", ph, 0.9), sh.math("SUBTRACT", zz, 0.25), 0.0)), 0.2, 0.16)
    dot = sh.remap(sh.vmath("LENGTH", sh.combine(sh.math("MULTIPLY", ph, 0.9), sh.math("SUBTRACT", zz, 0.25), 0.0)), 0.07, 0.05)
    col = sh.mix(petal, base, ink)
    sh.color(sh.mix(dot, col, accent))
    return sh.mat


def molcajete(name):
    """Каменная ступка на трех ножках с гуакамоле и пестиком."""
    sh = Sh(name + "M", rough=0.8)
    pits = sh.voronoi(None, 40.0, out="Distance")
    sh.color(sh.mix(sh.remap(pits, 0.05, 0.15), (0.16, 0.15, 0.15), (0.34, 0.32, 0.31)))
    sh.bump(pits, 0.6, 0.006)
    bowl = shell(name, [(0.12, 0.05), (0.18, 0.09), (0.2, 0.15), (0.19, 0.17), (0.17, 0.155), (0.12, 0.1)], 64, 4)
    parts = [M.assign(M.smooth(bowl), sh.mat)]
    for k in range(3):
        a = math.radians(90 + 120 * k)
        lg = lathe_s(f"{name}Leg{k}", [(0.03, 0.0), (0.035, 0.03), (0.03, 0.07)], 16, 3)
        lg.location = (0.11 * math.cos(a), 0.11 * math.sin(a), 0.0)
        M.apply_transform(lg)
        parts.append(M.assign(M.smooth(lg), sh.mat))
    guac = M.quad_sphere(name + "Guac", 16)
    M.deform(guac, lambda co: Vector((co.x * 0.17, co.y * 0.17, max(co.z, -0.3) * 0.05 + 0.15)))
    M.push_normals(guac, lambda co, n: 0.006 * M.fbm(co * 40))
    gsh = Sh(name + "G", rough=0.4, coat=0.3)
    gsh.color(gsh.mix(gsh.remap(gsh.noise(None, 30.0, 3.0), 0.4, 0.7), (0.46, 0.66, 0.18), (0.66, 0.80, 0.30)))
    parts.append(M.assign(M.smooth(guac), gsh.mat))
    for k, (x, y_, c) in enumerate(((0.05, -0.05, (0.92, 0.18, 0.12)), (-0.06, -0.02, (0.98, 0.96, 0.9)))):
        d = rbox(f"{name}Dice{k}", 0.025, 0.025, 0.02, ceramic(f"{name}DM{k}", c, rough=0.3), bev=0.006, loc=(x, y_, 0.19))
        parts.append(d)
    pest = M.capsule(name + "Pestle", 0.16, 0.035, 16, 12)
    pest.rotation_euler = (0, math.radians(-50), 0)
    pest.location = (0.13, 0.04, 0.2)
    M.apply_transform(pest)
    parts.append(M.assign(M.smooth(pest), sh.mat))
    return parts


def tortillero(name):
    """Корзинка для тортилий: плетеная, с цветными полосками и крышкой."""
    sh = Sh(name + "M", rough=0.55, sheen=0.3)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    weave = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", ang, 30 / (2 * math.pi)),
                                        sh.math("MULTIPLY", sh.math("FLOOR", sh.math("MULTIPLY", z, 60.0)), 0.5)), 0.5)
    col = sh.mix(sh.remap(weave, 0.5, 0.2, 0.0, 0.5), (0.96, 0.84, 0.56), (0.80, 0.62, 0.34))
    bands = sh.math("PINGPONG", sh.math("MULTIPLY", z, 9.0), 0.5)
    stripe = sh.ramp(sh.math("FLOOR", sh.math("MULTIPLY", z, 18.0)), [(0.0, (0.95, 0.28, 0.48)), (0.3, (0.18, 0.62, 0.52)),
                                                                       (0.6, (0.98, 0.72, 0.16)), (1.0, (0.95, 0.28, 0.48))])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(bands, 0.1, 0.05), 0.85), col, stripe)
    sh.color(col)
    sh.bump(weave, 0.3, 0.004)
    body = lathe_s(name, [(0.16, 0.0), (0.17, 0.02), (0.17, 0.09)], 64, 2)
    lid = lathe_s(name + "Lid", [(0.175, 0.085), (0.17, 0.11), (0.12, 0.15), (0.0, 0.16)], 64, 4)
    kn = M.sphere(name + "Kn", 0.025, 16, 8)
    kn.location = (0, 0, 0.17)
    M.apply_transform(kn)
    return [M.assign(M.smooth(body), sh.mat), M.assign(M.smooth(lid), sh.mat), M.assign(M.smooth(kn), sh.mat)]


def dress_mexico(st, kenney, metal_mat):
    """Мексика: плитка бархатцев с поясами талаверы, папель пикадо, кувшин, кактусы, ступка с гуакамоле, лаймы."""
    P = []
    colors = [(0.96, 0.28, 0.56), (1.0, 0.56, 0.12), (1.0, 0.86, 0.20), (0.30, 0.76, 0.36), (0.20, 0.62, 0.92),
              (0.62, 0.36, 0.86)]
    P += bunting("Picado", swags(((-2.6, -0.2), (-0.2, 2.6)), RAIL_Z + 0.04, 0.26, 0.4), colors, kind="picado", n=18)
    P.append(K.s_hook("HookChili", 1.72, metal_mat))
    P += put(K.chili_string("Chili", 0.75), 1.72, 0.40, RAIL_Z - 0.13, s=1.1)
    P += L(cantaro("Jug"), -1.86, 0.26)
    P += put(K.deco_plate("Plate", 0.3, (0.97, 0.94, 0.86), (0.10, 0.24, 0.66)), -1.2, 0.47, LEDGE_TOP + 0.3 * 0.97,
             rx=math.radians(76))
    P += L(glass_jar("Beans", 0.3, 0.1, "beans", 0.72, lid="wood"), -1.24, 0.14)
    P += L(potted_cactus("Cactus", 0.1, 0.2), -0.6, 0.26)
    P += L(vase_flowers("Marigolds", None, (1.0, 0.56, 0.08), "marigold", n=6, vase_mat=talavera_mat("VaseTal")), 0.02, 0.26)
    P += L(glass_jar("Jalapenos", 0.32, 0.1, "pickles", 0.8, lid="metal", lid_col=(0.86, 0.20, 0.16)), 0.6, 0.22)
    P += L(K.terracotta_pot("Pot2", 0.1, 0.16) + put(K.herb_plant("Cilantro", 0.1, 0.16, n=10, seed=21, pot=False), 0, 0, -0.02),
           1.02, 0.26)
    P += L(K.bowl_stack("Bowls", 3, 0.16, 0.1, talavera_mat("BowlTal"), ceramic("BowlRim", (0.10, 0.24, 0.66))), 1.86, 0.24)
    P += Cn(molcajete("Molcajete"), -1.6, -0.2, s=1.25)
    P += Cn(tortillero("Tortillas"), -0.72, -0.15, s=1.1)
    P += Cn(K.fruit_bowl("Limes", (0.97, 0.94, 0.86), (0.10, 0.24, 0.66), kinds=("lime", "lime", "lemon", "lime", "lime")),
            0.12, -0.32)
    P += Cn(prod("avocado", 0.17, rz=0.3), 0.72, -0.4)
    P += Cn(cantaro("Jug2"), 1.12, -0.05, s=0.9)
    P += Cn(potted_cactus("Cactus2", 0.11, 0.3, (1.0, 0.82, 0.2), pot_r=0.12), 1.78, -0.1)
    return P


# MARK: - Пекарня

def copper_mold(name, r=0.13, h=0.1):
    """Медная форма для кугельхопфа: рифленые стенки, трубка в середине."""
    cop = metal(name + "M", (0.94, 0.62, 0.42), rough=0.25)
    ob = shell(name, [(0.03, h), (0.035, 0.0), (r * 0.8, 0.0), (r, h * 0.7), (r * 1.05, h), (r * 0.98, h), (r * 0.9, h * 0.7),
                      (r * 0.75, 0.012), (0.045, 0.012), (0.04, h)], 96, 3)
    M.push_normals(ob, lambda co, n: 0.008 * math.cos(14 * math.atan2(co.y, co.x)) if math.hypot(co.x, co.y) > 0.06 else 0.0)
    M.smooth(ob)
    return [M.assign(ob, cop)]


def hanging_mold(name, r=0.12):
    m = copper_mold(name, r, 0.09)
    put(m, 0, 0, 0, rx=math.radians(80))
    put(m, 0, 0, -r - 0.03)
    return m + [K.hang_ring(name + "Ring", metal(name + "RM", (0.96, 0.54, 0.34), rough=0.22))]


def bread_basket(name):
    bsh = K.straw_sh(name + "W", (0.92, 0.76, 0.48), (0.72, 0.52, 0.28))
    b = shell(name, [(0.14, 0.0), (0.2, 0.03), (0.24, 0.1), (0.25, 0.13), (0.235, 0.13), (0.22, 0.1), (0.13, 0.02)], 64, 3)
    b.scale = (1.0, 0.7, 1.0)
    M.apply_transform(b)
    parts = [M.assign(M.smooth(b), bsh)]
    cloth = K.rbox(name + "Cloth", 0.36, 0.26, 0.02, gingham_mat(name + "G", (0.16, 0.24, 0.52)), bev=0.008, loc=(0, 0, 0.06))
    parts.append(cloth)
    for k, (x, a, zr) in enumerate(((-0.05, 18, 0.0), (0.06, -12, 0.03))):
        bg = prod("baguette", 0.15, rz=math.radians(a))
        put(bg, x, 0.0, 0.08 + zr, rx=math.radians(-25))
        parts += bg
    bl = K.boule(name + "Boule", 0.11, 0.1)
    put(bl, 0.0, -0.06, 0.07)
    return parts + bl


def baguette_crock(name):
    parts = K.crock(name, (0.96, 0.93, 0.86), r=0.12, h=0.24, tools=False)
    for k, (x, a, s) in enumerate(((-0.04, -10, 0.22), (0.03, 8, 0.2), (0.0, 2, 0.24))):
        bg = prod("baguette", s, ry=math.radians(90))
        put(bg, 0, 0, 0, ry=math.radians(a))
        put(bg, x, 0.01 * k, 0.04)
        parts += bg
    return parts


def canister(name, color, lid_col, h=0.3, r=0.11):
    m = ceramic(name + "M", color, rough=0.12)
    body = lathe_s(name, [(r, 0.0), (r, h - 0.02), (r - 0.01, h)], 64, 3)
    lid = lathe_s(name + "Lid", [(r + 0.006, h - 0.01), (r + 0.004, h + 0.02), (r * 0.6, h + 0.04), (0.0, h + 0.045)], 64, 3)
    kn = M.sphere(name + "Kn", 0.022, 16, 8)
    kn.location = (0, 0, h + 0.06)
    M.apply_transform(kn)
    lm = ceramic(name + "L", lid_col, rough=0.15)
    lb = K.label_patch(name + "Lb", r + 0.003, h * 0.35, h * 0.62, 0.6, ceramic(name + "P", (0.99, 0.97, 0.92), rough=0.5,
                                                                                coat=0.0), ink=lid_col)
    return [M.assign(M.smooth(body), m), M.assign(M.smooth(lid), lm), M.assign(M.smooth(kn), lm), lb]


def cake_stand(name, items, plate_col=(0.98, 0.97, 0.94), r=0.26):
    stand = lathe_s(name, [(0.1, 0.0), (0.08, 0.02), (0.03, 0.05), (0.028, 0.12), (0.05, 0.135), (r, 0.14), (r + 0.01, 0.155),
                           (r - 0.01, 0.16), (0.0, 0.16)], 96, 4)
    parts = [M.assign(M.smooth(stand), ceramic(name + "M", plate_col, rough=0.12))]
    for pid, s, x, y, rz in items:
        parts += put(prod(pid, s), x, y, 0.16, rz=rz)
    return parts


def croissant(name, s=1.0):
    """Круассан: сегменты-валики по дуге, к концам тоньше, глянцевая корочка."""
    sh = K.bread_mat(name + "M", (0.86, 0.50, 0.16), (0.98, 0.76, 0.42))
    parts = []
    n = 7
    for k in range(n):
        t = (k - (n - 1) / 2) / ((n - 1) / 2)
        a = t * math.radians(65)
        rr = 0.05 * (1 - 0.6 * abs(t) ** 1.5)
        seg = M.sphere(f"{name}{k}", 1.0, 24, 12)
        seg.scale = (rr * 1.1, rr * 0.9, rr)
        seg.rotation_euler = (0, 0, a)
        seg.location = (0.11 * math.sin(a), -0.11 * math.cos(a) + 0.11, rr * 0.9)
        M.apply_transform(seg)
        parts.append(M.assign(M.smooth(seg), sh.mat))
    return put(parts, 0, 0, 0, s=s)


def dress_bakery(st, kenney, metal_mat):
    """Французская пекарня: медные формы на рейлинге, корзина с багетами, банка муки, тортница с выпечкой, скалка."""
    P = []
    steel = metal("UtensilSteel", (0.90, 0.91, 0.94), rough=0.18)
    handle_m = wood_sh("UtensilHandle", (0.86, 0.58, 0.32), (0.62, 0.36, 0.16), axis="z", scale=6.0, rough=0.35, coat=0.4,
                       rings=6.0, soft=0.3)
    for x, u in ((-0.5, hanging_mold("Mold1", 0.12)), (-0.12, K.whisk_hang("Whisk", steel, handle_m)),
                 (0.26, hanging_mold("Mold2", 0.1)), (0.6, K.ladle("Ladle", steel))):
        P += put(u, x, 0.415, RAIL_Z - 0.16, s=1.15)
        P.append(K.s_hook(f"Hook{x}", x, metal_mat))
    P += L(bread_basket("Basket"), -1.8, 0.26)
    P += L(baguette_crock("Baguettes"), -1.12, 0.24)
    P += L(canister("Flour", (0.98, 0.96, 0.90), (0.08, 0.16, 0.36)), -0.5, 0.24)
    P += L(copper_mold("MoldA", 0.12, 0.1) + put(copper_mold("MoldB", 0.1, 0.08), 0, 0, 0.1), 0.12, 0.26)
    P += L(glass_jar("Sugar", 0.3, 0.1, "sugar", 0.7, lid="metal", lid_col=(0.98, 0.76, 0.36)), 0.68, 0.22)
    P += L(K.plate_stack("Plates", 4, 0.2, ceramic("PlW", (0.99, 0.98, 0.95)), ceramic("PlR", (0.08, 0.16, 0.36))), 1.2, 0.24)
    P += L(K.books("Books", [(0.075, 0.46, (0.10, 0.18, 0.40)), (0.09, 0.5, (0.86, 0.30, 0.24)),
                             (0.07, 0.42, (0.96, 0.80, 0.42))]), 1.8, 0.28)
    P += Cn(K.round_board("Board"), -1.62, rz=math.radians(-8))
    P += put(K.boule("Bread"), -1.7, -0.22, COUNTER_TOP + 0.05 * CS, s=CS)
    P += Cn(RM.rolling_pin("Pin", (0, 0, 0), math.radians(8), L=0.66, r=0.045), -1.5, -0.5)
    P += Cn(cake_stand("Stand", [("canele", 0.13, -0.11, 0.07, 0.0), ("canele", 0.12, 0.11, 0.08, 1.0),
                                 ("madeleine", 0.15, -0.09, -0.11, 0.3), ("madeleine", 0.15, 0.1, -0.1, -0.4)]), -0.62, -0.2)
    cb = K.bowl_obj("CroiBowl", 0.26, 0.1, K.straw_sh("CroiW", (0.92, 0.76, 0.48), (0.72, 0.52, 0.28)))
    croi = [cb]
    for k, (x, y, a) in enumerate(((-0.1, 0.06, 20), (0.1, 0.04, -15), (0.0, -0.1, 5))):
        croi += put(croissant(f"Croi{k}", 1.35), x, y - 0.04, 0.06 + 0.03 * k, rz=math.radians(a))
    P += Cn(croi, 0.2, -0.3)
    P += Cn(teapot("Teapot", (0.99, 0.97, 0.92), (0.08, 0.16, 0.36)), 1.0, -0.15, s=1.1)
    P += Cn(K.crock("Crock", (0.96, 0.93, 0.86)), 1.76, -0.05, s=1.05)
    return P


# MARK: - Хэллоуин

def dress_halloween(st, kenney, metal_mat):
    """Хэллоуин: тыквы-фонари, свечи, паутина, летучие мыши, зелья, котел, конфеты; свет от свечей и тыкв."""
    P = []
    pts = swags(((-2.6, -0.9), (-0.9, 0.9), (0.9, 2.6)), RAIL_Z + 0.02, 0.28, 0.38)
    P += K.string_lights("Lights", pts, 20, bulb=(1.0, 0.50, 0.10), wire=(0.06, 0.05, 0.06), strength=3.5)
    for k, (x, drop, s) in enumerate(((-0.55, 0.22, 1.0), (0.2, 0.34, 0.8), (0.7, 0.18, 0.9))):
        b = bat(f"Bat{k}", s)
        put(b, x, 0.36, RAIL_Z - 0.05 - drop - 0.5 * s)
        P += b
    P += cobweb("WebTop", -2.45, 5.15, 1.0, -88, -2, y=0.52, spokes=7, rings=6)
    P += cobweb("WebShelf", -1.82, LEDGE_TOP - 0.13, 0.42, -90, -8, y=0.45, spokes=5, rings=4)
    P += cobweb("WebRight", 2.42, LEDGE_TOP + 0.02, 0.5, 92, 178, y=0.5, spokes=5, rings=4)
    P += L(jack_o_lantern("Jack1", 0.2, 0.3), -1.85, 0.24)
    P += L(potion("Potion1", (0.40, 0.95, 0.30), "flask", 0.3), -1.3, 0.22)
    P += L(potion("Potion2", (0.70, 0.30, 0.95), "tall", 0.36), -1.04, 0.28)
    P += L(potion("Potion3", (1.0, 0.50, 0.10), "drop", 0.24), -0.82, 0.18)
    P += L(K.candle("Candle1", 0.04, 0.2, wax=(0.94, 0.90, 0.80), glass=False), -0.4, 0.24)
    P += L(K.candle("Candle2", 0.035, 0.13, wax=(0.94, 0.90, 0.80), glass=False), -0.28, 0.3)
    P += L(ribbed("Pump1", 0.1, 0.14, (0.96, 0.94, 0.88), ribs=8, depth=0.07), 0.2, 0.26)
    P += L(ribbed("Pump2", 0.08, 0.11, (0.98, 0.56, 0.12), ribs=8, depth=0.07), 0.42, 0.18)
    P += L(K.books("Books", [(0.08, 0.46, (0.30, 0.16, 0.36)), (0.09, 0.42, (0.20, 0.30, 0.22)),
                             (0.07, 0.4, (0.46, 0.22, 0.12))]), 1.0, 0.28)
    P += L(K.candle("Candle3", 0.045, 0.16, wax=(0.94, 0.90, 0.80), glass=True), 1.42, 0.24)
    P += L(jack_o_lantern("Jack2", 0.16, 0.24, teeth=False), 1.88, 0.24)
    P += Cn(cauldron("Cauldron"), -1.6, -0.15, s=1.05)
    P += Cn(candy_bowl("Candy", (0.16, 0.10, 0.18), (0.98, 0.50, 0.08),
                       [(0.98, 0.50, 0.08), (0.70, 0.30, 0.95), (0.40, 0.90, 0.30), (0.95, 0.20, 0.30)]), -0.62, -0.3)
    P += Cn(ribbed("Pump3", 0.17, 0.24, (0.98, 0.52, 0.08), ribs=10, depth=0.08), 0.22, -0.2)
    P += Cn(ribbed("Pump4", 0.1, 0.14, (0.42, 0.56, 0.30), ribs=8, depth=0.06), 0.5, -0.4)
    P += Cn(K.candle("Candle4", 0.05, 0.22, glass=False), 0.95, -0.15)
    P += Cn(K.candle("Candle5", 0.045, 0.14, glass=False), 1.12, -0.3)
    P += Cn(jack_o_lantern("Jack3", 0.19, 0.28), 1.72, -0.15)
    return P


# MARK: - Осень

def maple_leaf(name, size, color):
    pts = []
    for i in range(80):
        a = 2 * math.pi * i / 80
        lob = abs(math.cos(2.5 * (a - math.pi / 2))) ** 0.6
        tooth = 0.06 * max(0.0, math.cos(15 * (a - math.pi / 2)))
        rr = size * (0.45 + 0.55 * lob + tooth)
        if math.sin(a) < -0.7:
            rr *= 0.55
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    ob = I.slab(name, I.ccw(pts), 0.008, 0.003, ceramic(name + "M", color, rough=0.45, coat=0.3, mottle=0.12))
    st = EV.sweep(name + "St", [(0.0, -0.003, -size * 0.4), (0.0, -0.003, -size * 1.3)], 0.004, segs=6)
    return [ob, M.assign(st, ceramic(name + "StM", I.shade(color, 0.6), rough=0.6, coat=0.0))]


def leaf_garland(name, pts, n=24, seed=4):
    rnd = random.Random(seed)
    parts = [M.assign(EV.sweep(name + "Twine", EV.spline(pts, 8), 0.007, segs=8),
                      ceramic(name + "TwM", (0.80, 0.66, 0.42), rough=0.7, coat=0.0, mottle=0.0))]
    cols = [(0.90, 0.24, 0.10), (0.98, 0.56, 0.10), (0.96, 0.78, 0.22), (0.70, 0.30, 0.10), (0.82, 0.40, 0.08)]
    for k, p in enumerate(along(pts, n)):
        lf = maple_leaf(f"{name}L{k}", rnd.uniform(0.075, 0.1), cols[k % len(cols)])
        put(lf, 0, 0, 0, ry=math.radians(rnd.uniform(130, 230)))
        put(lf, p.x, p.y - 0.01, p.z - 0.1)
        parts += lf
    return parts


def apple_crate(name):
    wm = wood_sh(name + "W", (0.86, 0.62, 0.38), (0.64, 0.40, 0.20), axis="x", scale=4.0, rough=0.55, coat=0.1, soft=0.3)
    W, D, H = 0.56, 0.36, 0.22
    parts = [rbox(name + "Bottom", W, D, 0.02, wm, bev=0.006)]
    for k, z in enumerate((0.03, 0.12)):
        for y_ in (-D / 2 + 0.01, D / 2 - 0.01):
            parts.append(rbox(f"{name}S{k}{y_}", W, 0.02, 0.07, wm, bev=0.008, loc=(0, y_, z)))
    for x in (-W / 2 + 0.015, W / 2 - 0.015):
        parts.append(rbox(f"{name}E{x}", 0.03, D, H, wm, bev=0.008, loc=(x, 0, 0)))
    rnd = random.Random(3)
    for k in range(9):
        x = -0.18 + 0.18 * (k % 3) + rnd.uniform(-0.02, 0.02)
        y_ = -0.1 + 0.1 * (k // 3) + rnd.uniform(-0.02, 0.02)
        parts += M3fruit(f"{name}A{k}", "apple", (x, y_, 0.14 + 0.03 * (k % 2)), 0.085)
    for k, (x, y_) in enumerate(((-0.08, -0.04), (0.1, 0.02))):
        parts += M3fruit(f"{name}T{k}", "apple", (x, y_, 0.27), 0.085)
    return parts


def M3fruit(name, kind, loc, r):
    import models_match3 as M3
    return M3.fruit(name, kind, loc, r)


def pie_plate(name):
    parts = [K.plate_obj(name + "Plate", 0.28, ceramic(name + "P", (0.98, 0.96, 0.90)), ceramic(name + "R", (0.86, 0.36, 0.14)))]
    parts += put(prod("pie", 0.22, rx=math.radians(-30)), 0, 0, 0.03)
    return parts


def jug(name, color, ink):
    m = K.patterned_ceramic(name + "M", color, ink, "bands", 0.0, 0.34)
    body = lathe_s(name, [(0.09, 0.0), (0.12, 0.05), (0.12, 0.2), (0.08, 0.28), (0.06, 0.32), (0.07, 0.34)], 64, 4)
    hd = EV.sweep(name + "Hd", EV.spline([(0.06, 0.0, 0.3), (0.15, 0.0, 0.3), (0.15, 0.0, 0.18), (0.11, 0.0, 0.12)], 6), 0.016,
                  segs=12)
    return [M.assign(M.smooth(body), m), M.assign(hd, m)]


def dress_autumn(st, kenney, metal_mat):
    """Осенний урожай: гирлянда кленовых листьев, варенье в банках, тыквы и тыквочки, ящик яблок, яблочный пирог."""
    P = []
    P += leaf_garland("Leaves", swags(((-2.6, -0.9), (-0.9, 0.9), (0.9, 2.6)), RAIL_Z + 0.02, 0.24, 0.4), n=34)
    jams = (("Jam", "jam", (0.86, 0.16, 0.18)), ("Marm", "marmalade", (0.98, 0.62, 0.14)), ("Plum", "plum", (0.52, 0.22, 0.46)))
    for k, (nm, kind, cloth) in enumerate(jams):
        P += L(glass_jar(nm, 0.24 + 0.03 * (k % 2), 0.09, kind, 0.8, lid=None, cloth=cloth), -1.95 + 0.3 * k, 0.2 + 0.05 * (k % 2))
    P += L(ribbed("Pumpkin", 0.17, 0.22, (0.98, 0.52, 0.10), ribs=10, depth=0.08), -0.62, 0.26)
    P += L(ribbed("WhitePump", 0.1, 0.13, (0.96, 0.94, 0.86), ribs=8, depth=0.07), -0.28, 0.2)
    P += L(ribbed("Gourd", 0.07, 0.2, (0.96, 0.80, 0.22), ribs=8, depth=0.04, stripes=(0.30, 0.56, 0.24)), 0.0, 0.24)
    P += L(glass_jar("Honey", 0.28, 0.1, "marmalade", 0.85, lid="wood"), 0.5, 0.22)
    P += L(K.candle("Candle", 0.045, 0.15), 0.92, 0.24)
    P += L(jug("Cider", (0.96, 0.92, 0.82), (0.60, 0.26, 0.10)), 1.32, 0.24)
    P += L(K.books("Books", [(0.075, 0.46, (0.56, 0.20, 0.12)), (0.09, 0.5, (0.86, 0.60, 0.20)),
                             (0.07, 0.42, (0.22, 0.38, 0.24))]), 1.86, 0.28)
    P += Cn(apple_crate("Crate"), -1.55, -0.1)
    P += Cn(pie_plate("Pie"), -0.58, -0.3)
    P += Cn(ribbed("Pump2", 0.15, 0.2, (0.96, 0.58, 0.14), ribs=10, depth=0.08), 0.22, -0.15)
    P += Cn(ribbed("Gourd2", 0.08, 0.12, (0.40, 0.58, 0.26), ribs=8, depth=0.05, stripes=(0.94, 0.86, 0.50)), 0.48, -0.42)
    for k, (x, y_, a, c) in enumerate(((0.75, -0.5, 30, (0.90, 0.24, 0.10)), (-0.95, -0.55, -60, (0.98, 0.56, 0.10)),
                                       (1.35, -0.52, 100, (0.96, 0.78, 0.22)))):
        lf = maple_leaf(f"Fallen{k}", 0.07, c)
        put(lf, 0, 0, 0, rx=math.radians(-80))
        P += Cn(lf, x, y_, rz=math.radians(a))
    P += Cn(K.kettle("Kettle", (0.20, 0.42, 0.30), handle_col=(0.15, 0.12, 0.1)), 1.0, -0.12, rz=math.radians(-10))
    P += Cn(K.crock("Crock", (0.96, 0.92, 0.84)), 1.76, -0.05, s=1.05)
    return P


# MARK: - Сладости

def lollipop(name, r, colors):
    sh = Sh(name + "M", rough=0.08, coat=1.0)
    x, y, z = sh.xyz()
    rad = sh.vmath("LENGTH", sh.combine(x, sh.math("SUBTRACT", z, 0.0), 0.0))
    ang = sh.math("ARCTAN2", z, x)
    sw = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", rad, 60.0 / (r / 0.07)), ang), 0.5)
    sh.color(sh.mix(sh.math("GREATER_THAN", sw, 0.25), colors[0], colors[1]))
    disc = I.slab(name, [(r * math.cos(2 * math.pi * i / 48), r * math.sin(2 * math.pi * i / 48)) for i in range(48)], 0.03,
                  0.012, sh.mat)
    stick = M.cylinder(name + "St", 0.006, 0.26, 12)
    stick.location = (0, 0, -0.13 - r * 0.9)
    M.apply_transform(stick)
    parts = [disc, M.assign(stick, ceramic(name + "StM", (0.99, 0.98, 0.95), rough=0.4, coat=0.2, mottle=0.0))]
    put(parts, 0, 0, 0.26 + r * 0.9)
    return parts


def lollipop_jar(name):
    parts = glass_jar(name, 0.18, 0.1, "gumballs", 0.85, lid=None, label=False)
    cols = [((0.98, 0.46, 0.66), (0.99, 0.97, 0.95)), ((0.50, 0.80, 0.98), (0.99, 0.97, 0.95)),
            ((1.0, 0.82, 0.30), (0.98, 0.46, 0.66)), ((0.62, 0.90, 0.70), (0.80, 0.56, 0.96))]
    for k, (x, a, r) in enumerate(((-0.04, -14, 0.07), (0.04, 12, 0.065), (0.0, 2, 0.075), (0.02, -4, 0.06))):
        lp = lollipop(f"{name}L{k}", r, cols[k])
        put(lp, 0, 0, 0, ry=math.radians(a), rz=math.radians(10 * k))
        put(lp, x, 0.01 * k, 0.04 + 0.03 * k)
        parts += lp
    return parts


def macaron(name, color, r=0.045):
    """Макарун: две гладкие крышечки с "юбочкой" и светлая начинка."""
    m = ceramic(name + "M", color, rough=0.45, coat=0.2, mottle=0.03)
    parts = []
    for k, z in enumerate((0.016, 0.05)):
        sh_ = M.sphere(f"{name}S{k}", 1.0, 32, 16)
        sh_.scale = (r, r, 0.017)
        sh_.location = (0, 0, z)
        M.apply_transform(sh_)
        parts.append(M.assign(M.smooth(sh_), m))
    fill = M.cylinder(name + "F", r * 0.9, 0.016, 32)
    fill.location = (0, 0, 0.033)
    M.apply_transform(fill)
    M.bevel(fill, 0.005, 2, 30)
    parts.append(M.assign(M.smooth(fill, 30), ceramic(name + "FM", (0.99, 0.96, 0.92), rough=0.4)))
    return parts


def macaron_plate(name, colors):
    parts = [K.plate_obj(name, 0.22, ceramic(name + "P", (0.99, 0.98, 0.96)), ceramic(name + "R", (0.98, 0.70, 0.80)))]
    spots = [(-0.09, 0.04, 0.0), (0.0, 0.07, 0.0), (0.09, 0.03, 0.0), (-0.05, -0.06, 0.0), (0.05, -0.05, 0.0),
             (-0.04, 0.02, 0.05), (0.05, 0.02, 0.05), (0.0, -0.01, 0.1)]
    for k, (x, y_, z) in enumerate(spots):
        mc = macaron(f"{name}M{k}", colors[k % len(colors)])
        put(mc, 0, 0, 0, rx=math.radians(-25 if z else 0))
        parts += put(mc, x, y_, 0.035 + z)
    return parts


def cupcake_stand(name):
    m = ceramic(name + "M", (0.99, 0.97, 0.96), rough=0.12)
    rim = ceramic(name + "R", (0.98, 0.62, 0.74), rough=0.12)
    parts = []
    for k, (r, z) in enumerate(((0.26, 0.0), (0.17, 0.3))):
        p = K.plate_obj(f"{name}P{k}", r, m, rim)
        put([p], 0, 0, z + 0.02)
        parts.append(p)
    rod = M.cylinder(name + "Rod", 0.012, 0.42, 16)
    rod.location = (0, 0, 0.21)
    M.apply_transform(rod)
    parts.append(M.assign(rod, metal(name + "Gold", (0.98, 0.78, 0.40), rough=0.2)))
    ball = M.sphere(name + "Ball", 0.025, 16, 8)
    ball.location = (0, 0, 0.44)
    M.apply_transform(ball)
    parts.append(M.assign(ball, metal(name + "Gold2", (0.98, 0.78, 0.40), rough=0.2)))
    for k, (x, y_, z) in enumerate(((-0.15, -0.04, 0.05), (0.15, -0.04, 0.05), (0.0, 0.12, 0.05), (-0.07, -0.1, 0.35))):
        parts += put(prod("cupcake", 0.13), x, y_, z, rz=k)
    return parts


def dress_sweets(st, kenney, metal_mat):
    """Неделя сладостей: пастельные флажки, банки с конфетами, леденцы, макаруны, капкейки на подставке."""
    P = []
    pastel = [(0.98, 0.62, 0.74), (0.62, 0.86, 0.98), (1.0, 0.90, 0.56), (0.70, 0.92, 0.76), (0.84, 0.72, 0.98)]
    P += bunting("Flags", swags(((-2.6, -0.9), (-0.9, 0.9), (0.9, 2.6)), RAIL_Z + 0.03, 0.22, 0.4), pastel, n=24)
    P += L(glass_jar("Gum", 0.36, 0.12, "gumballs", 0.8, lid="metal", lid_col=(0.98, 0.62, 0.74)), -1.92, 0.22)
    P += L(glass_jar("Candy", 0.28, 0.1, "candy", 0.8, lid="metal", lid_col=(0.62, 0.86, 0.98)), -1.55, 0.26)
    P += L(lollipop_jar("Lolli"), -1.1, 0.22)
    P += L(macaron_plate("Macarons", pastel), -0.42, 0.24)
    P += L(prod("donut", 0.12) + put(prod("donut", 0.12, rz=1.0), 0, 0, 0.065), 0.2, 0.24)
    P += L(cake_stand("Mini", [("cupcake", 0.13, 0.0, 0.0, 0.0)], (0.99, 0.97, 0.96), r=0.14), 0.68, 0.24)
    P += L(prod("cotton_candy", 0.2), 1.18, 0.24)
    P += L(K.plate_stack("Plates", 4, 0.18, ceramic("PlW", (0.99, 0.98, 0.96)), ceramic("PlR", (0.70, 0.92, 0.76))), 1.62, 0.24)
    P += L(vase_flowers("Daisies", (0.98, 0.62, 0.74), (0.99, 0.98, 0.96), "daisy", n=5, seed=5), 1.98, 0.26)
    P += Cn(cupcake_stand("Stand"), -1.55, -0.15)
    P += Cn(macaron_plate("Macarons2", pastel[::-1]), -0.62, -0.32)
    P += Cn(candy_bowl("Bowl", (0.99, 0.98, 0.96), (0.98, 0.62, 0.74), pastel), 0.18, -0.32)
    P += Cn(tea_set("Tea", (0.99, 0.97, 0.96), (0.98, 0.56, 0.70)), 1.05, -0.15, s=1.05)
    P += Cn(lollipop_jar("Lolli2"), 1.8, -0.1, s=1.15)
    return P


# MARK: - Барбекю

def tongs(name, steel):
    parts = [K.hang_ring(name + "Ring", steel)]
    for s_ in (-1, 1):
        pts = [(s_ * (0.008 + 0.03 * (t / 10) ** 1.5), 0.0, -0.02 - 0.5 * t / 10) for t in range(11)]
        arm = EV.sweep(f"{name}A{s_}", pts, 0.012, segs=8, section=(1.0, 0.35), up=(0, -1, 0))
        parts.append(M.assign(arm, steel))
        tip = rbox(f"{name}T{s_}", 0.03, 0.02, 0.07, steel, bev=0.006, loc=(s_ * 0.042, 0.0, -0.56))
        parts.append(tip)
    grip = M.capsule(name + "Grip", 0.14, 0.02, 16, 8)
    grip.rotation_euler = (0, math.radians(90), 0)
    grip.location = (0, 0, -0.1)
    M.apply_transform(grip)
    grip.scale = (1.6, 0.8, 1.0)
    M.apply_transform(grip)
    parts.append(M.assign(M.smooth(grip), ceramic(name + "G", (0.12, 0.10, 0.10), rough=0.4, coat=0.3, mottle=0.0)))
    return parts


def bbq_fork(name, steel, handle_m):
    hd = lathe_s(name + "H", [(0.014, -0.02), (0.022, -0.04), (0.022, -0.2), (0.016, -0.22)], 24, 3)
    shaft = EV.sweep(name + "Sh", [(0.0, 0.0, -0.21), (0.0, 0.0, -0.42)], 0.008, segs=8)
    parts = [M.assign(M.smooth(hd), handle_m), M.assign(shaft, steel), K.hang_ring(name + "Ring", steel)]
    for s_ in (-1, 1):
        pr = EV.sweep(f"{name}P{s_}", EV.spline([(0.0, 0.0, -0.41), (s_ * 0.03, 0.0, -0.45), (s_ * 0.03, 0.0, -0.6)], 5), 0.006,
                      segs=8)
        parts.append(M.assign(pr, steel))
    return parts


def basting_brush(name, steel, handle_m):
    hd = lathe_s(name + "H", [(0.014, -0.02), (0.02, -0.05), (0.018, -0.3), (0.024, -0.32)], 24, 3)
    fer = rbox(name + "Fe", 0.07, 0.03, 0.05, steel, bev=0.008, loc=(0.0, 0.0, -0.37))
    bsh = Sh(name + "Br", rough=0.8)
    bsh.color(bsh.mix(bsh.remap(bsh.noise(bsh.mapping(None, scale=(80, 80, 2)), 3.0, 2.0), 0.3, 0.7), (0.92, 0.84, 0.66), (0.70, 0.56, 0.36)))
    br = rbox(name + "Bristle", 0.065, 0.025, 0.1, bsh.mat, bev=0.008, loc=(0.0, 0.0, -0.47))
    return [M.assign(M.smooth(hd), handle_m), fer, br, K.hang_ring(name + "Ring", steel)]


def sauce_bottle(name, sauce, label_ink, h=0.36, r=0.065):
    gl = lathe_s(name, [(r * 0.9, 0.0), (r, 0.02), (r, h * 0.55), (r * 0.6, h * 0.7), (r * 0.36, h * 0.82), (r * 0.36, h)],
                 48, 4)
    M.assign(M.smooth(gl), glass_mat(name + "G", tint=(0.96, 0.92, 0.88)))
    gl.visible_shadow = False
    fl = lathe_s(name + "F", [(r * 0.86, 0.01), (r - 0.008, 0.03), (r - 0.008, h * 0.5), (r * 0.58, h * 0.66),
                              (r * 0.3, h * 0.78), (0.0, h * 0.79)], 48, 3)
    M.assign(M.smooth(fl), I.toy(name + "S", sauce, rough=0.1, coat=0.8))
    cap = M.cylinder(name + "Cap", r * 0.42, 0.05, 24)
    cap.location = (0, 0, h + 0.015)
    M.apply_transform(cap)
    M.bevel(cap, 0.006, 2, 30)
    lb = K.label_patch(name + "Lb", r + 0.004, h * 0.14, h * 0.42, 0.75, ceramic(name + "P", (0.99, 0.95, 0.84), rough=0.5,
                                                                                  coat=0.0), ink=label_ink)
    return [gl, fl, M.assign(M.smooth(cap, 30), ceramic(name + "CapM", label_ink, rough=0.3)), lb]


def skillet(name, r=0.22):
    iron = K.iron_mat(name + "I", (0.14, 0.13, 0.13))
    pan = shell(name, [(r * 0.8, 0.0), (r, 0.01), (r * 1.05, 0.06), (r * 1.08, 0.07), (r * 1.03, 0.07), (r * 0.97, 0.02),
                       (r * 0.8, 0.012)], 64, 3)
    hd = rbox(name + "Hd", 0.24, 0.05, 0.03, iron, bev=0.012, loc=(r * 1.0 + 0.12, 0.0, 0.035))
    hole = M.cylinder(name + "Hole", 0.012, 0.2, 16)
    hole.location = (r + 0.2, 0.0, 0.05)
    M.apply_transform(hole)
    M.boolean_cut(hd, [hole])
    M.smooth(hd, 30)
    return [M.assign(M.smooth(pan), iron), hd]


def checked_towel(name, x0, x1, color):
    """Клетчатое полотенце перекинуто через переднюю кромку полки и свисает складками."""
    top, front_y = LEDGE_TOP, 0.25 - 0.32 - 0.006

    def fn(u, v):
        x = x0 + (x1 - x0) * u
        fold = 0.012 * math.sin(2 * math.pi * u * 3.0 + 0.6)
        if v < 0.35:
            t = v / 0.35
            return Vector((x, 0.12 - (0.12 - front_y) * t, top + 0.006 + fold * 0.2))
        if v < 0.45:
            t = (v - 0.35) / 0.1
            a = math.pi / 2 * t
            return Vector((x, front_y - 0.02 * math.sin(a), top + 0.006 - 0.02 * (1 - math.cos(a)) * 3))
        t = (v - 0.45) / 0.55
        return Vector((x + fold * t * 0.5, front_y - 0.02 - fold * t * 1.5 - 0.01 * t, top - 0.05 - 0.36 * t))
    ob = RM.surface(name, 30, 40, fn)
    M.solidify(ob, 0.008)
    M.smooth(ob)
    return [M.assign(ob, gingham_mat(name + "M", color, 7.0))]


def dress_bbq(st, kenney, metal_mat):
    """Барбекю: кирпичная стена, щипцы, вилка и кисточка на рейлинге, соусы, специи, чугунная сковорода, кукуруза."""
    P = []
    steel = metal("ToolSteel", (0.88, 0.89, 0.92), rough=0.2)
    hm = wood_sh("ToolHandle", (0.62, 0.38, 0.20), (0.40, 0.22, 0.10), axis="z", scale=6.0, rough=0.4, coat=0.4, rings=6.0,
                 soft=0.3)
    for x, u in ((-0.5, tongs("Tongs", steel)), (-0.12, K.turner("Turner", steel, hm)), (0.26, bbq_fork("Fork", steel, hm)),
                 (0.6, basting_brush("Brush", steel, hm))):
        P += put(u, x, 0.415, RAIL_Z - 0.16, s=1.15)
        P.append(K.s_hook(f"Hook{x}", x, metal_mat))
    P += L(sauce_bottle("BBQ", (0.36, 0.12, 0.06), (0.20, 0.10, 0.06)), -1.95, 0.24)
    P += L(sauce_bottle("Hot", (0.86, 0.14, 0.06), (0.86, 0.14, 0.06), h=0.28, r=0.045), -1.72, 0.28)
    P += L(K.squeeze_bottle("Ketchup", (0.88, 0.12, 0.10)), -1.42, 0.24)
    P += L(K.squeeze_bottle("Mustard", (1.0, 0.76, 0.12)), -1.22, 0.28)
    for k, kind in enumerate(("paprika", "pepper", "herbs")):
        P += L(glass_jar(f"Spice{k}", 0.16, 0.06, kind, 0.8, lid="metal", lid_col=(0.20, 0.18, 0.18), label=k != 1),
               -0.66 + 0.17 * k, 0.24 - 0.04 * (k % 2))
    P += L(glass_jar("Pickles", 0.32, 0.1, "pickles", 0.85, lid="metal", lid_col=(0.86, 0.80, 0.30)), 0.3, 0.22)
    P += checked_towel("Towel", 0.62, 0.98, (0.80, 0.10, 0.10))
    pan = put(skillet("PanWall", 0.2), 0.0, 0.0, 0.0, rx=math.radians(78))
    P += put(pan, 1.36, 0.5, LEDGE_TOP + 0.21 * K.LS, s=K.LS)
    corn_board = K.round_board("Board", 0.32)
    for k, (x, y_, a) in enumerate(((-0.06, 0.06, 15), (0.06, -0.02, -10), (0.0, -0.1, 5))):
        corn_board += put(prod("corn", 0.12, rz=math.radians(90)), x, y_, 0.05 + 0.03 * k, rz=math.radians(a))
    P += Cn(corn_board, -1.55, -0.22)
    P += Cn(skillet("Skillet") + put(prod("sausage", 0.13), 0.0, 0.0, 0.02), -0.55, -0.25, rz=math.radians(-15))
    P += Cn(sauce_bottle("BBQ2", (0.36, 0.12, 0.06), (0.20, 0.10, 0.06)), 0.32, -0.1)
    P += Cn([K.rbox("Napkin", 0.36, 0.3, 0.02, gingham_mat("NapM", (0.80, 0.10, 0.10)), bev=0.008)]
            + put(K.boule("Bun", 0.12, 0.1), -0.06, 0.0, 0.02) + put(K.boule("Bun2", 0.11, 0.09), 0.08, -0.04, 0.02), 1.0, -0.3)
    P += Cn(shaker("Salt", "sugar"), 1.66, -0.1)
    P += Cn(shaker("Pepper", "pepper"), 1.86, -0.04)
    return P


def shaker(name, kind):
    """Солонка или перечница: стекло с содержимым, стальная крышечка с дырочками."""
    gl = lathe_s(name, [(0.04, 0.0), (0.045, 0.01), (0.045, 0.12), (0.04, 0.13)], 32, 3)
    M.assign(M.smooth(gl), glass_mat(name + "G"))
    gl.visible_shadow = False
    fl = lathe_s(name + "F", [(0.036, 0.008), (0.038, 0.08), (0.0, 0.082)], 24, 2)
    M.assign(M.smooth(fl), K.fill_mat(name + "FM", kind))
    cap = lathe_s(name + "Cap", [(0.042, 0.125), (0.044, 0.15), (0.03, 0.175), (0.0, 0.18)], 32, 3)
    sh = Sh(name + "Steel", rough=0.2, metal=1.0, coat=0.3)
    sh.color((0.90, 0.91, 0.94))
    x, y, z = sh.xyz()
    holes = sh.remap(sh.voronoi(sh.mapping(None, scale=(1, 1, 1)), 60.0, out="Distance", rand=0.0), 0.12, 0.08)
    sh.color(sh.mix(sh.math("MULTIPLY", holes, sh.remap(z, 0.16, 0.17)), (0.90, 0.91, 0.94), (0.15, 0.15, 0.16)))
    return [gl, fl, M.assign(M.smooth(cap), sh.mat)]


# MARK: - Гурман

def wine_bottle(name, glass=(0.12, 0.26, 0.16), foil=(0.56, 0.08, 0.14), label=(0.98, 0.95, 0.86)):
    body = lathe_s(name, [(0.06, 0.0), (0.072, 0.01), (0.072, 0.24), (0.065, 0.29), (0.03, 0.35), (0.024, 0.42), (0.026, 0.46)],
                   48, 5)
    M.assign(M.smooth(body), I.toy(name + "G", glass, rough=0.06, coat=1.0))
    foil_ = lathe_s(name + "Foil", [(0.027, 0.38), (0.028, 0.46), (0.0, 0.463)], 32, 2)
    lb = K.label_patch(name + "Lb", 0.075, 0.08, 0.19, 0.7, ceramic(name + "P", label, rough=0.5, coat=0.0), ink=(0.40, 0.30, 0.16))
    return [body, M.assign(M.smooth(foil_), metal(name + "F", foil, rough=0.3)), lb]


def wine_glass(name, wine=(0.50, 0.04, 0.10)):
    gl = lathe_s(name, [(0.06, 0.0), (0.05, 0.006), (0.008, 0.015), (0.007, 0.12), (0.03, 0.14), (0.055, 0.19), (0.05, 0.26)],
                 48, 4)
    M.assign(M.smooth(gl), glass_mat(name + "G"))
    gl.visible_shadow = False
    fl = lathe_s(name + "W", [(0.012, 0.13), (0.035, 0.145), (0.05, 0.18), (0.0, 0.182)], 32, 3)
    return [gl, M.assign(M.smooth(fl), I.toy(name + "Wine", wine, rough=0.05, coat=1.0))]


def candlestick(name, h=0.22):
    brass = metal(name + "B", (0.98, 0.76, 0.36), rough=0.2)
    st = lathe_s(name, [(0.07, 0.0), (0.06, 0.02), (0.02, 0.05), (0.025, 0.09), (0.016, 0.14), (0.03, h - 0.02), (0.045, h)],
                 48, 4)
    parts = [M.assign(M.smooth(st), brass)]
    parts += put(K.candle(name + "C", 0.022, 0.22, wax=(0.99, 0.97, 0.92), glass=False), 0, 0, h - 0.005)
    return parts


def cloche(name):
    silver = metal(name + "S", (0.92, 0.93, 0.95), rough=0.12)
    platter = K.plate_obj(name + "Pl", 0.3, silver)
    dome = lathe_s(name + "Dome", [(0.26, 0.04), (0.26, 0.06), (0.24, 0.14), (0.18, 0.22), (0.08, 0.26), (0.0, 0.265)], 96, 5)
    kn = lathe_s(name + "Kn", [(0.02, 0.26), (0.015, 0.29), (0.04, 0.31), (0.0, 0.33)], 32, 3)
    return [platter, M.assign(M.smooth(dome), silver), M.assign(M.smooth(kn), metal(name + "K", (0.98, 0.76, 0.36), rough=0.2))]


def hanging_pan(name, r=0.13):
    cop = metal(name + "C", (0.96, 0.54, 0.34), rough=0.22, hammered=0.15)
    pan = shell(name, [(r * 0.9, 0.0), (r, 0.01), (r, 0.09), (r * 1.03, 0.1), (r * 0.96, 0.1), (r * 0.96, 0.012)], 64, 3)
    hd = EV.sweep(name + "Hd", [(r * 0.95, 0.0, 0.08), (r + 0.3, 0.0, 0.1)], 0.015, segs=10, section=(1.0, 0.6))
    parts = [M.assign(M.smooth(pan), cop), M.assign(hd, metal(name + "B", (0.98, 0.76, 0.36), rough=0.2))]
    put(parts, 0, 0, 0, rx=math.radians(90))
    put(parts, 0, 0, 0, ry=math.radians(-90))
    put(parts, 0, 0, -(r + 0.32))
    return parts + [K.hang_ring(name + "Ring", metal(name + "R", (0.98, 0.76, 0.36), rough=0.2))]


def dress_gourmet(st, kenney, metal_mat):
    """Гурман: темно-зеленая плитка с золотой затиркой, медные сотейники, вино, фарфор с золотом, свечи, клош."""
    P = []
    steel = metal("UtensilSteel", (0.90, 0.91, 0.94), rough=0.18)
    for x, u in ((-0.55, hanging_pan("Pan1", 0.13)), (-0.1, K.ladle("Ladle", steel)), (0.38, hanging_pan("Pan2", 0.11))):
        P += put(u, x, 0.415, RAIL_Z - 0.16, s=1.1)
        P.append(K.s_hook(f"Hook{x}", x, metal_mat))
    for k, (x, g) in enumerate(((-1.98, (0.12, 0.26, 0.16)), (-1.78, (0.30, 0.08, 0.10)), (-1.58, (0.12, 0.26, 0.16)))):
        P += L(wine_bottle(f"Wine{k}", g, foil=((0.56, 0.08, 0.14) if k != 1 else (0.86, 0.68, 0.30))), x, 0.24 + 0.04 * (k % 2))
    gold = metal("ChinaGold", (0.98, 0.78, 0.40), rough=0.2)
    P += put(K.deco_plate("Plate", 0.3, (0.99, 0.98, 0.96), (0.80, 0.62, 0.30)), -1.05, 0.47, LEDGE_TOP + 0.3 * 0.97,
             rx=math.radians(76))
    P += L(K.plate_stack("China", 4, 0.2, ceramic("ChinaW", (0.99, 0.98, 0.96)), gold), -0.95, 0.16)
    P += L(cup_saucer("Cup1", (0.99, 0.98, 0.96), (0.86, 0.68, 0.30)), -0.4, 0.22)
    P += L(K.herb_plant("Rosemary", 0.1, 0.16, n=12, size=0.8, seed=31, kind="blades"), 0.12, 0.26)
    P += L(candlestick("Candle1"), 0.6, 0.24)
    P += L(wine_glass("Glass1"), 0.95, 0.22)
    P += L(wine_glass("Glass2"), 1.12, 0.28)
    P += L(K.books("Books", [(0.08, 0.46, (0.10, 0.22, 0.16)), (0.09, 0.5, (0.36, 0.08, 0.10)),
                             (0.07, 0.44, (0.12, 0.12, 0.14))]), 1.62, 0.28)
    P += L(candlestick("Candle2", 0.18), 2.0, 0.24)
    P += Cn(cloche("Cloche"), -1.55, -0.2)
    P += Cn(K.round_board("Board", 0.3, wood=((0.70, 0.46, 0.26), (0.46, 0.28, 0.14)))
            + put(K.cheese_wheel("Cheese", 0.14, 0.09), -0.04, 0.02, 0.05) + put(prod("grapes", 0.12), 0.14, -0.06, 0.05),
            -0.55, -0.25)
    P += Cn(wine_glass("Glass3"), 0.18, -0.3, s=1.1)
    P += Cn(wine_bottle("Wine3", (0.30, 0.08, 0.10), foil=(0.86, 0.68, 0.30)), 0.42, -0.1)
    P += Cn(candlestick("Candle3"), 0.98, -0.2)
    P += Cn(candlestick("Candle4", 0.16), 1.16, -0.05)
    P += Cn(K.herb_plant("Thyme", 0.12, 0.2, n=14, size=0.8, seed=8), 1.76, -0.08)
    return P


# MARK: - Персик и лаванда: кухня по умолчанию со своими мелочами

def dress_shop(st, kenney, metal_mat, flowers, flower_col, tea_col, tea_ink):
    P = K.dress_kitchen(dict(st, generic=True), kenney, metal_mat)
    # вместо бутылки масла - ваза с цветами, вместо чайника - чайный сервиз
    drop = {"Oil", "Kettle"}
    keep = []
    for o in P:
        base = o.name.split(".")[0]
        if any(base.startswith(d) for d in drop):
            bpy.data.objects.remove(o)
        else:
            keep.append(o)
    vase = (0.99, 0.97, 0.95)
    keep += L(vase_flowers("Vase", vase, flower_col, flowers, n=6, seed=9), 0.66, 0.24)
    keep += Cn(tea_set("Tea", tea_col, tea_ink), 1.0, -0.15)
    return keep


def dress_peach(st, kenney, metal_mat):
    """Персиковая кухня: тюльпаны в вазе на полке, чайный сервиз в горошек на столешнице."""
    return dress_shop(st, kenney, metal_mat, "tulip", (0.98, 0.42, 0.40), (0.99, 0.96, 0.92), (0.96, 0.52, 0.40))


def dress_lavender(st, kenney, metal_mat):
    """Лавандовая кухня: букет лаванды на полке, сиреневый чайный сервиз."""
    return dress_shop(st, kenney, metal_mat, "lavender", (0.56, 0.42, 0.86), (0.96, 0.95, 1.0), (0.56, 0.42, 0.86))


K.DRESS.update({"mexico": dress_mexico, "bakery": dress_bakery, "halloween": dress_halloween, "autumn": dress_autumn,
                "sweets": dress_sweets, "bbq": dress_bbq, "gourmet": dress_gourmet, "peach": dress_peach,
                "lavender": dress_lavender})

K.STYLE_EXTRA.update({
    "mexico": dict(layout="square", band=((2.3, 2.95), (-3.9, -2.8)), talavera=True, val_jitter=0.12, hue_jitter=0.02,
                   mottle=0.22, edge=0.3, handle="knob", tile_rough=0.12),
    "bakery": dict(layout="subway", edge=0.3, val_jitter=0.08, mottle=0.18, handle="bar", top_mat="marble"),
    "halloween": dict(layout="subway", edge=0.3, edge_col=(0.30, 0.12, 0.40), val_jitter=0.18, hue_jitter=0.015, mottle=0.25,
                      tile_rough=0.1, tile_coat=0.5, lamps=True, strip_e=0, wash_e=35, key_k=0.45, world_k=1.2, bloom=True,
                      wood_mat="dark", top_mat="dark", handle="knob"),
    "autumn": dict(layout="subway", edge=0.3, val_jitter=0.14, hue_jitter=0.02, mottle=0.24, handle="knob"),
    "sweets": dict(layout="subway", edge=0.4, val_jitter=0.08, hue_jitter=0.015, mottle=0.18, handle="knob"),
    "bbq": dict(layout="brick", tile_rough=0.7, tile_coat=0.0, edge=0.15, val_jitter=0.3, hue_jitter=0.03, mottle=0.4,
                mottle_scale=9.0, pillow=0.01, bevel=0.025, gap=0.024, tilt=1.6, handle="bar", wood_mat="dark",
                top_mat="dark"),
    "gourmet": dict(layout="subway", edge=0.18, tile_rough=0.06, tile_coat=0.6, val_jitter=0.12, hue_jitter=0.015,
                    mottle=0.2, handle="bar", top_mat="marble", key_k=0.62, world_k=0.8),
    "peach": dict(layout="subway", edge=0.35, val_jitter=0.1, mottle=0.2),
    "lavender": dict(layout="subway", edge=0.35, val_jitter=0.1, mottle=0.2),
})
