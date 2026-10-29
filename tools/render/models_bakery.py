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
    assign(ob, material(f"{name}Mat", [(0.0, (0.90, 0.92, 0.96)), (0.6, (1.0, 1.0, 1.0)), (0.86, (1.0, 1.0, 1.0)),
                                       (0.9, (0.42, 0.60, 0.92)), (1.0, (0.32, 0.50, 0.86))],
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


# MARK: - Сладости к заказам тройками

MAC_SHELL = [(0.0, 0.0), (0.40, 0.0), (0.455, 0.008), (0.49, 0.025), (0.505, 0.048), (0.50, 0.068), (0.485, 0.082),
             (0.455, 0.105), (0.39, 0.145), (0.27, 0.178), (0.13, 0.194), (0.0, 0.198)]


def mirror_z(ob, z0=0.0):
    """Зеркало по высоте с разворотом граней, чтобы нормали смотрели наружу."""
    deform(ob, lambda co: Vector((co.x, co.y, 2 * z0 - co.z)))
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def macaron_obj(name, lo, hi, fill, r=0.5, seed=0):
    shell_mat = material(f"{name}Shell", [(0.0, lo), (1.0, hi)], coord="nz", lo=-0.2, hi=1.0, rough=0.32,
                         sss=0.25, sss_radius=(1, 0.8, 0.7), coat=0.3, coat_rough=0.12, vary=0.04)
    foot_mat = material(f"{name}Foot", [(0.0, tuple(0.5 * a + 0.5 * b for a, b in zip(lo, hi))), (1.0, hi)],
                        coord="z", lo=-0.1, hi=0.1, rough=0.7, sss=0.2, bump=0.5, bump_scale=60, bump_detail=4)
    k = r / 0.5
    parts = []
    for i, top in enumerate((False, True)):
        sh = lathe(f"{name}Shell{i}", [(rr * k, z * k) for rr, z in MAC_SHELL], 96)
        subdivide(sh, 1)

        def ruffle(co, n):
            if co.z > 0.075 * k:
                return 0.0
            f = 1 - abs(co.z - 0.04 * k) / (0.04 * k)
            return 0.016 * k * max(0.0, f) * (0.4 + M.fbm(co * 26 / k + Vector((seed + i, 0, 0)), 2))
        push_normals(sh, ruffle)
        smooth(sh)
        assign_faces(sh, shell_mat, [(lambda n, c: c.z < 0.074 * k and abs(n.z) < 0.85, foot_mat)])
        if not top:
            mirror_z(sh, 0.0)
            sh.location.z = 0.198 * k
        else:
            sh.location.z = 0.198 * k + 0.115 * k
        parts.append(sh)
    fl = lathe(f"{name}Fill", [(0.0, 0.0), (0.41 * k, 0.0), (0.445 * k, 0.025 * k), (0.452 * k, 0.058 * k),
                               (0.445 * k, 0.09 * k), (0.41 * k, 0.115 * k), (0.0, 0.115 * k)], 96)
    subdivide(fl, 1)
    push_normals(fl, lambda co, n: 0.006 * k * M.fbm(co * 14 / k))
    smooth(fl)
    fl.location.z = 0.198 * k
    assign(fl, material(f"{name}FillMat", [(0.0, tuple(c * 0.94 for c in fill)), (1.0, fill)], coord="nz", lo=-1,
                        hi=1, rough=0.3, sss=0.5, sss_radius=(1, 0.9, 0.8), coat=0.3))
    parts.append(fl)
    return parts


def macaron():
    specs = [("MacPink", (0.95, 0.50, 0.62), (1.0, 0.72, 0.80), (1.0, 0.96, 0.92)),
             ("MacPist", (0.56, 0.75, 0.38), (0.76, 0.90, 0.56), (0.95, 0.97, 0.84)),
             ("MacLav", (0.64, 0.53, 0.90), (0.82, 0.74, 0.98), (0.99, 0.95, 1.0))]
    parts = []
    z = 0.0
    for i, (nm, lo, hi, fill) in enumerate(specs):
        mac = macaron_obj(nm, lo, hi, fill, 0.5, i)
        rotate_all(mac, (math.radians(3 * (-1) ** i), math.radians(4 * (-1) ** (i + 1)), math.radians(40 * i)))
        for o in mac:
            o.location += Vector((0.035 * (-1) ** i, -0.02 * i, z))
        parts += mac
        z += 0.52
    # еще один стоит на ребре перед стопкой
    v = macaron_obj("MacVan", (0.98, 0.70, 0.42), (1.0, 0.86, 0.60), (0.55, 0.30, 0.16), 0.46, 7)
    rotate_all(v, (math.radians(76), 0, math.radians(-58)), pivot=(0, 0, 0.24))
    for o in v:
        o.location += Vector((0.66, -0.5, 0.22))
    parts += v
    return rotate_all(parts, (0, 0, math.radians(-8)))


def madeleine_obj(name, L=0.62, W=0.5, H=0.2, seed=0):
    ob = quad_sphere(name, 44)
    hy = -0.95 * L
    N = 40

    def shape(co):
        x, y, z = co.x, co.y, co.z
        w = W * (0.55 + 0.45 * (y + 1) / 2)
        X, Y = x * w, y * L
        dy = Y - hy
        phi = math.atan2(X, dy)
        dist = math.hypot(X, dy)
        rib = 0.5 + 0.5 * math.cos(N * phi)
        fade = smoothstep(0.08, 0.35, dist)
        edge = max(0.0, 1 - abs(z) / 0.35)
        sc = 1 + 0.035 * rib * fade * edge
        X, Y = X * sc, hy + dy * sc
        if z > 0:
            Z = z * H + 0.03 * rib * fade * min(1.0, z * 3) ** 0.6
        else:
            Z = z * H * 0.4
        return Vector((X, Y, Z + H * 0.4))
    deform(ob, shape)
    subdivide(ob, 1)
    smooth(ob)

    def valley(co):
        dy = co.y - hy
        phi = math.atan2(co.x, dy)
        return (0.5 - 0.5 * math.cos(N * phi)) * smoothstep(0.08, 0.35, math.hypot(co.x, dy))
    set_mask(ob, valley)
    mat = material(f"{name}Mat", [(0.0, (0.72, 0.38, 0.10)), (0.42, (0.78, 0.42, 0.11)), (0.62, (0.92, 0.58, 0.20)),
                                  (0.85, (0.99, 0.74, 0.34)), (1.0, (1.0, 0.82, 0.46))],
                   coord="nz", lo=-1, hi=1, rough=0.38, sss=0.25, sss_radius=(1, 0.6, 0.3), coat=0.45,
                   coat_rough=0.1, bump=0.08, bump_scale=22, vary=0.1, vary_scale=4)
    mask_over(mat, (0.80, 0.46, 0.13), lo=0.2, hi=1.2)
    assign(ob, mat)
    return ob


def madeleine():
    a = madeleine_obj("MadA", seed=0)
    rotate_all([a], (math.radians(14), 0, math.radians(-28)))
    a.location = (-0.12, -0.25, 0)
    b = madeleine_obj("MadB", seed=1)
    rotate_all([b], (math.radians(58), 0, math.radians(22)))
    b.location = (0.36, 0.42, 0.38)
    return [a, b]


def brioche():
    n = 12
    prof = [(0.0, 0.0), (0.40, 0.0), (0.45, 0.015), (0.48, 0.05), (0.60, 0.28), (0.72, 0.48), (0.80, 0.62),
            (0.83, 0.70), (0.82, 0.78), (0.76, 0.87), (0.64, 0.95), (0.50, 1.0), (0.38, 1.02), (0.30, 1.0),
            (0.24, 0.97), (0.14, 0.95), (0.0, 0.95)]
    body = lathe("Brioche", prof, 192)
    subdivide(body, 1)

    def lob(co):
        return abs(math.cos(n * math.atan2(co.y, co.x) / 2)) ** 0.5

    def flute(co):
        r = math.hypot(co.x, co.y)
        d = 0.1 * smoothstep(0.18, 0.32, r)
        kk = 1 - d * (1 - lob(co))
        z = co.z + 0.05 * (lob(co) - 0.6) * smoothstep(0.74, 0.9, co.z) * smoothstep(0.2, 0.35, r)
        return Vector((co.x * kk, co.y * kk, z))
    deform(body, flute)
    push_normals(body, lambda co, nn: 0.008 * M.fbm(co * 3.5))
    smooth(body)
    set_mask(body, lambda co: (1 - lob(co)) * smoothstep(0.18, 0.32, math.hypot(co.x, co.y)))
    mat = material("BriocheMat", [(0.0, (1.0, 0.80, 0.42)), (0.35, (0.97, 0.64, 0.24)), (0.62, (0.88, 0.48, 0.13)),
                                  (0.82, (0.72, 0.34, 0.08)), (1.0, (0.60, 0.27, 0.06))],
                   coord="z", lo=0.0, hi=1.04, rough=0.32, sss=0.25, sss_radius=(1, 0.5, 0.25), coat=0.65,
                   coat_rough=0.07, bump=0.05, bump_scale=18, vary=0.12, vary_scale=3)
    mask_over(mat, (1.0, 0.84, 0.50), lo=0.12, hi=0.85)
    assign(body, mat)
    head = sphere("BriocheHead", 0.36, 72, 48)
    deform(head, lambda co: Vector((co.x, co.y, co.z * 0.9)))
    push_normals(head, lambda co, nn: 0.01 * M.fbm(co * 4 + Vector((3, 0, 0))))
    head.location = (0.0, 0.0, 0.95 + 0.24)
    apply_transform(head)
    smooth(head)
    assign(head, material("BriocheHeadMat", [(0.0, (0.94, 0.58, 0.18)), (0.45, (0.76, 0.37, 0.09)),
                                             (1.0, (0.58, 0.25, 0.05))],
                          coord="z", lo=0.92, hi=1.52, rough=0.32, sss=0.25, coat=0.65, coat_rough=0.07, bump=0.05,
                          bump_scale=18, vary=0.1))
    return [body, head]


CANELE_PROF = [(0.0, 0.0), (0.40, 0.0), (0.45, 0.015), (0.47, 0.05), (0.47, 0.2), (0.46, 0.5), (0.45, 0.74),
               (0.465, 0.84), (0.455, 0.92), (0.41, 0.985), (0.34, 1.015), (0.26, 1.015), (0.19, 0.985),
               (0.13, 0.945), (0.06, 0.925), (0.0, 0.92)]


def canele_obj(name, size=1.0, seed=0):
    n = 10
    ob = lathe(name, [(r * size, z * size) for r, z in CANELE_PROF], 160)
    subdivide(ob, 1)

    def depth(z):
        return 0.05 + 0.13 * smoothstep(0.25, 0.88, z / size)

    def flute(co):
        a = math.atan2(co.y, co.x) + seed
        lob = abs(math.cos(n * a / 2)) ** 0.5
        kk = 1 - depth(co.z) * (1 - lob)
        z = co.z
        rr = math.hypot(co.x, co.y) / size
        if z > 0.9 * size and rr > 0.12:
            z += 0.035 * size * (lob - 0.5)
        return Vector((co.x * kk, co.y * kk, z))
    deform(ob, flute)
    push_normals(ob, lambda co, nn: 0.006 * size * M.fbm(co * 5 / size + Vector((seed, 0, 0))))
    smooth(ob)
    set_mask(ob, lambda co: (1 - abs(math.cos(n * (math.atan2(co.y, co.x) + seed) / 2)) ** 0.5) * depth(co.z) / 0.18)
    set_mask(ob, lambda co: (1 - smoothstep(0.08 * size, 0.2 * size, math.hypot(co.x, co.y))) * (co.z > 0.85 * size),
             "crater")
    mat = material(f"{name}Mat", [(0.0, (0.72, 0.38, 0.12)), (0.25, (0.56, 0.24, 0.07)), (0.7, (0.40, 0.15, 0.05)),
                                  (1.0, (0.28, 0.10, 0.035))],
                   coord="z", lo=0.0, hi=1.02 * size, rough=0.25, sss=0.15, sss_radius=(1, 0.4, 0.2), coat=0.75,
                   coat_rough=0.06, bump=0.06, bump_scale=14, vary=0.1, vary_scale=3)
    mask_over(mat, (0.20, 0.07, 0.025), lo=0.2, hi=1.0)
    mask_over(mat, (0.70, 0.38, 0.14), name="crater")
    assign(ob, mat)
    return ob


def canele():
    a = canele_obj("CaneleA", 1.0, 0.0)
    a.location = (-0.3, -0.12, 0)
    b = canele_obj("CaneleB", 0.92, 0.2)
    b.location = (0.42, 0.36, 0)
    return [a, b]


def meringue_kiss(name, r=0.42, h=0.78, n=8, twist=1.1, curl=0.12, seed=0):
    K, S = 72, 192
    verts = [(0.0, 0.0, 0.0)]
    for k in range(K):
        t = 0.985 * k / (K - 1)
        R = r * (1 - t ** 1.2) ** 1.45
        R *= 0.86 + 0.14 * math.sin(min(1.0, t / 0.07) * math.pi / 2)
        star = 0.14 * (1 - t ** 2)
        cx = curl * t ** 3
        z = h * t - 0.05 * h * t ** 4
        for j in range(S):
            a = 2 * math.pi * j / S
            rr = R * (1 + star * math.cos(n * a - twist * n * t + seed))
            verts.append((cx + rr * math.cos(a), rr * math.sin(a), z))
    verts.append((curl * 1.05, 0.0, h * 0.97))
    faces = [(0, 1 + (j + 1) % S, 1 + j) for j in range(S)]
    for k in range(K - 1):
        b0, b1 = 1 + k * S, 1 + (k + 1) * S
        for j in range(S):
            faces.append((b0 + j, b0 + (j + 1) % S, b1 + (j + 1) % S, b1 + j))
    top = len(verts) - 1
    b0 = 1 + (K - 1) * S
    faces += [(b0 + j, b0 + (j + 1) % S, top) for j in range(S)]
    ob = from_data(name, verts, faces)
    subdivide(ob, 1)
    smooth(ob)
    return ob


def meringue():
    white = material("MerWhite", [(0.0, (0.95, 0.90, 0.82)), (0.35, (0.99, 0.97, 0.93)), (1.0, (1.0, 1.0, 1.0))],
                     coord="z", lo=0.0, hi=0.8, rough=0.3, sss=0.45, sss_radius=(1, 0.9, 0.8), sss_scale=0.08,
                     coat=0.35, coat_rough=0.1)
    pink = material("MerPink", [(0.0, (0.94, 0.52, 0.64)), (0.5, (0.99, 0.70, 0.79)), (1.0, (1.0, 0.84, 0.89))],
                    coord="z", lo=0.0, hi=0.9, rough=0.3, sss=0.45, sss_radius=(1, 0.6, 0.6), sss_scale=0.08,
                    coat=0.35, coat_rough=0.1)
    a = meringue_kiss("MerBack", 0.44, 0.9, 8, 1.1, 0.14, 0.0)
    assign(a, pink)
    a.location = (0.0, 0.48, 0)
    b = meringue_kiss("MerLeft", 0.39, 0.74, 8, -1.0, -0.1, 1.0)
    assign(b, white)
    b.location = (-0.44, -0.2, 0)
    c = meringue_kiss("MerRight", 0.38, 0.72, 8, 1.2, 0.1, 2.0)
    assign(c, white)
    c.location = (0.45, -0.24, 0)
    c.rotation_euler = (0, 0, math.radians(200))
    return [a, b, c]


def heart_outline(w=0.5, n=72):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x * w / 32, (y + 2.5) * w / 32))
    return pts


def teaspoon(name, length=0.8):
    metal = material(f"{name}Metal", [(0.0, (0.66, 0.68, 0.74)), (1.0, (0.95, 0.96, 0.99))], coord="z", lo=-0.05,
                     hi=0.08, rough=0.16, metal=1.0)
    bowl = sphere(f"{name}Bowl", 1.0, 48, 24)
    bowl.scale = (0.13, 0.085, 0.03)
    apply_transform(bowl)
    bisect(bowl, (0, 0, 0.012), (0, 0, 1))
    smooth(bowl)
    bowl.location = (-length / 2 + 0.1, 0, 0.0)
    apply_transform(bowl)
    hd = capsule(f"{name}Handle", length - 0.2, 0.028, 24, 16)
    deform(hd, lambda co: Vector((co.x, co.y * (1 + 0.6 * max(0.0, co.x) / length), co.z * 0.5 + 0.02 * (co.x / length) ** 2)))
    hd.location = (0.1, 0, 0.012)
    apply_transform(hd)
    assign(smooth(bowl), metal)
    assign(smooth(hd), metal)
    return [bowl, hd]


def cafe_creme():
    teal = ceramic("CCTeal", (0.04, 0.42, 0.50), (0.20, 0.68, 0.72), 0.0, 0.75)
    white = ceramic("CCWhite", (0.92, 0.93, 0.95), (1.0, 1.0, 1.0), 0.0, 0.75)
    saucer = lathe("CCSaucer", [(0.0, 0.0), (0.5, 0.0), (0.55, 0.03), (0.58, 0.07), (0.95, 0.14), (1.0, 0.17),
                                (0.97, 0.185), (0.62, 0.10), (0.0, 0.09)], 128)
    subdivide(saucer, 1)
    smooth(saucer, 50)
    assign(saucer, ceramic("CCSaucerMat", (0.04, 0.40, 0.48), (0.24, 0.72, 0.76), 0.0, 0.185))
    cup = lathe("CCCup", [(0.0, 0.1), (0.26, 0.1), (0.30, 0.115), (0.32, 0.15), (0.30, 0.18), (0.40, 0.22),
                          (0.54, 0.34), (0.63, 0.50), (0.67, 0.64), (0.685, 0.72), (0.672, 0.742), (0.648, 0.735),
                          (0.635, 0.68), (0.61, 0.58), (0.0, 0.52)], 128)
    subdivide(cup, 1)
    smooth(cup, 50)
    inner_faces(cup, teal, white, 0.5)
    coffee = polar_disc("CCCoffee", 24, 128, 0.645, 0.645)
    deform(coffee, lambda co: Vector((co.x, co.y, 0.685 + 0.005 * (1 - (co.x ** 2 + co.y ** 2) / 0.42))))
    solidify(coffee, 0.04)
    smooth(coffee)
    assign(coffee, material("CCCoffeeMat", [(0.0, (0.88, 0.68, 0.46)), (0.5, (0.80, 0.55, 0.32)), (0.78, (0.62, 0.36, 0.16)),
                                            (0.9, (0.52, 0.28, 0.12)), (0.97, (0.90, 0.80, 0.66)), (1.0, (0.96, 0.90, 0.80))],
                            coord="r", lo=0.0, hi=0.645, rough=0.25, sss=0.3, coat=0.5, vary=0.08, vary_scale=6))
    heart = profile_prism("CCHeart", heart_outline(0.5), 0.014, 0.702)
    bevel(heart, 0.007, 2, 30)
    smooth(heart, 50)
    heart.location = (0.0, -0.03, 0)
    apply_transform(heart)
    assign(heart, material("CCHeartMat", [(0.0, (0.98, 0.94, 0.88)), (1.0, (1.0, 0.99, 0.96))], coord="z", lo=0.69,
                           hi=0.71, rough=0.4, sss=0.4, coat=0.2))
    handle = torus("CCHandle", 0.15, 0.045, 64, 20)
    handle.scale = (1.0, 1.0, 1.0)
    handle.rotation_euler = (math.radians(90), 0, 0)
    handle.location = (0.74, 0, 0.47)
    apply_transform(handle)
    deform(handle, lambda co: Vector((co.x, co.y * 0.8, 0.47 + (co.z - 0.47) * 1.15)))
    smooth(handle)
    assign(handle, teal)
    rotate_all([handle], (0, 0, math.radians(-32)))
    parts = [saucer, cup, coffee, heart, handle]
    return rotate_all(parts, (math.radians(14), 0, math.radians(6)))


def millefeuille():
    Lx, Ly = 1.5, 0.72
    pastry = material("MFPastry", [(0.0, (0.80, 0.46, 0.14)), (0.45, (0.94, 0.64, 0.26)), (0.7, (1.0, 0.78, 0.40)),
                                   (1.0, (0.96, 0.70, 0.32))],
                      coord="nz", lo=-1, hi=1, rough=0.42, sss=0.2, sss_radius=(1, 0.6, 0.3), coat=0.3,
                      bump=0.35, bump_scale=24, bump_detail=6, vary=0.15, vary_scale=6)
    add_bands(pastry, (0.72, 0.38, 0.10), scale=11.0, axis="Z", width=0.28, distortion=4.0, strength=0.75)
    cream_mat = material("MFCream", [(0.0, (1.0, 0.86, 0.56)), (1.0, (1.0, 0.94, 0.76))], coord="nz", lo=-1, hi=1,
                         rough=0.3, sss=0.5, sss_radius=(1, 0.8, 0.5), coat=0.3)
    add_speckles(cream_mat, (0.36, 0.22, 0.12), scale=70, threshold=0.73, strength=0.7)
    parts = []
    z = 0.0
    layers = [("P", 0.14), ("C", 0.17), ("P", 0.12), ("C", 0.17), ("P", 0.12)]
    for i, (kind, h) in enumerate(layers):
        if kind == "P":
            p = box_mesh(f"MFPastry{i}", Lx, Ly, h, z, cuts=36)
            bevel(p, 0.025, 3, 30)

            def flake(co, n, i=i, z0=z, h=h):
                if abs(n.z) > 0.6:
                    return 0.006 * M.fbm(co * 10)
                return 0.009 * math.sin((co.z - z0) / h * math.pi * 5 + 2 * M.fbm(co * 4 + Vector((i, 0, 0)))) + \
                    0.008 * M.fbm(co * 14 + Vector((0, i, 0)))
            push_normals(p, flake)
            subdivide(p, 1)
            smooth(p)
            assign(p, pastry)
            parts.append(p)
        else:
            core = box_mesh(f"MFCreamCore{i}", Lx - 0.1, Ly - 0.1, h + 0.02, z - 0.01)
            assign(core, cream_mat)
            blobs = []
            rb = h * 0.56
            nx = int(Lx / (2 * rb * 0.92))
            ny = int(Ly / (2 * rb * 0.92))
            pos = []
            for k in range(nx):
                x = -Lx / 2 + rb + (Lx - 2 * rb) * k / (nx - 1)
                pos += [(x, -Ly / 2 + rb - 0.02), (x, Ly / 2 - rb + 0.02)]
            for k in range(1, ny - 1):
                y = -Ly / 2 + rb + (Ly - 2 * rb) * k / (ny - 1)
                pos += [(-Lx / 2 + rb - 0.02, y), (Lx / 2 - rb + 0.02, y)]
            for k, (x, y) in enumerate(pos):
                b = sphere(f"MFBlob{i}_{k}", rb, 32, 20)
                b.scale = (1.0, 1.0, 0.9)
                b.location = (x, y, z + h / 2)
                apply_transform(b)
                push_normals(b, lambda co, n: 0.006 * M.fbm(co * 12))
                assign(b, cream_mat)
                blobs.append(b)
            parts.append(join(blobs + [core], f"MFCream{i}"))
        z += h
    icing = box_mesh("MFIcing", Lx + 0.012, Ly + 0.012, 0.055, z - 0.005, cuts=12)
    bevel(icing, 0.025, 4, 30)
    deform(icing, lambda co: Vector((co.x, co.y, co.z + (0.012 * (1 - (2 * co.x / Lx) ** 4) * (1 - (2 * co.y / Ly) ** 4)
                                                     if co.z > z + 0.02 else 0.0))))
    subdivide(icing, 1)
    smooth(icing)
    assign(icing, material("MFIcingMat", [(0.0, (0.95, 0.94, 0.92)), (1.0, (1.0, 1.0, 0.99))], coord="nz", lo=-1, hi=1,
                           rough=0.15, sss=0.3, coat=0.8, coat_rough=0.05))
    parts.append(icing)
    top = z + 0.05 + 0.012
    lines = []
    for k in range(11):
        x0 = -Lx / 2 + 0.13 + (Lx - 0.26) * k / 10
        pts = []
        for j in range(61):
            y = -Ly / 2 + 0.07 + (Ly - 0.14) * j / 60
            ph = (y + Ly / 2) / 0.16
            tri = 1 - 2 * abs(ph - math.floor(ph) - 0.5) * 2
            sgn = 1 if int(math.floor(ph)) % 2 == 0 else -1
            pts.append((x0 + 0.045 * sgn * max(0.0, tri) ** 1.5, y, top + 0.002))
        ln = tube(f"MFLine{k}", pts, 0.012)
        deform(ln, lambda co: Vector((co.x, co.y, top + (co.z - top) * 0.45)))
        lines.append(ln)
    feather = join(lines, "MFFeather")
    assign(feather, material("MFChoc", [(0.0, CHOC_DARK), (1.0, CHOC)], coord="z", lo=top - 0.01, hi=top + 0.01,
                             rough=0.15, coat=0.7))
    parts.append(feather)
    return rotate_all(parts, (math.radians(8), 0, math.radians(-18)))


# MARK: - Блюда

def pastry_mat(name, top=(0.76, 0.40, 0.10), mid=(0.96, 0.64, 0.24), low=(1.0, 0.80, 0.44), groove=None, gloss=0.75):
    mat = material(name, [(0.0, (0.86, 0.54, 0.20)), (0.3, low), (0.55, mid), (0.8, (0.86, 0.50, 0.15)), (1.0, top)],
                   coord="nz", lo=-1, hi=1, rough=0.32, sss=0.25, sss_radius=(1, 0.55, 0.25), coat=gloss,
                   coat_rough=0.06, bump=0.05, bump_scale=18, vary=0.12, vary_scale=3)
    if groove:
        mask_over(mat, groove, lo=0.1, hi=0.9)
    return mat


def croissant_obj(name, L=1.72, R0=0.36, bend_r=1.1, segs=5, seed=0):
    Nt, Nf = 140, 56
    th_max = (L / 2) / bend_r
    verts, rolls = [], []
    for i in range(Nt + 1):
        t = -1 + 2 * i / Nt
        th = t * th_max
        c = Vector((bend_r * math.sin(th), bend_r * math.cos(th) - bend_r, 0.0))
        nn = Vector((math.sin(th), math.cos(th), 0.0))
        base = R0 * max(0.0, 1 - abs(t) ** 2.2) ** 0.8 + 0.035
        lift = base * 0.86 * 0.8 * 0.5
        for j in range(Nf):
            f = 2 * math.pi * j / Nf
            u = (t + 1) / 2 * segs + 0.22 * math.cos(f) * math.tanh(t * 5)
            roll = abs(math.sin(math.pi * u)) ** 0.55
            rr = base * (0.84 + 0.16 * roll)
            sf = math.sin(f)
            zr = rr * 0.8 * (1.0 if sf > 0 else 0.5)
            p = c + nn * (rr * math.cos(f) * (1 + 0.05 * M.fbm(Vector((t * 3, f, seed))))) + Vector((0, 0, zr * sf + lift))
            verts.append(p)
            rolls.append(1 - roll)
    faces = []
    for i in range(Nt):
        for j in range(Nf):
            a, b = i * Nf + j, i * Nf + (j + 1) % Nf
            faces.append((a, b, b + Nf, a + Nf))
    for end, i0, sgn in ((0, 0, -1), (1, Nt, 1)):
        ring = [i0 * Nf + j for j in range(Nf)]
        cen = sum((verts[k] for k in ring), Vector()) / Nf
        th = sgn * th_max
        tang = Vector((math.cos(th), -math.sin(th), 0)) * sgn
        verts.append(cen + tang * 0.04)
        rolls.append(0.0)
        tip = len(verts) - 1
        for j in range(Nf):
            a, b = ring[j], ring[(j + 1) % Nf]
            faces.append((b, a, tip) if sgn > 0 else (a, b, tip))
    ob = from_data(name, verts, faces)
    at = ob.data.attributes.new("mask", "FLOAT", "POINT")
    for k, v in enumerate(rolls):
        at.data[k].value = v
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, pastry_mat(f"{name}Mat", groove=(1.0, 0.84, 0.52)))
    return ob


def dish_croissant():
    parts = [bistro_plate("CrPlate", 1.36)]
    a = croissant_obj("CroissantA", seed=0)
    a.rotation_euler = (0, 0, math.radians(6))
    a.location = (0.0, 0.34, 0.1)
    b = croissant_obj("CroissantB", seed=2)
    b.rotation_euler = (0, 0, math.radians(-8))
    b.location = (0.02, -0.44, 0.1)
    parts += [a, b]
    return rotate_all(parts, (0, 0, math.radians(-12)))


def choc_stick(name, length, w=0.11, h=0.065):
    st = box_mesh(name, length, w, h, -h / 2, cuts=2)
    bevel(st, 0.02, 3, 30)
    smooth(st, 40)
    assign(st, material(f"{name}Mat", [(0.0, CHOC_DARK), (1.0, CHOC_LIGHT)], coord="z", lo=-h / 2, hi=h / 2,
                        rough=0.2, coat=0.6, coat_rough=0.08))
    return st


def pain_choc_obj(name, Lx=1.24, Ly=0.76, H=0.45, seed=0):
    body = box_mesh(name, Lx, Ly, H, 0.0, cuts=16)
    bevel(body, 0.17, 6, 30)
    subdivide(body, 1)

    def shape(co):
        x, y, z = co
        xn = min(1.0, abs(2 * x / Lx))
        dome = 1 + 0.16 * max(0.0, 1 - (2 * y / Ly) ** 2) * (1 - 0.5 * xn ** 4) * (z / H) ** 2
        return Vector((x, y * (1 + 0.05 * (1 - xn ** 2)), z * dome * (1 - 0.06 * xn ** 6)))
    deform(body, shape)

    def layers(co, n):
        if abs(n.z) > 0.6:
            return 0.007 * M.fbm(co * 5 + Vector((seed, 0, 0)))
        return 0.011 * math.sin(co.z / H * math.pi * 4.2 + 1.2 * M.fbm(co * 3 + Vector((0, seed, 0)))) + \
            0.005 * M.fbm(co * 12)
    push_normals(body, layers)
    smooth(body)

    def ends(co):
        if abs(co.x) < Lx / 2 - 0.16:
            return 0.0
        rr = math.hypot(co.y, co.z - H * 0.5)
        ring = 0.5 + 0.5 * math.sin(rr * 46 + 2 * math.atan2(co.z - H * 0.5, co.y))
        return ring * smoothstep(Lx / 2 - 0.16, Lx / 2 - 0.04, abs(co.x)) * (1 - smoothstep(H * 0.7, H * 0.85, co.z))
    set_mask(body, ends)
    mat = pastry_mat(f"{name}Mat", top=(0.70, 0.34, 0.08))
    mask_over(mat, (1.0, 0.84, 0.54), lo=0.2, hi=0.9)
    add_bands(mat, (1.0, 0.84, 0.54), scale=4.4, axis="Z", width=0.22, distortion=2.0, strength=0.5)
    assign(body, mat)
    parts = [body]
    for k, zz in enumerate((0.14, 0.27)):
        st = choc_stick(f"{name}Stick{k}", Lx + 0.18, 0.16, 0.075)
        st.location = (0.0, 0.03 * (-1) ** k, zz)
        parts.append(st)
    return parts


def dish_pain_chocolat():
    parts = [bistro_plate("PcPlate", 1.36)]
    for i, (y, rz, dx) in enumerate(((0.44, 4, 0.03), (-0.44, -5, -0.04))):
        pc = pain_choc_obj(f"PainChoc{i}", seed=i)
        rotate_all(pc, (0, 0, math.radians(rz)))
        for o in pc:
            o.location += Vector((dx, y, 0.1))
        parts += pc
    return rotate_all(parts, (0, 0, math.radians(-36)))


def eclair_obj(name, L=1.5, R=0.22, drizzle=False, seed=0):
    zc = R * 0.82
    body = capsule(name, L, R, 64, 64)
    deform(body, lambda co: Vector((co.x, co.y, max(co.z, -R * 0.75) * 0.82 + zc)))

    def piped(co, n):
        a = math.atan2(co.z - zc, co.y)
        return 0.008 * math.cos(a * 12) * (abs(co.x) < L / 2 - R * 0.6)
    push_normals(body, piped)
    subdivide(body, 1)
    smooth(body)
    assign(body, pastry_mat(f"{name}Mat", top=(0.86, 0.50, 0.16), gloss=0.4))
    g = capsule(f"{name}Glaze", L + 0.04, R + 0.026, 64, 64)
    deform(g, lambda co: Vector((co.x, co.y, co.z * 0.82 + zc)))
    cut = zc + 0.02
    bisect(g, (0, 0, cut), (0, 0, -1), fill=False)

    def drip(co):
        if co.z < cut + 0.07:
            k = 1 - (co.z - cut) / 0.07
            d = 0.035 + 0.03 * math.sin(co.x * 9 + seed) + 0.025 * math.sin(co.x * 23 + 2 * seed)
            return Vector((co.x, co.y, co.z - max(0.0, d) * k))
        return co
    deform(g, drip)
    solidify(g, 0.024, 1.0)
    subdivide(g, 1)
    smooth(g)
    assign(g, material(f"{name}GlazeMat", [(0.0, CHOC_DARK), (0.6, CHOC), (1.0, (0.50, 0.27, 0.13))], coord="z",
                       lo=zc, hi=zc + R, rough=0.1, coat=0.9, coat_rough=0.03, sss=0.1))
    parts = [body, g]
    if drizzle:
        ry, rz = R + 0.03, (R + 0.03) * 0.82
        pts = []
        for k in range(161):
            t = k / 160
            x = -L / 2 + 0.22 + (L - 0.44) * t
            y = ry * 0.72 * math.sin(t * math.pi * 11)
            z = zc + rz * math.sqrt(max(0.0, 1 - (y / ry) ** 2)) + 0.006
            pts.append((x, y, z))
        dz = tube(f"{name}Drizzle", pts, 0.016)
        assign(smooth(dz), material(f"{name}DrizzleMat", [(0.0, (0.96, 0.92, 0.84)), (1.0, (1.0, 0.98, 0.94))],
                                    coord="z", lo=zc, hi=zc + R, rough=0.2, sss=0.3, coat=0.6))
        parts.append(dz)
    return parts


def dish_eclair():
    parts = [bistro_plate("EcPlate", 1.32)]
    for i, (y, dr) in enumerate(((0.3, True), (-0.3, False))):
        ec = eclair_obj(f"Eclair{i}", drizzle=dr, seed=i * 2)
        for o in ec:
            o.location += Vector((0.04 * (-1) ** i, y, 0.1))
        parts += ec
    return rotate_all(parts, (0, 0, math.radians(-24)))


def strawberry_half(name, s=0.24, seed=0):
    ob = lathe(name, [(r * s, z * s) for r, z in STRAW_PROFILE], 64)
    subdivide(ob, 1)
    deform(ob, lambda co: Vector((co.x * (1 + 0.04 * math.sin(3 * math.atan2(co.y, co.x) + seed)),
                                  co.y * (1 + 0.04 * math.sin(3 * math.atan2(co.y, co.x) + seed)), co.z)))
    bisect(ob, (0, 0, 0), (1, 0, 0))
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data)
    bm.free()
    smooth(ob, 60)
    skin = straw_mat(f"{name}Skin")
    add_speckles(skin, (1.0, 0.86, 0.40), scale=34 / s * 0.25, threshold=0.7, strength=0.9)
    flesh = material(f"{name}Flesh", [(0.0, (0.86, 0.10, 0.12)), (0.2, (0.98, 0.42, 0.40)), (0.42, (1.0, 0.84, 0.80)),
                                      (0.5, (1.0, 0.92, 0.88)), (0.58, (1.0, 0.84, 0.80)), (0.8, (0.98, 0.42, 0.40)),
                                      (1.0, (0.86, 0.10, 0.12))],
                     coord="y", lo=-0.72 * s, hi=0.72 * s, rough=0.12, sss=0.4, sss_radius=(1, 0.3, 0.3),
                     coat=0.9, coat_rough=0.03)
    assign_faces(ob, skin, [(lambda n, c: abs(n.x) > 0.9 and abs(c.x) < 1e-3, flesh)])
    return ob


def dish_tart():
    parts = [bistro_plate("TartPlate", 1.3)]
    shell = lathe("TartShell", [(0.0, 0.1), (0.9, 0.1), (0.96, 0.115), (0.99, 0.15), (1.0, 0.34), (0.99, 0.375),
                                (0.96, 0.39), (0.925, 0.38), (0.91, 0.35), (0.905, 0.31), (0.0, 0.31)], 192)
    subdivide(shell, 1)

    def flute(co):
        r = math.hypot(co.x, co.y)
        if r < 0.88:
            return co
        kk = lobed(32, 0.035, 0.5)(math.atan2(co.y, co.x))
        return Vector((co.x * kk, co.y * kk, co.z))
    deform(shell, flute)
    push_normals(shell, lambda co, n: 0.004 * M.fbm(co * 8))
    smooth(shell)
    crust = material("TartCrust", [(0.0, (0.84, 0.50, 0.16)), (0.5, (0.98, 0.72, 0.34)), (0.85, (0.96, 0.66, 0.28)),
                                   (1.0, (0.86, 0.52, 0.18))],
                     coord="z", lo=0.1, hi=0.39, rough=0.4, sss=0.2, coat=0.4, bump=0.1, bump_scale=16, vary=0.12)
    assign(shell, crust)
    cr = polar_disc("TartCream", 20, 128, 0.91, 0.91)
    deform(cr, lambda co: Vector((co.x, co.y, 0.33 + 0.02 * (1 - (co.x ** 2 + co.y ** 2) / 0.83))))
    solidify(cr, 0.04)
    smooth(cr)
    assign(cr, material("TartCreamMat", [(0.0, (1.0, 0.88, 0.58)), (1.0, (1.0, 0.95, 0.78))], coord="r", lo=0.0,
                        hi=0.9, rough=0.3, sss=0.5, coat=0.4))
    parts += [shell, cr]
    s = 0.24
    rings = [(0.66, 11, 36, 0.0), (0.33, 6, 30, 0.3)]
    k = 0
    for rho, n, lean, off in rings:
        for i in range(n):
            a = 2 * math.pi * (i + off) / n
            h = strawberry_half(f"TartBerry{k}", s * (1.0 if rho > 0.5 else 0.94), k)
            h.rotation_euler = (math.pi, math.radians(-lean), a)
            h.location = (rho * math.cos(a), rho * math.sin(a), 0.35 + 0.62 * s)
            parts.append(h)
            k += 1
    for i in range(3):
        lf = basil_leaf(f"TartMint{i}", 0.42)
        rotate_all(lf, (math.radians(-30), 0, math.radians(30 + 120 * i)))
        for o in lf:
            o.location += Vector((0.0, 0.0, 0.62))
        parts += lf
    return parts


def crepe_obj(name, R, rot, base_z, below=(), th=0.085, seed=0):
    """Блинчик, сложенный вчетверо: лист ложится на тарелку и на уже лежащие блинчики."""
    nr, na = 34, 56
    verts = [(0.0, 0.0, 0.0)]
    for i in range(1, nr + 1):
        rho = R * i / nr
        for j in range(na + 1):
            a = rot + (math.pi / 2) * j / na
            verts.append((rho * math.cos(a), rho * math.sin(a), 0.0))
    faces = [(0, 1 + j, 2 + j) for j in range(na)]
    for i in range(nr - 1):
        b0, b1 = 1 + i * (na + 1), 1 + (i + 1) * (na + 1)
        for j in range(na):
            faces.append((b0 + j, b1 + j, b1 + j + 1, b0 + j + 1))
    ob = from_data(name, verts, faces)
    bpy.context.view_layer.update()
    ring = [(0.0, 0.0, 0.0)] + [(rr * math.cos(k * math.pi / 4), rr * math.sin(k * math.pi / 4), rr)
                                for rr in (0.06, 0.13) for k in range(8)]

    def support(x, y):
        best = base_z
        for dx, dy, d in ring:
            for c in below:
                ok, loc, _, _ = c.ray_cast(Vector((x + dx, y + dy, 5.0)), Vector((0, 0, -1)))
                if ok:
                    best = max(best, loc.z - 0.75 * d)
        return best

    def drape(co):
        rho = math.hypot(co.x, co.y)
        a = math.atan2(co.y, co.x) - rot
        wave = 0.018 * (1 + math.sin(6 * a + 5 * rho + seed)) * (rho / R) ** 2
        puff = 0.03 * math.sin(math.pi * min(1.0, rho / R)) * max(0.0, math.sin(2 * a)) ** 0.7
        return Vector((co.x, co.y, support(co.x, co.y) + 0.004 + wave + puff))
    deform(ob, drape)
    solidify(ob, th, 1.0)
    subdivide(ob, 2)
    smooth(ob)
    return ob


def crepe_mat(name):
    mat = material(name, [(0.0, (0.88, 0.54, 0.22)), (0.5, (0.97, 0.70, 0.36)), (1.0, (1.0, 0.79, 0.46))], coord="nz",
                   lo=-1, hi=1, rough=0.42, sss=0.35, sss_radius=(1, 0.6, 0.3), coat=0.25, bump=0.15, bump_scale=18,
                   vary=0.12, vary_scale=4)
    add_speckles(mat, (0.88, 0.58, 0.26), scale=3.5, threshold=0.58, strength=0.6)
    add_speckles(mat, (0.80, 0.48, 0.18), scale=20.0, threshold=0.67, strength=0.5)
    dusting(mat, (1.0, 1.0, 1.0), scale=12.0, threshold=0.62, nz_min=0.75)
    return mat


def blueberry(name, r=0.075):
    b = sphere(name, r, 32, 20)
    deform(b, lambda co: Vector((co.x, co.y, co.z * 0.88 - 0.25 * r * math.exp(-((co.x ** 2 + co.y ** 2) / (0.3 * r) ** 2)) * (co.z > 0))))
    smooth(b)
    assign(b, material(f"{name}Mat", [(0.0, (0.14, 0.14, 0.36)), (1.0, (0.32, 0.34, 0.62))], coord="z", lo=-r, hi=r,
                       rough=0.35, sheen=0.5, coat=0.3, sss=0.2))
    return b


def dish_crepes():
    parts = [bistro_plate("CrepePlate", 1.3)]
    mat = crepe_mat("CrepeMat")
    crepes = []
    # веер из трех треугольников, каждый следующий лежит на предыдущих; свободный сектор - под сливки
    for i in range(3):
        c = crepe_obj(f"Crepe{i}", 1.0, math.radians(-170 + 72 * i), 0.1, list(crepes), 0.085, i * 1.7)
        assign(c, mat)
        crepes.append(c)
    parts += crepes
    bpy.context.view_layer.update()

    def height(x, y):
        best = None
        for c in crepes:
            ok, loc, _, _ = c.ray_cast(Vector((x, y, 5.0)), Vector((0, 0, -1)))
            if ok and (best is None or loc.z > best):
                best = loc.z
        return best
    choc = material("CrepeChoc", [(0.0, CHOC_DARK), (1.0, CHOC)], coord="z", lo=0.1, hi=0.3, rough=0.1, coat=0.8)
    segs, cur = [], []
    for k in range(400):
        t = k / 399
        x = -0.95 + 1.9 * t
        y = 0.62 * math.sin(t * math.pi * 7.5) + 0.06 * math.sin(t * 31)
        h = height(x, y)
        if h is None:
            if len(cur) > 3:
                segs.append(cur)
            cur = []
            continue
        cur.append((x, y, h + 0.014))
    if len(cur) > 3:
        segs.append(cur)
    lines = [tube(f"CrepeDrizzle{i}", sg, 0.026) for i, sg in enumerate(segs)]
    if lines:
        dr = join(lines, "CrepeDrizzle")
        assign(dr, choc)
        parts.append(dr)
    # шапка сливок в центре и черника вокруг
    ca = math.radians(110)
    cm = cream_mound("CrepeCream", 0.26, 0.13, 0.1, 5, peaks=[(0.0, 0.0, 0.17, 0.11, 0.03, -0.02)], folds=6)
    cm.location = (0.55 * math.cos(ca), 0.55 * math.sin(ca), 0.0)
    assign(cm, material("CrepeCreamMat", [(0.0, CREAM_LO), (1.0, CREAM_HI)], coord="nz", lo=-0.2, hi=1, rough=0.35,
                        sss=0.5, sss_radius=(1, 0.9, 0.75)))
    parts.append(cm)
    for i, (rr, da) in enumerate(((0.62, -38), (0.84, -16), (0.86, 18), (0.64, 40), (0.3, 4))):
        a = ca + math.radians(da)
        x, y = rr * math.cos(a), rr * math.sin(a)
        h = height(x, y) or 0.1
        bb = blueberry(f"CrepeBerry{i}")
        bb.location = (x, y, h + 0.066)
        parts.append(bb)
    return parts


def truffle_cup(name, mat):
    c = lathe(name, [(0.0, 0.0), (0.16, 0.0), (0.18, 0.01), (0.25, 0.14), (0.235, 0.145), (0.165, 0.02), (0.0, 0.016)], 96)
    deform(c, lambda co: Vector((co.x * lobed(22, 0.08, 0.6)(math.atan2(co.y, co.x)),
                                 co.y * lobed(22, 0.08, 0.6)(math.atan2(co.y, co.x)), co.z)))
    smooth(c, 70)
    assign(c, mat)
    return c


def zigzag_on_ball(name, r, n=6, amp=0.7, z0=0.0, rad=0.013):
    pts = []
    for k in range(121):
        t = k / 120
        x = (-0.75 + 1.5 * t) * r
        y = amp * r * math.sin(t * math.pi * n) * math.sqrt(max(0.0, 1 - (x / r) ** 2))
        z = math.sqrt(max(0.0, r * r - x * x - y * y)) + rad * 0.4
        pts.append((x, y, z + z0))
    return tube(name, pts, rad)


def dish_truffles():
    prof = [(0.0, 0.0), (0.985, 0.0), (1.0, 0.015), (1.0, 0.27), (0.99, 0.28), (0.965, 0.28), (0.955, 0.27),
            (0.955, 0.06), (0.94, 0.05), (0.0, 0.05)]
    box = rr_lathe("TrufBox", prof, 1.0, 0.7, 8.0, 192)
    bevel(box, 0.01, 2, 30)
    smooth(box, 45)
    pink = material("TrufBoxMat", [(0.0, (0.86, 0.42, 0.54)), (1.0, (0.98, 0.66, 0.74))], coord="z", lo=0.0, hi=0.28,
                    rough=0.3, coat=0.5, coat_rough=0.1)
    gold = material("TrufGold", [(0.0, (0.86, 0.60, 0.20)), (1.0, (1.0, 0.86, 0.46))], coord="z", lo=0.2, hi=0.3,
                    rough=0.22, metal=0.85, coat=0.3)
    liner = material("TrufLiner", [(0.0, (0.42, 0.20, 0.12)), (1.0, (0.52, 0.28, 0.16))], coord="x", lo=-1, hi=1,
                     rough=0.5, coat=0.2)
    assign_faces(box, pink, [(lambda n, c: c.z > 0.255, gold), (lambda n, c: n.z > 0.9 and 0.04 < c.z < 0.06, liner)])
    parts = [box]
    cup_mat = material("TrufCup", [(0.0, (0.78, 0.52, 0.18)), (1.0, (1.0, 0.82, 0.42))], coord="z", lo=0.0, hi=0.15,
                       rough=0.28, metal=0.85, bump=0.3, bump_scale=30)
    dark = material("TrufDark", [(0.0, (0.20, 0.09, 0.04)), (1.0, (0.40, 0.21, 0.10))], coord="z", lo=-0.2, hi=0.2,
                    rough=0.15, coat=0.8, coat_rough=0.05, sss=0.1)
    cocoa = material("TrufCocoa", [(0.0, (0.30, 0.16, 0.08)), (1.0, (0.50, 0.30, 0.17))], coord="z", lo=-0.2, hi=0.2,
                     rough=0.9, bump=0.7, bump_scale=70, bump_detail=8, vary=0.15, vary_scale=12)
    add_speckles(cocoa, (0.58, 0.38, 0.24), scale=50, threshold=0.62, strength=0.7)
    ivory = material("TrufIvory", [(0.0, (0.92, 0.84, 0.68)), (1.0, (1.0, 0.96, 0.86))], coord="z", lo=-0.2, hi=0.2,
                     rough=0.18, coat=0.7, sss=0.4, sss_radius=(1, 0.9, 0.7))
    milk = material("TrufMilk", [(0.0, (0.46, 0.25, 0.12)), (1.0, (0.66, 0.42, 0.24))], coord="z", lo=-0.2, hi=0.2,
                    rough=0.18, coat=0.8, coat_rough=0.05)
    white_line = material("TrufWhiteLine", [(0.0, (0.98, 0.95, 0.88)), (1.0, (1.0, 1.0, 0.97))], coord="z", lo=0, hi=0.3,
                          rough=0.2, coat=0.6, sss=0.3)
    dark_line = material("TrufDarkLine", [(0.0, CHOC_DARK), (1.0, CHOC)], coord="z", lo=0, hi=0.3, rough=0.15, coat=0.7)
    pist = material("TrufPist", [(0.0, (0.42, 0.62, 0.20)), (1.0, (0.70, 0.86, 0.40))], coord="z", lo=-0.05, hi=0.05,
                    rough=0.4, sss=0.3, coat=0.3)
    spr_mats = [flat(f"TrufSpr{i}", c, rough=0.25, coat=0.6) for i, c in
                enumerate(((1.0, 0.56, 0.70), (1.0, 0.96, 0.92), (0.98, 0.78, 0.30)))]
    r = 0.19
    kinds = ["cocoa", "drizzle_white", "pistachio", "ivory", "sprinkles", "milk"]
    for idx, kind in enumerate(kinds):
        col, row = idx % 3, idx // 3
        x, y = (col - 1) * 0.58, (0.5 - row) * 0.6
        cup = truffle_cup(f"TrufCup{idx}", cup_mat)
        ball = sphere(f"Truffle{idx}", r, 64, 40)
        push_normals(ball, lambda co, n, idx=idx: 0.012 * M.fbm(co * 7 + Vector((idx, 0, 0))))
        deform(ball, lambda co: Vector((co.x, co.y, co.z * 0.94)))
        smooth(ball)
        group = [ball]
        mat = {"cocoa": cocoa, "drizzle_white": dark, "pistachio": dark, "ivory": ivory, "sprinkles": dark,
               "milk": milk}[kind]
        assign(ball, mat)
        if kind == "drizzle_white":
            z = zigzag_on_ball(f"TrufLine{idx}", r * 0.94, 5, 0.75)
            assign(smooth(z), white_line)
            group.append(z)
        elif kind in ("ivory", "milk"):
            z = zigzag_on_ball(f"TrufLine{idx}", r * 0.94, 6, 0.7, rad=0.011)
            rotate_all([z], (0, 0, math.radians(90)))
            assign(smooth(z), dark_line if kind == "ivory" else white_line)
            group.append(z)
        elif kind in ("pistachio", "sprinkles"):
            bits = []

            def make(i, rnd, kind=kind):
                if kind == "pistachio":
                    b = sphere(f"TrufBit{idx}_{i}", 1.0, 10, 6)
                    b.scale = (rnd.uniform(0.022, 0.034), rnd.uniform(0.018, 0.028), 0.014)
                    assign(b, pist)
                else:
                    b = capsule(f"TrufBit{idx}_{i}", 0.07, 0.014, 10, 8)
                    assign(b, spr_mats[rnd.randrange(3)])
                bits.append(b)
                return b
            scatter_on(ball, 30, make, seed=idx, area=r * 0.92, spacing=0.035)
            group.append(join(bits, f"TrufBits{idx}"))
        for o in group:
            o.location += Vector((x, y, 0.05 + 0.02 + r * 0.92))
        cup.location = (x, y, 0.05)
        parts += [cup] + group
    return rotate_all(parts, (0, 0, math.radians(-18)))


M.MODELS.update({
    "butter": butter,
    "chocolate": chocolate,
    "strawberry": strawberry,
    "cream": cream,
    "sugar": sugar,
    "macaron": macaron,
    "madeleine": madeleine,
    "brioche": brioche,
    "canele": canele,
    "meringue": meringue,
    "cafe_creme": cafe_creme,
    "millefeuille": millefeuille,
    "dish_croissant": dish_croissant,
    "dish_pain_chocolat": dish_pain_chocolat,
    "dish_eclair": dish_eclair,
    "dish_tart": dish_tart,
    "dish_crepes": dish_crepes,
    "dish_truffles": dish_truffles,
})
