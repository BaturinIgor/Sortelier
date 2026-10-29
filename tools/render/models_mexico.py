"""Мексиканская кухня (биом 4): ингредиенты, закуски и блюда."""
import math
import random

import bpy
from mathutils import Vector
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
    attr = me.color_attributes.new(name, "FLOAT_COLOR", "POINT")
    for v in me.vertices:
        attr.data[v.index].color = (*lin(fn(v.co.copy(), v.normal.copy())), 1.0)
    return ob


def vmat(name, attr="Col", **kw):
    """Материал с цветом из атрибута вершин."""
    mat = material(name, [(0.0, (1, 1, 1)), (1.0, (1, 1, 1))], **kw)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    at = nodes.new("ShaderNodeAttribute")
    at.attribute_name = attr
    links.new(at.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
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
    lo, _, _ = R_bounds(objs)
    for o in objs:
        o.location.z += z - lo
    bpy.context.view_layer.update()
    return objs


def R_bounds(objs):
    zs = []
    for o in objs:
        mw = o.matrix_world
        zs += [(mw @ v.co).z for v in o.data.vertices]
    return min(zs), max(zs), None


def world_tree(ob, dz=0.0):
    mw = ob.matrix_world
    verts = [mw @ v.co + Vector((0, 0, dz)) for v in ob.data.vertices]
    return BVHTree.FromPolygons(verts, [tuple(p.vertices) for p in ob.data.polygons]), verts


def drop(ob, others, floor=0.0, step=0.012, top=None):
    """Опускает объект сверху, пока он не коснется других: куча без пересечений."""
    bpy.context.view_layer.update()
    trees = [world_tree(o)[0] for o in others]
    mw = ob.matrix_world
    base = [mw @ v.co for v in ob.data.vertices]
    polys = [tuple(p.vertices) for p in ob.data.polygons]
    zmin = min(v.z for v in base)
    dz = (top if top is not None else 3.0) - zmin
    while True:
        nz = dz - step
        if zmin + nz < floor:
            break
        tree = BVHTree.FromPolygons([v + Vector((0, 0, nz)) for v in base], polys)
        if any(tree.overlap(t) for t in trees):
            break
        dz = nz
    ob.location.z += dz
    bpy.context.view_layer.update()
    return ob


def husk_mat(name):
    mat = material(name, [(0.0, (0.86, 0.74, 0.46)), (0.5, (0.94, 0.86, 0.62)), (1.0, (0.99, 0.94, 0.76))],
                   coord="nz", lo=-1, hi=1, rough=0.5, sss=0.3, sss_radius=(1, 0.9, 0.5), coat=0.25, sheen=0.3,
                   vary=0.1, vary_scale=4)
    add_stripes(mat, (0.80, 0.66, 0.40), scale=4.0, angle=90, width=0.14, nz_min=-1.0, strength=0.55)
    return mat


def tortilla_mat(name, r=1.0):
    mat = material(name, [(0.0, (1.0, 0.91, 0.68)), (0.7, (0.99, 0.86, 0.58)), (1.0, (0.93, 0.73, 0.42))],
                   coord="r", lo=0.0, hi=r, rough=0.5, sss=0.3, sss_radius=(1, 0.8, 0.5), coat=0.15, sheen=0.25,
                   bump=0.08, bump_scale=20, vary=0.08, vary_scale=4)
    add_speckles(mat, (0.86, 0.60, 0.28), scale=7.0 / r, threshold=0.62, strength=0.55)
    add_speckles(mat, (0.60, 0.36, 0.14), scale=17.0 / r, threshold=0.69, strength=0.8)
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
    mat = material(name, [(0.0, (0.94, 0.62, 0.16)), (0.5, (1.0, 0.78, 0.26)), (1.0, (1.0, 0.86, 0.40))],
                   coord="r", lo=0.45, hi=0.0, rough=0.38, sss=0.3, sss_radius=(1, 0.7, 0.2), coat=0.3, bump=0.25,
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
    husk = husk_leaf("MasaHusk", 1.35, 0.52)
    husk.rotation_euler = (0, math.radians(-68), math.radians(150))
    husk.location = (0.62, 0.42, 0.62)
    return [bowl, dough_, husk]


def husk_leaf(name, length=1.4, width=0.5, cup=0.22):
    """Сухой кукурузный лист: узкий кончик, желобок вдоль."""
    rx, ry = length / 2, width / 2
    ob = polar_disc(name, 20, 120, rx, ry)

    def fn(co):
        xn = co.x / rx
        ky = (1.0 - 0.92 * max(0.0, xn) ** 1.4) * (1.0 - 0.15 * max(0.0, -xn) ** 3)
        y = co.y * ky
        z = cup * (y / ry) ** 2 + 0.08 * xn * xn + 0.012 * math.sin(co.x * 9 + co.y * 4)
        return Vector((co.x, y, z))
    deform(ob, fn)
    solidify(ob, 0.022)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, husk_mat(f"{name}Mat"))
    return ob


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
    ob = polar_disc(name, 34, 160, r, r)
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
    solidify(ob, 0.045 * r)
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
        t.location = (0.03 * math.cos(i * 2.1), 0.03 * math.sin(i * 2.1), i * 0.052)
        parts.append(t)
    top = tortilla_disc("TortillaTop", 1.0, seed=5, fold=fold_fn(0.42, 0.055, math.radians(166)), mat=mat)
    top.rotation_euler = (0, 0, math.radians(-62))
    top.location = (0.0, 0.0, 3 * 0.052)
    parts.append(top)
    return rotate_all(parts, (math.radians(16), 0, 0))


def beef_mat(name, r=1.3):
    mat = material(name, [(0.0, (0.26, 0.10, 0.05)), (0.35, (0.40, 0.16, 0.08)), (0.75, (0.58, 0.25, 0.12)),
                          (1.0, (0.64, 0.30, 0.15))],
                   coord="nz", lo=-1, hi=1, rough=0.3, sss=0.25, sss_radius=(1, 0.3, 0.2), coat=0.5, coat_rough=0.18,
                   bump=0.3, bump_scale=10, bump_detail=8, vary=0.18, vary_scale=2.5)
    add_stripes(mat, (0.17, 0.06, 0.03), scale=0.62, angle=35, width=0.15, nz_min=0.55, strength=0.85)
    add_stripes(mat, (0.22, 0.08, 0.04), scale=0.62, angle=-55, width=0.08, nz_min=0.55, strength=0.55)
    add_speckles(mat, (0.20, 0.07, 0.03), scale=9, threshold=0.66, strength=0.5)
    return mat


def beef():
    outline = polar_outline(lambda a: 1.0 + 0.10 * math.cos(a) + 0.07 * math.cos(2 * a + 1.0)
                            + 0.04 * math.sin(3 * a + 0.5))
    outline = [(x * 1.3, y * 0.85) for x, y in outline]
    ob = outline_slab("Steak", outline, 0.30, p=2.6, cuts=40)
    deform(ob, lambda co: Vector((co.x, co.y, co.z + 0.15)))
    push_normals(ob, lambda co, n: 0.025 * fbm(co * 1.8, 3) + 0.006 * fbm(co * 8, 2))
    smooth(ob)
    assign(ob, beef_mat("SteakMat"))
    # полоска жира по дальнему краю
    reach = reach_fn(outline)
    pts = []
    for i in range(30):
        a = math.radians(25 + 125 * i / 29)
        d = reach(a) - 0.05
        pts.append((d * math.cos(a), d * math.sin(a), 0.17))
    fat = tube("SteakFat", pts, 0.085, taper=(0.4, 0.5))
    deform(fat, lambda co: Vector((co.x, co.y, 0.17 + (co.z - 0.17) * 1.5)))
    smooth(fat)
    assign(fat, material("FatMat", [(0.0, (0.90, 0.66, 0.40)), (1.0, (1.0, 0.86, 0.62))], coord="z", lo=0.05, hi=0.32,
                         rough=0.25, sss=0.5, sss_radius=(1, 0.8, 0.5), coat=0.6))
    return rotate_all([ob, fat], (math.radians(10), 0, math.radians(-14)))


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
    mound = sphere("BeanMound", 0.5, 64, 32)
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
    scatter_on(mound, 60, make, seed=6, area=0.5, spacing=0.085)
    return [o for o in bpy.data.objects if o.type == "MESH"]


CHILI_PROF = [(0.0, 0.0), (0.02, 0.02), (0.05, 0.08), (0.09, 0.25), (0.13, 0.5), (0.165, 0.8), (0.19, 1.1),
              (0.205, 1.3), (0.2, 1.42), (0.17, 1.5), (0.10, 1.55), (0.0, 1.53)]


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
    deform(body, lambda co: Vector((co.x + curve * (1 - co.z / 1.55) ** 2.2, co.y, co.z)))
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
        smax = 0.26 + 0.07 * math.cos(5 * a)
        r, z, (nr, nz) = profile_point(CHILI_PROF, t * smax)
        off = 0.028
        r, z = r + nr * off, z + nz * off
        return Vector((r * math.cos(a), r * math.sin(a), z))
    deform(cal, drape)
    solidify(cal, 0.025)
    subdivide(cal, 1)
    smooth(cal)
    assign(cal, green)
    stem = tube(f"{name}Stem", [(0.0, 0.0, 1.52), (0.0, 0.0, 1.64), (0.03, 0.0, 1.74), (0.1, 0.0, 1.82),
                                (0.17, 0.0, 1.85)], 0.04, taper=(1.15, 0.8))
    assign(smooth(stem), green)
    parts = [body, cal, stem]
    for o in parts:
        o.scale = (scale, scale, scale)
    return parts


def chili():
    a = chili_pepper("ChiliA", 0.5, 1.0)
    rotate_all(a, (0, math.radians(-90), 0))
    rotate_all(a, (math.radians(-90), 0, 0))
    rotate_all(a, (0, 0, math.radians(14)))
    for o in a:
        o.location += Vector((0.75, 0.0, 0.2))
    b = chili_pepper("ChiliB", -0.45, 0.88)
    rotate_all(b, (0, math.radians(-90), 0))
    rotate_all(b, (math.radians(90), 0, 0))
    rotate_all(b, (0, 0, math.radians(-12)))
    for o in b:
        o.location += Vector((0.62, 0.42, 0.18))
    parts = a + b
    ground(parts)
    return parts


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


M.MODELS.update({
    "masa": masa,
    "tortilla": tortilla,
    "beef": beef,
    "salsa": salsa,
    "beans": beans,
    "chili": chili,
    "lime": lime,
    "onion": onion,
})
