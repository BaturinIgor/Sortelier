"""Переделка блюд (партия 2): брускетта, капрезе, шарлотка, блинчики, круассан, эклер, пан-о-шоколя, паста,
тыквенный суп, кесадилья, тако, буррито, гуакамоле, онигири.

Подключается последним в models.EXTENSIONS, поэтому эти dish_* перекрывают прежние сборщики из models.py,
models_bakery.py, models_events.py и models_mexico.py. Свет, камера и мир общие (models.reset_scene).
Принципы: еда крупная и заполняет кадр, тарелка или доска - только подложка чуть шире еды; фактура
процедурная (шейдер Sh из models_remodel: шум, вороной, маски, рельеф), неровности формы, рассеяние и лак.
"""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, noise

import models as M
from models import *  # noqa: F401,F403  помощники
import models_bakery as BK
import models_events as EV
import models_mexico as MX
import models_remodel as RM
from models_remodel import Sh, _col, ss


# MARK: - Помощники

def obj_random(sh):
    """Случайное число объекта (0..1): у одинаковых кусочков разный рисунок."""
    n = sh.nodes.new("ShaderNodeObjectInfo")
    return n.outputs["Random"]


def jitter_vec(sh, amount=10.0):
    """Координаты объекта со сдвигом на случайное число объекта."""
    r = sh.math("MULTIPLY", obj_random(sh), amount)
    return sh.vmath("ADD", sh.tc("Object"), sh.combine(r, sh.math("MULTIPLY", r, 1.7), sh.math("MULTIPLY", r, 0.6)))


def wave(sh, vec=None, scale=3.0, distortion=4.0, detail=3.0, kind="RINGS", direction="X"):
    n = sh.nodes.new("ShaderNodeTexWave")
    n.wave_type = kind
    if kind == "RINGS":
        n.rings_direction = direction
    else:
        n.bands_direction = direction
    sh.links.new(sh.vec(vec), n.inputs["Vector"])
    n.inputs["Scale"].default_value = scale
    n.inputs["Distortion"].default_value = distortion
    n.inputs["Detail"].default_value = detail
    return n.outputs["Fac"]


def wood_sh(name, light=(0.92, 0.72, 0.46), dark=(0.74, 0.50, 0.28), along="x", scale=1.6):
    """Светлое дерево: продольные волокна и годовые кольца, полулак."""
    sh = Sh(name, rough=0.42, coat=0.35, coat_rough=0.18)
    sc = (0.25, 3.0, 3.0) if along == "x" else (3.0, 0.25, 3.0)
    v = sh.mapping(None, scale=sc)
    rings = wave(sh, v, scale, 6.0, 3.0, "RINGS", "Z")
    mid = tuple((a + b) / 2 for a, b in zip(light, dark))
    col = sh.ramp(rings, [(0.0, dark), (0.35, mid), (1.0, light)])
    fine = sh.noise(sh.mapping(None, scale=(0.15, 6.0, 6.0) if along == "x" else (6.0, 0.15, 6.0)), 18.0, 3)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(fine, 0.5, 0.7), 0.35), col, dark)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(None, 1.2, 2), 0.4, 0.7), 0.25), col, (0.98, 0.84, 0.62))
    sh.color(col)
    sh.bump(fine, 0.06, 0.004)
    sh.rough_vary(0.36, 0.52, 4.0)
    return sh.mat


def rounded_board(name, w, d, h=0.12, mat=None, p=6.0):
    """Доска со скругленными углами и мягкой фаской; верх на z=0."""
    ob = MX.rcube(name, w / 2, d / 2, h / 2, p, 10)
    subdivide(ob, 1)
    deform(ob, lambda co: Vector((co.x, co.y, co.z - h / 2)))
    push_normals(ob, lambda co, n: 0.003 * fbm(co * 3))
    smooth(ob)
    assign(ob, mat or wood_sh(f"{name}Wood"))
    return ob


def flat_plate(name, r, stops, rim=0.08, h=0.07):
    """Плоское блюдо с низким бортиком; верх дна на z=h."""
    prof = [(0.0, 0.0), (r * 0.80, 0.0), (r * 0.84, 0.02), (r * 0.86, h - 0.01), (r * 0.90, h + 0.005),
            (r * 0.97, h + rim * 0.6), (r, h + rim), (r * 0.985, h + rim + 0.012), (r * 0.95, h + rim * 0.8),
            (r * 0.88, h + 0.012), (r * 0.84, h), (0.0, h)]
    ob = lathe(name, prof, 160)
    subdivide(ob, 1)
    smooth(ob, 50)
    sh = Sh(f"{name}Mat", rough=0.14, coat=0.85, coat_rough=0.04)
    x, y, _ = sh.xyz()
    rr = sh.vmath("LENGTH", sh.combine(x, y, 0.0))
    sh.color(sh.ramp(sh.remap(rr, 0.0, r, smooth=False), stops))
    assign(ob, sh.mat)
    return ob


def surface_samples(ob, count, seed=0, cond=None, spacing=0.0, tries=40):
    """Точки на поверхности (мировые координаты) равномерно по площади: (точка, нормаль)."""
    bpy.context.view_layer.update()
    me = ob.data
    me.calc_loop_triangles()
    mw = ob.matrix_world
    nm = mw.to_3x3().inverted().transposed()
    tris = list(me.loop_triangles)
    acc, tot = [], 0.0
    for t in tris:
        tot += t.area
        acc.append(tot)
    import bisect as _b
    rnd = random.Random(seed)
    out = []
    grid = {}
    cell = max(spacing, 1e-3)
    vn = [v.normal.copy() for v in me.vertices]
    for _ in range(count * tries):
        if len(out) >= count:
            break
        t = tris[min(len(tris) - 1, _b.bisect_left(acc, rnd.random() * tot))]
        a, b = rnd.random(), rnd.random()
        if a + b > 1:
            a, b = 1 - a, 1 - b
        i0, i1, i2 = t.vertices
        v0, v1, v2 = me.vertices[i0].co, me.vertices[i1].co, me.vertices[i2].co
        p = v0 + (v1 - v0) * a + (v2 - v0) * b
        n = (vn[i0] * (1 - a - b) + vn[i1] * a + vn[i2] * b)
        p = mw @ p
        n = (nm @ n).normalized()
        if cond and not cond(p, n):
            continue
        if spacing:
            key = (int(p.x // cell), int(p.y // cell), int(p.z // cell))
            bad = False
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    for dz in (-1, 0, 1):
                        for q in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                            if (q - p).length < spacing:
                                bad = True
                                break
                        if bad:
                            break
                    if bad:
                        break
                if bad:
                    break
            if bad:
                continue
            grid.setdefault(key, []).append(p)
        out.append((p, n))
    return out


def instances(name, template, frames, mat):
    """Один меш из множества копий шаблона: frames - список матриц."""
    tv = [v.co.copy() for v in template.data.vertices]
    tf = [tuple(p.vertices) for p in template.data.polygons]
    verts, faces = [], []
    for m in frames:
        base = len(verts)
        verts += [m @ v for v in tv]
        faces += [tuple(base + i for i in f) for f in tf]
    bpy.data.objects.remove(template, do_unlink=True)
    ob = from_data(name, verts, faces)
    smooth(ob)
    return assign(ob, mat)


def frame_at(p, n, spin, lift=0.0, up_hint=None):
    z = n.normalized()
    hint = Vector(up_hint) if up_hint else (Vector((0, 0, 1)) if abs(z.z) < 0.95 else Vector((1, 0, 0)))
    m = BK.orient(z, hint)
    return Matrix.Translation(p + z * lift) @ m @ Matrix.Rotation(spin, 4, "Z")


def ellipsoid_template(name, sx, sy, sz, segs=10, rings=6, bend_k=0.0):
    t = sphere(name, 1.0, segs, rings)
    deform(t, lambda co: Vector((co.x * sx, co.y * sy, co.z * sz + bend_k * sz * co.x * co.x)))
    return t


def top_z(targets, x, y, default=None):
    """Высота самой верхней поверхности среди targets над точкой (x, y)."""
    best = default
    for t in targets:
        inv = t.matrix_world.inverted()
        o = inv @ Vector((x, y, 50.0))
        d = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
        ok, loc, _, _ = t.ray_cast(o, d)
        if ok:
            z = (t.matrix_world @ loc).z
            if best is None or z > best:
                best = z
    return best


def drape_multi(objs, targets, lift=0.01, keep=0.6):
    """Как RM.drape_on, но опора - самая верхняя из нескольких поверхностей."""
    bpy.context.view_layer.update()
    for o in objs:
        mw = o.matrix_world
        mwi = mw.inverted()
        z0 = min((mw @ v.co).z for v in o.data.vertices)
        for v in o.data.vertices:
            w = mw @ v.co
            z = top_z(targets, w.x, w.y)
            if z is not None:
                w.z = z + lift + (w.z - z0) * keep
            v.co = mwi @ w
        o.data.update()
    return objs


def scatter_world(target_list, count, make, seed=1, center=(0.0, 0.0), rx=0.8, ry=None, zmin=-1e9, spacing=0.0,
                  nz_min=0.3, lift=0.0):
    """Россыпь сверху по нескольким поверхностям: кусочек ложится на самую верхнюю, по ее нормали."""
    ry = rx if ry is None else ry
    rnd = random.Random(seed)
    bpy.context.view_layer.update()
    placed = []
    tries = 0
    while len(placed) < count and tries < count * 80:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi)
        r = math.sqrt(rnd.random())
        x, y = center[0] + rx * r * math.cos(a), center[1] + ry * r * math.sin(a)
        best = None
        for t in target_list:
            inv = t.matrix_world.inverted()
            ok, loc, nor, _ = t.ray_cast(inv @ Vector((x, y, 50.0)),
                                         (inv.to_3x3() @ Vector((0, 0, -1))).normalized())
            if ok:
                wl = t.matrix_world @ loc
                wn = (t.matrix_world.to_3x3().inverted().transposed() @ nor).normalized()
                if best is None or wl.z > best[0].z:
                    best = (wl, wn)
        if best is None:
            continue
        loc, nor = best
        if loc.z < zmin or nor.z < nz_min:
            continue
        if spacing and any((loc - q).length < spacing for q in placed):
            continue
        placed.append(loc)
        ob = make(len(placed) - 1, rnd)
        q = nor.to_track_quat("Z", "Y")
        spin = Matrix.Rotation(rnd.uniform(0, 2 * math.pi), 4, "Z")
        ob.matrix_world = Matrix.Translation(loc + nor * lift) @ q.to_matrix().to_4x4() @ spin @ ob.matrix_basis
    return placed


def basil_leaf(name, L, at, psi, elev=0.12, roll=0.0, light=False):
    key = "D2Basil" + ("Light" if light else "Dark")
    mat = bpy.data.materials.get(key) or RM.basil_mat(key, light)
    return RM.basil_leaf_at(name, L, L * 0.62, mat, at, psi, elev, roll, None, 0.0, seed=len(name) * 0.37)


def center_xy(objs, keep=()):
    """Сдвигает группу так, чтобы центр ее границ в плоскости был в нуле."""
    bpy.context.view_layer.update()
    pts = [o.matrix_world @ v.co for o in objs for v in list(o.data.vertices)[::5]]
    cx = (min(p.x for p in pts) + max(p.x for p in pts)) / 2
    cy = (min(p.y for p in pts) + max(p.y for p in pts)) / 2
    for o in objs:
        o.location -= Vector((cx, cy, 0))
    bpy.context.view_layer.update()
    return objs


# MARK: - Онигири

def rice_body_sh(name):
    sh = Sh(name, rough=0.4, sss=0.6, sss_radius=(1.0, 1.0, 0.95), sss_scale=0.04, coat=0.25)
    cells = sh.voronoi(None, 46.0, "F1")
    col = sh.ramp(sh.noise(None, 8, 3), [(0.3, (0.90, 0.90, 0.88)), (0.7, (0.97, 0.97, 0.95))])
    col = sh.mix(sh.remap(cells, 0.18, 0.05, 0.0, 0.5), col, (0.80, 0.80, 0.78))
    sh.color(col)
    sh.bump(cells, 0.6, 0.01, invert=True)
    return sh.mat


def rice_grain_sh(name):
    gsh = Sh(name, rough=0.22, sss=0.55, sss_radius=(1.0, 1.0, 0.95), sss_scale=0.02, coat=0.6, coat_rough=0.06)
    gsh.set("Emission Color", _col((1.0, 1.0, 0.98)))
    gsh.set("Emission Strength", 0.05)
    _, _, gz = gsh.xyz()
    gsh.color(gsh.ramp(gsh.remap(gz, -0.02, 0.02, smooth=False), [(0.0, (0.90, 0.90, 0.89)), (1.0, (1.0, 1.0, 0.99))]))
    gsh.bump(gsh.noise(None, 90, 2), 0.1, 0.002)
    return gsh.mat


def nori_sh(name):
    sh = Sh(name, rough=0.42, coat=0.25, coat_rough=0.25, sheen=0.3, sheen_rough=0.4)
    fib = sh.noise(sh.mapping(None, scale=(1.0, 1.0, 1.0)), 30.0, 6, 0.6, distortion=0.4)
    col = sh.ramp(fib, [(0.3, (0.04, 0.08, 0.05)), (0.55, (0.08, 0.14, 0.09)), (0.75, (0.12, 0.20, 0.12))])
    spots = sh.remap(sh.voronoi(None, 22, "F1"), 0.08, 0.02, 0.0, 0.5)
    col = sh.mix(spots, col, (0.16, 0.24, 0.14))
    sh.color(col)
    sh.bump(fib, 0.25, 0.004)
    sh.bump(sh.noise(None, 6, 3), 0.15, 0.01)
    return sh.mat


def onigiri_obj(prefix, mats, kind="sesame", seed=0):
    """Треугольник риса: пухлый, видны зерна; полоска нори снизу спереди и сзади."""
    tri = rounded_triangle(0.66, 0.22, 24)
    tri = [(x, y + 0.30) for x, y in tri]
    ob = MX.outline_slab(f"{prefix}Rice", tri, 0.44, p=2.6, cuts=40, center=(0.0, 0.30))
    subdivide(ob, 1)
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 10)

    def shape(co):
        # стоит вертикально: треугольник в XZ, толщина по Y
        x, y, z = co.x, -co.z, co.y
        bulge = 1.0 + 0.10 * max(0.0, 1 - ((x / 0.55) ** 2 + ((z - 0.32) / 0.5) ** 2))
        p = Vector((x, y * bulge, z))
        p += Vector((0.012 * fbm(p * 2.5 + Vector((ph, 0, 0))), 0.012 * fbm(p * 2.5 + Vector((0, ph, 0))),
                     0.012 * fbm(p * 2.5 + Vector((0, 0, ph)))))
        return p
    deform(ob, shape)
    lo = min(v.co.z for v in ob.data.vertices)
    deform(ob, lambda co: Vector((co.x, co.y, max(co.z - lo, 0.0) if co.z - lo > 0.04 else (co.z - lo) * 0.4 + 0.024)))
    smooth(ob)
    assign(ob, mats["body"])
    parts = [ob]
    band_w, band_h = 0.27, 0.36

    def in_band(p):
        return abs(p.x) < band_w + 0.01 and p.z < band_h + 0.01
    # зерна риса по всей открытой поверхности
    pts = surface_samples(ob, 1500, seed + 3, cond=lambda p, n: not in_band(p) and p.z > 0.03, spacing=0.028)
    tmpl = ellipsoid_template(f"{prefix}GrainT", 0.034, 0.016, 0.013, 10, 6)
    frames = [frame_at(p, n, rnd.uniform(0, math.pi), 0.004) @ Matrix.Rotation(rnd.uniform(-0.3, 0.3), 4, "X")
              for p, n in pts]
    parts.append(instances(f"{prefix}Grains", tmpl, frames, mats["grain"]))
    # нори: копия поверхности в полосе, приподнята над зернами
    me = ob.data.copy()
    nori = link(bpy.data.objects.new(f"{prefix}Nori", me))
    bisect(nori, (band_w, 0, 0), (1, 0, 0), fill=False)
    bisect(nori, (-band_w, 0, 0), (-1, 0, 0), fill=False)
    bisect(nori, (0, 0, band_h), (0, 0, 1), fill=False)
    push_normals(nori, lambda co, n: 0.016 + 0.003 * fbm(co * 9))
    solidify(nori, 0.012, 1.0)
    smooth(nori)
    assign(nori, mats["nori"])
    parts.append(nori)
    if kind == "sesame":
        sp = surface_samples(ob, 46, seed + 9, cond=lambda p, n: not in_band(p) and p.z > 0.45 and abs(n.y) > 0.4,
                             spacing=0.05)
        t2 = ellipsoid_template(f"{prefix}SesT", 0.022, 0.013, 0.008, 10, 6)
        fr = [frame_at(p, n, rnd.uniform(0, math.pi), 0.016) for p, n in sp]
        parts.append(instances(f"{prefix}Sesame", t2, fr, mats["sesame"]))
    else:
        # ямка на макушке со шматочками лосося
        top = max(v.co.z for v in ob.data.vertices)
        for i in range(7):
            a = 2 * math.pi * i / 7 + rnd.uniform(-0.3, 0.3)
            rr = 0.05 + 0.04 * (i % 2)
            fl = MX.rcube(f"{prefix}Flake{i}", rnd.uniform(0.05, 0.065), rnd.uniform(0.035, 0.045), 0.026, 3.0, 4)
            push_normals(fl, lambda co, n: 0.004 * fbm(co * 30))
            fl.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.6, 0.6), a)
            fl.location = (rr * math.cos(a), rr * 0.6 * math.sin(a), top - 0.03 + 0.02 * (i % 3))
            assign(fl, mats["salmon"])
            parts.append(fl)
        c = MX.rcube(f"{prefix}FlakeTop", 0.06, 0.045, 0.03, 3.0, 4)
        c.rotation_euler = (0.3, -0.2, 0.7)
        c.location = (0.0, 0.0, top + 0.02)
        assign(c, mats["salmon"])
        parts.append(c)
    return parts


def salmon_flake_sh(name):
    sh = Sh(name, rough=0.3, sss=0.4, sss_radius=(1.0, 0.45, 0.25), sss_scale=0.03, coat=0.5)
    x, _, z = sh.xyz()
    stripes = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", sh.math("ADD", x, z), 22.0),
                                          sh.math("MULTIPLY", obj_random(sh), 5.0)), 0.5)
    col = sh.mix(sh.remap(stripes, 0.08, 0.02), (0.98, 0.50, 0.30), (1.0, 0.86, 0.74))
    sh.color(col)
    sh.bump(sh.noise(None, 40, 3), 0.2, 0.003)
    return sh.mat


def takuan_slice(name, r=0.17, th=0.05):
    pts = [(r * math.cos(math.pi * k / 24), r * math.sin(math.pi * k / 24)) for k in range(25)]
    ob = profile_prism(name, pts, th, -th / 2)
    bevel(ob, 0.014, 3, 30)
    smooth(ob, 40)
    sh = Sh(f"{name}Mat", rough=0.18, sss=0.5, sss_radius=(1.0, 0.9, 0.3), coat=0.8, coat_rough=0.05)
    x, y, _ = sh.xyz()
    rr = sh.vmath("LENGTH", sh.combine(x, y, 0.0))
    col = sh.ramp(sh.remap(rr, 0.0, r, smooth=False), [(0.0, (1.0, 0.92, 0.42)), (0.8, (1.0, 0.82, 0.18)),
                                                      (1.0, (0.96, 0.70, 0.10))])
    sh.color(col)
    sh.bump(wave(sh, None, 30.0, 2.0, 2.0, "RINGS", "Z"), 0.08, 0.003)
    return assign(ob, sh.mat)


def sasa_leaf(name, L=2.3, W=0.78):
    def fn(u, v):
        y0 = 2 * v - 1
        w = 0.5 * W * math.sin(math.pi * min(1.0, u) ** 0.9) ** 0.7
        x = (u - 0.5) * L
        z = 0.05 * W * y0 * y0 - 0.06 * math.sin(math.pi * u) + 0.012 * math.sin(u * 30) * abs(y0)
        return Vector((x, y0 * w, z + 0.06))
    ob = RM.surface(name, 90, 24, fn)
    solidify(ob, 0.012, 0.0)
    subdivide(ob, 1)
    smooth(ob)
    sh = Sh(f"{name}Mat", rough=0.24, sss=0.3, sss_radius=(0.5, 1.0, 0.3), sss_scale=0.05, coat=0.7, coat_rough=0.08)
    u, v, _ = sh.xyz("UV")
    vc = sh.math("MULTIPLY", sh.math("ABSOLUTE", sh.math("SUBTRACT", v, 0.5)), 2.0)
    col = sh.ramp(vc, [(0.0, (0.40, 0.70, 0.22)), (0.5, (0.26, 0.58, 0.14)), (1.0, (0.16, 0.44, 0.08))])
    veins = sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", vc, 7.0), 0.5), 0.06, 0.02, 0.0, 0.5)
    mid = sh.remap(vc, 0.05, 0.02)
    col = sh.mix(sh.math("MAXIMUM", veins, mid), col, (0.62, 0.84, 0.40))
    sh.color(col)
    sh.bump(sh.math("MAXIMUM", veins, mid), 0.15, 0.004)
    mat = sh.mat
    return assign(ob, mat)


def dish_onigiri():
    board = rounded_board("OniBoard", 2.35, 1.30, 0.12, wood_sh("OniWood", (0.96, 0.82, 0.60), (0.84, 0.66, 0.42)))
    parts = [board]
    leaf = sasa_leaf("OniLeaf", 2.2, 0.72)
    leaf.rotation_euler = (0, 0, math.radians(-8))
    leaf.location = (0.0, 0.06, 0.0)
    parts.append(leaf)
    mats = {"body": rice_body_sh("OniRiceBody"), "grain": rice_grain_sh("OniGrain"), "nori": nori_sh("OniNori"),
            "sesame": flat("OniSesame", (0.10, 0.08, 0.07), rough=0.25, coat=0.6),
            "salmon": salmon_flake_sh("OniSalmon")}
    a = onigiri_obj("OniA", mats, "sesame", 1)
    rotate_all(a, (0, 0, math.radians(14)))
    for o in a:
        o.location += Vector((-0.5, -0.06, 0.07))
    b = onigiri_obj("OniB", mats, "salmon", 2)
    rotate_all(b, (0, 0, math.radians(-16)))
    for o in b:
        o.location += Vector((0.5, 0.12, 0.07))
    parts += a + b
    for i, (x, y, rz) in enumerate(((0.92, -0.44, 20), (0.70, -0.52, 60))):
        t = takuan_slice(f"OniTakuan{i}")
        t.rotation_euler = (math.radians(70), 0, math.radians(rz))
        t.location = (x, y, 0.12 + 0.02 * i)
        parts.append(t)
    return rotate_all(parts, (0, 0, math.radians(-10)))


# MARK: - Брускетта

def crumb_toast_sh(name, grill=True, scale=1.0):
    """Мякиш поджаренного хлеба: поры разного размера, румяные края, следы гриля; бок - корка."""
    sh = Sh(name, rough=0.62, sss=0.25, sss_radius=(1.0, 0.7, 0.4), sss_scale=0.05, coat=0.12, coat_rough=0.3)
    x, y, _ = sh.xyz()
    _, _, nz = sh.xyz("Normal")
    toast = sh.ramp(sh.noise(None, 3.0 * scale, 4), [(0.25, (1.0, 0.86, 0.56)), (0.55, (0.98, 0.76, 0.42)),
                                                    (0.8, (0.90, 0.60, 0.26))])
    p1 = sh.voronoi(None, 16.0 * scale, "F1")
    c1 = sh.xyz(sh.voronoi(None, 16.0 * scale, "F1", 1.0, "Color"))[0]
    p2 = sh.voronoi(sh.mapping(None, loc=(0.3, 0.7, 0.1)), 34.0 * scale, "F1")
    hole1 = sh.math("MULTIPLY", sh.remap(p1, 0.2, 0.08), sh.remap(c1, 0.45, 0.6))
    hole2 = sh.remap(p2, 0.12, 0.05, 0.0, 0.8)
    holes = sh.math("MAXIMUM", hole1, hole2)
    col = sh.mix(holes, toast, (0.78, 0.50, 0.22))
    if grill:
        s = sh.math("ADD", sh.math("MULTIPLY", sh.math("ADD", sh.math("MULTIPLY", x, 0.8), sh.math("MULTIPLY", y, 0.6)),
                                   1 / 0.26), sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 5, 3), 0.5), 0.3))
        d = sh.math("PINGPONG", s, 0.5)
        g = sh.remap(d, 0.11, 0.05)
        col = sh.mix(sh.remap(d, 0.2, 0.1, 0.0, 0.6), col, (0.70, 0.40, 0.14))
        col = sh.mix(sh.math("MULTIPLY", g, 0.9), col, (0.30, 0.15, 0.06))
    crust = sh.ramp(sh.noise(None, 6, 4), [(0.3, (0.64, 0.32, 0.09)), (0.7, (0.84, 0.50, 0.18))])
    crust = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(None, 30, 3), 0.55, 0.7), 0.6), crust, (0.96, 0.88, 0.74))
    side = sh.remap(sh.math("ABSOLUTE", nz), 0.75, 0.55)
    sh.color(sh.mix(side, col, crust))
    sh.bump(holes, 0.5, 0.012, invert=True)
    sh.bump(sh.noise(None, 40 * scale, 4), 0.2, 0.004)
    sh.rough_vary(0.5, 0.75, 7)
    return sh.mat


def tomato_dice_sh(name):
    """Кубик помидора: мякоть, полупрозрачная слизь с семечками, сок блестит."""
    sh = Sh(name, rough=0.12, sss=0.5, sss_radius=(1.0, 0.3, 0.2), sss_scale=0.03, coat=0.9, coat_rough=0.03)
    v = jitter_vec(sh, 7.0)
    base = sh.ramp(sh.noise(v, 14, 3), [(0.3, (0.80, 0.08, 0.05)), (0.7, (0.94, 0.20, 0.10))])
    gel = sh.remap(sh.noise(v, 9, 2), 0.55, 0.62)
    base = sh.mix(sh.math("MULTIPLY", gel, 0.85), base, (1.0, 0.52, 0.26))
    seeds = sh.math("MULTIPLY", sh.remap(sh.voronoi(v, 34, "F1"), 0.12, 0.06), gel)
    base = sh.mix(seeds, base, (1.0, 0.90, 0.56))
    sh.color(base)
    sh.bump(sh.noise(v, 30, 3), 0.15, 0.003)
    return sh.mat


def bread_slice_obj(name, rx=0.62, ry=0.34, h=0.2, seed=0, mat=None):
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6)

    def rfn(a):
        e = 1.0 / math.sqrt((math.cos(a) / rx) ** 2 + (math.sin(a) / ry) ** 2)
        return e * (1.0 + 0.025 * math.sin(3 * a + ph) + 0.015 * math.sin(7 * a + 2 * ph))
    ob = MX.outline_slab(name, MX.polar_outline(rfn, 120), h, p=3.2, cuts=44)
    subdivide(ob, 1)
    push_normals(ob, lambda co, n: (0.012 * fbm(co * 3 + Vector((ph, 0, 0))) + 0.004 * fbm(co * 14))
                 * (1.0 if n.z > 0.6 else 0.5))
    deform(ob, lambda co: Vector((co.x, co.y, co.z + h / 2)))
    smooth(ob)
    return assign(ob, mat)


def dish_bruschetta():
    board = rounded_board("BrBoard", 2.45, 1.32, 0.12, wood_sh("BrWood", (0.90, 0.66, 0.40), (0.66, 0.42, 0.22)))
    parts = [board]
    bread_mat = crumb_toast_sh("BrToast")
    pulp = Sh("BrPulp", rough=0.12, sss=0.5, sss_radius=(1.0, 0.3, 0.2), sss_scale=0.03, coat=0.9, coat_rough=0.03)
    pc = pulp.ramp(pulp.voronoi(None, 14, "F1", 1.0, "Distance"), [(0.0, (1.0, 0.42, 0.22)), (0.35, (0.88, 0.14, 0.07)),
                                                                   (1.0, (0.70, 0.06, 0.04))])
    pulp.color(pc)
    pulp.bump(pulp.voronoi(None, 14, "F1"), 0.4, 0.01)
    dice_mat = tomato_dice_sh("BrDice")
    garlic = flat("BrGarlic", (1.0, 0.97, 0.88), rough=0.3, sss=0.4, coat=0.5)
    pepper = flat("BrPepper", (0.12, 0.08, 0.06), rough=0.5)
    slices = []
    lay = ((-0.74, 0.02, 84, 0), (0.0, -0.04, 96, 1), (0.74, 0.04, 80, 2))
    for i, (x, y, rz, sd) in enumerate(lay):
        sl = bread_slice_obj(f"BrSlice{i}", 0.60, 0.33, 0.2, sd, bread_mat)
        sl.rotation_euler = (0, 0, math.radians(rz))
        sl.location = (x, y, 0.0)
        slices.append(sl)
        mound = polar_disc(f"BrMound{i}", 20, 96, 0.48, 0.25)
        ph = i * 1.7

        def mshape(co, ph=ph):
            rr = min(1.0, math.hypot(co.x / 0.48, co.y / 0.25))
            return Vector((co.x, co.y, 0.2 + 0.07 * max(0.0, 1 - rr * rr) ** 0.7 + 0.015 * fbm(co * 6 + Vector((ph, 0, 0)))))
        deform(mound, mshape)
        solidify(mound, 0.03, 0.0)
        smooth(mound)
        assign(mound, pulp.mat)
        mound.rotation_euler = (0, 0, math.radians(rz))
        mound.location = (x, y, 0.0)
        parts += [sl, mound]
        bpy.context.view_layer.update()
        ca, sa = math.cos(math.radians(rz)), math.sin(math.radians(rz))

        def dice(k, rnd, i=i):
            c = MX.rcube(f"BrDice{i}_{k}", rnd.uniform(0.055, 0.075), rnd.uniform(0.05, 0.07), rnd.uniform(0.045, 0.06),
                         3.2, 4)
            push_normals(c, lambda co, n: 0.006 * fbm(co * 25 + Vector((k, i, 0))))
            c.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), 0)
            c.location.z += 0.025
            return assign(c, dice_mat)
        for layer in range(2):
            scatter_world([mound] + [o for o in bpy.data.objects if o.name.startswith(f"BrDice{i}_")], 22 - 6 * layer,
                          lambda k, rnd, layer=layer: dice(k + 100 * layer, rnd), seed=10 + i + 7 * layer,
                          center=(x, y), rx=0.42 * abs(ca) + 0.21 * abs(sa), ry=0.42 * abs(sa) + 0.21 * abs(ca),
                          spacing=0.075, nz_min=0.2)
            bpy.context.view_layer.update()

        def bit(k, rnd, i=i):
            c = MX.rcube(f"BrGar{i}_{k}", 0.025, 0.022, 0.014, 3.0, 3)
            c.location.z += 0.03
            return assign(c, garlic)
        tg = [mound] + [o for o in bpy.data.objects if o.name.startswith(f"BrDice{i}_")]
        scatter_world(tg, 5, bit, seed=30 + i, center=(x, y), rx=0.3 * abs(ca) + 0.15 * abs(sa),
                      ry=0.3 * abs(sa) + 0.15 * abs(ca), spacing=0.1)

        def pep(k, rnd, i=i):
            c = sphere(f"BrPep{i}_{k}", 0.011, 8, 6)
            return assign(c, pepper)
        scatter_world(tg, 12, pep, seed=40 + i, center=(x, y), rx=0.36 * abs(ca) + 0.18 * abs(sa),
                      ry=0.36 * abs(sa) + 0.18 * abs(ca), spacing=0.05, lift=0.006)
    bpy.context.view_layer.update()
    tops = [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(("BrDice", "BrMound"))]
    # листики базилика сверху каждой брускетты
    for i, (x, y, rz, _) in enumerate(lay):
        psi = math.radians(rz + 90 + (40 if i % 2 else -30))
        L = 0.38 if i != 1 else 0.42
        lf = basil_leaf(f"BrBasil{i}", L, (x - 0.16 * math.cos(psi), y - 0.16 * math.sin(psi), 0.0), psi, 0.1,
                        light=(i == 1))
        drape_multi(lf, tops, lift=0.015, keep=0.7)
        parts += lf
        if i == 1:
            lf2 = basil_leaf(f"BrBasilS{i}", 0.26, (x + 0.02, y + 0.02, 0.0), psi + 2.3, 0.15, light=True)
            drape_multi(lf2, tops, lift=0.03, keep=0.7)
            parts += lf2
    parts += [o for o in bpy.data.objects if o.type == "MESH" and o not in parts]
    return rotate_all(parts, (0, 0, math.radians(-12)))


# MARK: - Капрезе

def tomato_slice_sh(name, R, n_loc=5):
    """Срез помидора: кожица по краю, мякоть, перегородки, камеры с желе и семечками."""
    sh = Sh(name, rough=0.16, sss=0.45, sss_radius=(1.0, 0.3, 0.2), sss_scale=0.04, coat=0.85, coat_rough=0.04)
    x, y, _ = sh.xyz()
    _, _, nz = sh.xyz("Normal")
    r = sh.math("DIVIDE", sh.vmath("LENGTH", sh.combine(x, y, 0.0)), R)
    a = sh.math("ARCTAN2", y, x)
    wob = sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(jitter_vec(sh, 5.0), 2.5 / R, 3), 0.5), 0.5)
    ph = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", a, n_loc / (2 * math.pi)), wob), 0.5)
    rw = sh.math("ADD", r, sh.math("MULTIPLY", wob, 0.12))
    loc = sh.math("MULTIPLY", sh.remap(ph, 0.11, 0.17), sh.math("MULTIPLY", sh.remap(rw, 0.28, 0.34),
                                                                 sh.remap(rw, 0.76, 0.70)))
    flesh = sh.ramp(r, [(0.0, (0.96, 0.40, 0.30)), (0.25, (0.94, 0.26, 0.18)), (0.7, (0.88, 0.12, 0.08)),
                        (0.93, (0.82, 0.07, 0.05)), (1.0, (0.66, 0.03, 0.03))])
    gel = sh.ramp(sh.noise(jitter_vec(sh, 3.0), 6.0 / R, 3), [(0.3, (0.98, 0.40, 0.22)), (0.7, (1.0, 0.52, 0.28))])
    col = sh.mix(loc, flesh, gel)
    sv = sh.voronoi(jitter_vec(sh, 4.0), 7.0 / R, "F1")
    seeds = sh.math("MULTIPLY", sh.math("MULTIPLY", sh.remap(sv, 0.13, 0.07), loc),
                    sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", rw, 0.53)), 0.2, 0.12))
    col = sh.mix(seeds, col, (1.0, 0.93, 0.66))
    skin = sh.remap(sh.math("ABSOLUTE", nz), 0.62, 0.42)
    col = sh.mix(skin, col, (0.84, 0.08, 0.05))
    sh.color(col)
    sh.set("Roughness", sh.math("ADD", 0.22, sh.math("MULTIPLY", loc, -0.14)))
    sh.bump(loc, 0.35, 0.01, invert=True)
    sh.bump(seeds, 0.3, 0.004)
    return sh.mat


def mozz_slice_sh(name):
    sh = Sh(name, rough=0.28, sss=0.55, sss_radius=(1.0, 1.0, 0.92), sss_scale=0.06, coat=0.55, coat_rough=0.1)
    v = jitter_vec(sh, 6.0)
    fib = sh.noise(sh.mapping(v, scale=(1.0, 4.0, 1.0)), 9.0, 4, 0.6, distortion=0.6)
    col = sh.ramp(fib, [(0.3, (0.90, 0.89, 0.84)), (0.7, (0.98, 0.97, 0.93))])
    pits = sh.remap(sh.voronoi(v, 26.0, "F1"), 0.06, 0.02, 0.0, 0.4)
    col = sh.mix(pits, col, (0.86, 0.86, 0.82))
    pep = sh.math("MULTIPLY", sh.remap(sh.voronoi(sh.mapping(v, loc=(2, 1, 0)), 18.0, "F1"), 0.035, 0.02),
                  sh.remap(sh.noise(v, 3, 2), 0.5, 0.56))
    _, _, nz = sh.xyz("Normal")
    pep = sh.math("MULTIPLY", pep, sh.remap(nz, 0.6, 0.8))
    col = sh.mix(pep, col, (0.15, 0.11, 0.08))
    sh.color(col)
    sh.bump(fib, 0.12, 0.006)
    sh.bump(pits, 0.3, 0.004, invert=True)
    return sh.mat


def disc_slab(name, R, h, seed=0, wob=0.03, p=2.6, cuts=36):
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6)
    ob = MX.outline_slab(name, MX.polar_outline(lambda a: R * (1 + wob * math.sin(3 * a + ph) + 0.6 * wob *
                                                               math.sin(5 * a + 2 * ph)), 96), h, p=p, cuts=cuts)
    subdivide(ob, 1)
    push_normals(ob, lambda co, n: 0.004 * fbm(co * 8 + Vector((ph, 0, 0))))
    return smooth(ob)


def dish_caprese():
    """Ломтики внахлест по кругу (каждый лежит краем на следующем), в центре шарик моцареллы и букетик базилика."""
    plate_ = flat_plate("CapPlate", 1.04, [(0.0, (0.95, 0.95, 0.94)), (0.80, (1.0, 1.0, 0.99)), (0.88, (0.98, 0.98, 0.96)),
                                          (0.91, (0.20, 0.44, 0.36)), (0.95, (0.26, 0.52, 0.42)), (1.0, (0.96, 0.96, 0.94))],
                        rim=0.07, h=0.06)
    parts = [plate_]
    floor = 0.06
    slices = []
    n, ring, beta = 10, 0.58, math.radians(22)
    for i in range(n):
        a = 2 * math.pi * i / n + math.radians(6)
        is_tom = i % 2 == 0
        R = 0.37 if is_tom else 0.34
        h = 0.08 if is_tom else 0.10
        ob = disc_slab(f"CapSlice{i}", R, h, i, wob=0.025 if is_tom else 0.05, p=2.4 if is_tom else 2.0)
        assign(ob, tomato_slice_sh(f"CapTom{i}", R, 4 + i % 3) if is_tom else mozz_slice_sh(f"CapMozz{i}"))
        ob.matrix_world = (Matrix.Translation((ring * math.cos(a), ring * math.sin(a), 0.0)) @ Matrix.Rotation(a, 4, "Z")
                           @ Matrix.Rotation(-beta, 4, "X"))
        bpy.context.view_layer.update()
        lo = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
        ob.location.z += floor - lo + 0.004
        slices.append(ob)
    parts += slices
    bpy.context.view_layer.update()
    for i in range(5):
        a = 2 * math.pi * (2 * i + 1.6) / n + math.radians(6)
        base = Vector((0.50 * math.cos(a), 0.50 * math.sin(a), 0.0))
        lf = basil_leaf(f"CapBasil{i}", 0.36, tuple(base), a + 0.2, 0.1, light=bool(i % 2))
        drape_multi(lf, slices + [plate_], lift=0.014, keep=0.85)
        parts += lf
    pearl = sphere("CapPearl", 0.20, 64, 40)
    deform(pearl, lambda co: Vector((co.x, co.y, co.z * 0.82 if co.z > 0 else co.z * 0.5)))
    push_normals(pearl, lambda co, n: 0.008 * fbm(co * 10))
    smooth(pearl)
    assign(pearl, mozz_slice_sh("CapPearlMat"))
    pearl.location = (0.0, 0.0, floor + 0.10)
    parts.append(pearl)
    for j in range(5):
        psi = 2 * math.pi * j / 5 + 0.3
        lf = basil_leaf(f"CapTop{j}", 0.34 if j % 2 else 0.30, (0.10 * math.cos(psi), 0.10 * math.sin(psi), floor + 0.16),
                        psi, math.radians(24), 0.0, light=(j % 2 == 0))
        parts += lf
    sprig = basil_leaf("CapCrown", 0.24, (0.0, 0.0, floor + 0.25), 1.2, math.radians(55), 0.0, light=True)
    parts += sprig
    glaze = flat("CapGlaze", (0.16, 0.06, 0.04), rough=0.05, coat=1.0)
    rnd = random.Random(4)
    for q in range(10):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.84, 0.90)
        d = sphere(f"CapDrop{q}", 0.026, 16, 8)
        d.scale = (1.0, 1.0, 0.3)
        d.location = (rr * math.cos(a), rr * math.sin(a), floor + 0.004)
        assign(smooth(d), glaze)
        parts.append(d)
    rotate_all(parts, (0, 0, math.radians(-6)))
    return rotate_all(parts, (math.radians(16), 0, 0))


# MARK: - Ягоды и общие сладости

def raspberry(name, r=0.075, seed=0, mat=None):
    """Малина: шарики-костяночки по вытянутому куполу, ямка снизу."""
    rnd = random.Random(seed)
    core = sphere(f"{name}Core", 1.0, 24, 16)
    deform(core, lambda co: Vector((co.x * r * 0.92, co.y * r * 0.92, co.z * r * 1.1)))
    tmpl = sphere(f"{name}DrT", 1.0, 10, 8)
    frames = []
    rows = 7
    for i in range(rows):
        th = math.radians(15 + 150 * i / (rows - 1))
        n = max(3, int(round(10 * math.sin(th))))
        for j in range(n):
            ph = 2 * math.pi * (j + 0.5 * (i % 2)) / n + rnd.uniform(-0.1, 0.1)
            p = Vector((math.sin(th) * math.cos(ph) * r * 0.92, math.sin(th) * math.sin(ph) * r * 0.92,
                        math.cos(th) * r * 1.1))
            d = r * 0.34 * (0.9 + 0.2 * rnd.random())
            frames.append(Matrix.Translation(p * 0.98) @ Matrix.Scale(d, 4))
    ob = instances(f"{name}", tmpl, frames, mat)
    assign(core, mat)
    j = BK.join([ob, core], name)
    return assign(j, mat)


def raspberry_sh(name):
    sh = Sh(name, rough=0.28, sss=0.5, sss_radius=(1.0, 0.25, 0.3), sss_scale=0.02, coat=0.5, coat_rough=0.1,
            sheen=0.5, sheen_rough=0.3)
    sh.color(sh.ramp(sh.noise(None, 30, 3), [(0.3, (0.78, 0.06, 0.20)), (0.7, (0.92, 0.16, 0.30))]))
    return sh.mat


def currant_cluster(name, mat, stem_mat, n=4, r=0.045, seed=0):
    rnd = random.Random(seed)
    parts = []
    pts = [(0.0, 0.0, 0.0)]
    for k in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        p = Vector((0.03 * k + 0.02, 0.06 * math.cos(a), 0.0))
        b = sphere(f"{name}B{k}", r * rnd.uniform(0.9, 1.1), 24, 16)
        b.location = p
        assign(smooth(b), mat)
        parts.append(b)
        pts.append(tuple(p + Vector((0, 0, r * 0.9))))
    st = EV.sweep(f"{name}Stem", EV.spline([(-0.06, 0, r * 1.3), (0.02, 0, r * 1.5), (0.08 + 0.03 * n, 0.01, r * 1.4)], 6),
                  0.008, segs=8, step=0.01)
    assign(st, stem_mat)
    return parts + [st]


def mint_mat(name):
    return RM.leaf_shader(name, [(0.0, (0.46, 0.80, 0.30)), (0.4, (0.32, 0.70, 0.20)), (1.0, (0.22, 0.58, 0.12))],
                          (0.14, 0.46, 0.08), (0.62, 0.90, 0.44), N=5.0, K=1.2, raised=False, rough=0.34, sss=0.3,
                          coat=0.5, rib=0.06, vein=0.06, bump=0.35, pucker=0.08)


def mint_sprig(prefix, at, psi, mat, scale=1.0):
    parts = []
    for j, (dpsi, elev, L) in enumerate(((0.0, 40, 0.26), (2.2, 34, 0.24), (-2.1, 36, 0.22), (1.0, 70, 0.15))):
        parts += RM.basil_leaf_at(f"{prefix}{j}", L * scale, L * scale * 0.62, mat, at, psi + dpsi,
                                  math.radians(elev), 0.0, None, 0.0, seed=j * 2.1 + psi)
    return parts


def choc_sh(name, lo=(0.20, 0.09, 0.04), hi=(0.42, 0.21, 0.10), z0=0.0, z1=1.0):
    sh = Sh(name, rough=0.12, coat=0.9, coat_rough=0.03, sss=0.08, sss_radius=(1.0, 0.5, 0.3))
    _, _, z = sh.xyz()
    col = sh.ramp(sh.remap(z, z0, z1, smooth=False), [(0.0, lo), (1.0, hi)])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(None, 4, 2), 0.5, 0.7), 0.2), col, (0.50, 0.28, 0.14))
    sh.color(col)
    sh.bump(sh.noise(None, 6, 2), 0.04, 0.01)
    return sh.mat


def cream_sh(name, lo=(0.95, 0.92, 0.86), hi=(1.0, 0.99, 0.96)):
    sh = Sh(name, rough=0.34, sss=0.65, sss_radius=(1.0, 0.95, 0.85), sss_scale=0.08, coat=0.2, coat_rough=0.2)
    sh.set("Emission Color", _col(hi))
    sh.set("Emission Strength", 0.04)
    _, _, nz = sh.xyz("Normal")
    sh.color(sh.ramp(nz, [(0.0, lo), (1.0, hi)]))
    sh.bump(sh.noise(None, 20, 3), 0.05, 0.004)
    return sh.mat


# MARK: - Шарлотка (шарлот рюс): савоярди по кругу, мусс, ягоды, лента с бантом

def ladyfinger_sh(name):
    sh = Sh(name, rough=0.5, sss=0.3, sss_radius=(1.0, 0.7, 0.4), sss_scale=0.05, coat=0.15, coat_rough=0.3)
    _, ny, _ = sh.xyz("Normal")
    _, _, z = sh.xyz()
    v = jitter_vec(sh, 9.0)
    out = sh.remap(ny, -0.2, 0.7)
    base = sh.ramp(out, [(0.0, (1.0, 0.93, 0.74)), (0.45, (0.99, 0.82, 0.50)), (1.0, (0.92, 0.62, 0.28))])
    brown = sh.remap(sh.noise(v, 3.0, 3), 0.55, 0.72, 0.0, 0.5)
    ends = sh.math("MAXIMUM", sh.remap(z, 0.16, 0.04), sh.remap(z, 0.80, 0.93))
    base = sh.mix(sh.math("MULTIPLY", sh.math("MAXIMUM", brown, sh.math("MULTIPLY", ends, 0.6)), out), base,
                  (0.80, 0.48, 0.18))
    dots = sh.voronoi(v, 55.0, "F1")
    sugar = sh.math("MULTIPLY", sh.remap(dots, 0.14, 0.07), sh.remap(ny, 0.0, 0.4))
    base = sh.mix(sugar, base, (1.0, 1.0, 0.97))
    sh.color(base)
    sh.set("Roughness", sh.math("ADD", 0.52, sh.math("MULTIPLY", sugar, -0.4)))
    sh.bump(sugar, 0.35, 0.006)
    sh.bump(sh.noise(v, 18, 4), 0.15, 0.006)
    return sh.mat


def ladyfinger(name, L, W, T, mat, seed=0):
    def rfn(t):
        s = abs(2 * t - 1)
        return W * max(0.0, 1 - s ** 7) ** 0.5 * (0.9 + 0.1 * s ** 2)
    ob = RM.lathe_fn(name, rfn, 0.0, L, 60, 40)

    def shp(co):
        y = co.y * (T / W) * (1.0 if co.y > 0 else 0.55)
        return Vector((co.x * (1 + 0.03 * fbm(co * 6 + Vector((seed, 0, 0)))), y, co.z))
    deform(ob, shp)
    push_normals(ob, lambda co, n: 0.004 * fbm(co * 14 + Vector((0, seed, 0))))
    smooth(ob)
    return assign(ob, mat)


def ribbon_sh(name, c=(0.86, 0.18, 0.28)):
    sh = Sh(name, rough=0.3, coat=0.35, coat_rough=0.15, sheen=0.6, sheen_rough=0.25)
    _, _, z = sh.xyz()
    stripes = sh.math("PINGPONG", sh.math("MULTIPLY", z, 60.0), 0.5)
    dark = tuple(x * 0.78 for x in c)
    sh.color(sh.mix(sh.math("MULTIPLY", sh.remap(stripes, 0.1, 0.3), 0.25), c, dark))
    return sh.mat


def dish_charlotte():
    plate_ = flat_plate("ChPlate", 1.12, [(0.0, (0.97, 0.96, 0.94)), (0.84, (1.0, 1.0, 0.99)), (0.9, (0.96, 0.84, 0.86)),
                                         (0.95, (0.94, 0.78, 0.82)), (1.0, (0.99, 0.97, 0.96))], rim=0.06, h=0.06)
    parts = [plate_]
    base = 0.06
    Rr, N, L = 0.80, 24, 0.98
    W = math.pi * Rr / N * 1.02
    T = 0.075
    lf_mat = ladyfinger_sh("ChLady")
    rnd = random.Random(3)
    for i in range(N):
        a = 2 * math.pi * i / N
        f = ladyfinger(f"ChLady{i}", L * rnd.uniform(0.97, 1.02), W, T, lf_mat, i)
        f.matrix_world = (Matrix.Translation((Rr * math.cos(a), Rr * math.sin(a), base))
                          @ Matrix.Rotation(a - math.pi / 2, 4, "Z") @ Matrix.Rotation(rnd.uniform(-0.03, 0.03), 4, "X"))
        parts.append(f)
    # мусс внутри и бисквитное дно
    fill_top = base + L * 0.84
    mousse = RM.lathe_fn("ChMousse", lambda t: Rr - 0.01 if t < 0.98 else (Rr - 0.01) * (1 - (t - 0.98) * 30),
                         base + 0.02, fill_top, 40, 128)
    deform(mousse, lambda co: Vector((co.x, co.y, co.z + 0.04 * max(0.0, 1 - (co.x ** 2 + co.y ** 2) / Rr ** 2)
                                      * (co.z > fill_top - 0.03))))
    smooth(mousse)
    ms = Sh("ChMousseMat", rough=0.35, sss=0.6, sss_radius=(1.0, 0.8, 0.8), sss_scale=0.06, coat=0.3)
    ms.color(ms.ramp(ms.noise(None, 4, 3), [(0.3, (0.99, 0.84, 0.84)), (0.7, (1.0, 0.90, 0.88))]))
    ms.bump(ms.noise(None, 12, 3), 0.05, 0.01)
    assign(mousse, ms.mat)
    parts.append(mousse)
    # лента с бантом
    rib_mat = ribbon_sh("ChRibbon")
    rz0, rz1 = base + 0.30, base + 0.46
    ro = Rr + T + 0.008
    band = lathe("ChBand", [(ro - 0.012, rz0), (ro + 0.006, rz0 + 0.004), (ro + 0.012, rz0 + 0.02), (ro + 0.012, rz1 - 0.02),
                            (ro + 0.006, rz1 - 0.004), (ro - 0.012, rz1)], 192)
    smooth(band)
    assign(band, rib_mat)
    parts.append(band)
    fa = -math.pi / 2 - math.radians(20)
    fdir = Vector((math.cos(fa), math.sin(fa), 0))
    side = Vector((-fdir.y, fdir.x, 0))
    c0 = fdir * (ro + 0.03) + Vector((0, 0, (rz0 + rz1) / 2))
    bow = []
    for sgn in (-1, 1):
        loop = [c0 + side * sgn * (0.17 * (1 - math.cos(th)) * 0.5) + fdir * (0.05 * math.sin(th) ** 2 + 0.01)
                + Vector((0, 0, 0.09 * math.sin(th))) for th in [2 * math.pi * k / 40 for k in range(41)]]
        lp = EV.sweep(f"ChBow{sgn}", [tuple(p) for p in loop], 0.03, segs=14, step=0.01, section=(0.35, 1.0),
                      up=tuple(fdir))
        tail = EV.spline([tuple(c0), tuple(c0 + side * sgn * 0.06 + fdir * 0.03 + Vector((0, 0, -0.08))),
                          tuple(c0 + side * sgn * 0.12 + fdir * 0.05 + Vector((0, 0, -0.2))),
                          tuple(c0 + side * sgn * 0.16 + fdir * 0.06 + Vector((0, 0, -0.27)))], 6)
        tl = EV.sweep(f"ChTail{sgn}", tail, 0.032, segs=14, step=0.01, section=(0.3, 1.0), up=tuple(fdir))
        bow += [lp, tl]
    knot = sphere("ChKnot", 0.05, 24, 16)
    knot.scale = (1.0, 0.7, 1.1)
    knot.location = c0 + fdir * 0.02
    bow.append(smooth(knot))
    for o in bow:
        assign(o, rib_mat)
    parts += bow
    bpy.context.view_layer.update()
    # ягоды горкой: клубника, малина, голубика, смородина, мята
    berries = [mousse]
    for i, (rr, deg, tilt) in enumerate(((0.0, 0, 0), (0.42, 30, 22), (0.42, 150, 22), (0.42, 270, 22))):
        sb = BK.strawberry_obj(f"ChStraw{i}", 0.30 if i else 0.36, i)
        a = math.radians(deg)
        rotate_all(sb, (math.radians(tilt), 0, a + math.pi / 2))
        for o in sb:
            o.location += Vector((rr * math.cos(a), rr * math.sin(a), 0.0))
        MX.ground(sb, fill_top + (0.13 if i == 0 else 0.0))
        berries += sb
        parts += sb
    halves = []
    for i, deg in enumerate((90, 210, 330)):
        a = math.radians(deg)
        h = BK.strawberry_half(f"ChHalf{i}", 0.21, i)
        h.rotation_euler = (math.radians(-90 - 30), 0, a + math.pi / 2)
        h.location = (0.55 * math.cos(a), 0.55 * math.sin(a), fill_top + 0.14)
        halves.append(h)
    parts += halves
    berries += halves
    rmat = raspberry_sh("ChRasp")
    rasp = []

    def mk_r(k, rnd):
        r_ = raspberry(f"ChRasp{k}", 0.075, k, rmat)
        r_.rotation_euler = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), 0)
        r_.location.z += 0.06
        rasp.append(r_)
        return r_
    scatter_world(berries, 9, mk_r, seed=5, rx=0.66, spacing=0.17, nz_min=0.1)
    parts += rasp
    bpy.context.view_layer.update()
    blue = []

    def mk_b(k, rnd):
        b = BK.blueberry(f"ChBlue{k}", 0.06)
        b.location.z += 0.045
        blue.append(b)
        return b
    scatter_world(berries + rasp, 12, mk_b, seed=9, rx=0.72, spacing=0.13, nz_min=0.2)
    parts += blue
    cur_mat = Sh("ChCurrant", rough=0.06, sss=0.6, sss_radius=(1.0, 0.2, 0.2), sss_scale=0.03, coat=1.0, coat_rough=0.02)
    cur_mat.color((0.86, 0.06, 0.10))
    stem_mat = flat("ChCurStem", (0.42, 0.50, 0.20), rough=0.4)
    for i, (deg, rr) in enumerate(((60, 0.66), (240, 0.62))):
        a = math.radians(deg)
        cl = currant_cluster(f"ChCur{i}", cur_mat.mat, stem_mat, 4, 0.045, i)
        rotate_all(cl, (0, 0, a + 1.0))
        z = top_z(berries + rasp + blue, rr * math.cos(a), rr * math.sin(a), fill_top) + 0.03
        for o in cl:
            o.location += Vector((rr * math.cos(a), rr * math.sin(a), z))
        parts += cl
    mm = mint_mat("ChMint")
    zt = top_z(berries, 0.0, 0.0, fill_top + 0.3)
    parts += mint_sprig("ChMintA", (0.02, -0.02, zt - 0.05), 0.4, mm, 1.0)
    return rotate_all(parts, (0, 0, math.radians(10)))


# MARK: - Блинчики

def crepe_sh(name):
    """Тонкий блин: светлый с кружевом румяных пятен, края темнее; сахарная пудра сверху; слои по срезу."""
    sh = Sh(name, rough=0.45, sss=0.35, sss_radius=(1.0, 0.6, 0.3), sss_scale=0.05, coat=0.25, coat_rough=0.2)
    v = jitter_vec(sh, 5.0)
    _, _, nz = sh.xyz("Normal")
    _, _, z = sh.xyz()
    base = sh.ramp(sh.noise(v, 2.0, 3), [(0.3, (1.0, 0.86, 0.56)), (0.7, (0.98, 0.78, 0.44))])
    n1 = sh.noise(v, 3.2, 3, 0.5, distortion=0.5)
    lace = sh.math("MULTIPLY", sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", n1, 0.5)), 0.03, 0.0),
                   sh.remap(sh.noise(v, 1.5, 2), 0.45, 0.6))
    spots = sh.math("MULTIPLY", sh.remap(sh.voronoi(v, 7.0, "F1"), 0.22, 0.08),
                    sh.remap(sh.noise(v, 2.2, 2), 0.42, 0.58))
    small = sh.math("MULTIPLY", sh.remap(sh.voronoi(sh.mapping(v, loc=(2, 3, 1)), 18.0, "F1"), 0.12, 0.05),
                    sh.remap(sh.noise(v, 3.0, 2), 0.5, 0.6))
    brown = sh.math("MAXIMUM", sh.math("MAXIMUM", sh.math("MULTIPLY", lace, 0.8), spots), sh.math("MULTIPLY", small, 0.7))
    patch = sh.remap(sh.noise(v, 1.4, 3), 0.45, 0.65)
    col = sh.mix(sh.math("MULTIPLY", patch, 0.6), base, (0.94, 0.66, 0.30))
    col = sh.mix(brown, col, (0.72, 0.40, 0.13))
    # слои на боковом срезе
    layer = sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", z, 26.0), 0.5), 0.06, 0.0)
    side = sh.remap(sh.math("ABSOLUTE", nz), 0.6, 0.35)
    col = sh.mix(sh.math("MULTIPLY", layer, side), col, (0.72, 0.44, 0.16))
    sugar = sh.math("MULTIPLY", sh.remap(sh.noise(v, 22, 5), 0.55, 0.68), sh.remap(nz, 0.7, 0.95))
    col = sh.mix(sh.math("MULTIPLY", sugar, sh.remap(sh.noise(v, 1.3, 2), 0.4, 0.6)), col, (1.0, 1.0, 1.0))
    sh.color(col)
    sh.bump(brown, 0.12, 0.004, invert=True)
    sh.bump(sh.noise(v, 9, 3), 0.08, 0.006)
    return sh.mat


def crepe_fold(name, R, span, h, mat, seed=0):
    """Блинчик, сложенный вчетверо: сектор с пухлым верхом, острый угол у начала координат, дуга по +X."""
    half = span / 2
    pts = [(0.03 * math.cos(math.pi + a), 0.03 * math.sin(math.pi + a)) for a in (-0.9, 0.0, 0.9)]
    pts = [(0.0, 0.0)]
    for k in range(41):
        a = -half + span * k / 40
        pts.append((R * math.cos(a), R * math.sin(a)))
    ob = MX.outline_slab(name, pts, h, p=2.2, cuts=40, center=(R * 0.55, 0.0))
    subdivide(ob, 1)
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6)

    def shp(co):
        rr = math.hypot(co.x, co.y) / R
        a = math.atan2(co.y, co.x) / half
        puff = 0.10 * math.sin(math.pi * min(1.0, rr)) * (1 - 0.5 * a * a) if co.z > -h * 0.2 else 0.0
        wav = 0.025 * math.sin(5 * math.atan2(co.y, co.x) + ph) * rr ** 3
        return Vector((co.x, co.y, co.z + h / 2 + puff + wav + 0.012 * fbm(co * 3 + Vector((ph, 0, 0)))))
    deform(ob, shp)
    smooth(ob)
    return assign(ob, mat)


def banana_slice(name, mat, r=0.11, th=0.05):
    ob = disc_slab(name, r, th, len(name), wob=0.03, p=2.4, cuts=20)
    return assign(ob, mat)


def banana_sh(name):
    sh = Sh(name, rough=0.3, sss=0.5, sss_radius=(1.0, 0.9, 0.5), sss_scale=0.03, coat=0.4)
    x, y, _ = sh.xyz()
    rr = sh.vmath("LENGTH", sh.combine(x, y, 0.0))
    a = sh.math("ARCTAN2", y, x)
    star = sh.math("MULTIPLY", sh.remap(rr, 0.03, 0.015), 1.0)
    rays = sh.math("MULTIPLY", sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", a, 3 / (2 * math.pi)), 0.5), 0.06, 0.0),
                   sh.remap(rr, 0.045, 0.02))
    col = sh.ramp(sh.remap(rr, 0.0, 0.11, smooth=False), [(0.0, (0.99, 0.94, 0.72)), (0.85, (1.0, 0.96, 0.80)),
                                                         (1.0, (0.96, 0.88, 0.60))])
    col = sh.mix(sh.math("MAXIMUM", star, rays), col, (0.86, 0.74, 0.46))
    sh.color(col)
    return sh.mat


def dish_crepes():
    plate_ = BK.bistro_plate("CrpPlate", 1.12)
    parts = [plate_]
    mat = crepe_sh("CrpMat")
    choc = choc_sh("CrpChoc", (0.22, 0.10, 0.04), (0.44, 0.22, 0.10), 0.1, 0.5)
    crepes = []
    R, span, h = 0.94, math.radians(100), 0.17
    for i, deg in enumerate((90 + 12, 210 + 12, 330 + 12)):
        a = math.radians(deg)
        c = crepe_fold(f"Crepe{i}", R, span, h, mat, i)
        c.rotation_euler = (0, math.radians(9), a)
        c.location = (0.10 * math.cos(a), 0.10 * math.sin(a), 0.11)
        crepes.append(c)
    parts += crepes
    bpy.context.view_layer.update()
    for c in crepes:
        lo = min((c.matrix_world @ v.co).z for v in c.data.vertices)
        c.location.z += 0.105 - lo
    bpy.context.view_layer.update()
    # нутелла вытекает из слоев по дуге
    for i, deg in enumerate((90 + 12, 210 + 12, 330 + 12)):
        a0 = math.radians(deg)
        apex = Vector((0.10 * math.cos(a0), 0.10 * math.sin(a0), 0.0))
        pts = []
        for k in range(44):
            t = -0.36 + 0.72 * k / 43
            d = Vector((math.cos(a0 + t), math.sin(a0 + t), 0.0))
            p_out = apex + d * (R - 0.01)
            p_in = apex + d * (R - 0.10)
            zt = top_z(crepes, p_in.x, p_in.y, 0.2)
            pts.append((p_out.x, p_out.y, 0.105 + (zt - 0.105) * 0.45))
        ooze = EV.sweep(f"CrpOoze{i}", pts, lambda t: 0.03 * (0.6 + 0.5 * math.sin(math.pi * t) +
                                                              0.25 * math.sin(t * 17 + i)), segs=14, step=0.01)
        assign(ooze, choc)
        parts.append(ooze)
    # шоколадная паутинка поверх
    segs, cur = [], []
    for k in range(600):
        t = k / 599
        x = -0.95 + 1.9 * t
        y = 0.55 * math.sin(t * math.pi * 7.0 + 0.4) + 0.05 * math.sin(t * 29)
        hz = top_z(crepes, x, y)
        if hz is None or math.hypot(x, y) < 0.28:
            if len(cur) > 4:
                segs.append(cur)
            cur = []
            continue
        cur.append((x, y, hz + 0.012))
    if len(cur) > 4:
        segs.append(cur)
    for j, sg in enumerate(segs):
        dz = EV.sweep(f"CrpDrz{j}", sg, 0.022, segs=10, step=0.01, section=(0.6, 1.0))
        assign(dz, choc)
        parts.append(dz)
    # в центре сливки, клубника, голубика, банан, мята
    zc = top_z(crepes, 0.0, 0.0, 0.3)
    cream = cream_sh("CrpCream")
    sw = EV.piped_swirl("CrpWhip", cream, 0.34, 0.52, 9, 5.0)
    sw.location = (0.0, 0.0, zc - 0.06)
    parts.append(sw)
    bmat = banana_sh("CrpBanana")
    for i, deg in enumerate((30, 150, 270)):
        a = math.radians(deg)
        x, y = 0.38 * math.cos(a), 0.38 * math.sin(a)
        z = top_z(crepes, x, y, 0.3)
        bs = banana_slice(f"CrpBan{i}", bmat)
        bs.rotation_euler = (math.radians(20) * math.cos(a + 1), math.radians(20) * math.sin(a + 1), 0)
        bs.location = (x, y, z + 0.03)
        parts.append(bs)
    for i, deg in enumerate((90, 210, 330)):
        a = math.radians(deg)
        x, y = 0.40 * math.cos(a), 0.40 * math.sin(a)
        z = top_z(crepes, x, y, 0.3)
        sh_ = BK.strawberry_half(f"CrpBerry{i}", 0.29, i)
        sh_.rotation_euler = (math.radians(-90 + 25), 0, a + math.pi / 2)
        sh_.location = (x, y, z + 0.18)
        parts.append(sh_)
    for i, deg in enumerate((0, 60, 120, 180, 240, 300)):
        a = math.radians(deg + 15)
        x, y = 0.27 * math.cos(a), 0.27 * math.sin(a)
        z = top_z(crepes, x, y, 0.3)
        b = BK.blueberry(f"CrpBlue{i}", 0.06)
        b.location = (x, y, z + 0.05)
        parts.append(b)
    mm = mint_mat("CrpMint")
    parts += mint_sprig("CrpMintA", (0.04, -0.02, zc + 0.40), 0.6, mm, 1.0)
    rotate_all(parts, (0, 0, math.radians(-8)))
    return rotate_all(parts, (math.radians(14), 0, 0))


# MARK: - Круассан

def croissant_sh(name):
    """Яичная глазурь: глубокий янтарь сверху, светлое слоистое тесто в бороздках, хлопья."""
    sh = Sh(name, rough=0.28, sss=0.3, sss_radius=(1.0, 0.55, 0.25), sss_scale=0.05, coat=0.85, coat_rough=0.05)
    _, _, nz = sh.xyz("Normal")
    g = sh.attr("groove")
    v = jitter_vec(sh, 4.0)
    top = sh.ramp(sh.remap(nz, -0.6, 1.0, smooth=False), [(0.0, (0.98, 0.78, 0.44)), (0.35, (0.92, 0.58, 0.20)),
                                                          (0.7, (0.78, 0.40, 0.10)), (1.0, (0.66, 0.30, 0.07))])
    top = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(v, 3.0, 4), 0.4, 0.7), 0.4), top, (0.56, 0.24, 0.05))
    lam = sh.math("PINGPONG", sh.math("MULTIPLY", g, 7.0), 0.5)
    lines = sh.remap(lam, 0.18, 0.08)
    groove = sh.remap(g, 0.58, 0.95)
    dough = sh.mix(sh.math("MULTIPLY", lines, 0.7), (1.0, 0.86, 0.56), (0.86, 0.54, 0.20))
    col = sh.mix(groove, top, dough)
    flakes = sh.noise(sh.mapping(v, scale=(1.0, 1.0, 3.0)), 14.0, 5, 0.6)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(flakes, 0.6, 0.72), 0.35), col, (1.0, 0.86, 0.56))
    sh.color(col)
    sh.set("Coat Weight", sh.math("SUBTRACT", 0.9, sh.math("MULTIPLY", groove, 0.6)))
    sh.bump(lines, 0.25, 0.004)
    sh.bump(flakes, 0.2, 0.006)
    return sh.mat


def croissant2(name, L=1.95, R0=0.40, bend_r=0.82, wraps=5, seed=0, mat=None):
    Nt, Nf = 180, 64
    th_max = (L / 2) / bend_r
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6)
    verts, gro = [], []
    for i in range(Nt + 1):
        t = -1 + 2 * i / Nt
        th = t * th_max
        c = Vector((bend_r * math.sin(th), bend_r * math.cos(th) - bend_r, 0.0))
        nn = Vector((math.sin(th), math.cos(th), 0.0))
        # концы опускаются к тарелке
        c.z -= 0.10 * abs(t) ** 2.2
        base = R0 * max(0.0, 1 - abs(t) ** 1.6) ** 1.05 + 0.022
        for j in range(Nf):
            f = 2 * math.pi * j / Nf
            u = (t + 1) / 2 * wraps + 0.28 * math.cos(f) * math.tanh(t * 6) + 0.04 * fbm(Vector((t * 4, f, ph)))
            fr = u % 1.0
            d = min(fr, 1 - fr)
            roll = math.sin(math.pi * fr) ** 0.45
            rr = base * (0.74 + 0.26 * roll) * (1 + 0.03 * fbm(Vector((t * 5, f * 1.5, ph + 3))))
            sf, cf = math.sin(f), math.cos(f)
            zr = rr * (0.92 if sf > 0 else 0.42)
            p = c + nn * rr * cf + Vector((0, 0, zr * sf + base * 0.42))
            verts.append(p)
            gro.append(max(0.0, 1 - d / 0.22))
    faces = []
    for i in range(Nt):
        for j in range(Nf):
            a, b = i * Nf + j, i * Nf + (j + 1) % Nf
            faces.append((a, b, b + Nf, a + Nf))
    for i0, sgn in ((0, -1), (Nt, 1)):
        ring = [i0 * Nf + j for j in range(Nf)]
        cen = sum((verts[k] for k in ring), Vector()) / Nf
        verts.append(cen)
        gro.append(0.0)
        tip = len(verts) - 1
        for j in range(Nf):
            a, b = ring[j], ring[(j + 1) % Nf]
            faces.append((b, a, tip) if sgn > 0 else (a, b, tip))
    ob = from_data(name, verts, faces)
    at = ob.data.attributes.new("groove", "FLOAT", "POINT")
    for k, v in enumerate(gro):
        at.data[k].value = v
    subdivide(ob, 1)
    # опора - низ середины: рожки чуть ниже, их потом поднимет тарелка (drape_onto)
    lo = min(v.co.z for v in ob.data.vertices if abs(v.co.x) < 0.25)
    deform(ob, lambda co: Vector((co.x, co.y, co.z - lo)))
    smooth(ob)
    return assign(ob, mat)


def dish_croissant():
    plate_ = BK.bistro_plate("CrPlate", 1.12)
    parts = [plate_]
    mat = croissant_sh("CroisMat")
    # два внизу (рожками в разные стороны) и третий сверху поперек
    b = croissant2("CroissantB", 1.95, 0.42, 0.64, 7, 2, mat)
    b.rotation_euler = (0, 0, math.radians(-8))
    b.location = (-0.08, -0.28, 0.1)
    apply_transform(b)
    BK.drape_onto(b, [plate_])
    a = croissant2("CroissantA", 1.90, 0.40, 0.62, 7, 0, mat)
    a.rotation_euler = (0, 0, math.radians(180 + 10))
    a.location = (0.10, 0.36, 0.1)
    apply_transform(a)
    BK.drape_onto(a, [plate_, b])
    c = croissant2("CroissantC", 1.85, 0.40, 0.62, 7, 5, mat)
    c.rotation_euler = (math.radians(-8), 0, math.radians(84))
    c.location = (-0.30, 0.04, 1.2)
    apply_transform(c)
    bpy.context.view_layer.update()
    MX.drop([c], [a, b, plate_], floor=0.1, step=0.006)
    parts += [a, b, c]
    return rotate_all(parts, (0, 0, math.radians(-14)))


# MARK: - Эклеры

def choux_sh(name):
    sh = Sh(name, rough=0.42, sss=0.25, sss_radius=(1.0, 0.6, 0.3), sss_scale=0.05, coat=0.35, coat_rough=0.15)
    _, _, nz = sh.xyz("Normal")
    v = jitter_vec(sh, 6.0)
    col = sh.ramp(sh.remap(nz, -1.0, 1.0, smooth=False), [(0.0, (0.98, 0.80, 0.48)), (0.45, (0.94, 0.66, 0.30)),
                                                          (1.0, (0.80, 0.46, 0.16))])
    cr = sh.noise(v, 7.0, 5, 0.6, distortion=0.8)
    cracks = sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", cr, 0.5)), 0.03, 0.0)
    col = sh.mix(sh.math("MULTIPLY", cracks, 0.7), col, (1.0, 0.88, 0.62))
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(v, 3, 3), 0.5, 0.7), 0.4), col, (0.72, 0.40, 0.12))
    sh.color(col)
    sh.bump(cracks, 0.3, 0.006, invert=True)
    sh.bump(sh.noise(v, 20, 4), 0.12, 0.004)
    return sh.mat


def eclair2(prefix, L, R, mats, deco="drizzle", seed=0):
    zc = R * 0.80
    body = capsule(f"{prefix}Body", L, R, 72, 64)

    def bshape(co):
        z = co.z * 0.82 if co.z > 0 else max(co.z, -R * 0.78) * 0.82
        a = math.atan2(co.z, co.y)
        k = 1.0 + 0.035 * math.cos(9 * a + 0.4 * co.x) * (abs(co.x) < L / 2 - R * 0.4)
        return Vector((co.x, co.y * k, z * k + zc))
    deform(body, bshape)
    push_normals(body, lambda co, n: 0.008 * fbm(co * 5 + Vector((seed, 0, 0))))
    subdivide(body, 1)
    smooth(body)
    assign(body, mats["choux"])
    g = capsule(f"{prefix}Glaze", L + 0.03, R + 0.03, 72, 64)
    deform(g, lambda co: Vector((co.x, co.y * 1.06, co.z * 0.82 + zc)))
    cut = zc + R * 0.18

    def edge_h(x):
        return 0.02 * math.sin(x * 11 + seed) + 0.015 * math.sin(x * 27 + 2 * seed)
    bisect(g, (0, 0, cut - 0.03), (0, 0, -1), fill=False)

    def drip(co):
        e = cut + edge_h(co.x)
        if co.z < e + 0.05:
            k = (e + 0.05 - co.z) / 0.08
            dd = max(0.0, 0.05 * math.sin(co.x * 7 + seed * 3)) ** 1.5 * 8
            return Vector((co.x, co.y, co.z - min(0.06, dd * 0.06) * min(1.0, k)))
        return co
    deform(g, drip)
    solidify(g, 0.035, 1.0)
    subdivide(g, 1)
    smooth(g)
    assign(g, mats["glaze"])
    parts = [body, g]
    top = zc + R * 0.82 + 0.03
    if deco == "drizzle":
        pts = []
        for k in range(181):
            t = k / 180
            x = -L / 2 + 0.2 + (L - 0.4) * t
            y = (R * 0.7) * math.sin(t * math.pi * 12)
            z = zc + (R + 0.035) * 0.82 * math.sqrt(max(0.0, 1 - (y / (R + 0.04)) ** 2)) + 0.012
            pts.append((x, y, z))
        dz = EV.sweep(f"{prefix}Drizzle", pts, 0.017, segs=10, step=0.008, section=(0.7, 1.0))
        assign(dz, mats["white"])
        parts.append(dz)
    elif deco == "nuts":
        rnd = random.Random(seed)
        bits = []
        for k in range(26):
            x = rnd.uniform(-L / 2 + 0.2, L / 2 - 0.2)
            y = rnd.uniform(-R * 0.45, R * 0.45)
            z = zc + (R + 0.035) * 0.82 * math.sqrt(max(0.0, 1 - (y / (R + 0.04)) ** 2)) + 0.01
            c = MX.rcube(f"{prefix}Nut{k}", rnd.uniform(0.025, 0.04), rnd.uniform(0.02, 0.032), 0.018, 3.0, 3)
            c.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 3))
            c.location = (x, y, z)
            assign(c, mats["nut"] if k % 3 else mats["pist"])
            bits.append(c)
        parts += bits
    elif deco == "berries":
        for k, x in enumerate((-0.42, -0.14, 0.14, 0.42)):
            if k % 2 == 0:
                rb = raspberry(f"{prefix}Rasp{k}", 0.075, k + seed, mats["rasp"])
                rb.rotation_euler = (math.pi / 2 + 0.3, 0, 0.4 * k)
                rb.location = (x * L / 1.5, 0.0, top + 0.05)
            else:
                rb = BK.blueberry(f"{prefix}Blue{k}", 0.06)
                rb.location = (x * L / 1.5, 0.0, top + 0.035)
            parts.append(rb)
        for k in range(6):
            gl = sphere(f"{prefix}Gold{k}", 0.025, 12, 8)
            gl.scale = (1.0, 0.8, 0.15)
            gl.rotation_euler = (0.3, 0.2, k)
            gl.location = (-L / 2 + 0.3 + 0.18 * k, 0.07 * (-1) ** k, top + 0.004)
            assign(gl, mats["gold"])
            parts.append(gl)
    return parts


def dish_eclair():
    prof = [(0.0, 0.0), (0.92, 0.0), (0.95, 0.015), (0.96, 0.05), (0.97, 0.07), (1.0, 0.11), (0.99, 0.125),
            (0.96, 0.115), (0.93, 0.075), (0.90, 0.06), (0.0, 0.06)]
    plate_ = BK.rr_lathe("EcPlate", prof, 1.10, 0.78, 6.0, 192)
    subdivide(plate_, 1)
    smooth(plate_, 50)
    ps = Sh("EcPlateMat", rough=0.12, coat=0.85, coat_rough=0.04)
    _, _, pz = ps.xyz()
    ps.color(ps.mix(ps.remap(pz, 0.09, 0.105), (0.97, 0.97, 0.98), (0.40, 0.58, 0.90)))
    assign(plate_, ps.mat)
    parts = [plate_]
    mats = {"choux": choux_sh("EcChoux"), "glaze": choc_sh("EcGlaze", (0.18, 0.08, 0.03), (0.40, 0.20, 0.09), 0.2, 0.55),
            "white": cream_sh("EcWhite", (0.96, 0.92, 0.84), (1.0, 0.98, 0.94)),
            "nut": flat("EcNut", (0.84, 0.60, 0.32), rough=0.4, coat=0.3),
            "pist": flat("EcPist", (0.56, 0.74, 0.30), rough=0.4, coat=0.3, sss=0.2),
            "rasp": raspberry_sh("EcRasp"),
            "gold": flat("EcGold", (1.0, 0.80, 0.30), rough=0.15, metal=1.0)}
    L, R = 1.62, 0.25
    for i, (y, deco, dx) in enumerate(((-0.50, "drizzle", 0.06), (0.0, "nuts", -0.04), (0.50, "berries", 0.05))):
        ec = eclair2(f"Ec{i}", L, R, mats, deco, i * 3)
        for o in ec:
            o.location += Vector((dx, y, 0.06))
        parts += ec
    return rotate_all(parts, (0, 0, math.radians(-30)))


# MARK: - Пан-о-шоколя

def pastry_layers_sh(name, H):
    """Слоеное тесто: глянцевый верх, слоистые бока, на торцах завитки слоев; бороздки светлые."""
    sh = Sh(name, rough=0.3, sss=0.3, sss_radius=(1.0, 0.55, 0.25), sss_scale=0.05, coat=0.8, coat_rough=0.05)
    _, _, nz = sh.xyz("Normal")
    x, y, z = sh.xyz()
    v = jitter_vec(sh, 4.0)
    top = sh.ramp(sh.remap(nz, -0.6, 1.0, smooth=False), [(0.0, (0.98, 0.80, 0.46)), (0.4, (0.94, 0.62, 0.24)),
                                                          (0.75, (0.80, 0.44, 0.12)), (1.0, (0.70, 0.34, 0.08))])
    top = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(v, 3.0, 4), 0.4, 0.7), 0.35), top, (0.58, 0.26, 0.06))
    side = sh.remap(sh.math("ABSOLUTE", nz), 0.7, 0.4)
    zz = sh.math("ADD", z, sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(v, 4.0, 3), 0.5), 0.05))
    lam = sh.math("PINGPONG", sh.math("MULTIPLY", zz, 3.5 / H), 0.5)
    lines = sh.math("MULTIPLY", sh.remap(lam, 0.22, 0.10), side)
    fine = sh.math("MULTIPLY", sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", zz, 14.0 / H), 0.5), 0.12, 0.04), side)
    col = sh.mix(sh.math("MULTIPLY", side, 0.7), top, (1.0, 0.84, 0.54))
    col = sh.mix(sh.math("MULTIPLY", fine, 0.5), col, (0.90, 0.58, 0.24))
    col = sh.mix(sh.math("MULTIPLY", lines, 0.9), col, (0.74, 0.40, 0.12))
    stri = sh.noise(sh.mapping(v, scale=(0.25, 3.0, 3.0)), 10.0, 4)
    topm = sh.remap(nz, 0.6, 0.9)
    col = sh.mix(sh.math("MULTIPLY", sh.math("MULTIPLY", sh.remap(stri, 0.55, 0.68), topm), 0.5), col, (0.96, 0.70, 0.34))
    endm = sh.attr("ends")
    rings = sh.math("PINGPONG", sh.math("MULTIPLY", sh.attr("ring"), 9.0), 0.5)
    rl = sh.math("MULTIPLY", sh.remap(rings, 0.14, 0.05), endm)
    col = sh.mix(sh.math("MULTIPLY", endm, 0.6), col, (1.0, 0.84, 0.54))
    col = sh.mix(rl, col, (0.84, 0.50, 0.16))
    sh.color(col)
    sh.bump(sh.math("MAXIMUM", sh.math("MAXIMUM", lines, rl), sh.math("MULTIPLY", fine, 0.4)), 0.4, 0.006, invert=True)
    sh.bump(sh.math("MULTIPLY", stri, topm), 0.2, 0.006)
    sh.bump(sh.noise(v, 22, 4), 0.12, 0.004)
    return sh.mat


def honeycomb_sh(name):
    """Срез слоеного теста: изогнутые слои, вытянутые соты между ними, румяная корка по краю."""
    sh = Sh(name, rough=0.55, sss=0.35, sss_radius=(1.0, 0.7, 0.4), sss_scale=0.05, coat=0.1)
    _, y, z = sh.xyz()
    v = jitter_vec(sh, 3.0)
    zz = sh.math("ADD", z, sh.math("MULTIPLY", sh.math("MULTIPLY", y, y), -0.25))
    zz = sh.math("ADD", zz, sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(v, 5.0, 3), 0.5), 0.04))
    lay = sh.math("PINGPONG", sh.math("MULTIPLY", zz, 18.0), 0.5)
    cells = sh.voronoi(sh.mapping(v, scale=(1.0, 0.6, 2.2)), 16.0, "DISTANCE_TO_EDGE")
    col = sh.ramp(cells, [(0.0, (0.90, 0.60, 0.26)), (0.05, (0.98, 0.78, 0.44)), (0.14, (1.0, 0.92, 0.70)),
                          (1.0, (1.0, 0.95, 0.78))])
    col = sh.mix(sh.remap(lay, 0.1, 0.03), col, (0.86, 0.54, 0.20))
    sh.color(col)
    sh.bump(cells, 0.5, 0.01)
    sh.bump(sh.remap(lay, 0.1, 0.03), 0.3, 0.006, invert=True)
    return sh.mat


def pain_choc2(prefix, mats, Lx=1.36, Ly=0.80, H=0.42, seed=0, cut=False):
    body = MX.rcube(f"{prefix}Body", Lx / 2, Ly / 2, H / 2, 4.6, 30)
    subdivide(body, 1)
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6)

    def shape(co):
        x, y, z = co
        xn, yn = abs(2 * x / Lx), abs(2 * y / Ly)
        dome = 0.06 * max(0.0, 1 - yn ** 2) * max(0.0, 1 - xn ** 6) * max(0.0, (z / (H / 2) + 1) / 2) ** 2
        # бока вздуты слоями
        lay = math.sin((z / H + 0.5) * math.pi * 7 + 1.2 * fbm(co * 3 + Vector((ph, 0, 0))))
        bulge = 0.022 * (abs(lay) ** 0.5) * (1 - abs(2 * z / H) ** 4)
        k = 1 + bulge
        return Vector((x * (1 + 0.6 * bulge), y * k, z + dome + H / 2 + 0.006 * fbm(co * 7)))
    deform(body, shape)
    bpy.context.view_layer.update()
    EV.set_attr(body, "ends", lambda co, n: ss(Lx / 2 - 0.22, Lx / 2 - 0.10, abs(co.x)) * ss(0.4, 0.8, abs(n.x)))
    EV.set_attr(body, "ring", lambda co, n: ((abs(co.y) / (Ly / 2)) ** 3 + (abs(co.z - H * 0.45) / (H * 0.55)) ** 3) ** (1 / 3))
    smooth(body)
    assign(body, mats["pastry"])
    parts = [body]
    for k, zz in enumerate((0.32, 0.62)):
        st = BK.choc_stick(f"{prefix}Stick{k}", Lx + 0.16, 0.17, 0.08)
        st.location = (0.0, 0.03 * (-1) ** k, zz * H)
        assign(st, mats["choc"])
        parts.append(st)
    if cut:
        halves = []
        for side in (-1, 1):
            grp = []
            for o in parts:
                c = o.copy()
                c.data = o.data.copy()
                link(c)
                bisect(c, (0, 0, 0), (-side, 0, 0), fill=True)
                grp.append(c)
            b = grp[0]
            for p in b.data.polygons:
                if abs(p.normal.x) > 0.95 and abs(p.center.x) < 0.01:
                    p.use_smooth = False
            assign_faces(b, mats["pastry"], [(lambda n, c: abs(n.x) > 0.95 and abs(c.x) < 0.01, mats["crumb"])])
            for k, zz in enumerate((0.32, 0.62)):
                blob = sphere(f"{prefix}Melt{side}{k}", 1.0, 32, 20)
                blob.scale = (0.035, 0.14, 0.065)
                blob.location = (side * 0.012, 0.03 * (-1) ** k, zz * H - 0.005)
                apply_transform(blob)
                deform(blob, lambda co: Vector((co.x, co.y, co.z - 0.05 * max(0.0, -co.z / 0.05) ** 2)))
                assign(smooth(blob), mats["choc"])
                grp.append(blob)
            halves.append((side, grp))
        for o in parts:
            bpy.data.objects.remove(o, do_unlink=True)
        return halves
    return parts


def dish_pain_chocolat():
    board = rounded_board("PcBoard", 2.25, 1.80, 0.11, wood_sh("PcWood", (0.88, 0.64, 0.40), (0.62, 0.40, 0.22)))
    parts = [board]
    mats = {"pastry": pastry_layers_sh("PcPastry", 0.5), "crumb": honeycomb_sh("PcCrumb"),
            "choc": choc_sh("PcChoc", (0.16, 0.07, 0.03), (0.36, 0.17, 0.07), 0.0, 0.4)}
    whole = pain_choc2("PcA", mats, seed=1)
    rotate_all(whole, (0, 0, math.radians(4)))
    for o in whole:
        o.location += Vector((0.0, 0.40, 0.0))
    parts += whole
    halves = pain_choc2("PcB", mats, seed=2, cut=True)
    for side, grp in halves:
        rotate_all(grp, (0, 0, math.radians(-108 if side < 0 else 72)))
        for o in grp:
            o.location += Vector((0.46 * side, -0.72, 0.0))
        parts += grp
    return rotate_all(parts, (0, 0, math.radians(-12)))


# MARK: - Паста

def noodle_sh(name, sauce_r=0.42, sauce_z=0.0):
    """Спагетти: теплая желтизна, ближе к соусу окрашены в оранжево-красный."""
    sh = Sh(name, rough=0.26, sss=0.4, sss_radius=(1.0, 0.8, 0.3), sss_scale=0.03, coat=0.6, coat_rough=0.08)
    x, y, z = sh.xyz()
    rr = sh.vmath("LENGTH", sh.combine(x, y, 0.0))
    col = sh.ramp(sh.noise(None, 3.0, 3), [(0.3, (0.98, 0.80, 0.42)), (0.7, (1.0, 0.88, 0.54))])
    coat = sh.math("MULTIPLY", sh.remap(rr, sauce_r + 0.12, sauce_r - 0.05), sh.remap(z, sauce_z - 0.16, sauce_z - 0.04))
    coat = sh.math("ADD", coat, sh.math("MULTIPLY", sh.remap(sh.noise(None, 4.0, 3), 0.6, 0.7), 0.5))
    col = sh.mix(sh.math("MULTIPLY", coat, 0.85), col, (0.92, 0.36, 0.14))
    sh.color(col)
    sh.bump(sh.noise(None, 60, 2), 0.04, 0.002)
    return sh.mat


def sauce_sh(name):
    sh = Sh(name, rough=0.1, sss=0.4, sss_radius=(1.0, 0.3, 0.2), sss_scale=0.03, coat=0.9, coat_rough=0.04)
    v = jitter_vec(sh, 3.0)
    cells = sh.voronoi(v, 16.0, "F1")
    col = sh.ramp(sh.noise(v, 5.0, 4), [(0.3, (0.72, 0.08, 0.04)), (0.55, (0.86, 0.16, 0.07)), (0.8, (0.94, 0.30, 0.12))])
    col = sh.mix(sh.remap(cells, 0.14, 0.04, 0.0, 0.5), col, (1.0, 0.46, 0.20))
    sh.color(col)
    sh.bump(cells, 0.35, 0.01)
    sh.bump(sh.noise(v, 24, 3), 0.1, 0.004)
    return sh.mat


def parmesan_sh(name):
    sh = Sh(name, rough=0.55, sss=0.3, sss_radius=(1.0, 0.9, 0.6), coat=0.1)
    sh.color(sh.ramp(sh.noise(jitter_vec(sh, 5), 40, 3), [(0.3, (1.0, 0.94, 0.74)), (0.7, (1.0, 0.98, 0.86))]))
    sh.bump(sh.noise(None, 80, 3), 0.3, 0.002)
    return sh.mat


def dish_pasta():
    prof = [(0.0, 0.0), (0.44, 0.0), (0.47, 0.02), (0.48, 0.06), (0.46, 0.08), (0.56, 0.10), (0.70, 0.16), (0.80, 0.26),
            (0.86, 0.33), (0.98, 0.37), (1.02, 0.385), (1.0, 0.40), (0.96, 0.395), (0.86, 0.36), (0.80, 0.32),
            (0.70, 0.22), (0.56, 0.16), (0.30, 0.13), (0.0, 0.125)]
    bowl = lathe("PaBowl", prof, 192)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = Sh("PaBowlMat", rough=0.12, coat=0.85, coat_rough=0.04)
    x, y, z = out.xyz()
    rr = out.vmath("LENGTH", out.combine(x, y, 0.0))
    _, _, nz = out.xyz("Normal")
    inner = out.remap(nz, 0.0, 0.3)
    col = out.ramp(out.remap(z, 0.0, 0.43, smooth=False), [(0.0, (0.16, 0.30, 0.66)), (0.8, (0.22, 0.40, 0.80)),
                                                           (1.0, (0.28, 0.48, 0.86))])
    white = (0.98, 0.97, 0.95)
    rim_line = out.math("MULTIPLY", out.remap(out.math("ABSOLUTE", out.math("SUBTRACT", rr, 0.975)), 0.014, 0.008), inner)
    rim_line2 = out.math("MULTIPLY", out.remap(out.math("ABSOLUTE", out.math("SUBTRACT", rr, 0.90)), 0.006, 0.003), inner)
    col = out.mix(inner, col, white)
    col = out.mix(out.math("MAXIMUM", rim_line, rim_line2), col, (0.22, 0.40, 0.80))
    out.color(col)
    assign(bowl, out.mat)
    parts = [bowl]
    floor = 0.125
    Rn, Hn = 0.78, 0.56
    sauce_z = floor + Hn + 0.02

    def dome(rho):
        return floor + Hn * max(0.0, 1 - (rho / Rn) ** 2) ** 0.75
    nmat = noodle_sh("PaNoodle", 0.50, sauce_z)
    core = polar_disc("PaCore", 24, 128, Rn * 0.96, Rn * 0.96)
    deform(core, lambda co: Vector((co.x, co.y, dome(math.hypot(co.x, co.y)) - 0.03)))
    smooth(core)
    assign(core, nmat)
    parts.append(core)
    rnd = random.Random(7)
    strands = []
    for i in range(80):
        rho0 = Rn * math.sqrt(rnd.uniform(0.02, 0.98))
        th0 = rnd.uniform(0, 2 * math.pi)
        turns = rnd.uniform(0.45, 0.9)
        drift = rnd.uniform(-0.2, 0.2)
        ph = rnd.uniform(0, 6)
        pts = []
        n = 70
        for k in range(n):
            t = k / (n - 1)
            th = th0 + 2 * math.pi * turns * t
            rho = max(0.04, min(Rn * 1.02, rho0 + drift * (t - 0.5) * Rn + 0.04 * math.sin(7 * t + ph)))
            z = dome(rho) + 0.012 + 0.018 * (0.5 + 0.5 * math.sin(5 * th + ph)) + 0.03 * (i % 3) / 2
            pts.append((rho * math.cos(th), rho * math.sin(th), z))
        st = EV.sweep(f"PaSpag{i}", pts, 0.030, segs=10, step=0.02)
        strands.append(st)
    parts.append(join_one_(strands, "PaSpaghetti", nmat))
    # соус сверху: горка с кусочками
    smat = sauce_sh("PaSauce")
    sauce = polar_disc("PaSauceMound", 24, 128, 0.52, 0.52)
    zt = dome(0.0)

    def sshape(co):
        rho = math.hypot(co.x, co.y)
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.16 * math.sin(5 * a + 1.0) + 0.08 * math.sin(9 * a)
        t = min(1.0, rho / 0.52)
        return Vector((co.x * k / 1.24 * 1.1, co.y * k / 1.24 * 1.1,
                       dome(rho * k / 1.24 * 1.1) + 0.035 + 0.15 * max(0.0, 1 - t * t) ** 0.8 + 0.02 * fbm(co * 7)))
    deform(sauce, sshape)
    solidify(sauce, 0.03, 0.0)
    smooth(sauce)
    assign(sauce, smat)
    parts.append(sauce)
    bpy.context.view_layer.update()
    dice_mat = tomato_dice_sh("PaDice")

    def chunk(k, rnd):
        c = MX.rcube(f"PaChunk{k}", rnd.uniform(0.045, 0.065), rnd.uniform(0.04, 0.06), 0.035, 3.0, 4)
        push_normals(c, lambda co, n: 0.005 * fbm(co * 30 + Vector((k, 0, 0))))
        return assign(c, dice_mat)
    scatter_world([sauce], 18, chunk, seed=3, rx=0.42, spacing=0.09, nz_min=0.3)
    pmat = parmesan_sh("PaParm")
    parm = []

    def grate(k, rnd):
        c = MX.rcube(f"PaParm{k}", rnd.uniform(0.018, 0.03), rnd.uniform(0.01, 0.016), 0.008, 3.0, 3)
        parm.append(c)
        return assign(c, pmat)
    scatter_world([sauce] + strands_proxy(parts), 60, grate, seed=5, rx=0.62, spacing=0.035, nz_min=0.2, lift=0.006)
    zt = top_z([sauce], 0.0, 0.0, sauce_z)
    for j, (psi, L, el) in enumerate(((0.6, 0.40, 24), (2.6, 0.34, 30), (4.4, 0.30, 34))):
        parts += basil_leaf(f"PaBasil{j}", L, (0.04 * math.cos(psi), 0.04 * math.sin(psi), zt - 0.02), psi,
                            math.radians(el), 0.0, light=(j == 2))
    parts += [o for o in bpy.data.objects if o.type == "MESH" and o.name.startswith(("PaChunk", "PaParm"))]
    # стружка пармезана
    for j, (a, rr) in enumerate(((0.3, 0.30), (2.5, 0.26))):
        sv = surface_flake(f"PaShave{j}", 0.13, 0.08, pmat)
        x, y = rr * math.cos(a), rr * math.sin(a)
        sv.rotation_euler = (0.3, -0.25, a)
        sv.location = (x, y, top_z([sauce], x, y, sauce_z) + 0.03)
        parts.append(sv)
    return rotate_all(parts, (0, 0, math.radians(-10)))


def strands_proxy(parts):
    return [o for o in parts if o.name in ("PaSpaghetti", "PaCore")]


def join_one_(objs, name, mat):
    return RM.join_one(objs, name, mat)


def surface_flake(name, w, d, mat):
    ob = polar_disc(name, 8, 40, w, d)
    deform(ob, lambda co: Vector((co.x, co.y, 0.25 * (co.x ** 2) / w + 0.01 * fbm(co * 20))))
    solidify(ob, 0.012)
    smooth(ob)
    return assign(ob, mat)


# MARK: - Тыквенный суп в тыкве

def dish_pumpkin_soup():
    ribs = 10
    h = 0.84
    z_cut = 0.36

    def rib_k(a):
        u = (a * ribs / (2 * math.pi)) % 1.0
        x = 2 * u - 1
        return 0.90 + 0.10 * max(0.0, 1 - x * x) ** 0.35

    def r_out(z):
        return math.sqrt(max(0.0, 1 - (z / h) ** 2))
    zb = -h * 0.86
    prof = [(0.0, zb + 0.10), (0.22, zb + 0.03)]
    for k in range(1, 41):
        z = zb + (z_cut - zb) * k / 40
        prof.append((r_out(z), z))
    rc = r_out(z_cut)
    wall = 0.07
    prof += [(rc - 0.012, z_cut + 0.012), (rc - wall + 0.012, z_cut + 0.012), (rc - wall, z_cut - 0.004),
             (rc - wall - 0.004, z_cut - 0.07), (0.0, z_cut - 0.07)]
    body = lathe("PsPumpkin", prof, 200)
    subdivide(body, 1)

    def shape(co):
        a = math.atan2(co.y, co.x)
        k = rib_k(a)
        return Vector((co.x * k, co.y * k, co.z))
    deform(body, shape)
    push_normals(body, lambda co, n: 0.006 * fbm(co * 3))

    def groove(co, n):
        a = math.atan2(co.y, co.x)
        u = (a * ribs / (2 * math.pi)) % 1.0
        x = 2 * u - 1
        return (1 - max(0.0, 1 - x * x) ** 0.35) * min(1.0, math.hypot(co.x, co.y) / 0.5)
    EV.set_attr(body, "groove", groove)
    smooth(body)
    skin = Sh("PsSkin", rough=0.32, sss=0.25, sss_radius=(1.0, 0.45, 0.15), sss_scale=0.05, coat=0.6, coat_rough=0.1)
    _, _, z = skin.xyz()
    col = skin.ramp(skin.remap(z, zb, z_cut, smooth=False), [(0.0, (0.80, 0.30, 0.03)), (0.5, (0.96, 0.48, 0.07)),
                                                             (1.0, (1.0, 0.60, 0.14))])
    col = skin.mix(skin.remap(skin.attr("groove"), 0.0, 0.6), col, (0.70, 0.24, 0.02))
    streak = skin.noise(skin.mapping(None, scale=(6.0, 6.0, 0.6)), 3.0, 4)
    col = skin.mix(skin.math("MULTIPLY", skin.remap(streak, 0.55, 0.7), 0.3), col, (1.0, 0.72, 0.26))
    skin.color(col)
    skin.bump(skin.noise(None, 30, 3), 0.06, 0.004)
    flesh = Sh("PsFlesh", rough=0.4, sss=0.5, sss_radius=(1.0, 0.6, 0.2), sss_scale=0.05, coat=0.3)
    flesh.color(flesh.ramp(flesh.noise(None, 20, 3), [(0.3, (1.0, 0.70, 0.22)), (0.7, (1.0, 0.80, 0.36))]))
    flesh.bump(flesh.noise(None, 50, 3), 0.25, 0.003)
    assign_faces(body, skin.mat, [(lambda n, c: c.z > z_cut - 0.08 and (n.z > 0.6 or
                                                                         Vector((c.x, c.y, 0)).dot(n) < 0), flesh.mat)])
    lo = min(v.co.z for v in body.data.vertices)
    parts = [body]
    # суп
    soup = polar_disc("PsSoup", 30, 200, rc - wall + 0.01, rc - wall + 0.01)
    deform(soup, lambda co: Vector((co.x * rib_k(math.atan2(co.y, co.x)), co.y * rib_k(math.atan2(co.y, co.x)),
                                    z_cut - 0.022 + 0.012 * (1 - (co.x ** 2 + co.y ** 2) / rc ** 2)
                                    + 0.004 * fbm(co * 6))))
    smooth(soup)
    ss_ = Sh("PsSoupMat", rough=0.16, sss=0.5, sss_radius=(1.0, 0.5, 0.15), sss_scale=0.05, coat=0.6, coat_rough=0.08)
    sx, sy, _ = ss_.xyz()
    srr = ss_.vmath("LENGTH", ss_.combine(sx, sy, 0.0))
    scol = ss_.ramp(ss_.remap(srr, 0.0, rc, smooth=False), [(0.0, (1.0, 0.66, 0.18)), (0.7, (0.99, 0.56, 0.10)),
                                                            (1.0, (0.94, 0.46, 0.06))])
    scol = ss_.mix(ss_.math("MULTIPLY", ss_.remap(ss_.noise(None, 5, 3), 0.5, 0.7), 0.3), scol, (1.0, 0.74, 0.30))
    ss_.color(scol)
    ss_.bump(ss_.noise(None, 9, 3), 0.06, 0.008)
    assign(soup, ss_.mat)
    parts.append(soup)
    zs = z_cut - 0.01
    cream = cream_sh("PsCream", (0.97, 0.94, 0.88), (1.0, 0.99, 0.96))
    pts = []
    for k in range(140):
        t = k / 139
        a = 2 * math.pi * 1.8 * t + 0.6
        rr = 0.04 + 0.40 * t
        pts.append((rr * math.cos(a) - 0.05, rr * math.sin(a) + 0.02, zs + 0.006))
    swirl = EV.sweep("PsSwirl", pts, lambda t: 0.052 * (1.0 - 0.45 * t), segs=16, step=0.01, section=(0.36, 1.0))
    assign(swirl, cream)
    parts.append(swirl)
    seed_mat = Sh("PsPepita", rough=0.3, coat=0.5, sss=0.2)
    seed_mat.color(seed_mat.ramp(seed_mat.noise(None, 20, 2), [(0.3, (0.36, 0.52, 0.18)), (0.7, (0.54, 0.68, 0.28))]))
    rnd = random.Random(3)
    for i in range(11):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.18, 0.56)
        sd = sphere(f"PsPepita{i}", 1.0, 24, 14)
        sd.scale = (0.075, 0.042, 0.02)
        apply_transform(sd)
        deform(sd, lambda co: Vector((co.x, co.y * (1.0 - 1.4 * max(0.0, co.x)), co.z)))
        assign(smooth(sd), seed_mat.mat)
        sd.rotation_euler = (rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), rnd.uniform(0, 6.28))
        sd.location = (rr * math.cos(a), rr * math.sin(a), zs + 0.02)
        parts.append(sd)
    herb = herb_bits_mat("PsHerb")
    for i in range(16):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.1, 0.6)
        hb = MX.cilantro(f"PsHerb{i}", rnd.uniform(0.035, 0.05))
        hb.rotation_euler = (0, 0, rnd.uniform(0, 6))
        hb.location = (rr * math.cos(a), rr * math.sin(a), zs + 0.012)
        assign(hb, herb)
        parts.append(hb)
    toast = crumb_toast_sh("PsCrouton", grill=False, scale=2.0)
    for i, (a, rr) in enumerate(((2.2, 0.36), (2.8, 0.50), (-0.6, 0.44))):
        c = MX.rcube(f"PsCrouton{i}", 0.075, 0.07, 0.065, 4.0, 5)
        push_normals(c, lambda co, n: 0.008 * fbm(co * 18 + Vector((i, 0, 0))))
        c.rotation_euler = (0.2, 0.15, a)
        c.location = (rr * math.cos(a), rr * math.sin(a), zs + 0.04)
        assign(c, toast)
        parts.append(c)
    pep = flat("PsPepper", (0.10, 0.07, 0.05), rough=0.5)
    for i in range(18):
        a = rnd.uniform(0, 2 * math.pi)
        rr = rnd.uniform(0.05, 0.6)
        d = sphere(f"PsPep{i}", 0.01, 8, 6)
        d.location = (rr * math.cos(a), rr * math.sin(a), zs + 0.008)
        assign(d, pep)
        parts.append(d)
    plate_ = flat_plate("PsPlate", 1.28, [(0.0, (0.96, 0.92, 0.84)), (0.85, (0.99, 0.96, 0.90)), (0.92, (0.70, 0.44, 0.24)),
                                          (1.0, (0.62, 0.36, 0.18))], rim=0.06, h=0.06)
    plate_.location.z = lo - 0.06 + 0.02
    parts.append(plate_)
    return rotate_all(parts, (0, 0, math.radians(-8)))


def herb_bits_mat(name):
    sh = Sh(name, rough=0.3, sss=0.3, sss_radius=(0.5, 1.0, 0.3), coat=0.5)
    sh.color(sh.ramp(sh.noise(jitter_vec(sh, 4), 20, 2), [(0.3, (0.16, 0.48, 0.10)), (0.7, (0.30, 0.64, 0.16))]))
    return sh.mat


# MARK: - Мексика: общие

def seared_meat_sh(name, lo=(0.36, 0.15, 0.06), hi=(0.64, 0.32, 0.14)):
    sh = Sh(name, rough=0.32, sss=0.2, sss_radius=(1.0, 0.4, 0.3), sss_scale=0.03, coat=0.55, coat_rough=0.12)
    v = jitter_vec(sh, 8.0)
    _, _, nz = sh.xyz("Normal")
    col = sh.ramp(sh.noise(v, 9.0, 4), [(0.25, lo), (0.55, tuple((a + b) / 2 for a, b in zip(lo, hi))), (0.8, hi)])
    char = sh.remap(sh.noise(v, 5.0, 5, 0.6), 0.58, 0.72)
    col = sh.mix(sh.math("MULTIPLY", char, 0.8), col, (0.20, 0.08, 0.03))
    fib = sh.noise(sh.mapping(v, scale=(1.0, 5.0, 1.0)), 12.0, 3)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(fib, 0.55, 0.7), 0.3), col, (0.74, 0.42, 0.22))
    sh.color(col)
    sh.bump(fib, 0.2, 0.004)
    sh.bump(sh.noise(v, 30, 4), 0.25, 0.004)
    return sh.mat


def onion_dice_sh(name, red=False):
    sh = Sh(name, rough=0.15, sss=0.6, sss_radius=(1.0, 1.0, 0.9), sss_scale=0.03, coat=0.8, coat_rough=0.05)
    _, _, z = sh.xyz()
    lines = sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", z, 50.0), 0.5), 0.1, 0.03)
    c0, c1 = ((0.70, 0.22, 0.48), (0.96, 0.84, 0.92)) if red else ((0.95, 0.95, 0.90), (1.0, 1.0, 0.98))
    sh.color(sh.mix(lines, c1, c0))
    return sh.mat


def chunky_scatter(prefix, targets, specs, center=(0.0, 0.0), rx=0.5, ry=None, seed=1):
    """specs: [(kind, count, size, mat, spacing)] - кусочки ложатся по очереди на уже лежащие."""
    out = []
    tg = list(targets)
    for si, (kind, count, size, mat, spacing) in enumerate(specs):
        made = []

        def mk(k, rnd, kind=kind, size=size, mat=mat, si=si):
            nm = f"{prefix}{kind}{si}_{k}"
            if kind == "cube":
                c = MX.rcube(nm, size * rnd.uniform(0.8, 1.15), size * rnd.uniform(0.75, 1.0), size * rnd.uniform(0.6, 0.85),
                             3.0, 4)
                push_normals(c, lambda co, n: size * 0.12 * fbm(co * 9 / size + Vector((k, si, 0))))
                c.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0)
                c.location.z += size * 0.4
            elif kind == "leaf":
                c = MX.cilantro(nm, size * rnd.uniform(0.85, 1.15))
                c.location.z += size * 0.15
            elif kind == "ball":
                c = sphere(nm, size, 16, 10)
                c.scale = (1.0, 0.8, 0.7)
                c.location.z += size * 0.5
            assign(c, mat)
            made.append(c)
            return c
        scatter_world(tg, count, mk, seed=seed + si * 7, center=center, rx=rx, ry=ry, spacing=spacing, nz_min=0.15)
        bpy.context.view_layer.update()
        tg += made
        out += made
    return out


# MARK: - Тако

def dish_taco():
    plate_ = MX.talavera_plate("TacoPlate", 1.10)
    parts = [plate_]
    tort = RM.tortilla_sh("TacoTortilla").mat
    meat = seared_meat_sh("TacoMeat", (0.50, 0.22, 0.09), (0.74, 0.42, 0.20))
    cr = Sh("TacoCrumble", rough=0.35, coat=0.5, coat_rough=0.12, sss=0.15)
    cells = cr.voronoi(None, 26.0, "F1")
    cr.color(cr.ramp(cr.voronoi(None, 26.0, "F1", 1.0, "Color"), [(0.0, (0.40, 0.17, 0.07)), (0.5, (0.62, 0.30, 0.12)),
                                                                  (1.0, (0.74, 0.40, 0.18))]))
    cr.bump(cells, 0.8, 0.02)
    crumble = cr.mat
    meat2 = seared_meat_sh("TacoMeat2", (0.70, 0.28, 0.08), (0.92, 0.50, 0.18))
    onion = onion_dice_sh("TacoOnion")
    tom = tomato_dice_sh("TacoTom")
    herb = herb_bits_mat("TacoHerb")
    crema = cream_sh("TacoCrema", (0.96, 0.95, 0.90), (1.0, 1.0, 0.97))
    for i, (x, y, rz) in enumerate(((-0.08, -0.36, -28), (0.12, 0.36, -28))):
        shell, rf = MX.taco_shell(f"Taco{i}Shell", 0.74, 108, tort)
        fill = capsule(f"Taco{i}Fill", 1.04, rf * 0.70, 48, 32)
        deform(fill, lambda co: Vector((co.x, co.y, co.z * 0.7 + rf * 0.80)))
        push_normals(fill, lambda co, n: 0.03 * fbm(co * 6 + Vector((i, 0, 0))) + 0.012 * fbm(co * 18))
        smooth(fill)
        assign(fill, crumble)
        grp = [shell, fill]
        bits = chunky_scatter(f"Taco{i}", [fill], [("cube", 30, 0.085, meat, 0.085), ("cube", 22, 0.08, meat2, 0.08),
                                                   ("cube", 16, 0.04, onion, 0.06), ("cube", 14, 0.045, tom, 0.07),
                                                   ("leaf", 14, 0.08, herb, 0.08)],
                              rx=0.50, ry=0.20, seed=3 + i)
        grp += bits
        # сметанный соус зигзагом
        pts = []
        for k in range(120):
            t = k / 119
            xx = -0.44 + 0.88 * t
            yy = 0.12 * math.sin(t * math.pi * 7)
            zz = top_z(bits + [fill], xx, yy)
            if zz is not None:
                pts.append((xx, yy, zz + 0.012))
        if len(pts) > 5:
            cr = EV.sweep(f"Taco{i}Crema", pts, 0.02, segs=10, step=0.01, section=(0.7, 1.0))
            assign(cr, crema)
            grp.append(cr)
        rotate_all(grp, (0, 0, math.radians(rz)))
        for o in grp:
            o.location += Vector((x, y, 0.105))
        parts += grp
    for j, (x, y, rz) in enumerate(((0.86, -0.52, 40), (-0.84, 0.5, 200))):
        w = MX.lime_wedge(f"TacoLime{j}", 0.27)
        w.rotation_euler = (math.radians(180 + 34), 0, math.radians(rz))
        w.location = (x, y, 0.0)
        bpy.context.view_layer.update()
        MX.ground([w], 0.105)
        parts.append(w)
    return rotate_all(parts, (0, 0, math.radians(-8)))


# MARK: - Буррито

def burrito_face_sh(name, R):
    """Срез буррито: витки лепешки, мозаика начинки - рис, фасоль, мясо, сыр, салат, сальса."""
    sh = Sh(name, rough=0.35, sss=0.3, sss_radius=(1.0, 0.8, 0.5), sss_scale=0.03, coat=0.35, coat_rough=0.1)
    _, y, z = sh.xyz()
    rr = sh.math("DIVIDE", sh.vmath("LENGTH", sh.combine(0.0, y, z)), R)
    a = sh.math("ARCTAN2", z, y)
    v = sh.mapping(None, scale=(1.0, 1.0, 1.0))
    cells = sh.voronoi(v, 6.5 / R, "F1", 1.0, "Color")
    cr = sh.xyz(cells)[0]
    cdist = sh.voronoi(v, 6.5 / R, "F1", 1.0, "Distance")
    stops = [(0.0, (0.98, 0.97, 0.92)), (0.36, (0.16, 0.08, 0.10)), (0.54, (0.52, 0.26, 0.12)),
             (0.70, (1.0, 0.70, 0.16)), (0.80, (0.40, 0.70, 0.18)), (0.88, (0.88, 0.18, 0.10)), (0.95, (0.98, 0.97, 0.92))]
    col = sh.ramp(cr, stops, interp="CONSTANT")
    rice = sh.math("MULTIPLY", sh.remap(cr, 0.36, 0.35), 1.0)
    rice = sh.math("MAXIMUM", rice, sh.remap(cr, 0.95, 0.951))
    grains = sh.voronoi(sh.mapping(None, scale=(1.0, 1.0, 2.2)), 34.0 / R * 0.5, "F1")
    col = sh.mix(sh.math("MULTIPLY", sh.remap(grains, 0.10, 0.03, 0.0, 0.5), rice), col, (0.84, 0.82, 0.76))
    col = sh.mix(sh.remap(cdist, 0.05, 0.0, 0.0, 0.6), col, (0.70, 0.56, 0.38))
    spiral = sh.math("ADD", 0.58, sh.math("MULTIPLY", sh.math("ADD", a, math.pi), 0.30 / (2 * math.pi)))
    tl = sh.math("MAXIMUM", sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", rr, spiral)), 0.035, 0.02),
                 sh.remap(rr, 0.90, 0.92))
    col = sh.mix(tl, col, (1.0, 0.88, 0.60))
    sh.color(col)
    sh.bump(sh.math("MULTIPLY", sh.remap(grains, 0.1, 0.03), rice), 0.4, 0.004)
    sh.bump(sh.remap(cdist, 0.06, 0.0), 0.3, 0.006, invert=True)
    return sh.mat


def grilled_tortilla_sh(name, toast=False):
    sh = Sh(name, rough=0.5, sss=0.35, sss_radius=(1.0, 0.8, 0.5), sss_scale=0.04, sheen=0.3, coat=0.15 + 0.2 * toast,
            coat_rough=0.3)
    x, y, z = sh.xyz()
    _, _, nz = sh.xyz("Normal")
    c0, c1 = ((1.0, 0.88, 0.62), (0.96, 0.76, 0.46)) if toast else ((1.0, 0.90, 0.64), (0.98, 0.84, 0.54))
    col = sh.ramp(sh.noise(None, 3, 3), [(0.3, c0), (0.7, c1)])
    spots = sh.math("MULTIPLY", sh.remap(sh.voronoi(None, 6.0, "F1"), 0.22, 0.08),
                    sh.remap(sh.xyz(sh.voronoi(None, 6.0, "F1", 1.0, "Color"))[0], 0.4 - 0.15 * toast, 0.5 - 0.15 * toast))
    col = sh.mix(sh.math("MULTIPLY", spots, 0.7 + 0.2 * toast), col, (0.80, 0.52, 0.22) if not toast else (0.80, 0.48, 0.16))
    if toast:
        small = sh.math("MULTIPLY", sh.remap(sh.voronoi(None, 15.0, "F1"), 0.12, 0.05),
                        sh.remap(sh.noise(None, 3, 2), 0.42, 0.55))
        col = sh.mix(small, col, (0.56, 0.30, 0.10))
    s = sh.math("ADD", sh.math("MULTIPLY", sh.math("ADD", x, sh.math("MULTIPLY", y, 0.6)), 1 / (0.22 if toast else 0.34)),
                sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 5, 3), 0.5), 0.3))
    d = sh.math("PINGPONG", s, 0.5)
    top = sh.remap(nz, 0.2, 0.6)
    if not toast:
        top = sh.math("MULTIPLY", top, sh.remap(sh.noise(None, 2.2, 3), 0.40, 0.55))
    col = sh.mix(sh.math("MULTIPLY", sh.remap(d, 0.18, 0.08, 0.0, 0.5), top), col, (0.74, 0.44, 0.16))
    col = sh.mix(sh.math("MULTIPLY", sh.remap(d, 0.08, 0.04), top), col, (0.36, 0.18, 0.06))
    sh.color(col)
    sh.bump(sh.noise(None, 22, 4), 0.1, 0.004)
    sh.bump(sh.math("MULTIPLY", sh.remap(d, 0.08, 0.04), top), 0.2, 0.006, invert=True)
    return sh.mat


def burrito_half2(prefix, mats, L=1.10, R=0.46, seed=0):
    """Половинка вдоль +X от среза в x=0: торец-срез смотрит в -X, видна начинка."""
    body = capsule(f"{prefix}Body", 2 * L, R, 96, 72)
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6)

    def shp(co):
        k = 1 + 0.025 * fbm(co * 2.2 + Vector((ph, 0, 0)))
        # складка лепешки по спирали
        a = math.atan2(co.z, co.y)
        fold = 0.012 * ss(-0.2, 0.2, math.sin(a - co.x * 1.4 + ph))
        return Vector((co.x, co.y * (k + fold), co.z * 0.92 * (k + fold)))
    deform(body, shp)
    bisect(body, (0, 0, 0), (-1, 0, 0), fill=True)
    for p in body.data.polygons:
        if p.normal.x < -0.95 and abs(p.center.x) < 1e-3:
            p.use_smooth = False
    smooth(body)
    for p in body.data.polygons:
        if p.normal.x < -0.95 and abs(p.center.x) < 1e-3:
            p.use_smooth = False
    assign_faces(body, mats["tortilla"], [(lambda n, c: n.x < -0.95 and abs(c.x) < 1e-3, mats["face"])])
    parts = [body]
    # начинка чуть выпирает из среза: фасоль, рис, мясо, сыр, салат
    kinds = [("bean", 9), ("meat", 7), ("cheese", 4), ("lettuce", 4), ("tom", 4), ("rice", 26)]
    k = 0
    for kind, n in kinds:
        for _ in range(n):
            for _t in range(30):
                yy, zz = rnd.uniform(-0.82, 0.82) * R, rnd.uniform(-0.78, 0.78) * R * 0.92
                if math.hypot(yy / R, zz / (R * 0.92)) < 0.80:
                    break
            if kind == "bean":
                c = sphere(f"{prefix}Bean{k}", 1.0, 16, 10)
                c.scale = (0.03, 0.06, 0.04)
            elif kind == "rice":
                c = sphere(f"{prefix}Rice{k}", 1.0, 10, 6)
                c.scale = (0.012, 0.036, 0.015)
            elif kind == "meat":
                c = MX.rcube(f"{prefix}Meat{k}", 0.03, 0.06, 0.05, 3.0, 4)
            elif kind == "lettuce":
                c = sphere(f"{prefix}Lett{k}", 1.0, 12, 8)
                c.scale = (0.012, 0.07, 0.035)
            else:
                c = MX.rcube(f"{prefix}{kind}{k}", 0.025, 0.045, 0.04, 3.0, 4)
            c.rotation_euler = (rnd.uniform(0, 3.14), rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3))
            c.location = (-0.006, yy, zz)
            apply_transform(c)
            assign(smooth(c), mats[kind])
            parts.append(c)
            k += 1
    return parts


def dish_burrito():
    board = rounded_board("BuBoard", 2.4, 1.7, 0.11, wood_sh("BuWood", (0.84, 0.60, 0.36), (0.58, 0.36, 0.18)))
    parts = [board]
    paper = polar_disc("BuPaper", 8, 4, 1.0, 1.0)
    deform(paper, lambda co: Vector((co.x * 1.05, co.y * 1.05, 0.004 + 0.012 * fbm(co * 3))))
    paper.rotation_euler = (0, 0, math.radians(45 + 8))
    subdivide(paper, 3)
    push_normals(paper, lambda co, n: 0.01 * fbm(co * 4))
    smooth(paper)
    pm = Sh("BuPaperMat", rough=0.6, sheen=0.3, coat=0.05)
    pm.color(pm.ramp(pm.noise(None, 3, 3), [(0.3, (0.94, 0.88, 0.76)), (0.7, (0.98, 0.94, 0.84))]))
    pm.bump(pm.noise(None, 8, 4), 0.2, 0.01)
    assign(paper, pm.mat)
    parts.append(paper)
    R = 0.46
    mats = {"tortilla": grilled_tortilla_sh("BuTortilla"), "face": burrito_face_sh("BuFace", R),
            "bean": material("BuBean", [(0.0, (0.10, 0.05, 0.06)), (1.0, (0.30, 0.16, 0.18))], coord="z", lo=-0.05,
                             hi=0.05, rough=0.12, coat=0.9),
            "rice": flat("BuRice", (1.0, 1.0, 0.97), rough=0.3, sss=0.5, coat=0.4),
            "meat": seared_meat_sh("BuMeat"),
            "cheese": flat("BuCheese", (1.0, 0.72, 0.14), rough=0.2, sss=0.5, coat=0.6),
            "lettuce": flat("BuLett", (0.46, 0.76, 0.22), rough=0.3, sss=0.4, coat=0.5),
            "tom": tomato_dice_sh("BuTom")}
    # нижняя половинка лежит, срез к камере; вторая лежит сверху наискосок
    a = burrito_half2("BuA", mats, 1.0, R, 1)
    rotate_all(a, (0, math.radians(-12), 0))
    rotate_all(a, (0, 0, math.radians(90 + 28)))
    for o in a:
        o.location += Vector((-0.40, -0.30, 0.0))
    MX.ground(a, 0.02)
    b = burrito_half2("BuB", mats, 1.0, R, 2)
    rotate_all(b, (0, math.radians(-14), 0))
    rotate_all(b, (0, 0, math.radians(90 - 26)))
    for o in b:
        o.location += Vector((0.42, -0.26, 0.0))
    MX.ground(b, 0.02)
    parts += a + b
    # мисочка сальсы сзади
    bowl = lathe("BuSalsaBowl", [(0.0, 0.0), (0.16, 0.0), (0.19, 0.02), (0.28, 0.16), (0.29, 0.19), (0.27, 0.19),
                                 (0.25, 0.15), (0.0, 0.12)], 96)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    assign(bowl, RM.terracotta_sh("BuSalsaBowlMat", 0.0, 0.19, band=(0.10, 0.12)).mat)
    bowl.location = (0.0, 0.58, 0.0)
    parts.append(bowl)
    salsa = MX.bowl_fill("BuSalsa", 0.25, 0.14, 0.05, sauce_sh("BuSalsaMat"), noise=0.02, seed=1)
    salsa.location = (0.0, 0.58, 0.0)
    parts.append(salsa)
    bits = chunky_scatter("BuSal", [salsa], [("cube", 9, 0.035, mats["tom"], 0.06), ("cube", 4, 0.03,
                                                                                    onion_dice_sh("BuOnion"), 0.06),
                                             ("leaf", 4, 0.06, herb_bits_mat("BuHerb"), 0.08)],
                          center=(0.0, 0.58), rx=0.18, seed=2)
    parts += bits
    return rotate_all(parts, (0, 0, math.radians(-6)))


# MARK: - Кесадилья

def cheese_sh(name):
    sh = Sh(name, rough=0.12, sss=0.6, sss_radius=(1.0, 0.7, 0.2), sss_scale=0.04, coat=0.9, coat_rough=0.04)
    sh.color(sh.ramp(sh.noise(jitter_vec(sh, 3), 6, 3), [(0.3, (1.0, 0.68, 0.12)), (0.7, (1.0, 0.80, 0.28))]))
    sh.bump(sh.noise(None, 10, 3), 0.1, 0.01)
    return sh.mat


def q_filling_sh(name):
    """Срез начинки: тянучий сыр с кусочками курицы, перца, фасоли, кукурузы."""
    sh = Sh(name, rough=0.15, sss=0.5, sss_radius=(1.0, 0.7, 0.2), sss_scale=0.03, coat=0.8, coat_rough=0.05)
    v = jitter_vec(sh, 5.0)
    cells = sh.voronoi(sh.mapping(v, scale=(1.0, 1.0, 2.4)), 10.0, "F1", 1.0, "Color")
    cr = sh.xyz(cells)[0]
    cd = sh.voronoi(sh.mapping(v, scale=(1.0, 1.0, 2.4)), 10.0, "F1")
    cheese = sh.ramp(sh.noise(v, 8, 3), [(0.3, (1.0, 0.70, 0.14)), (0.7, (1.0, 0.82, 0.30))])
    bit = sh.ramp(cr, [(0.0, (0.86, 0.66, 0.44)), (0.3, (0.88, 0.14, 0.08)), (0.5, (0.34, 0.66, 0.16)),
                       (0.65, (0.20, 0.10, 0.10)), (0.8, (1.0, 0.86, 0.30))], interp="CONSTANT")
    m = sh.math("MULTIPLY", sh.remap(cd, 0.24, 0.16), sh.remap(sh.noise(v, 4, 2), 0.35, 0.5))
    col = sh.mix(m, cheese, bit)
    sh.color(col)
    sh.bump(m, 0.3, 0.008)
    return sh.mat


def q_wedge(prefix, R, span, H, mats, seed=0):
    """Долька кесадильи: две лепешки и толстый слой начинки по срезам, край-дуга прижат."""
    half = span / 2
    pts = [(0.0, 0.0)] + [(R * math.cos(-half + span * k / 30), R * math.sin(-half + span * k / 30)) for k in range(31)]
    c = (R * 0.55, 0.0)
    ob = MX.outline_slab(f"{prefix}Body", pts, H, p=3.6, cuts=44, center=c)
    subdivide(ob, 1)
    rnd = random.Random(seed)
    ph = rnd.uniform(0, 6)

    def shp(co):
        rr = math.hypot(co.x, co.y) / R
        z = co.z
        # верх пухлый, к дуге лепешки сходятся
        if z > 0:
            z = z * (1.0 - 0.25 * ss(0.8, 1.0, rr)) + 0.03 * math.sin(math.pi * min(1.0, rr))
        else:
            z = z * (1.0 - 0.2 * ss(0.8, 1.0, rr))
        return Vector((co.x, co.y, z + H / 2 + 0.01 * fbm(co * 4 + Vector((ph, 0, 0)))))
    deform(ob, shp)
    smooth(ob)

    def is_fill(n, cc):
        a = math.atan2(cc.y, cc.x)
        rr = math.hypot(cc.x, cc.y)
        straight = abs(abs(a) - half) < 0.25 or rr < 0.12
        return straight and abs(n.z) < 0.8 and 0.16 * H < cc.z < 0.82 * H and rr < R * 0.97
    assign_faces(ob, mats["tortilla"], [(is_fill, mats["fill"])])
    parts = [ob]
    # сыр выпирает из срезов
    for side in (-1, 1):
        a = side * half
        nrm = Vector((-math.sin(a) * side, math.cos(a) * side, 0.0))
        dirv = Vector((math.cos(a), math.sin(a), 0.0))
        pts_ = []
        for k in range(30):
            t = 0.12 + 0.8 * k / 29
            p = dirv * (t * R) + nrm * (0.022 + 0.01 * math.sin(t * 13 + seed)) + Vector((0, 0, H * 0.5 + 0.015 * math.sin(t * 9 + side)))
            pts_.append(tuple(p))
        ooze = EV.sweep(f"{prefix}Ooze{side}", pts_, lambda t: 0.06 * (0.75 + 0.35 * math.sin(t * 9 + seed + side)),
                        segs=14, step=0.01, section=(0.7, 1.0))
        assign(ooze, mats["cheese"])
        parts.append(ooze)
        for j in range(2):
            t = rnd.uniform(0.35, 0.8)
            p0 = dirv * (t * R) + nrm * 0.05 + Vector((0, 0, 0.012))
            pud = sphere(f"{prefix}Pud{side}{j}", 1.0, 24, 12)
            pud.scale = (0.10, 0.06, 0.02)
            pud.rotation_euler = (0, 0, math.atan2(dirv.y, dirv.x))
            pud.location = p0
            apply_transform(pud)
            assign(smooth(pud), mats["cheese"])
            parts.append(pud)
    return parts


def dish_quesadilla():
    """Дольки веером вокруг пиалы сальсы: острым углом лежат на бортике, срезы с сыром видны в промежутках."""
    board = MX.round_board("QBoard", 1.24)
    parts = [board]
    mats = {"tortilla": grilled_tortilla_sh("QTortilla", toast=True), "fill": q_filling_sh("QFill"),
            "cheese": cheese_sh("QCheese")}
    z0 = 0.14
    bowl = lathe("QBowl", [(0.0, 0.0), (0.18, 0.0), (0.21, 0.02), (0.31, 0.19), (0.32, 0.23), (0.30, 0.23),
                           (0.28, 0.18), (0.0, 0.14)], 96)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    assign(bowl, RM.terracotta_sh("QBowlMat", 0.0, 0.23, band=(0.12, 0.14)).mat)
    bowl.location = (0, 0, z0)
    salsa = MX.bowl_fill("QSalsa", 0.28, 0.17, 0.06, sauce_sh("QSalsaMat"), noise=0.02, seed=1)
    salsa.location = (0, 0, z0)
    parts += [bowl, salsa]
    bpy.context.view_layer.update()
    parts += chunky_scatter("QSal", [salsa], [("cube", 12, 0.035, tomato_dice_sh("QTom"), 0.06),
                                              ("cube", 5, 0.03, onion_dice_sh("QOnion"), 0.06),
                                              ("leaf", 5, 0.06, herb_bits_mat("QHerb"), 0.08)], rx=0.2, seed=4)
    R, H, span = 0.95, 0.30, math.radians(56)
    n = 5
    for i in range(n):
        a = 2 * math.pi * i / n + math.radians(-90 + 36)
        w = q_wedge(f"QW{i}", R, span, H, mats, i)
        # острый угол на бортике пиалы: наклон вниз к краю доски
        tilt = math.atan2(0.20, R * 0.9)
        rotate_all(w, (0, tilt, 0))
        rotate_all(w, (0, 0, a))
        for o in w:
            o.location += Vector((0.30 * math.cos(a), 0.30 * math.sin(a), 0.0))
        bpy.context.view_layer.update()
        lo = min((o.matrix_world @ v.co).z for o in w for v in o.data.vertices)
        for o in w:
            o.location.z += z0 - lo + 0.002
        parts += w
    lw = MX.lime_wedge("QLime", 0.26)
    lw.rotation_euler = (math.radians(180 + 34), 0, math.radians(20))
    a = 2 * math.pi * 2.5 / n + math.radians(-90 + 36)
    lw.location = (1.0 * math.cos(a), 1.0 * math.sin(a), 0.0)
    bpy.context.view_layer.update()
    MX.ground([lw], z0)
    parts.append(lw)
    rotate_all(parts, (0, 0, math.radians(-8)))
    return rotate_all(parts, (math.radians(12), 0, 0))


# MARK: - Гуакамоле

def guac_sh(name):
    sh = Sh(name, rough=0.3, sss=0.35, sss_radius=(0.6, 1.0, 0.3), sss_scale=0.04, coat=0.45, coat_rough=0.1)
    v = jitter_vec(sh, 2.0)
    col = sh.ramp(sh.noise(v, 4.0, 5), [(0.25, (0.34, 0.52, 0.10)), (0.5, (0.50, 0.68, 0.16)), (0.75, (0.70, 0.82, 0.30))])
    chunks = sh.voronoi(v, 9.0, "F1", 1.0, "Color")
    cr = sh.xyz(chunks)[0]
    cd = sh.voronoi(v, 9.0, "F1")
    pale = sh.math("MULTIPLY", sh.remap(cd, 0.25, 0.12), sh.remap(cr, 0.55, 0.65))
    col = sh.mix(sh.math("MULTIPLY", pale, 0.8), col, (0.80, 0.88, 0.40))
    dark = sh.math("MULTIPLY", sh.remap(cd, 0.22, 0.1), sh.remap(cr, 0.2, 0.1))
    col = sh.mix(sh.math("MULTIPLY", dark, 0.6), col, (0.26, 0.42, 0.08))
    sh.color(col)
    sh.bump(sh.math("MAXIMUM", pale, dark), 0.4, 0.012)
    sh.bump(sh.noise(v, 18, 4), 0.2, 0.006)
    return sh.mat


def volcanic_sh(name):
    sh = Sh(name, rough=0.6, coat=0.15, coat_rough=0.4)
    v = sh.tc("Object")
    col = sh.ramp(sh.noise(v, 4.0, 4), [(0.3, (0.17, 0.15, 0.15)), (0.7, (0.30, 0.27, 0.26))])
    pits = sh.voronoi(v, 30.0, "F1")
    pm = sh.math("MULTIPLY", sh.remap(pits, 0.12, 0.05), sh.remap(sh.xyz(sh.voronoi(v, 30.0, "F1", 1.0, "Color"))[0], 0.5, 0.6))
    col = sh.mix(pm, col, (0.06, 0.05, 0.05))
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(v, 50, 2), 0.62, 0.7), 0.6), col, (0.52, 0.48, 0.45))
    sh.color(col)
    sh.bump(pm, 0.6, 0.01, invert=True)
    sh.bump(sh.noise(v, 25, 5), 0.3, 0.006)
    return sh.mat


def chip_sh(name):
    sh = Sh(name, rough=0.4, sss=0.3, sss_radius=(1.0, 0.7, 0.2), sss_scale=0.03, coat=0.3, coat_rough=0.15)
    v = jitter_vec(sh, 6.0)
    col = sh.ramp(sh.noise(v, 6.0, 4), [(0.3, (0.98, 0.74, 0.22)), (0.7, (1.0, 0.84, 0.36))])
    bub = sh.voronoi(v, 22.0, "F1")
    col = sh.mix(sh.math("MULTIPLY", sh.remap(bub, 0.12, 0.04), 0.5), col, (0.86, 0.52, 0.12))
    salt = sh.math("MULTIPLY", sh.remap(sh.voronoi(sh.mapping(v, loc=(1, 2, 3)), 40.0, "F1"), 0.05, 0.02),
                   sh.remap(sh.noise(v, 5, 2), 0.45, 0.55))
    col = sh.mix(salt, col, (1.0, 1.0, 1.0))
    sh.color(col)
    sh.bump(bub, 0.3, 0.004)
    return sh.mat


def dish_guacamole():
    s = 1.0
    prof = [(0.0, 0.16), (0.36, 0.16), (0.56, 0.19), (0.74, 0.28), (0.86, 0.39), (0.93, 0.49), (0.92, 0.55),
            (0.87, 0.58), (0.80, 0.56), (0.71, 0.46), (0.52, 0.35), (0.26, 0.30), (0.0, 0.29)]
    bowl = lathe("GuMolca", prof, 128)
    subdivide(bowl, 1)
    push_normals(bowl, lambda co, n: 0.012 * fbm(co * 4) + 0.004 * fbm(co * 14))
    smooth(bowl)
    stone = volcanic_sh("GuStone")
    assign(bowl, stone)
    parts = [bowl]
    for i in range(3):
        a = math.radians(-90 + 120 * i + 60)
        foot = lathe(f"GuFoot{i}", [(0.0, 0.0), (0.09, 0.0), (0.12, 0.03), (0.15, 0.18), (0.0, 0.20)], 32)
        foot.location = (0.40 * math.cos(a), 0.40 * math.sin(a), 0.0)
        apply_transform(foot)
        subdivide(foot, 1)
        push_normals(foot, lambda co, n: 0.008 * fbm(co * 6))
        assign(smooth(foot), stone)
        parts.append(foot)
    gmat = guac_sh("GuGuac")
    fill = polar_disc("GuFill", 30, 160, 0.84, 0.84)

    def gshape(co):
        rr = math.hypot(co.x, co.y) / 0.84
        return Vector((co.x, co.y, 0.50 + 0.44 * max(0.0, 1 - rr * rr) ** 0.75 + 0.06 * fbm(co * 3.5) * (1 - rr ** 3)
                       + 0.015 * fbm(co * 10)))
    deform(fill, gshape)
    solidify(fill, 0.05, 0.0)
    smooth(fill)
    assign(fill, gmat)
    parts.append(fill)
    bpy.context.view_layer.update()
    avo = Sh("GuAvo", rough=0.2, sss=0.4, sss_radius=(0.6, 1.0, 0.3), sss_scale=0.03, coat=0.6, coat_rough=0.06)
    _, _, az = avo.xyz()
    avo.color(avo.ramp(avo.remap(az, -0.05, 0.05, smooth=False), [(0.0, (0.40, 0.62, 0.12)), (0.6, (0.76, 0.86, 0.36)),
                                                                  (1.0, (0.88, 0.92, 0.50))]))
    bits = chunky_scatter("Gu", [fill], [("cube", 16, 0.085, avo.mat, 0.13), ("cube", 12, 0.05, tomato_dice_sh("GuTom"), 0.09),
                                         ("cube", 12, 0.04, onion_dice_sh("GuOnion", True), 0.08),
                                         ("cube", 10, 0.03, flat("GuCotija", (1.0, 0.99, 0.94), rough=0.6, sss=0.3), 0.09),
                                         ("leaf", 14, 0.085, herb_bits_mat("GuHerb"), 0.1)],
                          rx=0.72, seed=4)
    parts += bits
    cmat = chip_sh("GuChip")
    for i, (a, rr, tilt) in enumerate(((95, 0.40, 26), (215, 0.42, 30), (335, 0.38, 24), (30, 0.12, 12), (160, 0.14, 10),
                                       (270, 0.30, 34))):
        c = MX.chip(f"GuChip{i}", 0.54 if i < 5 else 0.44, curve=0.22, seed=i)
        solidify(c, 0.01)
        assign(c, cmat)
        th = math.radians(a)
        c.rotation_euler = (math.radians(90 - tilt), 0, th - math.pi / 2)
        bpy.context.view_layer.update()
        x, y = rr * math.cos(th), rr * math.sin(th)
        z = top_z([fill], x, y, 0.8)
        c.location = (x, y, z + 0.16)
        parts.append(c)
    w = MX.lime_wedge("GuLime", 0.27)
    w.rotation_euler = (math.radians(180 + 34 + 18), 0, math.radians(20))
    w.location = (0.56, -0.40, 0.0)
    bpy.context.view_layer.update()
    MX.ground([w], (top_z([fill], 0.56, -0.40, 0.8) or 0.8) - 0.10)
    parts.append(w)
    return rotate_all(parts, (0, 0, math.radians(-10)))


M.MODELS.update({
    "dish_onigiri": dish_onigiri,
    "dish_bruschetta": dish_bruschetta,
    "dish_caprese": dish_caprese,
    "dish_charlotte": dish_charlotte,
    "dish_crepes": dish_crepes,
    "dish_croissant": dish_croissant,
    "dish_eclair": dish_eclair,
    "dish_pain_chocolat": dish_pain_chocolat,
    "dish_pasta": dish_pasta,
    "dish_pumpkin_soup": dish_pumpkin_soup,
    "dish_quesadilla": dish_quesadilla,
    "dish_taco": dish_taco,
    "dish_burrito": dish_burrito,
    "dish_guacamole": dish_guacamole,
})
