"""Французская пекарня (биом 5): ингредиенты, сладости к заказам тройками и блюда."""
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector, kdtree

import models as M
from models import *  # noqa: F401,F403  помощники


# MARK: - Помощники

def rr_lathe(name, profile, ax, ay, p=4.0, segs=128):
    """Тело вращения по скругленному прямоугольнику (суперэллипс): масленка, коробка."""
    verts, faces = [], []
    m = len(profile)
    for i in range(segs):
        a = 2 * math.pi * i / segs
        c, s = math.cos(a), math.sin(a)
        ex = math.copysign(abs(c) ** (2 / p), c) * ax
        ey = math.copysign(abs(s) ** (2 / p), s) * ay
        for r, z in profile:
            verts.append((r * ex, r * ey, z))
    for i in range(segs):
        for j in range(m - 1):
            a, b = i * m + j, ((i + 1) % segs) * m + j
            faces.append((a, b, b + 1, a + 1))
    ob = from_data(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(ob.data)
    bm.free()
    return ob


def lobed(n, depth, power=0.6):
    """Множитель радиуса для рифленой формы: круглые доли и острые бороздки между ними."""
    def fn(a):
        return 1.0 - depth * (1.0 - abs(math.cos(n * a / 2)) ** power)
    return fn


def set_mask(ob, fn, name="mask"):
    """Значение 0..1 в каждой вершине: им материал подкрашивает бороздки, края, глазурь."""
    me = ob.data
    if name in me.attributes:
        me.attributes.remove(me.attributes[name])
    at = me.attributes.new(name, "FLOAT", "POINT")
    for v in me.vertices:
        at.data[v.index].value = max(0.0, min(1.0, fn(v.co.copy())))
    return ob


def mask_over(mat, color, name="mask", lo=0.0, hi=1.0):
    """Подмешивает цвет по маске вершин."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    at = nodes.new("ShaderNodeAttribute")
    at.attribute_name = name
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = lo
    mr.inputs["From Max"].default_value = hi
    links.new(at.outputs["Fac"], mr.inputs["Value"])
    M._mix_over(mat, mr.outputs["Result"], color)
    return mat


def add_bands(mat, color, scale=30.0, axis="Z", width=0.3, distortion=3.0, strength=0.8, side_only=True):
    """Слоистость теста: тонкие неровные полосы вдоль оси, только на боковых гранях."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tc = nodes.new("ShaderNodeTexCoord")
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = axis
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = distortion
    wave.inputs["Detail"].default_value = 3.0
    links.new(tc.outputs["Object"], wave.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 1 - width - 0.08, (0, 0, 0, 1)
    els[1].position, els[1].color = 1 - width + 0.08, (strength, strength, strength, 1)
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    fac = ramp.outputs["Color"]
    if side_only:
        sep = nodes.new("ShaderNodeSeparateXYZ")
        links.new(tc.outputs["Normal"], sep.inputs[0])
        ab = nodes.new("ShaderNodeMath")
        ab.operation = "ABSOLUTE"
        links.new(sep.outputs["Z"], ab.inputs[0])
        mr = nodes.new("ShaderNodeMapRange")
        mr.inputs["From Min"].default_value = 0.75
        mr.inputs["From Max"].default_value = 0.45
        links.new(ab.outputs[0], mr.inputs["Value"])
        mul = nodes.new("ShaderNodeMath")
        mul.operation = "MULTIPLY"
        links.new(fac, mul.inputs[0])
        links.new(mr.outputs["Result"], mul.inputs[1])
        fac = mul.outputs[0]
    M._mix_over(mat, fac, color)
    return mat


def dusting(mat, color=(1.0, 1.0, 1.0), scale=26.0, threshold=0.5, nz_min=0.55):
    """Сахарная пудра или какао: пятнами сверху, по нормали вверх."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tc = nodes.new("ShaderNodeTexCoord")
    nz = nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 6.0
    links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = threshold - 0.08, (0, 0, 0, 1)
    els[1].position, els[1].color = threshold + 0.12, (1, 1, 1, 1)
    links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Normal"], sep.inputs[0])
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = nz_min
    mr.inputs["From Max"].default_value = nz_min + 0.3
    links.new(sep.outputs["Z"], mr.inputs["Value"])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    links.new(ramp.outputs["Color"], mul.inputs[0])
    links.new(mr.outputs["Result"], mul.inputs[1])
    M._mix_over(mat, mul.outputs[0], color)
    return mat


def orient(z_axis, y_hint=(0, 0, 1)):
    """Матрица поворота: ось Z вдоль нормали, Y как можно ближе к подсказке."""
    z = Vector(z_axis).normalized()
    y = Vector(y_hint)
    y = (y - z * y.dot(z))
    if y.length < 1e-4:
        y = Vector((0, 1, 0)) - z * z.y
    y.normalize()
    x = y.cross(z)
    return Matrix((x, y, z)).transposed().to_4x4()


def join(objs, name=None):
    """Сливает мелкие детали одного материала в один меш: быстрее рендер и меньше объектов."""
    if len(objs) == 1:
        return objs[0]
    bpy.context.view_layer.update()
    bm = bmesh.new()
    mats = []
    for o in objs:
        me = o.data.copy()
        me.transform(o.matrix_world)
        offset = len(mats)
        for s in o.data.materials:
            mats.append(s)
        for p in me.polygons:
            p.material_index += offset
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name or objs[0].name)
    bm.to_mesh(me)
    bm.free()
    for m in mats:
        me.materials.append(m)
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    ob = link(bpy.data.objects.new(name or "Joined", me))
    smooth(ob)
    return ob


def ceramic(name, lo, hi, z0=0.0, z1=1.0, coord="z"):
    return material(name, [(0.0, lo), (1.0, hi)], coord=coord, lo=z0, hi=z1, rough=0.14, coat=0.8, coat_rough=0.05)


def inner_faces(ob, mat_out, mat_in, zmin=-1e9):
    """Внутренняя поверхность чаши (нормаль к оси) - своим материалом."""
    def cond(n, c):
        rr = Vector((c.x, c.y, 0))
        return c.z > zmin and rr.length > 1e-3 and n.dot(rr.normalized()) < -0.05
    return assign_faces(ob, mat_out, [(cond, mat_in)])


def bistro_plate(name="Plate", r=1.3):
    """Белая тарелка с синей каймой, как во французском бистро."""
    ob = lathe(name, [(0.0, 0.0), (r * 0.62, 0.0), (r * 0.66, 0.03), (r * 0.7, 0.07), (r * 0.98, 0.16), (r, 0.2),
                      (r * 0.96, 0.21), (r * 0.68, 0.1), (0.0, 0.09)], 128)
    subdivide(ob, 1)
    smooth(ob, 50)
    assign(ob, material(f"{name}Mat", [(0.0, (0.90, 0.92, 0.96)), (0.6, (1.0, 1.0, 1.0)), (0.78, (1.0, 1.0, 1.0)),
                                       (0.84, (0.30, 0.50, 0.86)), (1.0, (0.22, 0.42, 0.80))],
                        coord="z", lo=0.0, hi=0.21, rough=0.14, coat=0.8, coat_rough=0.05))
    return ob


# Палитра выпечки
GOLD_DARK = (0.66, 0.30, 0.07)
GOLD = (0.94, 0.60, 0.20)
GOLD_LIGHT = (1.0, 0.78, 0.40)
DOUGH_IN = (1.0, 0.88, 0.62)
BUTTER_LO = (1.0, 0.78, 0.32)
BUTTER_HI = (1.0, 0.91, 0.56)
CHOC_DARK = (0.24, 0.11, 0.05)
CHOC = (0.40, 0.20, 0.09)
CHOC_LIGHT = (0.56, 0.32, 0.17)
CREAM_LO = (0.95, 0.90, 0.80)
CREAM_HI = (1.0, 0.99, 0.95)


# MARK: - Ингредиенты

def butter_curl(name, length=0.56, r0=0.15, turns=1.3, seed=0):
    """Завиток масла: тонкая пластина, свернутая спиралью, с бороздками и рваным краем."""
    nu, nv = 150, 30
    U = 2 * math.pi * turns
    verts, faces = [], []
    for i in range(nu + 1):
        u = U * i / nu
        r = r0 * (1 - 0.4 * u / U)
        for j in range(nv + 1):
            t = j / nv - 0.5
            edge = abs(2 * t)
            v = t * length + math.copysign(0.025, t) * edge ** 4 * fbm(Vector((u * 0.8, t, seed)))
            rr = r + 0.004 * math.sin(t * length * 90) * (1 - edge ** 6)
            verts.append((v, rr * math.sin(u), -rr * math.cos(u)))
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + nv + 1, a + nv + 2, a + 1))
    ob = from_data(name, verts, faces)
    solidify(ob, 0.024)
    subdivide(ob, 1)
    smooth(ob)
    return ob


def butter():
    dish = rr_lathe("ButterDish", [(0.0, 0.0), (0.80, 0.0), (0.85, 0.02), (0.87, 0.06), (0.96, 0.15), (1.0, 0.19),
                                   (0.975, 0.205), (0.90, 0.12), (0.86, 0.095), (0.0, 0.09)], 1.05, 0.74, 5.0, 160)
    subdivide(dish, 1)
    smooth(dish, 50)
    assign(dish, material("ButterDishMat", [(0.0, (0.40, 0.72, 0.60)), (0.5, (0.62, 0.88, 0.76)), (1.0, (0.80, 0.96, 0.88))],
                          coord="z", lo=0.0, hi=0.21, rough=0.14, coat=0.8, coat_rough=0.05))
    bmat = material("ButterMat", [(0.0, BUTTER_LO), (1.0, BUTTER_HI)], coord="z", lo=0.1, hi=0.55, rough=0.28,
                    sss=0.5, sss_radius=(1.0, 0.8, 0.4), sss_scale=0.1, coat=0.35, coat_rough=0.12, vary=0.05)
    block = box_mesh("Butter", 1.12, 0.6, 0.42, 0.09, cuts=4)
    bevel(block, 0.07, 5, 30)
    subdivide(block, 1)
    push_normals(block, lambda co, n: 0.006 * fbm(co * 3.0))
    smooth(block)
    assign(block, bmat)
    curl = butter_curl("ButterCurl", 0.42, 0.16, 1.35)
    curl.rotation_euler = (0, 0, math.radians(-48))
    curl.location = (0.1, -0.02, 0.51 + 0.16 + 0.012)
    apply_transform(curl)
    assign(curl, material("ButterCurlMat", [(0.0, BUTTER_LO), (1.0, (1.0, 0.96, 0.74))], coord="z", lo=0.5, hi=0.8,
                          rough=0.25, sss=0.5, sss_radius=(1.0, 0.8, 0.4), sss_scale=0.1, coat=0.4))
    return rotate_all([dish, block, curl], (0, 0, math.radians(22)))


def sleeve(name, sx, sy, sz, z0, cuts=6, bev=0.03):
    """Коробочка без торца +Y: бумажная обертка и фольга."""
    ob = box_mesh(name, sx, sy, sz, z0, cuts=cuts)
    bevel(ob, bev, 3, 30)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    kill = [f for f in bm.faces if f.calc_center_median().y > sy / 2 - bev * 1.05]
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def chocolate():
    s, g = 0.31, 0.04
    cols, rows = 3, 5
    W, L = cols * s, rows * s
    bh, sh = 0.07, 0.085
    choc = material("Choc", [(0.0, CHOC_DARK), (0.55, CHOC), (1.0, CHOC_LIGHT)], coord="z", lo=0.0, hi=bh + sh,
                    rough=0.2, coat=0.6, coat_rough=0.08, sss=0.1, sss_radius=(1, 0.5, 0.3))
    # плитка без верхнего правого квадратика: неровный край облома
    rnd = random.Random(4)

    def jag(p0, p1, n=7):
        out = []
        for k in range(n):
            t = k / n
            x = p0[0] + (p1[0] - p0[0]) * t
            y = p0[1] + (p1[1] - p0[1]) * t
            j = 0.0 if k == 0 else rnd.uniform(-0.018, 0.018)
            out.append((x + (j if p0[0] == p1[0] else 0), y + (j if p0[1] == p1[1] else 0)))
        return out
    x0, x1, y0, y1 = -W / 2, W / 2, -L / 2, L / 2
    pts = [(x0, y0), (x1, y0)]
    pts += jag((x1, y1 - s), (x1 - s, y1 - s))
    pts += jag((x1 - s, y1 - s), (x1 - s, y1))
    pts += [(x0, y1)]
    base = profile_prism("ChocBase", pts, bh, 0.0)
    bevel(base, 0.025, 3, 30)
    smooth(base, 40)
    assign(base, choc)
    parts = [base]
    for c in range(cols):
        for r in range(rows):
            if c == cols - 1 and r == rows - 1:
                continue
            q = box_mesh(f"ChocSq{c}{r}", s - g, s - g, sh, bh - 0.01, cuts=1)
            deform(q, lambda co: Vector((co.x * (1 - 0.22 * (co.z - bh) / sh), co.y * (1 - 0.22 * (co.z - bh) / sh), co.z)))
            bevel(q, 0.03, 4, 30)
            subdivide(q, 1)
            q.location = (x0 + s * (c + 0.5), y0 + s * (r + 0.5), 0)
            apply_transform(q)
            smooth(q)
            assign(q, choc)
            parts.append(q)
    parts = [join(parts, "ChocBar")]
    # фольга чуть больше плитки и выглядывает из обертки рваным краем, верх отогнут
    yw = y0 + 2.15 * s
    fl = 2.15 * s + 0.24
    foil = sleeve("Foil", W + 0.05, fl, bh + sh + 0.06, -0.03, cuts=10, bev=0.02)
    foil.location = (0, y0 - 0.02 + fl / 2, 0)
    apply_transform(foil)
    ys = yw - 0.05

    def tear(co):
        y, z = co.y, co.z
        if y > ys:
            k = (y - ys) / (fl - 2.15 * s)
            y = ys + (y - ys) * (1 + 0.45 * math.sin(co.x * 21 + 1.3) * 0.5 + 0.35 * M.fbm(Vector((co.x * 6, 0, z * 3))))
            if z > bh + sh:
                z += 0.16 * k * k
            elif z < 0.0:
                z -= 0.05 * k * k
        return Vector((co.x, y, z))
    deform(foil, tear)
    push_normals(foil, lambda co, n: 0.008 * fbm(co * 9))
    solidify(foil, 0.01)
    smooth(foil)
    assign(foil, material("FoilMat", [(0.0, (0.72, 0.74, 0.80)), (1.0, (0.94, 0.95, 0.98))], coord="z", lo=-0.05,
                          hi=0.2, rough=0.22, metal=1.0, bump=0.45, bump_scale=14, bump_detail=6))
    wl = 2.15 * s + 0.04
    wrap = sleeve("Wrapper", W + 0.12, wl, bh + sh + 0.12, -0.055, cuts=8, bev=0.035)
    wrap.location = (0, y0 - 0.04 + wl / 2, 0)
    apply_transform(wrap)
    solidify(wrap, 0.012)
    smooth(wrap, 50)
    red = material("WrapRed", [(0.0, (0.66, 0.06, 0.10)), (1.0, (0.90, 0.18, 0.20))], coord="z", lo=-0.06, hi=0.22,
                   rough=0.35, coat=0.5, coat_rough=0.1)
    band = material("WrapGold", [(0.0, (0.86, 0.60, 0.18)), (1.0, (1.0, 0.84, 0.42))], coord="z", lo=-0.06, hi=0.22,
                    rough=0.25, metal=0.6, coat=0.4)
    assign_faces(wrap, red, [(lambda n, c: yw - 0.16 < c.y < yw - 0.07, band)])
    parts += [foil, wrap]
    rotate_all(parts, (math.radians(48), 0, 0))
    return rotate_all(parts, (0, 0, math.radians(-32)))


STRAW_PROFILE = [(0.0, -1.0), (0.10, -0.97), (0.24, -0.87), (0.40, -0.68), (0.55, -0.42), (0.66, -0.12), (0.71, 0.15),
                 (0.70, 0.36), (0.63, 0.52), (0.50, 0.63), (0.32, 0.69), (0.14, 0.70), (0.0, 0.67)]


def straw_top(rho):
    """Высота верхушки клубники на расстоянии rho от оси (по профилю)."""
    top = STRAW_PROFILE[6:][::-1]
    for (r0, z0), (r1, z1) in zip(top, top[1:]):
        if r0 <= rho <= r1:
            t = (rho - r0) / max(1e-6, r1 - r0)
            return z0 + (z1 - z0) * t
    return top[-1][1]


def straw_mat(name):
    return material(name, [(0.0, (0.98, 0.34, 0.22)), (0.22, (0.94, 0.14, 0.12)), (0.7, (0.84, 0.05, 0.09)),
                           (0.9, (0.86, 0.10, 0.10)), (1.0, (0.98, 0.62, 0.42))],
                    coord="z", lo=-1.0, hi=0.72, rough=0.14, sss=0.4, sss_radius=(1, 0.2, 0.15), coat=0.85,
                    coat_rough=0.04, vary=0.06, vary_scale=2.0)


def calyx(name, size=1.0, n=7, seed=0):
    """Зеленая звездочка чашелистиков и хвостик."""
    rnd = random.Random(seed)
    green = material(f"{name}Mat", [(0.0, (0.14, 0.46, 0.12)), (1.0, (0.46, 0.80, 0.24))], coord="z", lo=0.6 * size,
                     hi=0.82 * size, rough=0.3, sss=0.3, sss_radius=(0.5, 1, 0.3), coat=0.45)
    parts = []
    for i in range(n):
        ln = size * rnd.uniform(0.30, 0.38)
        wd = size * 0.075
        lf = polar_disc(f"{name}Sepal{i}", 10, 48, ln / 2, wd)

        def shape(co, ln=ln, wd=wd):
            xn = co.x / (ln / 2)
            k = (1 - 0.92 * max(0.0, xn) ** 1.3) * (1 - 0.3 * max(0.0, -xn) ** 2)
            x = co.x + ln / 2
            rho = x
            z = straw_top(min(0.7, rho / size)) * size + 0.018 * size + 0.12 * size * (x / ln) ** 3
            return Vector((x, co.y * k, z + 0.04 * size * (co.y / wd) ** 2))
        deform(lf, shape)
        solidify(lf, 0.02 * size)
        subdivide(lf, 1)
        smooth(lf)
        lf.rotation_euler = (0, 0, 2 * math.pi * i / n + rnd.uniform(-0.15, 0.15))
        apply_transform(lf)
        assign(lf, green)
        parts.append(lf)
    z0 = straw_top(0.0) * size
    stem = tube(f"{name}Stem", [(0, 0, z0), (0.01 * size, 0, z0 + 0.1 * size), (0.05 * size, 0, z0 + 0.2 * size)],
                0.035 * size, taper=(1.1, 0.8))
    assign(smooth(stem), green)
    parts.append(stem)
    return parts


def strawberry_obj(name, size=1.0, seed=0, seeds=True):
    body = lathe(name, [(r * size, z * size) for r, z in STRAW_PROFILE], 72)
    subdivide(body, 1)

    def lump(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.03 * math.sin(3 * a + seed) + 0.02 * M.fbm(co * 1.6 / size + Vector((seed, 0, 0)))
        return Vector((co.x * k, co.y * k, co.z))
    deform(body, lump)
    smooth(body)
    parts = [body]
    if seeds:
        bpy.context.view_layer.update()
        pts = []
        rows = 11
        for k in range(rows):
            zn = -0.86 + 1.32 * k / (rows - 1)
            rr = max(0.12, min(0.72, 0.72 * math.sqrt(max(0.0, 1 - ((zn - 0.12) / 1.0) ** 2))))
            n = max(4, int(2 * math.pi * rr / 0.2))
            for j in range(n):
                a = 2 * math.pi * (j + 0.5 * (k % 2)) / n + seed
                o = Vector((3 * math.cos(a), 3 * math.sin(a), zn * size))
                ok, loc, nor, _ = body.ray_cast(o, Vector((-math.cos(a), -math.sin(a), 0)))
                if ok:
                    pts.append((loc.copy(), nor.copy()))
        kd = kdtree.KDTree(len(pts))
        for i, (p, _) in enumerate(pts):
            kd.insert(p, i)
        kd.balance()
        rad = 0.05 * size

        def dimple(co, n):
            _, _, d = kd.find(co)
            return -0.02 * size * math.exp(-(d / rad) ** 2)
        push_normals(body, dimple)
        smooth(body)
        seed_mat = material(f"{name}SeedMat", [(0.0, (0.96, 0.74, 0.26)), (1.0, (1.0, 0.90, 0.50))], coord="z",
                            lo=-0.01, hi=0.02, rough=0.25, coat=0.6, sss=0.3)
        seeds_obj = []
        for i, (p, nrm) in enumerate(pts):
            sd = sphere(f"{name}Seed{i}", 1.0, 12, 8)
            sd.scale = (0.022 * size, 0.04 * size, 0.018 * size)
            apply_transform(sd)
            sd.matrix_world = Matrix.Translation(p - nrm * 0.006 * size) @ orient(nrm, (0, 0, 1))
            assign(sd, seed_mat)
            seeds_obj.append(sd)
        parts.append(join(seeds_obj, f"{name}Seeds"))
    assign(body, straw_mat(f"{name}Mat"))
    parts += calyx(f"{name}Calyx", size, 7, seed)
    return parts


def strawberry():
    a = strawberry_obj("StrawA", 1.0, 0)
    rotate_all(a, (math.radians(16), math.radians(38), 0))
    for o in a:
        o.location.x -= 0.42
    b = strawberry_obj("StrawB", 0.84, 3)
    rotate_all(b, (math.radians(-4), math.radians(-30), math.radians(30)))
    for o in b:
        o.location += Vector((0.66, 0.5, -0.08))
    return a + b


def cream_mound(name, R=0.8, H=0.45, z0=0.0, seed=0, peaks=(), folds=5):
    """Шапка взбитых сливок: купол с мягкими складками и пиками, загнутыми набок."""
    ob = polar_disc(name, 48, 192, R, R)

    def shape(co):
        x, y = co.x, co.y
        r = min(1.0, math.hypot(x, y) / R)
        a = math.atan2(y, x)
        h = H * max(0.0, 1 - r * r) ** 0.6
        h += 0.045 * math.sin(folds * a + 9 * r + 2.5 * M.fbm(co * 1.4 + Vector((seed, 0, 0)))) * (1 - r) ** 0.7
        dx = dy = 0.0
        for px, py, ph, pr, cx, cy in peaks:
            d2 = (x - px) ** 2 + (y - py) ** 2
            gg = math.exp(-d2 / (pr * pr))
            h += ph * gg ** 1.6
            dx += cx * gg ** 4
            dy += cy * gg ** 4
        return Vector((x + dx, y + dy, z0 + h))
    deform(ob, shape)
    solidify(ob, 0.18)
    subdivide(ob, 1)
    smooth(ob)
    return ob


def whisk(name, L=0.62, W=0.2, loops=5):
    metal = material(f"{name}Metal", [(0.0, (0.62, 0.64, 0.70)), (1.0, (0.92, 0.93, 0.97))], coord="z", lo=-0.7, hi=0.3,
                     rough=0.18, metal=1.0)
    parts = []
    for k in range(loops):
        a = math.pi * k / loops
        pts = []
        for i in range(61):
            s = 2 * i / 60
            u = W * math.sin(math.pi * s) * (0.7 + 0.3 * math.sin(math.pi * min(s, 2 - s) / 1.0))
            z = -L * ((1 - math.cos(math.pi * min(s, 2 - s))) / 2) ** 0.75
            pts.append((u * math.cos(a), u * math.sin(a), z))
        w = tube(f"{name}Wire{k}", pts, 0.011)
        assign(smooth(w), metal)
        parts.append(w)
    ferrule = lathe(f"{name}Ferrule", [(0.0, -0.04), (0.035, -0.04), (0.05, 0.02), (0.05, 0.12), (0.0, 0.12)], 32)
    assign(smooth(ferrule), metal)
    handle = capsule(f"{name}Handle", 0.6, 0.055, 32, 24)
    handle.rotation_euler = (0, math.radians(90), 0)
    handle.location = (0, 0, 0.4)
    apply_transform(handle)
    deform(handle, lambda co: Vector((co.x * (1 + 0.25 * (co.z - 0.1)), co.y * (1 + 0.25 * (co.z - 0.1)), co.z)))
    assign(smooth(handle), material(f"{name}Wood", [(0.0, (0.70, 0.44, 0.22)), (1.0, (0.90, 0.64, 0.38))], coord="z",
                                    lo=0.1, hi=0.7, rough=0.35, coat=0.5, bump=0.05, bump_scale=8))
    return parts + [ferrule, handle]


def cream():
    bowl = lathe("CreamBowl", [(0.0, 0.0), (0.36, 0.0), (0.39, 0.02), (0.40, 0.07), (0.38, 0.09), (0.52, 0.16),
                               (0.74, 0.36), (0.86, 0.56), (0.90, 0.64), (0.885, 0.665), (0.855, 0.66), (0.82, 0.58),
                               (0.70, 0.38), (0.48, 0.20), (0.0, 0.16)], 96)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = ceramic("CreamBowlOut", (0.92, 0.52, 0.62), (1.0, 0.76, 0.82), 0.0, 0.66)
    inn = ceramic("CreamBowlIn", (0.94, 0.94, 0.96), (1.0, 1.0, 1.0), 0.0, 0.66)
    inner_faces(bowl, out, inn, 0.12)
    cmat = material("WhipMat", [(0.0, (0.93, 0.88, 0.80)), (0.5, (0.99, 0.96, 0.90)), (1.0, (1.0, 1.0, 0.97))],
                    coord="nz", lo=-0.2, hi=1.0, rough=0.35, sss=0.6, sss_radius=(1, 0.9, 0.75), sss_scale=0.1,
                    coat=0.2, coat_rough=0.15)
    mound = cream_mound("Whip", 0.83, 0.2, 0.58, 2,
                        peaks=[(-0.08, 0.0, 0.36, 0.2, 0.16, -0.06), (-0.42, -0.18, 0.14, 0.13, -0.07, -0.06),
                               (0.38, -0.25, 0.12, 0.13, 0.06, -0.07), (0.3, 0.36, 0.13, 0.13, 0.06, 0.06),
                               (-0.36, 0.34, 0.12, 0.13, -0.06, 0.05)], folds=7)
    assign(mound, cmat)
    wk = whisk("Whisk")
    rotate_all(wk, (math.radians(-22), math.radians(38), 0))
    for o in wk:
        o.location += Vector((0.34, 0.16, 1.3))
    parts = [bowl, mound] + wk
    return rotate_all(parts, (0, 0, math.radians(-10)))


def sugar_cube(name, s=0.2, mat=None):
    c = box_mesh(name, s, s, s, -s / 2, cuts=2)
    bevel(c, 0.022, 3, 30)
    push_normals(c, lambda co, n: 0.004 * fbm(co * 20))
    smooth(c, 40)
    if mat:
        assign(c, mat)
    return c


def sugar_mat(name="SugarCube"):
    mat = material(name, [(0.0, (0.90, 0.91, 0.94)), (1.0, (1.0, 1.0, 1.0))], coord="nz", lo=-1, hi=1, rough=0.45,
                   sss=0.3, sss_radius=(1, 1, 1), sss_scale=0.05, coat=0.15, bump=0.45, bump_scale=110, bump_detail=2)
    add_speckles(mat, (0.82, 0.85, 0.92), scale=90, threshold=0.62, strength=0.6)
    return mat


def sugar():
    prof = [(0.0, 0.0), (0.30, 0.0), (0.33, 0.02), (0.34, 0.06), (0.31, 0.09), (0.36, 0.12), (0.50, 0.21),
            (0.60, 0.34), (0.625, 0.45), (0.60, 0.56), (0.555, 0.65), (0.56, 0.70), (0.565, 0.725), (0.54, 0.74),
            (0.515, 0.715), (0.52, 0.62), (0.555, 0.47), (0.50, 0.30), (0.32, 0.2), (0.0, 0.18)]
    bowl = lathe("SugarBowl", prof, 96)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    white = ceramic("Porcelain", (0.90, 0.92, 0.97), (1.0, 1.0, 1.0), 0.0, 0.74)
    blue = ceramic("Cobalt", (0.10, 0.24, 0.66), (0.24, 0.42, 0.88), 0.0, 0.74)
    assign_faces(bowl, white, [(lambda n, c: c.z > 0.675 or c.z < 0.1 or 0.53 < c.z < 0.565, blue)])
    parts = [bowl]
    # синие точки-цветочки по пузу
    dots = []
    for i in range(10):
        a = 2 * math.pi * i / 10
        for k, dz in enumerate((0.0,)):
            d = sphere(f"SugarDot{i}{k}", 1.0, 20, 12)
            d.scale = (0.05, 0.05, 0.012)
            apply_transform(d)
            rr = 0.62
            d.matrix_world = Matrix.Translation((rr * math.cos(a), rr * math.sin(a), 0.4)) @ orient(
                (math.cos(a), math.sin(a), 0.12))
            assign(d, blue)
            dots.append(d)
    parts.append(join(dots, "SugarDots"))
    for i, sx in enumerate((-1, 1)):
        h = torus(f"SugarHandle{i}", 0.11, 0.032, 48, 16)
        h.rotation_euler = (math.radians(90), 0, 0)
        h.scale = (1.0, 1.0, 1.0)
        h.location = (sx * 0.64, 0, 0.5)
        apply_transform(h)
        assign(smooth(h), white)
        parts.append(h)
    smat = sugar_mat()
    rnd = random.Random(3)
    inside = [(-0.22, 0.08, 0.66), (0.08, -0.16, 0.67), (0.22, 0.14, 0.66), (-0.08, 0.30, 0.64), (-0.3, -0.18, 0.62),
              (0.32, -0.12, 0.6), (-0.04, 0.02, 0.84), (0.16, -0.02, 0.86)]
    for i, (x, y, z) in enumerate(inside):
        c = sugar_cube(f"SugarIn{i}", 0.2, smat)
        c.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 1.5))
        c.location = (x, y, z)
        parts.append(c)
    for i, (x, y, z, rz, ry) in enumerate(((0.62, -0.62, 0.1, 0.4, 0.0), (0.36, -0.78, 0.1, -0.3, 0.0))):
        c = sugar_cube(f"SugarOut{i}", 0.2, smat)
        c.rotation_euler = (0, ry, rz)
        c.location = (x, y, z)
        parts.append(c)
    return rotate_all(parts, (0, 0, math.radians(8)))


M.MODELS.update({
    "butter": butter,
    "chocolate": chocolate,
    "strawberry": strawberry,
    "cream": cream,
    "sugar": sugar,
})
