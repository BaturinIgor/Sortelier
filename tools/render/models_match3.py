"""Мини-игра "три в ряд" на рынке: спецфишки, препятствия и иконки бустеров; тайный критик и иконки ивентов.

Подключается из models.py (EXTENSIONS): все функции добавляются в M.MODELS.
Фишки и препятствия (m3_*) рендерятся как продукты. Иконки (icon_*) собраны помощниками icons.py
(глянцевый пластик toy(), окружение gold_world) и рендерятся тем же models.py:
  python tools/render/models.py art/new/match3 --only m3_pin,m3_bomb,...
  python tools/render/models.py art/new/match3 --only icon_m3_mallet,icon_market,...
Портрет critic собирается из customers.py и снимается в кадре покупателей (см. portrait_frame).
"""
import math
import random

import bpy
from mathutils import Matrix, Vector

import models as M
from models import *  # noqa: F401,F403  помощники
import coins as C
import customers as CU
import icons as I
import render as RD
from models_events import citrus_mat, leaf, spline, sweep
from models_mexico import vcol, vmat


# MARK: - Помощники

def face_cam(parts, extra=0.0):
    """Вид строго спереди: ось X модели идет вдоль кадра (камера смотрит с азимута 14 градусов)."""
    return rotate_all(parts, (0, 0, M.AZIMUTH + math.radians(extra)))


def rbox(name, x0, x1, y0, y1, z0, z1, mat, bev=0.02, segs=3):
    """Брусок по координатам углов со скругленными ребрами."""
    ob = box_mesh(name, x1 - x0, y1 - y0, z1 - z0, z0)
    ob.location = ((x0 + x1) / 2, (y0 + y1) / 2, 0)
    apply_transform(ob)
    if bev:
        bevel(ob, bev, segs, 30)
    smooth(ob, 30)
    return assign(ob, mat)


def glow_mat(name, color, strength=4.0):
    """Светящийся материал: искра, блестки."""
    mat = flat(name, color, rough=0.4)
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (*lin(color), 1)
    b.inputs["Emission Strength"].default_value = strength
    return mat


def add_grain(mat, color, axis="x", scale=9.0, strength=0.3, width=0.22, distortion=4.0):
    """Волокна дерева: тонкие темные прожилки вдоль оси axis (в координатах объекта)."""
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    mp = nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = {"x": (0.08, 1.0, 1.0), "y": (1.0, 0.08, 1.0), "z": (1.0, 1.0, 0.08)}[axis]
    links.new(tc.outputs["Object"], mp.inputs["Vector"])
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "DIAGONAL"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = distortion
    wave.inputs["Detail"].default_value = 2.0
    wave.inputs["Detail Scale"].default_value = 1.2
    links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (strength, strength, strength, 1)
    els[1].position, els[1].color = width, (0, 0, 0, 1)
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    M._mix_over(mat, ramp.outputs["Color"], color)
    return mat


def wood(name, color, axis="x", rough=0.4, coat=0.45, grain=0.3, scale=9.0):
    """Теплое дерево игрушечного вида: свет сверху, прожилки вдоль оси."""
    mat = I.toy(name, color, rough=rough, coat=coat)
    return add_grain(mat, I.shade(color, 0.7), axis=axis, scale=scale, strength=grain)


def lathe_smooth(name, ctrl, segs=96, n=6):
    """Тело вращения по плавной кривой через опорные точки (радиус, высота), концы на оси."""
    pts = [(max(0.0, r), z) for r, _, z in spline([(r, 0.0, z) for r, z in ctrl], n)]
    prof = [(0.0, ctrl[0][1])] + pts + [(0.0, ctrl[-1][1])]
    return lathe(name, prof, segs)


# MARK: - Спецфишки

def m3_pin():
    """Скалка: бочонок и две ручки с цветным пояском. Лежит вдоль кадра, симметрична."""
    barrel_m = wood("PinWood", (0.90, 0.58, 0.30), axis="z", rough=0.28, coat=0.75, grain=0.3, scale=7)
    handle_m = wood("PinHandle", (0.80, 0.48, 0.22), axis="z", rough=0.28, coat=0.75, grain=0.25, scale=7)
    ring_m = I.toy("PinRing", (0.93, 0.18, 0.28), rough=0.2, coat=0.9)
    R, hb, cr = 0.44, 0.6, 0.15
    prof = [(0.0, -hb)]
    for k in range(9):
        a = math.radians(-90 + 90 * k / 8)
        prof.append((R - cr + cr * math.cos(a), -hb + cr + cr * math.sin(a)))
    for k in range(9):
        a = math.radians(90 * k / 8)
        prof.append((R - cr + cr * math.cos(a), hb - cr + cr * math.sin(a)))
    prof.append((0.0, hb))
    barrel = lathe("Barrel", prof, 128)
    assign(smooth(barrel), barrel_m)
    axle = cylinder("Axle", 0.09, 2 * hb + 0.2, 48)
    assign(smooth(axle), handle_m)
    parts = [barrel, axle]
    gap, Lh = 0.05, 0.44
    ctrl = [(0.134, 0.0), (0.156, 0.026), (0.146, 0.088), (0.149, 0.176), (0.17, 0.264), (0.186, 0.343),
            (0.178, 0.396), (0.138, 0.431), (0.06, Lh)]
    s0, s1 = 0.215, 0.29
    for i, side in enumerate((1, -1)):
        h = lathe_smooth(f"Handle{i}", ctrl, 96, 8)
        h.location = (0, 0, hb + gap)
        apply_transform(h)
        smooth(h)
        assign_faces(h, handle_m, [(lambda n, c: hb + gap + s0 < c.z < hb + gap + s1, ring_m)])
        if side < 0:
            h.rotation_euler = (math.radians(180), 0, 0)
            apply_transform(h)
        parts.append(h)
    rotate_all(parts, (0, math.radians(90), 0))
    return face_cam(parts)


def m3_bomb():
    """Вишня-бомба: крупная глянцевая вишня, хвостик-фитиль и искра на кончике."""
    R = 0.82
    body = sphere("Cherry", R, 96, 64)

    def shape(co):
        x, y, z = co / R
        r = math.hypot(x, y)
        k = 1.03 + 0.05 * z
        z = z * 0.93 - 0.22 * math.exp(-(r / 0.3) ** 2) * max(0.0, z) ** 2
        return Vector((x * k, y * k, z)) * R
    deform(body, shape)
    # едва заметный шовчик сбоку, как у настоящей вишни
    a0 = math.radians(-128)
    push_normals(body, lambda co, n: -0.02 * math.exp(-((math.atan2(co.y, co.x) - a0) / 0.06) ** 2)
                 * max(0.0, 1 - (co.z / R) ** 4))
    smooth(body)
    # глубокий вишневый, темнее и холоднее помидора
    cherry = C.world_mat("Cherry", [(0.0, (0.26, 0.0, 0.04)), (0.45, (0.60, 0.01, 0.08)), (0.8, (0.80, 0.04, 0.12)),
                                    (1.0, (0.95, 0.22, 0.26))], rough=0.1, metal=0.0, coat=1.0)
    b = cherry.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 0.15
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.2, 0.2)
    b.inputs["Subsurface Scale"].default_value = 0.08
    assign(body, cherry)
    top = R * (0.93 - 0.22)
    path = spline([(0.0, 0.0, top - 0.08), (0.02, 0.0, top + 0.2), (0.1, 0.0, top + 0.42), (0.26, 0.0, top + 0.56),
                   (0.43, 0.0, top + 0.6)], 10)
    stem = sweep("Fuse", path, lambda t: 0.072 - 0.022 * t, segs=24)
    stem_m = material("Fuse", [(0.0, (0.22, 0.48, 0.10)), (0.55, (0.42, 0.72, 0.20)), (0.78, (0.50, 0.78, 0.24)),
                               (0.9, (0.32, 0.22, 0.10)), (1.0, (0.16, 0.10, 0.06))], coord="x", lo=-0.02, hi=0.46,
                      rough=0.3, coat=0.6)
    assign(stem, stem_m)
    parts = [body, stem]
    tip = Vector(path[-1]) + Vector((0.07, 0.0, 0.02))
    parts += spark(tip, 1.35)
    return face_cam(parts)


def spark(tip, size=1.0):
    """Искра: оранжевая звезда, желтая серединка, белое ядро и пара брызг."""
    # лучи через один короче: искра не выглядит правильной звездочкой
    outer = [(x * size * (0.78 if k % 4 == 2 else 1.0), y * size * (0.78 if k % 4 == 2 else 1.0))
             for k, (x, y) in enumerate(I.star_pts(0.36, 0.13, n=8, rot=90))]
    s1 = I.slab("SparkOut", outer, 0.05, 0.02, glow_mat("SparkOrange", (1.0, 0.50, 0.08), 3.0))
    s2 = I.slab("SparkIn", I.star_pts(0.22 * size, 0.1 * size, n=8, rot=112.5), 0.05, 0.02,
                glow_mat("SparkYellow", (1.0, 0.88, 0.25), 4.0), y=-0.03)
    core = sphere("SparkCore", 0.075 * size, 24, 12)
    core.location = (0, -0.06, 0)
    apply_transform(core)
    assign(smooth(core), glow_mat("SparkWhite", (1.0, 0.98, 0.85), 6.0))
    parts = [s1, s2, core]
    for k, (a, d, r) in enumerate(((40, 0.46, 0.035), (150, 0.44, 0.03), (250, 0.42, 0.028), (320, 0.47, 0.024))):
        dot = sphere(f"Ember{k}", r * size, 16, 8)
        dot.location = (d * size * math.cos(math.radians(a)), -0.02, d * size * math.sin(math.radians(a)))
        apply_transform(dot)
        assign(smooth(dot), glow_mat(f"EmberM{k}", (1.0, 0.78, 0.2), 4.0))
        parts.append(dot)
    # звезда смотрит в камеру
    rotate_all(parts, (0, 0, -M.AZIMUTH))
    for o in parts:
        o.location = o.location + tip
    bpy.context.view_layer.update()
    return parts


def m3_whisk():
    """Венчик: блестящие петли и бирюзовая ручка, наклон около 30 градусов."""
    C.gold_world(0.6)
    steel = I.toy("WhiskSteel", (0.82, 0.85, 0.92), rough=0.18, coat=0.4, metal=0.75)
    teal = I.toy("WhiskTeal", (0.08, 0.68, 0.70), rough=0.22, coat=0.85)
    L, W, wr = 1.4, 0.5, 0.046
    parts = []
    n = 220
    for k in range(4):
        a = math.pi * k / 4 + math.radians(22)
        pts = []
        for i in range(n + 1):
            s = 2 * i / n
            t = s if s <= 1 else 2 - s
            side = 1 if s <= 1 else -1
            u = side * W * 3.0 * t ** 1.4 * (1 - t) ** 0.5
            pts.append((u * math.cos(a), u * math.sin(a), -0.12 + (L + 0.12) * t))
        parts.append(I.tube(f"Wire{k}", pts, wr, steel, res=6))
    ferrule = lathe_smooth("Ferrule", [(0.115, -0.34), (0.136, -0.3), (0.138, -0.08), (0.155, -0.04), (0.15, 0.0),
                                       (0.09, 0.03)], 64, 4)
    assign(smooth(ferrule), steel)
    handle = lathe_smooth("Handle", [(0.12, -1.2), (0.162, -1.17), (0.186, -1.05), (0.18, -0.8), (0.158, -0.5),
                                     (0.148, -0.33)], 64, 6)
    assign(smooth(handle), teal)
    parts += [ferrule, handle]
    rotate_all(parts, (0, math.radians(30), 0))
    return face_cam(parts)


RAINBOW = [(0.96, 0.18, 0.24), (1.0, 0.52, 0.10), (1.0, 0.84, 0.14), (0.30, 0.80, 0.30), (0.18, 0.55, 1.0),
           (0.62, 0.32, 0.95)]


def rainbow_mat(name, bend=-0.35, half=0.94, soft=0.012):
    """Радужная глазурь: шесть полос поперек пончика, чуть изогнутых дугой (x + bend * y^2)."""
    mat = material(name, [(0.0, (1, 1, 1)), (1.0, (1, 1, 1))], rough=0.1, sss=0.15, coat=1.0, coat_rough=0.03)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    sq = nodes.new("ShaderNodeMath")
    sq.operation = "MULTIPLY"
    links.new(sep.outputs["Y"], sq.inputs[0])
    links.new(sep.outputs["Y"], sq.inputs[1])
    arc_ = nodes.new("ShaderNodeMath")
    arc_.operation = "MULTIPLY_ADD"
    links.new(sq.outputs[0], arc_.inputs[0])
    arc_.inputs[1].default_value = bend
    links.new(sep.outputs["X"], arc_.inputs[2])
    u = nodes.new("ShaderNodeMapRange")
    u.inputs["From Min"].default_value = -half
    u.inputs["From Max"].default_value = half
    links.new(arc_.outputs[0], u.inputs["Value"])
    val = u.outputs["Result"]
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    n = len(RAINBOW)
    stops = []
    for i, c in enumerate(RAINBOW):
        stops.append((i / n + (soft if i else 0.0), c))
        stops.append(((i + 1) / n - (soft if i < n - 1 else 0.0), c))
    els[0].position, els[0].color = stops[0][0], (*lin(stops[0][1]), 1)
    els[1].position, els[1].color = stops[-1][0], (*lin(stops[-1][1]), 1)
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = (*lin(col), 1)
    links.new(val, ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    return mat


def glaze_mesh(name, major, minor, seed=0):
    """Глазурь на пончике с неровным краем и подтеками (как у обычного пончика)."""
    segs, ring = 160, 56
    verts, faces = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        thr = -0.08 + 0.09 * math.sin(6 * a + seed) + 0.06 * math.sin(11 * a + 1.3 + seed)
        for j in range(ring):
            b = 2 * math.pi * j / ring
            sz = math.sin(b)
            g = smoothstep(thr - 0.12, thr + 0.05, sz)
            r = minor * (0.92 + 0.14 * g)
            x = (major + r * math.cos(b)) * math.cos(a)
            y = (major + r * math.cos(b)) * math.sin(a)
            verts.append((x, y, r * sz * 0.85 + 0.012 * g))
    for i in range(segs):
        for j in range(ring):
            a_, b_ = i * ring + j, ((i + 1) % segs) * ring + j
            c_, d_ = ((i + 1) % segs) * ring + (j + 1) % ring, i * ring + (j + 1) % ring
            faces.append((a_, b_, c_, d_))
    return smooth(from_data(name, verts, faces))


def m3_rainbow():
    """Радужный пончик: самая яркая фишка (цветная бомба). Белая посыпка и серебряные жемчужинки."""
    major, minor = 0.62, 0.34
    dough = torus("Dough", major, minor, 128, 48)
    deform(dough, lambda co: Vector((co.x, co.y, co.z * 0.85)))
    smooth(dough)
    assign(dough, material("Dough", [(0.0, (0.80, 0.44, 0.16)), (0.5, (0.96, 0.64, 0.28)), (1.0, (1.0, 0.82, 0.5))],
                           coord="nz", lo=-1, hi=1, rough=0.45, sss=0.3, coat=0.2, bump=0.05, bump_scale=20))
    glaze = glaze_mesh("Glaze", major, minor)
    assign(glaze, rainbow_mat("Rainbow", half=(major + minor) * 0.98))
    white = flat("Sprinkle", (1.0, 1.0, 1.0), rough=0.25, coat=0.6)
    silver = I.toy("Pearl", (0.92, 0.93, 0.97), rough=0.08, coat=1.0, metal=0.9)

    def make(i, rnd):
        if i % 5 == 4:
            # серебряные жемчужинки дают искры на свету
            sp = sphere(f"Pearl{i}", 0.04, 16, 10)
            sp.location = (0, 0, 0.02)
            apply_transform(sp)
            return assign(smooth(sp), silver)
        sp = capsule(f"Sprinkle{i}", 0.13, 0.026, 12, 8)
        return assign(smooth(sp), white)
    scatter_on(glaze, 34, make, seed=11, area=0.98, zmin=0.16, spacing=0.13)
    parts = [o for o in bpy.data.objects if o.type == "MESH"]
    # чуть наклонен к камере: глазури видно больше; полосы идут поперек кадра
    rotate_all(parts, (math.radians(12), 0, 0))
    return face_cam(parts)


# MARK: - Препятствия

CRATE_W, CRATE_H, CRATE_D = 1.0, 0.86, 0.62


def plank_pts(x0, x1, z0, z1, left=None, right=None):
    """Контур доски в плоскости XZ; left/right - торцы снизу вверх [(dx, доля высоты)], у сломанных доски излом."""
    left = left or [(0.0, 0.0), (0.0, 1.0)]
    right = right or [(0.0, 0.0), (0.0, 1.0)]
    pts = [(x1 + dx, z0 + (z1 - z0) * f) for dx, f in right]
    pts += [(x0 + dx, z0 + (z1 - z0) * f) for dx, f in reversed(left)]
    return pts


def crate(level):
    """Ящик для овощей спереди: 3 - окован железом, 2 - целый, 1 - с треснувшими досками."""
    W, H, D = CRATE_W, CRATE_H, CRATE_D
    xl, xr, yf, yb = -W / 2, W / 2, -D / 2, D / 2
    pw, rail = 0.15, 0.15
    frame_m = wood("CrateFrame", (0.80, 0.50, 0.26), axis="z", rough=0.5, coat=0.3, grain=0.35, scale=7)
    rail_m = wood("CrateRail", (0.82, 0.52, 0.27), axis="x", rough=0.5, coat=0.3, grain=0.35, scale=7)
    slat_m = wood("CrateSlat", (0.92, 0.66, 0.38), axis="x", rough=0.5, coat=0.3, grain=0.3, scale=8)
    lid_m = wood("CrateLid", (0.80, 0.54, 0.30), axis="x", rough=0.5, coat=0.3, grain=0.3, scale=8)
    dark = flat("CrateInside", (0.22, 0.12, 0.06), rough=0.8)
    nail_m = I.toy("Nail", (0.42, 0.40, 0.42), rough=0.35, coat=0.3, metal=0.4)
    parts = [rbox("Inside", xl + 0.05, xr - 0.05, yf + 0.03, yb - 0.05, 0.03, H - 0.04, dark, 0.0)]
    # боковины-стойки во всю глубину и задняя стенка
    for i, (a, b) in enumerate(((xl, xl + pw), (xr - pw, xr))):
        parts.append(rbox(f"Post{i}", a, b, yf - 0.04, yb, 0.0, H, frame_m, 0.025))
    parts.append(rbox("Back", xl + pw - 0.01, xr - pw + 0.01, yb - 0.08, yb, 0.0, H, rail_m, 0.02))
    # верхняя и нижняя перекладины рамки
    parts.append(rbox("RailTop", xl + pw - 0.01, xr - pw + 0.01, yf - 0.03, yf + 0.1, H - rail, H, rail_m, 0.025))
    parts.append(rbox("RailBottom", xl + pw - 0.01, xr - pw + 0.01, yf - 0.03, yf + 0.1, 0.0, rail, rail_m, 0.025))
    # крышка из двух досок
    lid_y = [(yf + 0.1, yf + 0.1 + 0.205), (yb - 0.08 - 0.205, yb - 0.08)]
    gap = 0.035
    slat_h = (H - 2 * rail - 3 * gap) / 2
    slats = [(rail + gap, rail + gap + slat_h), (rail + 2 * gap + slat_h, H - rail - gap)]
    sx0, sx1 = xl + pw - 0.02, xr - pw + 0.02
    sy = yf + 0.035
    if level == 1:
        # верхняя доска сломана посередине, кусок выпал
        z0, z1 = slats[1]
        lj = [(0.02, 0.0), (0.07, 0.2), (-0.02, 0.4), (0.09, 0.58), (0.02, 0.8), (0.06, 1.0)]
        rj = [(0.03, 0.0), (-0.05, 0.18), (0.03, 0.36), (-0.06, 0.55), (0.0, 0.78), (-0.03, 1.0)]
        left = I.slab("SlatTopL", plank_pts(sx0, -0.08, z0, z1, right=lj), 0.06, 0.012, slat_m, y=sy)
        right = I.slab("SlatTopR", plank_pts(0.12, sx1, z0, z1, left=rj), 0.06, 0.012, slat_m, y=sy)
        rotate_all([left], (0, math.radians(6), 0), pivot=(sx0, sy, z0))
        rotate_all([right], (0, math.radians(-3), 0), pivot=(sx1, sy, z1))
        right.location.y += 0.015
        parts += [left, right]
        # щепки на изломе
        for k, (x, z, ang, ln) in enumerate(((-0.04, z0 + 0.62 * slat_h, 20, 0.11), (0.08, z0 + 0.3 * slat_h, 195, 0.1),
                                             (0.09, z0 + 0.84 * slat_h, 165, 0.08))):
            a = math.radians(ang)
            sp = I.slab(f"Splinter{k}", [(0.0, -0.014), (ln, 0.0), (0.0, 0.014)], 0.025, 0.004, slat_m, y=sy - 0.01)
            sp.rotation_euler = (0, -a, 0)
            sp.location = (x, 0, z)
            apply_transform(sp)
            parts.append(sp)
        # нижняя доска треснула наискосок, правая часть просела
        z0, z1 = slats[0]
        crack = [(-0.06, 0.0), (0.0, 0.2), (-0.03, 0.42), (0.05, 0.6), (0.02, 0.8), (0.1, 1.0)]
        cx = 0.12
        a_ = I.slab("SlatLowL", plank_pts(sx0, cx, z0, z1, right=crack), 0.06, 0.01, slat_m, y=sy)
        b_ = I.slab("SlatLowR", plank_pts(cx + 0.02, sx1, z0, z1, left=crack), 0.06, 0.01, slat_m, y=sy)
        rotate_all([b_], (0, math.radians(-4), 0), pivot=(sx1, sy, z0))
        b_.location.y += 0.012
        parts += [a_, b_]
        # крышка: передняя доска с отколотым краем
        y0, y1 = lid_y[0]
        lid = rbox("Lid0", sx0, sx1, y0, y1, H - 0.07, H - 0.003, lid_m, 0.02)
        parts.append(lid)
        cut = I.slab("LidChip", [(-0.2, -0.2), (0.05, -0.2), (0.0, 0.3), (-0.12, 0.25)], 0.3, 0.0, dark)
        cut.rotation_euler = (math.radians(-90), 0, 0)
        cut.location = (0.05, y0 - 0.02, H)
        apply_transform(cut)
        boolean_cut(lid, [cut])
        smooth(lid, 30)
        y0, y1 = lid_y[1]
        parts.append(rbox("Lid1", sx0, sx1, y0, y1, H - 0.07, H - 0.003, lid_m, 0.02))
    else:
        for k, (z0, z1) in enumerate(slats):
            parts.append(rbox(f"Slat{k}", sx0, sx1, yf, yf + 0.07, z0, z1, slat_m, 0.022))
        for k, (y0, y1) in enumerate(lid_y):
            parts.append(rbox(f"Lid{k}", sx0, sx1, y0, y1, H - 0.07, H - 0.003, lid_m, 0.02))
    # гвозди на стойках напротив досок
    for side in (-1, 1):
        for k, z in enumerate((rail / 2, (slats[0][0] + slats[0][1]) / 2, (slats[1][0] + slats[1][1]) / 2,
                               H - rail / 2)):
            if level == 1 and side == 1 and k == 2:
                continue
            nl = sphere(f"Nail{side}{k}", 0.026, 16, 8)
            nl.scale = (1, 0.5, 1)
            nl.location = (side * (W / 2 - pw / 2), yf - 0.04, z)
            apply_transform(nl)
            parts.append(assign(smooth(nl), nail_m))
    if level == 3:
        parts += crate_irons(W, H, yf - 0.04)
    return face_cam(parts)


def crate_irons(W, H, yfront):
    """Темные железные уголки с заклепками на углах и полоса посередине."""
    iron = I.toy("Iron", (0.26, 0.28, 0.33), rough=0.3, coat=0.5, metal=0.35)
    rivet_m = I.toy("Rivet", (0.62, 0.64, 0.70), rough=0.22, coat=0.5, metal=0.6)
    arm, w, th = 0.3, 0.1, 0.03
    parts = []
    y = yfront - th / 2 + 0.004
    for sx in (-1, 1):
        for sz in (-1, 1):
            cx = sx * (W / 2 - 0.012)
            # нижние уголки чуть выше: выступающее железо не должно опускать силуэт ниже, чем у других ящиков
            cz = H / 2 + sz * (H / 2 - (0.012 if sz > 0 else 0.04))
            # уголок: вершина в углу ящика, полки уходят внутрь
            pts = [(cx + sx * x, cz + sz * y_) for x, y_ in [(0, 0), (-arm, 0), (-arm, -w), (-w, -w), (-w, -arm),
                                                               (0, -arm)]]
            if sx * sz < 0:
                pts = list(reversed(pts))
            pl = I.slab(f"Corner{sx}{sz}", pts, th, 0.012, iron, y=y)
            parts.append(pl)
            for k, (dx, dz) in enumerate(((-w / 2, -w / 2), (-arm + 0.06, -w / 2), (-w / 2, -arm + 0.06))):
                rv = sphere(f"Rivet{sx}{sz}{k}", 0.026, 16, 8)
                rv.scale = (1, 0.6, 1)
                rv.location = (cx + sx * dx, y - th / 2, cz + sz * dz)
                apply_transform(rv)
                parts.append(assign(smooth(rv), rivet_m))
    # полоса поперек ящика
    zc, bw = H / 2, 0.1
    parts.append(I.slab("Band", I.rounded_rect(W - 0.03, bw, 0.02), th, 0.012, iron, y=y))
    parts[-1].location.z += zc
    apply_transform(parts[-1])
    for k, x in enumerate((-W / 2 + 0.07, -0.16, 0.16, W / 2 - 0.07)):
        rv = sphere(f"BandRivet{k}", 0.026, 16, 8)
        rv.scale = (1, 0.6, 1)
        rv.location = (x, y - th / 2, zc)
        apply_transform(rv)
        parts.append(assign(smooth(rv), rivet_m))
    return parts


def m3_jam():
    """Клякса малинового джема: плоская лужица с каплями, лежит на столе и видна почти сверху."""
    # как желе: в толще темнее, к тонкому краю светлее и розовее
    jam_m = material("Jam", [(0.0, (0.66, 0.03, 0.20)), (0.6, (0.80, 0.06, 0.27)), (1.0, (0.94, 0.24, 0.42))],
                     coord="r", lo=0.0, hi=1.05, rough=0.16, sss=0.2, sss_radius=(1.0, 0.1, 0.15), sss_scale=0.05,
                     coat=1.0, coat_rough=0.05, spec=0.6)
    # клякса - мягкое объединение кругов: середина и круглые наплывы по краю
    circles = ((0.0, 0.0, 0.8), (0.52, 0.44, 0.42), (-0.24, 0.78, 0.2), (-0.74, 0.06, 0.34), (-0.44, -0.66, 0.22),
               (0.36, -0.56, 0.38), (0.92, -0.08, 0.15))

    def reach(a, cs, k=9.0):
        dx, dy = math.cos(a), math.sin(a)
        acc = 0.0
        for cx, cy, r in cs:
            b = cx * dx + cy * dy
            q = r * r - (cx * cx + cy * cy - b * b)
            if q > 0:
                acc += max(0.0, b + math.sqrt(q)) ** k
        return acc ** (1.0 / k)

    def blob(name, rfn, h, p=2.4, bumps=0.0, loc=(0.0, 0.0)):
        ob = quad_sphere(name, 40)

        def fn(co):
            rho = math.hypot(co.x, co.y)
            k = 1.0 / ((rho ** p + abs(co.z) ** p) ** (1.0 / p))
            a = math.atan2(co.y, co.x)
            d = rfn(a)
            x, y = co.x * k * d, co.y * k * d
            z = co.z * k * h
            if z < 0:
                z *= 0.1
            else:
                # середина чуть выпуклая, по поверхности пологие волны - на них ловятся блики
                t = rho * k
                z *= 1.0 + 0.3 * max(0.0, 1 - t * t)
                z += bumps * fbm(Vector((x * 1.3, y * 1.3, 0.5))) * t ** 0.5 * (1 - t ** 6)
            return Vector((x, y, z))
        deform(ob, fn)
        ob.location = (loc[0], loc[1], 0.0)
        return assign(smooth(ob), jam_m)
    parts = [blob("Jam", lambda a: reach(a, circles), 0.12, bumps=0.03)]
    for k, (x, y, s) in enumerate(((1.14, 0.6, 0.09), (0.96, 0.92, 0.05), (-0.36, 1.14, 0.07), (-1.2, 0.0, 0.085),
                                   (-0.68, -1.0, 0.06), (0.74, -1.04, 0.1), (1.18, -0.36, 0.05))):
        parts.append(blob(f"Drop{k}", lambda a, s=s: s * (1 + 0.06 * math.sin(3 * a + k)), 0.035 + s * 0.35,
                          loc=(x, y)))
    seed_m = I.toy("Seed", (0.40, 0.03, 0.12), rough=0.3, coat=0.5)

    def make(i, rnd):
        sd = sphere(f"Seed{i}", 0.024, 12, 8)
        sd.scale = (1.0, 0.7, 0.45)
        return assign(smooth(sd), seed_m)
    scatter_on(parts[0], 12, make, seed=4, area=0.7, spacing=0.22)
    parts = [o for o in bpy.data.objects if o.type == "MESH"]
    rotate_all(parts, (math.radians(44), 0, 0))
    return face_cam(parts)


# MARK: - Иконки

def closed_spline(pts, n=8):
    """Замкнутая плавная кривая через точки контура (x, y)."""
    P = [Vector((x, y, 0.0)) for x, y in pts]
    m = len(P)
    out = []
    for i in range(m):
        p0, p1, p2, p3 = P[i - 1], P[i], P[(i + 1) % m], P[(i + 2) % m]
        for k in range(n):
            t = k / n
            v = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                       (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t)
            out.append((v.x, v.y))
    return out


def round_poly(pts, r, n=6):
    """Многоугольник со скругленными углами (скругление r вдоль сторон)."""
    out = []
    m = len(pts)
    for i in range(m):
        a, p, b = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % m])
        da, db = (a - p).normalized(), (b - p).normalized()
        p0, p1 = p + da * r, p + db * r
        for k in range(n + 1):
            t = k / n
            q = p0 * (1 - t) ** 2 + p * 2 * (1 - t) * t + p1 * t * t
            out.append((q.x, q.y))
    return out


def steel_mat(name, color=(0.80, 0.84, 0.92), rough=0.22, metal=0.6):
    return I.toy(name, color, rough=rough, coat=0.4, metal=metal)


def cut_slab(name, pts, depth, bev, mat, cutters, y=0.0):
    """Плоская деталь с прорезями: сначала вырезаем, потом скругляем края."""
    ob = I.slab(name, pts, depth, 0.0, mat, y=y)
    boolean_cut(ob, cutters)
    bevel(ob, bev, 3, 30)
    return smooth(ob, 30)


def slot_cutter(name, x, z, w, h, depth=1.0):
    c = I.slab(name, I.rounded_rect(w, h, w / 2 - 0.001, 8), depth, 0.0, None)
    c.location = (x, 0, z)
    apply_transform(c)
    return c


def spikes(name, n, size, height, mat):
    """Решетка пирамидок на грани в плоскости YZ, острия смотрят по +X."""
    verts, faces = [], []
    pitch = size / n
    h = pitch / 2 * 0.96
    for i in range(n):
        for j in range(n):
            cy = -size / 2 + pitch * (i + 0.5)
            cz = -size / 2 + pitch * (j + 0.5)
            b = len(verts)
            verts += [(0, cy - h, cz - h), (0, cy + h, cz - h), (0, cy + h, cz + h), (0, cy - h, cz + h),
                      (height, cy, cz)]
            faces += [(b, b + 1, b + 4), (b + 1, b + 2, b + 4), (b + 2, b + 3, b + 4), (b + 3, b, b + 4),
                      (b + 3, b + 2, b + 1, b)]
    ob = from_data(name, verts, faces)
    bevel(ob, pitch * 0.07, 2, 20)
    return assign(smooth(ob, 30), mat)


def icon_m3_mallet():
    """Молоток для отбивания мяса: шипастая стальная головка, деревянная ручка."""
    I._prep()
    steel = steel_mat("Steel", (0.62, 0.67, 0.76), rough=0.2, metal=0.75)
    L, hs = 0.86, 0.56
    head = box_mesh("Head", L, hs, hs, -hs / 2)
    bevel(head, 0.05, 4, 30)
    assign(smooth(head, 30), steel)
    parts = [head]
    for side in (1, -1):
        sp = spikes(f"Spikes{side}", 4, hs - 0.04, 0.13, steel)
        sp.location = (L / 2 - 0.005, 0, 0)
        apply_transform(sp)
        if side < 0:
            sp.rotation_euler = (0, 0, math.radians(180))
            apply_transform(sp)
        parts.append(sp)
    collar = lathe_smooth("Collar", [(0.09, -0.5), (0.12, -0.47), (0.125, -0.3), (0.14, -0.26), (0.12, -0.2)], 48, 4)
    assign(smooth(collar), steel)
    handle = lathe_smooth("Handle", [(0.1, -2.05), (0.128, -1.98), (0.13, -1.7), (0.112, -1.2), (0.098, -0.7),
                                     (0.1, -0.45)], 64, 6)
    assign_faces(smooth(handle), wood("HandleWood", (0.88, 0.56, 0.28), axis="z", rough=0.3, coat=0.6, grain=0.3),
                 [(lambda n, c: c.z < -1.84, I.toy("Cap", (0.93, 0.22, 0.26), rough=0.2, coat=0.9))])
    parts += [collar, handle]
    # ручка уходит влево вниз, шипастая грань смотрит в камеру и чуть вверх, под ключевой свет
    hdir = Vector((-0.6, 0.0, -0.8))
    ax = (Vector((0.0, -1.0, 0.0)) * math.cos(math.radians(40)) + Vector((-0.8, 0.0, 0.6)) * math.sin(math.radians(40)))
    ax.normalize()
    zc = -hdir
    rot = Matrix((ax, zc.cross(ax), zc)).transposed().to_4x4()
    for o in parts:
        o.matrix_world = rot @ o.matrix_world
    bpy.context.view_layer.update()
    return I.finish(parts, tilt=8)


def icon_m3_knife():
    """Поварской нож: широкое блестящее лезвие и темная ручка с заклепками."""
    I._prep()
    edge = spline([(0.0, 0.0, -0.58), (0.5, 0.0, -0.58), (1.0, 0.0, -0.52), (1.42, 0.0, -0.36), (1.74, 0.0, -0.12)], 8)
    spine = spline([(1.8, 0.0, -0.05), (1.5, 0.0, 0.02), (1.0, 0.0, 0.05), (0.4, 0.0, 0.06), (0.0, 0.0, 0.06)], 8)
    pts = [(x, z) for x, _, z in edge] + [(x, z) for x, _, z in spine]
    blade = I.slab("Blade", pts, 0.07, 0.03, None, segs=4)
    edge_v = [Vector((x, 0, z)) for x, _, z in edge]

    def tone(co, n):
        # кромка светлая (подвод), дальше чуть темнее, к обуху снова светлее
        d = min((Vector((co.x, 0, co.z)) - e).length for e in edge_v)
        t = smoothstep(0.05, 0.13, d)
        top = smoothstep(0.25, 0.5, d)
        c = tuple(a + (b - a) * t for a, b in zip((0.98, 0.99, 1.0), (0.72, 0.76, 0.85)))
        return tuple(a + (b - a) * top for a, b in zip(c, (0.86, 0.89, 0.95)))
    vcol(blade, tone)
    assign(blade, vmat("BladeMat", rough=0.16, coat=0.6, metal=0.45))
    steel = steel_mat("Bolster")
    bolster = I.slab("Bolster", I.rounded_rect(0.12, 0.56, 0.05), 0.14, 0.04, steel)
    bolster.location = (-0.04, 0, -0.24)
    apply_transform(bolster)
    hp = closed_spline([(-0.06, 0.0), (-0.5, 0.02), (-0.92, -0.01), (-1.08, -0.1), (-1.08, -0.3), (-0.96, -0.42),
                        (-0.6, -0.36), (-0.3, -0.36), (-0.06, -0.38)], 8)
    handle = I.slab("Handle", hp, 0.2, 0.08, I.toy("HandleDark", (0.24, 0.15, 0.12), rough=0.3, coat=0.8), segs=6)
    parts = [blade, bolster, handle]
    for k, x in enumerate((-0.28, -0.56, -0.84)):
        rv = I.disc(f"Rivet{k}", 0.05, 0.04, steel_mat(f"RivetM{k}", (0.9, 0.9, 0.94)), y=-0.1)
        rv.location = (x, 0, -0.18)
        apply_transform(rv)
        parts.append(rv)
    rotate_all(parts, (0, math.radians(-36), 0))
    return I.finish(parts, tilt=8)


def icon_m3_spatula():
    """Лопатка: плоская стальная головка с прорезями и яркая ручка."""
    I._prep()
    steel = steel_mat("Steel")
    head_pts = round_poly([(-0.22, 0.0), (0.22, 0.0), (0.42, 1.0), (-0.42, 1.0)], 0.13, 8)
    cutters = [slot_cutter(f"Slot{k}", x, 0.56, 0.07, 0.6) for k, x in enumerate((-0.19, -0.063, 0.063, 0.19))]
    head = cut_slab("Head", head_pts, 0.06, 0.02, steel, cutters)
    neck = I.slab("Neck", [(-0.2, 0.06), (-0.07, -0.42), (0.07, -0.42), (0.2, 0.06)], 0.05, 0.02, steel)
    hp = round_poly([(-0.1, -0.3), (0.1, -0.3), (0.13, -1.35), (-0.13, -1.35)], 0.09, 8)
    hole = slot_cutter("Hole", 0.0, -1.18, 0.09, 0.09)
    handle = cut_slab("Handle", hp, 0.16, 0.05, I.toy("HandleOrange", (1.0, 0.50, 0.14), rough=0.22, coat=0.9),
                      [hole])
    parts = [head, neck, handle]
    for k, z in enumerate((-0.42, -0.6)):
        rv = I.disc(f"Rivet{k}", 0.04, 0.03, steel_mat(f"RivetM{k}", (0.92, 0.92, 0.95)), y=-0.08)
        rv.location = (0, 0, z)
        apply_transform(rv)
        parts.append(rv)
    rotate_all(parts, (0, math.radians(-30), 0))
    return I.finish(parts, tilt=8)


def beater(name, x, y, steel, z_top=-0.2):
    """Венчик миксера: стержень и четыре петли, широкие внизу."""
    parts = []
    shaft = cylinder(f"{name}Shaft", 0.042, 0.5, 24)
    shaft.location = (x, y, z_top - 0.25)
    apply_transform(shaft)
    parts.append(assign(smooth(shaft), steel))
    collar = cylinder(f"{name}Collar", 0.07, 0.07, 32)
    collar.location = (x, y, z_top - 0.08)
    apply_transform(collar)
    bevel(collar, 0.02, 3, 30)
    parts.append(assign(smooth(collar, 30), steel))
    z0, z1, W = z_top - 0.42, z_top - 1.22, 0.24
    for k in range(4):
        a = math.pi * k / 4 + math.radians(20)
        pts = []
        n = 120
        for i in range(n + 1):
            s = 2 * i / n
            t = s if s <= 1 else 2 - s
            side = 1 if s <= 1 else -1
            u = side * W * 2.17 * t ** 1.0 * (1 - t) ** 0.35
            pts.append((x + u * math.cos(a), y + u * math.sin(a), z0 + (z1 - z0) * t))
        parts.append(I.tube(f"{name}Loop{k}", pts, 0.032, steel, res=5))
    return parts


def icon_m3_mixer():
    """Ручной миксер пастельного цвета с двумя венчиками."""
    I._prep()
    body_m = I.toy("Body", (0.98, 0.58, 0.68), rough=0.25, coat=0.85)
    trim = I.white("Trim")
    steel = steel_mat("Steel", (0.86, 0.88, 0.94))
    body_pts = closed_spline([(-0.95, 0.05), (-0.86, 0.32), (-0.5, 0.42), (0.1, 0.44), (0.6, 0.38), (0.86, 0.16),
                              (0.88, -0.06), (0.7, -0.22), (0.2, -0.27), (-0.5, -0.22), (-0.86, -0.12)], 8)
    body = I.slab("Body", body_pts, 0.66, 0.24, body_m, segs=8)
    grip = sweep("Grip", spline([(-0.62, 0.0, 0.22), (-0.66, 0.0, 0.62), (-0.42, 0.0, 0.86), (0.12, 0.0, 0.86),
                                 (0.38, 0.0, 0.66), (0.4, 0.0, 0.3)], 8), 0.14, segs=32)
    assign(grip, body_m)
    parts = [body, grip]
    # кнопка скоростей на ручке и круглая наклейка сбоку
    btn = sphere("Button", 0.1, 32, 16)
    btn.scale = (1.5, 0.9, 0.7)
    btn.location = (-0.12, 0, 1.0)
    apply_transform(btn)
    parts.append(assign(smooth(btn), trim))
    badge = I.disc("Badge", 0.17, 0.05, trim, y=-0.33)
    badge.location = (0.38, 0, 0.1)
    apply_transform(badge)
    parts.append(badge)
    dot = I.disc("BadgeDot", 0.07, 0.04, I.toy("BadgeDotM", (0.95, 0.42, 0.52), rough=0.2, coat=0.9), y=-0.36)
    dot.location = (0.38, 0, 0.1)
    apply_transform(dot)
    parts.append(dot)
    for k, z in enumerate((0.16, 0.04, -0.08)):
        v = I.slab(f"Vent{k}", I.rounded_rect(0.28, 0.045, 0.022), 0.03, 0.01,
                   I.toy(f"VentM{k}", (0.86, 0.48, 0.58), rough=0.3, coat=0.5), y=-0.335)
        v.location = (-0.55, 0, z)
        apply_transform(v)
        parts.append(v)
    parts += beater("BeaterA", 0.0, 0.12, steel, -0.18)
    parts += beater("BeaterB", 0.44, -0.12, steel, -0.2)
    return I.finish(parts, tilt=8)


def fruit(name, kind, loc, r=0.15):
    """Фрукт для прилавка: красное яблоко, апельсин, лимон или лайм."""
    cols = {"apple": (0.92, 0.16, 0.16), "orange": (1.0, 0.55, 0.10), "lemon": (1.0, 0.84, 0.18),
            "lime": (0.42, 0.78, 0.22)}
    ob = sphere(name, r, 32, 20)
    if kind == "lemon":
        deform(ob, lambda co: Vector((co.x * 1.25 * (1 - 0.1 * (co.y / r) ** 2), co.y * 0.95, co.z * 0.92)))
        deform(ob, lambda co: co + Vector((0.04 * math.copysign(max(0.0, abs(co.x) / r - 0.9) * 2, co.x), 0, 0)))
    elif kind == "apple":
        # ямка у хвостика
        deform(ob, lambda co: Vector((co.x, co.y, co.z * 0.92 - (0.04 if co.z > 0 else 0.0)
                                      * math.exp(-(math.hypot(co.x, co.y) / (0.3 * r)) ** 2))))
    ob.location = loc
    apply_transform(ob)
    mat = I.toy(f"{name}M", cols[kind], rough=0.3 if kind in ("orange", "lemon") else 0.18, coat=0.7)
    if kind in ("orange", "lemon"):
        b = mat.node_tree.nodes["Principled BSDF"]
        nodes, links = mat.node_tree.nodes, mat.node_tree.links
        nz = nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = 60.0
        bp = nodes.new("ShaderNodeBump")
        bp.inputs["Strength"].default_value = 0.25
        links.new(nz.outputs["Fac"], bp.inputs["Height"])
        links.new(bp.outputs["Normal"], b.inputs["Normal"])
    parts = [assign(smooth(ob), mat)]
    if kind == "apple":
        st = cylinder(f"{name}Stem", 0.014, 0.08, 12)
        st.rotation_euler = (0, math.radians(15), 0)
        st.location = (loc[0], loc[1], loc[2] + r * 0.92)
        apply_transform(st)
        parts.append(assign(smooth(st), I.toy(f"{name}StemM", (0.42, 0.26, 0.12))))
    if kind in ("apple", "orange"):
        lf = sphere(f"{name}Leaf", 0.06, 16, 8)
        lf.scale = (1.0, 0.45, 0.16)
        lf.rotation_euler = (0, math.radians(-25), math.radians(30))
        lf.location = (loc[0] + 0.05, loc[1], loc[2] + r * 0.95)
        apply_transform(lf)
        parts.append(assign(smooth(lf), I.toy(f"{name}LeafM", (0.30, 0.70, 0.22))))
    return parts


def icon_market():
    """Рыночный прилавок: полосатый навес с фестонами, деревянный прилавок, горки фруктов."""
    I._prep()
    red = I.toy("AwnRed", (0.93, 0.20, 0.22), rough=0.35, coat=0.6)
    wht = I.toy("AwnWhite", (0.98, 0.95, 0.90), rough=0.35, coat=0.5)
    wood_m = wood("Wood", (0.80, 0.50, 0.26), axis="z", rough=0.45, coat=0.4, grain=0.3)
    top_m = wood("Top", (0.90, 0.64, 0.36), axis="x", rough=0.45, coat=0.4, grain=0.3)
    parts = [rbox("Counter", -0.92, 0.92, -0.32, 0.34, 0.0, 0.8, wood_m, 0.03)]
    for k in range(5):
        x0 = -0.9 + k * 0.36
        m = wood(f"Plank{k}", (0.86, 0.56, 0.30) if k % 2 else (0.80, 0.50, 0.26), axis="z", rough=0.45, coat=0.4,
                 grain=0.3)
        parts.append(rbox(f"Plank{k}", x0 + 0.01, x0 + 0.35, -0.37, -0.31, 0.03, 0.77, m, 0.025))
    parts.append(rbox("Top", -1.02, 1.02, -0.46, 0.42, 0.8, 0.9, top_m, 0.035))
    # лотки с фруктами
    tray_m = wood("Tray", (0.74, 0.46, 0.24), axis="x", rough=0.5, coat=0.3, grain=0.3)
    kinds = ("apple", "orange", "lemon", "lime")
    for k, (x, kind) in enumerate(zip((-0.69, -0.23, 0.23, 0.69), kinds)):
        parts.append(rbox(f"Tray{k}", x - 0.21, x + 0.21, -0.36, 0.2, 0.9, 0.98, tray_m, 0.02))
        r = 0.135
        for j, (dx, dy, dz) in enumerate(((-0.1, -0.12, 0.0), (0.1, -0.12, 0.0), (0.0, 0.08, 0.02), (0.0, -0.06, 0.2))):
            parts += fruit(f"F{k}{j}", kind, (x + dx, dy, 0.98 + r * 0.92 + dz), r)
    for k, (x, y) in enumerate(((-0.95, -0.36), (0.95, -0.36), (-0.95, 0.34), (0.95, 0.34))):
        p = cylinder(f"Post{k}", 0.05, 1.2 if y < 0 else 1.4, 24)
        p.location = (x, y, 1.48 if y < 0 else 1.58)
        apply_transform(p)
        parts.append(assign(smooth(p), wood_m))
    # навес: полосы по скату, спереди фестоны
    n, w = 8, 0.29
    slope = math.radians(17)
    y0, y1, zf = -0.56, 0.5, 2.02
    awn = []
    for k in range(n):
        x = -w * n / 2 + w * (k + 0.5)
        m = red if k % 2 == 0 else wht
        st = rbox(f"Stripe{k}", x - w / 2 + 0.004, x + w / 2 - 0.004, y0, y1, -0.04, 0.04, m, 0.035, 4)
        deform(st, lambda co, x=x: co + Vector((0, 0, 0.03 * math.cos(math.pi * (co.x - x) / w))))
        awn.append(st)
        sc = I.slab(f"Scallop{k}", [(w / 2 * math.cos(math.radians(a)), w / 2 * math.sin(math.radians(a)))
                                    for a in range(180, 361, 10)], 0.05, 0.018, m, y=y0 + 0.01)
        sc.location = (x, 0, -0.1)
        apply_transform(sc)
        awn.append(sc)
        band = rbox(f"Valance{k}", x - w / 2 + 0.004, x + w / 2 - 0.004, y0 - 0.015, y0 + 0.035, -0.12, 0.0, m, 0.015)
        awn.append(band)
    rotate_all(awn, (slope, 0, 0), pivot=(0, y0, 0))
    for o in awn:
        o.location.z += zf
    parts += awn
    return I.finish(parts, tilt=10)


# MARK: - Тайный критик

def portrait_frame():
    """Кадр как у покупателей (customers.render): камера с азимута 8 и высоты 6 градусов, поле 1.04.
    models.render ставит свою камеру (14 и 26 градусов) по границам мешей, поэтому поворачиваем модель
    вместе со светом так, чтобы его камера видела то же самое, а границы кадра задаем невидимой рамкой."""
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    _, _, pts = RD.bounds(meshes)
    frame = [p for p in pts if p.z > -0.25] + [Vector((-1.25, 0, -0.25)), Vector((1.25, 0, -0.25))]

    def cam_rot(az, el):
        d = Vector((math.sin(az) * math.cos(el), -math.cos(az) * math.cos(el), math.sin(el)))
        return (-d).to_track_quat("-Z", "Y")
    qc = cam_rot(math.radians(8), math.radians(6))
    qp = cam_rot(M.AZIMUTH, M.ELEVATION)
    loc = [qc.inverted() @ p for p in frame]
    x0, x1 = min(p.x for p in loc), max(p.x for p in loc)
    y0, y1 = min(p.y for p in loc), max(p.y for p in loc)
    h = max(x1 - x0, y1 - y0) * 1.04 / 1.08 / 2
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    rot = (qp @ qc.inverted()).to_matrix().to_4x4()
    for o in bpy.data.objects:
        if o.type in ("MESH", "LIGHT"):
            o.matrix_world = rot @ o.matrix_world
        if o.type == "MESH":
            o["no_bounds"] = True
    corners = [(cx - h, cy - h, 0), (cx + h, cy - h, 0), (cx + h, cy + h, 0), (cx - h, cy + h, 0)]
    fr = from_data("PortraitFrame", corners, [(0, 1, 2, 3)])
    fr.matrix_world = qp.to_matrix().to_4x4()
    fr.hide_render = True
    bpy.context.view_layer.update()


def body_y(x, z):
    """Передняя поверхность туловища покупателя (эллипсоид из customers.build)."""
    return 0.1 - 0.82 * math.sqrt(max(0.0, 1 - (x / 1.38) ** 2 - ((z + 0.2) / 0.78) ** 2))


def critic():
    """Тайный ресторанный критик: шляпа, круглые темные очки, тонкие усики, тренч с поднятым воротником,
    водолазка, блокнот и ручка у подбородка. Собран из customers.build, одно настроение (любопытство)."""
    HZ = CU.HEAD_Z
    CU.build(("fair", "bald", (0.18, 0.11, 0.07), (0.80, 0.63, 0.38), None), "happy")
    # заменяем воротник, брови и рот, глаза закрыты очками
    for o in list(bpy.data.objects):
        if o.type == "MESH" and o.name.startswith(("Collar", "Brow", "Eye", "Highlight", "Mouth")):
            bpy.data.objects.remove(o)
    skin = bpy.data.objects["Head"].data.materials[0]
    hair_m = bpy.data.materials["Hair"]
    brow_m = bpy.data.materials["Brow"]
    lip = bpy.data.materials["Mouth"]
    coat = bpy.data.materials["Shirt"]
    white = M.flat("Shine", (1.0, 1.0, 1.0), rough=0.1)
    # линия волос выше, чем у ковбоя: брови над очками должны быть видны
    parts = [CU.hair_shell("Hair", hair_m, low=-0.3, front_cut=0.46)]
    # фетровая шляпа: поля спереди чуть опущены, тулья с ложбинкой и щипками
    felt = M.material("Fedora", [(0.0, (0.12, 0.11, 0.14)), (1.0, (0.36, 0.33, 0.40))], coord="z", lo=HZ + 0.4,
                      hi=HZ + 1.4, rough=0.5, sheen=0.5, coat=0.15)
    tilt = (math.radians(-8), math.radians(5), 0)
    brim = cylinder("HatBrim", 1.45, 0.06, 96)
    deform(brim, lambda co: Vector((co.x, co.y,
                                    co.z + 0.14 * (co.x / 1.45) ** 2 - 0.1 * max(0.0, -co.y / 1.45) ** 1.5)))
    bevel(brim, 0.03, 3, 30)
    brim.location = (0, 0.05, HZ + 0.6)
    brim.rotation_euler = tilt
    apply_transform(brim)
    subdivide(brim, 1)
    assign(smooth(brim, 40), felt)
    crown = lathe_smooth("HatCrown", [(0.8, 0.0), (0.78, 0.3), (0.72, 0.54), (0.6, 0.66), (0.35, 0.71), (0.05, 0.7)],
                         96, 6)

    def crease(co):
        t = max(0.0, (co.z - 0.35) / 0.36)
        z = co.z - 0.17 * t * math.exp(-(co.x / 0.24) ** 2)
        x = co.x * (1 - 0.18 * t * max(0.0, -co.y / 0.75))
        return Vector((x, co.y, z))
    deform(crown, crease)
    crown.location = (0, 0.08, HZ + 0.6)
    crown.rotation_euler = tilt
    apply_transform(crown)
    assign(smooth(crown), felt)
    band = lathe("HatBand", [(0.0, 0.0), (0.825, 0.0), (0.83, 0.02), (0.815, 0.16), (0.0, 0.16)], 96)
    band.location = (0, 0.08, HZ + 0.62)
    band.rotation_euler = tilt
    apply_transform(band)
    assign(smooth(band, 40), M.flat("HatBandMat", (0.70, 0.13, 0.20), rough=0.4, sheen=0.4))
    parts += [brim, crown, band]
    # круглые темные очки в золотой оправе, блик на стеклах
    lens_m = M.material("Lens", [(0.0, (0.16, 0.13, 0.24)), (1.0, (0.02, 0.02, 0.04))], coord="z", lo=HZ - 0.2,
                        hi=HZ + 0.22, rough=0.06, coat=1.0, coat_rough=0.02, spec=0.8)
    gold_m = M.material("FrameGold", [(0.0, (0.80, 0.55, 0.12)), (1.0, (1.0, 0.85, 0.40))], coord="z", lo=HZ - 0.2,
                        hi=HZ + 0.3, rough=0.2, metal=1.0)
    for side in (-1, 1):
        x = side * 0.35
        lens = CU.ellipsoid(f"Lens{side}", (0.21, 0.05, 0.2), lens_m, 48, 24)
        CU.at_face(lens, x, 0.02, -0.05)
        ring = torus(f"Rim{side}", 0.21, 0.03, 64, 12)
        ring.rotation_euler = (math.radians(90), 0, 0)
        CU.at_face(ring, x, 0.02, -0.07)
        assign(smooth(ring), gold_m)
        sh = CU.ellipsoid(f"LensShine{side}", (0.08, 0.02, 0.035), white, 16, 10)
        sh.rotation_euler = (0, math.radians(-35), 0)
        sh.location = (x - 0.07, CU.head_surface_y(x - 0.07, 0.11) * 0.97 - 0.11, HZ + 0.11)
        temple = M.tube(f"Temple{side}", [(side * 0.55, CU.head_surface_y(0.55, 0.06) * 0.97 - 0.06, HZ + 0.07),
                                         (side * 0.8, -0.45, HZ + 0.08), (side * 0.99, -0.05, HZ + 0.06)], 0.022)
        assign(smooth(temple), gold_m)
        parts += [lens, ring, sh, temple]
    bridge = []
    for i in range(9):
        t = -1 + 2 * i / 8
        xx = 0.14 * t
        zz = HZ + 0.09 + 0.03 * (1 - t * t)
        bridge.append((xx, CU.head_surface_y(xx, zz - HZ) * 0.97 - 0.08, zz))
    parts.append(assign(smooth(M.tube("Bridge", bridge, 0.022)), gold_m))
    # брови над очками: правая приподнята от любопытства
    for side, bz, arch in ((-1, HZ + 0.33, 0.02), (1, HZ + 0.41, 0.06)):
        x = side * 0.35
        pts = []
        for i in range(10):
            t = i / 9
            xx = x - side * 0.12 + side * 0.24 * t
            zz = bz + arch * math.sin(math.pi * t) + (0.02 * (1 - t) if side > 0 else 0.0)
            pts.append((xx, CU.head_surface_y(xx, zz - HZ) * 0.99 - 0.015, zz))
        parts.append(assign(smooth(M.tube(f"NewBrow{side}", pts, 0.036, taper=(1.0, 0.75))), brow_m))
    # тонкие усики с подкрученными кончиками и легкая улыбка
    mz = HZ - 0.245
    for side in (-1, 1):
        pts = []
        for i in range(12):
            t = i / 11
            xx = side * (0.03 + 0.24 * t)
            zz = mz + 0.07 * t ** 2.2 - 0.015 * math.sin(math.pi * t)
            pts.append((xx, CU.head_surface_y(xx, zz - HZ) * 0.985 - 0.04, zz))
        parts.append(assign(smooth(M.tube(f"Mustache{side}", pts, 0.042, taper=(1.0, 0.4))), hair_m))
    parts.append(CU.arc_tube("Smile", 0.03, HZ - 0.39, 0.26, 0.05, 0.028, lip))
    # водолазка: толстый вязаный ворот под подбородком
    knit = M.material("Knit", [(0.0, (0.10, 0.10, 0.13)), (1.0, (0.30, 0.30, 0.36))], coord="z", lo=0.0, hi=0.6,
                      rough=0.6, sheen=0.4)
    roll = torus("Turtleneck", 0.5, 0.15, 64, 24)
    roll.location = (0, 0.03, 0.34)
    apply_transform(roll)
    push_normals(roll, lambda co, n: 0.012 * math.sin(math.atan2(co.y, co.x) * 40))
    parts.append(assign(smooth(roll), knit))
    # тренч распахнут: в вырезе между лацканами видна водолазка
    body = bpy.data.objects["Body"]
    assign_faces(body, coat, [(lambda n, c: c.y < 0 and -0.5 < c.z < 0.5 and abs(c.x) < 0.12 + 0.34 * (c.z + 0.4) / 0.8,
                               knit)])
    # тренч: лацканы по груди и поднятый воротник за шеей
    lapel_m = M.material("Lapel", [(0.0, (0.66, 0.50, 0.30)), (1.0, (0.90, 0.74, 0.50))], coord="z", lo=-0.6, hi=0.6,
                         rough=0.45, coat=0.2, sheen=0.3)
    for side in (-1, 1):
        pts = []
        for i in range(14):
            t = i / 13
            x = side * (0.46 - 0.34 * t)
            z = 0.4 - 0.8 * t
            pts.append((x, body_y(x, z) - 0.03, z))
        lp = sweep(f"Lapel{side}", pts, lambda t: 0.17 - 0.04 * t, segs=24, section=(0.3, 1.0), up=(0, -1, 0))
        parts.append(assign(lp, lapel_m))
        btn = CU.ellipsoid(f"Button{side}", (0.055, 0.03, 0.055), M.flat("ButtonM", (0.32, 0.20, 0.12), rough=0.3,
                                                                        coat=0.6), 16, 10)
        btn.location = (side * 0.34, body_y(side * 0.34, -0.15) - 0.03, -0.15)
        parts.append(btn)
    # блокнот в левой руке (справа в кадре): бордовая обложка, листок с линейками, золотая звездочка-оценка
    pad = [I.slab("PadCover", I.rounded_rect(0.5, 0.64, 0.05), 0.05, 0.015,
                  M.flat("PadCoverM", (0.60, 0.12, 0.16), rough=0.4, coat=0.4))]
    page = I.slab("PadPage", I.rounded_rect(0.44, 0.54, 0.035), 0.03, 0.01,
                  M.flat("Paper", (0.99, 0.97, 0.92), rough=0.5), y=-0.035)
    page.location.z -= 0.03
    apply_transform(page)
    pad.append(page)
    ink = M.flat("Ink", (0.45, 0.55, 0.75), rough=0.5)
    for k, (w, z) in enumerate(((0.3, 0.1), (0.26, 0.0), (0.3, -0.1), (0.18, -0.2))):
        ln = I.slab(f"Line{k}", I.rounded_rect(w, 0.022, 0.01), 0.01, 0.0, ink, y=-0.055)
        ln.location = (-0.04 + (0.3 - w) / 2 * -1, 0, z)
        apply_transform(ln)
        pad.append(ln)
    star = I.slab("PadStar", I.star_pts(0.075, 0.034), 0.03, 0.008, I.gold(), y=-0.06)
    star.location = (0.13, 0, 0.17)
    apply_transform(star)
    pad.append(star)
    for k in range(5):
        sp = torus(f"Spiral{k}", 0.035, 0.011, 24, 8)
        sp.rotation_euler = (0, math.radians(90), 0)
        sp.location = (-0.16 + k * 0.08, -0.01, 0.31)
        apply_transform(sp)
        pad.append(assign(smooth(sp), M.flat("SpiralM", (0.8, 0.82, 0.86), rough=0.2, metal=1.0)))
    rotate_all(pad, (math.radians(-12), math.radians(-12), math.radians(-10)))
    for o in pad:
        o.location = o.location + Vector((0.66, -1.0, 0.12))
    parts += pad
    # руки в рукавах тренча: правая держит блокнот снизу, левая подносит ручку к подбородку
    for side, wrist, fist in ((1, (0.86, -1.0, -0.22), (0.86, -1.08, -0.1)),
                              (-1, (-0.6, -1.0, -0.12), (-0.5, -1.06, 0.02))):
        elbow = Vector((side * 1.05, -0.62, -0.9))
        sleeve = sweep(f"Sleeve{side}", [elbow, wrist], 0.2, segs=32)
        parts.append(assign(sleeve, coat))
        cuff = sweep(f"Cuff{side}", [Vector(wrist) - (Vector(wrist) - elbow).normalized() * 0.05, wrist], 0.215, segs=32)
        parts.append(assign(cuff, lapel_m))
        hand = CU.ellipsoid(f"Hand{side}", (0.2, 0.16, 0.2), skin, 32, 20)
        hand.location = fist
        thumb = CU.ellipsoid(f"Thumb{side}", (0.06, 0.05, 0.1), skin, 16, 10)
        thumb.rotation_euler = (0, math.radians(side * -30), 0)
        thumb.location = (fist[0] - side * 0.1, fist[1] - 0.1, fist[2] + 0.06)
        parts += [hand, thumb]
    # ручка: темный корпус, золотое кольцо, кончиком к подбородку
    p0, p1 = Vector((-0.58, -1.14, -0.12)), Vector((-0.27, -0.88, 0.3))
    dirv = (p1 - p0).normalized()
    pen_body = sweep("Pen", [p0, p1], 0.042, segs=24)
    parts.append(assign(pen_body, M.flat("PenM", (0.10, 0.10, 0.16), rough=0.2, coat=0.9)))
    ring = sweep("PenRing", [p1 - dirv * 0.09, p1 - dirv * 0.03], 0.046, segs=24)
    parts.append(assign(ring, gold_m))
    tip = I.cone_head("PenTip", p1 + dirv * 0.12, dirv, 0.04, 0.14, gold_m)
    parts.append(tip)
    portrait_frame()
    return parts


# MARK: - Иконки ивентов

def tomato_slice(name, r=0.17, th=0.045):
    """Кружок помидора: темная кожица по краю, светлая мякоть с семенными камерами."""
    ob = cylinder(name, r, th, 48)
    bevel(ob, th * 0.35, 3, 30)
    smooth(ob, 40)
    # как срез цитруса, только камеры светлые с семечками, а стенки и кожица красные
    mat = citrus_mat(f"{name}M", r, n=4, rind=(0.82, 0.07, 0.05), flesh=(1.0, 0.52, 0.34), memb=(0.94, 0.20, 0.13))
    add_speckles(mat, (1.0, 0.88, 0.45), scale=34.0, threshold=0.68, strength=0.9)
    return assign(ob, mat)


def golden_spoon(name):
    """Золотая поварская ложка: черпачок у начала координат (открыт вверх), ручка по +X."""
    g = I.gold()
    bowl = sphere(f"{name}Bowl", 1.0, 48, 24)
    bowl.scale = (0.34, 0.26, 0.13)
    apply_transform(bowl)
    bisect(bowl, (0, 0, 0.0), (0, 0, 1), fill=False)
    solidify(bowl, 0.03)
    assign(smooth(bowl), g)
    path = spline([(0.26, 0.0, 0.0), (0.6, 0.0, 0.08), (1.1, 0.0, 0.16), (1.55, 0.0, 0.2)], 8)
    handle = sweep(f"{name}Handle", path, lambda t: 0.065 - 0.015 * t + 0.035 * max(0.0, t - 0.85) / 0.15, segs=24,
                   section=(0.6, 1.0), up=(0, 0, 1))
    assign(handle, g)
    return [bowl, handle]


def place(parts, origin, xdir, zhint):
    """Ставит группу: локальная X вдоль xdir, Z как можно ближе к zhint."""
    x = Vector(xdir).normalized()
    z = Vector(zhint)
    z = (z - x * z.dot(x)).normalized()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    for o in parts:
        o.matrix_world = m @ o.matrix_world
    bpy.context.view_layer.update()
    return parts


def icon_recipe():
    """Большой рецепт: огромная пицца на круглой доске, помидоры, сыр, долька лайма, золотая ложка."""
    I._prep()
    board_m = wood("Board", (0.82, 0.54, 0.28), axis="x", rough=0.45, coat=0.4, grain=0.3)
    board = cylinder("Board", 1.22, 0.14, 128)
    board.location = (0, 0, 0.07)
    apply_transform(board)
    bevel(board, 0.05, 4, 30)
    parts = [assign(smooth(board, 30), board_m)]
    hd = box_mesh("BoardHandle", 0.62, 0.36, 0.14, 0.0)
    hd.rotation_euler = (0, 0, math.radians(35))
    hd.location = (1.32 * math.cos(math.radians(35)), 1.32 * math.sin(math.radians(35)), 0)
    apply_transform(hd)
    bevel(hd, 0.06, 4, 30)
    parts.append(assign(smooth(hd, 30), board_m))
    top = 0.14
    dough = cylinder("Dough", 0.98, 0.06, 96)
    dough.location = (0, 0, top + 0.03)
    apply_transform(dough)
    parts.append(assign(smooth(dough), I.toy("DoughM", (0.98, 0.78, 0.48), rough=0.5, coat=0.2)))
    crust = torus("Crust", 0.92, 0.12, 128, 24)
    crust.scale = (1, 1, 0.85)
    crust.location = (0, 0, top + 0.1)
    apply_transform(crust)
    push_normals(crust, lambda co, n: 0.018 * fbm(co * 4))
    parts.append(assign(smooth(crust), material("CrustM", [(0.0, (0.86, 0.52, 0.20)), (0.6, (0.96, 0.68, 0.32)),
                                                           (1.0, (0.78, 0.40, 0.14))], coord="z", lo=top + 0.02,
                                                hi=top + 0.21, rough=0.5, sss=0.2, coat=0.3)))
    sauce = cylinder("Sauce", 0.86, 0.03, 96)
    sauce.location = (0, 0, top + 0.075)
    apply_transform(sauce)
    parts.append(assign(smooth(sauce), I.toy("SauceM", (0.86, 0.18, 0.10), rough=0.25, coat=0.7)))
    cheese_c = ((0.0, 0.0, 0.5), (0.4, 0.3, 0.32), (-0.35, 0.4, 0.3), (-0.45, -0.25, 0.32), (0.2, -0.5, 0.3),
                (0.55, -0.15, 0.24))

    def reach(a):
        dx, dy = math.cos(a), math.sin(a)
        acc = 0.0
        for cx, cy, r in cheese_c:
            b = cx * dx + cy * dy
            q = r * r - (cx * cx + cy * cy - b * b)
            if q > 0:
                acc += max(0.0, b + math.sqrt(q)) ** 8
        return acc ** (1 / 8)
    # расплавленный сыр: тонкая линза по контуру из кругов, края сходят на нет
    ch = quad_sphere("Cheese", 32)

    def melt(co):
        d = reach(math.atan2(co.y, co.x))
        return Vector((co.x * d, co.y * d, max(co.z, -0.3) * 0.05 + top + 0.1))
    deform(ch, melt)
    parts.append(assign(smooth(ch), I.toy("CheeseM", (1.0, 0.78, 0.26), rough=0.2, coat=0.8)))
    for k in range(4):
        a = math.radians(20 + 90 * k)
        sl = tomato_slice(f"Slice{k}", 0.23, 0.05)
        sl.location = (0.54 * math.cos(a), 0.54 * math.sin(a), top + 0.15)
        parts.append(sl)
    for k, (x, y, a) in enumerate(((-0.3, 0.1, 100), (0.3, -0.12, 300), (0.05, 0.4, 200))):
        lf = leaf(f"Basil{k}", length=0.3, width=0.18, fold=0.15, curl=0.1, thick=0.02, petiole=0.03)
        rotate_all(lf, (0, 0, math.radians(a)))
        for o in lf:
            o.location = o.location + Vector((x, y, top + 0.13))
        parts += lf
    # половинка лайма стоит в середине, срезом к камере
    lime = cylinder("Lime", 0.4, 0.15, 64)
    bevel(lime, 0.05, 3, 30)
    bisect(lime, (0, 0, 0), (0, -1, 0))
    smooth(lime, 40)
    assign(lime, citrus_mat("LimeM", 0.4, n=8, rind=(0.36, 0.72, 0.14), flesh=(0.72, 0.92, 0.36),
                            memb=(0.94, 1.0, 0.82)))
    lime.matrix_world = (Matrix.Translation((0.0, -0.06, top + 0.12)) @ Matrix.Rotation(math.radians(-10), 4, "Z")
                         @ Matrix.Rotation(math.radians(90), 4, "X"))
    parts.append(lime)
    spoon = golden_spoon("Spoon")
    place(spoon, (0.74, 0.2, 1.62), (0.36, 0.4, -1.5), (0.2, -1.0, 0.3))
    parts += spoon
    rotate_all(parts, (math.radians(14), 0, 0))
    return I.finish(parts, tilt=8)


def sprout(name, x, y, z, h=0.24, lean=0.0, size=1.0):
    """Росток: стебелек и два круглых листика галочкой."""
    green = I.toy("SproutGreen", (0.42, 0.80, 0.24), rough=0.3, coat=0.6)
    pts = spline([(x, y, z - 0.05), (x + lean * 0.4, y, z + h * 0.5), (x + lean, y, z + h)], 6)
    parts = [assign(sweep(f"{name}Stem", pts, 0.025 * size, segs=12), green)]
    for side in (-1, 1):
        lf = sphere(f"{name}Leaf{side}", 1.0, 24, 12)
        lf.scale = (0.13 * size, 0.07 * size, 0.022 * size)
        apply_transform(lf)
        deform(lf, lambda co: co + Vector((0, 0, 0.6 * co.x * co.x / size)))
        lf.rotation_euler = (0, math.radians(side * -30), 0)
        lf.location = (x + lean + side * 0.11 * size, y, z + h + 0.04 * size)
        apply_transform(lf)
        parts.append(assign(smooth(lf), green))
    return parts


def icon_garden():
    """Грядка: деревянный ящик с темной землей, ростки и спелый помидор на подвязанном стебле."""
    I._prep()
    W, D, H = 1.56, 0.8, 0.62
    xl, xr, yf, yb = -W / 2, W / 2, -D / 2, D / 2
    plank_m = wood("Plank", (0.82, 0.52, 0.27), axis="x", rough=0.45, coat=0.4, grain=0.35)
    plank2_m = wood("Plank2", (0.76, 0.46, 0.23), axis="x", rough=0.45, coat=0.4, grain=0.35)
    post_m = wood("Post", (0.70, 0.42, 0.21), axis="z", rough=0.45, coat=0.4, grain=0.35)
    parts = [rbox("Inside", xl + 0.05, xr - 0.05, yf + 0.05, yb - 0.05, 0.02, H - 0.04,
                  flat("Inside", (0.22, 0.12, 0.06), rough=0.8), 0.0)]
    for k, (z0, z1) in enumerate(((0.0, 0.3), (0.32, H))):
        m = plank_m if k else plank2_m
        parts.append(rbox(f"Front{k}", xl + 0.06, xr - 0.06, yf - 0.02, yf + 0.06, z0, z1, m, 0.025))
        parts.append(rbox(f"Back{k}", xl + 0.06, xr - 0.06, yb - 0.06, yb + 0.02, z0, z1, m, 0.025))
        for sx in (-1, 1):
            x0, x1 = (xr - 0.06, xr + 0.02) if sx > 0 else (xl - 0.02, xl + 0.06)
            parts.append(rbox(f"Side{sx}{k}", x0, x1, yf + 0.04, yb - 0.04, z0, z1, m, 0.025))
    for k, (x, y) in enumerate(((xl, yf), (xr, yf), (xl, yb), (xr, yb))):
        parts.append(rbox(f"Post{k}", x - 0.08, x + 0.08, y - 0.08, y + 0.08, 0.0, H + 0.07, post_m, 0.035))
    soil = box_mesh("Soil", W - 0.14, D - 0.14, 0.2, H - 0.24, cuts=24)
    deform(soil, lambda co: co + Vector((0, 0, (0.035 * fbm(co * 5) + 0.03 * math.cos(co.x * 1.6)) if co.z > H - 0.05
                                         else 0.0)))
    soil_m = material("Soil", [(0.0, (0.20, 0.12, 0.07)), (1.0, (0.40, 0.25, 0.13))], coord="z", lo=H - 0.08,
                      hi=H + 0.02, rough=0.9, bump=0.6, bump_scale=30, vary=0.15, vary_scale=6)
    parts.append(assign(smooth(soil), soil_m))
    for k, (x, y, h, lean) in enumerate(((-0.5, -0.06, 0.3, -0.03), (-0.14, 0.04, 0.24, 0.02))):
        parts += sprout(f"Sprout{k}", x, y, H - 0.02, h, lean, 1.25)
    # помидорный куст у колышка
    sx = 0.36
    stake = cylinder("Stake", 0.035, 1.35, 16)
    stake.location = (sx + 0.06, 0.12, H + 0.6)
    apply_transform(stake)
    parts.append(assign(smooth(stake), I.toy("StakeM", (0.86, 0.66, 0.40), rough=0.5)))
    vine_m = I.toy("Vine", (0.30, 0.62, 0.18), rough=0.35, coat=0.5)
    vine = []
    for i in range(41):
        t = i / 40
        a = t * math.pi * 3.2
        vine.append((sx + 0.06 + 0.07 * math.cos(a), 0.12 - 0.07 * math.sin(a), H - 0.02 + 1.2 * t))
    parts.append(assign(sweep("Vine", vine, lambda t: 0.04 - 0.015 * t, segs=16), vine_m))
    for k, (z, ang, ln) in enumerate(((0.45, 160, 0.42), (0.85, 20, 0.4), (1.12, 140, 0.32), (0.25, 40, 0.3))):
        lf = leaf(f"TLeaf{k}", length=ln, width=ln * 0.55, fold=0.1, curl=-0.15, thick=0.02, petiole=0.04, serr=0.12)
        rotate_all(lf, (math.radians(-20), math.radians(-25), math.radians(ang)))
        for o in lf:
            o.location = o.location + Vector((sx + 0.06, 0.12, H + z))
        parts += lf
    truss = spline([(sx + 0.08, 0.06, H + 0.74), (sx + 0.22, -0.08, H + 0.72), (sx + 0.29, -0.17, H + 0.6)], 6)
    parts.append(assign(sweep("Truss", truss, 0.025, segs=12), vine_m))
    before = set(bpy.data.objects)
    tomato()
    tom = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    for o in tom:
        o.matrix_world = Matrix.Translation((sx + 0.3, -0.18, H + 0.34)) @ Matrix.Scale(0.31, 4) @ o.matrix_world
    parts += tom
    return I.finish(parts, tilt=10)


def glass(name, tint=(0.93, 0.97, 1.0), edge=(0.70, 0.86, 1.0), center=0.06, rim=0.85):
    """Стекло для иконки: посередине прозрачное с голубым оттенком, к краям светлое голубоватое и блестящее."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*lin(edge), 1)
    bsdf.inputs["Roughness"].default_value = 0.05
    bsdf.inputs["Coat Weight"].default_value = 1.0
    bsdf.inputs["Coat Roughness"].default_value = 0.02
    out = nodes["Material Output"]
    tr = nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (*lin(tint), 1)
    lw = nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = center
    mr.inputs["To Max"].default_value = rim
    links.new(lw.outputs["Facing"], mr.inputs["Value"])
    mix = nodes.new("ShaderNodeMixShader")
    links.new(mr.outputs["Result"], mix.inputs["Fac"])
    links.new(tr.outputs[0], mix.inputs[1])
    links.new(bsdf.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def icon_jar():
    """Банка-копилка: широкая стеклянная банка, на три четверти полная монет, красная жестяная крышка, монеты сверху."""
    I._prep()
    rnd = random.Random(21)
    prof = [(1.18, 0.0), (1.36, 0.06), (1.44, 0.3), (1.47, 1.2), (1.44, 2.2), (1.34, 2.55), (1.22, 2.72), (1.2, 2.95)]
    outer = [(r, z) for r, _, z in spline([(r, 0.0, z) for r, z in prof], 8)]
    jar = lathe("Jar", [(0.0, 0.0)] + outer, 128)
    smooth(jar)
    # монеты насыпаем физикой в невидимый цилиндр чуть уже стекла
    wall = lathe("Wall", [(0.0, 0.07), (1.37, 0.07), (1.37, 3.6)], 64)
    coins_ = C.deposit("Jar", 84, 0.92, rnd, statics=[wall], per_wave=8, frames=60, tilt=0.5)
    bpy.data.objects.remove(wall)
    # монеты выше трех четвертей (застрявшие у горлышка) убираем
    for c in list(coins_):
        if c.matrix_world.translation.z > 2.3:
            coins_.remove(c)
            bpy.data.objects.remove(c)
    assign(jar, glass("Glass"))
    # стекло не дает тени: монеты внутри светлые, как на витрине
    jar.visible_shadow = False
    parts = [jar] + coins_
    lid = cylinder("Lid", 1.3, 0.34, 128)
    lid.location = (0, 0, 2.95 + 0.15)
    apply_transform(lid)
    push_normals(lid, lambda co, n: -0.02 * (0.5 + 0.5 * math.cos(math.atan2(co.y, co.x) * 48))
                 if abs(n.z) < 0.5 else 0.0)
    bevel(lid, 0.07, 4, 30)
    parts.append(assign(smooth(lid, 30), I.toy("LidRed", (0.90, 0.18, 0.20), rough=0.25, coat=0.9, metal=0.3)))
    top = 2.95 + 0.32
    st = C.stack("TopCoin", 0.38, -0.12, 2, rnd, z0=top, jitter=0.06)
    flat_ = C.coin("TopFlat", loc=(-0.36, -0.36, top + 0.062), rot=(0.03, -0.02, 1.1))
    parts += st + [flat_]
    # блики на стекле: две белые полоски слева
    shine_m = glow_mat("ShineW", (1.0, 1.0, 1.0), 1.0)
    for k, (a, z0, z1, r) in enumerate(((-128, 0.4, 2.2, 0.1), (-110, 0.6, 1.4, 0.06), (-110, 1.62, 1.86, 0.06))):
        ar = math.radians(a)
        pts = [(1.5 * math.cos(ar), 1.5 * math.sin(ar), z0 + (z1 - z0) * i / 12) for i in range(13)]
        parts.append(assign(sweep(f"Shine{k}", pts, r, segs=16, section=(0.3, 1.0), up=(math.cos(ar), math.sin(ar), 0)),
                            shine_m))
    return I.finish(parts, tilt=8)


def icon_happy():
    """Счастливый час: розовый будильник с золотыми колокольчиками, стрелки на 10:10 (улыбка), золотые искорки."""
    I._prep()
    pink = I.toy("ClockPink", (0.95, 0.30, 0.62), rough=0.22, coat=0.9)
    g = I.gold()
    plum = I.toy("Hands", (0.36, 0.10, 0.32), rough=0.25, coat=0.8)
    parts = [I.disc("Body", 0.86, 0.5, pink)]
    rim = torus("Rim", 0.72, 0.06, 96, 16)
    rim.rotation_euler = (math.radians(90), 0, 0)
    rim.location = (0, -0.25, 0)
    apply_transform(rim)
    parts.append(assign(smooth(rim), g))
    parts.append(I.disc("Dial", 0.7, 0.06, I.white("Dial"), y=-0.24))
    for k in range(12):
        a = math.radians(90 - 30 * k)
        big = k % 3 == 0
        d = sphere(f"Tick{k}", 0.055 if big else 0.032, 16, 8)
        d.scale = (1, 0.5, 1)
        d.location = (0.55 * math.cos(a), -0.28, 0.55 * math.sin(a))
        apply_transform(d)
        parts.append(assign(smooth(d), pink if big else plum))
    for k, (ang, ln, w) in enumerate(((150, 0.34, 0.085), (30, 0.5, 0.065))):
        hand = I.slab(f"Hand{k}", I.rounded_rect(ln, w, w / 2 - 0.002), 0.04, 0.012, plum, y=-0.3 - 0.02 * k)
        hand.location.x += ln / 2 - w / 2
        apply_transform(hand)
        hand.rotation_euler = (0, -math.radians(ang), 0)
        apply_transform(hand)
        parts.append(hand)
    cap = I.disc("Cap", 0.07, 0.06, g, y=-0.35)
    parts.append(cap)
    # колокольчики и молоточек
    bell_prof = [(0.0, 0.0), (0.3, 0.0), (0.31, 0.03), (0.28, 0.12), (0.22, 0.24), (0.12, 0.3), (0.0, 0.31)]
    for side in (-1, 1):
        bell = lathe_smooth(f"Bell{side}", bell_prof, 64, 4)
        knob = sphere(f"Knob{side}", 0.06, 16, 8)
        knob.location = (0, 0, 0.33)
        apply_transform(knob)
        post = cylinder(f"BellPost{side}", 0.035, 0.25, 16)
        post.location = (0, 0, -0.1)
        apply_transform(post)
        grp = [assign(smooth(bell), g), assign(smooth(knob), g), assign(smooth(post), g)]
        a = math.radians(90 - side * 42)
        rotate_all(grp, (0, math.radians(side * 40), 0))
        for o in grp:
            o.location = o.location + Vector((0.86 * math.cos(a), 0.05, 0.86 * math.sin(a)))
        parts += grp
    stick = cylinder("Hammer", 0.03, 0.22, 16)
    stick.location = (0, 0.05, 0.92)
    apply_transform(stick)
    ball = sphere("HammerBall", 0.07, 16, 8)
    ball.location = (0, 0.05, 1.05)
    apply_transform(ball)
    parts += [assign(smooth(stick), g), assign(smooth(ball), g)]
    for side in (-1, 1):
        leg = M.capsule(f"Leg{side}", 0.3, 0.07, 16, 12)
        leg.rotation_euler = (0, math.radians(90 + side * -35), 0)
        leg.location = (side * 0.5, 0.05, -0.82)
        apply_transform(leg)
        parts.append(assign(smooth(leg), g))
    # искорки близко к часам: на 30 точках будильник остается крупным
    for k, (x, z, r) in enumerate(((-1.08, 0.6, 0.2), (1.1, 0.12, 0.16), (-0.98, -0.62, 0.12), (0.98, 0.9, 0.11))):
        st = I.slab(f"Sparkle{k}", I.star_pts(r, r * 0.3, n=4), 0.08, 0.025, g)
        st.location = (x, 0, z)
        apply_transform(st)
        parts.append(st)
    return I.finish(parts, tilt=6)


M.MODELS.update({
    "m3_pin": m3_pin,
    "m3_bomb": m3_bomb,
    "m3_whisk": m3_whisk,
    "m3_rainbow": m3_rainbow,
    "m3_crate_1": lambda: crate(1),
    "m3_crate_2": lambda: crate(2),
    "m3_crate_3": lambda: crate(3),
    "m3_jam": m3_jam,
    "icon_m3_mallet": icon_m3_mallet,
    "icon_m3_knife": icon_m3_knife,
    "icon_m3_spatula": icon_m3_spatula,
    "icon_m3_mixer": icon_m3_mixer,
    "icon_market": icon_market,
    "critic": critic,
    "icon_recipe": icon_recipe,
    "icon_garden": icon_garden,
    "icon_jar": icon_jar,
    "icon_happy": icon_happy,
})
