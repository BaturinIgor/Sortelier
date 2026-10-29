"""Покупатели Sortelier: аватары по пояс в стиле мягких игрушек, 4 настроения.

Запуск: python customers.py <папка вывода> [--only 0,3] [--moods happy,joy] [--size 256] [--samples 64]
Выход: customer_<n>_<mood>.png, mood: happy, wait, upset, joy.

Лицо: глаза с радужкой, зрачком и бликами, веки и брови по настроению, рот-накладка по форме настроения,
румянец нарисован в материале кожи. Волосы собраны из прядей (strand) поверх темной основы, шапки со швами
и строчкой, одежда с воротниками, пуговицами, фактурой ткани и складками.

Кадр зафиксирован таблицей FRAMES (камера прежних спрайтов): игра раскладывает прилавок по этим спрайтам,
поэтому прически и шапки не должны менять кадр. Новый образ без записи в FRAMES получает кадр по границам.
"""
import argparse
import math
import os
import random
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import models as M  # noqa: E402
import render as R  # noqa: E402

MOODS = ("happy", "wait", "upset", "joy")

SKIN = {
    "light": (1.0, 0.86, 0.75),
    "fair": (0.98, 0.79, 0.66),
    "olive": (0.92, 0.73, 0.55),
    "tan": (0.86, 0.63, 0.45),
    "brown": (0.68, 0.46, 0.31),
    "dark": (0.48, 0.32, 0.22),
}

# радужка
EYES = {
    "brown": (0.42, 0.24, 0.12),
    "hazel": (0.52, 0.40, 0.16),
    "blue": (0.24, 0.50, 0.86),
    "green": (0.26, 0.58, 0.34),
    "violet": (0.56, 0.32, 0.80),
    "dark": (0.26, 0.16, 0.10),
}

# кожа, прическа, цвет волос, одежда, аксессуар, {одежда (garment), глаза (eyes), пробор (part)}
CUSTOMERS = [
    ("fair", "short", (0.36, 0.22, 0.12), (0.26, 0.56, 0.95), None, {"garment": "crew", "eyes": "brown", "part": 1}),
    ("light", "bob", (0.95, 0.72, 0.30), (0.95, 0.40, 0.52), None, {"garment": "peter", "eyes": "blue"}),
    ("brown", "curly", (0.16, 0.10, 0.07), (1.0, 0.78, 0.20), None, {"garment": "hoodie", "eyes": "dark"}),
    ("tan", "bun", (0.20, 0.12, 0.08), (0.36, 0.78, 0.52), "glasses", {"garment": "shirt", "eyes": "hazel"}),
    ("olive", "cap", (0.30, 0.18, 0.10), (0.95, 0.35, 0.25), None, {"garment": "polo", "eyes": "brown"}),
    ("dark", "short", (0.10, 0.07, 0.05), (0.62, 0.42, 0.92), "glasses", {"garment": "turtle", "eyes": "dark", "part": -1}),
    ("fair", "beanie", (0.62, 0.30, 0.12), (0.20, 0.70, 0.78), None, {"garment": "sweater", "eyes": "green"}),
    ("light", "pony", (0.72, 0.36, 0.14), (1.0, 0.62, 0.22), None, {"garment": "stripes", "eyes": "green"}),
    ("tan", "bangs", (0.12, 0.08, 0.06), (0.92, 0.28, 0.42), None, {"garment": "cardigan", "eyes": "dark"}),
    ("brown", "bald", (0.10, 0.07, 0.05), (0.32, 0.46, 0.72), "moustache", {"garment": "shirt", "eyes": "dark", "pocket": True}),
    # гурман: цилиндр, монокль, усы, бабочка, фрак
    ("fair", "tophat", (0.82, 0.80, 0.78), (0.10, 0.10, 0.13), "gourmet", {"garment": "tailcoat", "eyes": "blue"}),
    # гости сезонных ивентов (Guests.swift): 11 ведьмочка, 12 Снегурочка, 13 конфетная фея, 14 ковбой, 15 фермер
    ("light", "witch", (0.92, 0.42, 0.12), (0.44, 0.20, 0.66), "witch", {"garment": "cape", "eyes": "green"}),
    ("fair", "snowmaiden", (0.98, 0.84, 0.46), (0.42, 0.66, 0.95), "snowmaiden", {"garment": "furcoat", "eyes": "blue"}),
    ("tan", "fairy", (1.0, 0.52, 0.74), (1.0, 0.62, 0.78), "fairy", {"garment": "ruffle", "eyes": "violet"}),
    ("olive", "cowboy", (0.26, 0.15, 0.08), (0.82, 0.28, 0.16), "bandana", {"garment": "western", "eyes": "brown"}),
    ("fair", "straw", (0.62, 0.30, 0.12), (0.34, 0.62, 0.30), "freckles", {"garment": "plaid", "eyes": "green"}),
]

HEAD_Z = 1.25
HEAD_C = Vector((0.0, 0.0, HEAD_Z))
HEAD_AX = Vector((1.0, 0.96, 0.98))
BODY_C = Vector((0.0, 0.1, -0.2))
BODY_AX = Vector((1.38, 0.82, 0.78))
CAM_AZ, CAM_EL = math.radians(8), math.radians(6)

# Камера прежних спрайтов (азимут 8, высота 6 градусов): положение и ortho_scale для каждого образа.
# Снято со старой сборки (кадр по границам с полем 1.04), одинаково для всех настроений.
FRAMES = {
    0: ((1.397055, -9.840559, 2.168623), 3.079839),
    1: ((1.397028, -9.840369, 2.186770), 3.079839),
    2: ((1.397959, -9.846994, 2.260083), 3.079839),
    3: ((1.397524, -9.843898, 2.265244), 3.079839),
    4: ((1.397028, -9.840366, 2.199171), 3.079839),
    5: ((1.397055, -9.840559, 2.168623), 3.079839),
    6: ((1.397817, -9.845985, 2.260187), 3.079839),
    7: ((1.397055, -9.840559, 2.168623), 3.079839),
    8: ((1.397055, -9.840559, 2.168623), 3.079839),
    9: ((1.397193, -9.841541, 2.082889), 3.079839),
    10: ((1.397239, -9.841866, 2.435048), 3.430864),
    11: ((1.391048, -9.842593, 2.423235), 3.632755),
    12: ((1.397180, -9.841451, 2.205234), 3.079839),
    13: ((1.398284, -9.849307, 2.205608), 3.079839),
    14: ((1.390400, -9.843068, 2.247991), 3.745853),
    15: ((1.390377, -9.843014, 2.246505), 3.628711),
}


# MARK: - Поверхности

def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def head_surface_y(x, dz, r=1.0):
    """Где передняя поверхность головы (y < 0) для точки (x, dz)."""
    return -math.sqrt(max(0.0, r * r - x * x - dz * dz))


def at_face(ob, x, dz, inset=0.0):
    y = head_surface_y(x, dz) * 0.97 + inset
    ob.location = (x, y, HEAD_Z + dz)
    return ob


def ell_front(c, ax):
    """Передняя сторона эллипсоида: surf(x, z, lift) -> (точка над (x, z) со сдвигом по нормали, нормаль)."""
    def surf(x, z, lift=0.0):
        dx, dz = (x - c.x) / ax.x, (z - c.z) / ax.z
        q = max(0.0, 1 - dx * dx - dz * dz)
        y = c.y - ax.y * math.sqrt(q)
        n = Vector((dx / ax.x, (y - c.y) / ax.y ** 2, dz / ax.z)).normalized()
        return Vector((x, y, z)) + n * lift, n
    return surf


head_surf = ell_front(HEAD_C, HEAD_AX)
body_surf = ell_front(BODY_C, BODY_AX)


def hp(th, ph, r=1.0):
    """Точка на голове: th - угол от макушки, ph - азимут от лица (+ вправо в кадре), в градусах."""
    t, p = math.radians(th), math.radians(ph)
    return HEAD_C + Vector((r * HEAD_AX.x * math.sin(t) * math.sin(p), -r * HEAD_AX.y * math.sin(t) * math.cos(p),
                            r * HEAD_AX.z * math.cos(t)))


def head_r(p):
    d = p - HEAD_C
    return Vector((d.x / HEAD_AX.x, d.y / HEAD_AX.y, d.z / HEAD_AX.z)).length


def push_out(p, r):
    """Точку внутри эллипсоида головы радиуса r выталкиваем на него."""
    d = p - HEAD_C
    q = Vector((d.x / HEAD_AX.x, d.y / HEAD_AX.y, d.z / HEAD_AX.z))
    if q.length >= r:
        return p
    q = q.normalized() * r
    return HEAD_C + Vector((q.x * HEAD_AX.x, q.y * HEAD_AX.y, q.z * HEAD_AX.z))


# MARK: - Меши

def ellipsoid(name, scale, mat, segs=32, rings=20):
    ob = M.sphere(name, 1.0, segs, rings)
    ob.scale = scale
    M.apply_transform(ob)
    M.smooth(ob)
    M.assign(ob, mat)
    return ob


def placed(ob, loc):
    """Ставит объект и запекает положение: координаты материала становятся мировыми."""
    ob.location = loc
    return M.apply_transform(ob)


def mesh_obj(name, verts, faces, mat=None, uvs=None, recalc=False):
    ob = M.from_data(name, verts, faces)
    me = ob.data
    if recalc:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        bm.to_mesh(me)
        bm.free()
    if uvs:
        uv = me.uv_layers.new(name="UVMap")
        for poly in me.polygons:
            for li in poly.loop_indices:
                uv.data[li].uv = uvs[me.loops[li].vertex_index]
    M.smooth(ob)
    if mat:
        M.assign(ob, mat)
    return ob


def blobs(name, mat, mats, segs=12, rings=8):
    """Много мелких эллипсоидов одним мешем: строчка, крапинки, жемчуг. mats - матрицы (сдвиг, поворот, масштаб)."""
    bm = bmesh.new()
    for mx in mats:
        bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=1.0, matrix=mx)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = M.link(bpy.data.objects.new(name, me))
    M.smooth(ob)
    return M.assign(ob, mat)


def blob_matrix(center, axis, size, up=None):
    """Эллипсоид size=(вдоль axis, поперек, по нормали up) с центром center."""
    a = Vector(axis).normalized()
    u = Vector(up) if up is not None else Vector((0, -1, 0))
    u = (u - a * u.dot(a))
    if u.length < 1e-6:
        u = a.orthogonal()
    u.normalize()
    b = u.cross(a)
    rot = Matrix((a, b, u)).transposed().to_4x4()
    return Matrix.Translation(center) @ rot @ Matrix.Diagonal((size[0], size[1], size[2], 1.0))


def pillow(name, mat, surf, u0, u1, top, bot, lift=0.03, base=-0.012, nu=32, nv=10, power=0.5, end=0.3,
           origin=(0.0, 0.0), angle=0.0):
    """Выпуклая накладка на поверхность: область между кривыми bot(u) и top(u) для u в [u0, u1].

    Координаты (u, w) поворачиваются на angle и сдвигаются в origin -> (x, z) поверхности surf.
    По краям накладка уходит под поверхность (base), посередине поднимается на lift: мягкий пластилиновый край.
    """
    ca, sa = math.cos(angle), math.sin(angle)
    verts, faces = [], []
    for i in range(nu + 1):
        s = i / nu
        u = u0 + (u1 - u0) * s
        wt, wb = top(u), bot(u)
        e = math.sin(math.pi * s) ** end if end else 1.0
        for j in range(nv + 1):
            v = j / nv
            w = wb + (wt - wb) * v
            x = origin[0] + u * ca - w * sa
            z = origin[1] + u * sa + w * ca
            h = base + (lift - base) * (math.sin(math.pi * v) ** power) * e
            p, _ = surf(x, z, h)
            verts.append(p)
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + nv + 1, a + nv + 2, a + 1))
    return mesh_obj(name, verts, faces, mat)


def stroke(name, mat, surf, u0, u1, center, half, lift=0.025, **kw):
    """Мазок вдоль кривой center(u) с полутолщиной half(u)."""
    return pillow(name, mat, surf, u0, u1, lambda u: center(u) + half(u), lambda u: center(u) - half(u), lift=lift, **kw)


def catmull(pts, n=10):
    P = [Vector(p) for p in pts]
    if len(P) < 3:
        return [P[0].lerp(P[-1], i / n) for i in range(n + 1)]
    ext = [P[0] * 2 - P[1]] + P + [P[-1] * 2 - P[-2]]
    out = []
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(n):
            t = k / n
            t2, t3 = t * t, t * t * t
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t3))
    out.append(P[-1])
    return out


def resample(pts, n):
    cum = [0.0]
    for a, b in zip(pts, pts[1:]):
        cum.append(cum[-1] + (b - a).length)
    L = cum[-1]
    out, j = [], 0
    for i in range(n):
        s = L * i / (n - 1)
        while j < len(cum) - 2 and cum[j + 1] < s:
            j += 1
        seg = cum[j + 1] - cum[j]
        out.append(pts[j].lerp(pts[j + 1], (s - cum[j]) / seg if seg > 0 else 0.0))
    return out, L


def strand(name, mat, ctrl, width, thick, n=30, tip=0.35, root=0.12, root_w=0.7, flat=0.4, groove=0.22,
           ring=16, blunt=False, rmin=None, up=None, bulge=0.12):
    """Прядь: сплющенная трубка вдоль сглаженного пути. Ширина вбок, толщина от головы (или по up),
    канавка посередине, острый (или тупой) кончик. rmin(t) - на сколько прядь отстоит от головы (радиус)."""
    path, L = resample(catmull(ctrl, 10), n)
    if rmin is not None:
        path = [push_out(p, rmin(i / (n - 1))) for i, p in enumerate(path)]
    verts, uvs, faces = [], [], []

    def prof(t):
        r = root_w + (1 - root_w) * smoothstep(0.0, root, t)
        if blunt:
            tp = math.sqrt(max(0.0, 1 - ((t - 0.9) / 0.1) ** 2)) if t > 0.9 else 1.0
            tp = 0.35 + 0.65 * tp
        else:
            tp = (1 - smoothstep(1 - tip, 1.0, t)) ** 0.8
        return max(0.004, r * tp * (1 + bulge * math.sin(math.pi * t)))

    frames = []
    for i, p in enumerate(path):
        t = i / (n - 1)
        T = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        u0 = (up(p) if callable(up) else Vector(up)) if up is not None else (p - HEAD_C)
        N = (u0 - T * u0.dot(T))
        if N.length < 1e-6:
            N = T.orthogonal()
        N.normalize()
        B = T.cross(N).normalized()
        frames.append((p, T, N, B, prof(t)))
    for i, (p, T, N, B, k) in enumerate(frames):
        w = width * k
        h = thick * (max(min(1.0, k), 0.55) if blunt else min(1.0, k) ** 0.55)
        for j in range(ring + 1):
            a = 2 * math.pi * j / ring
            cx, sy = math.cos(a), math.sin(a)
            y = sy * h if sy >= 0 else sy * h * flat
            if sy > 0:
                y -= groove * h * sy * math.exp(-(cx / 0.32) ** 2)
            verts.append(p + B * (cx * w) + N * y)
            uvs.append((i / (n - 1), j / ring))
    rw = ring + 1
    for i in range(n - 1):
        for j in range(ring):
            a = i * rw + j
            faces.append((a, a + rw, a + rw + 1, a + 1))
    # торцы
    p0, T0 = frames[0][0], frames[0][1]
    c0 = len(verts)
    verts.append(p0 - T0 * thick * 0.4)
    uvs.append((0.0, 0.5))
    for j in range(ring):
        faces.append((c0, j + 1, j))
    pe, Te = frames[-1][0], frames[-1][1]
    c1 = len(verts)
    verts.append(pe + Te * (thick * 0.5 if blunt else 0.004))
    uvs.append((1.0, 0.5))
    last = (n - 1) * rw
    for j in range(ring):
        faces.append((c1, last + j, last + j + 1))
    return mesh_obj(name, verts, faces, mat, uvs, recalc=True)


def tube(name, pts, radius, mat, taper=(1.0, 1.0), res=12):
    ob = M.tube(name, pts, radius, taper=taper, res=res)
    M.smooth(ob)
    return M.assign(ob, mat)


# MARK: - Материалы

def shade(c, k):
    return tuple(min(1.0, v * k) for v in c)


def _node(nodes, kind, **inputs):
    n = nodes.new(kind)
    for k, v in inputs.items():
        if k in ("operation", "blend_type", "data_type", "wave_type", "bands_direction", "direction_type", "uv_map"):
            setattr(n, k, v)
        else:
            n.inputs[k].default_value = v
    return n


def _math(nodes, links, op, a, b=None, c=None):
    n = nodes.new("ShaderNodeMath")
    n.operation = op
    for k, v in enumerate((a, b, c)):
        if v is None:
            continue
        if hasattr(v, "node"):
            links.new(v, n.inputs[k])
        else:
            n.inputs[k].default_value = v
    return n.outputs[0]


def _bump(mat, height, strength=0.2, distance=0.02):
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    b = nodes.new("ShaderNodeBump")
    b.inputs["Strength"].default_value = strength
    b.inputs["Distance"].default_value = distance
    links.new(height, b.inputs["Height"])
    if bsdf.inputs["Normal"].links:
        links.new(bsdf.inputs["Normal"].links[0].from_socket, b.inputs["Normal"])
    links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return b


def _scale_color(mat, fac):
    """Умножает базовый цвет на fac (0..1)."""
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    src = bsdf.inputs["Base Color"].links[0].from_socket
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    mix.blend_type = "MULTIPLY"
    mix.inputs[0].default_value = 1.0
    ins = [i for i in mix.inputs if i.type == "RGBA"]
    out = [o for o in mix.outputs if o.type == "RGBA"][0]
    links.new(src, ins[0])
    comb = nodes.new("ShaderNodeCombineColor")
    for k in range(3):
        links.new(fac, comb.inputs[k])
    links.new(comb.outputs[0], ins[1])
    links.new(out, bsdf.inputs["Base Color"])


def hair_mat(name, col, lo=HEAD_Z - 0.9, hi=HEAD_Z + 1.15, k=1.0, lines=7.0, aniso=0.55):
    """Волосы: градиент снизу вверх, тонкие бороздки вдоль пряди (по UV) и вытянутый вдоль пряди блик."""
    col = shade(col, k)
    mat = M.material(name, [(0.0, shade(col, 0.5)), (0.55, col), (1.0, tuple(min(1, c * 1.25 + 0.03) for c in col))],
                     coord="z", lo=lo, hi=hi, rough=0.36, coat=0.25, coat_rough=0.2)
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    uvn = _node(nodes, "ShaderNodeUVMap", uv_map="UVMap")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(uvn.outputs["UV"], sep.inputs[0])
    wave = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY", sep.outputs["Y"], 2 * math.pi * lines))
    _scale_color(mat, _math(nodes, links, "MULTIPLY_ADD", wave, 0.07, 0.93))
    _bump(mat, wave, strength=0.12, distance=0.01)
    tan = _node(nodes, "ShaderNodeTangent", direction_type="UV_MAP", uv_map="UVMap")
    links.new(tan.outputs["Tangent"], bsdf.inputs["Tangent"])
    bsdf.inputs["Anisotropic"].default_value = aniso
    return mat


def skin_mat(col, blush=0.5, nose=0.3):
    darker = shade(col, 0.86)
    mat = M.material("Skin", [(0.0, darker), (0.6, col), (1.0, shade(col, 1.04))], coord="z", lo=0.3, hi=2.2,
                     rough=0.45, sss=0.32, sss_radius=(1.0, 0.5, 0.32), sss_scale=0.06, coat=0.12, coat_rough=0.25)
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    total = None
    spots = []
    for side in (-1, 1):
        p, _ = head_surf(side * 0.52, HEAD_Z - 0.17)
        spots.append((p, (0.17, 0.3, 0.11), blush))
    pn, _ = head_surf(0.0, HEAD_Z - 0.11)
    spots.append((pn, (0.07, 0.08, 0.06), nose))
    for c, sig, amt in spots:
        if amt <= 0:
            continue
        sub = _node(nodes, "ShaderNodeVectorMath", operation="SUBTRACT")
        links.new(tc.outputs["Object"], sub.inputs[0])
        sub.inputs[1].default_value = tuple(c)
        div = _node(nodes, "ShaderNodeVectorMath", operation="DIVIDE")
        links.new(sub.outputs[0], div.inputs[0])
        div.inputs[1].default_value = sig
        dot = _node(nodes, "ShaderNodeVectorMath", operation="DOT_PRODUCT")
        links.new(div.outputs[0], dot.inputs[0])
        links.new(div.outputs[0], dot.inputs[1])
        e = _math(nodes, links, "EXPONENT", _math(nodes, links, "MULTIPLY", dot.outputs["Value"], -1.0))
        v = _math(nodes, links, "MULTIPLY", e, amt)
        total = v if total is None else _math(nodes, links, "ADD", total, v)
    if total is not None:
        M._mix_over(mat, _math(nodes, links, "MINIMUM", total, 1.0), (1.0, 0.45, 0.48))
    return mat


def fabric_mat(name, col, rough=0.62, weave=60.0, bump=0.14, sheen=0.45, knit=False, coat=0.05, lo=-0.7, hi=0.65):
    """Ткань: градиент, полотняное плетение (две системы полос) или трикотаж (рубчик и петли) в рельефе."""
    mat = M.material(name, [(0.0, shade(col, 0.7)), (0.6, col), (1.0, shade(col, 1.07))], coord="z", lo=lo, hi=hi,
                     rough=rough, sheen=sheen, coat=coat, vary=0.05, vary_scale=4.0)
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    if knit:
        # рубчик вертикальными столбиками петель: |sin| по x и легкие "елочки" по z
        a = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY", sep.outputs["X"], weave))
        b = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY",
                                              _math(nodes, links, "ADD", sep.outputs["Z"],
                                                    _math(nodes, links, "MULTIPLY",
                                                          _math(nodes, links, "ABSOLUTE", a), 0.04)), weave * 1.4))
        h = _math(nodes, links, "ADD", _math(nodes, links, "ABSOLUTE", a), _math(nodes, links, "MULTIPLY", b, 0.35))
        _bump(mat, h, strength=bump * 1.8, distance=0.02)
        _scale_color(mat, _math(nodes, links, "MULTIPLY_ADD", _math(nodes, links, "ABSOLUTE", a), 0.12, 0.88))
    else:
        a = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY", sep.outputs["X"], weave))
        b = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY", sep.outputs["Z"], weave))
        h = _math(nodes, links, "MULTIPLY", a, b)
        _bump(mat, h, strength=bump, distance=0.01)
    return mat


def add_bands(mat, color, axis="Z", freq=9.0, width=0.3, offset=0.0, soft=0.04):
    """Полосы ткани вдоль оси (в координатах объекта): тельняшка, клетка."""
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    s = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY",
                                          _math(nodes, links, "ADD", sep.outputs[axis], offset), freq * 2 * math.pi))
    thr = math.cos(math.pi * width)
    m = _node(nodes, "ShaderNodeMapRange")
    m.inputs["From Min"].default_value = thr - soft
    m.inputs["From Max"].default_value = thr + soft
    links.new(s, m.inputs["Value"])
    return M._mix_over(mat, m.outputs["Result"], color)


def glossy(name, col, rough=0.15, coat=0.8, **kw):
    return M.flat(name, col, rough=rough, coat=coat, **kw)


def emissive(name, col, strength=1.2):
    mat = M.flat(name, col, rough=0.3)
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (*M.lin(col), 1)
    b.inputs["Emission Strength"].default_value = strength
    return mat


def gold_mat(name="Gold"):
    return M.material(name, [(0.0, (0.80, 0.55, 0.12)), (1.0, (1.0, 0.86, 0.42))], coord="nz", lo=-1.0, hi=1.0,
                      rough=0.22, metal=1.0)


# MARK: - Лицо

EYE_X, EYE_DZ = 0.35, 0.02
EYE_A, EYE_B, EYE_D = 0.118, 0.152, 0.062


def eye_frame(side):
    p, n = head_surf(side * EYE_X, HEAD_Z + EYE_DZ)
    q = (-n).to_track_quat("Y", "Z")
    return Matrix.Translation(p - n * 0.014) @ q.to_matrix().to_4x4()


def local_ellipsoid(name, mx, center, axes, mat, segs=32, rings=20):
    ob = M.sphere(name, 1.0, segs, rings)
    ob.data.transform(Matrix.Translation(center) @ Matrix.Diagonal((*axes, 1.0)))
    ob.matrix_world = mx
    M.smooth(ob)
    return M.assign(ob, mat)


def dome_y(u, w, a=EYE_A, b=EYE_B, d=EYE_D):
    return -d * math.sqrt(max(0.0, 1 - (u / a) ** 2 - (w / b) ** 2))


def eye(side, mood, iris_col, mats, gaze=(0.0, 0.0)):
    """Глаз: темная основа, радужка с градиентом, зрачок, два блика; веко и ресничная линия по настроению."""
    mx = eye_frame(side)
    A, B, D = EYE_A, EYE_B, EYE_D
    gx, gz = gaze[0] * A, gaze[1] * B
    parts = [local_ellipsoid(f"EyeBase{side}", mx, (0, 0, 0), (A, D, B), mats["eye_dark"])]
    iris_m = M.material(f"Iris{side}", [(0.0, shade(iris_col, 1.55)), (0.45, iris_col), (1.0, shade(iris_col, 0.32))],
                        coord="z", lo=-B * 0.8, hi=B * 0.75, rough=0.12, coat=1.0, coat_rough=0.03)
    parts.append(local_ellipsoid(f"Iris{side}", mx, (gx, -0.006, gz - B * 0.03), (A * 0.82, D * 1.04, B * 0.84), iris_m))
    parts.append(local_ellipsoid(f"Pupil{side}", mx, (gx + 0.004, -0.012, gz + 0.004), (A * 0.4, D * 1.08, B * 0.44),
                                 mats["pupil"]))
    for k, (cu, cw, sa, sb) in enumerate(((0.34, 0.36, 0.3, 0.27), (-0.3, -0.42, 0.14, 0.12))):
        u, w = gx + cu * A, gz + cw * B
        y = dome_y(u - gx * 0.0, w, A * 0.95, B * 0.95, D * 1.1) - 0.004
        parts.append(local_ellipsoid(f"Catch{side}{k}", mx, (u, y, w), (A * sa, 0.008, B * sb), mats["catch"], 16, 10))
    # верхнее веко: срез эллипсоида плоскостью z = zc + k*u (u к виску со знаком side)
    lid = {"happy": None, "joy": None, "wait": (0.05, 0.0), "upset": (0.2, 0.42)}[mood]
    if lid:
        zc, tilt = lid
        kk = tilt * side  # внутренний край (к носу) ниже
        LA, LD, LB = A * 1.12, D * 1.5, B * 1.1
        ob = M.sphere(f"Lid{side}", 1.0, 48, 32)
        ob.data.transform(Matrix.Diagonal((LA, LD, LB, 1.0)))
        M.bisect(ob, (0, 0, zc * B), (kk, 0, -1), fill=True)
        M.bevel(ob, 0.006, 2, 30)
        ob.matrix_world = mx
        M.smooth(ob)
        M.assign(ob, mats["lid"])
        parts.append(ob)
        pts = []
        for i in range(17):
            u = -LA * 1.02 + 2 * LA * 1.02 * i / 16
            w = zc * B + kk * u
            q = 1 - (u / LA) ** 2 - (w / LB) ** 2
            y = -LD * math.sqrt(max(0.0, q)) - 0.002
            pts.append(mx @ Vector((u, y, w - 0.004)))
        parts.append(tube(f"Lash{side}", pts, 0.017, mats["lash"], taper=(0.6, 0.6)))
    return parts


def joy_eye(side, mats):
    """Зажмуренный от радости глаз: толстая дуга концами вниз."""
    x, cz = side * EYE_X, HEAD_Z + EYE_DZ + 0.02
    L = 0.135
    return [stroke(f"JoyEye{side}", mats["lash"], head_surf, x - L, x + L,
                   lambda u: cz + 0.05 - 0.11 * ((u - x) / L) ** 2,
                   lambda u: 0.026 * (1 - 0.45 * ((u - x) / L) ** 2), lift=0.035, end=0.35, nu=28, nv=8)]


BROWS = {
    # высота, изгиб, наклон (+ внутренний край ниже), толщина
    "happy": (0.30, 0.035, -0.01, 0.028),
    "joy": (0.35, 0.05, -0.03, 0.028),
    "upset": (0.27, 0.0, 0.085, 0.034),
    "wait": (0.26, 0.012, -0.015, 0.026),
}


def brow(side, mat, bz, arch, tilt, th, x=None, L=0.14, name=None):
    """Бровь-мазок: у переносицы толще, к виску тоньше."""
    x = side * EYE_X if x is None else x

    def t(u):
        return side * (u - x) / L  # -1 у переносицы, +1 у виска

    return stroke(name or f"Brow{side}", mat, head_surf, x - L, x + L,
                  lambda u: HEAD_Z + bz + arch * (1 - t(u) ** 2) + tilt * t(u),
                  lambda u: th * (1.0 - 0.38 * t(u)), lift=0.03, end=0.45, nu=28, nv=8)


MOUTH_Z = HEAD_Z - 0.38


def mouth(mood, mats, mz=MOUTH_Z, cx=0.0):
    parts = []
    if mood == "happy":
        W = 0.19
        parts.append(pillow("Mouth", mats["mouth"], head_surf, cx - W, cx + W,
                            lambda u: mz + 0.085 * ((u - cx) / W) ** 2 + 0.012 * (1 - ((u - cx) / W) ** 2),
                            lambda u: mz + 0.085 * ((u - cx) / W) ** 2 - 0.05 * (1 - ((u - cx) / W) ** 2) ** 0.8,
                            lift=0.014, end=0.4, nu=32, nv=8))
    elif mood == "joy":
        W = 0.23

        def top(u):
            t = (u - cx) / W
            return mz + 0.07 + 0.035 * t * t

        def bot(u):
            t = (u - cx) / W
            return mz + 0.105 - 0.27 * max(0.0, 1 - t * t) ** 0.75 - 0.035 * (1 - t * t)

        parts.append(pillow("Mouth", mats["mouth_in"], head_surf, cx - W, cx + W, top, bot, lift=0.01, end=0.25,
                            nu=36, nv=12, power=0.25))
        TW = 0.13
        parts.append(pillow("Tongue", mats["tongue"], head_surf, cx - TW, cx + TW,
                            lambda u: bot(u) + 0.03 + 0.075 * max(0.0, 1 - ((u - cx) / TW) ** 2) ** 0.6,
                            lambda u: bot(u) + 0.004, lift=0.018, end=0.4, nu=24, nv=8))
        EW = 0.165
        parts.append(pillow("Teeth", mats["teeth"], head_surf, cx - EW, cx + EW, lambda u: top(u) - 0.004,
                            lambda u: top(u) - 0.032 * max(0.0, 1 - ((u - cx) / EW) ** 2) ** 0.4,
                            lift=0.015, end=0.3, nu=24, nv=6))
        # губной валик по краю открытого рта: рот читается углублением
        rim = []
        for i in range(48):
            a = 2 * math.pi * i / 48
            t = -math.cos(a)
            u = cx + W * 1.02 * t
            z = top(u) + 0.006 if math.sin(a) > 0 else bot(u) - 0.008
            p, n = head_surf(u, z, 0.006)
            rim.append(p)
        rim.append(rim[0])
        parts.append(tube("MouthRim", rim, 0.013, mats["lip"]))
    elif mood == "upset":
        W = 0.16
        parts.append(stroke("Mouth", mats["mouth"], head_surf, cx - W, cx + W,
                            lambda u: mz + 0.035 - 0.075 * ((u - cx) / W) ** 2,
                            lambda u: 0.024 * (1 - 0.5 * ((u - cx) / W) ** 2), lift=0.016, end=0.45, nu=28, nv=8))
    else:  # wait: короткая ровная черточка, один уголок чуть ниже
        W = 0.1
        parts.append(stroke("Mouth", mats["mouth"], head_surf, cx - W + 0.01, cx + W + 0.01,
                            lambda u: mz + 0.012 - 0.022 * (u - cx) / W,
                            lambda u: 0.019, lift=0.014, end=0.5, nu=24, nv=8))
    return parts


def face(mood, spec_eyes, skin_m, hair_col, brow_col=None, glasses=False):
    lash = glossy("Lash", (0.10, 0.06, 0.06), rough=0.3, coat=0.4)
    mats = {
        "eye_dark": glossy("EyeDark", (0.07, 0.05, 0.06), rough=0.12, coat=1.0),
        "pupil": glossy("Pupil", (0.02, 0.015, 0.02), rough=0.08, coat=1.0),
        "catch": emissive("Catch", (1.0, 1.0, 1.0), 1.4),
        "lid": skin_m,
        "lash": lash,
        "mouth": glossy("Mouth", (0.50, 0.15, 0.15), rough=0.35, coat=0.3),
        "mouth_in": M.material("MouthIn", [(0.0, (0.62, 0.20, 0.22)), (1.0, (0.30, 0.06, 0.08))], coord="z",
                               lo=MOUTH_Z - 0.18, hi=MOUTH_Z + 0.06, rough=0.4, coat=0.3),
        "tongue": M.material("Tongue", [(0.0, (0.98, 0.50, 0.52)), (1.0, (1.0, 0.66, 0.66))], coord="z",
                             lo=MOUTH_Z - 0.18, hi=MOUTH_Z - 0.06, rough=0.35, sss=0.2, coat=0.3),
        "teeth": glossy("Teeth", (1.0, 0.98, 0.95), rough=0.25, coat=0.5),
        "lip": M.flat("Lip", (0.85, 0.42, 0.40), rough=0.4, sss=0.2),
    }
    brow_m = M.flat("Brow", brow_col or shade(hair_col, 0.8), rough=0.45, coat=0.15)
    parts = []
    gaze = {"happy": (0.05, 0.02), "joy": (0.0, 0.0), "upset": (0.0, 0.05), "wait": (-0.28, 0.1)}[mood]
    for side in (-1, 1):
        if mood == "joy":
            parts += joy_eye(side, mats)
        else:
            parts += eye(side, mood, EYES[spec_eyes], mats, gaze)
        bz, arch, tilt, th = BROWS[mood]
        if glasses:
            bz += 0.035
        parts.append(brow(side, brow_m, bz, arch, tilt, th))
    parts += mouth(mood, mats)
    nose = ellipsoid("Nose", (0.068, 0.05, 0.056), skin_m, 24, 16)
    p, n = head_surf(0.0, HEAD_Z - 0.12, 0.0)
    placed(nose, p - n * 0.012)
    parts.append(nose)
    return parts


# MARK: - Волосы

def scalp(name, mat, hairline, r=1.025):
    """Темная основа под прядями: сфера чуть больше головы, срезанная по линии роста hairline(ph) -> th."""
    ob = M.sphere(name, 1.0, 96, 64)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    kill = []
    for f in bm.faces:
        c = f.calc_center_median()
        th = math.degrees(math.acos(max(-1.0, min(1.0, c.z))))
        ph = math.degrees(math.atan2(c.x, -c.y))
        if th > hairline(ph):
            kill.append(f)
    bmesh.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.transform(Matrix.Diagonal((r * HEAD_AX.x, r * HEAD_AX.y, r * HEAD_AX.z, 1.0)))
    ob.location = HEAD_C
    M.apply_transform(ob)
    M.solidify(ob, 0.02, -1.0)
    M.smooth(ob)
    return M.assign(ob, mat)


def lock(name, mats, rnd, pts, width, thick, **kw):
    """Прядь по точкам (th, ph, r) на голове; r - минимальный радиус (прядь лежит на голове и не тонет в ней)."""
    ctrl = [hp(th, ph, r) for th, ph, r in pts]
    rs = [r for _, _, r in pts]

    def rmin(t):
        f = t * (len(rs) - 1)
        i = min(int(f), len(rs) - 2)
        return rs[i] + (rs[i + 1] - rs[i]) * (f - i)
    return strand(name, rnd.choice(mats), ctrl, width, thick, rmin=rmin, **kw)


def hairline_default(front=60.0, side=86.0, back=116.0):
    def f(ph):
        a = abs(((ph + 180) % 360) - 180)
        if a <= 90:
            return front + (side - front) * smoothstep(0, 90, a)
        return side + (back - side) * smoothstep(90, 180, a)
    return f


def fringe_lock_pts(ph_end, th_end, sweep, r0=1.035, origin=(14, None), flick=0.03):
    """Прядь челки: от макушки вперед к линии роста, с заносом кончика вбок."""
    th0, ph0 = origin
    ph0 = ph_end - sweep * 2.2 if ph0 is None else ph0
    return [(th0, ph0, r0 - 0.005), ((th0 + th_end) * 0.5, ph_end - sweep * 0.8, r0 + 0.02),
            (th_end - 8, ph_end - sweep * 0.1, r0 + 0.012), (th_end, ph_end + sweep * 0.5, r0 + flick)]


def hair_short(hm, rnd, part=1, top_r=1.04):
    """Короткая стрижка: макушка-вихор сзади, пряди расходятся во все стороны, челка зачесана вбок."""
    parts = []
    hl = hairline_default(62, 84, 112)
    W = (26, 180 - part * 12)
    n = 15
    for layer in range(2):
        r0 = top_r - 0.012 + layer * 0.022
        for k in range(n):
            ph = -180 + 360 * (k + 0.5 * layer + 0.5) / n + rnd.uniform(-4, 4)
            a = abs(((ph + 180) % 360) - 180)
            th_e = hl(ph) + (2 if layer == 0 else -3) + rnd.uniform(-2, 3)
            if a < 70:
                sw = part * (16 + rnd.uniform(-4, 4))
                pts = [(W[0] - 6, W[1], r0 - 0.01), (10, ph * 0.3 + 180 * (1 if ph >= 0 else -1) * 0.0 - sw, r0 + 0.02),
                       ((th_e + 10) * 0.55, ph - sw * 0.6, r0 + 0.03), (th_e - 6, ph, r0 + 0.02),
                       (th_e + 1, ph + sw * 0.6, r0 + 0.045)]
            else:
                sw = 10 * (1 if ph > 0 else -1) * (1 if a < 150 else 0.5)
                pts = [W + (r0 - 0.01,), ((W[0] + th_e) * 0.5, ph - sw, r0 + 0.025), (th_e - 8, ph, r0 + 0.02),
                       (th_e, ph + sw * 0.7, r0 + 0.05)]
            w = (0.15 if layer == 0 else 0.12) * rnd.uniform(0.9, 1.1)
            parts.append(lock(f"Lock{layer}_{k}", hm, rnd, pts, w, 0.065 * rnd.uniform(0.9, 1.1), tip=0.32))
    return parts


def hair_bob(hm, rnd, long=False, wavy=0.0, fringe=True, start_th=None):
    """Каре (или длинные волосы): пробор сбоку, пряди до подбородка с подкрученными внутрь кончиками, косая челка."""
    parts = []
    P = (16, -38)
    end_th = 150 if long else 138
    n = 18
    for layer in range(2):
        r0 = 1.06 + layer * 0.02
        for k in range(n):
            ph = -180 + 360 * (k + 0.5 * layer + 0.5) / n + rnd.uniform(-3, 3)
            a = abs(((ph + 180) % 360) - 180)
            if a < 62 and fringe:
                continue
            th_e = end_th + rnd.uniform(-4, 3) - (4 if layer else 0)
            wv = wavy * (1 if k % 2 else -1)
            th0 = start_th if start_th is not None else P[0]
            ph0 = P[1] if start_th is None else ph
            pts = [(th0, ph0 if a < 120 else ph * 0.6 + P[1] * 0.4, r0 - 0.02),
                   (48, ph - 4 * (1 if ph > P[1] else -1), r0 + 0.01),
                   (85, ph + wv, r0 + 0.03), (112, ph - wv, r0 + 0.07 + (0.02 if long else 0.0)),
                   (end_th - 12, ph + wv, r0 + 0.1 + (0.05 if long else 0.0)),
                   (th_e, ph + wv * 0.5, r0 + 0.05 + (0.03 if long else 0.0))]
            w = (0.17 if layer == 0 else 0.14) * rnd.uniform(0.9, 1.1)
            parts.append(lock(f"Lock{layer}_{k}", hm, rnd, pts, w, 0.07 * rnd.uniform(0.9, 1.1), tip=0.28, n=36))
    if fringe:
        for k, ph_e in enumerate((-44, -26, -8, 10, 28, 46)):
            th_e = 60 + 6 * abs(ph_e) / 46 + rnd.uniform(-2, 2)
            pts = [(P[0], P[1] + 8, 1.06), (36, ph_e - 22, 1.085), (th_e - 8, ph_e - 4, 1.07), (th_e, ph_e + 9, 1.085)]
            parts.append(lock(f"Fringe{k}", hm, rnd, pts, 0.13 * rnd.uniform(0.92, 1.08), 0.065, tip=0.4))
    return parts


def hair_bangs(hm, rnd):
    """Прямые черные волосы до подбородка и прямая густая челка с тупыми кончиками."""
    parts = []
    n = 22
    for layer in range(2):
        r0 = 1.045 + layer * 0.02
        for k in range(n):
            ph = -180 + 360 * (k + 0.5 * layer + 0.5) / n
            a = abs(((ph + 180) % 360) - 180)
            if a < 58:
                th_e = 57 + 2 * (a / 58) ** 2
                pts = [(6, ph * 0.3, r0 - 0.01), (30, ph, r0 + 0.015), (th_e, ph, r0 + 0.035)]
                parts.append(lock(f"Bang{layer}_{k}", hm, rnd, pts, 0.13, 0.065, blunt=True, n=24))
            else:
                th_e = 106 + rnd.uniform(-2, 2)
                pts = [(6, ph * 0.5, r0 - 0.01), (50, ph, r0 + 0.015), (88, ph, r0 + 0.03),
                       (th_e, ph * 0.97, r0 + 0.035)]
                parts.append(lock(f"Lock{layer}_{k}", hm, rnd, pts, 0.15, 0.065, blunt=True, n=30))
    return parts


def hair_curly(hm, rnd, base_r=1.07):
    """Пышные кудри: розетки-завитки (спираль из пряди) по всей шапке волос."""
    parts = []
    hl = hairline_default(56, 84, 110)
    pts = []
    N = 160
    for i in range(N):
        z = 1 - 2 * (i + 0.5) / N
        th = math.degrees(math.acos(z))
        ph = math.degrees((i * 137.508) % 360) - 180
        if th < hl(ph) - 4:
            pts.append((th, ph))
    for k, (th, ph) in enumerate(pts):
        th += rnd.uniform(-2, 2)
        ph += rnd.uniform(-3, 3)
        c = hp(th, ph, base_r)
        nrm = (c - HEAD_C)
        nrm = Vector((nrm.x / HEAD_AX.x ** 2, nrm.y / HEAD_AX.y ** 2, nrm.z / HEAD_AX.z ** 2)).normalized()
        u = nrm.orthogonal().normalized()
        v = nrm.cross(u)
        size = rnd.uniform(0.15, 0.19) * (0.85 if th > 70 else 1.0)
        turns = 1.7
        ph0 = rnd.uniform(0, 2 * math.pi)
        spiral = []
        for s in [i / 20 for i in range(21)]:
            ang = ph0 + 2 * math.pi * turns * s
            rad = size * (1 - 0.82 * s)
            h = size * 0.7 * (0.25 + 0.75 * math.sin(min(1.0, s * 1.4) * math.pi / 2))
            spiral.append(c + (u * math.cos(ang) + v * math.sin(ang)) * rad + nrm * h)
        parts.append(strand(f"Curl{k}", rnd.choice(hm), spiral, size * 0.36, size * 0.3, n=34, tip=0.25,
                            root_w=0.6, groove=0.15, up=nrm, flat=0.7))
    return parts


def hair_bun(hm, rnd):
    """Гладко зачесанные назад волосы и пучок-улитка на макушке, резинка, две выбившиеся прядки."""
    parts = []
    hl = hairline_default(60, 86, 114)
    Bth, Bph = 30, 180
    n = 22
    for k in range(n):
        ph = -180 + 360 * (k + 0.5) / n + rnd.uniform(-3, 3)
        th_e = hl(ph)
        pts = [(th_e + 2, ph, 1.03), (th_e * 0.6 + Bth * 0.4, ph * 0.85 + (Bph if ph > 0 else -Bph) * 0.15, 1.05),
               (Bth + 12, ph * 0.3 + (Bph if ph > 0 else -Bph) * 0.7, 1.045), (Bth + 2, Bph, 1.03)]
        parts.append(lock(f"Lock{k}", hm, rnd, pts, 0.15, 0.05, root=0.0, root_w=0.9, tip=0.2, groove=0.15))
    # пучок: толстая прядь закручена спиралью вокруг оси
    axis = Vector((0, 0.25, 1.05)).normalized()
    c0 = HEAD_C + Vector((0, 0.25, 1.05)) * 0.86
    u = axis.orthogonal().normalized()
    v = axis.cross(u)
    coil = []
    for i in range(61):
        s = i / 60
        ang = 2 * math.pi * 2.3 * s
        rad = 0.3 * (1 - 0.72 * s)
        coil.append(c0 + (u * math.cos(ang) + v * math.sin(ang)) * rad + axis * (0.02 + 0.3 * s ** 0.8))
    parts.append(strand("Bun", hm[0], coil, 0.14, 0.12, n=90, tip=0.15, root=0.05, groove=0.18,
                        up=lambda p: (p - (c0 + axis * 0.1)), flat=0.8))
    tie = M.torus("BunTie", 0.27, 0.045, 48, 12)
    tie.matrix_world = Matrix.Translation(c0 + axis * 0.0) @ axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
    M.smooth(tie)
    M.assign(tie, glossy("TieMat", (0.95, 0.40, 0.45), rough=0.3, coat=0.6))
    parts.append(tie)
    for side in (-1, 1):
        pts = [(66, side * 62, 1.03), (82, side * 70, 1.05), (100, side * 66, 1.07), (114, side * 70, 1.1)]
        parts.append(lock(f"Wisp{side}", hm, rnd, pts, 0.05, 0.035, tip=0.45, n=24))
    return parts


def hair_pony(hm, rnd):
    """Челка на пробор и два хвостика за ушами с резинками-бусинами, кончики подкручены."""
    parts = []
    hl = hairline_default(62, 88, 112)
    n = 16
    for k in range(n):
        ph = -180 + 360 * (k + 0.5) / n + rnd.uniform(-3, 3)
        a = abs(((ph + 180) % 360) - 180)
        if a < 60:
            continue
        side = 1 if ph > 0 else -1
        T = (98, side * 108)
        pts = [(8, ph * 0.2, 1.035), (45, ph, 1.05), (75, ph * 0.6 + T[1] * 0.4, 1.06), (T[0] - 4, T[1], 1.06)]
        parts.append(lock(f"Lock{k}", hm, rnd, pts, 0.16, 0.06, tip=0.15, root_w=0.8))
    for k, ph_e in enumerate((-50, -32, -14, 4, 22, 40, 56)):
        side = -1 if ph_e < -5 else 1
        th_e = 61 + 5 * abs(ph_e) / 56 + rnd.uniform(-2, 2)
        pts = [(10, ph_e * 0.4 - side * 10, 1.04), (34, ph_e - side * 6, 1.07), (th_e - 8, ph_e + side * 2, 1.06),
               (th_e, ph_e + side * 12, 1.075)]
        parts.append(lock(f"Fringe{k}", hm, rnd, pts, 0.12, 0.06, tip=0.4))
    bead = glossy("Bead", (0.30, 0.78, 0.55), rough=0.2, coat=0.9)
    for side in (-1, 1):
        t = hp(98, side * 108, 1.1)
        b = ellipsoid(f"Tie{side}", (0.1, 0.1, 0.1), bead, 24, 16)
        parts.append(placed(b, t))
        for j, (dx, dz, sw) in enumerate(((0.02, 0.0, 1.0), (0.07, -0.05, -0.6), (-0.03, -0.03, 0.4))):
            P0 = t + Vector((0, 0.02, -0.02))
            ctrl = [P0, P0 + Vector((side * (0.08 + dx), -0.02, -0.18)), P0 + Vector((side * (0.13 + dx), 0.0, -0.4 + dz)),
                    P0 + Vector((side * (0.08 + dx + 0.05 * sw), -0.04, -0.6 + dz)),
                    P0 + Vector((side * (0.0 + dx), -0.05, -0.68 + dz))]
            parts.append(strand(f"Tail{side}{j}", rnd.choice(hm), ctrl, 0.09, 0.075, n=30, tip=0.35,
                                up=Vector((side, -0.4, 0)), root_w=0.6))
    return parts


def hair_under_hat(hm, rnd, th0=56, side_end=90, back_end=112, fringe=(), front_gap=56, r0=1.04):
    """Волосы, видные из-под шляпы: пряди по бокам и сзади, по желанию - челка спереди."""
    parts = []
    n = 18
    for k in range(n):
        ph = -180 + 360 * (k + 0.5) / n + rnd.uniform(-3, 3)
        a = abs(((ph + 180) % 360) - 180)
        if a < front_gap:
            continue
        th_e = side_end + (back_end - side_end) * smoothstep(90, 180, a) + rnd.uniform(-3, 3)
        sw = 8 * (1 if ph > 0 else -1)
        pts = [(th0 + (6 if a > 100 else 0), ph - sw, r0), ((th0 + th_e) * 0.5, ph, r0 + 0.02),
               (th_e, ph + sw, r0 + 0.05)]
        parts.append(lock(f"Lock{k}", hm, rnd, pts, 0.15, 0.06, tip=0.4, n=22))
    for k, (ph_e, th_e, sw) in enumerate(fringe):
        pts = [(th0 - 6, ph_e - sw * 1.5, r0), (th_e - 8, ph_e - sw * 0.4, r0 + 0.025), (th_e, ph_e + sw * 0.5, r0 + 0.04)]
        parts.append(lock(f"Fringe{k}", hm, rnd, pts, 0.11, 0.055, tip=0.45, n=22))
    return parts


def hair_horseshoe(hm, rnd):
    """Лысина: короткий венчик волос по бокам и сзади."""
    parts = []
    n = 16
    for k in range(n):
        ph = -180 + 360 * (k + 0.5) / n
        a = abs(((ph + 180) % 360) - 180)
        if a < 72:
            continue
        th0 = 78 - 6 * smoothstep(90, 180, a)
        th_e = 98 + 10 * smoothstep(90, 180, a)
        sw = 6 * (1 if ph > 0 else -1)
        pts = [(th0, ph - sw, 1.012), ((th0 + th_e) / 2, ph, 1.03), (th_e, ph + sw, 1.035)]
        parts.append(lock(f"Lock{k}", hm, rnd, pts, 0.13, 0.04, tip=0.45, n=18, groove=0.1))
    return parts


def moustache(name, mats, rnd, mz=HEAD_Z - 0.245, width=0.23, droop=0.05, curl=0.0, thick=0.05, tufts=3):
    """Усы из прядок: от середины в стороны, кончики опущены (droop) или подкручены вверх (curl)."""
    parts = []
    for side in (-1, 1):
        for j in range(tufts):
            off = (j - (tufts - 1) / 2) * 0.022
            pts = []
            for i in range(7):
                t = i / 6
                x = side * (0.015 + width * t)
                z = mz + off * (1 - t) - droop * t ** 1.6 + curl * max(0.0, t - 0.65) ** 2 * 9
                if curl and t > 0.8:
                    x -= side * curl * (t - 0.8) * 1.2
                p, _ = head_surf(x, z, 0.035 + 0.02 * math.sin(math.pi * t))
                pts.append(p)
            parts.append(strand(f"{name}{side}{j}", rnd.choice(mats), pts, thick * (1.1 - 0.15 * abs(off) / 0.022),
                                thick * 0.8, n=24, tip=0.45, root_w=0.9, up=Vector((0, -1, 0.3))))
    return parts


# MARK: - Шапки

def stitch_line(name, pts_fn, count, mat, size=(0.022, 0.007, 0.006)):
    """Строчка: короткие стежки вдоль кривой pts_fn(t) -> (точка, нормаль)."""
    mats = []
    for k in range(count):
        t = (k + 0.5) / count
        p, n = pts_fn(t)
        p2, _ = pts_fn(min(1.0, t + 0.2 / count))
        p1, _ = pts_fn(max(0.0, t - 0.2 / count))
        mats.append(blob_matrix(p, p2 - p1, size, n))
    return blobs(name, mat, mats)


def thread_mat(col):
    return M.flat("Thread", col, rough=0.5, sheen=0.5)


def hat_brim_stitches(name, r, z_of, mat, count=48, lift=0.035):
    def f(t):
        a = 2 * math.pi * t
        p = Vector((r * math.cos(a), r * math.sin(a), 0))
        return Vector((p.x, p.y, z_of(p))), Vector((0, 0, 1))
    return f


def tilt_matrix(rx_deg, rz_deg=0.0, loc=(0, 0, 0)):
    return Matrix.Translation(loc) @ Matrix.Rotation(math.radians(rz_deg), 4, "Z") @ \
        Matrix.Rotation(math.radians(rx_deg), 4, "X")


def ring_stitches(name, mat, mx, r, z, count, size=(0.03, 0.009, 0.008), normal=(0, 0, 1), radial=False):
    """Строчка по кругу радиуса r на высоте z в осях шляпы (матрица mx)."""
    mats = []
    for k in range(count):
        a = 2 * math.pi * (k + 0.5) / count
        p = mx @ Vector((r * math.cos(a), r * math.sin(a), z))
        tng = mx.to_3x3() @ Vector((-math.sin(a), math.cos(a), 0))
        nrm = mx.to_3x3() @ (Vector((math.cos(a), math.sin(a), 0)) if radial else Vector(normal))
        mats.append(blob_matrix(p, tng, size, nrm))
    return blobs(name, mat, mats)


def hat_tophat(parts):
    felt = M.material("Felt", [(0.0, (0.05, 0.05, 0.07)), (1.0, (0.18, 0.18, 0.22))], coord="z",
                      lo=HEAD_Z + 0.5, hi=HEAD_Z + 1.9, rough=0.4, coat=0.4, coat_rough=0.25, sheen=0.6)
    _bump(felt, _felt_noise(felt), strength=0.08)
    mx = tilt_matrix(-8, 0, (0, 0.04, HEAD_Z + 0.62))
    brim = M.cylinder("HatBrim", 1.25, 0.06, 96)
    M.deform(brim, lambda co: Vector((co.x, co.y, co.z + 0.07 * (co.x / 1.25) ** 2)))
    brim.data.transform(mx)
    M.bevel(brim, 0.03, 3, 30)
    M.smooth(brim, 40)
    M.assign(brim, felt)
    binding = M.torus("BrimBinding", 1.24, 0.038, 96, 12)
    M.deform(binding, lambda co: Vector((co.x, co.y, co.z + 0.07 * (co.x / 1.25) ** 2)))
    binding.data.transform(mx)
    M.smooth(binding)
    M.assign(binding, M.flat("Grosgrain", (0.08, 0.08, 0.1), rough=0.3, sheen=0.8, coat=0.5))
    mxc = tilt_matrix(-8, 0, (0, 0.1, HEAD_Z + 0.65))
    crown = M.lathe("HatCrown", [(0.0, 0.0), (0.76, 0.0), (0.74, 0.3), (0.73, 0.6), (0.76, 0.85), (0.8, 0.92),
                                 (0.79, 0.95), (0.6, 0.955), (0.0, 0.955)], 96)
    crown.data.transform(mxc)
    M.bevel(crown, 0.05, 4, 30)
    M.subdivide(crown, 1)
    M.smooth(crown, 40)
    M.assign(crown, felt)
    band_m = M.flat("BandMat", (0.80, 0.10, 0.12), rough=0.35, sheen=0.7, coat=0.3)
    band = M.lathe("HatBand", [(0.0, 0.03), (0.775, 0.03), (0.785, 0.05), (0.78, 0.2), (0.77, 0.22), (0.0, 0.22)], 96)
    band.data.transform(mxc)
    M.assign(M.smooth(band, 40), band_m)
    # бант сбоку на ленте
    bow = []
    bx = mxc @ Vector((0.6, -0.52, 0.13))
    for k, (dx, s) in enumerate(((-0.07, 1), (0.07, -1))):
        w = M.sphere(f"HatBow{k}", 1.0, 24, 12)
        M.deform(w, lambda co: Vector((co.x * 0.09, co.y * 0.04, co.z * 0.07 * (1 + 0.4 * s * co.x))))
        w.data.transform(Matrix.Translation(bx + Vector((dx, -0.02, 0))) @ Matrix.Rotation(math.radians(-38), 4, "Z"))
        bow.append(M.assign(M.smooth(w), band_m))
    knot = ellipsoid("HatBowKnot", (0.035, 0.03, 0.05), band_m)
    bow.append(placed(knot, bx + Vector((0, -0.05, 0))))
    th = thread_mat((0.95, 0.75, 0.75))
    st = [ring_stitches("BandStitch0", th, mxc, 0.792, 0.06, 64, radial=True),
          ring_stitches("BandStitch1", th, mxc, 0.787, 0.19, 64, radial=True)]
    parts += [brim, binding, crown, band] + bow + st


def _felt_noise(mat, scale=40.0):
    nt = mat.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 6.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    return nz.outputs["Fac"]


def hat_cap(parts, col):
    cap_mat = fabric_mat("CapMat", col, rough=0.55, weave=110.0, bump=0.18, lo=HEAD_Z, hi=HEAD_Z + 1.1)
    crown = M.sphere("Crown", 1.17, 96, 48)
    crown.location = (0, 0.02, HEAD_Z + 0.02)
    M.apply_transform(crown)
    M.bisect(crown, (0, 0, HEAD_Z + 0.28), (0, 0, -1))
    # шесть клиньев: ложбинки по швам
    M.deform(crown, lambda co: co - (co - Vector((0, 0.02, HEAD_Z + 0.02))).normalized() * 0.016 *
             max(0.0, 1 - abs(math.sin(3 * math.atan2(co.x, -(co.y - 0.02)))) / 0.12) ** 2 *
             smoothstep(HEAD_Z + 0.32, HEAD_Z + 0.5, co.z))
    M.smooth(crown)
    M.assign(crown, cap_mat)
    brim_m = fabric_mat("BrimMat", shade(col, 0.95), rough=0.5, weave=110.0, bump=0.15, lo=HEAD_Z, hi=HEAD_Z + 1.1)
    brim = M.sphere("Brim", 1.0, 64, 16)
    M.deform(brim, lambda co: Vector((co.x * 0.78, co.y * 0.5 - 0.92, co.z * 0.05 + HEAD_Z + 0.36 + 0.35 * (co.y * 0.5) -
                                      0.06 * co.x * co.x)))
    M.smooth(brim)
    M.assign(brim, brim_m)
    btn = ellipsoid("CapButton", (0.11, 0.11, 0.06), cap_mat)
    placed(btn, (0, 0.02, HEAD_Z + 1.19))
    th = thread_mat(shade(col, 1.25))
    # строчка по козырьку: две дуги параллельно краю
    def brim_pt(k):
        def f(t):
            a = math.pi * (0.12 + 0.76 * t)
            x, y = math.cos(a) * 0.78 * k, -math.sin(a) * 0.5 * k
            z = 0.05 + HEAD_Z + 0.36 + 0.35 * y - 0.06 * (x / 0.78) ** 2
            return Vector((x, y - 0.92, z + 0.012 + 0.35 * 0.0)), Vector((0, -0.35, 1)).normalized()
        return f
    st = [stitch_line("BrimStitch0", brim_pt(0.82), 30, th), stitch_line("BrimStitch1", brim_pt(0.68), 24, th)]
    # строчка вдоль швов клиньев спереди
    for s, a0 in ((0, -60), (1, 0), (2, 60)):
        def seam(t, a0=a0):
            th_ = math.radians(10 + 58 * t)
            a = math.radians(a0) + 0.05
            r = 1.18
            p = Vector((r * math.sin(th_) * math.sin(a), 0.02 - r * math.sin(th_) * math.cos(a), HEAD_Z + 0.02 + r * math.cos(th_)))
            return p, (p - Vector((0, 0.02, HEAD_Z))).normalized()
        st.append(stitch_line(f"SeamStitch{s}", seam, 14, th, size=(0.02, 0.006, 0.006)))
    # нашивка-эмблема спереди: белый кружок с оранжевой звездочкой
    patch_c = Vector((0.0, 0.02, HEAD_Z + 0.02)) + Vector((0, -math.cos(math.radians(52)), math.sin(math.radians(52)))) * 1.175
    nrm = (patch_c - Vector((0, 0.02, HEAD_Z + 0.02))).normalized()
    patch = M.cylinder("CapPatch", 0.15, 0.025, 48)
    M.bevel(patch, 0.01, 2, 30)
    patch.matrix_world = Matrix.Translation(patch_c) @ nrm.to_track_quat("Z", "Y").to_matrix().to_4x4()
    M.apply_transform(patch)
    M.assign(M.smooth(patch, 40), M.flat("PatchMat", (1.0, 0.97, 0.9), rough=0.6, sheen=0.4))
    star_pts = []
    for k in range(10):
        a = math.radians(90 + k * 36)
        rr = 0.09 if k % 2 == 0 else 0.04
        star_pts.append((rr * math.cos(a), rr * math.sin(a)))
    star = M.profile_prism("CapStar", star_pts, 0.02)
    M.bevel(star, 0.006, 2, 30)
    star.matrix_world = Matrix.Translation(patch_c + nrm * 0.012) @ nrm.to_track_quat("Z", "Y").to_matrix().to_4x4()
    M.apply_transform(star)
    M.assign(M.smooth(star, 40), M.flat("StarMat", (1.0, 0.62, 0.12), rough=0.5, sheen=0.3))
    parts += [crown, brim, btn, patch, star] + st


def hat_beanie(parts, col):
    knit = fabric_mat("Knit", col, rough=0.75, weave=70.0, bump=0.25, knit=True, sheen=0.6, lo=HEAD_Z, hi=HEAD_Z + 1.3)
    crown = M.sphere("Beanie", 1.19, 96, 48)
    crown.location = (0, 0.02, HEAD_Z + 0.06)
    M.apply_transform(crown)
    M.bisect(crown, (0, 0, HEAD_Z + 0.38), (0, 0, -1))
    # продольный рубчик и легкие поперечные складки трикотажа
    M.push_normals(crown, lambda co, n: 0.012 * abs(math.sin(14 * math.atan2(co.x, -(co.y - 0.02)))) *
                   (1 - smoothstep(HEAD_Z + 0.9, HEAD_Z + 1.2, co.z)) - 0.01 * smoothstep(-1, 1, math.sin(co.z * 11)))
    M.smooth(crown)
    M.assign(crown, knit)
    cuff = M.torus("Cuff", 1.1, 0.14, 128, 20)
    M.push_normals(cuff, lambda co, n: 0.016 * abs(math.sin(math.atan2(co.y, co.x) * 36)))
    cuff.location = (0, 0.02, HEAD_Z + 0.42)
    M.apply_transform(cuff)
    M.smooth(cuff)
    M.assign(cuff, fabric_mat("CuffKnit", shade(col, 0.92), rough=0.8, weave=90.0, bump=0.25, knit=True, sheen=0.6,
                              lo=HEAD_Z, hi=HEAD_Z + 1.3))
    pom = M.sphere("Pom", 0.21, 96, 64)
    M.push_normals(pom, lambda co, n: 0.035 * M.fbm(co * 28, 2) + 0.02 * M.fbm(co * 60, 2))
    pom.location = (0, 0.02, HEAD_Z + 1.21)
    M.apply_transform(pom)
    M.smooth(pom)
    pm = M.material("PomMat", [(0.0, (0.88, 0.86, 0.84)), (1.0, (1.0, 0.99, 0.97))], coord="z", lo=HEAD_Z + 1.0,
                    hi=HEAD_Z + 1.4, rough=0.85, sheen=1.0)
    _bump(pm, _felt_noise(pm, 160.0), strength=0.5)
    M.assign(pom, pm)
    parts += [crown, cuff, pom]


def hat_witch(parts):
    felt = M.material("WitchFelt", [(0.0, (0.10, 0.05, 0.16)), (1.0, (0.40, 0.18, 0.55))], coord="z",
                      lo=HEAD_Z + 0.4, hi=HEAD_Z + 2.4, rough=0.55, coat=0.15, sheen=0.6)
    _bump(felt, _felt_noise(felt, 30.0), strength=0.12)
    mx = Matrix.Translation((0, 0.05, HEAD_Z + 0.6)) @ Matrix.Rotation(math.radians(4), 4, "Z") @ \
        Matrix.Rotation(math.radians(-10), 4, "X")
    brim = M.cylinder("WitchBrim", 1.55, 0.06, 128)
    # поля чуть волной и с загибом кверху по краю
    M.deform(brim, lambda co: Vector((co.x, co.y, co.z + 0.06 * (co.x * co.x + co.y * co.y) / 2.4 +
                                      0.025 * math.sin(5 * math.atan2(co.y, co.x)) * (math.hypot(co.x, co.y) / 1.55) ** 3)))
    M.bevel(brim, 0.03, 3, 30)
    brim.data.transform(mx)
    M.smooth(brim, 40)
    M.assign(brim, felt)
    mxc = Matrix.Translation((0, 0.1, HEAD_Z + 0.62)) @ Matrix.Rotation(math.radians(4), 4, "Z") @ \
        Matrix.Rotation(math.radians(-10), 4, "X")
    cone = M.lathe("WitchCone", [(0.86, 0.0), (0.72, 0.2), (0.54, 0.45), (0.36, 0.7), (0.2, 0.95), (0.06, 1.15), (0.0, 1.2)], 96)
    M.subdivide(cone, 1)

    # кончик заломлен набок, по конусу - мятые складки
    def bend(co):
        h = max(0.0, co.z / 1.2)
        a = math.atan2(co.y, co.x)
        wob = 1 + 0.06 * math.sin(3 * a + co.z * 5) * h + 0.05 * math.sin(co.z * 9) * h
        return Vector((co.x * wob + 0.62 * h ** 3, co.y * wob + 0.1 * h ** 2, co.z - 0.12 * h ** 4))
    M.deform(cone, bend)
    cone.data.transform(mxc)
    M.smooth(cone)
    M.assign(cone, felt)
    band = M.cylinder("WitchBand", 0.84, 0.18, 96)
    band.data.transform(Matrix.Translation((0, 0.1, HEAD_Z + 0.73)) @ Matrix.Rotation(math.radians(4), 4, "Z") @
                        Matrix.Rotation(math.radians(-10), 4, "X"))
    M.smooth(band, 40)
    band_m = M.flat("WitchBandMat", (1.0, 0.55, 0.08), rough=0.35, coat=0.3, sheen=0.5)
    M.assign(band, band_m)
    buckle = M.box_mesh("Buckle", 0.28, 0.04, 0.22, 0.0)
    hole = M.box_mesh("BuckleHole", 0.15, 0.2, 0.1, 0.0)
    hole.location = (0, 0, 0.06)
    M.apply_transform(hole)
    M.boolean_cut(buckle, [hole])
    buckle.location = (0.05, -0.8, HEAD_Z + 0.65)
    buckle.rotation_euler = (math.radians(-10), 0, math.radians(4))
    M.apply_transform(buckle)
    M.bevel(buckle, 0.012, 2, 30)
    M.assign(buckle, gold_mat("BuckleGold"))
    # заплатка на колпаке: зеленый квадратик с крупной строчкой
    pc = mxc @ Vector((-0.25, -0.5, 0.42))
    nrm = (mxc.to_3x3() @ Vector((-0.25, -0.5, 0.2))).normalized()
    patch = M.box_mesh("Patch", 0.24, 0.03, 0.2, -0.1)
    M.bevel(patch, 0.012, 2, 30)
    q = nrm.to_track_quat("-Y", "Z").to_matrix().to_4x4()
    patch.matrix_world = Matrix.Translation(pc) @ q @ Matrix.Rotation(math.radians(12), 4, "Y")
    M.apply_transform(patch)
    patch_m = fabric_mat("PatchMat", (0.38, 0.62, 0.30), weave=120.0, bump=0.2, lo=HEAD_Z + 1.0, hi=HEAD_Z + 1.4)
    M.assign(M.smooth(patch, 40), patch_m)
    th = thread_mat((1.0, 0.85, 0.4))
    mats = []
    for k in range(12):
        t = (k + 0.5) / 12 * 4
        e, f = int(t), t - int(t)
        corners = [(-0.1, 0.085), (0.1, 0.085), (0.1, -0.085), (-0.1, -0.085), (-0.1, 0.085)]
        a, b = Vector((*corners[e], 0)), Vector((*corners[e + 1], 0))
        lp = a.lerp(b, f)
        p = patch.matrix_world @ Vector((0, 0, 0))
        world = Matrix.Translation(pc) @ q @ Matrix.Rotation(math.radians(12), 4, "Y")
        pw = world @ Vector((lp.x, -0.03, lp.y))
        dirv = world.to_3x3() @ Vector((b.x - a.x, 0, b.y - a.y))
        mats.append(blob_matrix(pw, dirv, (0.02, 0.008, 0.008), -(world.to_3x3() @ Vector((0, 1, 0)))))
    st = blobs("PatchStitch", th, mats)
    parts += [brim, cone, band, buckle, patch, st]


def hat_snowmaiden(parts):
    blue = M.material("Kokoshnik", [(0.0, (0.22, 0.42, 0.85)), (1.0, (0.55, 0.78, 1.0))], coord="z",
                      lo=HEAD_Z + 0.3, hi=HEAD_Z + 1.4, rough=0.3, coat=0.6, sheen=0.5)
    crown = M.sphere("Cap", 1.16, 64, 32)
    crown.location = (0, 0.04, HEAD_Z + 0.05)
    M.apply_transform(crown)
    M.bisect(crown, (0, 0, HEAD_Z + 0.42), (0, 0, -1))
    M.smooth(crown)
    M.assign(crown, fabric_mat("CapMat", (0.82, 0.90, 1.0), rough=0.5, weave=120, bump=0.15, sheen=0.7,
                               lo=HEAD_Z + 0.3, hi=HEAD_Z + 1.3))
    arch = [(math.cos(math.pi * k / 32) * 0.92, 0.72 * math.sin(math.pi * k / 32)) for k in range(33)]
    plate = M.profile_prism("Plate", arch, 0.12)
    plate.rotation_euler = (math.radians(80), 0, 0)
    plate.location = (0, -0.66, HEAD_Z + 0.5)
    M.apply_transform(plate)
    M.bevel(plate, 0.04, 3, 30)
    M.smooth(plate, 40)
    M.assign(plate, blue)
    pearl = M.material("Pearl", [(0.0, (0.90, 0.88, 0.98)), (1.0, (1.0, 1.0, 1.0))], coord="nz", lo=-1, hi=1,
                       rough=0.12, coat=0.9)
    silver = M.material("Silver", [(0.0, (0.70, 0.75, 0.85)), (1.0, (1.0, 1.0, 1.0))], coord="nz", lo=-1, hi=1,
                        rough=0.2, metal=1.0)
    ca, sa = math.cos(math.radians(80)), math.sin(math.radians(80))

    def on_plate(px, pz, out=0.09):
        return Vector((px, -0.66 - out + pz * ca, HEAD_Z + 0.5 + pz * sa))
    mats = []
    for k in range(13):
        a = math.pi * (k + 0.5) / 13
        mats.append(blob_matrix(on_plate(0.84 * math.cos(a), 0.64 * math.sin(a)), (1, 0, 0), (0.05, 0.05, 0.05)))
    # второй ряд жемчужин и серебряные завитки-точки внутри
    for k in range(9):
        a = math.pi * (k + 0.5) / 9
        mats.append(blob_matrix(on_plate(0.6 * math.cos(a), 0.12 + 0.36 * math.sin(a)), (1, 0, 0), (0.032, 0.032, 0.032)))
    pearls = blobs("Pearls", pearl, mats, 16, 10)
    gem = M.material("SnowGem", [(0.0, (0.25, 0.55, 1.0)), (1.0, (0.75, 0.92, 1.0))], coord="z", lo=HEAD_Z + 0.5,
                     hi=HEAD_Z + 0.9, rough=0.05, coat=1.0, transmission=0.2)
    g = ellipsoid("SnowGemC", (0.1, 0.05, 0.12), gem, 32, 16)
    placed(g, on_plate(0.0, 0.2, 0.11))
    setting = M.torus("GemSetting", 0.11, 0.022, 48, 10)
    setting.matrix_world = Matrix.Translation(on_plate(0.0, 0.2, 0.1)) @ Matrix.Rotation(math.radians(80 + 90), 4, "X")
    M.apply_transform(setting)
    M.assign(M.smooth(setting), silver)
    snow = []
    for k, (px, pz) in enumerate(((-0.42, 0.2), (0.42, 0.2))):
        c = on_plate(px, pz, 0.08)
        for j in range(6):
            a = math.pi * j / 3
            snow.append(blob_matrix(c + Vector((0.045 * math.cos(a), 0, 0.045 * math.sin(a))),
                                    (math.cos(a), 0, math.sin(a)), (0.05, 0.012, 0.012)))
    flakes = blobs("Flakes", silver, snow)
    fur = M.torus("Fur", 1.12, 0.13, 128, 20)
    fur.location = (0, 0.02, HEAD_Z + 0.45)
    M.apply_transform(fur)
    M.push_normals(fur, lambda co, n: 0.035 * M.fbm(co * 9) + 0.015 * M.fbm(co * 30))
    M.smooth(fur)
    fm = M.material("FurMat", [(0.0, (0.86, 0.9, 1.0)), (1.0, (1.0, 1.0, 1.0))], coord="z",
                    lo=HEAD_Z + 0.3, hi=HEAD_Z + 0.6, rough=0.85, sheen=1.0)
    _bump(fm, _felt_noise(fm, 120.0), strength=0.45)
    M.assign(fur, fm)
    parts += [crown, plate, pearls, g, setting, flakes, fur]


def hat_tiara(parts):
    gold = gold_mat("Tiara")
    band = M.torus("TiaraBand", 0.86, 0.05, 96, 12)
    band.location = (0, 0.05, HEAD_Z + 0.86)
    band.rotation_euler = (math.radians(-22), 0, 0)
    M.apply_transform(band)
    M.smooth(band)
    M.assign(band, gold)
    gem = M.material("Gem", [(0.0, (0.85, 0.15, 0.45)), (1.0, (1.0, 0.55, 0.8))], coord="z", lo=HEAD_Z + 0.7,
                     hi=HEAD_Z + 1.5, rough=0.06, coat=1.0, transmission=0.2)
    for k, x in enumerate((-0.42, 0.0, 0.42)):
        h = 0.42 if x == 0 else 0.3
        spike = M.profile_prism(f"Spike{k}", [(-0.13, 0.0), (0.13, 0.0), (0.0, h)], 0.06)
        spike.rotation_euler = (math.radians(70), 0, 0)
        spike.location = (x, -0.72 + 0.18 * abs(x), HEAD_Z + 0.9 - 0.1 * abs(x))
        M.apply_transform(spike)
        M.bevel(spike, 0.02, 2, 30)
        M.smooth(spike, 40)
        M.assign(spike, gold)
        g = ellipsoid(f"Gem{k}", (0.08, 0.06, 0.08), gem, 24, 12)
        g.location = (x, -0.76 + 0.18 * abs(x) - h * math.cos(math.radians(70)) * 0.9,
                      HEAD_Z + 0.9 - 0.1 * abs(x) + h * math.sin(math.radians(70)))
        M.apply_transform(g)
        # маленький камешек в основании зубца
        g2 = ellipsoid(f"GemS{k}", (0.04, 0.03, 0.04), gem, 16, 10)
        g2.location = (x, -0.76 + 0.18 * abs(x) - 0.03, HEAD_Z + 0.95 - 0.1 * abs(x))
        M.apply_transform(g2)
        parts += [spike, g, g2]
    parts.append(band)
    disc = M.cylinder("ClipCandy", 0.24, 0.07, 64)
    disc.rotation_euler = (math.radians(90), 0, 0)
    disc.location = (-0.86, -0.42, HEAD_Z + 0.42)
    M.apply_transform(disc)
    M.bevel(disc, 0.025, 3, 30)
    M.smooth(disc, 40)
    swirl = M.material("Swirl", [(0.0, (1.0, 1.0, 1.0)), (0.5, (0.35, 0.75, 1.0)), (1.0, (1.0, 1.0, 1.0))],
                       coord="x", lo=-1.06, hi=-0.66, rough=0.1, coat=1.0)
    # спираль леденца поверх диска
    sw_pts = []
    for i in range(60):
        s = i / 59
        a = 2 * math.pi * 2.2 * s
        rr = 0.2 * (1 - s) + 0.01
        sw_pts.append(Vector((-0.86 + rr * math.cos(a), -0.42 - 0.04, HEAD_Z + 0.42 + rr * math.sin(a))))
    swirl_line = tube("CandySwirl", sw_pts, 0.022, glossy("SwirlPink", (1.0, 0.35, 0.6), rough=0.1, coat=1.0))
    M.assign(disc, swirl)
    parts += [disc, swirl_line]


def hat_brimmed(parts, style):
    if style == "cowboy":
        hat = M.material("CowboyFelt", [(0.0, (0.34, 0.19, 0.08)), (1.0, (0.64, 0.42, 0.21))], coord="z",
                         lo=HEAD_Z + 0.4, hi=HEAD_Z + 1.4, rough=0.6, sheen=0.6, coat=0.1)
        _bump(hat, _felt_noise(hat, 35.0), strength=0.12)
        band_col = (0.14, 0.08, 0.05)
    else:
        hat = straw_mat()
        band_col = (0.80, 0.18, 0.14)
    r_brim = 1.6 if style == "cowboy" else 1.55
    brim = M.cylinder("HatBrim", r_brim, 0.06, 128)
    curl = 0.32 if style == "cowboy" else 0.06
    M.deform(brim, lambda co: Vector((co.x, co.y, co.z + curl * (co.x / r_brim) ** 2 - 0.05 * (co.y / r_brim))))
    M.bevel(brim, 0.03, 3, 30)
    mxb = tilt_matrix(-8, 0, (0, 0.05, HEAD_Z + 0.6))
    brim.data.transform(mxb)
    M.subdivide(brim, 1)
    M.smooth(brim, 40)
    M.assign(brim, hat)
    hcrown = 0.72 if style == "cowboy" else 0.55
    crown = M.cylinder("HatCrown", 0.8, hcrown, 96)
    top = hcrown / 2
    if style == "cowboy":
        # продольная вмятина сверху и два щипка спереди
        M.deform(crown, lambda co: Vector((co.x * (1 - 0.1 * max(0.0, (co.z + top) / (2 * top)) ** 2 * max(0.0, -co.y / 0.8)),
                                           co.y, co.z - (0.16 * (1 - min(1, abs(co.x) / 0.8) ** 2) if co.z > top - 0.01 else 0))))
    crown.data.transform(tilt_matrix(-8, 0, (0, 0.08, HEAD_Z + 0.95)))
    M.bevel(crown, 0.12, 4, 30)
    M.smooth(crown, 40)
    M.assign(crown, hat)
    band = M.cylinder("HatBand", 0.82, 0.14, 96)
    band.data.transform(tilt_matrix(-8, 0, (0, 0.07, HEAD_Z + 0.72)))
    M.smooth(band, 40)
    band_m = M.flat("HatBandMat", band_col, rough=0.45, sheen=0.5, coat=0.15)
    M.assign(band, band_m)
    mxs = tilt_matrix(-8, 0, (0, 0.07, HEAD_Z + 0.72))
    th = thread_mat((0.95, 0.85, 0.65) if style == "cowboy" else (1.0, 0.92, 0.85))
    st = [ring_stitches("BandStitch0", th, mxs, 0.828, -0.05, 60, radial=True),
          ring_stitches("BandStitch1", th, mxs, 0.828, 0.05, 60, radial=True)]
    extra = []
    if style == "cowboy":
        # серебряная бляха на ленте и строчка по краю полей
        silver = M.material("Concho", [(0.0, (0.65, 0.68, 0.74)), (1.0, (1.0, 1.0, 1.0))], coord="nz", lo=-1, hi=1,
                            rough=0.2, metal=1.0)
        ch = M.cylinder("Concho", 0.09, 0.03, 48)
        M.bevel(ch, 0.012, 2, 30)
        ch.rotation_euler = (math.radians(90), 0, 0)
        M.apply_transform(ch)
        ch.data.transform(mxs @ Matrix.Translation((0.0, -0.84, 0.0)))
        extra.append(M.assign(M.smooth(ch, 40), silver))
        brim_st = []
        for k in range(90):
            a = 2 * math.pi * (k + 0.5) / 90
            rr = r_brim - 0.09
            x, y = rr * math.cos(a), rr * math.sin(a)
            z = 0.035 + curl * (x / r_brim) ** 2 - 0.05 * (y / r_brim)
            p = mxb @ Vector((x, y, z))
            tng = mxb.to_3x3() @ Vector((-math.sin(a), math.cos(a), 2 * curl * x / r_brim ** 2 * -math.sin(a)))
            brim_st.append(blob_matrix(p, tng, (0.03, 0.009, 0.007), mxb.to_3x3() @ Vector((0, 0, 1))))
        extra.append(blobs("BrimStitch", th, brim_st))
    else:
        # бахрома: торчащие соломинки по краю полей
        straws = []
        rnd = random.Random(5)
        for k in range(120):
            a = 2 * math.pi * k / 120 + rnd.uniform(-0.02, 0.02)
            rr = r_brim + rnd.uniform(-0.01, 0.035)
            x, y = rr * math.cos(a), rr * math.sin(a)
            z = curl * (x / r_brim) ** 2 - 0.05 * (y / r_brim)
            p = mxb @ Vector((x, y, z))
            d = mxb.to_3x3() @ Vector((math.cos(a + rnd.uniform(-0.3, 0.3)), math.sin(a + rnd.uniform(-0.3, 0.3)),
                                       rnd.uniform(-0.2, 0.2)))
            straws.append(blob_matrix(p, d, (rnd.uniform(0.03, 0.06), 0.012, 0.008), mxb.to_3x3() @ Vector((0, 0, 1))))
        extra.append(blobs("Fringe", hat, straws, 8, 6))
        # цветок на ленте
        petal = M.flat("Petal", (1.0, 0.96, 0.9), rough=0.5, sheen=0.4)
        fl = []
        fc = mxs @ Vector((-0.55, -0.6, 0.0))
        nrm = (mxs.to_3x3() @ Vector((-0.55, -0.6, 0))).normalized()
        u = nrm.cross(Vector((0, 0, 1))).normalized()
        v = u.cross(nrm)
        for k in range(5):
            a = 2 * math.pi * k / 5
            d = u * math.cos(a) + v * math.sin(a)
            fl.append(blob_matrix(fc + d * 0.07 + nrm * 0.03, d, (0.07, 0.045, 0.02), nrm))
        extra.append(blobs("Flower", petal, fl, 16, 10))
        ctr = ellipsoid("FlowerC", (0.04, 0.04, 0.04), M.flat("FlowerCM", (1.0, 0.78, 0.15), rough=0.5))
        extra.append(placed(ctr, fc + nrm * 0.05))
    parts += [brim, crown, band] + st + extra


def straw_mat():
    """Соломка: корзиночное плетение (шахматка из полос) в цвете и рельефе."""
    mat = M.material("Straw", [(0.0, (0.80, 0.62, 0.30)), (1.0, (1.0, 0.88, 0.55))], coord="z",
                     lo=HEAD_Z + 0.4, hi=HEAD_Z + 1.4, rough=0.65)
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Object"], sep.inputs[0])
    ang = _math(nodes, links, "ARCTAN2", sep.outputs["X"], sep.outputs["Y"])
    rad = nodes.new("ShaderNodeVectorMath")
    rad.operation = "LENGTH"
    links.new(tc.outputs["Object"], rad.inputs[0])
    a = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY", ang, 48.0))
    b = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY", rad.outputs["Value"], 70.0))
    c = _math(nodes, links, "SINE", _math(nodes, links, "MULTIPLY", sep.outputs["Z"], 70.0))
    h = _math(nodes, links, "MULTIPLY", a, _math(nodes, links, "ADD", b, c))
    _bump(mat, h, strength=0.35, distance=0.02)
    _scale_color(mat, _math(nodes, links, "MULTIPLY_ADD", h, 0.08, 0.92))
    return mat


# MARK: - Одежда

def button(name, p, n, r, mat, holes=None):
    ob = M.cylinder(name, r, r * 0.45, 32)
    M.bevel(ob, r * 0.2, 3, 30)
    M.deform(ob, lambda co: Vector((co.x, co.y, co.z + 0.25 * r * (1 - (co.x ** 2 + co.y ** 2) / r ** 2) * (co.z > 0))))
    ob.matrix_world = Matrix.Translation(p + n * r * 0.15) @ (-n).to_track_quat("-Z", "Y").to_matrix().to_4x4()
    M.apply_transform(ob)
    M.smooth(ob, 40)
    M.assign(ob, mat)
    out = [ob]
    if holes:
        mats = []
        for dx, dz in ((-0.3, 0.3), (0.3, 0.3), (-0.3, -0.3), (0.3, -0.3)):
            q = p + n * r * 0.42 + Vector((dx * r, 0, dz * r))
            mats.append(blob_matrix(q, (1, 0, 0), (r * 0.13, r * 0.13, r * 0.06), n))
        out.append(blobs(name + "Holes", holes, mats, 8, 6))
    return out


def body_folds(co, n):
    """Мягкие складки: от подмышек по бокам и пара поперечных у пояса."""
    d = 0.0
    for s in (-1, 1):
        dx = co.x - s * 1.0
        w = math.exp(-((dx / 0.38) ** 2) - ((co.z - 0.05) / 0.35) ** 2)
        d += 0.014 * w * math.sin(16 * (co.z * 0.8 - s * co.x * 0.55))
    w2 = smoothstep(0.55, 0.95, abs(co.x)) * (1 - smoothstep(-0.2, 0.25, co.z))
    d += 0.01 * w2 * math.sin(co.z * 22 + co.x * 4)
    return d


def collar_rib(name, mat, r=0.36, minor=0.07, z=0.52, ribs=56, y=0.05):
    ob = M.torus(name, r, minor, 96, 16)
    M.push_normals(ob, lambda co, n: 0.008 * abs(math.sin(math.atan2(co.y, co.x) * ribs / 2)))
    ob.location = (0, y, z)
    M.apply_transform(ob)
    M.smooth(ob)
    return M.assign(ob, mat)


def flap(name, mat, origin, angle, length, w0, w1, lift=0.045, round_tip=True, surf=None):
    """Плоский лоскут на груди (уголок воротника, лацкан): от origin под углом angle (рад), ширина w0 -> w1."""
    def half(u):
        t = u / length
        w = w0 + (w1 - w0) * t
        if round_tip:
            w *= math.sqrt(max(0.0, 1 - max(0.0, (t - 0.8) / 0.2) ** 2))
        return w / 2
    return pillow(name, mat, surf or body_surf, 0.0, length, half, lambda u: -half(u), lift=lift, base=-0.006,
                  nu=24, nv=10, power=0.35, end=0.15, origin=origin, angle=angle)


def placket(name, mat, x0=0.0, z0=0.48, z1=-0.35, w=0.075, lift=0.016):
    return pillow(name, mat, body_surf, z1, z0, lambda u: w, lambda u: -w, lift=lift, base=-0.006, nu=24, nv=8,
                  power=0.3, end=0.08, origin=(x0, 0.0), angle=math.pi / 2)


def pocket(name, mat, th, cx, cz, w=0.26, h=0.26, r=0.06):
    def top(u):
        return cz + h / 2

    def bot(u):
        a = abs(u - cx)
        k = w / 2 - r
        if a > k:
            return cz - h / 2 + r - math.sqrt(max(0.0, r * r - (a - k) ** 2))
        return cz - h / 2
    pk = pillow(name, mat, body_surf, cx - w / 2, cx + w / 2, top, bot, lift=0.018, base=-0.004, nu=24, nv=12,
                power=0.25, end=0.06)
    hem = stitch_line(name + "Stitch", lambda t: body_surf(cx - w / 2 + 0.03 + (w - 0.06) * t, cz + h / 2 - 0.035, 0.02),
                      9, th, size=(0.012, 0.005, 0.004))
    return [pk, hem]


def neck_hole_mask(m_in, w=0.13, k=0.36):
    return lambda n, c: c.y < 0 and -0.5 < c.z < 0.62 and abs(c.x) < w + k * (c.z + 0.4) / 0.9


def garment(kind, col, parts, acc_bandana=False):
    """Тело-туловище (как прежде, эллипсоид) в одежде kind с воротником, пуговицами и складками."""
    rnd = random.Random(7)
    knit = kind in ("turtle", "sweater")
    shirt = fabric_mat("Shirt", col, knit=knit, weave=70.0 if knit else 130.0, bump=0.2 if knit else 0.16,
                       rough=0.7 if knit else 0.58)
    if kind == "stripes":
        add_bands(shirt, (0.99, 0.96, 0.9), axis="Z", freq=4.2, width=0.32, offset=0.02)
    if kind == "plaid":
        add_bands(shirt, shade(col, 0.55), axis="Z", freq=3.2, width=0.22)
        add_bands(shirt, shade(col, 0.6), axis="X", freq=3.2, width=0.22)
        add_bands(shirt, (0.98, 0.86, 0.35), axis="X", freq=3.2, width=0.05, offset=0.15)
    body = M.sphere("Body", 1.0, 128, 80)
    M.deform(body, lambda co: Vector((co.x * 1.38, co.y * 0.82, co.z * 0.78)))
    body.location = (0, 0.1, -0.2)
    M.apply_transform(body)
    M.push_normals(body, body_folds)
    M.smooth(body)
    M.assign(body, shirt)
    parts.append(body)
    trim = fabric_mat("Trim", shade(col, 1.1), knit=True, weave=90.0, bump=0.2, rough=0.6)
    white = fabric_mat("WhiteCloth", (0.98, 0.97, 0.94), weave=140.0, bump=0.12, rough=0.55, lo=-0.4, hi=0.6)
    th = thread_mat(shade(col, 1.35) if sum(col) < 2.2 else shade(col, 0.6))
    btn_m = glossy("ButtonMat", shade(col, 0.55) if kind not in ("cardigan",) else (0.95, 0.9, 0.8), rough=0.2, coat=0.9)
    holes = M.flat("ButtonHole", (0.1, 0.08, 0.08), rough=0.5)
    if kind in ("crew", "stripes"):
        parts.append(collar_rib("Collar", trim if kind == "crew" else fabric_mat("TrimS", (0.98, 0.96, 0.9), knit=True, weave=90.0)))
        if kind == "crew":
            parts += pocket("Pocket", shirt, th, -0.5, 0.06)
    elif kind == "sweater":
        parts.append(collar_rib("Collar", trim, minor=0.085, ribs=64))
        # полоса узора-"косички" поперек груди светлым цветом
        add_bands(shirt, (0.98, 0.96, 0.9), axis="Z", freq=1.0, width=0.05, offset=0.3)
    elif kind == "turtle":
        roll = M.torus("Turtleneck", 0.42, 0.13, 96, 24)
        M.push_normals(roll, lambda co, n: 0.012 * abs(math.sin(math.atan2(co.y, co.x) * 26)))
        roll.location = (0, 0.04, 0.52)
        M.apply_transform(roll)
        parts.append(M.assign(M.smooth(roll), trim))
    elif kind in ("shirt", "polo", "western"):
        parts.append(collar_rib("Collar", shirt, r=0.35, minor=0.06, ribs=0))
        if kind == "western":
            # платок закрывает ворот: видны планка с жемчужными кнопками и строчка кокетки
            parts.append(placket("Placket", shirt, 0.0, 0.1, -0.4, 0.07))
            pearl = M.material("Pearl", [(0.0, (0.9, 0.88, 0.95)), (1.0, (1.0, 1.0, 1.0))], coord="nz", lo=-1, hi=1,
                               rough=0.1, coat=1.0)
            for k, z in enumerate((-0.02, -0.2)):
                p, n = body_surf(0.0, z, 0.016)
                parts += button(f"Button{k}", p, n, 0.036, pearl)
            parts.append(stitch_line("YokeStitch", lambda t: body_surf(-1.05 + 2.1 * t, 0.16 - 0.1 * (1 - abs(-1 + 2 * t)) ** 1.5,
                                                                       0.012), 40, thread_mat((0.98, 0.9, 0.75)),
                                     size=(0.02, 0.006, 0.005)))
            for s in (-1, 1):
                parts += pocket(f"Pocket{s}", shirt, thread_mat((0.98, 0.9, 0.75)), s * 0.55, -0.12, w=0.26, h=0.2)
        else:
            pl_len = -0.35 if kind != "polo" else 0.12
            parts.append(placket("Placket", shirt, 0.0, 0.47, pl_len, 0.07))
            for s in (-1, 1):
                # уголки воротника: от шеи вниз-наружу к острию
                ang = math.radians(-90 + s * 32)
                origin = (s * 0.17, 0.5)
                parts.append(flap(f"CollarFlap{s}", shirt, origin, ang, 0.34, 0.2, 0.04 if kind != "polo" else 0.12,
                                  lift=0.05, round_tip=(kind == "polo")))
            zs = (0.32, 0.12, -0.08) if kind != "polo" else (0.36, 0.22)
            for k, z in enumerate(zs):
                p, n = body_surf(0.0, z, 0.016)
                parts += button(f"Button{k}", p, n, 0.034, btn_m, holes)
    elif kind == "peter":
        parts.append(collar_rib("Collar", white, r=0.35, minor=0.05, ribs=0))

        def ptop(a):
            return 0.53 + 0.03 * (a / 0.42) ** 2

        def pbot(a):
            t = (a - 0.215) / 0.215
            return ptop(a) - 0.24 * math.sqrt(max(0.0, 1 - t * t)) ** 0.9
        pink = thread_mat((0.95, 0.5, 0.6))
        for s in (-1, 1):
            u0, u1 = (0.0, 0.43) if s > 0 else (-0.43, 0.0)
            parts.append(pillow(f"PeterCollar{s}", white, body_surf, u0, u1, lambda u: ptop(abs(u)),
                                lambda u: pbot(abs(u)), lift=0.04, base=-0.006, nu=28, nv=10, power=0.35, end=0.15))
            parts.append(stitch_line(f"PeterStitch{s}", lambda t, s=s: body_surf(
                s * (0.06 + 0.32 * t), pbot(0.06 + 0.32 * t) + 0.03, 0.04), 13, pink, size=(0.016, 0.006, 0.005)))
        for k, z in enumerate((0.16, -0.08)):
            p, n = body_surf(0.0, z, 0.01)
            parts += button(f"Button{k}", p, n, 0.04, glossy("BtnWhite", (1.0, 0.97, 0.9), rough=0.2), holes)
    elif kind == "hoodie":
        # капюшон лежит валиком вокруг шеи: сзади толстый и высокий, к груди сходит на нет
        hood = M.torus("Hood", 0.48, 0.17, 96, 24)

        def hood_shape(co):
            a = math.atan2(co.y, co.x)
            c = Vector((0.48 * math.cos(a), 0.48 * math.sin(a), 0.0))
            back = (1 + math.sin(a)) / 2
            f = 0.35 + 0.65 * back
            o = (co - c) * f
            o.z *= 1.0 + 0.7 * back
            return c * (1.0 + 0.12 * back) + o + Vector((0, 0, 0.08 * back))
        M.deform(hood, hood_shape)
        hood.location = (0, 0.1, 0.52)
        M.apply_transform(hood)
        M.push_normals(hood, lambda co, n: 0.01 * math.sin(math.atan2(co.y - 0.1, co.x) * 9))
        parts.append(M.assign(M.smooth(hood), shirt))
        parts.append(collar_rib("Collar", trim, r=0.37, minor=0.06))
        for s in (-1, 1):
            a0, _ = body_surf(s * 0.13, 0.46, 0.03)
            pts = [a0, a0 + Vector((s * 0.01, -0.04, -0.12)), a0 + Vector((s * 0.03, -0.06, -0.3)),
                   a0 + Vector((s * 0.02, -0.07, -0.44))]
            parts.append(tube(f"Drawstring{s}", pts, 0.017, M.flat("String", (1.0, 0.98, 0.94), rough=0.5, sheen=0.5)))
            ag = ellipsoid(f"Aglet{s}", (0.025, 0.025, 0.05), glossy("Aglet", (0.85, 0.85, 0.9), rough=0.2, metal=1.0))
            parts.append(placed(ag, pts[-1] + Vector((0, 0, -0.04))))
            p, n = body_surf(s * 0.13, 0.42, 0.012)
            eyelet = M.torus(f"Eyelet{s}", 0.03, 0.009, 24, 8)
            eyelet.matrix_world = Matrix.Translation(p) @ (-n).to_track_quat("Z", "Y").to_matrix().to_4x4()
            M.apply_transform(eyelet)
            parts.append(M.assign(M.smooth(eyelet), glossy("Aglet", (0.85, 0.85, 0.9), rough=0.2, metal=1.0)))
    elif kind == "cardigan":
        # кардиган распахнут: в вырезе белая футболка
        M.assign_faces(body, shirt, [(lambda n, c: c.y < 0 and -0.5 < c.z < 0.62 and abs(c.x) < 0.05 + 0.3 * (c.z + 0.5) / 1.1,
                                      white)])
        parts.append(collar_rib("Collar", white, r=0.35, minor=0.05))
        for s in (-1, 1):
            pts = []
            for i in range(14):
                t = i / 13
                z = 0.5 - 0.95 * t
                x = s * (0.05 + 0.3 * (z + 0.5) / 1.1 + 0.02)
                pts.append(body_surf(x, z, 0.015)[0])
            parts.append(strand(f"Edge{s}", trim, pts, 0.05, 0.025, n=28, tip=0.02, root=0.02, root_w=1.0, groove=0.0,
                                up=Vector((0, -1, 0)), blunt=True))
        for k, z in enumerate((0.02, -0.2)):
            x = -(0.05 + 0.3 * (z + 0.5) / 1.1 + 0.02)
            p, n = body_surf(x, z, 0.03)
            parts += button(f"Button{k}", p, n, 0.036, glossy("BtnCream", (0.98, 0.92, 0.78), rough=0.2), holes)
    elif kind == "tailcoat":
        M.assign_faces(body, shirt, [(lambda n, c: c.y < 0 and -0.5 < c.z < 0.6 and abs(c.x) < 0.12 + 0.3 * (c.z + 0.4) / 0.9,
                                      white)])
        satin = M.material("Satin", [(0.0, (0.05, 0.05, 0.07)), (1.0, (0.22, 0.22, 0.27))], coord="z", lo=-0.5, hi=0.5,
                           rough=0.22, coat=0.6, sheen=0.3)
        for s in (-1, 1):
            parts.append(flap(f"Lapel{s}", satin, (s * 0.36, 0.42), math.radians(-90 - s * 22), 0.62, 0.2, 0.06, lift=0.04,
                              round_tip=False))
            # стоячий воротничок-"бабочка" рубашки
            parts.append(flap(f"Wing{s}", white, (s * 0.08, 0.53), math.radians(-90 + s * 55), 0.13, 0.12, 0.05,
                              lift=0.05))
        parts.append(collar_rib("Collar", white, r=0.35, minor=0.06, ribs=0))
        stud = glossy("Stud", (0.08, 0.08, 0.1), rough=0.15, coat=1.0)
        for k, z in enumerate((0.1, -0.1)):
            p, n = body_surf(0.0, z, 0.01)
            parts += button(f"Stud{k}", p, n, 0.03, stud)
        parts.append(placket("ShirtPleat", white, 0.0, 0.3, -0.35, 0.06, lift=0.012))
        # бабочка: два крыла со складками и узелок
        bow_mat = M.material("BowMat", [(0.0, (0.62, 0.06, 0.09)), (1.0, (0.92, 0.16, 0.18))], coord="z", lo=0.15, hi=0.35,
                             rough=0.3, sheen=0.6, coat=0.3)
        for side in (-1, 1):
            w = M.sphere(f"Bow{side}", 1.0, 48, 24)
            M.deform(w, lambda co, side=side: Vector((co.x * 0.2 * (1 + 0.5 * side * co.x),
                                                      co.y * 0.08 * (1 - 0.3 * abs(co.z)),
                                                      co.z * 0.14 * (1 + 0.6 * side * co.x) *
                                                      (1 - 0.12 * math.cos(co.z * 9) * max(0.0, side * co.x)))))
            w.location = (side * 0.17, -0.77, 0.24)
            M.apply_transform(w)
            parts.append(M.assign(M.smooth(w), bow_mat))
        knot = ellipsoid("BowKnot", (0.07, 0.07, 0.085), bow_mat)
        parts.append(placed(knot, (0, -0.83, 0.24)))
    elif kind == "cape":
        # высокий стоячий воротник-пелерина и брошь
        # большой острый воротник накидки на розовой подкладке, брошь и вышитые звездочки
        lining = M.material("CapeLining", [(0.0, (0.62, 0.16, 0.36)), (1.0, (0.92, 0.36, 0.52))], coord="z", lo=0.0,
                            hi=0.6, rough=0.3, sheen=0.7, coat=0.3)
        parts.append(collar_rib("Collar", shirt, r=0.36, minor=0.07, ribs=0))
        for s in (-1, 1):
            parts.append(flap(f"CapeCollar{s}", lining, (s * 0.12, 0.5), math.radians(-90 + s * 52), 0.6, 0.34, 0.02,
                              lift=0.05, round_tip=False))
            parts.append(stitch_line(f"CapeStitch{s}", lambda t, s=s: body_surf(
                s * 0.12 + math.cos(math.radians(-90 + s * 52)) * 0.55 * t + s * 0.02,
                0.5 + math.sin(math.radians(-90 + s * 52)) * 0.55 * t + 0.11 * (1 - t), 0.055), 14,
                thread_mat((1.0, 0.8, 0.35)), size=(0.016, 0.006, 0.005)))
        p, n = body_surf(0.0, 0.38, 0.03)
        br = ellipsoid("Brooch", (0.075, 0.04, 0.09), glossy("BroochGem", (0.35, 0.85, 0.45), rough=0.06, coat=1.0))
        parts.append(placed(br, p + n * 0.02))
        rim = M.torus("BroochRim", 0.08, 0.018, 32, 8)
        rim.matrix_world = Matrix.Translation(p + n * 0.015) @ (-n).to_track_quat("Z", "Y").to_matrix().to_4x4() @ \
            Matrix.Diagonal((1.0, 1.2, 1.0, 1.0))
        M.apply_transform(rim)
        parts.append(M.assign(M.smooth(rim), gold_mat("BroochGold")))
        stars = []
        for x, z, r in ((-0.6, 0.0, 0.05), (0.55, -0.12, 0.04), (0.8, 0.12, 0.035), (-0.85, 0.2, 0.035)):
            p, n = body_surf(x, z, 0.012)
            for j in range(4):
                a = math.pi * j / 2 + 0.3
                stars.append(blob_matrix(p, (math.cos(a), 0, math.sin(a)), (r, r * 0.25, 0.008), n))
        parts.append(blobs("CapeStars", M.flat("StarGold", (1.0, 0.82, 0.3), rough=0.3, metal=0.6), stars))
    elif kind == "furcoat":
        fur = M.torus("FurCollar", 0.42, 0.13, 128, 20)
        fur.location = (0, 0.05, 0.5)
        M.apply_transform(fur)
        M.push_normals(fur, lambda co, n: 0.03 * M.fbm(co * 9) + 0.012 * M.fbm(co * 30))
        fm = M.material("CollarFur", [(0.0, (0.86, 0.9, 1.0)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.3, hi=0.65,
                        rough=0.85, sheen=1.0)
        _bump(fm, _felt_noise(fm, 120.0), strength=0.45)
        parts.append(M.assign(M.smooth(fur), fm))
        # полоса меха по борту и серебряный узор-снежинки
        parts.append(pillow("FurTrim", fm, body_surf, -0.4, 0.4, lambda u: 0.07, lambda u: -0.07, lift=0.06, base=-0.01,
                            nu=24, nv=8, power=0.4, end=0.05, origin=(0.0, 0.0), angle=math.pi / 2))
        silver = M.material("SilverThread", [(0.0, (0.75, 0.82, 0.95)), (1.0, (1.0, 1.0, 1.0))], coord="nz", lo=-1, hi=1,
                            rough=0.3, metal=0.7)
        flakes = []
        for x, z in ((-0.55, 0.05), (0.55, 0.05), (-0.85, -0.15), (0.85, -0.15), (-0.3, -0.2), (0.3, -0.2)):
            p, n = body_surf(x, z, 0.01)
            for j in range(6):
                a = math.pi * j / 3
                d = Vector((math.cos(a), 0, math.sin(a)))
                flakes.append(blob_matrix(p + d * 0.035, d, (0.04, 0.01, 0.008), n))
        parts.append(blobs("CoatFlakes", silver, flakes))
    elif kind == "ruffle":
        # волнистый воротник-оборка в карамельную полоску
        frill = M.material("Frill", [(0.0, (1.0, 0.98, 0.98)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0.2, hi=0.6, rough=0.4,
                           sheen=0.6, coat=0.3)
        add_bands(frill, (1.0, 0.45, 0.65), axis="X", freq=7.0, width=0.3)
        parts.append(collar_drape("Ruffle", frill, 0.0, 0.3, lift=0.03, scallops=18, amp=0.035, wave=0.05))
        parts.append(collar_rib("Collar", frill, r=0.35, minor=0.055, ribs=0))
        p, n = body_surf(0.0, 0.33, 0.03)
        bow_m = glossy("RuffleBow", (0.45, 0.78, 1.0), rough=0.2, coat=0.8)
        for s in (-1, 1):
            w = ellipsoid(f"RBow{s}", (0.09, 0.03, 0.06), bow_m)
            w.rotation_euler = (0, math.radians(s * 20), 0)
            parts.append(placed(w, p + Vector((s * 0.08, -0.02, 0))))
        parts.append(placed(ellipsoid("RBowKnot", (0.035, 0.03, 0.04), bow_m), p + Vector((0, -0.04, 0))))
    elif kind == "plaid":
        parts.append(collar_rib("Collar", shirt, r=0.35, minor=0.06, ribs=0))
        denim = fabric_mat("Denim", (0.26, 0.40, 0.62), weave=160.0, bump=0.25, rough=0.7, lo=-0.6, hi=0.6)
        brass = gold_mat("Brass")
        gold_thread = thread_mat((0.95, 0.75, 0.3))
        for s in (-1, 1):
            ang = math.pi / 2 - s * 0.2
            ox = s * 0.45

            def strap_pt(u, w, lift, ang=ang, ox=ox):
                return body_surf(ox + u * math.cos(ang) - w * math.sin(ang), u * math.sin(ang) + w * math.cos(ang), lift)
            parts.append(pillow(f"Strap{s}", denim, body_surf, -0.45, 0.42, lambda u: 0.075, lambda u: -0.075, lift=0.022,
                                base=-0.006, nu=24, nv=8, power=0.3, end=0.04, origin=(ox, 0.0), angle=ang))
            p, n = strap_pt(-0.12, 0.0, 0.025)
            parts += button(f"Brass{s}", p, n, 0.048, brass)
            for e, w in enumerate((-0.05, 0.05)):
                parts.append(stitch_line(f"StrapStitch{s}{e}", lambda t, w=w, sp=strap_pt: sp(-0.45 + 0.85 * t, w, 0.026),
                                         18, gold_thread, size=(0.016, 0.005, 0.004)))
    return shirt


def body_top_z(x, y):
    q = 1 - (x / BODY_AX.x) ** 2 - ((y - BODY_C.y) / BODY_AX.y) ** 2
    return BODY_C.z + BODY_AX.z * math.sqrt(max(q, 0.0))


def collar_drape(name, mat, d0, d1, lift=0.03, scallops=0, amp=0.0, wave=0.0, nu=192, nv=8, thick=0.025):
    """Воротник, лежащий на плечах вокруг шеи: кольцо от d0 до d1 от шеи, край волной (scallops)."""
    verts, faces = [], []
    for i in range(nu):
        a = 2 * math.pi * i / nu
        for j in range(nv + 1):
            t = j / nv
            d = d0 + (d1 + amp * math.cos(scallops * a)) * t if scallops else d0 + d1 * t
            r = 0.34 + d
            x, y = r * math.cos(a), 0.05 + r * math.sin(a)
            z = body_top_z(x, y) + lift + wave * t * t * math.sin(scallops * a) + 0.01 * (1 - t)
            verts.append(Vector((x, y, z)))
    for i in range(nu):
        for j in range(nv):
            a, b = i * (nv + 1) + j, ((i + 1) % nu) * (nv + 1) + j
            faces.append((a, a + 1, b + 1, b))
    ob = mesh_obj(name, verts, faces)
    M.solidify(ob, thick, 0.0)
    M.smooth(ob)
    return M.assign(ob, mat)


# MARK: - Аксессуары

def glasses(parts):
    frame = glossy("Frame", (0.15, 0.12, 0.12), rough=0.2, coat=0.8)
    glass = M.material("Glass", [(0.0, (0.85, 0.92, 1.0)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=0, hi=1, rough=0.02,
                       transmission=1.0, alpha=0.25, coat=1.0, coat_rough=0.0)
    for side in (-1, 1):
        x = side * EYE_X
        p, n = head_surf(x, HEAD_Z + EYE_DZ, 0.085)
        rot = (-n).to_track_quat("Z", "Y").to_matrix().to_4x4()
        ring = M.torus(f"Lens{side}", 0.19, 0.027, 64, 12)
        ring.matrix_world = Matrix.Translation(p) @ rot
        M.apply_transform(ring)
        parts.append(M.assign(M.smooth(ring), frame))
        sh = ellipsoid(f"LensShine{side}", (0.055, 0.008, 0.022), M.flat("LensShineM", (1, 1, 1), rough=0.1), 16, 8)
        sh.matrix_world = Matrix.Translation(p + Vector((-0.08, -0.01, 0.1))) @ rot @ Matrix.Rotation(math.radians(90), 4, "X") @ \
            Matrix.Rotation(math.radians(35), 4, "Y")
        M.apply_transform(sh)
        sh.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Alpha"].default_value = 0.7
        parts.append(sh)
        temple = M.tube(f"Temple{side}", [p + Vector((side * 0.19, 0.03, 0.02)), Vector((side * 0.82, -0.45, HEAD_Z + 0.06)),
                                          Vector((side * 0.99, -0.05, HEAD_Z + 0.05))], 0.02)
        parts.append(M.assign(M.smooth(temple), frame))
    pts = []
    for i in range(9):
        t = -1 + 2 * i / 8
        xx = (EYE_X - 0.19) * t
        p, _ = head_surf(xx, HEAD_Z + EYE_DZ + 0.06 + 0.025 * (1 - t * t), 0.085)
        pts.append(p)
    parts.append(tube("Bridge", pts, 0.022, frame))


def monocle(parts):
    gold = gold_mat("Monocle")
    x = EYE_X
    p, n = head_surf(x, HEAD_Z + EYE_DZ, 0.08)
    rot = (-n).to_track_quat("Z", "Y").to_matrix().to_4x4()
    ring = M.torus("MonocleRing", 0.2, 0.032, 64, 12)
    ring.matrix_world = Matrix.Translation(p) @ rot
    M.apply_transform(ring)
    parts.append(M.assign(M.smooth(ring), gold))
    sh = ellipsoid("MonocleShine", (0.07, 0.008, 0.025), M.flat("MonoShine", (1, 1, 1), rough=0.1), 16, 8)
    sh.matrix_world = Matrix.Translation(p + Vector((-0.06, -0.012, 0.11))) @ rot @ Matrix.Rotation(math.radians(90), 4, "X") @ \
        Matrix.Rotation(math.radians(30), 4, "Y")
    M.apply_transform(sh)
    parts.append(sh)
    chain_pts = [p + Vector((0.16, -0.02, -0.1)), Vector((0.62, -0.7, HEAD_Z - 0.45)), Vector((0.6, -0.62, HEAD_Z - 0.8))]
    links_m = []
    path, L = resample(catmull(chain_pts, 12), 40)
    for k in range(len(path) - 1):
        a, b = path[k], path[k + 1]
        links_m.append(blob_matrix((a + b) / 2, b - a, (0.016, 0.009 if k % 2 else 0.005, 0.005 if k % 2 else 0.009),
                                   Vector((0, -1, 0))))
    parts.append(blobs("MonocleChain", gold, links_m, 10, 6))


def bandana(parts):
    red = fabric_mat("Bandana", (0.86, 0.16, 0.14), weave=140.0, bump=0.15, rough=0.55, lo=0.0, hi=0.8)
    # белый горошек-"пейсли" точками
    nt = red.node_tree
    tc = nt.nodes.new("ShaderNodeTexCoord")
    vor = nt.nodes.new("ShaderNodeTexVoronoi")
    vor.inputs["Scale"].default_value = 14.0
    nt.links.new(tc.outputs["Object"], vor.inputs["Vector"])
    mr = _node(nt.nodes, "ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = 0.16
    mr.inputs["From Max"].default_value = 0.12
    nt.links.new(vor.outputs["Distance"], mr.inputs["Value"])
    M._mix_over(red, mr.outputs["Result"], (1.0, 0.95, 0.9))
    scarf = M.torus("Scarf", 0.42, 0.11, 96, 16)
    M.push_normals(scarf, lambda co, n: 0.02 * math.sin(math.atan2(co.y, co.x) * 7) * abs(co.z) / 0.11)
    scarf.location = (0, 0.02, 0.56)
    M.apply_transform(scarf)
    M.smooth(scarf)
    M.assign(scarf, red)
    tri = pillow("ScarfTip", red, body_surf, -0.36, 0.36, lambda u: 0.47 - 0.02 * (u / 0.36) ** 2,
                 lambda u: 0.47 - 0.42 * (1 - abs(u) / 0.36) ** 1.2, lift=0.045, base=-0.01, nu=32, nv=12, power=0.4, end=0.2)
    M.push_normals(tri, lambda co, n: 0.008 * math.sin((co.x * 0.6 + co.z) * 30))
    M.assign(tri, red)
    parts += [scarf, tri]


def neckerchief(parts):
    yellow = fabric_mat("FarmerScarf", (0.98, 0.78, 0.22), weave=140.0, bump=0.15, rough=0.55, lo=0.2, hi=0.8)
    add_bands(yellow, (0.85, 0.35, 0.15), axis="X", freq=6.0, width=0.08)
    add_bands(yellow, (0.85, 0.35, 0.15), axis="Z", freq=6.0, width=0.08)
    scarf = M.torus("Scarf", 0.42, 0.1, 96, 16)
    M.push_normals(scarf, lambda co, n: 0.015 * math.sin(math.atan2(co.y, co.x) * 8) * abs(co.z) / 0.1)
    scarf.location = (0, 0.02, 0.56)
    M.apply_transform(scarf)
    M.assign(M.smooth(scarf), yellow)
    p, n = body_surf(0.0, 0.45, 0.04)
    knot = ellipsoid("ScarfKnot", (0.1, 0.07, 0.08), yellow)
    parts += [scarf, placed(knot, p)]
    for s in (-1, 1):
        end = pillow(f"ScarfEnd{s}", yellow, body_surf, 0.0, 0.22, lambda u: 0.05 * (1 - 0.3 * u / 0.22),
                     lambda u: -0.05 * (1 - 0.3 * u / 0.22), lift=0.035, base=-0.005, nu=16, nv=8, power=0.4, end=0.1,
                     origin=(s * 0.03, 0.42), angle=math.radians(-90 + s * 25))
        parts.append(end)


def freckles(parts):
    dots = M.flat("Freckle", (0.72, 0.42, 0.28), rough=0.5)
    rnd = random.Random(3)
    mats = []
    for side in (-1, 1):
        for k in range(7):
            x = side * (0.42 + rnd.uniform(-0.1, 0.14))
            z = HEAD_Z - 0.14 + rnd.uniform(-0.09, 0.07)
            p, n = head_surf(x, z, 0.0)
            r = rnd.uniform(0.014, 0.022)
            mats.append(blob_matrix(p, (1, 0, 0), (r, r, 0.006), n))
    parts.append(blobs("Freckles", dots, mats, 10, 6))


# MARK: - Сборка

def build(spec, mood, face_on=True):
    skin_key, style, hair_col, shirt_col, acc = spec[:5]
    extra = spec[5] if len(spec) > 5 else {}
    rnd = random.Random(sum(ord(ch) * (k + 1) for k, ch in enumerate(style + skin_key)))
    skin = SKIN[skin_key]
    blush = {"happy": 0.5, "joy": 0.75, "upset": 0.32, "wait": 0.3}[mood]
    if skin_key in ("brown", "dark"):
        blush *= 0.75
    skin_m = skin_mat(skin, blush)
    hm = [hair_mat(f"Hair{k}" if k else "Hair", hair_col, k=kk) for k, kk in enumerate((1.0, 0.9, 1.1))]
    base_m = M.flat("HairBase", shade(hair_col, 0.45), rough=0.6)
    parts = []

    head = M.sphere("Head", 1.0, 96, 64)
    M.deform(head, lambda co: Vector((co.x * 1.0, co.y * 0.96, co.z * 0.98)))
    head.location = (0, 0, HEAD_Z)
    M.apply_transform(head)
    M.smooth(head)
    M.assign(head, skin_m)
    parts.append(head)
    for side in (-1, 1):
        ear = ellipsoid(f"Ear{side}", (0.09, 0.14, 0.2), skin_m)
        parts.append(placed(ear, (side * 0.97, 0.05, HEAD_Z - 0.02)))
    neck = M.cylinder("Neck", 0.32, 0.5, 48)
    neck.location = (0, 0.05, 0.5)
    M.apply_transform(neck)
    M.smooth(neck)
    M.assign(neck, skin_m)
    parts.append(neck)
    garment(extra.get("garment", "plain"), shirt_col, parts)

    if face_on:
        brow_col = (0.16, 0.1, 0.07) if style == "bald" else None
        if style == "tophat":
            brow_col = (0.62, 0.60, 0.60)
        parts += face(mood, extra.get("eyes", "brown"), skin_m, hair_col, brow_col, glasses=(acc == "glasses"))

    # прическа
    hl = None
    if style == "short":
        hl = hairline_default(62, 84, 112)
        parts += hair_short(hm, rnd, part=extra.get("part", 1))
    elif style in ("bob", "fairy"):
        hl = hairline_default(56, 90, 130)
        parts += hair_bob(hm, rnd, long=(style == "fairy"), wavy=(6.0 if style == "fairy" else 0.0))
    elif style == "witch":
        hl = hairline_default(56, 90, 130)
        parts += hair_bob(hm, rnd, long=True, start_th=44)
    elif style == "bangs":
        hl = hairline_default(56, 90, 112)
        parts += hair_bangs(hm, rnd)
    elif style == "curly":
        hl = hairline_default(56, 84, 110)
        parts += hair_curly(hm, rnd)
    elif style == "bun":
        hl = hairline_default(60, 86, 114)
        parts += hair_bun(hm, rnd)
    elif style == "pony":
        hl = hairline_default(62, 88, 112)
        parts += hair_pony(hm, rnd)
    elif style == "bald":
        parts += hair_horseshoe(hm, rnd)
    elif style == "cap":
        hl = hairline_default(70, 86, 110)
        parts += hair_under_hat(hm, rnd, th0=70, side_end=92, back_end=112, front_gap=70)
    elif style == "beanie":
        hl = hairline_default(66, 86, 110)
        parts += hair_under_hat(hm, rnd, th0=64, side_end=92, back_end=112, front_gap=62,
                                fringe=((-34, 74, 10), (-14, 72, 12), (8, 73, 12), (30, 75, 10)))
    elif style == "tophat":
        hl = hairline_default(60, 84, 110)
        parts += hair_under_hat(hm, rnd, th0=58, side_end=98, back_end=110, front_gap=52)
    elif style == "snowmaiden":
        hl = hairline_default(56, 88, 112)
        parts += hair_under_hat(hm, rnd, th0=42, side_end=92, back_end=110, front_gap=44,
                                fringe=((-30, 62, -10), (-10, 60, -8), (10, 60, 8), (30, 62, 10)))
    elif style in ("cowboy", "straw"):
        hl = hairline_default(62, 86, 110)
        fr = ((-30, 66, 10), (-8, 65, 12), (16, 66, 12)) if style == "straw" else ((-22, 66, 10), (4, 65, 10))
        parts += hair_under_hat(hm, rnd, th0=56, side_end=92, back_end=110, front_gap=46, fringe=fr)
    if hl is not None:
        parts.append(scalp("HairBase", base_m, lambda ph: hl(ph) - 3))

    # шапки и костюмы
    if style == "tophat":
        hat_tophat(parts)
    elif style == "cap":
        hat_cap(parts, shirt_col)
    elif style == "beanie":
        hat_beanie(parts, shirt_col)
    elif style == "witch":
        hat_witch(parts)
    elif style == "snowmaiden":
        hat_snowmaiden(parts)
        for side in (-1, 1):
            parts += braid(side, hm, rnd)
    elif style == "fairy":
        hat_tiara(parts)
    elif style in ("cowboy", "straw"):
        hat_brimmed(parts, style)

    if acc == "glasses":
        glasses(parts)
    if acc == "gourmet":
        monocle(parts)
        parts += moustache("Moustache", hm, rnd, width=0.25, droop=-0.01, curl=0.035, thick=0.05)
    if acc == "moustache":
        parts += moustache("Moustache", hm, rnd, width=0.22, droop=0.06, thick=0.055)
    if acc == "bandana":
        bandana(parts)
        parts += moustache("Moustache", hm, rnd, width=0.22, droop=0.08, thick=0.05)
    if acc == "freckles":
        freckles(parts)
        neckerchief(parts)
    return parts


def braid(side, hm, rnd):
    """Коса через плечо: чередующиеся дольки-пряди, резинка и кисточка."""
    parts = []
    ctrl = [Vector((side * 0.86, 0.1, HEAD_Z - 0.1)), Vector((side * 0.98, -0.25, HEAD_Z - 0.75)),
            Vector((side * 0.9, -0.62, 0.1)), Vector((side * 0.82, -0.78, -0.3))]
    path, L = resample(catmull(ctrl, 12), 60)
    mats = []
    nseg = 11
    for k in range(nseg):
        t = (k + 0.5) / nseg
        i = int(t * (len(path) - 1))
        p = path[i]
        T = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        out = Vector((side, -0.6, 0.0)).normalized()
        out = (out - T * out.dot(T)).normalized()
        sideways = T.cross(out).normalized()
        r = 0.16 * (1 - 0.3 * t)
        s = 1 if k % 2 else -1
        axis = (T + sideways * s * 0.9).normalized()
        mats.append(blob_matrix(p + sideways * s * r * 0.45 + out * 0.01, axis, (r * 1.15, r * 0.62, r * 0.75), out))
    bm = blobs(f"Braid{side}", hm[0], mats, 24, 14)
    parts.append(bm)
    core = strand(f"BraidCore{side}", hm[1], ctrl[:3] + [ctrl[3] * 0.98 + path[-1] * 0.02], 0.1, 0.1, n=40, tip=0.05,
                  root_w=1.0, up=Vector((side, -0.6, 0)), blunt=True, groove=0.0, flat=1.0)
    parts.append(core)
    tie_c = path[-6]
    tie = ellipsoid(f"BraidTie{side}", (0.12, 0.12, 0.08), glossy("TieMat", (0.30, 0.55, 0.95), rough=0.3, coat=0.6))
    parts.append(placed(tie, tie_c))
    for j in range(5):
        a = (j - 2) * 0.35
        ctrl2 = [tie_c, tie_c + Vector((side * 0.03 * a, -0.05, -0.12)), tie_c + Vector((side * 0.06 * a, -0.06, -0.24))]
        parts.append(strand(f"Tassel{side}{j}", rnd.choice(hm), ctrl2, 0.04, 0.035, n=16, tip=0.5,
                            up=Vector((side, -0.6, 0))))
    return parts


def setup_camera(scene, index, meshes):
    if index in FRAMES:
        loc, scale = FRAMES[index]
        cam_data = bpy.data.cameras.new("Cam")
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = scale
        cam = bpy.data.objects.new("Cam", cam_data)
        scene.collection.objects.link(cam)
        d = Vector((math.sin(CAM_AZ) * math.cos(CAM_EL), -math.cos(CAM_AZ) * math.cos(CAM_EL), math.sin(CAM_EL)))
        cam.location = loc
        cam.rotation_euler = (-d).to_track_quat("-Z", "Y").to_euler()
        scene.camera = cam
        return cam
    lo, hi, pts = R.bounds(meshes)
    frame = [p for p in pts if p.z > -0.25] + [Vector((-1.25, 0, -0.25)), Vector((1.25, 0, -0.25))]
    center = Vector((0, 0, (max(p.z for p in frame) + min(p.z for p in frame)) / 2))
    return R.add_camera(scene, center, frame, azimuth=CAM_AZ, elevation=CAM_EL, margin=1.04)


def render(index, mood, out_dir, size=256, samples=64):
    scene = M.reset_scene(samples)
    build(CUSTOMERS[index], mood)
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    setup_camera(scene, index, meshes)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    scene.render.filepath = os.path.join(out_dir, f"customer_{index}_{mood}.png")
    bpy.ops.render.render(write_still=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--moods", default=",".join(MOODS))
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    ids = [int(x) for x in args.only.split(",") if x] or list(range(len(CUSTOMERS)))
    for i in ids:
        for mood in args.moods.split(","):
            render(i, mood, args.out, args.size, args.samples)
            print("rendered", i, mood, flush=True)


if __name__ == "__main__":
    main()
