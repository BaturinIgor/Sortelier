"""Модели продуктов сезонных ивентов: Хэллоуин, Новый год, Неделя сладостей, Летний гриль, Осенний урожай.

Подключается из models.py (EXTENSIONS), функции добавляются в M.MODELS.
"""
import bisect as _bisect
import math
import random

import bpy
from mathutils import Matrix, Vector

import models as M
from models import *  # noqa: F401,F403  помощники


# MARK: - Помощники

def move(objs, d):
    for o in objs:
        o.location = o.location + Vector(d)
    bpy.context.view_layer.update()
    return objs


def set_attr(ob, name, fn):
    """Числовой атрибут на вершинах fn(co, normal); в материале читается через mix_attr."""
    me = ob.data
    me.update()
    vals = [float(fn(v.co.copy(), v.normal.copy())) for v in me.vertices]
    a = me.attributes.get(name) or me.attributes.new(name, "FLOAT", "POINT")
    a.data.foreach_set("value", vals)
    return ob


def mix_attr(mat, name, color, lo=0.0, hi=1.0):
    """Подмешивает цвет по атрибуту вершин (бороздки, подпалины, румянец)."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    at = nodes.new("ShaderNodeAttribute")
    at.attribute_name = name
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = lo
    mr.inputs["From Max"].default_value = hi
    links.new(at.outputs["Fac"], mr.inputs["Value"])
    M._mix_over(mat, mr.outputs["Result"], color)
    return mat


def _ramp(nodes, stops, interp="LINEAR"):
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = interp
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*lin(stops[0][1]), 1)
    els[1].position, els[1].color = stops[-1][0], (*lin(stops[-1][1]), 1)
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = (*lin(col), 1)
    return ramp


def uv_pattern(mat, stops, fu=1.0, fv=0.0):
    """Цвет по фазе fract(u * fu + v * fv) из UV трубки: спиральные полоски вдоль длины."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["UV"], sep.inputs[0])
    mv = nodes.new("ShaderNodeMath")
    mv.operation = "MULTIPLY"
    mv.inputs[1].default_value = fv
    links.new(sep.outputs["Y"], mv.inputs[0])
    mu = nodes.new("ShaderNodeMath")
    mu.operation = "MULTIPLY_ADD"
    mu.inputs[1].default_value = fu
    links.new(sep.outputs["X"], mu.inputs[0])
    links.new(mv.outputs[0], mu.inputs[2])
    fr = nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    links.new(mu.outputs[0], fr.inputs[0])
    ramp = _ramp(nodes, stops)
    links.new(fr.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def sweep(name, pts, radius, segs=32, step=0.02, caps=True, section=(1.0, 1.0), up=(0.0, 0.0, 1.0), power=2.0):
    """Трубка по ломаной с плавной рамкой, круглыми торцами и UV: u - длина пути, v - доля обхода.

    radius - число или fn(t) для t 0..1 вдоль пути; section - сплющивание сечения (ленты).
    """
    P = [Vector(p) for p in pts]
    cum = [0.0]
    for a, b in zip(P, P[1:]):
        cum.append(cum[-1] + (b - a).length)
    L = cum[-1]
    rf = radius if callable(radius) else (lambda t, r=radius: r)

    def at(s):
        s = min(max(s, 0.0), L)
        i = min(max(_bisect.bisect_right(cum, s) - 1, 0), len(P) - 2)
        seg = cum[i + 1] - cum[i]
        return P[i].lerp(P[i + 1], (s - cum[i]) / seg if seg > 0 else 0.0)

    def tangent(s):
        e = min(step * 0.5, L * 0.01)
        t = at(min(L, s + e)) - at(max(0.0, s - e))
        return t.normalized() if t.length > 1e-9 else Vector((1, 0, 0))

    rings = []  # (центр, касательная, радиус, u)
    nc = 7
    t0, t1 = tangent(0.0), tangent(L)
    r0, r1 = rf(0.0), rf(1.0)
    if caps:
        for k in range(1, nc):
            ph = math.pi / 2 * k / nc
            rings.append((P[0] - t0 * r0 * math.cos(ph), t0, r0 * math.sin(ph), -r0 * math.cos(ph)))
    n = max(2, int(L / step) + 1)
    for i in range(n):
        s = L * i / (n - 1)
        rings.append((at(s), tangent(s), rf(s / L), s))
    if caps:
        for k in range(nc - 1, 0, -1):
            ph = math.pi / 2 * k / nc
            rings.append((at(L) + t1 * r1 * math.cos(ph), t1, r1 * math.sin(ph), L + r1 * math.cos(ph)))
    upv = Vector(up)
    nrm = upv - t0 * upv.dot(t0)
    if nrm.length < 1e-4:
        nrm = t0.orthogonal()
    nrm.normalize()
    verts, faces, uvs = [], [], []
    prev_t = rings[0][1]
    frames = []
    for c, t, r, u in rings:
        q = prev_t.rotation_difference(t)
        nrm = q @ nrm
        nrm = (nrm - t * nrm.dot(t)).normalized()
        prev_t = t
        frames.append((c, t, nrm, t.cross(nrm), r, u))
    sx, sy = section
    e = 2.0 / power  # power > 2 - сечение ближе к скругленному прямоугольнику

    def sp(v):
        return math.copysign(abs(v) ** e, v)
    for c, t, nv, bv, r, u in frames:
        for j in range(segs):
            th = 2 * math.pi * j / segs
            verts.append(c + (nv * sp(math.cos(th)) * sx + bv * sp(math.sin(th)) * sy) * r)
    m = len(frames)
    for i in range(m - 1):
        for j in range(segs):
            jn = (j + 1) % segs
            faces.append((i * segs + j, i * segs + jn, (i + 1) * segs + jn, (i + 1) * segs + j))
            ua, ub = frames[i][5], frames[i + 1][5]
            uvs.append([(ua, j / segs), (ua, (j + 1) / segs), (ub, (j + 1) / segs), (ub, j / segs)])
    if caps:
        a = len(verts)
        verts.append(P[0] - t0 * r0)
        b = len(verts)
        verts.append(at(L) + t1 * r1)
        for j in range(segs):
            jn = (j + 1) % segs
            faces.append((a, jn, j))
            uvs.append([(-r0, 0.5), (frames[0][5], (j + 1) / segs), (frames[0][5], j / segs)])
            last = (m - 1) * segs
            faces.append((b, last + j, last + jn))
            uvs.append([(L + r1, 0.5), (frames[-1][5], j / segs), (frames[-1][5], (j + 1) / segs)])
    ob = from_data(name, verts, faces)
    uv = ob.data.uv_layers.new(name="UVMap")
    for p, fuv in zip(ob.data.polygons, uvs):
        for li, val in zip(p.loop_indices, fuv):
            uv.data[li].uv = val
    return smooth(ob)


def settle(objs, frames=90, passive=(), floor=0.0, friction=0.9, margin=0.002, wall=None, hull_passive=(),
           shape="CONVEX_HULL"):
    """Роняет объекты физикой твердых тел: куча ложится естественно и без пересечений."""
    scene = bpy.context.scene
    bpy.context.view_layer.update()
    bpy.ops.rigidbody.world_add()
    rbw = scene.rigidbody_world
    rbw.point_cache.frame_start = 1
    rbw.point_cache.frame_end = frames
    rbw.substeps_per_frame = 20
    rbw.solver_iterations = 30
    extra = []
    passive = list(passive)
    if floor is not None:
        fl = box_mesh("RBFloor", 30, 30, 1.0, floor - 1.0)
        extra.append(fl)
        passive.append(fl)
    if wall:
        # временная стенка собирает кучку в горку
        w = lathe("RBWall", [(wall, -0.5), (wall + 0.3, -0.5), (wall + 0.3, 6.0), (wall, 6.0), (wall, -0.5)], 48)
        extra.append(w)
        passive.append(w)
    for o in list(objs) + passive:
        for s in scene.objects:
            s.select_set(False)
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        act = o in objs
        bpy.ops.rigidbody.object_add(type="ACTIVE" if act else "PASSIVE")
        rb = o.rigid_body
        rb.collision_shape = shape if act else ("CONVEX_HULL" if o in hull_passive else "MESH")
        rb.friction = friction
        rb.restitution = 0.0
        rb.linear_damping = 0.5
        rb.angular_damping = 0.7
        rb.use_margin = True
        rb.collision_margin = margin
    for f in range(1, frames + 1):
        scene.frame_set(f)
    mats = [o.matrix_world.copy() for o in objs]
    bpy.ops.rigidbody.world_remove()
    for o, m in zip(objs, mats):
        o.matrix_world = m
    for o in extra:
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()
    return objs


def spline(pts, n=8):
    """Плавная кривая Катмулла-Рома через точки."""
    P = [Vector(p) for p in pts]
    P = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t * t * t))
    out.append(P[-2])
    return [tuple(v) for v in out]


def see_through(mat, opacity=0.7):
    """Полупрозрачность: часть света проходит насквозь (напитки, видно дольки внутри)."""
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    out = nodes["Material Output"]
    tr = nodes.new("ShaderNodeBsdfTransparent")
    mix = nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = opacity
    links.new(tr.outputs[0], mix.inputs[1])
    links.new(bsdf.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def outline_offset(pts, d):
    """Сдвиг замкнутого контура внутрь на d (контур против часовой)."""
    n = len(pts)
    out = []
    for i in range(n):
        p0, p1, p2 = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % n])
        e1 = (p1 - p0).normalized()
        e2 = (p2 - p1).normalized()
        n1 = Vector((-e1.y, e1.x))
        n2 = Vector((-e2.y, e2.x))
        nn = (n1 + n2)
        nn = nn.normalized() if nn.length > 1e-6 else n1
        out.append((p1.x + nn.x * d, p1.y + nn.y * d))
    return out


def hull(points):
    """Выпуклая оболочка точек на плоскости (против часовой)."""
    pts = sorted(set(points))

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return lower[:-1] + upper[:-1]


def circles_hull(circles, n=24):
    pts = []
    for cx, cy, r in circles:
        for i in range(n):
            a = 2 * math.pi * i / n
            pts.append((round(cx + r * math.cos(a), 6), round(cy + r * math.sin(a), 6)))
    return hull(pts)


def leaf(name, length=1.0, width=0.45, fold=0.08, curl=0.12, thick=0.03, stops=None, petiole=0.12, serr=0.0):
    """Лист: черешок в начале координат, кончик по +X, складка по прожилке, кончик загнут вверх."""
    ob = polar_disc(name, 18, 96, 0.5, 0.5)

    def w_of(u):
        return 0.5 * width * math.sin(math.pi * min(1.0, u) ** 0.85) ** 0.8

    def z_of(u, yn):
        return fold * width * (yn * yn + 0.004) ** 0.6 + curl * length * (u - 0.35) ** 2

    def shape(co):
        u = (co.x / 0.5 + 1) / 2
        ymax = math.sqrt(max(1e-6, 0.25 - co.x * co.x))
        yn = max(-1.0, min(1.0, co.y / ymax))
        w = w_of(u) * (1.0 + serr * math.sin(u * 40) * abs(yn) ** 4)
        return Vector((u * length, yn * w, z_of(u, yn)))
    deform(ob, shape)
    solidify(ob, thick)
    subdivide(ob, 1)
    smooth(ob)
    stops = stops or [(0.0, (0.20, 0.52, 0.14)), (0.6, (0.32, 0.68, 0.20)), (1.0, (0.46, 0.78, 0.26))]
    mat = material(f"{name}Mat", stops, coord="x", lo=0.0, hi=length, rough=0.28, sss=0.3,
                   sss_radius=(0.5, 1.0, 0.3), coat=0.5, coat_rough=0.1, vary=0.06)
    assign(ob, mat)
    parts = [ob]
    rib_mat = material(f"{name}RibMat", [(0.0, tuple(min(1.0, c * 1.25 + 0.05) for c in stops[0][1])),
                                         (1.0, tuple(min(1.0, c * 1.15 + 0.08) for c in stops[-1][1]))],
                       coord="x", lo=0.0, hi=length, rough=0.3, coat=0.4)
    pts = [(-petiole + (length * 0.85 + petiole) * k / 24, 0.0, 0.0) for k in range(25)]
    pts = [(x, 0.0, (z_of(x / length, 0.0) if x > 0 else z_of(0.0, 0.0)) + thick * 0.5) for x, _, _ in pts]
    rib = sweep(f"{name}Rib", pts, lambda t: 0.022 * length * (1.3 - t), segs=12, step=0.02)
    assign(rib, rib_mat)
    parts.append(rib)
    return parts


def wood_mat(name, light=(0.96, 0.86, 0.66), dark=(0.84, 0.68, 0.46), coord="x", lo=-1.0, hi=1.0):
    return material(name, [(0.0, dark), (1.0, light)], coord=coord, lo=lo, hi=hi, rough=0.45, coat=0.2,
                    bump=0.08, bump_scale=6, vary=0.1, vary_scale=8)


def glass_mat(name, tint=(0.94, 0.97, 1.0), center=0.06, edge=0.7):
    """Стекло как у игрушки: прозрачная середина и блестящие края, свет проходит внутрь (без темных теней)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    for nd in list(nodes):
        if nd.type != "OUTPUT_MATERIAL":
            nodes.remove(nd)
    out = nodes["Material Output"]
    tr = nodes.new("ShaderNodeBsdfTransparent")
    tr.inputs["Color"].default_value = (*lin(tint), 1)
    gl = nodes.new("ShaderNodeBsdfGlossy")
    gl.inputs["Color"].default_value = (1, 1, 1, 1)
    gl.inputs["Roughness"].default_value = 0.04
    lw = nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.3
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["To Min"].default_value = center
    mr.inputs["To Max"].default_value = edge
    links.new(lw.outputs["Facing"], mr.inputs["Value"])
    mix = nodes.new("ShaderNodeMixShader")
    links.new(mr.outputs["Result"], mix.inputs["Fac"])
    links.new(tr.outputs[0], mix.inputs[1])
    links.new(gl.outputs[0], mix.inputs[2])
    links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def cinnamon_stick(name, length=1.2, r=0.09):
    """Палочка корицы: свернутая трубочкой кора, видна спираль на торцах."""
    pts_o, pts_i = [], []
    turns = 1.6
    th = 0.32 * r
    for k in range(60):
        t = k / 59
        a = 2 * math.pi * turns * t
        rr = r * (1.0 - 0.42 * t)
        pts_o.append((rr * math.cos(a), rr * math.sin(a)))
        pts_i.append(((rr - th) * math.cos(a), (rr - th) * math.sin(a)))
    outline = pts_o + list(reversed(pts_i))
    ob = profile_prism(name, outline, length, -length / 2)
    ob.rotation_euler = (0, math.radians(90), 0)
    apply_transform(ob)
    bevel(ob, th * 0.3, 2, 30)
    smooth(ob, 35)
    mat = material(f"{name}Mat", [(0.0, (0.46, 0.22, 0.10)), (0.5, (0.62, 0.32, 0.14)), (1.0, (0.70, 0.40, 0.18))],
                   coord="nz", lo=-1, hi=1, rough=0.55, coat=0.15, bump=0.35, bump_scale=30, bump_detail=6,
                   vary=0.15, vary_scale=12)
    assign(ob, mat)
    return ob


# MARK: - Хэллоуин

PUMPKIN_STOPS = [(0.0, (0.84, 0.32, 0.03)), (0.45, (0.98, 0.50, 0.07)), (0.8, (1.0, 0.60, 0.13)),
                 (1.0, (1.0, 0.64, 0.18))]


def pumpkin_body(name="Pumpkin", r=1.0, h=0.70, ribs=10):
    ob = sphere(name, 1.0, 160, 72)

    def rib_x(a):
        u = (a * ribs / (2 * math.pi)) % 1.0
        return 2 * u - 1

    def shape(co):
        rr = math.hypot(co.x, co.y)
        a = math.atan2(co.y, co.x)
        x = rib_x(a)
        k = 0.90 + 0.10 * max(0.0, 1 - x * x) ** 0.35
        z = co.z * h
        z -= 0.24 * math.exp(-(rr / 0.30) ** 2) * (co.z > 0)
        z += 0.12 * math.exp(-(rr / 0.26) ** 2) * (co.z < 0)
        return Vector((co.x * k * r, co.y * k * r, z * r))
    deform(ob, shape)
    smooth(ob)

    def groove(co, n):
        a = math.atan2(co.y, co.x)
        x = rib_x(a)
        return (1 - max(0.0, 1 - x * x) ** 0.35) * min(1.0, math.hypot(co.x, co.y) / (0.5 * r))
    set_attr(ob, "groove", groove)
    mat = material(f"{name}Mat", PUMPKIN_STOPS, coord="z", lo=-h * r, hi=h * r * 0.8, rough=0.32, sss=0.25,
                   sss_radius=(1.0, 0.45, 0.15), coat=0.55, coat_rough=0.12, vary=0.06, bump=0.03, bump_scale=10)
    mix_attr(mat, "groove", (0.72, 0.24, 0.02), 0.0, 0.55)
    assign(ob, mat)
    return ob


def pumpkin_stem(name, base_z, height=0.5, r=0.15, lean=0.32):
    st = lathe(name, [(0.0, 0.0), (r * 1.25, 0.0), (r * 1.1, 0.06), (r * 0.78, 0.2), (r * 0.7, height * 0.86),
                      (r * 0.74, height * 0.97), (r * 0.5, height), (0.0, height)], 48)

    def ridges(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.13 * math.cos(6 * a)
        t = co.z / height
        return Vector((co.x * k + lean * t * t, co.y * k, co.z - 0.08 * lean * t * t))
    deform(st, ridges)
    subdivide(st, 1)
    smooth(st)
    assign(st, material(f"{name}Mat", [(0.0, (0.36, 0.46, 0.14)), (0.5, (0.48, 0.42, 0.18)),
                                       (0.88, (0.52, 0.38, 0.18)), (1.0, (0.82, 0.72, 0.48))],
                        coord="z", lo=0.0, hi=height, rough=0.5, coat=0.2, bump=0.25, bump_scale=18, vary=0.1))
    st.location = (0, 0, base_z - 0.03)
    return st


def pumpkin_top_z(x, y, h=0.70):
    """Высота верха тыквы над точкой (по гребню ребра)."""
    r = min(0.995, math.hypot(x, y))
    return math.sqrt(1 - r * r) * h - 0.24 * math.exp(-(r / 0.30) ** 2)


def drape(objs, zfn, lift=0.02):
    """Кладет плоские детали (лист) на поверхность: z += высота поверхности под вершиной."""
    for o in objs:
        apply_transform(o)
        deform(o, lambda co: Vector((co.x, co.y, co.z + zfn(co.x, co.y) + lift)))
    return objs


def pumpkin():
    body = pumpkin_body()
    top = 0.70 - 0.24
    stem = pumpkin_stem("PStem", top, 0.48, 0.15, 0.30)
    parts = [body, stem]
    # завиток усика: пружинка по поверхности от хвостика вправо назад
    ang = math.radians(35)
    d = Vector((math.cos(ang), math.sin(ang), 0))
    side = Vector((-d.y, d.x, 0))
    pts = []
    for k in range(140):
        t = k / 139
        a = 6.0 * math.pi * t
        rad = 0.055 * (1 - 0.4 * t)
        c = d * (0.17 + 0.42 * t)
        p = c + side * rad * math.cos(a)
        pts.append((p.x, p.y, pumpkin_top_z(c.x, c.y) + 0.035 + rad * (1 + math.sin(a))))
    tendril = sweep("Tendril", pts, lambda t: 0.02 * (1 - 0.5 * t), segs=10, step=0.008)
    assign(tendril, material("TendrilMat", [(0.0, (0.30, 0.52, 0.14)), (1.0, (0.50, 0.70, 0.22))], coord="z",
                             lo=0.3, hi=0.7, rough=0.35, coat=0.4))
    parts.append(tendril)
    lf = leaf("PLeaf", 0.78, 0.52, fold=0.10, curl=0.10, serr=0.04)
    rotate_all(lf, (0, 0, math.radians(200)))
    move(lf, (0.14 * math.cos(math.radians(200)), 0.14 * math.sin(math.radians(200)), 0))
    drape(lf, pumpkin_top_z, 0.025)
    parts += lf
    return rotate_all(parts, (math.radians(8), 0, math.radians(10)))


def dish_pumpkin_soup():
    parts = [plate("SoupPlate", 1.34, ((0.95, 0.93, 0.90), (1.0, 0.99, 0.97)))]
    dz = 0.1  # дно миски на тарелке
    bowl = lathe("SoupBowl", [(0.0, 0.0), (0.42, 0.0), (0.47, 0.04), (0.52, 0.1), (0.86, 0.42), (1.0, 0.68),
                              (1.02, 0.74), (0.99, 0.77), (0.94, 0.74), (0.88, 0.66), (0.0, 0.62)], 96)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    assign(bowl, material("SoupBowlMat", [(0.0, (0.30, 0.16, 0.42)), (0.75, (0.48, 0.28, 0.62)), (0.86, (0.56, 0.36, 0.70)),
                                          (0.9, (0.99, 0.96, 0.92)), (1.0, (1.0, 1.0, 0.98))],
                          coord="z", lo=0.0, hi=0.77, rough=0.2, coat=0.75, coat_rough=0.06))

    def soup_z(r):
        return 0.67 + 0.08 * math.sqrt(max(0.0, 1 - (r / 0.93) ** 2))
    soup = sphere("Soup", 0.93, 96, 32)
    deform(soup, lambda co: Vector((co.x, co.y, max(co.z, -0.1) * 0.08 + 0.67)))
    push_normals(soup, lambda co, n: 0.006 * fbm(co * 5) if n.z > 0.5 else 0.0)
    smooth(soup)
    assign(soup, material("SoupMat", [(0.0, (1.0, 0.66, 0.20)), (0.6, (0.99, 0.55, 0.10)), (1.0, (0.92, 0.44, 0.06))],
                          coord="r", lo=0.0, hi=0.93, rough=0.14, sss=0.45, sss_radius=(1.0, 0.5, 0.15), coat=0.7,
                          coat_rough=0.06))
    cream = material("CreamSwirl", [(0.0, (0.98, 0.96, 0.92)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.6, hi=0.8,
                     rough=0.18, sss=0.4, coat=0.6)
    pts = []
    for k in range(120):
        t = k / 119
        a = 2 * math.pi * 1.7 * t + 0.6
        rr = 0.05 + 0.46 * t
        x, y = rr * math.cos(a) - 0.04, rr * math.sin(a) + 0.02
        pts.append((x, y, soup_z(math.hypot(x, y)) + 0.006))
    swirl = sweep("Swirl", pts, lambda t: 0.05 * (1.0 - 0.5 * t), segs=16, step=0.01, section=(0.42, 1.0))
    assign(swirl, cream)
    group = [bowl, soup, swirl]
    seed_mat = material("Pepita", [(0.0, (0.34, 0.50, 0.18)), (1.0, (0.56, 0.70, 0.30))], coord="x", lo=-0.08, hi=0.08,
                        rough=0.3, coat=0.5, sss=0.2)
    for i, (x, y, a) in enumerate(((0.62, -0.30, 30), (0.70, -0.06, 80), (0.44, -0.52, -20), (-0.56, 0.42, 50),
                                   (-0.36, 0.62, 110), (0.12, 0.68, 160), (-0.66, -0.22, 10))):
        sd = sphere(f"Pepita{i}", 1.0, 24, 14)
        sd.scale = (0.085, 0.045, 0.022)
        apply_transform(sd)
        deform(sd, lambda co: Vector((co.x, co.y * (1.0 - 1.6 * max(0.0, co.x)), co.z)))
        assign(smooth(sd), seed_mat)
        sd.rotation_euler = (math.radians(6), 0, math.radians(a))
        sd.location = (x, y, soup_z(math.hypot(x, y)) + 0.012)
        group.append(sd)
    # треугольная гренка воткнута в суп сзади справа
    tri = circles_hull([(-0.36, -0.30, 0.09), (0.36, -0.30, 0.09), (0.0, 0.34, 0.09)], 20)
    toast = profile_prism("SoupToast", tri, 0.13, -0.065)
    bevel(toast, 0.04, 4, 30)
    smooth(toast, 40)
    crust = material("SoupToastCrust", [(0.0, (0.70, 0.36, 0.10)), (1.0, (0.86, 0.52, 0.18))], coord="y", lo=-0.4,
                     hi=0.45, rough=0.45, sss=0.15, coat=0.3, bump=0.1, bump_scale=16)
    crumb = material("SoupToastCrumb", [(0.0, (0.98, 0.80, 0.46)), (0.55, (0.96, 0.70, 0.34)), (1.0, (0.84, 0.52, 0.20))],
                     coord="r", lo=0.0, hi=0.42, rough=0.6, sss=0.2, bump=0.45, bump_scale=26, bump_detail=8,
                     vary=0.25, vary_scale=5)
    add_speckles(crumb, (0.74, 0.44, 0.16), scale=26, threshold=0.66, strength=0.6)
    assign_faces(toast, crust, [(lambda n, c: abs(n.z) > 0.92, crumb)])
    toast.rotation_euler = (math.radians(90 - 22), 0, math.radians(-35))
    toast.location = (0.38, 0.30, 0.92)
    group.append(toast)
    move(group, (0, 0, dz))
    parts += group
    return parts


def apple_shape(co, h=0.88, wide=0.10):
    """Яблоко из единичной сферы: шире к верху, ямки у хвостика и снизу."""
    r = math.hypot(co.x, co.y)
    a = math.atan2(co.y, co.x)
    k = (1.0 + wide * co.z - 0.05 * co.z * co.z) * (1 + 0.025 * math.cos(5 * a) * max(0.0, -co.z))
    z = co.z * h
    z -= 0.27 * math.exp(-(r / 0.30) ** 2) * (co.z > 0)
    z += 0.13 * math.exp(-(r / 0.24) ** 2) * (co.z < 0)
    return Vector((co.x * k, co.y * k, z))


def apple_mat(name, deep=(0.70, 0.04, 0.07), mid=(0.90, 0.10, 0.10), light=(0.98, 0.26, 0.16)):
    mat = material(name, [(0.0, deep), (0.45, mid), (0.85, light), (1.0, (0.96, 0.62, 0.28))], coord="z", lo=-0.85,
                   hi=0.78, rough=0.16, sss=0.3, sss_radius=(1.0, 0.25, 0.15), coat=0.8, coat_rough=0.05,
                   vary=0.12, vary_scale=4)
    add_speckles(mat, (1.0, 0.82, 0.56), scale=26, threshold=0.70, strength=0.35)
    return mat


def caramel_apple():
    apple = sphere("CApple", 1.0, 96, 64)
    deform(apple, apple_shape)
    smooth(apple)
    assign(apple, apple_mat("CAppleMat"))
    # карамель: та же форма чуть больше; выше волнистой кромки уходит внутрь яблока
    car = sphere("Caramel", 1.0, 128, 80)

    def thr(a):
        return 0.30 + 0.07 * math.sin(3 * a + 0.8) + 0.05 * math.sin(7 * a + 2.0) - 0.10 * max(0.0, math.sin(5 * a)) ** 6

    def car_shape(co):
        a = math.atan2(co.y, co.x)
        g = smoothstep(thr(a) + 0.04, thr(a) - 0.06, co.z)
        p = apple_shape(co)
        k = 0.975 + 0.05 * g + 0.035 * g * max(0.0, -co.z) ** 2
        return Vector((p.x * k, p.y * k, p.z * (0.99 + 0.02 * g) - 0.02 * g * max(0.0, -co.z) ** 3))
    deform(car, car_shape)
    smooth(car)
    caramel = material("CaramelMat", [(0.0, (0.62, 0.30, 0.06)), (0.5, (0.84, 0.48, 0.12)), (1.0, (0.95, 0.66, 0.26))],
                       coord="z", lo=-0.9, hi=0.45, rough=0.08, sss=0.5, sss_radius=(1.0, 0.5, 0.15), coat=0.9,
                       coat_rough=0.03)
    assign(car, caramel)
    # лужица карамели под яблоком
    foot = sphere("CaramelFoot", 1.0, 96, 24)

    def foot_shape(co):
        a = math.atan2(co.y, co.x)
        k = 0.62 + 0.06 * math.sin(4 * a + 1.0) + 0.04 * math.sin(7 * a)
        return Vector((co.x * k, co.y * k, max(co.z, -0.2) * 0.12 - 0.86 + 0.02))
    deform(foot, foot_shape)
    smooth(foot)
    assign(foot, caramel)
    parts = [apple, car, foot]
    # орешки по нижней половине
    nut = material("NutMat", [(0.0, (0.78, 0.52, 0.26)), (0.6, (0.92, 0.72, 0.44)), (1.0, (0.98, 0.86, 0.62))],
                   coord="z", lo=-0.06, hi=0.06, rough=0.42, coat=0.3, sss=0.2, vary=0.2, vary_scale=40)
    rnd = random.Random(11)
    placed = []
    tries = 0
    while len(placed) < 34 and tries < 3000:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi)
        cz = rnd.uniform(-0.82, 0.12)
        cr = math.sqrt(max(0.0, 1 - cz * cz))
        co = Vector((cr * math.cos(a), cr * math.sin(a), cz))
        if cz > thr(a) - 0.18:
            continue
        p = apple_shape(co) * 1.0
        p = Vector((p.x * 1.025, p.y * 1.025, p.z))
        if any((p - q).length < 0.2 for q in placed):
            continue
        placed.append(p)
        ch = sphere(f"Nut{len(placed)}", 1.0, 12, 8)
        ch.scale = (rnd.uniform(0.07, 0.10), rnd.uniform(0.055, 0.08), rnd.uniform(0.04, 0.06))
        apply_transform(ch)
        push_normals(ch, lambda c, n, s=rnd.random() * 10: 0.016 * fbm(c * 22 + Vector((s, 0, 0))))
        assign(smooth(ch, 40), nut)
        nrm = Vector((co.x, co.y, co.z * 0.7)).normalized()
        q = nrm.to_track_quat("Z", "Y")
        ch.matrix_world = Matrix.Translation(p) @ q.to_matrix().to_4x4() @ Matrix.Rotation(rnd.uniform(0, 6.3), 4, "Z")
        parts.append(ch)
    stick = capsule("CStick", 1.5, 0.065, 24, 16)
    deform(stick, lambda co: Vector((co.x, co.y * 1.0, co.z * 0.8)))
    stick.rotation_euler = (0, math.radians(-90), 0)
    apply_transform(stick)
    stick.location = (0.0, 0.0, 0.95)
    stick.rotation_euler = (math.radians(-6), math.radians(8), 0)
    assign(stick, wood_mat("CStickMat", coord="z", lo=-0.75, hi=0.75))
    parts.append(stick)
    return rotate_all(parts, (0, 0, math.radians(-15)))


def ghost_outline():
    pts = []
    n = 44
    cy, rr = 0.30, 0.62
    for i in range(n + 1):
        a = math.radians(-6 + 192 * i / n)
        pts.append((rr * math.cos(a), cy + rr * math.sin(a)))
    x0, y0 = pts[-1]
    # левый бок с ручкой, вниз с расширением
    for i in range(1, 14):
        t = i / 13
        y = y0 + (-0.56 - y0) * t
        arm = 0.12 * math.exp(-((y - 0.02) / 0.11) ** 2)
        pts.append((x0 - 0.10 * t ** 1.5 - arm, y))
    # низ: три округлых язычка
    xl = pts[-1][0]
    for i in range(1, 48):
        u = i / 48
        x = xl + (-2 * xl) * u
        y = -0.56 - 0.15 * abs(math.sin(3 * math.pi * u)) ** 0.75
        pts.append((x, y))
    xr = -xl
    for i in range(0, 13):
        t = 1 - i / 13
        y = pts[0][1] + (-0.56 - pts[0][1]) * t
        arm = 0.12 * math.exp(-((y - 0.02) / 0.11) ** 2)
        pts.append((pts[0][0] + 0.10 * t ** 1.5 + arm, y))
    return pts


def ghost_cookie():
    outline = ghost_outline()
    th = 0.20
    base = profile_prism("Ghost", outline, th, -th / 2)
    bevel(base, 0.07, 4, 30)
    subdivide(base, 1)
    push_normals(base, lambda co, n: 0.01 * fbm(co * 4))
    smooth(base)
    dough_mat = material("GhostDough", [(0.0, (0.74, 0.44, 0.16)), (0.5, (0.88, 0.60, 0.28)), (1.0, (0.96, 0.74, 0.42))],
                         coord="nz", lo=-1, hi=1, rough=0.5, sss=0.2, coat=0.2, bump=0.2, bump_scale=14, vary=0.15,
                         vary_scale=5)
    assign(base, dough_mat)
    ic_th = 0.07
    icing = profile_prism("GhostIcing", outline_offset(outline, 0.065), ic_th, th / 2 - 0.02)
    bevel(icing, 0.034, 4, 30)
    subdivide(icing, 1)
    smooth(icing)
    assign(icing, material("IcingMat", [(0.0, (0.92, 0.93, 0.97)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=th / 2,
                           hi=th / 2 + ic_th, rough=0.22, sss=0.35, sss_radius=(1, 1, 1), coat=0.6))
    zf = th / 2 - 0.02 + ic_th + 0.005
    parts = [base, icing]
    face = material("GhostFace", [(0.0, (0.10, 0.08, 0.12)), (1.0, (0.22, 0.18, 0.26))], coord="z", lo=zf - 0.02,
                    hi=zf + 0.03, rough=0.15, coat=0.8)
    for i, x in enumerate((-0.2, 0.2)):
        e = sphere(f"GEye{i}", 1.0, 32, 20)
        e.scale = (0.085, 0.115, 0.035)
        e.location = (x, 0.36, zf)
        apply_transform(e)
        assign(smooth(e), face)
        hl = sphere(f"GEyeHi{i}", 0.026, 16, 10)
        hl.scale = (1, 1, 0.5)
        hl.location = (x + 0.03, 0.40, zf + 0.03)
        apply_transform(hl)
        assign(smooth(hl), flat(f"GEyeHiMat{i}", (1.0, 1.0, 1.0), rough=0.2))
        ch = sphere(f"GCheek{i}", 1.0, 24, 12)
        ch.scale = (0.075, 0.045, 0.012)
        ch.location = (x * 1.75, 0.2, zf - 0.004)
        apply_transform(ch)
        assign(smooth(ch), flat(f"GCheekMat{i}", (1.0, 0.62, 0.66), rough=0.4, sss=0.3))
        parts += [e, hl, ch]
    mouth = sphere("GMouth", 1.0, 32, 20)
    mouth.scale = (0.06, 0.075, 0.03)
    mouth.location = (0.0, 0.16, zf)
    apply_transform(mouth)
    assign(smooth(mouth), face)
    parts.append(mouth)
    rotate_all(parts, (math.radians(90), 0, 0))
    return rotate_all(parts, (math.radians(-16), 0, math.radians(-12)))


def candy_corn_piece(name, mat, w=0.80, h=0.98, th=0.34):
    outline = circles_hull([(-w / 2 + 0.14, -h / 2 + 0.14, 0.14), (w / 2 - 0.14, -h / 2 + 0.14, 0.14),
                            (0.0, h / 2 - 0.06, 0.06), (0.0, -h / 2 + 0.03, 0.05)], 28)
    ob = profile_prism(name, outline, th, -th / 2)
    bevel(ob, 0.12, 5, 30)
    subdivide(ob, 1)

    def taper(co):
        # к кончику тоньше: клинышек
        t = (co.y + h / 2) / h
        k = 1.0 - 0.62 * max(0.0, t) ** 1.2
        return Vector((co.x, co.y, co.z * k))
    deform(ob, taper)
    smooth(ob)
    assign(ob, mat)
    return ob


def candy_corn():
    mat = material("CandyCorn", [(0.0, (0.98, 0.68, 0.05)), (0.36, (1.0, 0.80, 0.14)), (0.40, (1.0, 0.48, 0.05)),
                                 (0.65, (1.0, 0.56, 0.10)), (0.69, (1.0, 0.98, 0.94)), (1.0, (1.0, 1.0, 1.0))],
                   coord="y", lo=-0.49, hi=0.49, rough=0.22, sss=0.4, sss_radius=(1.0, 0.7, 0.4), coat=0.6,
                   coat_rough=0.08)
    parts = []
    rnd = random.Random(5)
    th = 0.34
    # нижний ряд: треугольнички валетом, сверху физика роняет еще три
    for i, x in enumerate((-0.75, -0.25, 0.25, 0.75)):
        p = candy_corn_piece(f"Corn{i}", mat, th=th)
        p.location = (x, 0.04 * (-1) ** i, th / 2 + 0.002)
        p.rotation_euler = (0, 0, math.radians(180 * (i % 2) + rnd.uniform(-4, 4)))
        parts.append(p)
    top = []
    for i, (x, y, rz) in enumerate(((-0.30, 0.05, 15), (0.28, -0.02, 160), (0.0, 0.10, -70))):
        p = candy_corn_piece(f"CornTop{i}", mat, th=th)
        p.location = (x, y, 0.7 + 0.5 * i)
        p.rotation_euler = (math.radians(rnd.uniform(-6, 6)), math.radians(rnd.uniform(-6, 6)), math.radians(rz))
        top.append(p)
    settle(top, 90, passive=parts, hull_passive=parts, friction=1.0)
    parts += top
    # кучку наклоняем к камере, чтобы были видны треугольнички
    return rotate_all(parts, (math.radians(34), 0, 0))


# MARK: - Новый год

def merge(name, objs):
    """Склеивает объекты в один меш (для объединения через ремеш)."""
    verts, faces = [], []
    bpy.context.view_layer.update()
    for o in objs:
        mw = o.matrix_world.copy()
        off = len(verts)
        verts += [mw @ v.co for v in o.data.vertices]
        faces += [tuple(off + i for i in p.vertices) for p in o.data.polygons]
        bpy.data.objects.remove(o, do_unlink=True)
    return from_data(name, verts, faces)


def surface_z(ob, x, y, default=0.0):
    """Высота поверхности объекта под точкой (луч сверху вниз)."""
    ok, loc, _, _ = ob.ray_cast(Vector((x, y, 50.0)), Vector((0, 0, -1)))
    return loc.z if ok else default


def slab(name, r, h, length=0.0, p=2.6):
    """Плоская шайба со скругленным краем; length растягивает ее в овал-стадион по X."""
    ob = rounded_disc(name, r, h, p, 24)
    if length:
        deform(ob, lambda co: Vector((co.x + math.copysign(length / 2, co.x), co.y, co.z)))
    return ob


def marshmallow_piece(name, mat, r=0.27, h=0.46):
    ob = rounded_disc(name, r, h, 4.6, 20)
    push_normals(ob, lambda co, n: 0.008 * fbm(co * 6))
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, mat)
    return ob


def marshmallow_mats(prefix):
    white = material(f"{prefix}White", [(0.0, (0.90, 0.89, 0.93)), (1.0, (1.0, 0.99, 0.97))], coord="z", lo=-0.25,
                     hi=0.25, rough=0.5, sss=0.6, sss_radius=(1, 0.9, 0.85), sheen=0.6, coat=0.15)
    pink = material(f"{prefix}Pink", [(0.0, (0.96, 0.62, 0.74)), (1.0, (1.0, 0.80, 0.86))], coord="z", lo=-0.25,
                    hi=0.25, rough=0.5, sss=0.6, sss_radius=(1, 0.7, 0.75), sheen=0.6, coat=0.15)
    for m in (white, pink):
        add_speckles(m, (1.0, 1.0, 1.0), scale=70, threshold=0.66, strength=0.5)
    return white, pink


def marshmallow():
    white, pink = marshmallow_mats("Mallow")
    bowl = lathe("MallowBowl", [(0.0, 0.0), (0.34, 0.0), (0.38, 0.03), (0.70, 0.32), (0.78, 0.46), (0.76, 0.49),
                                (0.71, 0.47), (0.64, 0.40), (0.0, 0.36)], 72)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    assign(bowl, material("MallowBowlMat", [(0.0, (0.36, 0.58, 0.88)), (0.8, (0.52, 0.74, 0.98)), (0.9, (0.98, 0.98, 1.0)),
                                            (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=0.49, rough=0.2, coat=0.75))
    # горка руками: три стоят на дне, одна сверху, две выпали вперед
    h = 0.36
    pieces = []
    for i, (ang, mt, tilt) in enumerate(((90, white, (8, -6)), (210, pink, (-10, 6)), (330, white, (6, 10)))):
        m = marshmallow_piece(f"Mallow{i}", mt, 0.25, h)
        m.rotation_euler = (math.radians(tilt[0]), math.radians(tilt[1]), math.radians(ang))
        m.location = (0.31 * math.cos(math.radians(ang)), 0.31 * math.sin(math.radians(ang)), 0.36 + h / 2 + 0.02)
        pieces.append(m)
    m = marshmallow_piece("MallowTop", pink, 0.25, h)
    m.rotation_euler = (math.radians(12), math.radians(-8), 0.4)
    m.location = (0.0, 0.0, 0.36 + h + h / 2 + 0.11)
    pieces.append(m)
    out = []
    for i, (x, y, rz, mt) in enumerate(((0.62, -0.66, 20, white), (0.02, -0.92, -30, pink))):
        m = marshmallow_piece(f"MallowOut{i}", mt, 0.25, h)
        m.rotation_euler = (math.radians(90), 0, math.radians(rz))
        m.location = (x, y, 0.25)
        out.append(m)
    return [bowl] + pieces + out


def snowflake(name, mat, size=0.3, r_tube=0.024):
    """Снежинка в плоскости XZ (лицом к -Y)."""
    parts = []
    for k in range(6):
        a = math.radians(90 + 60 * k)
        d = Vector((math.cos(a), 0, math.sin(a)))
        arm = sweep(f"{name}Arm{k}", [(0, 0, 0), tuple(d * size)], r_tube, segs=10, step=0.03)
        parts.append(arm)
        for side in (-1, 1):
            b = math.radians(90 + 60 * k + side * 45)
            e = Vector((math.cos(b), 0, math.sin(b)))
            c = d * size * 0.58
            br = sweep(f"{name}Br{k}{side}", [tuple(c), tuple(c + e * size * 0.32)], r_tube * 0.85, segs=10, step=0.03)
            parts.append(br)
    dot = sphere(f"{name}Dot", r_tube * 1.9, 16, 10)
    parts.append(dot)
    ob = merge(name, parts)
    smooth(ob)
    assign(ob, mat)
    return ob


def wrap_on_cylinder(ob, radius_fn, angle):
    """Наносит плоскую деталь (лицом к -Y) на боковину цилиндра под углом angle."""
    def fn(co):
        rz = radius_fn(co.z)
        th = angle + co.x / rz
        rr = rz - co.y
        return Vector((rr * math.sin(th), -rr * math.cos(th), co.z))
    return deform(ob, fn)


def dish_hot_cocoa():
    mug_r = lambda z: 0.585 + 0.025 * min(1.0, max(0.0, (z - 0.1) / 0.8))
    mug = lathe("CocoaMug", [(0.0, 0.0), (0.48, 0.0), (0.54, 0.03), (0.585, 0.1), (0.61, 0.9), (0.612, 1.0),
                             (0.59, 1.04), (0.55, 1.01), (0.54, 0.92), (0.0, 0.9)], 96)
    subdivide(mug, 1)
    smooth(mug, 50)
    red = material("CocoaMugMat", [(0.0, (0.66, 0.06, 0.07)), (0.5, (0.84, 0.12, 0.11)), (0.93, (0.94, 0.20, 0.16)),
                                   (0.95, (0.99, 0.96, 0.92)), (1.0, (1.0, 1.0, 0.98))],
                   coord="z", lo=0.0, hi=1.04, rough=0.18, coat=0.8, coat_rough=0.05)
    assign(mug, red)
    parts = [mug]
    flake_mat = material("FlakeMat", [(0.0, (0.94, 0.95, 0.98)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.2, hi=0.9,
                         rough=0.25, coat=0.6, sss=0.2)
    for i, a in enumerate((-20, 100, 220)):
        fl = snowflake(f"Flake{i}", flake_mat, 0.2, 0.022)
        deform(fl, lambda co: Vector((co.x, co.y, co.z + 0.5)))
        wrap_on_cylinder(fl, lambda z: mug_r(z) + 0.004, math.radians(a))
        parts.append(fl)
    handle = torus("CocoaHandle", 0.24, 0.075, 64, 24)
    handle.rotation_euler = (math.radians(90), 0, 0)
    apply_transform(handle)
    deform(handle, lambda co: Vector((co.x * 0.9, co.y, co.z * 1.15)))
    handle.location = (0.74, 0, 0.52)
    apply_transform(handle)
    assign(smooth(handle), red)
    parts.append(handle)
    cocoa = cylinder("Cocoa", 0.56, 0.04, 96)
    cocoa.location = (0, 0, 0.935)
    apply_transform(cocoa)
    smooth(cocoa, 50)
    assign(cocoa, material("CocoaMat", [(0.0, (0.56, 0.32, 0.18)), (0.7, (0.46, 0.24, 0.12)), (1.0, (0.36, 0.18, 0.08))],
                           coord="r", lo=0.0, hi=0.56, rough=0.12, sss=0.3, coat=0.8, coat_rough=0.05))
    parts.append(cocoa)
    white, pink = marshmallow_mats("Mini")
    rnd = random.Random(7)
    for i, (x, y) in enumerate(((-0.18, -0.22), (0.12, -0.28), (0.30, -0.02), (-0.30, 0.10), (0.05, 0.05),
                                (0.22, 0.28), (-0.10, 0.32))):
        m = rounded_disc(f"MiniMallow{i}", 0.1, 0.15, 3.2, 14)
        subdivide(m, 1)
        smooth(m)
        assign(m, pink if i in (1, 3, 5) else white)
        m.rotation_euler = (math.radians(rnd.uniform(60, 100)), 0, math.radians(rnd.uniform(0, 180)))
        m.location = (x, y, 0.985)
        parts.append(m)
    stick = cinnamon_stick("CocoaCinnamon", 1.15, 0.075)
    stick.rotation_euler = (math.radians(-8), math.radians(-58), math.radians(30))
    stick.location = (-0.18, 0.24, 1.3)
    parts.append(stick)
    return parts


def gingerbread():
    th = 0.24
    shapes = []
    head = slab("GBHead", 0.37, th)
    head.location = (0, 0.80, 0)
    shapes.append(head)
    body = slab("GBBody", 0.42, th, 0.0)
    body.scale = (1.0, 1.18, 1.0)
    body.location = (0, 0.12, 0)
    shapes.append(body)
    limbs = []
    for side in (-1, 1):
        # руки чуть вниз, ноги расставлены
        limbs += [((side * 0.22, 0.42), (side * 0.80, 0.27), 0.165), ((side * 0.15, -0.28), (side * 0.40, -0.84), 0.19)]
    for i, ((x0, y0), (x1, y1), r) in enumerate(limbs):
        ln = math.hypot(x1 - x0, y1 - y0)
        sl = slab(f"GBLimb{i}", r, th, ln)
        sl.rotation_euler = (0, 0, math.atan2(y1 - y0, x1 - x0))
        sl.location = ((x0 + x1) / 2, (y0 + y1) / 2, 0)
        shapes.append(sl)
    cookie = merge("Gingerbread", shapes)
    modify(cookie, "REMESH", mode="VOXEL", voxel_size=0.014)
    bake(cookie)
    modify(cookie, "SMOOTH", factor=0.8, iterations=12)
    bake(cookie)
    push_normals(cookie, lambda co, n: 0.008 * fbm(co * 5))
    smooth(cookie)
    gmat = material("GingerMat", [(0.0, (0.52, 0.24, 0.08)), (0.45, (0.70, 0.38, 0.14)), (1.0, (0.80, 0.48, 0.20))],
                    coord="nz", lo=-1, hi=1, rough=0.45, sss=0.2, sss_radius=(1, 0.5, 0.25), coat=0.3, bump=0.18,
                    bump_scale=16, vary=0.12, vary_scale=5)
    add_speckles(gmat, (0.42, 0.18, 0.06), scale=34, threshold=0.68, strength=0.5)
    assign(cookie, gmat)
    parts = [cookie]
    icing = material("GBIcing", [(0.0, (0.95, 0.95, 0.98)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=0.2,
                     rough=0.22, sss=0.35, coat=0.6)

    def line(name, pts2, r=0.032):
        pts = [(x, y, surface_z(cookie, x, y, th / 2) + r * 0.25) for x, y in pts2]
        tb = sweep(name, pts, r, segs=12, step=0.01)
        assign(tb, icing)
        parts.append(tb)
    # улыбка
    line("GBSmile", [(0.16 * math.cos(a), 0.72 + 0.10 * math.sin(a)) for a in
                     [math.radians(200 + 140 * k / 16) for k in range(17)]], 0.028)
    # зигзаги у кистей и стоп поперек руки/ноги
    for i, ((x0, y0), (x1, y1), r) in enumerate(limbs):
        d = Vector((x1 - x0, y1 - y0)).normalized()
        perp = Vector((-d.y, d.x))
        c = Vector((x1, y1)) - d * r * 0.55
        pts = []
        for k in range(25):
            t = k / 24
            p2 = c + perp * (-0.85 * r + 1.7 * r * t) + d * (0.04 * math.sin(t * math.pi * 4))
            pts.append((p2.x, p2.y))
        line(f"GBZig{i}", pts, 0.028)
    eye_mat = material("GBEye", [(0.0, (0.12, 0.06, 0.04)), (1.0, (0.26, 0.14, 0.08))], coord="z", lo=0.0, hi=0.2,
                       rough=0.15, coat=0.8)
    for i, x in enumerate((-0.13, 0.13)):
        e = sphere(f"GBEye{i}", 1.0, 24, 16)
        e.scale = (0.055, 0.065, 0.03)
        e.location = (x, 0.88, surface_z(cookie, x, 0.88, th / 2))
        assign(smooth(e), eye_mat)
        ch = sphere(f"GBCheek{i}", 1.0, 20, 12)
        ch.scale = (0.055, 0.04, 0.012)
        ch.location = (x * 1.9, 0.74, surface_z(cookie, x * 1.9, 0.74, th / 2))
        assign(smooth(ch), flat(f"GBCheekMat{i}", (1.0, 0.56, 0.58), rough=0.4, sss=0.3))
        parts += [e, ch]
    for i, (y, col) in enumerate(((0.30, (0.92, 0.10, 0.14)), (0.06, (0.16, 0.66, 0.28)), (-0.18, (0.98, 0.72, 0.10)))):
        b = sphere(f"GBButton{i}", 1.0, 32, 20)
        b.scale = (0.085, 0.085, 0.045)
        b.location = (0.0, y, surface_z(cookie, 0.0, y, th / 2) + 0.01)
        assign(smooth(b), material(f"GBButtonMat{i}", [(0.0, tuple(c * 0.8 for c in col)), (1.0, col)], coord="z",
                                   lo=-0.05, hi=0.05, rough=0.12, sss=0.3, coat=0.9, coat_rough=0.04))
        parts.append(b)
    rotate_all(parts, (math.radians(90), 0, 0))
    return rotate_all(parts, (math.radians(-16), 0, math.radians(-10)))


CANE_STOPS = [(0.0, (0.86, 0.06, 0.10)), (0.30, (0.92, 0.10, 0.12)), (0.315, (1.0, 0.99, 0.97)),
              (0.48, (1.0, 1.0, 1.0)), (0.495, (0.90, 0.08, 0.11)), (0.56, (0.90, 0.08, 0.11)),
              (0.575, (1.0, 0.99, 0.97)), (1.0, (0.98, 0.97, 0.95))]


def cane(name, mirror=1, r=0.1, shaft=1.5, hook=0.32):
    pts = [(0.0, 0.0, z) for z in [shaft * k / 20 for k in range(21)]]
    for k in range(1, 41):
        a = math.pi - math.pi * 1.25 * k / 40
        pts.append((mirror * (hook + hook * math.cos(a)), 0.0, shaft + hook * math.sin(a)))
    ob = sweep(name, pts, r, segs=40, step=0.012)
    mat = material(f"{name}Mat", [(0.0, (1, 1, 1)), (1.0, (1, 1, 1))], rough=0.12, sss=0.3, sss_radius=(1, 0.6, 0.6),
                   coat=0.9, coat_rough=0.03)
    uv_pattern(mat, CANE_STOPS, fu=1 / 0.42, fv=mirror * 1.0)
    assign(ob, mat)
    return ob


def ribbon_bow(name, mat, size=1.0):
    parts = []
    for side in (-1, 1):
        pts = []
        for k in range(61):
            t = k / 60
            a = math.pi + 2 * math.pi * t
            x = 0.5 + 0.5 * math.cos(a)
            z = 0.42 * math.sin(a) * (x ** 0.6)
            pts.append((side * x * 0.34 * size, 0.0, (z + 0.12 * x) * 0.34 * size))
        lp = sweep(f"{name}Loop{side}", pts, 0.075 * size, segs=20, step=0.008, caps=False, section=(0.42, 1.0),
                   up=(0.0, 1.0, 0.0))
        assign(lp, mat)
        parts.append(lp)
        tail = sweep(f"{name}Tail{side}", [(0, 0, 0), (side * 0.06 * size, 0, -0.12 * size),
                                           (side * 0.13 * size, 0, -0.26 * size)],
                     lambda t: (0.06 + 0.025 * t) * size, segs=16, step=0.01, section=(0.4, 1.0), up=(0.0, 1.0, 0.0))
        assign(tail, mat)
        parts.append(tail)
    knot = sphere(f"{name}Knot", 1.0, 24, 16)
    knot.scale = (0.09 * size, 0.08 * size, 0.095 * size)
    assign(smooth(knot), mat)
    parts.append(knot)
    return parts


def candy_cane():
    a = cane("CaneA", 1)
    b = cane("CaneB", -1)
    a.rotation_euler = (0, math.radians(20), 0)
    a.location = (-0.40, 0.12, 0.0)
    b.rotation_euler = (0, math.radians(-20), 0)
    b.location = (0.40, -0.12, 0.0)
    bpy.context.view_layer.update()
    bow_mat = material("BowMat", [(0.0, (0.10, 0.48, 0.20)), (1.0, (0.24, 0.70, 0.32))], coord="z", lo=-0.15,
                       hi=0.15, rough=0.25, sss=0.2, coat=0.7, coat_rough=0.06)
    bow = ribbon_bow("Bow", bow_mat, 1.0)
    move(bow, (0.0, -0.26, 1.06))
    return rotate_all([a, b] + bow, (0, 0, math.radians(-8)))


def mandarin_segment(name, mat):
    ob = sphere(name, 1.0, 64, 40)

    def shape(co):
        x = co.x * 0.44
        z = co.z * 0.20
        y = co.y * 0.19 * (0.45 + 0.55 * (co.z + 1) / 2)
        z -= 0.30 * co.x * co.x * 0.44
        return Vector((x, y, z))
    deform(ob, shape)
    push_normals(ob, lambda co, n: 0.004 * math.sin(co.x * 60))
    smooth(ob)
    assign(ob, mat)
    return ob


def mandarin():
    ob = sphere("Mandarin", 0.75, 96, 64)

    def shape(co):
        r = math.hypot(co.x, co.y)
        z = co.z * 0.82
        z -= 0.07 * math.exp(-(r / 0.16) ** 2) * (co.z > 0)
        z += 0.05 * math.exp(-(r / 0.14) ** 2) * (co.z < 0)
        return Vector((co.x, co.y, z))
    deform(ob, shape)
    smooth(ob)
    peel = material("MandarinPeel", [(0.0, (0.94, 0.38, 0.03)), (0.5, (1.0, 0.50, 0.05)), (1.0, (1.0, 0.62, 0.14))],
                    coord="z", lo=-0.6, hi=0.6, rough=0.28, sss=0.3, sss_radius=(1, 0.5, 0.1), coat=0.55,
                    coat_rough=0.12, bump=0.22, bump_scale=48, bump_detail=2, vary=0.05)
    assign(ob, peel)
    top = 0.75 * 0.82 - 0.07
    nub = lathe("MandarinNub", [(0.0, 0.0), (0.07, 0.0), (0.06, 0.04), (0.035, 0.07), (0.0, 0.08)], 24)
    nub.location = (0, 0, top - 0.015)
    assign(smooth(nub), flat("MandarinNubMat", (0.40, 0.42, 0.16), rough=0.5, coat=0.2))
    parts = [ob, nub]
    gstops = [(0.0, (0.10, 0.40, 0.12)), (0.6, (0.20, 0.56, 0.16)), (1.0, (0.32, 0.68, 0.20))]
    for i, (ang, tilt) in enumerate(((140, 18), (200, 28))):
        lf = leaf(f"MLeaf{i}", 0.62 - 0.08 * i, 0.30, fold=0.10, curl=0.25, stops=gstops, petiole=0.05)
        rotate_all(lf, (0, math.radians(-tilt), math.radians(ang)))
        move(lf, (0, 0, top + 0.04))
        parts += lf
    flesh = material("MandarinFlesh", [(0.0, (0.98, 0.46, 0.05)), (0.6, (1.0, 0.56, 0.10)), (1.0, (1.0, 0.68, 0.24))],
                     coord="z", lo=-0.15, hi=0.17, rough=0.18, sss=0.7, sss_radius=(1.0, 0.55, 0.2), coat=0.7,
                     coat_rough=0.06)
    s1 = mandarin_segment("MSeg0", flesh)
    s1.rotation_euler = (math.radians(90), 0, math.radians(-25))
    s1.location = (0.80, -0.60, -0.62 + 0.20)
    s2 = mandarin_segment("MSeg1", flesh)
    s2.rotation_euler = (math.radians(4), 0, math.radians(30))
    s2.location = (0.2, -0.85, -0.62 + 0.08)
    parts += [s1, s2]
    return parts


# MARK: - Неделя сладостей

def scoop_unit(co, seed=0):
    """Форма шарика мороженого (как scoop в models.py) для единичной сферы."""
    a = math.atan2(co.y, co.x)
    if co.z < -0.25:
        k = 1.0 + 0.07 * math.sin(9 * a + seed) + 0.05
        return Vector((co.x * k, co.y * k, -0.25 - (co.z + 0.25) * 0.25))
    return Vector((co.x, co.y, co.z * 0.92))


def shell_cover(name, base, r, thr, mat, inner=0.93, outer=1.04, segs=96, rings=64, seed=0):
    """Глазурь/соус поверх шарика: та же форма, выше порога thr(a) снаружи, ниже уходит внутрь."""
    ob = sphere(name, 1.0, segs, rings)

    def fn(co):
        a = math.atan2(co.y, co.x)
        g = smoothstep(thr(a) - 0.05, thr(a) + 0.05, co.z)
        k = inner + (outer - inner) * g
        p = scoop_unit(co, seed)
        return Vector((p.x * r * k, p.y * r * k, p.z * r * (k if g > 0.5 else min(k, 0.97))))
    deform(ob, fn)
    smooth(ob)
    assign(ob, mat)
    return ob


def piped_swirl(name, mat, r=0.3, h=0.45, ridges=8, twist=5.0):
    """Розочка взбитых сливок: ступенчатый конус с рифлением звездной насадки."""
    prof = [(0.0, 0.0)]
    for k in range(1, 41):
        t = k / 40
        rr = r * (1 - t) ** 0.85 * (0.86 + 0.14 * math.cos(t * math.pi * 6) ** 2)
        prof.append((max(rr, 0.002), h * t))
    prof.append((0.0, h * 1.02))
    ob = lathe(name, prof, 96)

    def star(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.10 * math.cos(ridges * a + twist * co.z / h * 2)
        return Vector((co.x * k, co.y * k, co.z))
    deform(ob, star)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, mat)
    return ob


def strawberry_obj(name, size=1.0, half=False):
    ob = sphere(name, 1.0, 48, 32)

    def shape(co):
        t = (co.z + 1) / 2
        k = 0.35 + 0.65 * t ** 0.6
        return Vector((co.x * k * 0.42 * size, co.y * k * 0.42 * size, co.z * 0.5 * size))
    deform(ob, shape)
    red = material(f"{name}Red", [(0.0, (0.80, 0.06, 0.10)), (0.7, (0.94, 0.14, 0.16)), (1.0, (0.98, 0.30, 0.22))],
                   coord="z", lo=-0.5 * size, hi=0.5 * size, rough=0.15, sss=0.4, sss_radius=(1, 0.3, 0.3), coat=0.8,
                   coat_rough=0.05)
    add_speckles(red, (1.0, 0.86, 0.40), scale=34 / size, threshold=0.68, strength=0.85)
    if half:
        bisect(ob, (0, 0, 0), (0, -1, 0))
        smooth(ob, 60)
        cut = material(f"{name}Cut", [(0.0, (1.0, 0.92, 0.90)), (0.45, (1.0, 0.62, 0.66)), (1.0, (0.92, 0.18, 0.22))],
                       coord="r_xz", lo=0.0, hi=0.4 * size, rough=0.2, sss=0.5, coat=0.6)
        assign_faces(ob, red, [(lambda n, c: n.y < -0.9, cut)])
    else:
        smooth(ob)
        assign(ob, red)
    parts = [ob]
    green = material(f"{name}Green", [(0.0, (0.18, 0.52, 0.14)), (1.0, (0.42, 0.76, 0.24))], coord="z", lo=0.4 * size,
                     hi=0.6 * size, rough=0.3, sss=0.3, coat=0.4)
    for i in range(5):
        if half and i in (1, 2):
            continue
        a = 2 * math.pi * i / 5 + 0.4
        sp = sphere(f"{name}Sepal{i}", 1.0, 16, 10)
        sp.scale = (0.17 * size, 0.06 * size, 0.025 * size)
        sp.location = (0.12 * size * math.cos(a), 0.12 * size * math.sin(a), 0.5 * size)
        sp.rotation_euler = (0, math.radians(-20), a)
        assign(smooth(sp), green)
        parts.append(sp)
    return parts


def dish_sundae():
    glass = lathe("SundaeGlass", [(0.0, 0.0), (0.52, 0.0), (0.55, 0.03), (0.52, 0.07), (0.14, 0.10), (0.085, 0.16),
                                  (0.075, 0.48), (0.11, 0.58), (0.32, 0.70), (0.60, 0.92), (0.80, 1.22), (0.83, 1.29),
                                  (0.80, 1.30), (0.76, 1.25), (0.57, 0.96), (0.30, 0.76), (0.0, 0.72)], 96)
    subdivide(glass, 1)
    smooth(glass, 60)
    assign(glass, glass_mat("SundaeGlassMat", (0.92, 0.96, 1.0)))
    fill = lathe("SundaeFill", [(0.0, 0.74), (0.28, 0.775), (0.55, 0.97), (0.73, 1.24), (0.0, 1.24)], 96)
    smooth(fill, 60)
    assign(fill, material("SundaeFillMat", [(0.0, (0.86, 0.14, 0.26)), (0.62, (0.98, 0.38, 0.48)),
                                            (0.68, (1.0, 0.93, 0.80)), (1.0, (1.0, 0.97, 0.88))],
                          coord="z", lo=0.74, hi=1.24, rough=0.3, sss=0.5, coat=0.3))
    parts = [glass, fill]
    flavors = [("Vanilla", (0.98, 0.86, 0.58), (1.0, 0.96, 0.82)), ("Berry", (0.94, 0.38, 0.54), (1.0, 0.64, 0.76)),
               ("Choco", (0.46, 0.24, 0.12), (0.66, 0.40, 0.24))]
    sauce = material("ChocSauce", [(0.0, (0.28, 0.12, 0.05)), (1.0, (0.46, 0.22, 0.10))], coord="z", lo=-0.3, hi=0.4,
                     rough=0.06, sss=0.2, coat=0.9, coat_rough=0.03)
    rs = 0.37
    for i, (nm, lo_c, hi_c) in enumerate(flavors):
        a = math.radians(110 + 120 * i)
        x, y, z = 0.30 * math.cos(a), 0.30 * math.sin(a), 1.40
        sc = scoop(f"Scoop{nm}", rs, lo_c, hi_c, 0.0, i * 2)
        sc.location = (x, y, z)
        parts.append(sc)
    cream = material("Whipped", [(0.0, (0.96, 0.95, 0.94)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=0.5,
                     rough=0.35, sss=0.5, sss_radius=(1, 1, 1), coat=0.2)
    sw = piped_swirl("Whip", cream, 0.36, 0.56)
    sw.location = (0.0, 0.0, 1.62)
    parts.append(sw)
    # шоколадный соус тонкой струйкой по шарикам
    scoops = [o for o in parts if o.name.startswith("Scoop")]
    bpy.context.view_layer.update()

    def top_z(x, y):
        best = None
        for o in scoops:
            inv = o.matrix_world.inverted()
            ok, loc, _, _ = o.ray_cast(inv @ Vector((x, y, 10.0)), (inv.to_3x3() @ Vector((0, 0, -1))).normalized())
            if ok:
                z = (o.matrix_world @ loc).z
                best = z if best is None else max(best, z)
        return best
    for j, (y0, ph) in enumerate(((-0.30, 0.0), (0.0, 1.3), (0.30, 2.1))):
        line = []
        for k in range(90):
            t = k / 89
            x = -0.62 + 1.24 * t
            y = y0 + 0.13 * math.sin(t * math.pi * 5 + ph)
            z = top_z(x, y)
            if z is None or math.hypot(x, y) < 0.2:
                if len(line) > 4:
                    tb = sweep(f"Drizzle{j}_{k}", line, 0.026, segs=12, step=0.008, section=(0.7, 1.0))
                    assign(tb, sauce)
                    parts.append(tb)
                line = []
                continue
            line.append((x, y, z + 0.012))
        if len(line) > 4:
            tb = sweep(f"Drizzle{j}e", line, 0.026, segs=12, step=0.008, section=(0.7, 1.0))
            assign(tb, sauce)
            parts.append(tb)
    cherry = sphere("SCherry", 0.14, 48, 32)
    cherry.scale = (1.0, 1.0, 0.92)
    cherry.location = (0.0, 0.0, 2.27)
    assign(smooth(cherry), material("SCherryMat", [(0.0, (0.62, 0.02, 0.06)), (1.0, (0.92, 0.10, 0.12))], coord="z",
                                    lo=-0.14, hi=0.14, rough=0.06, sss=0.3, coat=0.9))
    stem = sweep("SCherryStem", [(0.0, 0.0, 2.37), (0.03, 0.0, 2.49), (0.11, 0.02, 2.59)], 0.016, segs=8, step=0.02)
    assign(stem, flat("SCherryStemMat", (0.40, 0.56, 0.18), rough=0.4))
    parts += [cherry, stem]
    for i in range(3):
        a = math.radians(110 + 60 + 120 * i)
        sb = strawberry_obj(f"SBerry{i}", 0.42, half=True)
        rotate_all(sb, (math.radians(-90 + 20), 0, 0))
        rotate_all(sb, (0, 0, a + math.pi / 2))
        move(sb, (0.56 * math.cos(a), 0.56 * math.sin(a), 1.44))
        parts += sb
    return parts


RAINBOW = [(0.95, 0.22, 0.28), (1.0, 0.56, 0.14), (1.0, 0.84, 0.22), (0.36, 0.80, 0.40), (0.26, 0.60, 0.96),
           (0.66, 0.40, 0.90)]


def lollipop():
    R, H = 0.82, 0.24
    disc = rounded_disc("Lolly", R, H, 2.4, 56)
    subdivide(disc, 1)
    n, twist = len(RAINBOW), 1.15

    def phase(co):
        a = math.atan2(co.y, co.x)
        r = math.hypot(co.x, co.y)
        return (a / (2 * math.pi) - r * twist) * n

    def relief(co, nrm):
        if abs(nrm.z) < 0.25:
            return 0.0
        d = phase(co) % 1.0
        e = min(d, 1 - d)
        fade = min(1.0, math.hypot(co.x, co.y) / 0.1)
        return (-0.022 * math.exp(-(e / 0.07) ** 2) + 0.01 * math.sin(math.pi * d)) * fade
    push_normals(disc, relief)
    smooth(disc)
    mat = material("LollyMat", [(0.0, (1, 1, 1)), (1.0, (1, 1, 1))], rough=0.1, sss=0.35, sss_radius=(1, 0.8, 0.8),
                   coat=0.9, coat_rough=0.03)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    at2 = nodes.new("ShaderNodeMath")
    at2.operation = "ARCTAN2"
    links.new(sep.outputs["Y"], at2.inputs[0])
    links.new(sep.outputs["X"], at2.inputs[1])
    vm = nodes.new("ShaderNodeVectorMath")
    vm.operation = "LENGTH"
    mul = nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = (1, 1, 0)
    links.new(tc.outputs["Object"], mul.inputs[0])
    links.new(mul.outputs[0], vm.inputs[0])
    d1 = nodes.new("ShaderNodeMath")
    d1.operation = "MULTIPLY"
    d1.inputs[1].default_value = 1 / (2 * math.pi)
    links.new(at2.outputs[0], d1.inputs[0])
    d2 = nodes.new("ShaderNodeMath")
    d2.operation = "MULTIPLY_ADD"
    d2.inputs[1].default_value = -twist
    links.new(vm.outputs["Value"], d2.inputs[0])
    links.new(d1.outputs[0], d2.inputs[2])
    fr = nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    links.new(d2.outputs[0], fr.inputs[0])
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.interpolation = "CONSTANT"
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (*lin(RAINBOW[0]), 1)
    els[1].position, els[1].color = 1 / n, (*lin(RAINBOW[1]), 1)
    for k in range(2, n):
        e = els.new(k / n)
        e.color = (*lin(RAINBOW[k]), 1)
    links.new(fr.outputs[0], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], nodes["Principled BSDF"].inputs["Base Color"])
    assign(disc, mat)
    parts = [disc]
    stick = sweep("LollyStick", [(0.0, -R * 0.55, 0.0), (0.0, -R - 1.25, 0.0)], 0.055, segs=24, step=0.05)
    assign(stick, material("LollyStickMat", [(0.0, (0.90, 0.90, 0.92)), (1.0, (1.0, 1.0, 1.0))], coord="y", lo=-2.0,
                           hi=-0.5, rough=0.35, coat=0.3))
    parts.append(stick)
    bow_mat = material("LollyBowMat", [(0.0, (0.92, 0.36, 0.56)), (1.0, (1.0, 0.56, 0.72))], coord="z", lo=-0.15,
                       hi=0.15, rough=0.25, sss=0.2, coat=0.7)
    bow = ribbon_bow("LollyBow", bow_mat, 0.75)
    rotate_all(bow, (math.radians(-90), 0, 0))
    move(bow, (0.0, -R - 0.08, H / 2 + 0.06))
    parts += bow
    rotate_all(parts, (math.radians(90), 0, 0))
    return rotate_all(parts, (math.radians(-12), 0, math.radians(-14)))


def cotton_candy():
    mb = bpy.data.metaballs.new("Cotton")
    mb.resolution = 0.035
    mb.render_resolution = 0.035
    mo = link(bpy.data.objects.new("Cotton", mb))
    rnd = random.Random(8)
    balls = [(0.0, 0.0, 1.62, 0.62), (0.0, 0.0, 1.15, 0.36)]
    for i in range(34):
        u = rnd.uniform(-1, 1)
        a = rnd.uniform(0, 2 * math.pi)
        rr = math.sqrt(1 - u * u)
        d = rnd.uniform(0.55, 0.95)
        balls.append((0.62 * rr * math.cos(a) * d, 0.52 * rr * math.sin(a) * d, 1.62 + 0.50 * u * d,
                      rnd.uniform(0.26, 0.40)))
    for x, y, z, r in balls:
        e = mb.elements.new()
        e.co = (x, y, z)
        e.radius = r
        e.stiffness = 1.6
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(mo.evaluated_get(dg))
    bpy.data.objects.remove(mo, do_unlink=True)
    cloud = link(bpy.data.objects.new("CottonMesh", me))
    push_normals(cloud, lambda co, n: 0.035 * fbm(co * 3.5, 3) + 0.012 * fbm(co * 11, 2))
    smooth(cloud)
    mat = material("CottonMat", [(0.0, (0.96, 0.52, 0.72)), (0.5, (1.0, 0.66, 0.80)), (1.0, (1.0, 0.82, 0.90))],
                   coord="z", lo=0.9, hi=2.3, rough=0.6, sss=0.8, sss_radius=(1, 0.75, 0.85), sss_scale=0.15,
                   sheen=1.0, bump=0.45, bump_scale=38, bump_detail=8, vary=0.35, vary_scale=2.5)
    assign(cloud, mat)
    stick = sweep("CottonStick", [(0.0, 0.0, -0.05), (0.0, 0.0, 1.3)], lambda t: 0.075 - 0.03 * t, segs=28, step=0.02)
    smat = material("CottonStickMat", [(0.0, (1, 1, 1)), (1.0, (1, 1, 1))], rough=0.5, coat=0.2)
    uv_pattern(smat, [(0.0, (0.98, 0.97, 0.94)), (0.6, (0.99, 0.98, 0.95)), (0.62, (0.42, 0.72, 0.96)),
                      (0.86, (0.42, 0.72, 0.96)), (0.88, (0.98, 0.97, 0.94)), (1.0, (0.98, 0.97, 0.94))],
               fu=1 / 0.24, fv=1.0)
    assign(stick, smat)
    return rotate_all([cloud, stick], (0, math.radians(-8), math.radians(-10)))


def cake_slice():
    R, ang = 1.30, 38.0
    a0, a1 = math.radians(90 - ang / 2), math.radians(90 + ang / 2)
    sector = [(0.0, 0.0)] + [(R * math.cos(a0 + (a1 - a0) * k / 24), R * math.sin(a0 + (a1 - a0) * k / 24))
                             for k in range(25)]
    H = 0.86
    body = profile_prism("Cake", sector, H, 0.0)
    bevel(body, 0.03, 3, 30)
    smooth(body, 40)
    sponge, cream = (1.0, 0.86, 0.56), (1.0, 0.64, 0.74)
    bands = [(0.0, (0.94, 0.74, 0.40))]
    z = 0.0
    for kind, h in (("s", 0.24), ("c", 0.07), ("s", 0.22), ("c", 0.07), ("s", 0.26)):
        col = sponge if kind == "s" else cream
        bands += [(min(1.0, (z + 0.01) / H), col), (min(1.0, (z + h - 0.01) / H), col)]
        z += h
    cake = material("CakeLayers", bands, coord="z", lo=0.0, hi=H, rough=0.55, sss=0.3, sss_radius=(1, 0.8, 0.6),
                    bump=0.3, bump_scale=30, bump_detail=6)
    frost = material("CakeFrost", [(0.0, (0.97, 0.95, 0.96)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=1.0,
                     rough=0.25, sss=0.4, sss_radius=(1, 1, 1), coat=0.5)
    mid = (a0 + a1) / 2
    assign_faces(body, cake, [(lambda n, c: (c.x * math.cos(mid) + c.y * math.sin(mid)) > R * 0.85 and
                               (n.x * c.x + n.y * c.y) > 0.6 * math.hypot(c.x, c.y), frost)])
    parts = [body]
    big = [(0.0, -0.04)] + [((R + 0.03) * math.cos(a0 - 0.03 + (a1 - a0 + 0.06) * k / 24),
                             (R + 0.03) * math.sin(a0 - 0.03 + (a1 - a0 + 0.06) * k / 24)) for k in range(25)]
    top = profile_prism("CakeTop", big, 0.12, H - 0.02)
    bevel(top, 0.05, 4, 30)
    subdivide(top, 1)
    smooth(top)
    assign(top, frost)
    parts.append(top)
    # тонкий слой крема по дуге сзади
    shell = lathe("CakeBack", [(R - 0.02, 0.02), (R + 0.035, 0.03), (R + 0.04, H * 0.5), (R + 0.035, H - 0.01),
                               (R - 0.02, H - 0.01)], 160)
    shell = bisect(shell, (0, 0, 0), (math.sin(a0), -math.cos(a0), 0), fill=False)
    shell = bisect(shell, (0, 0, 0), (-math.sin(a1), math.cos(a1), 0), fill=False)
    smooth(shell)
    assign(shell, frost)
    parts.append(shell)
    pink = material("CakeRose", [(0.0, (1.0, 0.56, 0.70)), (1.0, (1.0, 0.74, 0.84))], coord="z", lo=0.0, hi=0.3,
                    rough=0.3, sss=0.4, coat=0.4)
    for i, t in enumerate((-0.55, 0.0, 0.55)):
        a = mid + t * (a1 - a0) / 2
        ro = piped_swirl(f"CakeRose{i}", pink, 0.12, 0.17, 7, 3.0)
        ro.location = ((R - 0.13) * math.cos(a), (R - 0.13) * math.sin(a), H + 0.08)
        parts.append(ro)
    sb = strawberry_obj("CakeBerry", 0.5)
    rotate_all(sb, (math.radians(180), 0, 0))
    rotate_all(sb, (math.radians(-25), 0, math.radians(10)))
    move(sb, (0.0, 0.66, H + 0.30))
    parts += sb
    cols = [(1.0, 0.85, 0.2), (0.3, 0.75, 1.0), (0.45, 0.85, 0.4), (0.62, 0.42, 0.95), (1.0, 0.45, 0.55)]
    smats = [flat(f"CakeSpr{i}", c, rough=0.25, coat=0.5) for i, c in enumerate(cols)]

    def make(i, rnd):
        sp = capsule(f"CakeSprinkle{i}", 0.10, 0.02, 10, 8)
        assign(smooth(sp), smats[rnd.randrange(len(smats))])
        return sp
    scatter_on(top, 26, make, seed=4, area=1.2, zmin=H + 0.05, spacing=0.09)
    plate_ob = plate("CakePlate", 0.98, ((0.62, 0.84, 0.96), (0.80, 0.93, 1.0)))
    plate_ob.location = (0.0, 0.62, -0.10)
    parts.append(plate_ob)
    return rotate_all(parts, (0, 0, math.radians(-34)), pivot=(0, 0.62, 0))


# MARK: - Летний гриль

def beef_cube(name, size=0.32, seed=0):
    ob = box_mesh(name, size, size, size, -size / 2, cuts=4)
    bevel(ob, size * 0.22, 4, 30)
    subdivide(ob, 1)
    push_normals(ob, lambda co, n: 0.018 * fbm(co * 7 + Vector((seed, 0, 0)), 3))
    smooth(ob)
    mat = material(f"{name}Mat", [(0.0, (0.36, 0.14, 0.06)), (0.45, (0.58, 0.25, 0.10)), (0.8, (0.70, 0.34, 0.14)),
                                  (1.0, (0.62, 0.29, 0.12))],
                   coord="nz", lo=-1, hi=1, rough=0.45, sss=0.25, sss_radius=(1, 0.35, 0.2), coat=0.35, coat_rough=0.2,
                   bump=0.45, bump_scale=16, bump_detail=8, vary=0.25, vary_scale=6)
    add_speckles(mat, (0.26, 0.10, 0.04), scale=12, threshold=0.66, strength=0.6)
    add_stripes(mat, (0.16, 0.06, 0.03), scale=4.0, angle=40, width=0.2, nz_min=0.35, strength=0.85)
    assign(ob, mat)
    return ob


def onion_chunk(name, size=0.34):
    skin = material(f"{name}Skin", [(0.0, (0.52, 0.14, 0.36)), (1.0, (0.76, 0.32, 0.58))], coord="z", lo=-0.2, hi=0.2,
                    rough=0.25, sss=0.4, sss_radius=(1, 0.5, 0.8), coat=0.6)
    flesh = material(f"{name}Flesh", [(0.0, (0.94, 0.80, 0.90)), (1.0, (1.0, 0.95, 0.98))], coord="z", lo=-0.2, hi=0.2,
                     rough=0.25, sss=0.5, coat=0.5)
    add_speckles(flesh, (0.36, 0.18, 0.08), scale=9, threshold=0.66, strength=0.7)
    add_speckles(skin, (0.24, 0.08, 0.10), scale=9, threshold=0.68, strength=0.6)
    parts = []
    for k in range(3):
        ly = box_mesh(f"{name}L{k}", 0.07 * size / 0.34, size, size * 0.92, -size * 0.46, cuts=6)
        bevel(ly, 0.02, 2, 30)
        subdivide(ly, 1)
        rr = 0.42 + 0.06 * k
        gap = 0.082 * size / 0.34
        deform(ly, lambda co, rr=rr, k=k: Vector((co.x + (k - 1) * gap - (co.y * co.y) / (2 * rr), co.y, co.z)))
        smooth(ly)
        assign_faces(ly, flesh, [(lambda n, c: n.x > 0.55, skin)])
        parts.append(ly)
    return parts


def cherry_tomato(name, r=0.16):
    ob = sphere(name, r, 48, 32)
    deform(ob, lambda co: Vector((co.x, co.y, co.z * 0.92)))
    smooth(ob)
    tm = material(f"{name}Mat", [(0.0, (0.80, 0.08, 0.05)), (0.6, (0.96, 0.18, 0.08)), (1.0, (1.0, 0.36, 0.20))],
                  coord="z", lo=-r, hi=r, rough=0.12, sss=0.35, sss_radius=(1, 0.25, 0.15), coat=0.85,
                  coat_rough=0.04)
    add_speckles(tm, (0.36, 0.06, 0.03), scale=6 / r * 0.2, threshold=0.72, strength=0.7)
    assign(ob, tm)
    return ob


def dish_kebab():
    parts = wooden_board("KebabBoard", 2.5, 1.12)
    stick_mat = material("SkewerMat", [(0.0, (0.62, 0.40, 0.20)), (0.3, (0.90, 0.76, 0.54)), (1.0, (0.94, 0.82, 0.60))],
                         coord="x", lo=-1.5, hi=1.5, rough=0.5, coat=0.15)
    rnd = random.Random(12)
    seqs = [["b", "o", "t", "b", "o", "b"], ["t", "b", "o", "b", "t", "b"]]
    zc = 0.25
    for si, (y, seq) in enumerate(zip((0.25, -0.25), seqs)):
        stick = sweep(f"Skewer{si}", [(-1.50, y, zc), (1.40, y, zc)],
                      lambda t: 0.036 * (1.0 if t < 0.94 else max(0.12, (1 - t) / 0.06)), segs=16, step=0.04)
        assign(stick, stick_mat)
        parts.append(stick)
        widths = {"b": 0.45, "o": 0.32, "t": 0.40}
        x = -sum(widths[k] for k in seq) / 2 + 0.05
        for k, kind in enumerate(seq):
            w = widths[kind]
            xc = x + w / 2
            if kind == "b":
                ob = beef_cube(f"Beef{si}{k}", 0.42, si * 10 + k)
                ob.rotation_euler = (rnd.uniform(-0.15, 0.15), rnd.uniform(-0.15, 0.15), rnd.uniform(-0.2, 0.2))
                ob.location = (xc, y, zc)
                parts.append(ob)
            elif kind == "o":
                ch = onion_chunk(f"Onion{si}{k}", 0.42)
                rotate_all(ch, (rnd.uniform(-0.2, 0.2), 0, math.radians(180 * (k % 2))))
                move(ch, (xc, y, zc))
                parts += ch
            else:
                ob = cherry_tomato(f"KTom{si}{k}", 0.19)
                ob.location = (xc, y, zc)
                parts.append(ob)
            x += w
    return rotate_all(parts, (0, 0, math.radians(-10)))


def watermelon():
    R, ang, th = 1.25, 64.0, 0.42
    a0, a1 = math.radians(-90 - ang / 2), math.radians(-90 + ang / 2)
    outline = [(0.0, 0.0)] + [(R * math.cos(a0 + (a1 - a0) * k / 40), R * math.sin(a0 + (a1 - a0) * k / 40))
                              for k in range(41)]
    ob = profile_prism("Watermelon", outline, th, -th / 2)
    bevel(ob, 0.07, 5, 30)
    subdivide(ob, 1)
    push_normals(ob, lambda co, n: 0.006 * fbm(co * 6) if abs(n.z) > 0.8 else 0.0)
    smooth(ob)
    mat = material("WatermelonMat", [(0.0, (0.88, 0.10, 0.18)), (0.55, (0.96, 0.22, 0.28)), (0.76, (1.0, 0.40, 0.42)),
                                     (0.80, (1.0, 0.86, 0.80)), (0.86, (0.86, 0.96, 0.70)), (0.885, (0.40, 0.72, 0.26)),
                                     (0.93, (0.16, 0.46, 0.14)), (1.0, (0.10, 0.34, 0.10))],
                   coord="r", lo=0.0, hi=R, rough=0.22, sss=0.45, sss_radius=(1, 0.3, 0.3), coat=0.6, coat_rough=0.08,
                   bump=0.12, bump_scale=22, vary=0.04)
    assign(ob, mat)
    parts = [ob]
    seed_mat = material("WSeed", [(0.0, (0.06, 0.04, 0.04)), (1.0, (0.20, 0.14, 0.12))], coord="z", lo=-0.03, hi=0.03,
                        rough=0.1, coat=0.9)
    rnd = random.Random(4)
    k = 0
    for rr, n in ((0.42, 3), (0.70, 5)):
        for i in range(n):
            a = a0 + (a1 - a0) * (i + 0.5) / n + rnd.uniform(-0.04, 0.04)
            for face in (1, -1):
                sd = sphere(f"WSeed{k}", 1.0, 20, 12)
                sd.scale = (0.038, 0.06, 0.02)
                apply_transform(sd)
                deform(sd, lambda co: Vector((co.x * (1 - 0.6 * max(0.0, co.y / 0.06)), co.y, co.z)))
                assign(smooth(sd), seed_mat)
                sd.rotation_euler = (0, 0, a + math.pi / 2)
                sd.location = (rr * math.cos(a), rr * math.sin(a), face * (th / 2 - 0.004))
                parts.append(sd)
                k += 1
    rotate_all(parts, (math.radians(90), 0, 0))
    move(parts, (0, 0, R))
    return rotate_all(parts, (math.radians(-10), 0, math.radians(-22)))


def citrus_mat(name, R, n=9, rind=(1.0, 0.82, 0.10), flesh=(1.0, 0.86, 0.30), memb=(1.0, 0.97, 0.84)):
    """Срез цитруса: дольки с белыми перегородками, белая корочка и цедра по краю."""
    mat = material(name, [(0.0, memb), (0.12, flesh), (0.80, flesh), (0.83, memb), (0.90, memb), (0.92, rind),
                          (1.0, tuple(c * 0.9 for c in rind))], coord="r", lo=0.0, hi=R, rough=0.15, sss=0.6,
                   sss_radius=(1, 0.8, 0.3), coat=0.7, coat_rough=0.05)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    at2 = nodes.new("ShaderNodeMath")
    at2.operation = "ARCTAN2"
    links.new(sep.outputs["Y"], at2.inputs[0])
    links.new(sep.outputs["X"], at2.inputs[1])
    m1 = nodes.new("ShaderNodeMath")
    m1.operation = "MULTIPLY"
    m1.inputs[1].default_value = n / (2 * math.pi)
    links.new(at2.outputs[0], m1.inputs[0])
    fr = nodes.new("ShaderNodeMath")
    fr.operation = "FRACT"
    links.new(m1.outputs[0], fr.inputs[0])
    inv = nodes.new("ShaderNodeMath")
    inv.operation = "SUBTRACT"
    inv.inputs[0].default_value = 1.0
    links.new(fr.outputs[0], inv.inputs[1])
    mn = nodes.new("ShaderNodeMath")
    mn.operation = "MINIMUM"
    links.new(fr.outputs[0], mn.inputs[0])
    links.new(inv.outputs[0], mn.inputs[1])
    edge = nodes.new("ShaderNodeMapRange")
    edge.inputs["From Min"].default_value = 0.07
    edge.inputs["From Max"].default_value = 0.0
    links.new(mn.outputs[0], edge.inputs["Value"])
    ln = nodes.new("ShaderNodeVectorMath")
    ln.operation = "LENGTH"
    mul = nodes.new("ShaderNodeVectorMath")
    mul.operation = "MULTIPLY"
    mul.inputs[1].default_value = (1, 1, 0)
    links.new(tc.outputs["Object"], mul.inputs[0])
    links.new(mul.outputs[0], ln.inputs[0])
    inner = nodes.new("ShaderNodeMapRange")
    inner.inputs["From Min"].default_value = 0.12 * R
    inner.inputs["From Max"].default_value = 0.18 * R
    links.new(ln.outputs["Value"], inner.inputs["Value"])
    outer = nodes.new("ShaderNodeMapRange")
    outer.inputs["From Min"].default_value = 0.82 * R
    outer.inputs["From Max"].default_value = 0.78 * R
    links.new(ln.outputs["Value"], outer.inputs["Value"])
    m2 = nodes.new("ShaderNodeMath")
    m2.operation = "MULTIPLY"
    links.new(edge.outputs["Result"], m2.inputs[0])
    links.new(inner.outputs["Result"], m2.inputs[1])
    m3 = nodes.new("ShaderNodeMath")
    m3.operation = "MULTIPLY"
    links.new(m2.outputs[0], m3.inputs[0])
    links.new(outer.outputs["Result"], m3.inputs[1])
    M._mix_over(mat, m3.outputs[0], memb)
    return mat


def citrus_wheel(name, R=0.3, th=0.07, **kw):
    ob = cylinder(name, R, th, 64)
    bevel(ob, th * 0.3, 3, 30)
    smooth(ob, 40)
    assign(ob, citrus_mat(f"{name}Mat", R, **kw))
    return ob


def ice_cube(name, s=0.2):
    ob = box_mesh(name, s, s, s, -s / 2, cuts=2)
    bevel(ob, s * 0.2, 3, 30)
    smooth(ob, 40)
    assign(ob, glass_mat(f"{name}Mat", (0.86, 0.94, 1.0), center=0.25, edge=0.9))
    return ob


def lemonade():
    prof = [(0.0, 0.0), (0.50, 0.0), (0.56, 0.04), (0.61, 0.30), (0.63, 0.70), (0.57, 1.10), (0.52, 1.34), (0.55, 1.50),
            (0.58, 1.56), (0.555, 1.57), (0.525, 1.51), (0.49, 1.35), (0.535, 1.10), (0.595, 0.70), (0.575, 0.30),
            (0.52, 0.09), (0.0, 0.08)]
    jug = lathe("Pitcher", prof, 128)

    def spout(co):
        a = math.atan2(co.y, co.x)
        da = math.atan2(math.sin(a - math.pi), math.cos(a - math.pi))
        w = math.exp(-(da / 0.38) ** 2) * smoothstep(1.2, 1.56, co.z)
        r = math.hypot(co.x, co.y)
        k = 1.0 + 0.32 * w
        return Vector((co.x * k, co.y * k, co.z + 0.08 * w))
    deform(jug, spout)
    subdivide(jug, 1)
    smooth(jug, 60)
    gl = glass_mat("PitcherGlass", (1.0, 1.0, 1.0))
    assign(jug, gl)
    parts = [jug]
    hp = [(0.58, 0.0, 1.36), (0.82, 0.0, 1.32), (0.92, 0.0, 1.10), (0.88, 0.0, 0.78), (0.74, 0.0, 0.56),
          (0.60, 0.0, 0.50)]
    handle = sweep("PitcherHandle", spline(hp, 10), 0.06, segs=16, step=0.02, section=(1.0, 1.3))
    assign(handle, gl)
    parts.append(handle)
    level = 1.22
    liquid = lathe("Lemonade", [(0.0, 0.10), (0.46, 0.10), (0.50, 0.30), (0.515, 0.70), (0.47, 1.10),
                                (0.46, level), (0.0, level)], 96)
    smooth(liquid, 60)
    lem = material("LemonadeMat", [(0.0, (1.0, 0.78, 0.08)), (0.6, (1.0, 0.86, 0.18)), (1.0, (1.0, 0.93, 0.40))],
                   coord="z", lo=0.1, hi=level, rough=0.06, sss=0.15, sss_radius=(1, 0.8, 0.2), coat=0.8)
    # легкое свечение: солнечный лимонад не уходит в оливковый в тени
    lb = lem.node_tree.nodes["Principled BSDF"]
    lb.inputs["Emission Color"].default_value = (*lin((1.0, 0.82, 0.18)), 1)
    lb.inputs["Emission Strength"].default_value = 0.35
    assign(liquid, see_through(lem, 0.92))
    parts.append(liquid)
    # дольки лимона прижаты к стенке изнутри
    for i, (a, z, tilt) in enumerate(((-80, 0.68, 10), (-25, 0.46, -15), (-135, 0.44, 20))):
        w = citrus_wheel(f"LemonIn{i}", 0.19, 0.045)
        w.rotation_euler = (math.radians(90), math.radians(tilt), math.radians(a + 90))
        rr = 0.535
        w.location = (rr * math.cos(math.radians(a)), rr * math.sin(math.radians(a)), z)
        parts.append(w)
    for i, (x, y, rz) in enumerate(((0.14, -0.18, 20), (-0.18, 0.10, 50), (0.16, 0.18, -15))):
        c = ice_cube(f"Ice{i}", 0.2)
        c.rotation_euler = (math.radians(12), math.radians(-8), math.radians(rz))
        c.location = (x, y, level + 0.02)
        parts.append(c)
    gstops = [(0.0, (0.12, 0.46, 0.16)), (0.6, (0.22, 0.62, 0.22)), (1.0, (0.36, 0.76, 0.30))]
    for i, (ang, tilt) in enumerate(((60, 40), (150, 30), (250, 45))):
        lf = leaf(f"Mint{i}", 0.34, 0.2, fold=0.12, curl=0.3, stops=gstops, petiole=0.03, serr=0.06)
        rotate_all(lf, (0, math.radians(-tilt), math.radians(ang)))
        move(lf, (-0.05, 0.0, level + 0.10))
        parts += lf
    rim = citrus_wheel("LemonRim", 0.26, 0.06)
    rim.rotation_euler = (math.radians(90), 0, math.radians(120))
    rim.location = (0.555 * math.cos(math.radians(-60)), 0.555 * math.sin(math.radians(-60)), 1.50)
    parts.append(rim)
    return rotate_all(parts, (0, 0, math.radians(20)))


def graham(name, s=0.95, th=0.12, seed=0):
    ob = box_mesh(name, s, s, th, -th / 2, cuts=30)
    bevel(ob, 0.035, 3, 30)
    subdivide(ob, 1)

    def hole(co):
        # проколы 4x4 и линия надлома посередине
        gx = (co.x / s + 0.5) * 4
        gy = (co.y / s + 0.5) * 4
        dx, dy = gx - math.floor(gx) - 0.5, gy - math.floor(gy) - 0.5
        d = math.hypot(dx, dy)
        return max(max(0.0, 1 - d / 0.17) ** 0.7, math.exp(-(co.x / 0.016) ** 2))

    def dents(co, n):
        if n.z < 0.7:
            return 0.0
        return -0.02 * hole(co) + 0.003 * fbm(co * 9 + Vector((seed, 0, 0)))
    push_normals(ob, dents)
    smooth(ob)
    set_attr(ob, "hole", lambda co, n: hole(co) if n.z > 0.7 else 0.0)
    mat = material(f"{name}Mat", [(0.0, (0.62, 0.34, 0.12)), (0.45, (0.80, 0.50, 0.22)), (1.0, (0.92, 0.66, 0.34))],
                   coord="nz", lo=-1, hi=1, rough=0.55, sss=0.15, coat=0.2, bump=0.3, bump_scale=24, bump_detail=6,
                   vary=0.18, vary_scale=5)
    add_speckles(mat, (0.58, 0.30, 0.10), scale=40, threshold=0.66, strength=0.6)
    mix_attr(mat, "hole", (0.56, 0.28, 0.08), 0.2, 0.9)
    assign(ob, mat)
    return ob


def smores():
    parts = []
    bot = graham("GrahamBottom", seed=1)
    bot.location = (0, 0, 0.06)
    parts.append(bot)
    choc = box_mesh("SmoreChoc", 0.70, 0.52, 0.09, 0.0, cuts=6)
    bevel(choc, 0.02, 2, 30)

    def segs(co, n):
        if n.z < 0.7:
            return 0.0
        return -0.014 * math.exp(-(co.x / 0.012) ** 2) - 0.014 * math.exp(-(co.y / 0.012) ** 2)
    subdivide(choc, 2)
    push_normals(choc, segs)
    smooth(choc, 40)
    choc_mat = material("SmoreChocMat", [(0.0, (0.28, 0.13, 0.06)), (1.0, (0.46, 0.23, 0.11))], coord="z", lo=0.0,
                        hi=0.1, rough=0.12, sss=0.2, coat=0.85, coat_rough=0.05)
    assign(choc, choc_mat)
    choc.rotation_euler = (0, 0, math.radians(12))
    choc.location = (0.10, -0.08, 0.12)
    parts.append(choc)
    # шоколад стекает через край нижнего печенья
    for i, (x, ln) in enumerate(((0.30, 0.07), (0.04, 0.03))):
        d = sweep(f"ChocDrip{i}", [(x, -0.30, 0.17), (x, -0.43, 0.155), (x, -0.495, 0.125), (x, -0.505, 0.11 - ln)],
                  lambda t: 0.042 * (1 - 0.15 * t), segs=16, step=0.01)
        assign(d, choc_mat)
        parts.append(d)
    mallow = rounded_disc("SmoreMallow", 0.43, 0.44, 2.4, 24)

    def melt(co):
        a = math.atan2(co.y, co.x)
        t = 1 - abs(co.z) / 0.22
        k = 1.0 + 0.13 * max(0.0, t) ** 1.5 + 0.06 * math.sin(3 * a + 1) * max(0.0, t)
        return Vector((co.x * k, co.y * k, co.z))
    deform(mallow, melt)
    subdivide(mallow, 1)
    push_normals(mallow, lambda co, n: 0.012 * fbm(co * 5))
    smooth(mallow)
    mm = material("SmoreMallowMat", [(0.0, (1.0, 0.99, 0.96)), (0.7, (1.0, 0.97, 0.92)), (0.9, (0.99, 0.90, 0.74)),
                                     (1.0, (0.96, 0.80, 0.54))],
                  coord="r", lo=0.0, hi=0.52, rough=0.35, sss=0.7, sss_radius=(1, 0.9, 0.8), coat=0.4)
    add_speckles(mm, (0.94, 0.68, 0.34), scale=5, threshold=0.6, strength=0.85)
    assign(mallow, mm)
    mallow.location = (0.02, 0.0, 0.42)
    parts.append(mallow)
    # тягучая капля маршмеллоу
    goo = sweep("SmoreGoo", [(-0.26, -0.30, 0.34), (-0.30, -0.40, 0.27), (-0.31, -0.43, 0.19), (-0.31, -0.42, 0.16)],
                lambda t: 0.075 + 0.02 * t, segs=20, step=0.01)
    assign(goo, mm)
    parts.append(goo)
    top = graham("GrahamTop", seed=5)
    top.rotation_euler = (math.radians(-6), math.radians(5), math.radians(14))
    top.location = (-0.04, 0.06, 0.70)
    parts.append(top)
    return rotate_all(parts, (math.radians(4), 0, math.radians(-36)))


# MARK: - Осенний урожай

def apple():
    ob = sphere("Apple", 1.0, 96, 64)
    deform(ob, lambda co: apple_shape(co, h=0.98, wide=0.16))
    smooth(ob)
    am = material("AppleMat", [(0.0, (0.56, 0.02, 0.06)), (0.45, (0.76, 0.04, 0.08)), (0.82, (0.88, 0.10, 0.10)),
                               (0.93, (0.92, 0.30, 0.14)), (1.0, (0.86, 0.62, 0.24))], coord="z", lo=-0.95, hi=0.85,
                  rough=0.15, sss=0.3, sss_radius=(1.0, 0.25, 0.15), coat=0.85, coat_rough=0.04, vary=0.1,
                  vary_scale=3)
    add_speckles(am, (1.0, 0.80, 0.50), scale=26, threshold=0.71, strength=0.35)
    assign(ob, am)
    top = 0.98 - 0.27
    stem = sweep("AppleStem", [(0.0, 0.0, top - 0.04), (0.01, 0.0, top + 0.12), (0.05, 0.0, top + 0.26),
                               (0.11, 0.0, top + 0.34)], lambda t: 0.04 * (1.0 - 0.3 * t), segs=12, step=0.015)
    assign(stem, material("AppleStemMat", [(0.0, (0.36, 0.22, 0.10)), (1.0, (0.52, 0.36, 0.18))], coord="z",
                          lo=top, hi=top + 0.35, rough=0.5, coat=0.2))
    lf = leaf("AppleLeaf", 0.80, 0.46, fold=0.10, curl=0.20, petiole=0.08)
    rotate_all(lf, (math.radians(-35), math.radians(-14), math.radians(-30)))
    move(lf, (0.06, 0.0, top + 0.22))
    return rotate_all([ob, stem] + lf, (math.radians(4), 0, math.radians(12)))


def apple_slice_obj(name, r=0.30, th=0.07):
    """Полукруглая долька яблока с красной кожицей по дуге."""
    pts = [(r * math.cos(math.pi * k / 30), r * math.sin(math.pi * k / 30) * 0.92) for k in range(31)]
    pts += [(-r * 0.6, 0.02), (0.0, 0.05), (r * 0.6, 0.02)]
    ob = profile_prism(name, pts, th, -th / 2)
    bevel(ob, 0.018, 3, 30)
    smooth(ob, 40)
    return ob


def dish_charlotte():
    parts = [plate("CharPlate", 1.42, ((0.95, 0.94, 0.92), (1.0, 1.0, 0.99)))]
    R, H = 1.06, 0.58
    cake = rounded_disc("Charlotte", R, H, 3.2, 36)
    push_normals(cake, lambda co, n: 0.012 * fbm(co * 3.5))
    cut_a = math.radians(-62)
    half = math.radians(25)
    wedge = [(0.0, 0.0)] + [(2.0 * math.cos(cut_a - half + 2 * half * k / 8), 2.0 * math.sin(cut_a - half + 2 * half * k / 8))
                            for k in range(9)]
    cutter = profile_prism("CharCutter", wedge, 2.0, -1.0)
    bpy.context.view_layer.update()
    boolean_cut(cake, [cutter])
    smooth(cake, 50)
    crust = material("CharCrust", [(0.0, (0.58, 0.30, 0.10)), (0.45, (0.76, 0.44, 0.16)), (0.8, (0.88, 0.58, 0.24)),
                                   (1.0, (0.92, 0.66, 0.32))], coord="nz", lo=-1, hi=1, rough=0.5, sss=0.25,
                     coat=0.25, bump=0.3, bump_scale=12, bump_detail=6, vary=0.18, vary_scale=4)
    add_speckles(crust, (1.0, 0.98, 0.96), scale=40, threshold=0.58, strength=0.8)
    crumb = material("CharCrumb", [(0.0, (1.0, 0.90, 0.64)), (1.0, (1.0, 0.95, 0.78))], coord="z", lo=-H / 2, hi=H / 2,
                     rough=0.65, sss=0.3, bump=0.5, bump_scale=36, bump_detail=8, vary=0.1, vary_scale=8)
    add_speckles(crumb, (1.0, 0.86, 0.52), scale=6, threshold=0.64, strength=0.4)

    def is_cut(n, c):
        rr = math.hypot(c.x, c.y)
        if abs(n.z) > 0.5 or rr < 1e-4:
            return False
        return abs((n.x * c.x + n.y * c.y) / rr) < 0.4
    assign_faces(cake, crust, [(is_cut, crumb)])
    cake.location = (0, 0, 0.09 + H / 2)
    parts.append(cake)
    flesh = material("CharApple", [(0.0, (0.88, 0.58, 0.20)), (0.6, (0.98, 0.80, 0.40)), (1.0, (1.0, 0.88, 0.56))],
                     coord="r", lo=0.0, hi=0.32, rough=0.18, sss=0.5, sss_radius=(1, 0.8, 0.3), coat=0.75)
    add_speckles(flesh, (1.0, 1.0, 1.0), scale=50, threshold=0.64, strength=0.55)
    skin = material("CharSkin", [(0.0, (0.66, 0.06, 0.06)), (1.0, (0.86, 0.16, 0.10))], coord="z", lo=-0.05, hi=0.05,
                    rough=0.2, coat=0.7)
    top_z = 0.09 + H
    k = 0
    for ring_r, n, dz in ((0.70, 11, -0.02), (0.30, 5, -0.03)):
        for i in range(n):
            a = 2 * math.pi * i / n + (0.2 if n == 8 else 0.0)
            da = math.atan2(math.sin(a - cut_a), math.cos(a - cut_a))
            if abs(da) < half + 0.22:
                continue
            sl = apple_slice_obj(f"CharSlice{k}")
            assign_faces(sl, flesh, [(lambda nn, c: abs(nn.z) < 0.6 and c.y > 0.08, skin)])
            sl.rotation_euler = (math.radians(14), math.radians(46), a - math.pi / 2)
            sl.location = (ring_r * math.cos(a), ring_r * math.sin(a), top_z + dz)
            parts.append(sl)
            k += 1
    return rotate_all(parts, (0, 0, math.radians(8)))


def chestnut(name, seed=0):
    ob = sphere(name, 1.0, 64, 40)

    def shape(co):
        k = 1.0 - 0.42 * max(0.0, co.z) ** 1.6
        return Vector((co.x * k * 0.30, co.y * k * 0.22, co.z * 0.27))
    deform(ob, shape)
    cut = []
    # крестовый надрез сверху: два V-образных клина
    for ang in (40, -40):
        tri = profile_prism(f"{name}Cut{ang}", [(0.0, 0.0), (0.06, 0.13), (-0.06, 0.13)], 0.44, -0.22)
        tri.rotation_euler = (math.radians(90), 0, 0)
        apply_transform(tri)
        tri.rotation_euler = (0, 0, math.radians(ang))
        tri.location = (0.0, 0.0, 0.175)
        cut.append(tri)
    bpy.context.view_layer.update()
    boolean_cut(ob, cut)
    smooth(ob, 50)
    shell = material(f"{name}Shell", [(0.0, (0.88, 0.76, 0.56)), (0.18, (0.78, 0.60, 0.40)), (0.26, (0.36, 0.15, 0.07)),
                                      (0.7, (0.50, 0.22, 0.09)), (1.0, (0.60, 0.30, 0.13))],
                     coord="z", lo=-0.27, hi=0.27, rough=0.18, sss=0.15, coat=0.75, coat_rough=0.08, vary=0.1,
                     vary_scale=6, bump=0.08, bump_scale=10)
    assign(ob, shell)
    nut = sphere(f"{name}Nut", 1.0, 48, 32)
    deform(nut, shape)
    nut.scale = (0.94, 0.94, 0.95)
    apply_transform(nut)
    push_normals(nut, lambda co, n: 0.006 * fbm(co * 20))
    smooth(nut)
    assign(nut, material(f"{name}NutMat", [(0.0, (0.94, 0.80, 0.44)), (1.0, (1.0, 0.90, 0.60))], coord="z", lo=0.0,
                         hi=0.27, rough=0.5, sss=0.4, bump=0.3, bump_scale=30))
    return [ob, nut]


def chestnuts():
    paper = material("ConePaper", [(0.0, (0.84, 0.66, 0.44)), (0.82, (0.94, 0.80, 0.58)), (0.83, (0.70, 0.14, 0.12)),
                                   (0.90, (0.76, 0.18, 0.14)), (0.91, (0.95, 0.82, 0.60)), (1.0, (0.96, 0.84, 0.62))],
                     coord="z", lo=0.0, hi=1.38, rough=0.6, coat=0.1, bump=0.2, bump_scale=10, vary=0.06)
    cone = lathe("PaperCone", [(0.0, 0.0), (0.05, 0.03), (0.60, 1.32), (0.63, 1.36), (0.61, 1.39), (0.57, 1.35),
                               (0.04, 0.07), (0.0, 0.06)], 64)

    # бумага слегка мятая
    push_normals(cone, lambda co, n: 0.008 * fbm(co * 4))
    subdivide(cone, 1)
    smooth(cone, 50)
    assign(cone, paper)
    nuts = []
    rnd = random.Random(6)
    for i in range(6):
        pr = chestnut(f"Chestnut{i}", i)
        a = rnd.uniform(0, 2 * math.pi)
        r = 0.2 * math.sqrt(rnd.random())
        for o in pr:
            o.location = (r * math.cos(a), r * math.sin(a), 1.62 + 0.5 * i)
            o.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, 6.3))
        nuts.append(pr)
    shells = [pr[0] for pr in nuts]
    # пробка внутри кулька, чтобы каштаны легли горкой у края
    plug = cylinder("ConePlug", 0.52, 0.1, 24)
    plug.location = (0, 0, 1.12)
    apply_transform(plug)
    proxy = lathe("ConeProxy", [(0.0, 0.0), (0.62, 1.33), (0.62, 3.0), (0.6, 3.0), (0.58, 1.36), (0.0, 0.04)], 32)
    settle(shells, 100, passive=[plug, proxy], friction=0.8)
    for pr in nuts:
        pr[1].matrix_world = pr[0].matrix_world.copy()
    bpy.data.objects.remove(plug, do_unlink=True)
    bpy.data.objects.remove(proxy, do_unlink=True)
    parts = [cone] + [o for pr in nuts for o in pr]
    # кулек наклонен вправо, горлышком к камере
    rotate_all(parts, (math.radians(12), math.radians(28), 0))
    lo = min((o.matrix_world @ Vector(c)).z for o in parts for c in o.bound_box)
    move(parts, (0, 0, -lo))
    front = []
    for i, (x, y, rz) in enumerate(((0.30, -0.62, 30), (-0.30, -0.70, -40))):
        pr = chestnut(f"ChestnutOut{i}", 20 + i)
        for o in pr:
            o.rotation_euler = (math.radians(14), 0, math.radians(rz))
            o.location = (x, y, 0.26)
        front.append(pr)
    return parts + [o for pr in front for o in pr]


def cider():
    prof = [(0.0, 0.0), (0.50, 0.0), (0.54, 0.03), (0.56, 0.12), (0.58, 1.30), (0.60, 1.36), (0.58, 1.38),
            (0.54, 1.33), (0.52, 0.24), (0.0, 0.22)]
    mug = lathe("CiderMug", prof, 96)
    subdivide(mug, 1)
    smooth(mug, 60)
    gl = glass_mat("CiderGlass", (0.96, 0.98, 1.0))
    assign(mug, gl)
    hp = []
    for k in range(31):
        t = k / 30
        a = math.pi / 2 - math.pi * t
        hp.append((0.56 + 0.30 * math.cos(a) * (0.6 + 0.4 * math.sin(math.pi * t)), 0.0, 0.72 + 0.36 * math.sin(a)))
    handle = sweep("CiderHandle", hp, 0.075, segs=16, step=0.02, section=(1.0, 1.25))
    assign(handle, gl)
    level = 1.14
    liquid = lathe("Cider", [(0.0, 0.23), (0.515, 0.23), (0.535, level), (0.0, level)], 96)
    smooth(liquid, 60)
    cm = material("CiderMat", [(0.0, (0.76, 0.30, 0.02)), (0.6, (0.90, 0.46, 0.06)), (1.0, (0.98, 0.62, 0.14))],
                  coord="z", lo=0.23, hi=level, rough=0.05, sss=0.2, sss_radius=(1, 0.4, 0.1), coat=0.8)
    cb = cm.node_tree.nodes["Principled BSDF"]
    cb.inputs["Emission Color"].default_value = (*lin((0.95, 0.50, 0.10)), 1)
    cb.inputs["Emission Strength"].default_value = 0.25
    assign(liquid, see_through(cm, 0.94))
    parts = [mug, handle, liquid]
    # кружок яблока на краю: прорезь надета на стенку
    R = 0.34
    wheel = cylinder("CiderApple", R, 0.07, 64)
    bevel(wheel, 0.02, 3, 30)
    smooth(wheel, 40)
    wm = material("CiderAppleMat", [(0.0, (0.94, 0.84, 0.56)), (0.25, (1.0, 0.94, 0.76)), (0.86, (1.0, 0.95, 0.80)),
                                    (0.9, (0.98, 0.90, 0.70)), (0.93, (0.80, 0.08, 0.08)), (1.0, (0.70, 0.04, 0.06))],
                  coord="r", lo=0.0, hi=R, rough=0.25, sss=0.4, coat=0.6)
    assign(wheel, wm)
    seed_mat = flat("CiderSeed", (0.30, 0.14, 0.06), rough=0.2, coat=0.8)
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.3
        sd = sphere(f"CiderSeed{i}", 1.0, 16, 10)
        sd.scale = (0.022, 0.04, 0.012)
        sd.rotation_euler = (0, 0, a - math.pi / 2)
        sd.location = (0.07 * math.cos(a), 0.07 * math.sin(a), 0.035)
        apply_transform(sd)
        assign(smooth(sd), seed_mat)
        parts.append(sd)
        sd2 = sphere(f"CiderSeedB{i}", 1.0, 16, 10)
        sd2.scale = (0.022, 0.04, 0.012)
        sd2.rotation_euler = (0, 0, a - math.pi / 2)
        sd2.location = (0.07 * math.cos(a), 0.07 * math.sin(a), -0.035)
        apply_transform(sd2)
        assign(smooth(sd2), seed_mat)
        parts.append(sd2)
    group = [wheel] + parts[-10:]
    rotate_all(group, (math.radians(90), 0, 0))
    rotate_all(group, (0, math.radians(-8), math.radians(20)))
    a = math.radians(-160)
    move(group, (0.57 * math.cos(a), 0.57 * math.sin(a), 1.37 + 0.06))
    parts.append(wheel)
    stick = cinnamon_stick("CiderCinnamon", 1.15, 0.075)
    stick.rotation_euler = (math.radians(-6), math.radians(-70), math.radians(40))
    stick.location = (0.08, 0.18, 1.3)
    parts.append(stick)
    anise = star_anise("CiderAnise")
    anise.location = (0.18, -0.18, level + 0.02)
    parts.append(anise)
    return rotate_all(parts, (0, 0, math.radians(-20)))


def star_anise(name, r=0.17):
    ob = sphere(name, 1.0, 64, 24)

    def shape(co):
        a = math.atan2(co.y, co.x)
        k = (0.35 + 0.65 * abs(math.cos(4 * a)) ** 1.4)
        return Vector((co.x * r * k, co.y * r * k, co.z * 0.05 * (0.6 + 0.4 * k)))
    deform(ob, shape)
    smooth(ob)
    assign(ob, material(f"{name}Mat", [(0.0, (0.36, 0.16, 0.08)), (1.0, (0.58, 0.30, 0.14))], coord="r", lo=0.0, hi=r,
                        rough=0.4, coat=0.4, bump=0.3, bump_scale=30))
    return ob


def cinnamon_bun():
    turns = 2.6
    w = 0.24
    pts = []
    n = 400
    for k in range(n + 1):
        t = k / n
        th = 2 * math.pi * turns * t
        r = 0.06 + w * th / (2 * math.pi)
        pts.append((r * math.cos(th), r * math.sin(th), 0.10 * (1 - t) ** 1.2))
    rmax = 0.06 + w * turns

    def rad(t):
        return 0.135 * (1 - 0.15 * t) * (1 - 0.55 * smoothstep(0.88, 1.0, t))
    bun = sweep("CinnamonBun", pts, rad, segs=40, step=0.01, section=(1.9, 0.92), power=3.0)
    mat = material("BunDough", [(0.0, (1.0, 1.0, 1.0)), (1.0, (1.0, 1.0, 1.0))], rough=0.45, sss=0.35,
                   sss_radius=(1, 0.7, 0.4), coat=0.3, bump=0.15, bump_scale=18)
    uv_pattern(mat, [(0.0, (0.98, 0.76, 0.42)), (0.14, (0.92, 0.62, 0.28)), (0.3, (0.82, 0.48, 0.18)),
                     (0.5, (0.80, 0.46, 0.16)), (0.62, (0.62, 0.30, 0.10)), (0.72, (0.46, 0.20, 0.07)),
                     (0.82, (0.50, 0.22, 0.08)), (0.9, (0.86, 0.56, 0.24)), (1.0, (0.98, 0.76, 0.42))], fu=0.0, fv=1.0)
    assign(bun, mat)
    parts = [bun]
    icing = material("BunIcing", [(0.0, (0.95, 0.95, 0.97)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=0.5,
                     rough=0.15, sss=0.4, coat=0.8, coat_rough=0.04)
    bpy.context.view_layer.update()
    for j, (y0, amp) in enumerate(((-0.42, 0.10), (-0.10, 0.12), (0.22, 0.11), (0.50, 0.09))):
        line = []
        for k in range(80):
            t = k / 79
            x = -rmax * 0.95 + 2 * rmax * 0.95 * t
            y = y0 + amp * math.sin(t * math.pi * 7 + j)
            if math.hypot(x, y) > rmax * 0.92:
                continue
            line.append((x, y, surface_z(bun, x, y, 0.1) + 0.02))
        if len(line) > 3:
            tb = sweep(f"BunIcing{j}", line, 0.034, segs=12, step=0.01, section=(0.75, 1.0))
            assign(tb, icing)
            parts.append(tb)
    return rotate_all(parts, (math.radians(16), 0, math.radians(-10)))


M.MODELS.update({
    "pumpkin": pumpkin,
    "dish_pumpkin_soup": dish_pumpkin_soup,
    "caramel_apple": caramel_apple,
    "ghost_cookie": ghost_cookie,
    "candy_corn": candy_corn,
    "marshmallow": marshmallow,
    "dish_hot_cocoa": dish_hot_cocoa,
    "gingerbread": gingerbread,
    "candy_cane": candy_cane,
    "mandarin": mandarin,
    "dish_sundae": dish_sundae,
    "lollipop": lollipop,
    "cotton_candy": cotton_candy,
    "cake_slice": cake_slice,
    "dish_kebab": dish_kebab,
    "watermelon": watermelon,
    "lemonade": lemonade,
    "smores": smores,
    "apple": apple,
    "dish_charlotte": dish_charlotte,
    "chestnuts": chestnuts,
    "cider": cider,
    "cinnamon_bun": cinnamon_bun,
})
