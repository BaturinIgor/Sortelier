"""Мексиканская кухня (биом 4): ингредиенты, закуски и блюда."""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

import models as M
from models import *  # noqa: F401,F403  помощники


# MARK: - Помощники

def mix(a, b, t):
    t = min(1.0, max(0.0, t))
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def vcol(ob, fn, name="Col"):
    """Цвет по вершинам: fn(co, normal) -> (r, g, b) в sRGB."""
    me = ob.data
    # нормали читаем заранее: запись атрибута сбрасывает их кеш
    data = [(v.co.copy(), v.normal.copy()) for v in me.vertices]
    cols = []
    for co, n in data:
        cols.extend((*lin(fn(co, n)), 1.0))
    attr = me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    attr.data.foreach_set("color", cols)
    return ob


def vmat(name, attr="Col", **kw):
    """Материал с цветом из атрибута вершин."""
    mat = material(name, [(0.0, (1, 1, 1)), (1.0, (1, 1, 1))], **kw)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    at = nodes.new("ShaderNodeAttribute")
    at.attribute_name = attr
    links.new(at.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    return mat


def glow(mat, color, strength=0.2):
    """Легкое свечение: белые жидкости не уходят в серый."""
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Emission Color"].default_value = (*lin(color), 1)
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def add_turns(mat, color, count=8, width=0.5, twist=0.0, strength=1.0):
    """Полоски вокруг оси Z: бумажный кулек, трубочка. twist - закрутка на единицу высоты."""
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    grad = nodes.new("ShaderNodeTexGradient")
    grad.gradient_type = "RADIAL"
    links.new(tc.outputs["Object"], grad.inputs["Vector"])
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    tw = nodes.new("ShaderNodeMath")
    tw.operation = "MULTIPLY_ADD"
    links.new(sep.outputs["Z"], tw.inputs[0])
    tw.inputs[1].default_value = twist
    links.new(grad.outputs["Fac"], tw.inputs[2])
    sc = nodes.new("ShaderNodeMath")
    sc.operation = "MULTIPLY"
    sc.inputs[1].default_value = count
    links.new(tw.outputs[0], sc.inputs[0])
    fr = nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    links.new(sc.outputs[0], fr.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    s = (strength, strength, strength, 1)
    els[0].position, els[0].color = 0.0, s
    els[1].position, els[1].color = 1.0, s
    e = els.new(max(0.0, width - 0.02))
    e.color = s
    e = els.new(min(1.0, width + 0.02))
    e.color = (0, 0, 0, 1)
    e = els.new(0.98)
    e.color = (0, 0, 0, 1)
    links.new(fr.outputs[0], ramp.inputs["Fac"])
    M._mix_over(mat, ramp.outputs["Color"], color)
    return mat


def checker_mat(name, c1, c2, scale=3.0, **kw):
    """Клетка: бумажная подложка."""
    mat = material(name, [(0.0, c1), (1.0, c1)], **kw)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tc = nodes.new("ShaderNodeTexCoord")
    ch = nodes.new("ShaderNodeTexChecker")
    ch.inputs["Scale"].default_value = scale
    ch.inputs["Color1"].default_value = (*lin(c1), 1)
    ch.inputs["Color2"].default_value = (*lin(c2), 1)
    links.new(tc.outputs["Object"], ch.inputs["Vector"])
    links.new(ch.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    return mat


def rcube(name, sx, sy, sz, p=4.0, cuts=5):
    """Кубик со скругленными гранями: суперэллипсоид."""
    ob = quad_sphere(name, cuts)

    def fn(co):
        k = 1.0 / ((abs(co.x) ** p + abs(co.y) ** p + abs(co.z) ** p) ** (1.0 / p))
        return Vector((co.x * k * sx, co.y * k * sy, co.z * k * sz))
    deform(ob, fn)
    return smooth(ob)


def reach_fn(pts, center=(0.0, 0.0)):
    """Расстояние от центра до контура pts по направлению a (контур выпуклый вокруг центра)."""
    cx, cy = center
    segs = [((pts[i][0] - cx, pts[i][1] - cy), (pts[(i + 1) % len(pts)][0] - cx, pts[(i + 1) % len(pts)][1] - cy))
            for i in range(len(pts))]
    cache = {}

    def reach(a):
        key = round(a, 5)
        if key in cache:
            return cache[key]
        dx, dy = math.cos(a), math.sin(a)
        best = 1e9
        for (x1, y1), (x2, y2) in segs:
            ex, ey = x2 - x1, y2 - y1
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            t = (x1 * ey - y1 * ex) / den
            u = (x1 * dy - y1 * dx) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = min(best, t)
        cache[key] = best
        return best
    return reach


def outline_slab(name, pts, h, p=3.0, cuts=28, center=(0.0, 0.0)):
    """Плитка по контуру pts толщиной h со скругленным краем: стейк, чипс, долька кесадильи."""
    ob = quad_sphere(name, cuts)
    reach = reach_fn(pts, center)
    half = h / 2

    def fn(co):
        rr = math.hypot(co.x, co.y)
        k = 1.0 / ((rr ** p + abs(co.z) ** p) ** (1.0 / p))
        a = math.atan2(co.y, co.x)
        d = reach(a)
        return Vector((center[0] + co.x * k * d, center[1] + co.y * k * d, co.z * k * half))
    return deform(ob, fn)


def polar_outline(fn, n=96):
    return [(fn(2 * math.pi * i / n) * math.cos(2 * math.pi * i / n), fn(2 * math.pi * i / n) * math.sin(2 * math.pi * i / n))
            for i in range(n)]


def ground(objs, z=0.0):
    """Ставит группу на высоту z нижней точкой."""
    bpy.context.view_layer.update()
    lo, _, _ = z_range(objs)
    for o in objs:
        o.location.z += z - lo
    bpy.context.view_layer.update()
    return objs


def z_range(objs):
    """Нижняя и верхняя точка группы по Z."""
    zs = []
    for o in objs:
        mw = o.matrix_world
        zs += [(mw @ v.co).z for v in o.data.vertices]
    return min(zs), max(zs), None


def world_tree(ob, dz=0.0):
    mw = ob.matrix_world
    verts = [mw @ v.co + Vector((0, 0, dz)) for v in ob.data.vertices]
    return BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in ob.data.polygons]), verts


def drop(objs, others, floor=0.0, step=0.012, top=None):
    """Опускает объекты сверху, пока они не коснутся других: куча без пересечений."""
    if not isinstance(objs, (list, tuple)):
        objs = [objs]
    bpy.context.view_layer.update()
    trees = [world_tree(o)[0] for o in others]
    bases = []
    for ob in objs:
        mw = ob.matrix_world
        bases.append(([mw @ v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons]))
    zmin = min(v.z for b, _ in bases for v in b)
    dz = (top if top is not None else zmin + 3.0) - zmin
    while True:
        nz = dz - step
        if zmin + nz < floor:
            break
        hit = False
        for b, polys in bases:
            tree = BVHTree.FromPolygons([v + Vector((0, 0, nz)) for v in b], polys)
            if any(tree.overlap(t) for t in trees):
                hit = True
                break
        if hit:
            break
        dz = nz
    for ob in objs:
        ob.location.z += dz
    bpy.context.view_layer.update()
    return objs


def husk_mat(name):
    return vmat(name, rough=0.5, sss=0.3, sss_radius=(1, 0.9, 0.5), coat=0.25, coat_rough=0.2, sheen=0.35,
                bump=0.12, bump_scale=30)


def husk_colors(ob, across, along, palette=None, lines=5.5):
    """Сухой лист: солома с тонкими продольными прожилками. across(co) - поперек, along(co) - вдоль 0..1."""
    base, dark, light, end = palette or ((0.92, 0.80, 0.52), (0.74, 0.58, 0.32), (0.99, 0.93, 0.74), (0.86, 0.74, 0.46))

    def col(co, n):
        v = across(co)
        f = (v * lines + 0.03 * fbm(co * 2)) % 1.0
        line = smoothstep(0.2, 0.0, min(f, 1 - f))
        c = mix(light, base, 0.35 + 0.5 * min(1.0, abs(v)))
        c = mix(c, end, 0.6 * along(co))
        return mix(c, dark, 0.7 * line)
    return vcol(ob, col)


def tortilla_mat(name, r=1.0):
    mat = material(name, [(0.0, (1.0, 0.91, 0.68)), (0.7, (0.99, 0.86, 0.58)), (1.0, (0.93, 0.73, 0.42))],
                   coord="r", lo=0.0, hi=r, rough=0.5, sss=0.3, sss_radius=(1, 0.8, 0.5), coat=0.15, sheen=0.25,
                   bump=0.08, bump_scale=20, vary=0.08, vary_scale=4)
    add_speckles(mat, (0.88, 0.60, 0.26), scale=5.5 / r, threshold=0.60, strength=0.7)
    add_speckles(mat, (0.56, 0.32, 0.12), scale=15.0 / r, threshold=0.675, strength=0.85)
    return mat


CLAY = [(0.0, (0.56, 0.23, 0.10)), (0.55, (0.78, 0.38, 0.17)), (1.0, (0.92, 0.54, 0.28))]
CREAM = (1.0, 0.93, 0.78)


def clay_mat(name, lo, hi, bands=()):
    """Терракота с градиентом по высоте и расписными кремовыми поясками."""
    stops = list(CLAY)

    def at(p):
        for (p0, c0), (p1, c1) in zip(stops, stops[1:]):
            if p0 <= p <= p1:
                return mix(c0, c1, (p - p0) / (p1 - p0))
        return stops[-1][1]
    extra = []
    for p, w in bands:
        extra += [(p - w - 0.006, at(p - w - 0.006)), (p - w, CREAM), (p + w, CREAM), (p + w + 0.006, at(p + w + 0.006))]
    stops = sorted(stops + extra)
    return material(name, stops, coord="z", lo=lo, hi=hi, rough=0.42, coat=0.4, coat_rough=0.15, bump=0.05,
                    bump_scale=12, vary=0.05)


def stone_mat(name, lo, hi):
    mat = material(name, [(0.0, (0.15, 0.13, 0.13)), (0.55, (0.27, 0.24, 0.23)), (1.0, (0.40, 0.37, 0.35))],
                   coord="z", lo=lo, hi=hi, rough=0.5, coat=0.3, coat_rough=0.25, bump=0.45, bump_scale=26,
                   bump_detail=6, vary=0.12, vary_scale=5)
    add_speckles(mat, (0.52, 0.49, 0.47), scale=42, threshold=0.67, strength=0.6)
    return mat


def molcajete(name, s=1.0):
    """Каменная ступка на трех ножках."""
    prof = [(0.0, 0.16), (0.30, 0.16), (0.48, 0.20), (0.66, 0.32), (0.78, 0.48), (0.82, 0.60), (0.80, 0.68),
            (0.74, 0.72), (0.66, 0.70), (0.58, 0.58), (0.44, 0.46), (0.22, 0.40), (0.0, 0.39)]
    bowl = lathe(name, [(r * s, z * s) for r, z in prof], 96)
    subdivide(bowl, 1)
    push_normals(bowl, lambda co, n: 0.008 * s * fbm(co * 6 / s))
    smooth(bowl)
    mat = stone_mat(f"{name}Mat", 0.0, 0.72 * s)
    assign(bowl, mat)
    parts = [bowl]
    for i in range(3):
        a = math.radians(-90 + 120 * i)
        foot = lathe(f"{name}Foot{i}", [(0.0, 0.0), (0.08 * s, 0.0), (0.11 * s, 0.03 * s), (0.14 * s, 0.22 * s),
                                        (0.0, 0.24 * s)], 32)
        foot.location = (0.42 * s * math.cos(a), 0.42 * s * math.sin(a), 0.0)
        apply_transform(foot)
        subdivide(foot, 1)
        assign(smooth(foot), mat)
        parts.append(foot)
    return parts


def bowl_fill(name, r, z0, dome, mat, noise=0.02, seed=0):
    """Горка начинки в миске: диск с куполом и бугорками."""
    ob = polar_disc(name, 28, 128, r, r)
    off = Vector((seed * 3.1, seed * 1.7, 0))

    def fn(co):
        rr = math.hypot(co.x, co.y) / r
        z = z0 + dome * (1 - rr * rr) + noise * fbm((co + off) * 4.0 / r) * (1 - rr ** 4)
        return Vector((co.x, co.y, z))
    deform(ob, fn)
    smooth(ob)
    assign(ob, mat)
    return ob


def cilantro(name, s=0.12):
    """Листик кинзы: три лопасти с зубчиками."""
    ob = polar_disc(name, 6, 48, 1, 1)

    def fn(co):
        a = math.atan2(co.y, co.x)
        rr = math.hypot(co.x, co.y)
        k = (0.5 + 0.5 * abs(math.cos(1.5 * a)) ** 0.7) * (1.0 + 0.1 * math.sin(9 * a))
        return Vector((co.x * k * s, co.y * k * s, 0.25 * s * rr * rr))
    deform(ob, fn)
    solidify(ob, 0.18 * s)
    return smooth(ob)


def herb_mat(name):
    return material(name, [(0.0, (0.16, 0.50, 0.10)), (1.0, (0.40, 0.76, 0.20))], coord="z", lo=-0.05, hi=0.05,
                    rough=0.3, sss=0.3, sss_radius=(0.5, 1.0, 0.3), coat=0.5)


def citrus_face(name, R, segs=10, rind=(0.27, 0.58, 0.10), pulp=(0.80, 0.92, 0.40), relief=0.03):
    """Срез цитруса: корка, белая кайма и выпуклые дольки с перепонками (цвет по вершинам)."""
    ob = polar_disc(name, 36, 200, R, R)
    pith = (0.97, 0.99, 0.88)

    def seg_t(co):
        a = math.atan2(co.y, co.x) + math.pi
        f = (a / (2 * math.pi) * segs) % 1.0
        return f

    def fn(co):
        rr = math.hypot(co.x, co.y) / R
        f = seg_t(co)
        across = math.sin(math.pi * f) ** 0.6
        along = math.sin(math.pi * min(1.0, max(0.0, (rr - 0.1) / 0.76))) ** 0.5
        z = relief * R * across * along if rr < 0.86 else 0.0
        return Vector((co.x, co.y, z))

    def col(co, n):
        rr = math.hypot(co.x, co.y) / R
        if rr > 0.95:
            return rind
        if rr > 0.87:
            return mix(pith, rind, (rr - 0.87) / 0.08 * 0.25)
        f = seg_t(co)
        d = min(f, 1 - f) * 2 * math.pi * rr / segs
        if rr < 0.1 or d < 0.022:
            return pith
        return mix(mix(pulp, (0.92, 0.97, 0.66), 0.45 * (1 - rr)), (1.0, 1.0, 0.9), 0.3 * fbm(co * 18 / R + Vector((3, 1, 0))))
    vcol(ob, col)
    deform(ob, fn)
    smooth(ob)
    assign(ob, vmat(f"{name}Mat", rough=0.12, sss=0.4, sss_radius=(0.8, 1.0, 0.4), coat=0.8, coat_rough=0.05))
    return ob


def lime_body(name, R=0.5):
    ob = sphere(name, 1.0, 72, 48)

    def fn(co):
        x, y, z = co
        # слегка вытянут, на одном конце сосочек
        nub = 0.12 * math.exp(-(y * y + z * z) / 0.025) if x > 0 else 0.03 * math.exp(-(y * y + z * z) / 0.02)
        return Vector(((x * 1.1 + nub * (1 if x > 0 else -1)) * R, y * R, z * R))
    deform(ob, fn)
    return smooth(ob)


def lime_skin_mat(name, R=0.5):
    return material(name, [(0.0, (0.16, 0.42, 0.07)), (0.5, (0.27, 0.58, 0.11)), (1.0, (0.50, 0.78, 0.20))],
                    coord="z", lo=-R, hi=R, rough=0.3, sss=0.15, coat=0.7, coat_rough=0.1, bump=0.2,
                    bump_scale=40 / R * 0.5, vary=0.08)


def chip(name, s=0.42, curve=0.35, seed=0):
    """Треугольный кукурузный чипс, чуть выгнутый."""
    ob = outline_slab(name, rounded_triangle(s, 0.07, 10), 0.04, p=2.4, cuts=18)
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 10)
    deform(ob, lambda co: Vector((co.x, co.y, co.z - curve * (co.x * co.x + 0.6 * co.y * co.y) / s
                                  + 0.02 * fbm(co * 3 + Vector((ph, 0, 0))))))
    return smooth(ob)


def chip_mat(name):
    mat = material(name, [(0.0, (0.90, 0.52, 0.10)), (0.4, (0.99, 0.72, 0.20)), (1.0, (1.0, 0.84, 0.36))],
                   coord="r", lo=0.4, hi=0.0, rough=0.38, sss=0.3, sss_radius=(1, 0.7, 0.2), coat=0.3, bump=0.25,
                   bump_scale=22, vary=0.12, vary_scale=6)
    add_speckles(mat, (0.86, 0.52, 0.14), scale=24, threshold=0.66, strength=0.6)
    return mat


def talavera_plate(name="Plate", r=1.2, rim=(0.14, 0.32, 0.72)):
    """Тарелка в стиле талавера: белая с синим бортом и желтой каймой."""
    ob = lathe(name, [(0.0, 0.0), (r * 0.62, 0.0), (r * 0.66, 0.03), (r * 0.7, 0.07), (r * 0.98, 0.16), (r, 0.2),
                      (r * 0.96, 0.21), (r * 0.68, 0.1), (0.0, 0.09)], 96)
    subdivide(ob, 1)
    smooth(ob, 50)
    white = (0.98, 0.97, 0.94)
    gold = (1.0, 0.78, 0.22)
    assign(ob, material(f"{name}Mat", [(0.0, white), (0.62, white), (0.64, gold), (0.68, gold), (0.70, white),
                                       (0.76, white), (0.78, rim), (1.0, mix(rim, (0, 0, 0), 0.15))],
                        coord="r", lo=0.0, hi=r, rough=0.15, coat=0.8))
    return ob


def clay_plate(name="ClayPlate", r=1.2):
    ob = lathe(name, [(0.0, 0.0), (r * 0.6, 0.0), (r * 0.66, 0.03), (r * 0.7, 0.07), (r * 0.98, 0.17), (r, 0.21),
                      (r * 0.96, 0.22), (r * 0.68, 0.1), (0.0, 0.09)], 96)
    subdivide(ob, 1)
    smooth(ob, 50)
    assign(ob, clay_mat(f"{name}Mat", 0.0, 0.22, bands=((0.86, 0.035),)))
    return ob


# MARK: - Ингредиенты

def masa():
    prof = [(0.0, 0.0), (0.36, 0.0), (0.40, 0.02), (0.43, 0.06), (0.58, 0.16), (0.72, 0.32), (0.78, 0.44),
            (0.80, 0.50), (0.78, 0.54), (0.72, 0.54), (0.68, 0.48), (0.60, 0.34), (0.44, 0.20), (0.0, 0.17)]
    bowl = lathe("MasaBowl", prof, 96)
    subdivide(bowl, 1)
    smooth(bowl)
    assign(bowl, clay_mat("MasaBowlMat", 0.0, 0.54, bands=((0.62, 0.025),)))
    dough_ = sphere("Masa", 0.66, 72, 48)

    def shape(co):
        z = co.z * 0.62 if co.z > 0 else co.z * 0.3
        return Vector((co.x, co.y, z + 0.42))
    deform(dough_, shape)

    def dents(co, n):
        d = 0.03 * fbm(co * 2.2) + 0.006 * fbm(co * 9)
        # пара вмятин от пальцев
        for cx, cy in ((0.12, -0.18), (-0.2, 0.05)):
            d -= 0.05 * math.exp(-((co.x - cx) ** 2 + (co.y - cy) ** 2) / 0.012)
        return d
    push_normals(dough_, dents)
    smooth(dough_)
    mat = material("MasaMat", [(0.0, (0.93, 0.68, 0.24)), (0.5, (1.0, 0.82, 0.38)), (1.0, (1.0, 0.90, 0.56))],
                   coord="z", lo=0.35, hi=0.84, rough=0.5, sss=0.5, sss_radius=(1, 0.8, 0.4), sheen=0.3, coat=0.15,
                   bump=0.15, bump_scale=30, vary=0.08)
    add_speckles(mat, (0.90, 0.62, 0.20), scale=50, threshold=0.68, strength=0.6)
    assign(dough_, mat)
    husk = husk_leaf("MasaHusk", 1.7, 0.4, cup=0.16)
    base, tip = Vector((1.2, -0.25, 0.02)), Vector((0.35, 0.1, 1.05))
    d = (tip - base).normalized()
    cam = Vector((0.22, -0.87, 0.44))
    zax = (cam - d * cam.dot(d)).normalized()
    yax = zax.cross(d)
    rot = Matrix((d, yax, zax)).transposed().to_4x4()
    husk.matrix_world = Matrix.Translation((base + tip) / 2) @ rot
    nudge([husk], [bowl, dough_], (1, -0.3, 0), 0.01)
    return [bowl, dough_, husk]


def husk_leaf(name, length=1.4, width=0.5, cup=0.22):
    """Сухой кукурузный лист: узкий кончик, желобок вдоль."""
    rx, ry = length / 2, width / 2
    ob = polar_disc(name, 20, 120, rx, ry)

    def ky(xn):
        return (1.0 - 0.92 * max(0.0, xn) ** 1.4) * (1.0 - 0.15 * max(0.0, -xn) ** 3)
    husk_colors(ob, lambda co: co.y / ry, lambda co: max(0.0, -co.x / rx))

    def fn(co):
        xn = co.x / rx
        y = co.y * ky(xn)
        z = cup * (y / ry) ** 2 * (1 - 0.5 * max(0.0, xn)) + 0.18 * max(0.0, xn) ** 2.5 + 0.012 * math.sin(co.x * 9)
        return Vector((co.x, y, z))
    deform(ob, fn)
    solidify(ob, 0.022)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, husk_mat(f"{name}Mat"))
    return ob


def nudge(objs, others, direction, step=0.01, limit=200):
    """Отодвигает группу по направлению, пока она пересекается с другими."""
    bpy.context.view_layer.update()
    trees = [world_tree(o)[0] for o in others]
    d = Vector(direction).normalized() * step
    for _ in range(limit):
        hit = False
        for ob in objs:
            t, _ = world_tree(ob)
            if any(t.overlap(o) for o in trees):
                hit = True
                break
        if not hit:
            break
        for ob in objs:
            ob.location += d
        bpy.context.view_layer.update()
    return objs


def fold_fn(x0, R, th_max):
    """Загиб листа вдоль линии x = x0 вверх и назад."""
    def fn(co):
        d = co.x - x0
        if d <= 0:
            return co
        th = d / R
        if th <= th_max:
            return Vector((x0 + R * math.sin(th), co.y, co.z + R * (1 - math.cos(th))))
        px, pz = x0 + R * math.sin(th_max), R * (1 - math.cos(th_max))
        s = d - R * th_max
        return Vector((px + s * math.cos(th_max), co.y, co.z + pz + s * math.sin(th_max)))
    return fn


def tortilla_disc(name, r=1.0, seed=0, fold=None, mat=None):
    ob = polar_disc(name, 30, 128, r, r)
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6.28)

    def shape(co):
        a = math.atan2(co.y, co.x)
        rr = math.hypot(co.x, co.y) / r
        k = 1.0 + 0.02 * math.sin(3 * a + ph) + 0.012 * math.sin(7 * a + 2 * ph)
        z = 0.02 * r * math.sin(2 * a + ph) * rr ** 3
        return Vector((co.x * k, co.y * k, z))
    deform(ob, shape)
    if fold:
        deform(ob, fold)
    solidify(ob, 0.06 * r)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, mat or tortilla_mat(f"{name}Mat", r))
    return ob


def tortilla():
    mat = tortilla_mat("TortillaMat", 1.0)
    parts = []
    for i in range(3):
        t = tortilla_disc(f"Tortilla{i}", 1.0, seed=i, mat=mat)
        t.rotation_euler = (0, 0, i * 1.3)
        t.location = (0.07 * math.cos(i * 2.4 + 0.5), 0.07 * math.sin(i * 2.4 + 0.5), i * 0.075)
        parts.append(t)
    top = tortilla_disc("TortillaTop", 1.0, seed=5, fold=fold_fn(0.3, 0.06, math.radians(168)), mat=mat)
    top.rotation_euler = (0, 0, math.radians(-75))
    top.location = (0.0, 0.0, 3 * 0.075)
    parts.append(top)
    return rotate_all(parts, (math.radians(8), 0, 0))


def beef_mat(name, grill=True):
    mat = material(name, [(0.0, (0.20, 0.08, 0.04)), (0.35, (0.32, 0.12, 0.05)), (0.75, (0.48, 0.20, 0.09)),
                          (1.0, (0.55, 0.25, 0.11))],
                   coord="nz", lo=-1, hi=1, rough=0.32, sss=0.1, sss_radius=(1, 0.3, 0.2), coat=0.45, coat_rough=0.2,
                   bump=0.3, bump_scale=10, bump_detail=8, vary=0.18, vary_scale=2.5)
    if grill:
        add_stripes(mat, (0.16, 0.06, 0.03), scale=0.75, angle=35, width=0.15, nz_min=0.55, strength=0.85)
        add_stripes(mat, (0.20, 0.07, 0.04), scale=0.75, angle=-55, width=0.08, nz_min=0.55, strength=0.5)
    add_speckles(mat, (0.18, 0.06, 0.03), scale=9, threshold=0.66, strength=0.5)
    return mat


def steak_cut_mat(name, lo, hi, coord="z"):
    """Срез стейка: розовая середина, темная корочка по краям."""
    crust = (0.30, 0.12, 0.06)
    return material(name, [(0.0, crust), (0.13, (0.40, 0.15, 0.07)), (0.3, (0.70, 0.24, 0.18)), (0.5, (0.82, 0.32, 0.27)),
                           (0.7, (0.70, 0.24, 0.18)), (0.87, (0.40, 0.15, 0.07)), (1.0, crust)],
                    coord=coord, lo=lo, hi=hi, rough=0.28, sss=0.2, sss_radius=(1, 0.3, 0.25), coat=0.5,
                    coat_rough=0.12, bump=0.2, bump_scale=24, vary=0.08, vary_scale=8)


def beef():
    H = 0.36
    outline = polar_outline(lambda a: 1.0 + 0.10 * math.cos(a + 0.4) + 0.06 * math.cos(2 * a + 1.0)
                            + 0.04 * math.sin(3 * a + 0.5))
    outline = [(x * 1.05, y * 0.8) for x, y in outline]
    ob = outline_slab("Steak", outline, H, p=2.6, cuts=40)
    deform(ob, lambda co: Vector((co.x, co.y, co.z + H / 2)))
    push_normals(ob, lambda co, n: 0.02 * fbm(co * 1.8, 3) + 0.005 * fbm(co * 8, 2))
    # срез справа: видна розовая середина
    bisect(ob, (0.42, 0, 0), (1, 0, 0))
    smooth(ob, 50)
    assign_faces(ob, beef_mat("SteakMat"), [(lambda n, c: n.x > 0.95 and c.x > 0.38, steak_cut_mat("SteakCut", 0.0, H))])
    parts = [ob]
    # отрезанные ломтики лежат черепицей
    cut = steak_cut_mat("SliceCut", -H / 2, H / 2, coord="x")
    crust = beef_mat("SliceCrust", grill=False)
    slices = []
    for i in range(3):
        w = 0.66 - 0.06 * i

        def so(t):
            c, s_ = math.cos(t), math.sin(t)
            return math.copysign(abs(c) ** 0.45, c) * H / 2, math.copysign(abs(s_) ** 0.8, s_) * w
        sl = outline_slab(f"Slice{i}", [so(2 * math.pi * k / 64) for k in range(64)], 0.16, p=3.0, cuts=24)
        push_normals(sl, lambda co, n: 0.008 * fbm(co * 6))
        smooth(sl)
        assign_faces(sl, crust, [(lambda n, c: abs(n.z) > 0.75, cut)])
        # ломтик лежит срезом вверх, с наклоном на соседа
        sl.rotation_euler = (0, math.radians(24), 0)
        sl.location = (0.70 + 0.26 * i, -0.05 * i, 0.4)
        bpy.context.view_layer.update()
        drop(sl, parts + slices, floor=0.0, step=0.01, top=0.9)
        slices.append(sl)
    parts += slices
    return rotate_all(parts, (0, 0, math.radians(-38)))


def salsa_bits(target, prefix, n_tomato=26, n_onion=8, n_herb=12, s=1.0, area=0.6, seed=2, zmin=-1e9):
    """Кусочки помидора, лука и кинзы на поверхности сальсы."""
    toms = [material(f"{prefix}Tom{i}", [(0.0, c0), (1.0, c1)], coord="z", lo=-0.06, hi=0.06, rough=0.12, sss=0.4,
                     sss_radius=(1, 0.3, 0.2), coat=0.8)
            for i, (c0, c1) in enumerate((((0.80, 0.08, 0.04), (0.98, 0.26, 0.12)), ((0.88, 0.18, 0.06), (1.0, 0.42, 0.20)),
                                          ((0.70, 0.06, 0.04), (0.90, 0.16, 0.08))))]
    onion = material(f"{prefix}Onion", [(0.0, (0.94, 0.90, 0.88)), (1.0, (1.0, 0.98, 0.96))], coord="z", lo=-0.03,
                     hi=0.03, rough=0.2, sss=0.5, coat=0.6)
    herb = herb_mat(f"{prefix}Herb")

    def tom(i, rnd):
        c = rcube(f"{prefix}T{i}", *(s * rnd.uniform(0.06, 0.085) for _ in range(2)), s * rnd.uniform(0.045, 0.065))
        c.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0)
        return assign(c, toms[i % 3])
    scatter_on(target, n_tomato, tom, seed=seed, area=area, spacing=0.09 * s, zmin=zmin)

    def oni(i, rnd):
        c = rcube(f"{prefix}O{i}", s * 0.06, s * 0.035, s * 0.025)
        return assign(c, onion)
    scatter_on(target, n_onion, oni, seed=seed + 7, area=area, spacing=0.06 * s, zmin=zmin)

    def hb(i, rnd):
        c = cilantro(f"{prefix}H{i}", s * rnd.uniform(0.07, 0.1))
        c.location.z += 0.03 * s
        return assign(c, herb)
    scatter_on(target, n_herb, hb, seed=seed + 13, area=area * 0.9, spacing=0.12 * s, zmin=zmin)


def salsa():
    parts = molcajete("Molca", 1.0)
    sauce = material("SalsaMat", [(0.0, (0.66, 0.07, 0.04)), (1.0, (0.90, 0.18, 0.08))], coord="z", lo=0.55, hi=0.8,
                     rough=0.15, sss=0.4, sss_radius=(1, 0.3, 0.2), coat=0.8, bump=0.25, bump_scale=14)
    fill = bowl_fill("SalsaFill", 0.72, 0.62, 0.10, sauce, noise=0.03)
    salsa_bits(fill, "Sal", area=0.58, seed=3)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def beans():
    prof = [(0.0, 0.0), (0.30, 0.0), (0.36, 0.03), (0.52, 0.16), (0.62, 0.34), (0.63, 0.46), (0.56, 0.62),
            (0.50, 0.70), (0.51, 0.76), (0.57, 0.82), (0.58, 0.86), (0.54, 0.88), (0.48, 0.84), (0.45, 0.76),
            (0.44, 0.66), (0.0, 0.62)]
    pot = lathe("BeanPot", prof, 96)
    subdivide(pot, 1)
    smooth(pot)
    clay = clay_mat("BeanPotMat", 0.0, 0.88, bands=((0.52, 0.02), (0.6, 0.012)))
    assign(pot, clay)
    parts = [pot]
    for i, x in enumerate((-1, 1)):
        h = torus(f"PotHandle{i}", 0.11, 0.035, 48, 16)
        h.rotation_euler = (math.radians(90), 0, 0)
        h.location = (x * 0.6, 0, 0.58)
        apply_transform(h)
        assign(smooth(h), clay)
        parts.append(h)
    mound = sphere("BeanMound", 0.47, 64, 32)
    deform(mound, lambda co: Vector((co.x, co.y, (co.z * 0.5 if co.z > 0 else co.z * 0.2) + 0.78)))
    push_normals(mound, lambda co, n: 0.02 * fbm(co * 8))
    smooth(mound)
    assign(mound, flat("BeanMoundMat", (0.10, 0.06, 0.08), rough=0.3, coat=0.6))
    parts.append(mound)
    bean_mats = [material(f"BeanMat{i}", [(0.0, c0), (1.0, c1)], coord="z", lo=-0.03, hi=0.04, rough=0.15, coat=0.9,
                          coat_rough=0.04, sss=0.1)
                 for i, (c0, c1) in enumerate((((0.05, 0.03, 0.05), (0.22, 0.13, 0.18)),
                                               ((0.07, 0.04, 0.05), (0.28, 0.16, 0.20)),
                                               ((0.04, 0.03, 0.04), (0.18, 0.12, 0.16))))]

    def make(i, rnd):
        b = sphere(f"Bean{i}", 1.0, 24, 14)
        b.scale = (0.085, 0.058, 0.045)
        apply_transform(b)
        bend(b, 0.35)
        b.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), 0)
        b.location.z += 0.015
        return assign(smooth(b), bean_mats[i % 3])
    scatter_on(mound, 60, make, seed=6, area=0.47, spacing=0.085, zmin=0.8)
    return [o for o in bpy.data.objects if o.type == "MESH"]


CHILI_PROF = [(0.0, 0.0), (0.025, 0.02), (0.065, 0.08), (0.12, 0.25), (0.17, 0.5), (0.215, 0.8), (0.25, 1.1),
              (0.27, 1.3), (0.26, 1.42), (0.22, 1.51), (0.12, 1.56), (0.0, 1.54)]


def profile_point(prof, s):
    """Точка профиля по длине дуги s от последней точки (сверху вниз)."""
    pts = list(reversed(prof))
    acc = 0.0
    for (r0, z0), (r1, z1) in zip(pts, pts[1:]):
        L = math.hypot(r1 - r0, z1 - z0)
        if acc + L >= s:
            t = (s - acc) / L
            nr, nz = (z0 - z1), (r1 - r0)
            ln = math.hypot(nr, nz) or 1.0
            return r0 + (r1 - r0) * t, z0 + (z1 - z0) * t, (-nr / ln, -nz / ln)
        acc += L
    r0, z0 = pts[-1]
    return r0, z0, (1.0, 0.0)


def chili_pepper(name, curve=0.45, scale=1.0, red=True):
    body = lathe(name, CHILI_PROF, 72)

    def ridges(co):
        a = math.atan2(co.y, co.x)
        t = co.z / 1.55
        k = 1.0 + 0.05 * math.cos(3 * a) * min(1.0, t * 3)
        return Vector((co.x * k, co.y * k, co.z))
    deform(body, ridges)
    subdivide(body, 1)
    deform(body, lambda co: Vector((co.x + curve * max(0.0, 1 - co.z / 1.56) ** 2.2, co.y, co.z)))
    smooth(body)
    if red:
        cols = [(0.0, (0.62, 0.03, 0.03)), (0.5, (0.86, 0.07, 0.04)), (1.0, (1.0, 0.24, 0.12))]
    else:
        cols = [(0.0, (0.16, 0.42, 0.08)), (0.5, (0.26, 0.58, 0.12)), (1.0, (0.48, 0.78, 0.22))]
    assign(body, material(f"{name}Mat", cols, coord="x", lo=-0.25, hi=0.25, rough=0.15, sss=0.3,
                          sss_radius=(1, 0.3, 0.2), coat=0.9, coat_rough=0.05, vary=0.06))
    green = material(f"{name}Calyx", [(0.0, (0.18, 0.46, 0.10)), (1.0, (0.44, 0.74, 0.22))], coord="z", lo=1.3,
                     hi=1.8, rough=0.35, sss=0.3, coat=0.4)
    cal = polar_disc(f"{name}Cap", 12, 80, 1, 1)

    def drape(co):
        t = math.hypot(co.x, co.y)
        a = math.atan2(co.y, co.x)
        smax = 0.34 + 0.1 * math.cos(5 * a)
        r, z, (nr, nz) = profile_point(CHILI_PROF, t * smax)
        off = 0.028
        r, z = r + nr * off, z + nz * off
        return Vector((r * math.cos(a), r * math.sin(a), z))
    deform(cal, drape)
    solidify(cal, 0.025)
    subdivide(cal, 1)
    smooth(cal)
    assign(cal, green)
    stem = tube(f"{name}Stem", [(0.0, 0.0, 1.52), (0.0, 0.0, 1.66), (0.03, 0.0, 1.77), (0.1, 0.0, 1.86),
                                (0.19, 0.0, 1.9)], 0.055, taper=(1.2, 0.85))
    assign(smooth(stem), green)
    parts = [body, cal, stem]
    for o in parts:
        o.scale = (scale, scale, scale)
    return parts


def chili():
    # два перца веером: плодоножки вместе, кончики врозь
    a = chili_pepper("ChiliA", 0.55, 1.0)
    rotate_all(a, (0, math.radians(-90), 0))
    rotate_all(a, (math.radians(-90), 0, 0))
    rotate_all(a, (0, 0, math.radians(18)))
    for o in a:
        o.location += Vector((0.0, -0.3, 0.0))
    b = chili_pepper("ChiliB", -0.55, 0.9)
    rotate_all(b, (0, math.radians(-90), 0))
    rotate_all(b, (math.radians(-90), 0, 0))
    rotate_all(b, (0, 0, math.radians(-30)))
    for o in b:
        o.location += Vector((-0.05, 0.3, 0.0))
    ground(a)
    ground(b)
    return a + b


def lime():
    R = 0.5
    skin = lime_skin_mat("LimeSkin", R)
    whole = lime_body("Lime", R)
    assign(whole, skin)
    whole.rotation_euler = (0, 0, math.radians(30))
    whole.location = (-0.38, 0.32, R)
    half = lime_body("LimeHalf", R)
    bisect(half, (0, 0, 0), (1, 0, 0))
    smooth(half)
    assign(half, skin)
    face = citrus_face("LimeFace", R * 0.985, segs=10)
    face.rotation_euler = (0, math.radians(90), 0)
    face.location = (0.003, 0, 0)
    apply_transform(face)
    hp = [half, face]
    rotate_all(hp, (0, math.radians(-90), 0))
    rotate_all(hp, (math.radians(46), 0, 0))
    rotate_all(hp, (0, 0, math.radians(-18)))
    for o in hp:
        o.location += Vector((0.36, -0.28, 0))
    ground(hp)
    return [whole] + hp


def onion_r(th):
    """Радиус луковицы по углу от верхушки: острый носик, сплюснутое дно."""
    c = math.cos(th)
    return 0.62 * (1 + 0.55 * max(0.0, c) ** 6) * (1 - 0.1 * max(0.0, -c) ** 2)


def onion_bulb(name):
    ob = sphere(name, 1.0, 72, 48)

    def fn(co):
        th = math.acos(max(-1.0, min(1.0, co.z)))
        r = onion_r(th)
        return Vector((co.x * r, co.y * r, co.z * r * 0.92))
    deform(ob, fn)
    return smooth(ob)


def onion_skin_mat(name):
    mat = material(name, [(0.0, (0.36, 0.08, 0.22)), (0.35, (0.56, 0.13, 0.34)), (0.75, (0.74, 0.26, 0.48)),
                          (1.0, (0.90, 0.60, 0.66))],
                   coord="z", lo=-0.55, hi=0.85, rough=0.3, sss=0.2, sss_radius=(1, 0.4, 0.6), coat=0.6,
                   coat_rough=0.12, sheen=0.3, vary=0.08)
    add_turns(mat, (0.34, 0.06, 0.20), count=16, width=0.1, strength=0.45)
    return mat


def onion_face(name):
    """Срез луковицы: слои следуют форме луковицы."""
    ob = polar_disc(name, 60, 160, 1.0, 1.0)
    white = (0.99, 0.95, 0.96)
    purple = (0.62, 0.14, 0.38)
    n = 6

    def to_xz(co):
        t = math.hypot(co.x, co.y)
        phi = math.atan2(co.x, co.y)
        r = onion_r(abs(phi)) * 0.995 * t
        return r * math.sin(phi), r * math.cos(phi) * 0.92

    def col(co, nrm):
        t = math.hypot(co.x, co.y)
        if t > 0.96:
            return purple
        f = (t * n + 0.3) % 1.0
        c = mix(white, (0.96, 0.82, 0.88), t)
        return purple if f > 0.84 else mix(c, (0.92, 0.70, 0.80), max(0.0, (f - 0.7) / 0.14))
    vcol(ob, col)

    def fn(co):
        t = math.hypot(co.x, co.y)
        x, z = to_xz(co)
        f = (t * n + 0.3) % 1.0
        return Vector((x, -0.004 * math.sin(math.pi * f), z))
    deform(ob, fn)
    smooth(ob)
    assign(ob, vmat(f"{name}Mat", rough=0.15, sss=0.4, sss_radius=(1, 0.8, 0.9), coat=0.7, coat_rough=0.06))
    return ob


def onion_top(name, z0):
    paper = material(f"{name}Mat", [(0.0, (0.70, 0.46, 0.30)), (1.0, (0.92, 0.78, 0.58))], coord="z", lo=z0,
                     hi=z0 + 0.3, rough=0.45, coat=0.3, sheen=0.4)
    parts = []
    for i, (dx, bx, h) in enumerate(((0.0, 0.06, 0.28), (0.025, 0.13, 0.22), (-0.02, -0.07, 0.2))):
        pts = [(dx * (1 - t) + bx * t * t, 0.01 * i, z0 - 0.05 + h * t) for t in [k / 8 for k in range(9)]]
        st = tube(f"{name}{i}", pts, 0.035, taper=(1.0, 0.3))
        assign(smooth(st), paper)
        parts.append(st)
    return parts


def onion():
    skin = onion_skin_mat("OnionSkin")
    whole = onion_bulb("Onion")
    assign(whole, skin)
    top = onion_top("OnionTop", 0.62 * 1.55 * 0.92)
    root = sphere("OnionRoot", 0.12, 24, 12)
    root.scale = (1, 1, 0.3)
    root.location = (0, 0, -0.5)
    apply_transform(root)
    assign(smooth(root), flat("OnionRootMat", (0.86, 0.74, 0.56), rough=0.6))
    wp = [whole, root] + top
    ground(wp)
    for o in wp:
        o.location += Vector((-0.3, 0.35, 0))
    half = onion_bulb("OnionHalf")
    bisect(half, (0, 0, 0), (0, 1, 0))
    smooth(half)
    assign(half, skin)
    face = onion_face("OnionFace")
    face.location = (0, 0.002, 0)
    apply_transform(face)
    hp = [half, face]
    # срезом к камере и чуть вверх
    rotate_all(hp, (math.radians(180), 0, 0))
    rotate_all(hp, (math.radians(-90 + 40), 0, 0))
    for o in hp:
        o.location += Vector((0.42, -0.42, 0))
    ground(hp)
    return wp + hp


# MARK: - Закуски

def jalapeno_slice(name, r=0.1):
    """Колечко халапеньо: зеленое кольцо, светлая мякоть, семечки."""
    ring = torus(f"{name}Ring", r * 0.82, r * 0.2, 40, 12)
    deform(ring, lambda co: Vector((co.x, co.y, co.z * 0.8)))
    assign(smooth(ring), material(f"{name}RingMat", [(0.0, (0.16, 0.44, 0.08)), (1.0, (0.34, 0.66, 0.14))], coord="z",
                                  lo=-0.03, hi=0.03, rough=0.15, coat=0.8, sss=0.3))
    core = cylinder(f"{name}Core", r * 0.7, r * 0.18, 32)
    smooth(core)
    assign(core, material(f"{name}CoreMat", [(0.0, (0.86, 0.94, 0.58)), (1.0, (0.62, 0.84, 0.30))], coord="r", lo=0.0,
                          hi=r * 0.7, rough=0.2, sss=0.4, coat=0.6))
    parts = [ring, core]
    for k in range(4):
        a = k * math.pi / 2 + 0.4
        sd = sphere(f"{name}Seed{k}", r * 0.12, 12, 8)
        sd.scale = (1.3, 1, 0.5)
        sd.location = (r * 0.38 * math.cos(a), r * 0.38 * math.sin(a), r * 0.08)
        apply_transform(sd)
        assign(smooth(sd), flat(f"{name}SeedMat", (1.0, 0.96, 0.82), rough=0.3, coat=0.5))
        parts.append(sd)
    return parts


def place_on(objs, origin, normal, spin=0.0):
    """Ставит группу (собранную у начала координат, ось Z вверх) в точку поверхности по нормали."""
    q = Vector(normal).to_track_quat("Z", "Y")
    mat = Matrix.Translation(origin) @ q.to_matrix().to_4x4() @ Matrix.Rotation(spin, 4, "Z")
    for o in objs:
        o.matrix_world = mat @ o.matrix_world
    bpy.context.view_layer.update()
    return objs


def ray_down(x, y, top=5.0, skip=()):
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, nor, _, ob, _ = bpy.context.scene.ray_cast(dg, Vector((x, y, top)), Vector((0, 0, -1)))
    return (loc, nor) if hit else (None, None)


def nachos():
    red, white = (0.88, 0.12, 0.10), (1.0, 0.98, 0.95)
    tray = box_mesh("NachoTray", 1.6, 1.15, 0.34, 0.0, cuts=8)

    def taper(co):
        t = co.z / 0.34
        k = 0.8 + 0.2 * t
        return Vector((co.x * k, co.y * k, co.z))
    deform(tray, taper)
    bevel(tray, 0.06, 4, 30)
    smooth(tray, 40)
    assign(tray, checker_mat("NachoTrayMat", red, white, scale=5.5, rough=0.4, coat=0.3))
    parts = [tray]
    cmat = chip_mat("ChipMat")
    rnd = random.Random(11)
    chips = []
    # внешний круг чипсов чуть наружу, потом середина
    spots = [(2 * math.pi * k / 7 + rnd.uniform(-0.12, 0.12), 0.55, True) for k in range(7)]
    spots += [(2 * math.pi * k / 4 + 0.6, 0.22, False) for k in range(4)] + [(0.0, 0.0, False)]
    peak = 0.4
    for i, (a, r, outer) in enumerate(spots):
        c = chip(f"Chip{i}", rnd.uniform(0.27, 0.31), seed=i)
        assign(c, cmat)
        if outer:
            c.rotation_euler = (math.radians(rnd.uniform(10, 18)), math.radians(rnd.uniform(-8, 8)), a - math.pi / 2)
        else:
            c.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 6.28))
        c.location = (r * math.cos(a) * 1.2, r * math.sin(a) * 0.82, 0.0)
        bpy.context.view_layer.update()
        drop(c, [tray] + chips, floor=0.3, step=0.01, top=peak + 0.25)
        peak = max(peak, max((c.matrix_world @ v.co).z for v in c.data.vertices))
        chips.append(c)
    parts += chips
    # сырный соус зигзагом по верху
    cheese = material("NachoCheese", [(0.0, (0.98, 0.56, 0.04)), (1.0, (1.0, 0.76, 0.18))], coord="z", lo=0.5, hi=1.0,
                      rough=0.1, sss=0.5, sss_radius=(1, 0.6, 0.1), coat=0.9, coat_rough=0.04)
    pts = []
    for k in range(70):
        t = k / 69
        x = -0.45 + 0.9 * t
        y = 0.22 * math.sin(t * 2 * math.pi * 1.6 + 0.4) * (1 - 0.3 * abs(x))
        loc, nor = ray_down(x, y)
        if loc is not None and loc.z > 0.4:
            pts.append((x, y, loc.z + 0.035))
    sm = [pts[0]] + [tuple((a + b + c) / 3 for a, b, c in zip(pts[i - 1], pts[i], pts[i + 1])) for i in range(1, len(pts) - 1)] + [pts[-1]]
    sm = [(x, y, max(z, pts[i][2])) for i, (x, y, z) in enumerate(sm)]
    dr = tube("CheeseDrizzle", sm, 0.055, taper=(0.8, 1.0))
    assign(smooth(dr), cheese)
    parts.append(dr)
    for i, (x, y) in enumerate(((-0.2, 0.05), (0.18, -0.1), (0.35, 0.2), (-0.4, -0.18))):
        loc, nor = ray_down(x, y)
        if loc is None:
            continue
        b = sphere(f"CheeseBlob{i}", 0.12, 24, 16)
        b.scale = (1.25, 1.0, 0.5)
        apply_transform(b)
        assign(smooth(b), cheese)
        place_on([b], loc, nor, i)
        parts.append(b)
    for i, (x, y) in enumerate(((0.05, 0.12), (-0.3, -0.05), (0.32, -0.02))):
        loc, nor = ray_down(x, y)
        if loc is None:
            continue
        js = jalapeno_slice(f"Jal{i}", 0.1)
        for o in js:
            o.location.z += 0.03
        place_on(js, loc, nor, i * 1.3)
        parts += js
    return rotate_all(parts, (0, 0, math.radians(-12)))


def churro(name, length=1.5, r=0.12, ridges=8):
    prof = []
    n = 48
    for i in range(n + 1):
        t = i / n
        e = min(t, 1 - t) * length / (r * 0.9)
        rr = r * (math.sqrt(max(0.0, 1 - (1 - e) ** 2)) if e < 1 else 1.0)
        prof.append((rr, t * length))
    prof[0], prof[-1] = (0.0, 0.0), (0.0, length)
    ob = lathe(name, prof, 128)

    def star(co):
        a = math.atan2(co.y, co.x)
        k = 0.86 + 0.2 * (0.5 + 0.5 * math.cos(ridges * a)) ** 0.6
        return Vector((co.x * k, co.y * k, co.z))
    deform(ob, star)
    subdivide(ob, 1)
    smooth(ob)
    return ob


def churro_mat(name, r=0.12):
    mat = material(name, [(0.0, (0.56, 0.26, 0.08)), (0.55, (0.84, 0.50, 0.16)), (1.0, (0.96, 0.70, 0.32))],
                   coord="r", lo=r * 0.75, hi=r * 1.1, rough=0.4, sss=0.25, sss_radius=(1, 0.6, 0.3), coat=0.35,
                   sheen=0.6, bump=0.25, bump_scale=40, vary=0.1)
    add_speckles(mat, (1.0, 0.98, 0.94), scale=90, threshold=0.62, strength=0.85)
    add_speckles(mat, (1.0, 0.96, 0.90), scale=45, threshold=0.68, strength=0.6)
    return mat


def churros():
    cone = lathe("ChurroCone", [(0.0, 0.0), (0.05, 0.05), (0.42, 1.0), (0.46, 1.08), (0.45, 1.11), (0.42, 1.07),
                                (0.05, 0.1), (0.0, 0.08)], 96)
    subdivide(cone, 1)
    smooth(cone, 50)
    mat = material("ConeMat", [(0.0, (0.96, 0.94, 0.90)), (1.0, (1.0, 1.0, 0.98))], coord="z", lo=0.0, hi=1.1,
                   rough=0.4, coat=0.3, bump=0.04, bump_scale=8)
    add_turns(mat, (0.88, 0.12, 0.12), count=7, width=0.5, twist=0.35)
    assign(cone, mat)
    parts = [cone]
    cmat = churro_mat("ChurroMat")
    for i, (dx, dy, tilt, h, ln) in enumerate(((0.0, 0.12, 0, 0.55, 1.6), (-0.19, -0.05, -14, 0.45, 1.45),
                                                (0.19, -0.06, 12, 0.5, 1.5))):
        c = churro(f"Churro{i}", ln, 0.12)
        assign(c, cmat)
        c.location = (0, 0, -0.45)
        apply_transform(c)
        c.rotation_euler = (math.radians(-8 if i else 6), math.radians(tilt), 0)
        c.location = (dx, dy, h + 0.45)
        parts.append(c)
    return rotate_all(parts, (0, math.radians(8), math.radians(-10)))


def glass_mat(name):
    return material(name, [(0.0, (0.92, 0.95, 1.0)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=1.5,
                    rough=0.04, transmission=1.0)


def ice_cube(name, s=0.17, rot=(0, 0, 0)):
    c = rcube(name, s, s, s, p=5.0, cuts=6)
    c.rotation_euler = rot
    assign(c, material(f"{name}Mat", [(0.0, (0.86, 0.94, 1.0)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=-s, hi=s,
                       rough=0.05, coat=1.0, coat_rough=0.02, transmission=0.75, sss=0.2, sss_radius=(0.8, 0.9, 1.0)))
    return c


def cinnamon_stick(name, p0, p1, r=0.065):
    """Палочка корицы: свернутая кора, на торце завиток."""
    mat = material(f"{name}Mat", [(0.0, (0.48, 0.22, 0.10)), (1.0, (0.70, 0.38, 0.18))], coord="nz", lo=-1, hi=1,
                   rough=0.55, coat=0.2, bump=0.35, bump_scale=30, vary=0.15)
    d = (Vector(p1) - Vector(p0))
    ln = d.length
    st = lathe(name, [(0.0, 0.0), (r, 0.0), (r, ln), (0.0, ln)], 48)
    smooth(st, 40)
    assign(st, mat)
    # завиток на верхнем торце
    pts = []
    for k in range(40):
        t = k / 39
        a = t * 2 * math.pi * 1.6
        rr = r * (1 - 0.75 * t)
        pts.append((rr * math.cos(a), rr * math.sin(a), ln + 0.004))
    sp = tube(f"{name}Curl", pts, 0.014)
    assign(smooth(sp), flat(f"{name}CurlMat", (0.42, 0.18, 0.08), rough=0.5))
    q = d.normalized().to_track_quat("Z", "Y")
    m = Matrix.Translation(p0) @ q.to_matrix().to_4x4()
    for o in (st, sp):
        o.matrix_world = m
    return [st, sp]


def horchata():
    glass = lathe("HorGlass", [(0.0, 0.0), (0.40, 0.0), (0.43, 0.04), (0.47, 1.5), (0.43, 1.5), (0.37, 0.10),
                               (0.0, 0.10)], 72)
    smooth(glass, 50)
    assign(glass, glass_mat("HorGlassMat"))
    milk_ = lathe("HorMilk", [(0.0, 0.10), (0.37, 0.10), (0.424, 1.28), (0.0, 1.28)], 72)
    smooth(milk_, 50)
    assign(milk_, material("HorMilkMat", [(0.0, (0.96, 0.84, 0.64)), (0.55, (1.0, 0.92, 0.78)), (1.0, (1.0, 0.96, 0.88))],
                           coord="z", lo=0.1, hi=1.28, rough=0.25, sss=0.2, sss_radius=(1, 0.85, 0.6), coat=0.4))
    glow(milk_.data.materials[0], (1.0, 0.92, 0.80), 0.42)
    top = polar_disc("HorTop", 20, 72, 0.423, 0.423)
    deform(top, lambda co: Vector((co.x, co.y, 1.282 + 0.006 * fbm(co * 8))))
    smooth(top)
    tmat = material("HorTopMat", [(0.0, (0.98, 0.88, 0.72)), (1.0, (1.0, 0.95, 0.86))], coord="r", lo=0.0, hi=0.42,
                    rough=0.4, sss=0.3, sheen=0.4)
    glow(tmat, (1.0, 0.92, 0.80), 0.3)
    add_speckles(tmat, (0.66, 0.36, 0.16), scale=14, threshold=0.56, strength=0.65)
    add_speckles(tmat, (0.52, 0.26, 0.10), scale=40, threshold=0.6, strength=0.85)
    add_speckles(tmat, (0.46, 0.22, 0.08), scale=90, threshold=0.62, strength=0.9)
    assign(top, tmat)
    parts = [glass, milk_, top]
    for i, (x, y, rot) in enumerate(((-0.16, -0.08, (0.3, 0.2, 0.5)), (0.12, -0.14, (-0.2, 0.4, 1.2)),
                                     (-0.04, 0.17, (0.5, -0.3, 0.2)))):
        c = ice_cube(f"HorIce{i}", 0.13, rot)
        c.location = (x, y, 1.3)
        parts.append(c)
    parts += cinnamon_stick("Cinnamon", (0.1, 0.12, 0.5), (0.48, 0.18, 1.95))
    return rotate_all(parts, (0, 0, math.radians(-20)))


def tamale():
    # кукурузный лист лодочкой: широкий открытый конец, узкий перевязанный хвост
    nu, nv = 90, 48
    verts, faces = [], []
    for i in range(nu + 1):
        u = -1 + 2 * i / nu
        for j in range(nv + 1):
            verts.append((u, -1 + 2 * j / nv, 0.0))
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + nv + 1, a + nv + 2, a + 1))
    husk = from_data("TamaleHusk", verts, faces)
    L, tie_u = 1.25, 0.64

    def half_w(u):
        w = 0.96 + 0.06 * smoothstep(-0.6, -1.0, u)
        w -= 0.86 * smoothstep(0.22, tie_u, u)
        w += 0.17 * smoothstep(tie_u + 0.04, 1.0, u)
        return w

    def theta(u):
        t = 2.5 - 0.9 * smoothstep(-0.55, -1.0, u)
        t += 0.6 * smoothstep(0.22, tie_u, u)
        t -= 1.9 * smoothstep(tie_u + 0.04, 1.0, u)
        return t
    palette = ((0.86, 0.80, 0.50), (0.62, 0.56, 0.30), (0.95, 0.92, 0.70), (0.76, 0.78, 0.44))
    husk_colors(husk, lambda co: co.y * half_w(co.x) / 0.96, lambda co: 0.5 * smoothstep(0.4, 1.0, abs(co.x)),
                palette, lines=7.0)

    def wrap(co):
        u, v = co.x, co.y
        w, th = half_w(u), theta(u)
        r = w / th
        zc = r + (0.4 - r) * smoothstep(0.22, tie_u, u) + 0.02
        s_ = v * w
        phi = s_ / r
        rib = 0.008 * math.cos(s_ * 80) + 0.01 * fbm(Vector((u * 3, v * 2, 0)))
        # края листа отогнуты наружу
        lip = 0.14 * smoothstep(0.78, 1.0, abs(v)) * (1 - smoothstep(0.1, tie_u, u))
        rr = r + rib
        y, z = rr * math.sin(phi), zc - rr * math.cos(phi)
        return Vector((u * L, y + math.copysign(lip, v), z + 0.15 * lip))
    deform(husk, wrap)
    solidify(husk, 0.022)
    subdivide(husk, 1)
    smooth(husk)
    assign(husk, husk_mat("TamaleHuskMat"))
    zc = 0.42
    fill = capsule("TamaleFill", 1.62, 0.33, 64, 48)
    fill.location = (-0.36, 0, zc - 0.02)
    apply_transform(fill)
    deform(fill, lambda co: Vector((co.x, co.y, zc - 0.02 + (co.z - zc + 0.02) * (0.9 if co.z > zc else 1.0))))
    push_normals(fill, lambda co, n: 0.014 * fbm(co * 5) + 0.004 * fbm(co * 18))
    smooth(fill)
    fmat = material("TamaleFillMat", [(0.0, (0.92, 0.58, 0.14)), (0.6, (1.0, 0.76, 0.28)), (1.0, (1.0, 0.86, 0.44))],
                    coord="z", lo=0.15, hi=0.72, rough=0.5, sss=0.5, sss_radius=(1, 0.8, 0.4), sheen=0.35, coat=0.1,
                    bump=0.3, bump_scale=34, bump_detail=6)
    add_speckles(fmat, (0.90, 0.56, 0.16), scale=40, threshold=0.64, strength=0.55)
    assign(fill, fmat)
    tie = torus("TamaleTie", 0.075, 0.034, 48, 12)
    tie.scale = (1, 1, 1.7)
    tie.rotation_euler = (0, math.radians(90), 0)
    tie.location = (tie_u * L, 0, 0.42)
    apply_transform(tie)
    tmat = material("TamaleTieMat", [(0.0, (0.66, 0.62, 0.34)), (1.0, (0.84, 0.82, 0.54))], coord="z", lo=0.3, hi=0.55,
                    rough=0.5, sheen=0.3, coat=0.2)
    assign(smooth(tie), tmat)
    parts = [husk, fill, tie]
    for k, (dy, dz) in enumerate(((0.12, -0.16), (-0.1, -0.2))):
        end = tube(f"TamaleTieEnd{k}", [(tie_u * L, 0.0, 0.36), (tie_u * L + 0.05, dy * 0.6, 0.36 + dz * 0.5),
                                         (tie_u * L + 0.08, dy, 0.36 + dz)], 0.03, taper=(1.0, 0.7))
        assign(smooth(end), tmat)
        parts.append(end)
    return rotate_all(parts, (math.radians(10), 0, math.radians(-22)))


def flan():
    parts = [talavera_plate("FlanPlate", 0.95)]
    body = lathe("Flan", [(0.0, 0.1), (0.56, 0.1), (0.58, 0.13), (0.57, 0.17), (0.50, 0.52), (0.47, 0.56),
                          (0.0, 0.57)], 96)
    subdivide(body, 1)
    smooth(body)
    assign(body, material("FlanMat", [(0.0, (0.98, 0.76, 0.34)), (0.7, (1.0, 0.86, 0.48)), (1.0, (1.0, 0.82, 0.42))],
                          coord="z", lo=0.1, hi=0.57, rough=0.15, sss=0.6, sss_radius=(1, 0.8, 0.4), coat=0.8))
    caramel = material("Caramel", [(0.0, (0.52, 0.18, 0.02)), (0.6, (0.72, 0.32, 0.04)), (1.0, (0.86, 0.48, 0.08))],
                       coord="z", lo=0.1, hi=0.64, rough=0.05, sss=0.5, sss_radius=(1, 0.5, 0.1), coat=1.0,
                       coat_rough=0.02)
    cap = lathe("FlanTop", [(0.0, 0.545), (0.47, 0.545), (0.495, 0.565), (0.49, 0.6), (0.43, 0.628), (0.0, 0.638)], 96)
    subdivide(cap, 1)
    assign(smooth(cap), caramel)
    parts += [body, cap]
    rnd = random.Random(3)
    for i in range(9):
        a = 2 * math.pi * i / 9 + rnd.uniform(-0.2, 0.2)
        ln = rnd.uniform(0.1, 0.36)
        pts = []
        for k in range(12):
            z = 0.58 - ln * k / 11
            r = 0.475 + (0.56 - z) / 0.39 * 0.085 + 0.022
            pts.append((r * math.cos(a), r * math.sin(a), z))
        d = tube(f"FlanDrip{i}", pts, 0.04, taper=(1.1, 0.9))
        assign(smooth(d), caramel)
        tip = sphere(f"FlanDripTip{i}", 0.045, 24, 16)
        tip.scale = (1, 1, 1.25)
        tip.location = pts[-1]
        apply_transform(tip)
        assign(smooth(tip), caramel)
        parts += [d, tip]
    pool = polar_disc("FlanPool", 16, 96, 1.0, 1.0)

    def pool_fn(co):
        a = math.atan2(co.y, co.x)
        rr = math.hypot(co.x, co.y)
        k = 0.66 + 0.04 * math.sin(5 * a + 1) + 0.025 * math.sin(9 * a)
        return Vector((co.x * k, co.y * k, 0.112 - 0.012 * rr ** 6))
    deform(pool, pool_fn)
    solidify(pool, 0.02)
    subdivide(pool, 1)
    assign(smooth(pool), caramel)
    parts.append(pool)
    return parts


def concha():
    bread_ = sphere("ConchaBread", 0.82, 72, 48)
    deform(bread_, lambda co: Vector((co.x, co.y, co.z * 0.5 if co.z > 0 else co.z * 0.2)))
    smooth(bread_)
    assign(bread_, material("ConchaBreadMat", [(0.0, (0.78, 0.44, 0.14)), (0.6, (0.94, 0.64, 0.28)), (1.0, (1.0, 0.80, 0.46))],
                            coord="nz", lo=-1, hi=1, rough=0.45, sss=0.3, coat=0.3, bump=0.06, bump_scale=18))
    crust = sphere("ConchaCrust", 0.84, 160, 80)
    deform(crust, lambda co: Vector((co.x, co.y, co.z * 0.53 + 0.015)))
    bisect(crust, (0, 0, 0.13), (0, 0, -1), fill=False)
    solidify(crust, 0.06, 1.0)
    subdivide(crust, 1)
    N = 12

    def groove(co):
        rh = math.hypot(co.x, co.y) / 0.84
        a = math.atan2(co.y, co.x)
        phi = a + 1.2 * rh
        f = (phi * N / (2 * math.pi)) % 1.0
        d = min(f, 1 - f) * 2 * math.pi / N * rh * 0.84
        w = 0.035 * smoothstep(0.12, 0.3, rh)
        return smoothstep(w, w * 0.35, d) if w > 0 else 0.0
    push_normals(crust, lambda co, n: -0.04 * groove(co) if n.z > -0.2 else 0.0)
    pink, pink_hi, gold = (0.98, 0.56, 0.68), (1.0, 0.80, 0.86), (0.96, 0.66, 0.28)
    vcol(crust, lambda co, n: mix(mix(pink, pink_hi, (co.z - 0.2) / 0.3), gold, groove(co)))
    smooth(crust)
    mat = vmat("ConchaCrustMat", rough=0.5, sss=0.3, sss_radius=(1, 0.8, 0.8), sheen=0.6, coat=0.2, bump=0.25,
               bump_scale=45, bump_detail=6)
    add_speckles(mat, (1.0, 0.94, 0.96), scale=80, threshold=0.63, strength=0.7)
    assign(crust, mat)
    return rotate_all([bread_, crust], (math.radians(14), 0, 0))


def paleta():
    # прямоугольник с полукруглым верхом
    pts = []
    w, h = 0.48, 1.3
    for k in range(17):
        a = math.pi * k / 16
        pts.append((w * math.cos(a), h - w + w * 0.85 * math.sin(a) + w * 0.15))
    for k in range(9):
        a = math.pi + math.pi / 2 * k / 8
        pts.append((-w + 0.12 + 0.12 * math.cos(a), 0.12 + 0.12 * math.sin(a)))
    for k in range(9):
        a = 1.5 * math.pi + math.pi / 2 * k / 8
        pts.append((w - 0.12 + 0.12 * math.cos(a), 0.12 + 0.12 * math.sin(a)))
    body = outline_slab("Paleta", pts, 0.34, p=2.6, cuts=36, center=(0.0, h * 0.5))
    cutters = []
    for i, (x, y) in enumerate(((0.44, 1.12), (0.30, 1.30), (0.52, 0.90))):
        c = cylinder(f"Bite{i}", 0.15, 1.0, 48)
        c.location = (x, y, 0)
        cutters.append(c)
    bpy.context.view_layer.update()
    boolean_cut(body, cutters)
    smooth(body, 45)
    mat = material("PaletaMat", [(0.0, (0.90, 0.24, 0.34)), (0.6, (0.98, 0.40, 0.48)), (1.0, (1.0, 0.56, 0.62))],
                   coord="y", lo=0.0, hi=1.3, rough=0.22, sss=0.5, sss_radius=(1, 0.4, 0.45), coat=0.6, coat_rough=0.1,
                   bump=0.1, bump_scale=30, vary=0.08)
    add_speckles(mat, (0.78, 0.08, 0.16), scale=26, threshold=0.68, strength=0.7)
    assign(body, mat)
    parts = [body]
    berry = material("PaletaBerry", [(0.0, (1.0, 0.86, 0.86)), (0.5, (0.98, 0.42, 0.44)), (1.0, (0.80, 0.06, 0.12))],
                     coord="r", lo=0.0, hi=0.12, rough=0.12, sss=0.4, coat=0.8)
    add_speckles(berry, (1.0, 0.86, 0.36), scale=60, threshold=0.68, strength=0.8)
    for i, (x, y, side, rz) in enumerate(((-0.2, 0.95, 1, 20), (0.12, 0.62, 1, -30), (-0.18, 0.32, 1, 60),
                                          (0.22, 0.25, 1, 10), (0.1, 0.9, -1, 40), (-0.2, 0.5, -1, -20))):
        sl = sphere(f"Berry{i}", 1.0, 32, 16)

        def heart(co):
            k = 1.0 - 0.35 * max(0.0, -co.y) ** 1.5
            return Vector((co.x * 0.12 * k, co.y * 0.13, co.z * 0.025))
        deform(sl, heart)
        sl.rotation_euler = (0, 0, math.radians(rz))
        sl.location = (x, y, side * 0.168)
        apply_transform(sl)
        assign(smooth(sl), berry)
        parts.append(sl)
    stick = outline_slab("PaletaStick", polar_outline(lambda a: 1.0, 48), 0.07, p=3, cuts=16)
    deform(stick, lambda co: Vector((co.x * 0.1, co.y * 0.45 - 0.18, co.z)))
    assign(smooth(stick), material("PaletaStickMat", [(0.0, (0.86, 0.68, 0.42)), (1.0, (0.96, 0.84, 0.62))], coord="y",
                                   lo=-0.6, hi=0.2, rough=0.5, coat=0.2, bump=0.1, bump_scale=12))
    parts.append(stick)
    rotate_all(parts, (math.radians(90), 0, 0))
    return rotate_all(parts, (0, math.radians(14), math.radians(-24)))


# MARK: - Блюда

def lime_wedge(name, R=0.34, half=34):
    """Долька лайма: сектор вдоль длинной оси, два среза с мякотью."""
    ob = lime_body(name, R)
    b = math.radians(half)
    bisect(ob, (0, 0, 0), (0, math.cos(b), -math.sin(b)))
    bisect(ob, (0, 0, 0), (0, -math.cos(b), -math.sin(b)))
    smooth(ob, 40)
    pulp = material(f"{name}Pulp", [(0.0, (0.97, 0.99, 0.88)), (0.12, (0.86, 0.95, 0.52)), (0.8, (0.74, 0.90, 0.36)),
                                    (0.88, (0.95, 0.98, 0.86)), (0.94, (0.95, 0.98, 0.86)), (1.0, (0.27, 0.58, 0.10))],
                    coord="r_yz", lo=0.0, hi=R, rough=0.1, sss=0.4, sss_radius=(0.8, 1, 0.4), coat=0.8, coat_rough=0.05)
    assign_faces(ob, lime_skin_mat(f"{name}Skin", R), [(lambda n, c: n.z < -0.3, pulp)])
    return ob


def taco_shell(name, R=0.62, th_max=88, mat=None):
    ob = polar_disc(name, 28, 128, R, R)
    rnd = random.Random(len(name))
    ph = rnd.uniform(0, 6)
    tm = math.radians(th_max)
    rf = R / tm

    def fold(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.02 * math.sin(5 * a + ph)
        x, y = co.x * k, co.y * k
        th = y / rf
        return Vector((x, rf * math.sin(th), rf * (1 - math.cos(th))))
    deform(ob, fold)
    solidify(ob, 0.045)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, mat or tortilla_mat(f"{name}Mat", R))
    return ob, rf


def taco(prefix, mats):
    shell, rf = taco_shell(f"{prefix}Shell", 0.66, 96, mats["tortilla"])
    meat = capsule(f"{prefix}Meat", 1.02, 0.27, 48, 32)
    deform(meat, lambda co: Vector((co.x, co.y * 1.2, co.z * 0.8 + 0.3)))
    push_normals(meat, lambda co, n: 0.03 * fbm(co * 5 + Vector((len(prefix), 0, 0))))
    smooth(meat)
    assign(meat, mats["meat"])
    parts = [shell, meat]

    def chunk(i, rnd):
        c = rcube(f"{prefix}Beef{i}", *(rnd.uniform(0.07, 0.1) for _ in range(2)), rnd.uniform(0.05, 0.07))
        c.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), 0)
        return assign(c, mats["beef"][i % 2])
    scatter_on(meat, 26, chunk, seed=len(prefix), area=0.52, spacing=0.085, zmin=0.38)
    salsa_bits(meat, f"{prefix}S", n_tomato=14, n_onion=10, n_herb=14, s=0.85, area=0.48, seed=len(prefix) + 2,
               zmin=0.42)
    return [o for o in bpy.data.objects if o.name.startswith(prefix) and o.type == "MESH"]


def dish_taco():
    parts = [talavera_plate("TacoPlate", 1.3)]
    mats = {
        "tortilla": tortilla_mat("TacoTortilla", 0.66),
        "meat": material("TacoMeat", [(0.0, (0.40, 0.17, 0.08)), (1.0, (0.62, 0.30, 0.14))], coord="z", lo=0.2,
                         hi=0.6, rough=0.3, sss=0.2, coat=0.5, bump=0.4, bump_scale=16, vary=0.15),
        "beef": [material(f"TacoBeef{i}", [(0.0, c0), (1.0, c1)], coord="z", lo=-0.05, hi=0.06, rough=0.3, sss=0.2,
                          sss_radius=(1, 0.4, 0.3), coat=0.6, vary=0.15, vary_scale=8)
                 for i, (c0, c1) in enumerate((((0.36, 0.14, 0.06), (0.66, 0.32, 0.15)),
                                               ((0.46, 0.20, 0.09), (0.76, 0.42, 0.22))))],
    }
    for i, (y, rz) in enumerate(((-0.45, 6), (0.45, -6))):
        t = taco(f"Taco{i}", mats)
        rotate_all(t, (0, 0, math.radians(rz)))
        for o in t:
            o.location += Vector((0, y, 0.1))
        parts += t
    w = lime_wedge("TacoLime", 0.3)
    w.rotation_euler = (math.radians(180 + 34), 0, math.radians(90))
    w.location = (0.98, 0.0, 0.0)
    bpy.context.view_layer.update()
    ground([w], 0.105)
    parts.append(w)
    return rotate_all(parts, (0, 0, math.radians(-20)))


def burrito_half(prefix, mats, L=1.15, R=0.52, seed=0, wrap=True):
    body = capsule(prefix, 2 * L, R, 72, 56)
    deform(body, lambda co: Vector((co.x, co.y, co.z * 0.9)))
    push_normals(body, lambda co, n: 0.01 * fbm(co * 3 + Vector((seed, 0, 0))))
    bisect(body, (0, 0, 0), (1, 0, 0))
    smooth(body, 50)
    assign(body, mats["tortilla"])
    face = polar_disc(f"{prefix}Face", 30, 128, R, R * 0.9)
    rnd = random.Random(seed)
    rice_c, tort_c = (0.97, 0.95, 0.90), (1.0, 0.86, 0.58)

    def col(co, n):
        rr = math.hypot(co.x / R, co.y / (R * 0.9))
        a = math.atan2(co.y, co.x)
        # край лепешки и виток внутри
        if rr > 0.9:
            return tort_c
        sp = 0.62 + 0.25 * ((a + math.pi) / (2 * math.pi))
        if abs(rr - sp) < 0.035:
            return mix(tort_c, (0.95, 0.78, 0.5), 0.3)
        return mix(rice_c, (0.92, 0.88, 0.80), 0.5 + 0.5 * fbm(co * 20))
    vcol(face, col)
    deform(face, lambda co: Vector((co.x, co.y, 0.05 * max(0.0, 1 - (co.x / R) ** 2 - (co.y / (R * 0.9)) ** 2))))
    smooth(face)
    assign(face, vmat(f"{prefix}FaceMat", rough=0.45, sss=0.4, sss_radius=(1, 1, 0.9), bump=0.4, bump_scale=60,
                      bump_detail=2, coat=0.2))
    bits = [face]
    for i in range(14):
        a, rr = rnd.uniform(0, 6.28), 0.72 * R * math.sqrt(rnd.random())
        b = sphere(f"{prefix}Bean{i}", 1.0, 20, 12)
        b.scale = (0.088, 0.058, 0.045)
        b.rotation_euler = (0, 0, rnd.uniform(0, 3.14))
        b.location = (rr * math.cos(a), rr * math.sin(a) * 0.9, 0.05 * (1 - (rr / R) ** 2) + 0.01)
        apply_transform(b)
        assign(smooth(b), mats["bean"])
        bits.append(b)
    for i in range(20):
        a, rr = rnd.uniform(0, 6.28), 0.8 * R * math.sqrt(rnd.random())
        g = capsule(f"{prefix}Rice{i}", 0.08, 0.022, 12, 8)
        g.rotation_euler = (0, 0, rnd.uniform(0, 3.14))
        g.location = (rr * math.cos(a), rr * math.sin(a) * 0.9, 0.05 * (1 - (rr / R) ** 2) + 0.012)
        apply_transform(g)
        assign(smooth(g), mats["rice"])
        bits.append(g)
    for i, key in enumerate(("tom", "tom", "tom", "herb", "herb", "cheese", "cheese")):
        a, rr = rnd.uniform(0, 6.28), 0.65 * R * math.sqrt(rnd.random())
        c = rcube(f"{prefix}Bit{i}", 0.05, 0.045, 0.03)
        c.location = (rr * math.cos(a), rr * math.sin(a) * 0.9, 0.05 * (1 - (rr / R) ** 2) + 0.01)
        apply_transform(c)
        assign(c, mats[key])
        bits.append(c)
    for o in bits:
        o.rotation_euler = (0, math.radians(90), 0)
        o.location.x += 0.004
        apply_transform(o)
    if not wrap:
        return [body] + bits
    # бумажная обертка на дальней части
    paper = capsule(f"{prefix}Paper", 2 * L, R + 0.03, 72, 56)
    deform(paper, lambda co: Vector((co.x, co.y, co.z * 0.9)))
    bisect(paper, (-0.38 * L, 0, 0), (1, 0, 0), fill=False)

    def ragged(co):
        e = max(0.0, co.x + 0.6 * L) / (0.22 * L)
        a = math.atan2(co.z, co.y)
        return Vector((co.x + 0.05 * e * math.sin(a * 7 + seed) + 0.03 * e * fbm(co * 6), co.y, co.z))
    deform(paper, ragged)
    push_normals(paper, lambda co, n: 0.014 * fbm(co * 6 + Vector((seed, 2, 0))))
    solidify(paper, 0.012)
    smooth(paper, 60)
    assign(paper, mats["paper"])
    return [body, paper] + bits


def dish_burrito():
    parts = [clay_plate("BurritoPlate", 1.3)]
    mats = {
        "tortilla": tortilla_mat("BurritoTortilla", 0.9),
        "bean": material("BurritoBean", [(0.0, (0.06, 0.03, 0.05)), (1.0, (0.24, 0.14, 0.18))], coord="x", lo=-0.05,
                         hi=0.05, rough=0.15, coat=0.9),
        "rice": flat("BurritoRice", (1.0, 1.0, 0.97), rough=0.3, sss=0.5, coat=0.3),
        "tom": flat("BurritoTom", (0.90, 0.16, 0.08), rough=0.15, sss=0.3, coat=0.8),
        "herb": flat("BurritoHerb", (0.30, 0.66, 0.16), rough=0.3, coat=0.5),
        "cheese": flat("BurritoCheese", (1.0, 0.74, 0.16), rough=0.25, sss=0.4, coat=0.5),
        "paper": material("BurritoPaper", [(0.0, (0.88, 0.84, 0.76)), (1.0, (1.0, 0.98, 0.94))], coord="nz", lo=-1,
                          hi=1, rough=0.55, sheen=0.3, bump=0.3, bump_scale=8, bump_detail=4),
    }
    # две половинки рядом наискосок, срезы к камере
    axis = Vector((-0.87, 0.5, 0))
    perp = Vector((0.5, 0.87, 0))
    for k, (shift, seed) in enumerate(((0.0, 1), (1.18, 2))):
        h = burrito_half(f"Bur{k}", mats, seed=seed, wrap=(k == 1))
        rotate_all(h, (0, math.radians(-10), 0))
        rotate_all(h, (0, 0, math.atan2(-axis.y, -axis.x)))
        off = perp * shift + axis * (-0.25 * shift)
        for o in h:
            o.location += off
        ground(h, 0.1)
        parts += h
    # блюдо по центру еды
    food = parts[1:]
    bpy.context.view_layer.update()
    xs = [(o.matrix_world @ v.co) for o in food for v in list(o.data.vertices)[::7]]
    cx = (min(p.x for p in xs) + max(p.x for p in xs)) / 2
    cy = (min(p.y for p in xs) + max(p.y for p in xs)) / 2
    for o in food:
        o.location -= Vector((cx, cy, 0))
    return rotate_all(parts, (0, 0, math.radians(-6)))


def round_board(name="RoundBoard", r=1.3):
    ob = lathe(name, [(0.0, 0.0), (r - 0.05, 0.0), (r, 0.04), (r + 0.01, 0.09), (r - 0.03, 0.14), (0.0, 0.14)], 128)
    subdivide(ob, 1)
    smooth(ob, 50)
    wood = material(f"{name}Wood", [(0.0, (0.70, 0.46, 0.24)), (1.0, (0.86, 0.62, 0.36))], coord="x", lo=-r, hi=r,
                    rough=0.5, coat=0.2, bump=0.12, bump_scale=5, vary=0.14, vary_scale=2)
    add_stripes(wood, (0.62, 0.38, 0.18), scale=3.5, angle=0, width=0.1, nz_min=-1.0, strength=0.4)
    assign(ob, wood)
    return ob


def red_chili_ring(name, r=0.08):
    ring = torus(f"{name}Ring", r * 0.8, r * 0.22, 40, 12)
    deform(ring, lambda co: Vector((co.x, co.y, co.z * 0.75)))
    assign(smooth(ring), material(f"{name}Mat", [(0.0, (0.72, 0.04, 0.03)), (1.0, (1.0, 0.22, 0.12))], coord="z",
                                  lo=-0.02, hi=0.02, rough=0.12, coat=0.9, sss=0.3))
    seeds = []
    for k in range(3):
        a = k * 2.1 + 0.3
        sd = sphere(f"{name}Seed{k}", r * 0.13, 12, 8)
        sd.scale = (1.3, 1, 0.5)
        sd.location = (r * 0.45 * math.cos(a), r * 0.45 * math.sin(a), 0.0)
        apply_transform(sd)
        assign(smooth(sd), flat(f"{name}SeedMat", (1.0, 0.92, 0.70), rough=0.3, coat=0.5))
        seeds.append(sd)
    return [ring] + seeds


def dish_quesadilla():
    parts = [round_board("QBoard", 1.4)]
    tort = material("QTortilla", [(0.0, (0.98, 0.76, 0.38)), (0.7, (0.95, 0.68, 0.30)), (1.0, (0.86, 0.56, 0.22))],
                    coord="r", lo=0.0, hi=1.0, rough=0.42, sss=0.25, sss_radius=(1, 0.8, 0.5), coat=0.3, sheen=0.2,
                    bump=0.1, bump_scale=18, vary=0.12, vary_scale=4)
    add_speckles(tort, (0.78, 0.44, 0.12), scale=6.0, threshold=0.58, strength=0.75)
    add_speckles(tort, (0.48, 0.24, 0.07), scale=15.0, threshold=0.65, strength=0.9)
    cheese = material("QCheese", [(0.0, (1.0, 0.60, 0.06)), (1.0, (1.0, 0.80, 0.26))], coord="z", lo=0.1, hi=0.4,
                      rough=0.1, sss=0.6, sss_radius=(1, 0.7, 0.2), coat=0.9, coat_rough=0.04)
    Rq, H, z0, off, yshift = 1.1, 0.34, 0.14, 0.26, 0.0
    wedges = []
    for k in range(3):
        a0, a1 = math.radians(60 * k), math.radians(60 * (k + 1))
        bis = (a0 + a1) / 2
        pts = [(0.0, 0.0)] + [(Rq * math.cos(a0 + (a1 - a0) * i / 16), Rq * math.sin(a0 + (a1 - a0) * i / 16))
                              for i in range(17)]
        c = (0.55 * Rq * math.cos(bis), 0.55 * Rq * math.sin(bis))
        w = outline_slab(f"QWedge{k}", pts, H, p=3.0, cuts=36, center=c)
        push_normals(w, lambda co, n: (0.035 * max(0.0, n.z) + 0.005 * fbm(co * 6)))
        deform(w, lambda co: Vector((co.x, co.y, co.z + H / 2 + z0)))
        smooth(w)
        assign_faces(w, tort, [(lambda n, cc: abs(n.z) < 0.8 and z0 + 0.09 < cc.z < z0 + 0.24, cheese)])
        base = Vector((off * math.cos(bis), off * math.sin(bis) + yshift, 0))
        w.location = base
        wedges.append((w, a0, a1, bis, base))
        parts.append(w)
    bpy.context.view_layer.update()
    rnd = random.Random(4)

    def side_point(base, a, t, dz=0.0):
        return base + Vector((t * Rq * math.cos(a), t * Rq * math.sin(a), z0 + H * 0.52 + dz))
    # тянущийся сыр между дольками: провисает к середине
    for k in range(2):
        _, _, a1, _, b0 = wedges[k]
        _, a0n, _, _, b1 = wedges[k + 1]
        for j, t in enumerate((0.32, 0.58, 0.84)):
            p0, p1 = side_point(b0, a1, t), side_point(b1, a0n, t)
            pts = [tuple(p0 + (p1 - p0) * (u / 14) + Vector((0, 0, -0.07 * math.sin(math.pi * u / 14))))
                   for u in range(15)]
            st = tube(f"QStrand{k}{j}", pts, 0.05, taper=(1.0, 1.0))
            assign(smooth(st), cheese)
            parts.append(st)
    # сыр вытекает по срезам и по краю
    for k, (w, a0, a1, bis, base) in enumerate(wedges):
        for side_a, sgn in ((a0, -1), (a1, 1)):
            if (k == 0 and sgn < 0) or (k == 2 and sgn > 0):
                pts = [tuple(side_point(base, side_a, 0.12 + 0.8 * u / 10)
                             + Vector((-sgn * math.sin(side_a) * 0.035, sgn * math.cos(side_a) * 0.035, -0.02)))
                       for u in range(11)]
                ooze = tube(f"QOozeS{k}{sgn}", pts, 0.065, taper=(0.8, 1.15))
                assign(smooth(ooze), cheese)
                parts.append(ooze)
        for j in range(2):
            a = a0 + (a1 - a0) * (0.28 + 0.44 * j) + rnd.uniform(-0.08, 0.08)
            d = Vector((math.cos(a), math.sin(a), 0))
            # сыр выдавливается из шва по краю
            blob = sphere(f"QOoze{k}{j}", 0.12, 32, 16)
            blob.scale = (1.7, 0.75, 0.42)
            blob.rotation_euler = (0, 0, a + math.pi / 2)
            blob.location = base + d * (Rq - 0.02) + Vector((0, 0, z0 + H * 0.47))
            apply_transform(blob)
            push_normals(blob, lambda co, n: 0.01 * fbm(co * 9))
            assign(smooth(blob), cheese)
            parts.append(blob)
        for j in range(3):
            rr = Rq * (0.3 + 0.2 * j) + rnd.uniform(-0.05, 0.05)
            a = a0 + (a1 - a0) * rnd.uniform(0.3, 0.7)
            x, y = base.x + rr * math.cos(a), base.y + rr * math.sin(a)
            loc, nor = ray_down(x, y)
            if loc is None:
                continue
            ring = red_chili_ring(f"QChili{k}{j}", 0.11)
            for o in ring:
                o.location.z += 0.014
            place_on(ring, loc, nor, rnd.uniform(0, 6))
            parts += ring
    # дольки по центру доски, дугой к камере: видно сыр между ними
    food = parts[1:]
    bpy.context.view_layer.update()
    pts_ = [(o.matrix_world @ v.co) for o in food for v in list(o.data.vertices)[::5]]
    cx = (min(p_.x for p_ in pts_) + max(p_.x for p_ in pts_)) / 2
    cy = (min(p_.y for p_ in pts_) + max(p_.y for p_ in pts_)) / 2
    for o in food:
        o.location -= Vector((cx, cy, 0))
    bpy.context.view_layer.update()
    return rotate_all(parts, (0, 0, math.radians(180 - 12)))


def dish_guacamole():
    s = 1.35
    parts = molcajete("GuacMolca", s)
    guac = material("GuacMat", [(0.0, (0.30, 0.50, 0.10)), (0.5, (0.46, 0.68, 0.16)), (1.0, (0.64, 0.82, 0.30))],
                    coord="z", lo=0.8, hi=1.2, rough=0.35, sss=0.3, sss_radius=(0.6, 1, 0.3), coat=0.4, bump=0.45,
                    bump_scale=12, bump_detail=6, vary=0.15, vary_scale=4)
    fill = bowl_fill("GuacFill", 0.72 * s, 0.62 * s, 0.24, guac, noise=0.08, seed=2)
    parts.append(fill)
    avo = material("GuacAvo", [(0.0, (0.52, 0.72, 0.18)), (1.0, (0.80, 0.90, 0.42))], coord="z", lo=-0.05, hi=0.06,
                   rough=0.25, sss=0.4, coat=0.5)
    red_onion = material("GuacOnion", [(0.0, (0.56, 0.12, 0.34)), (1.0, (0.86, 0.46, 0.62))], coord="z", lo=-0.03,
                         hi=0.03, rough=0.15, sss=0.4, coat=0.7)
    tom = material("GuacTom", [(0.0, (0.80, 0.08, 0.04)), (1.0, (0.98, 0.26, 0.12))], coord="z", lo=-0.04, hi=0.04,
                   rough=0.12, sss=0.4, coat=0.8)
    herb = herb_mat("GuacHerb")

    def avo_c(i, rnd):
        c = rcube(f"GAvo{i}", rnd.uniform(0.08, 0.11), rnd.uniform(0.08, 0.1), rnd.uniform(0.06, 0.08))
        c.location.z -= 0.02
        c.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0)
        return assign(c, avo)
    scatter_on(fill, 14, avo_c, seed=3, area=0.85, spacing=0.14, zmin=0.9)

    def oni(i, rnd):
        c = rcube(f"GOni{i}", 0.06, 0.045, 0.03)
        c.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0)
        return assign(c, red_onion)
    scatter_on(fill, 14, oni, seed=5, area=0.85, spacing=0.1, zmin=0.9)

    def tm(i, rnd):
        c = rcube(f"GTom{i}", 0.06, 0.06, 0.045)
        return assign(c, tom)
    scatter_on(fill, 8, tm, seed=8, area=0.8, spacing=0.12, zmin=0.9)

    def hb(i, rnd):
        c = cilantro(f"GHerb{i}", rnd.uniform(0.08, 0.11))
        c.location.z += 0.03
        return assign(c, herb)
    scatter_on(fill, 10, hb, seed=9, area=0.8, spacing=0.15, zmin=0.9)
    cmat = chip_mat("GChipMat")
    for i, (a, rr, tilt) in enumerate(((100, 0.38, 22), (220, 0.42, 26), (340, 0.36, 20), (40, 0.12, 8))):
        c = chip(f"GChip{i}", 0.46, curve=0.25, seed=i)
        assign(c, cmat)
        th = math.radians(a)
        c.rotation_euler = (math.radians(90 - tilt), 0, th - math.pi / 2)
        bpy.context.view_layer.update()
        x, y = rr * math.cos(th), rr * math.sin(th)
        loc, _ = ray_down(x, y)
        c.location = (x, y, (loc.z if loc else 1.0) + 0.16)
        parts.append(c)
    w = lime_wedge("GuacLime", 0.3)
    w.rotation_euler = (math.radians(180 + 34 + 15), 0, math.radians(30))
    bpy.context.view_layer.update()
    loc, _ = ray_down(0.5, -0.45)
    w.location = (0.62, -0.5, 0)
    bpy.context.view_layer.update()
    ground([w], (loc.z if loc else 0.9) - 0.04)
    parts.append(w)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def lime_wheel(name, R=0.3, th=0.05, wrap=0.0):
    """Кружок лайма; wrap - радиус цилиндра, по которому кружок изогнут (прижат к стеклу)."""
    face = citrus_face(f"{name}Face", R, segs=10, relief=0.02)
    back = citrus_face(f"{name}Back", R, segs=10, relief=0.02)
    rind = cylinder(f"{name}Rind", R, th, 64)
    smooth(rind, 40)
    assign(rind, lime_skin_mat(f"{name}RindMat", R))
    face.location.z = th / 2
    back.rotation_euler = (math.pi, 0, 0)
    back.location.z = -th / 2
    parts = [face, back, rind]
    for o in parts:
        apply_transform(o)
    if wrap:
        for o in parts:
            deform(o, lambda co: Vector(((wrap + co.z) * math.sin(co.x / wrap), co.y, (wrap + co.z) * math.cos(co.x / wrap)
                                         - wrap)))
    return parts


def mint_leaf(name, size=0.3):
    """Лист мяты: яйцевидный, с зубчиками и прожилкой посередине."""
    ob = polar_disc(name, 18, 120, 1.0, 1.0)

    def fn(co):
        a = math.atan2(co.y, co.x)
        rr = math.hypot(co.x, co.y)
        x, y = co.x, co.y * 0.62
        # к кончику (+x) уже, у основания шире
        y *= 1.0 - 0.45 * max(0.0, x) ** 1.3 + 0.1 * max(0.0, -x)
        k = 1.0 + 0.05 * math.sin(22 * a) * rr ** 4
        x, y = x * k, y * k
        z = 0.22 * (y / 0.62) ** 2 - 0.05 * math.exp(-(y / 0.06) ** 2) * (1 - abs(x)) + 0.1 * x * x
        return Vector((x * size, y * size, z * size))
    deform(ob, fn)
    solidify(ob, 0.05 * size)
    subdivide(ob, 1)
    smooth(ob)
    return assign(ob, material(f"{name}Mat", [(0.0, (0.46, 0.80, 0.30)), (0.6, (0.26, 0.64, 0.18)), (1.0, (0.14, 0.46, 0.12))],
                               coord="r", lo=0.0, hi=size, rough=0.3, sss=0.35, sss_radius=(0.5, 1, 0.3), coat=0.5,
                               bump=0.15, bump_scale=30))


def dish_limeade():
    glass = lathe("LimeadeJar", [(0.0, 0.0), (0.46, 0.0), (0.50, 0.03), (0.52, 0.1), (0.52, 1.15), (0.50, 1.25),
                                 (0.47, 1.31), (0.47, 1.35), (0.49, 1.37), (0.47, 1.39), (0.49, 1.41), (0.47, 1.43),
                                 (0.48, 1.47), (0.46, 1.5), (0.44, 1.5), (0.44, 1.32), (0.47, 1.25), (0.49, 1.15),
                                 (0.49, 0.14), (0.45, 0.11), (0.0, 0.11)], 96)
    smooth(glass, 50)
    assign(glass, glass_mat("LimeadeGlass"))
    liquid = lathe("Limeade", [(0.0, 0.11), (0.44, 0.11), (0.475, 0.15), (0.475, 1.14), (0.464, 1.2), (0.0, 1.2)], 96)
    smooth(liquid, 50)
    lmat = material("LimeadeMat", [(0.0, (0.62, 0.88, 0.24)), (0.7, (0.78, 0.95, 0.40)), (1.0, (0.88, 0.98, 0.56))],
                    coord="z", lo=0.1, hi=1.2, rough=0.1, sss=0.5, sss_radius=(0.7, 1, 0.4), coat=0.6)
    glow(lmat, (0.78, 0.95, 0.42), 0.3)
    assign(liquid, lmat)
    parts = [glass, liquid]
    # кружки лайма прижаты к стеклу изнутри
    for i, (ang, z, rz) in enumerate(((-100, 0.62, 10), (-48, 0.38, -20), (160, 0.7, 0), (40, 0.45, 30))):
        w = lime_wheel(f"LWheel{i}", 0.26, 0.03, wrap=0.47)
        rotate_all(w, (math.radians(-90), 0, 0))
        rotate_all(w, (0, math.radians(rz), 0))
        for o in w:
            o.location = (0, 0, 0)
        rotate_all(w, (0, 0, math.radians(ang + 90)))
        for o in w:
            o.location.z += z
        parts += w
    # кружок на краю банки: прорезь насаживается на стекло
    rim = lime_wheel("LRim", 0.3, 0.05)
    for o in rim:
        bm = bmesh.new()
        bm.from_mesh(o.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if abs(v.co.x) < 0.035 and v.co.y < 0.01], context="VERTS")
        bm.to_mesh(o.data)
        bm.free()
        o.data.update()
    rotate_all(rim, (math.radians(90), 0, 0))
    rotate_all(rim, (0, 0, math.radians(90)))
    rotate_all(rim, (0, 0, math.radians(40)))
    for o in rim:
        o.location += Vector((0.455 * math.cos(math.radians(40)), 0.455 * math.sin(math.radians(40)), 1.47))
    parts += rim
    # кружок плавает сверху
    fl = lime_wheel("LFloat", 0.24, 0.04)
    rotate_all(fl, (math.radians(-28), math.radians(10), 0))
    for o in fl:
        o.location += Vector((0.12, -0.2, 1.2))
    parts += fl
    for i, (x, y, rot) in enumerate(((-0.18, -0.1, (0.3, 0.2, 0.5)), (0.14, -0.2, (-0.2, 0.4, 1.2)),
                                     (-0.05, 0.2, (0.5, -0.3, 0.2)))):
        c = ice_cube(f"LIce{i}", 0.14, rot)
        c.location = (x, y, 1.21)
        parts.append(c)
    for i, (x, y, rz, rx) in enumerate(((-0.05, 0.05, 40, -38), (-0.2, 0.12, 160, -42), (-0.08, -0.06, 250, -32))):
        lf = mint_leaf(f"Mint{i}", 0.32)
        lf.location = (0.18, 0, 0)
        apply_transform(lf)
        rotate_all([lf], (math.radians(rx), 0, 0))
        rotate_all([lf], (0, 0, math.radians(rz)))
        lf.location += Vector((x, y, 1.3))
        parts.append(lf)
    straw_mat = material("StrawMat", [(0.0, (1.0, 1.0, 1.0)), (1.0, (1.0, 1.0, 1.0))], rough=0.25, coat=0.6)
    add_turns(straw_mat, (0.22, 0.66, 0.24), count=3, width=0.45, twist=4.0)
    straw = tube("LStraw", [(0.0, 0.0, 0.0), (0.0, 0.0, 1.9)], 0.055)
    assign(smooth(straw), straw_mat)
    straw.rotation_euler = (math.radians(10), math.radians(16), 0)
    straw.location = (-0.12, 0.08, 0.3)
    parts.append(straw)
    return parts


M.MODELS.update({
    "masa": masa,
    "tortilla": tortilla,
    "beef": beef,
    "salsa": salsa,
    "beans": beans,
    "chili": chili,
    "lime": lime,
    "onion": onion,
    "nachos": nachos,
    "churros": churros,
    "horchata": horchata,
    "tamale": tamale,
    "flan": flan,
    "concha": concha,
    "paleta": paleta,
    "dish_taco": dish_taco,
    "dish_burrito": dish_burrito,
    "dish_quesadilla": dish_quesadilla,
    "dish_guacamole": dish_guacamole,
    "dish_limeade": dish_limeade,
})
