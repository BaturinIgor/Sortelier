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


def sweep(name, pts, radius, segs=32, step=0.02, caps=True, section=(1.0, 1.0), up=(0.0, 0.0, 1.0)):
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
    for c, t, nv, bv, r, u in frames:
        for j in range(segs):
            th = 2 * math.pi * j / segs
            verts.append(c + (nv * math.cos(th) * sx + bv * math.sin(th) * sy) * r)
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


def settle(objs, frames=90, passive=(), floor=0.0, friction=0.9, margin=0.002):
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
    for o in list(objs) + passive:
        for s in scene.objects:
            s.select_set(False)
        bpy.context.view_layer.objects.active = o
        o.select_set(True)
        act = o in objs
        bpy.ops.rigidbody.object_add(type="ACTIVE" if act else "PASSIVE")
        rb = o.rigid_body
        rb.collision_shape = "CONVEX_HULL" if act else "MESH"
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


def glass_mat(name, tint=(0.94, 0.97, 1.0)):
    return material(name, [(0.0, tint), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.0, hi=1.5, rough=0.03,
                    transmission=1.0, coat=0.3)


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


def plate_colored(name, r, inner, outer):
    ob = plate(name, r, (inner, outer))
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
    lf = leaf("PLeaf", 0.92, 0.60, fold=0.10, curl=0.10, serr=0.04)
    rotate_all(lf, (0, 0, math.radians(200)))
    move(lf, (0.14 * math.cos(math.radians(200)), 0.14 * math.sin(math.radians(200)), 0))
    drape(lf, pumpkin_top_z, 0.025)
    parts += lf
    return rotate_all(parts, (math.radians(8), 0, math.radians(10)))


def toast_slice(name, scale=1.0, thick=0.16):
    ob = profile_prism(name, [(x * scale, y * scale) for x, y in M.toast_outline()], thick, -thick / 2)
    bevel(ob, 0.045, 4, 30)
    smooth(ob, 40)
    crust = material(f"{name}Crust", [(0.0, (0.66, 0.34, 0.10)), (1.0, (0.82, 0.48, 0.16))], coord="y", lo=0.0,
                     hi=1.7 * scale, rough=0.45, sss=0.15, coat=0.3, bump=0.1, bump_scale=16)
    crumb = material(f"{name}Toast", [(0.0, (0.86, 0.56, 0.22)), (0.6, (0.96, 0.72, 0.38)), (1.0, (0.90, 0.60, 0.26))],
                     coord="r", lo=0.0, hi=1.0 * scale, rough=0.6, sss=0.2, bump=0.45, bump_scale=26, bump_detail=8,
                     vary=0.2, vary_scale=5)
    add_speckles(crumb, (0.70, 0.40, 0.14), scale=30, threshold=0.66, strength=0.6)
    assign_faces(ob, crust, [(lambda n, c: abs(n.z) > 0.92, crumb)])
    return ob


def dish_pumpkin_soup():
    parts = [plate("SoupPlate", 1.72, ((0.95, 0.93, 0.90), (1.0, 0.99, 0.97)))]
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
    move(group, (0, 0, dz))
    parts += group
    # гренка лежит на тарелке, краем заходит под стенку миски
    phi = math.radians(-50)
    toast = toast_slice("SoupToast", 0.5, 0.15)
    toast.rotation_euler = (math.radians(4), 0, phi - math.radians(90))
    toast.location = (0.62 * math.cos(phi), 0.62 * math.sin(phi), 0.1 + 0.075)
    parts.append(toast)
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
    nut = material("NutMat", [(0.0, (0.86, 0.66, 0.40)), (1.0, (0.98, 0.88, 0.66))], coord="z", lo=-0.05, hi=0.05,
                   rough=0.45, coat=0.3, sss=0.2)
    rnd = random.Random(11)
    placed = []
    tries = 0
    while len(placed) < 46 and tries < 3000:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi)
        cz = rnd.uniform(-0.82, 0.12)
        cr = math.sqrt(max(0.0, 1 - cz * cz))
        co = Vector((cr * math.cos(a), cr * math.sin(a), cz))
        if cz > thr(a) - 0.18:
            continue
        p = apple_shape(co) * 1.0
        p = Vector((p.x * 1.025, p.y * 1.025, p.z))
        if any((p - q).length < 0.15 for q in placed):
            continue
        placed.append(p)
        ch = sphere(f"Nut{len(placed)}", 1.0, 12, 8)
        ch.scale = (rnd.uniform(0.045, 0.07), rnd.uniform(0.035, 0.055), rnd.uniform(0.03, 0.045))
        apply_transform(ch)
        push_normals(ch, lambda c, n, s=rnd.random() * 10: 0.012 * fbm(c * 30 + Vector((s, 0, 0))))
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


def candy_corn_piece(name, mat, w=0.80, h=0.95, th=0.40):
    outline = circles_hull([(-w / 2 + 0.15, -h / 2 + 0.15, 0.15), (w / 2 - 0.15, -h / 2 + 0.15, 0.15),
                            (0.0, h / 2 - 0.07, 0.07), (0.0, -h / 2 + 0.02, 0.06)], 28)
    ob = profile_prism(name, outline, th, -th / 2)
    bevel(ob, 0.13, 5, 30)
    subdivide(ob, 1)

    def taper(co):
        t = (co.y + h / 2) / h
        k = 1.0 - 0.45 * max(0.0, t) ** 1.4
        return Vector((co.x * (1 + 0.04 * (1 - t)), co.y, co.z * k))
    deform(ob, taper)
    smooth(ob)
    assign(ob, mat)
    return ob


def candy_corn():
    mat = material("CandyCorn", [(0.0, (0.98, 0.70, 0.06)), (0.36, (1.0, 0.80, 0.14)), (0.40, (1.0, 0.50, 0.06)),
                                 (0.66, (1.0, 0.56, 0.10)), (0.70, (1.0, 0.98, 0.94)), (1.0, (1.0, 1.0, 1.0))],
                   coord="y", lo=-0.48, hi=0.48, rough=0.22, sss=0.4, sss_radius=(1.0, 0.7, 0.4), coat=0.6,
                   coat_rough=0.08)
    parts = []
    rnd = random.Random(21)
    # роняем штучки горсткой, физика укладывает их в кучку
    for i in range(9):
        p = candy_corn_piece(f"Corn{i}", mat)
        a = rnd.uniform(0, 2 * math.pi)
        r = 0.25 * math.sqrt(rnd.random())
        p.location = (r * math.cos(a), r * math.sin(a), 0.4 + 0.55 * i)
        p.rotation_euler = (rnd.uniform(0, 6.3), rnd.uniform(0, 6.3), rnd.uniform(0, 6.3))
        parts.append(p)
    return settle(parts, 120)


M.MODELS.update({
    "pumpkin": pumpkin,
    "dish_pumpkin_soup": dish_pumpkin_soup,
    "caramel_apple": caramel_apple,
    "ghost_cookie": ghost_cookie,
    "candy_corn": candy_corn,
})
