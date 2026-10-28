"""Процедурные модели продуктов Sortelier в стиле мягких 3D-иконок.

Каждый продукт собирается из простых форм, которые потом деформируются, сглаживаются
и получают материалы с градиентом, подповерхностным рассеянием и лаком.

Запуск: python models.py <папка вывода> [--only id,id] [--spin] [--size 360]
Нужен Blender как модуль Python (pip install bpy).
"""
import argparse
import math
import os
import random
import sys

import bpy
import bmesh  # доступен только после bpy
from mathutils import Euler, Matrix, Vector, noise

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import render as R  # noqa: E402  камера и границы общие

ELEVATION = math.radians(26)
AZIMUTH = math.radians(14)


# MARK: - Сцена и свет

def reset_scene(samples=96):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"
    scene.view_settings.view_transform = "Standard"
    scene.view_settings.look = "None"
    scene.render.threads_mode = "FIXED"
    scene.render.threads = 2

    world = bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.96, 0.95, 1.0, 1.0)
    bg.inputs[1].default_value = 0.3

    def area(name, power, loc, size, color):
        light = bpy.data.lights.new(name, type="AREA")
        light.energy = power
        light.size = size
        light.color = color
        obj = bpy.data.objects.new(name, light)
        obj.location = loc
        direction = -Vector(loc).normalized()
        obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
        scene.collection.objects.link(obj)

    # большой мягкий ключевой сверху слева, холодная заливка справа, яркий контровой сзади
    area("Key", 380, (-3.2, -3.6, 5.0), 4.5, (1.0, 0.96, 0.9))
    area("Fill", 110, (4.2, -2.6, 1.2), 5.0, (0.86, 0.92, 1.0))
    area("Rim", 420, (1.6, 4.8, 3.2), 3.0, (1.0, 0.98, 0.95))
    area("Top", 60, (0.0, 0.0, 6.0), 5.0, (1.0, 1.0, 1.0))
    return scene


# MARK: - Меши

def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def from_data(name, verts, faces):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in verts], [], faces)
    me.update()
    return link(bpy.data.objects.new(name, me))


def sphere(name, r=1.0, segs=64, rings=40):
    bm = bmesh.new()
    bmesh.ops.create_uvsphere(bm, u_segments=segs, v_segments=rings, radius=r)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def quad_sphere(name, cuts=24):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        v.co = v.co.normalized()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def rounded_disc(name, r=1.0, h=0.3, p=4.0, cuts=28):
    """Шайба со скругленным краем без звезды на крышке: суперэллипс в профиле."""
    ob = quad_sphere(name, cuts)
    half = h / 2

    def shape(co):
        rr = math.hypot(co.x, co.y)
        k = 1.0 / ((rr ** p + (abs(co.z)) ** p) ** (1.0 / p))
        return Vector((co.x * k * r, co.y * k * r, co.z * k * half))
    return deform(ob, shape)


def tube(name, pts, radius, taper=(1.0, 1.0), res=12):
    """Трубка вдоль точек: жилки листа, полоски соуса."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = 4
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    n = len(pts)
    for i, p in enumerate(pts):
        sp.points[i].co = (*p, 1.0)
        t = i / max(1, n - 1)
        sp.points[i].radius = taper[0] + (taper[1] - taper[0]) * t
    ob = link(bpy.data.objects.new(name, cu))
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    mo = link(bpy.data.objects.new(name + "Mesh", me))
    bpy.data.objects.remove(ob, do_unlink=True)
    return mo


def cylinder(name, r=1.0, h=1.0, segs=64):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segs, radius1=r, radius2=r, depth=h)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def torus(name, major=1.0, minor=0.3, segs=96, ring=32):
    verts, faces = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        for j in range(ring):
            b = 2 * math.pi * j / ring
            x = (major + minor * math.cos(b)) * math.cos(a)
            y = (major + minor * math.cos(b)) * math.sin(a)
            verts.append((x, y, minor * math.sin(b)))
    for i in range(segs):
        for j in range(ring):
            a, b = i * ring + j, ((i + 1) % segs) * ring + j
            c, d = ((i + 1) % segs) * ring + (j + 1) % ring, i * ring + (j + 1) % ring
            faces.append((a, b, c, d))
    return from_data(name, verts, faces)


def polar_disc(name, rings=36, segs=144, rx=1.0, ry=1.0):
    """Диск из колец: удобно деформировать лист или слой начинки по радиусу и углу."""
    verts = [(0.0, 0.0, 0.0)]
    for i in range(1, rings + 1):
        t = i / rings
        for j in range(segs):
            a = 2 * math.pi * j / segs
            verts.append((rx * t * math.cos(a), ry * t * math.sin(a), 0.0))
    faces = [(0, 1 + j, 1 + (j + 1) % segs) for j in range(segs)]
    for i in range(rings - 1):
        base, nxt = 1 + i * segs, 1 + (i + 1) * segs
        for j in range(segs):
            faces.append((base + j, nxt + j, nxt + (j + 1) % segs, base + (j + 1) % segs))
    return from_data(name, verts, faces)


def profile_prism(name, points, height, z0=0.0):
    """Призма из многоугольника в плоскости XY."""
    n = len(points)
    verts = [(x, y, z0) for x, y in points] + [(x, y, z0 + height) for x, y in points]
    faces = [tuple(reversed(range(n))), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return from_data(name, verts, faces)


def lathe(name, profile, segs=96):
    """Тело вращения: profile - точки (радиус, высота) снизу вверх."""
    verts, faces = [], []
    m = len(profile)
    for i in range(segs):
        a = 2 * math.pi * i / segs
        for r, z in profile:
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(segs):
        for j in range(m - 1):
            a, b = i * m + j, ((i + 1) % segs) * m + j
            faces.append((a, b, b + 1, a + 1))
    ob = from_data(name, verts, faces)
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
    bm.to_mesh(me)
    bm.free()
    return ob


def modify(ob, kind, **props):
    m = ob.modifiers.new(kind.lower(), kind)
    for k, v in props.items():
        setattr(m, k, v)
    return m


def bake(ob):
    """Применяет модификаторы: результат становится обычным мешем."""
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    bpy.data.meshes.remove(old)
    return ob


def subdivide(ob, levels=2):
    modify(ob, "SUBSURF", levels=levels, render_levels=levels)
    return bake(ob)


def bevel(ob, width, segments=4, angle=40):
    m = modify(ob, "BEVEL", width=width, segments=segments, limit_method="ANGLE")
    m.angle_limit = math.radians(angle)
    m.harden_normals = False
    return bake(ob)


def solidify(ob, thickness, offset=0.0):
    modify(ob, "SOLIDIFY", thickness=thickness, offset=offset)
    return bake(ob)


def boolean_cut(ob, cutters):
    for c in cutters:
        m = modify(ob, "BOOLEAN", operation="DIFFERENCE", solver="EXACT")
        m.object = c
        bake(ob)
        bpy.data.objects.remove(c, do_unlink=True)
    return ob


def deform(ob, fn):
    """fn(Vector) -> Vector для каждой вершины."""
    for v in ob.data.vertices:
        v.co = fn(v.co.copy())
    ob.data.update()
    return ob


def push_normals(ob, fn):
    """Сдвиг вдоль нормали: fn(co, normal) -> расстояние."""
    ob.data.update()
    moves = [(v.index, v.normal.copy() * fn(v.co.copy(), v.normal.copy())) for v in ob.data.vertices]
    for i, d in moves:
        ob.data.vertices[i].co += d
    ob.data.update()
    return ob


def smooth(ob, sharp_angle=None):
    for p in ob.data.polygons:
        p.use_smooth = True
    if sharp_angle is not None:
        ob.data.set_sharp_from_angle(angle=math.radians(sharp_angle))
    return ob


def place(ob, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
    ob.location = loc
    ob.rotation_euler = rot
    ob.scale = scale
    return ob


def apply_transform(ob):
    ob.data.transform(ob.matrix_basis)
    ob.matrix_basis = Matrix.Identity(4)
    return ob


def fbm(p, octaves=3):
    return noise.fractal(p, 0.5, 2.0, octaves, noise_basis="PERLIN_ORIGINAL")


def scatter_on(target, count, make, seed=1, area=0.8, zmin=-1e9, dir_down=True, spacing=0.0):
    """Раскладывает мелкие детали (кунжут, посыпку) по поверхности сверху лучом вниз."""
    rnd = random.Random(seed)
    bpy.context.view_layer.update()
    dg = bpy.context.evaluated_depsgraph_get()
    inv = target.matrix_world.inverted()
    placed = []
    tries = 0
    while len(placed) < count and tries < count * 60:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi)
        r = area * math.sqrt(rnd.random())
        origin = Vector((r * math.cos(a), r * math.sin(a), 50.0))
        o_local = inv @ origin
        d_local = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
        ok, loc, nor, _ = target.ray_cast(o_local, d_local)
        if not ok:
            continue
        loc = target.matrix_world @ loc
        nor = (target.matrix_world.to_3x3() @ nor).normalized()
        if loc.z < zmin or nor.z < 0.25:
            continue
        if spacing and any((loc - q).length < spacing for q in placed):
            continue
        placed.append(loc)
        ob = make(len(placed) - 1, rnd)
        q = nor.to_track_quat("Z", "Y")
        spin = Matrix.Rotation(rnd.uniform(0, 2 * math.pi), 4, "Z")
        ob.matrix_world = Matrix.Translation(loc) @ q.to_matrix().to_4x4() @ spin @ ob.matrix_basis
    return placed


# MARK: - Материалы

def lin(c):
    """Цвета в палитре заданы как на экране (sRGB), Cycles считает в линейном пространстве."""
    return tuple(((v + 0.055) / 1.055) ** 2.4 if v > 0.04045 else v / 12.92 for v in c)


def material(name, stops, coord="z", lo=0.0, hi=1.0, rough=0.45, sss=0.0, sss_radius=(1.0, 0.45, 0.25),
             sss_scale=0.08, coat=0.0, coat_rough=0.08, spec=0.5, bump=0.0, bump_scale=12.0, bump_detail=4.0,
             vary=0.0, vary_scale=3.0, sheen=0.0, metal=0.0, transmission=0.0, alpha=1.0):
    """stops: [(позиция 0..1, (r, g, b))] вдоль coord: x, y, z, r (радиус в XY), nz (нормаль по Z)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    if coord in ("nx", "ny", "nz"):
        links.new(tc.outputs["Normal"], sep.inputs[0])
        value = sep.outputs[coord[1].upper()]
    elif coord in ("r", "r_yz", "r_xz"):
        mul = nodes.new("ShaderNodeVectorMath")
        mul.operation = "MULTIPLY"
        mul.inputs[1].default_value = {"r": (1, 1, 0), "r_yz": (0, 1, 1), "r_xz": (1, 0, 1)}[coord]
        ln = nodes.new("ShaderNodeVectorMath")
        ln.operation = "LENGTH"
        links.new(tc.outputs["Object"], mul.inputs[0])
        links.new(mul.outputs[0], ln.inputs[0])
        value = ln.outputs["Value"]
    else:
        links.new(tc.outputs["Object"], sep.inputs[0])
        value = sep.outputs[coord.upper()]
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = lo
    mr.inputs["From Max"].default_value = hi
    links.new(value, mr.inputs["Value"])
    fac = mr.outputs["Result"]
    if vary:
        nz = nodes.new("ShaderNodeTexNoise")
        nz.inputs["Scale"].default_value = vary_scale
        nz.inputs["Detail"].default_value = 3.0
        links.new(tc.outputs["Object"], nz.inputs["Vector"])
        sub = nodes.new("ShaderNodeMath")
        sub.operation = "SUBTRACT"
        sub.inputs[1].default_value = 0.5
        links.new(nz.outputs["Fac"], sub.inputs[0])
        sc = nodes.new("ShaderNodeMath")
        sc.operation = "MULTIPLY"
        sc.inputs[1].default_value = vary
        links.new(sub.outputs[0], sc.inputs[0])
        add = nodes.new("ShaderNodeMath")
        add.operation = "ADD"
        links.new(fac, add.inputs[0])
        links.new(sc.outputs[0], add.inputs[1])
        fac = add.outputs[0]
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*lin(stops[0][1]), 1)
    els[1].position, els[1].color = stops[-1][0], (*lin(stops[-1][1]), 1)
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = (*lin(col), 1)
    links.new(fac, ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Specular IOR Level"].default_value = spec
    bsdf.inputs["Metallic"].default_value = metal
    if sss:
        bsdf.inputs["Subsurface Weight"].default_value = sss
        bsdf.inputs["Subsurface Radius"].default_value = sss_radius
        bsdf.inputs["Subsurface Scale"].default_value = sss_scale
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = coat_rough
    if sheen:
        bsdf.inputs["Sheen Weight"].default_value = sheen
    if transmission:
        bsdf.inputs["Transmission Weight"].default_value = transmission
    if alpha < 1:
        bsdf.inputs["Alpha"].default_value = alpha
    if bump:
        bn = nodes.new("ShaderNodeTexNoise")
        bn.inputs["Scale"].default_value = bump_scale
        bn.inputs["Detail"].default_value = bump_detail
        links.new(tc.outputs["Object"], bn.inputs["Vector"])
        b = nodes.new("ShaderNodeBump")
        b.inputs["Strength"].default_value = bump
        b.inputs["Distance"].default_value = 0.02
        links.new(bn.outputs["Fac"], b.inputs["Height"])
        links.new(b.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def _mix_over(mat, fac_socket, color):
    """Подмешивает цвет поверх базового по маске fac_socket."""
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    base_link = bsdf.inputs["Base Color"].links[0]
    src = base_link.from_socket
    mix = nodes.new("ShaderNodeMix")
    mix.data_type = "RGBA"
    ins = [i for i in mix.inputs if i.type == "RGBA"]
    out = [o for o in mix.outputs if o.type == "RGBA"][0]
    links.new(fac_socket, mix.inputs[0])
    links.new(src, ins[0])
    ins[1].default_value = (*lin(color), 1)
    links.new(out, bsdf.inputs["Base Color"])
    return mix


def add_stripes(mat, color, scale=3.0, angle=30, width=0.18, nz_min=0.55, strength=0.9):
    """Темные полоски гриля сверху (по нормали вверх)."""
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    mp = nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(angle))
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "X"
    wave.inputs["Scale"].default_value = scale
    wave.inputs["Distortion"].default_value = 0.3
    links.new(tc.outputs["Object"], mp.inputs["Vector"])
    links.new(mp.outputs["Vector"], wave.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 1 - width - 0.06, (0, 0, 0, 1)
    els[1].position, els[1].color = 1 - width + 0.06, (strength, strength, strength, 1)
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Normal"], sep.inputs[0])
    mask = nodes.new("ShaderNodeMapRange")
    mask.inputs["From Min"].default_value = nz_min
    mask.inputs["From Max"].default_value = nz_min + 0.25
    links.new(sep.outputs["Z"], mask.inputs["Value"])
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "MULTIPLY"
    links.new(ramp.outputs["Color"], mul.inputs[0])
    links.new(mask.outputs["Result"], mul.inputs[1])
    _mix_over(mat, mul.outputs[0], color)
    return mat


def add_speckles(mat, color, scale=60.0, threshold=0.64, strength=0.7):
    """Мелкие крапинки: скорлупа, специи."""
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    tc = nodes.new("ShaderNodeTexCoord")
    nz = nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 2.0
    links.new(tc.outputs["Object"], nz.inputs["Vector"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = threshold, (0, 0, 0, 1)
    els[1].position, els[1].color = threshold + 0.02, (strength, strength, strength, 1)
    links.new(nz.outputs["Fac"], ramp.inputs["Fac"])
    _mix_over(mat, ramp.outputs["Color"], color)
    return mat


def flat(name, color, **kw):
    return material(name, [(0.0, color), (1.0, color)], **kw)


def assign(ob, mat):
    ob.data.materials.clear()
    ob.data.materials.append(mat)
    return ob


def assign_faces(ob, base, rules):
    """Разные материалы по граням: rules = [(условие(нормаль, центр), материал)], первое совпавшее."""
    assign(ob, base)
    for _, m in rules:
        ob.data.materials.append(m)
    for p in ob.data.polygons:
        for k, (cond, _) in enumerate(rules):
            if cond(p.normal, p.center):
                p.material_index = k + 1
                break
    return ob


def bisect(ob, co, no, fill=True):
    """Срезает часть меша по плоскости (остается сторона против нормали) и закрывает срез."""
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    res = bmesh.ops.bisect_plane(bm, geom=geom, plane_co=co, plane_no=no, clear_outer=True)
    if fill:
        edges = [e for e in res["geom_cut"] if isinstance(e, bmesh.types.BMEdge)]
        if edges:
            bmesh.ops.edgeloop_fill(bm, edges=edges)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def capsule(name, length, radius, segs=64, rings=48, pinch=0.0):
    """Капсула вдоль X: колбаска, багет, булка для хот-дога."""
    prof = []
    half = length / 2
    body = half - radius
    for i in range(rings + 1):
        t = -1 + 2 * i / rings
        z = t * half
        if abs(z) > body:
            u = (abs(z) - body) / radius
            r = radius * math.sqrt(max(0.0, 1 - u * u))
            r *= 1 - pinch * u ** 4
        else:
            r = radius
        prof.append((r, z))
    prof[0] = (0.0, -half)
    prof[-1] = (0.0, half)
    ob = lathe(name, prof, segs)
    ob.rotation_euler = (0, math.radians(90), 0)
    return apply_transform(ob)


def rotate_all(objs, rot, pivot=(0, 0, 0)):
    """Поворот группы объектов вокруг общей точки."""
    bpy.context.view_layer.update()
    m = Matrix.Translation(pivot) @ Euler(rot, "XYZ").to_matrix().to_4x4() @ Matrix.Translation(-Vector(pivot))
    for o in objs:
        o.matrix_world = m @ o.matrix_world
    bpy.context.view_layer.update()
    return objs


def bend(ob, radius):
    """Изгиб вдоль X дугой в плоскости XY (центр кривизны со стороны -Y)."""
    def fn(co):
        th = co.x / radius
        rr = radius + co.y
        return Vector((rr * math.sin(th), rr * math.cos(th) - radius, co.z))
    return deform(ob, fn)


# Палитра
CRUST_TOP = (0.72, 0.36, 0.10)
CRUST = (0.95, 0.60, 0.22)
CRUST_LIGHT = (1.0, 0.76, 0.38)
CRUMB = (1.0, 0.90, 0.68)
SEED = (1.0, 0.93, 0.74)


# MARK: - Продукты

def bun_top(name="BunTop", r=1.0, h=0.62, seeds=24, seed=3):
    ob = sphere(name, r)

    def shape(co):
        x, y, z = co
        if z >= 0:
            z *= h
        else:
            z *= 0.10
        # чуть шире у основания, как у настоящей булки
        k = 1.0 + 0.05 * (1 - abs(co.z))
        return Vector((x * k, y * k, z))
    deform(ob, shape)
    push_normals(ob, lambda co, n: 0.015 * fbm(co * 2.2))
    smooth(ob)
    assign(ob, material("BunTop", [(0.0, CRUMB), (0.14, CRUMB), (0.30, CRUST_LIGHT), (0.62, CRUST), (1.0, CRUST_TOP)],
                        coord="nz", lo=-1, hi=1, rough=0.38, sss=0.25, sss_radius=(1, 0.6, 0.3), coat=0.35,
                        bump=0.08, bump_scale=18, vary=0.12, vary_scale=2.5))
    seed_mat = material("Seed", [(0.0, (0.92, 0.78, 0.5)), (1.0, SEED)], coord="z", lo=-0.02, hi=0.02,
                        rough=0.3, sss=0.3, coat=0.3)

    def make(i, rnd):
        s = sphere(f"{name}Seed{i}", 1.0, 16, 10)
        s.scale = (0.075 * r, 0.042 * r, 0.026 * r)
        assign(s, seed_mat)
        smooth(s)
        return s
    if seeds:
        scatter_on(ob, seeds, make, seed=seed, area=0.82 * r, spacing=0.17 * r)
    return ob


def bun_bottom(name="BunBottom", r=1.0, h=0.32):
    ob = sphere(name, r)

    def shape(co):
        x, y, z = co
        # почти плоская шайба с мягким краем
        z = z * h * 0.5 if z < 0 else z * 0.06
        k = 1.0 - 0.06 * max(0.0, -co.z) ** 3
        return Vector((x * k, y * k, z))
    deform(ob, shape)
    push_normals(ob, lambda co, n: 0.01 * fbm(co * 2.5))
    smooth(ob)
    assign(ob, material("BunBottom", [(0.0, (0.78, 0.40, 0.1)), (0.45, CRUST), (0.80, CRUST_LIGHT), (0.92, CRUMB), (1.0, CRUMB)],
                        coord="nz", lo=-1, hi=1, rough=0.45, sss=0.25, coat=0.2, bump=0.06, bump_scale=22))
    return ob


def patty_obj(name="Patty", r=1.0, h=0.30):
    ob = rounded_disc(name, r, h, 3.0, 30)
    push_normals(ob, lambda co, n: 0.022 * fbm(co * 2.4, 3) + 0.008 * fbm(co * 9.0, 2))
    smooth(ob)
    mat = material("Patty", [(0.0, (0.36, 0.16, 0.07)), (0.35, (0.56, 0.28, 0.12)), (0.6, (0.62, 0.32, 0.14)),
                             (1.0, (0.50, 0.24, 0.10))],
                   coord="nz", lo=-1, hi=1, rough=0.34, sss=0.2, sss_radius=(1, 0.35, 0.2), coat=0.4,
                   coat_rough=0.2, bump=0.3, bump_scale=11, bump_detail=8, vary=0.14, vary_scale=3.0)
    add_stripes(mat, (0.22, 0.09, 0.04), scale=0.8 / r, angle=35, width=0.16)
    assign(ob, mat)
    return ob


def leaf_shape(rx, ry, cup, curl, ruffle, waves, seed):
    """Высота листа салата в точке (x, y): лодочка поперек, кончик загибается, край волной."""
    def zf(x, y):
        xn, yn = x / rx, y / ry
        r = min(1.0, math.hypot(xn, yn))
        a = math.atan2(yn, xn)
        z = cup * yn * yn + curl * xn + 0.6 * curl * max(0.0, xn) ** 2
        edge = max(0.0, (r - 0.55) / 0.45) ** 1.5
        z += ruffle * edge * math.sin(waves * a + seed + 2.2 * fbm(Vector((xn, yn, seed)) * 1.6))
        z += 0.03 * fbm(Vector((xn * 2.5, yn * 2.5, seed + 3)))
        return z
    return zf


def lettuce_leaf(name="Leaf", rx=1.25, ry=0.68, cup=0.45, curl=0.22, ruffle=0.075, waves=15, seed=0):
    ob = polar_disc(name, 36, 200, rx, ry)
    zf = leaf_shape(rx, ry, cup, curl, ruffle, waves, seed)

    def shape(co):
        xn = co.x / rx
        # к черешку лист уже
        ky = 1.0 - 0.35 * max(0.0, -xn) ** 1.6
        a = math.atan2(co.y, co.x)
        r = math.hypot(xn, co.y / ry)
        k = 1.0 + 0.035 * r ** 3 * math.sin(waves * 1.5 * a + seed)
        x, y = co.x * k, co.y * ky * k
        return Vector((x, y, zf(x, y)))
    deform(ob, shape)
    solidify(ob, 0.04, 0.0)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, material(f"{name}Mat", [(0.0, (0.74, 0.93, 0.32)), (0.35, (0.48, 0.83, 0.22)), (0.75, (0.24, 0.66, 0.15)),
                                       (1.0, (0.13, 0.50, 0.10))],
                        coord="r", lo=0.0, hi=rx, rough=0.3, sss=0.35, sss_radius=(0.5, 1.0, 0.3),
                        coat=0.4, coat_rough=0.12, bump=0.04, bump_scale=9, vary=0.1))
    vein_mat = flat(f"{name}VeinMat", (0.84, 0.96, 0.56), rough=0.32, sss=0.3, coat=0.3)
    parts = [ob]
    # центральная жилка переходит в черешок
    pts = [(x, 0.0, zf(x, 0.0) + 0.03) for x in [rx * (-1.12 + 1.95 * i / 30) for i in range(31)]]
    main = tube(f"{name}Vein", pts, 0.05, taper=(1.3, 0.25))
    assign(smooth(main), vein_mat)
    parts.append(main)
    for i, x0 in enumerate((-0.55, -0.15, 0.25, 0.6)):
        for side in (-1, 1):
            vp = []
            for k in range(12):
                t = k / 11
                x = (x0 + 0.34 * t) * rx
                y = side * t * ry * 0.5 * (1.0 - 0.3 * max(0.0, -x0))
                vp.append((x, y, zf(x, y) + 0.022))
            v = tube(f"{name}Side{i}{side}", vp, 0.022, taper=(1.0, 0.3))
            assign(smooth(v), vein_mat)
            parts.append(v)
    return parts


def lettuce():
    parts = lettuce_leaf("Leaf")
    # лист лицом к камере и по диагонали
    return rotate_all(parts, (math.radians(48), 0, math.radians(28)))


def cheese_wedge():
    pts = []
    R0 = 1.55
    for i in range(25):
        a = math.radians(-24 + 48 * i / 24)
        pts.append((R0 * math.cos(a) - 0.75, R0 * math.sin(a)))
    pts.append((-0.75, 0.0))
    ob = profile_prism("Cheese", pts, 0.78, 0.0)
    bevel(ob, 0.05, 4, 30)
    rnd = random.Random(7)
    cutters = []
    holes = [((0.2, -0.33, 0.78), 0.17), ((0.45, 0.2, 0.78), 0.12), ((-0.2, 0.05, 0.78), 0.1),
             ((0.78, -0.4, 0.35), 0.14), ((0.7, 0.2, 0.55), 0.1), ((0.1, -0.42, 0.25), 0.16),
             ((0.75, 0.05, 0.12), 0.1), ((0.35, 0.47, 0.35), 0.12)]
    for (x, y, z), r in holes:
        c = sphere("Hole", r, 32, 20)
        c.location = (x, y, z)
        cutters.append(c)
    bpy.context.view_layer.update()
    boolean_cut(ob, cutters)
    smooth(ob, 35)
    assign(ob, material("Cheese", [(0.0, (1.0, 0.50, 0.03)), (0.5, (1.0, 0.68, 0.08)), (1.0, (1.0, 0.80, 0.22))],
                        coord="z", lo=0.0, hi=0.78, rough=0.32, sss=0.45, sss_radius=(1.0, 0.7, 0.2), coat=0.3,
                        vary=0.08))
    return [ob]


def tomato():
    ob = sphere("Tomato", 1.0, 72, 48)

    def shape(co):
        x, y, z = co
        a = math.atan2(y, x)
        r = math.hypot(x, y)
        lobes = 1.0 + 0.045 * math.cos(5 * a) * r
        z = z * 0.82
        # ямка у плодоножки
        z -= 0.16 * math.exp(-(r / 0.22) ** 2) * (1 if z > 0 else 0)
        return Vector((x * lobes, y * lobes, z))
    deform(ob, shape)
    smooth(ob)
    assign(ob, material("Tomato", [(0.0, (0.86, 0.16, 0.06)), (0.55, (0.96, 0.18, 0.08)), (1.0, (0.78, 0.07, 0.05))],
                        coord="z", lo=-0.85, hi=0.85, rough=0.18, sss=0.35, sss_radius=(1.0, 0.25, 0.15),
                        coat=0.7, coat_rough=0.05, vary=0.08))
    green = material("Calyx", [(0.0, (0.16, 0.52, 0.12)), (1.0, (0.45, 0.82, 0.25))], coord="z", lo=0.6, hi=0.9,
                     rough=0.35, sss=0.3, coat=0.3)
    parts = [ob]
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.3
        leaf = sphere(f"Sepal{i}", 1.0, 24, 12)
        leaf.scale = (0.30, 0.085, 0.03)
        apply_transform(leaf)
        def drape(co):
            r = co.x + 0.29
            zs = 0.82 * math.sqrt(max(0.0, 1 - r * r)) - 0.16 * math.exp(-(r / 0.22) ** 2)
            return Vector((r, co.y, zs + 0.03 + co.z + 0.06 * r))
        deform(leaf, drape)
        leaf.rotation_euler = (0, 0, a)
        smooth(leaf)
        assign(leaf, green)
        parts.append(leaf)
    stem = lathe("Stem", [(0.0, 0.0), (0.055, 0.0), (0.045, 0.16), (0.06, 0.2), (0.0, 0.22)], 24)
    stem.location = (0, 0, 0.62)
    stem.rotation_euler = (math.radians(12), 0, 0)
    smooth(stem)
    assign(stem, green)
    parts.append(stem)
    return parts


def stack(parts):
    """Ставит части друг на друга снизу вверх: [(объекты, зазор)]."""
    z = 0.0
    out = []
    for objs, gap in parts:
        lo, hi, _ = R.bounds(objs)
        dz = z - lo.z
        for o in objs:
            o.location.z += dz
        bpy.context.view_layer.update()
        z = hi.z + dz + gap
        out += objs
    return out


def lettuce_layer(name="LettuceLayer", r=1.12):
    ob = polar_disc(name, 24, 180, r, r)

    def shape(co):
        rr = math.hypot(co.x, co.y) / r
        a = math.atan2(co.y, co.x)
        z = 0.0
        if rr > 0.78:
            t = (rr - 0.78) / 0.22
            z = -0.10 * t + 0.07 * math.sin(16 * a + 2 * fbm(co * 1.3)) * t
        k = 1.0 + 0.04 * math.sin(9 * a) * (rr > 0.8)
        return Vector((co.x * k, co.y * k, z))
    deform(ob, shape)
    solidify(ob, 0.05)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, material("LettuceLayer", [(0.0, (0.55, 0.86, 0.28)), (0.75, (0.40, 0.78, 0.22)), (1.0, (0.20, 0.58, 0.14))],
                        coord="r", lo=0.0, hi=r, rough=0.3, sss=0.35, sss_radius=(0.5, 1.0, 0.3), coat=0.35))
    return ob


def cheese_slice(name="CheeseSlice", size=1.7):
    ob = polar_disc(name, 20, 4 * 30, 1, 1)

    def shape(co):
        # квадрат из диска: углы свисают вниз
        a = math.atan2(co.y, co.x)
        rr = math.hypot(co.x, co.y)
        sq = rr / max(abs(math.cos(a)), abs(math.sin(a))) if rr > 0 else 0
        x, y = sq * math.cos(a) * size / 2 * 0.98, sq * math.sin(a) * size / 2 * 0.98
        x, y = x * math.cos(0.5) - y * math.sin(0.5), x * math.sin(0.5) + y * math.cos(0.5)
        d = math.hypot(x, y)
        z = -0.55 * max(0.0, d - 0.95) ** 1.6
        return Vector((x, y, z))
    deform(ob, shape)
    solidify(ob, 0.05)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, material("CheeseSlice", [(0.0, (1.0, 0.66, 0.1)), (1.0, (1.0, 0.82, 0.25))], coord="z", lo=-0.3, hi=0.05,
                        rough=0.25, sss=0.45, coat=0.45))
    return ob


def dish_burger(cheese=False):
    bottom = bun_bottom("BBottom", 1.0)
    patty = patty_obj("BPatty", 1.08, 0.32)
    let = lettuce_layer("BLettuce", 1.12)
    layers = [([bottom], 0.0), ([let], -0.02), ([patty], -0.02)]
    if cheese:
        layers.append(([cheese_slice("BCheese", 1.75)], -0.03))
    top = bun_top("BTop", 1.0, 0.62, 26)
    seeds = [o for o in bpy.data.objects if o.name.startswith("BTopSeed")]
    layers.append(([top] + seeds, 0.0))
    return stack(layers)


def whole_bun():
    bottom = bun_bottom("Bottom", 1.0, 0.36)
    top = bun_top("Top", 1.0, 0.6, 24)
    seeds = [o for o in bpy.data.objects if o.name.startswith("TopSeed")]
    return stack([([bottom], 0.025), ([top] + seeds, 0.0)])


def patty():
    return [patty_obj("Patty", 1.0, 0.34)]



# MARK: - Хот-дог, кетчуп, хлеб, ветчина

def sausage_obj(name="Sausage", length=2.3, radius=0.27, curve=2.6):
    ob = capsule(name, length, radius, 64, 64, pinch=0.25)
    if curve:
        bend(ob, curve)
    push_normals(ob, lambda co, n: 0.006 * fbm(co * 6))
    smooth(ob)
    mat = material(f"{name}Mat", [(0.0, (0.55, 0.16, 0.08)), (0.5, (0.80, 0.30, 0.15)), (0.85, (0.92, 0.45, 0.26)),
                                  (1.0, (0.86, 0.38, 0.2))],
                   coord="nz", lo=-1, hi=1, rough=0.25, sss=0.3, sss_radius=(1, 0.3, 0.2), coat=0.6,
                   coat_rough=0.08, vary=0.08, bump=0.03, bump_scale=20)
    add_stripes(mat, (0.42, 0.12, 0.05), scale=0.7, angle=55, width=0.14, nz_min=0.3, strength=0.75)
    assign(ob, mat)
    return ob


def sausage():
    return [sausage_obj()]


def hotdog_bun_halves(name="HBun", length=2.5, radius=0.46, gap=0.05, open_deg=24):
    crust = material(f"{name}Crust", [(0.0, (0.86, 0.54, 0.22)), (0.45, (0.97, 0.70, 0.34)), (0.75, (0.96, 0.66, 0.30)),
                                      (1.0, (0.84, 0.50, 0.18))],
                     coord="nz", lo=-1, hi=1, rough=0.38, sss=0.25, coat=0.35, bump=0.06, bump_scale=18, vary=0.1)
    # мякиш с порами: светлый, с мелкими темными точками и рельефом
    crumb = material(f"{name}Crumb", [(0.0, (1.0, 0.88, 0.66)), (1.0, (0.98, 0.80, 0.54))], coord="r_xz", lo=0.0,
                     hi=1.3, rough=0.7, sss=0.25, bump=0.55, bump_scale=34, bump_detail=8, vary=0.12, vary_scale=6)
    add_speckles(crumb, (0.86, 0.66, 0.42), scale=48, threshold=0.62, strength=0.7)
    parts = []
    for side in (-1, 1):
        h = capsule(f"{name}{side}", length, radius, 64, 48)
        deform(h, lambda co: Vector((co.x, co.y, co.z * 0.92)))
        # оставляем внешнюю половину: срез по плоскости y = 0
        bisect(h, (0, 0, 0), (0, -side, 0))
        subdivide(h, 1)
        smooth(h, 50)
        assign_faces(h, crust, [(lambda n, c, s=side: n.y * s < -0.85, crumb)])
        h.location = (0, side * gap, 0)
        rotate_all([h], (math.radians(-side * open_deg), 0, 0), pivot=(0, side * gap, -radius * 0.8))
        parts.append(h)
    return parts


def hotdog_bun():
    parts = hotdog_bun_halves()
    rotate_all(parts, (0, 0, math.radians(-22)))
    # чуть наклоняем к камере, чтобы был виден разрез
    return rotate_all(parts, (math.radians(24), 0, 0))


def ketchup():
    red = material("Bottle", [(0.0, (0.72, 0.06, 0.04)), (0.5, (0.92, 0.12, 0.07)), (1.0, (0.98, 0.25, 0.14))],
                   coord="z", lo=0.0, hi=1.6, rough=0.15, sss=0.2, coat=0.8, coat_rough=0.04)
    body = lathe("Bottle", [(0.0, 0.0), (0.38, 0.0), (0.47, 0.06), (0.5, 0.18), (0.5, 1.15), (0.47, 1.32),
                             (0.36, 1.48), (0.22, 1.58), (0.2, 1.62), (0.0, 1.62)], 72)
    subdivide(body, 1)
    smooth(body)
    assign(body, red)
    cap_mat = material("Cap", [(0.0, (0.92, 0.90, 0.88)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=1.6, hi=2.0,
                       rough=0.25, coat=0.5)
    cap = lathe("Cap", [(0.0, 1.58), (0.24, 1.58), (0.25, 1.62), (0.24, 1.78), (0.2, 1.82), (0.0, 1.82)], 48)
    subdivide(cap, 1)
    smooth(cap)
    assign(cap, cap_mat)
    nozzle = lathe("Nozzle", [(0.0, 1.8), (0.12, 1.8), (0.07, 2.02), (0.04, 2.06), (0.0, 2.06)], 32)
    subdivide(nozzle, 1)
    smooth(nozzle)
    assign(nozzle, red)
    label = lathe("Label", [(0.508, 0.42), (0.512, 0.45), (0.512, 0.95), (0.508, 0.98)], 72)
    smooth(label)
    assign(label, material("Label", [(0.0, (1.0, 0.86, 0.3)), (1.0, (1.0, 0.94, 0.6))], coord="z", lo=0.42, hi=0.98,
                           rough=0.35, coat=0.4))
    # помидорка на этикетке
    dot = sphere("Dot", 0.15, 32, 20)
    dot.scale = (1.0, 0.3, 0.92)
    dot.location = (0.0, -0.52, 0.68)
    apply_transform(dot)
    smooth(dot)
    assign(dot, red)
    leaf = sphere("DotLeaf", 0.07, 24, 12)
    leaf.scale = (1.4, 0.3, 0.6)
    leaf.location = (0.06, -0.56, 0.83)
    apply_transform(leaf)
    smooth(leaf)
    assign(leaf, flat("DotLeafMat", (0.3, 0.7, 0.2), rough=0.35, coat=0.4))
    return [body, cap, nozzle, label, dot, leaf]


def toast_outline(w=1.6, h=1.25, lobe=0.48):
    cx = w / 2 - lobe + 0.06
    pts = []
    # низ и правый бок
    for i in range(8):
        pts.append((-w / 2 + w * i / 7, 0.0))
    for i in range(1, 6):
        pts.append((w / 2, h * i / 6))
    # правая и левая шапки
    th_mid = math.degrees(math.acos(-cx / lobe))
    for i in range(16):
        a = math.radians(-10 + (th_mid + 10) * i / 15)
        pts.append((cx + lobe * math.cos(a) + 0.02, h + lobe * math.sin(a)))
    for i in range(1, 16):
        a = math.radians(180 - th_mid + (th_mid + 10) * i / 15)
        pts.append((-cx + lobe * math.cos(a) - 0.02, h + lobe * math.sin(a)))
    for i in range(5, 0, -1):
        pts.append((-w / 2, h * i / 6))
    return pts


def bread():
    ob = profile_prism("Toast", toast_outline(), 0.30, -0.15)
    ob.rotation_euler = (math.radians(90), 0, 0)
    apply_transform(ob)
    bevel(ob, 0.07, 5, 30)
    smooth(ob, 40)
    crust = material("Crust", [(0.0, (0.80, 0.45, 0.14)), (1.0, (0.93, 0.62, 0.25))], coord="z", lo=0.0, hi=1.7,
                     rough=0.5, sss=0.2, coat=0.2, bump=0.08, bump_scale=16)
    crumb = material("Crumb", [(0.0, (1.0, 0.86, 0.58)), (1.0, (1.0, 0.93, 0.74))], coord="z", lo=0.0, hi=1.7,
                     rough=0.65, sss=0.25, bump=0.35, bump_scale=28, bump_detail=8)
    assign_faces(ob, crust, [(lambda n, c: abs(n.y) > 0.92, crumb)])
    ob.rotation_euler = (0, 0, math.radians(-12))
    return [ob]


def ham():
    body = sphere("Ham", 1.0, 72, 48)

    def shape(co):
        # капля: толстая к +X, сужается к кости
        x = co.x
        k = 0.62 + 0.38 * (x + 1) / 2
        return Vector((x * 1.05, co.y * k * 0.82, co.z * k * 0.78))
    deform(body, shape)
    bisect(body, (0.72, 0, 0), (1, 0, 0))
    subdivide(body, 1)
    smooth(body, 50)
    glaze = material("Glaze", [(0.0, (0.62, 0.22, 0.10)), (0.5, (0.86, 0.38, 0.18)), (1.0, (0.95, 0.55, 0.28))],
                     coord="nz", lo=-1, hi=1, rough=0.25, sss=0.3, coat=0.7, coat_rough=0.06, bump=0.08,
                     bump_scale=8, vary=0.12)
    cut = material("HamCut", [(0.0, (0.96, 0.55, 0.58)), (0.55, (0.98, 0.62, 0.64)), (0.72, (1.0, 0.92, 0.86)),
                              (0.82, (0.98, 0.70, 0.66)), (1.0, (0.9, 0.5, 0.5))],
                   coord="r_yz", lo=0.0, hi=0.62, rough=0.4, sss=0.4, sss_radius=(1, 0.4, 0.4), coat=0.3)
    assign_faces(body, glaze, [(lambda n, c: n.x > 0.9 and c.x > 0.6, cut)])
    bone_mat = material("Bone", [(0.0, (0.92, 0.86, 0.76)), (1.0, (1.0, 0.98, 0.94))], coord="nz", lo=-1, hi=1,
                        rough=0.35, sss=0.2, coat=0.3)
    bone = capsule("Bone", 0.62, 0.1, 32, 24)
    bone.location = (-1.12, 0, 0)
    smooth(bone)
    assign(bone, bone_mat)
    parts = [body, bone]
    for dy in (-0.09, 0.09):
        knob = sphere("Knob", 0.12, 32, 20)
        knob.location = (-1.42, dy, 0.02)
        smooth(knob)
        assign(knob, bone_mat)
        parts.append(knob)
    center = sphere("BoneCut", 0.1, 24, 16)
    center.scale = (0.25, 1, 1)
    center.location = (0.72, 0.05, 0.08)
    apply_transform(center)
    smooth(center)
    assign(center, bone_mat)
    parts.append(center)
    return rotate_all(parts, (0, math.radians(-8), math.radians(-28)))


# MARK: - Багет, яйцо, молоко, мед, картошка

def box_mesh(name, sx, sy, sz, z0=0.0, cuts=0):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    if cuts:
        bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    for v in bm.verts:
        v.co = Vector((v.co.x * sx, v.co.y * sy, v.co.z * sz + sz / 2 + z0))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return link(bpy.data.objects.new(name, me))


def baguette():
    ob = capsule("Baguette", 2.7, 0.42, 64, 64, pinch=0.15)
    deform(ob, lambda co: Vector((co.x, co.y, co.z * 0.86)))
    push_normals(ob, lambda co, n: 0.012 * fbm(co * 3))
    smooth(ob)
    assign(ob, material("BaguetteCrust", [(0.0, (0.80, 0.46, 0.14)), (0.45, (0.93, 0.62, 0.24)), (0.8, (0.88, 0.52, 0.17)),
                                          (1.0, (0.74, 0.40, 0.12))],
                        coord="nz", lo=-1, hi=1, rough=0.45, sss=0.2, coat=0.3, bump=0.1, bump_scale=14, vary=0.12))
    score = material("Score", [(0.0, (0.98, 0.78, 0.44)), (1.0, (1.0, 0.88, 0.60))], coord="z", lo=0.28, hi=0.38,
                     rough=0.55, sss=0.25, bump=0.2, bump_scale=30)
    parts = [ob]
    for i, x in enumerate((-0.78, -0.26, 0.26, 0.78)):
        sc = sphere(f"Score{i}", 1.0, 32, 16)
        sc.scale = (0.3, 0.09, 0.06)
        sc.rotation_euler = (0, 0, math.radians(38))
        sc.location = (x, 0.0, 0.335)
        apply_transform(sc)
        deform(sc, lambda co: Vector((co.x, co.y, co.z - 0.5 * co.y * co.y - 0.25 * (co.x - x) ** 2)))
        smooth(sc)
        assign(sc, score)
        parts.append(sc)
    return rotate_all(parts, (0, 0, math.radians(36)))


def egg():
    ob = sphere("Egg", 1.0, 72, 48)

    def shape(co):
        z = co.z
        k = 1.0 - 0.13 * z
        return Vector((co.x * 0.78 * k, co.y * 0.78 * k, z * 1.0))
    deform(ob, shape)
    smooth(ob)
    mat = material("Shell", [(0.0, (0.90, 0.72, 0.54)), (0.5, (0.98, 0.84, 0.68)), (1.0, (1.0, 0.92, 0.80))],
                   coord="z", lo=-1, hi=1, rough=0.32, sss=0.4, sss_radius=(1, 0.8, 0.6), coat=0.45,
                   bump=0.03, bump_scale=40, vary=0.06)
    add_speckles(mat, (0.78, 0.56, 0.38), scale=30, threshold=0.66, strength=0.55)
    assign(ob, mat)
    return rotate_all([ob], (math.radians(10), math.radians(-14), 0))


def milk():
    white = material("Carton", [(0.0, (0.90, 0.92, 0.96)), (0.5, (1.0, 1.0, 1.0)), (1.0, (0.96, 0.97, 1.0))],
                     coord="z", lo=0.0, hi=1.3, rough=0.3, coat=0.4, sss=0.1)
    blue = material("Blue", [(0.0, (0.16, 0.42, 0.92)), (1.0, (0.36, 0.62, 1.0))], coord="z", lo=0.4, hi=1.75,
                    rough=0.3, coat=0.4)
    body = box_mesh("Carton", 0.9, 0.9, 1.3, 0.0, cuts=8)
    bevel(body, 0.05, 4, 30)
    smooth(body, 40)
    # синяя полоса по середине
    assign_faces(body, white, [(lambda n, c: 0.48 < c.z < 0.9 and abs(n.z) < 0.5, blue)])
    roof = profile_prism("Roof", [(-0.45, 0.0), (0.45, 0.0), (0.0, 0.36)], 0.9, -0.45)
    roof.rotation_euler = (math.radians(90), 0, math.radians(90))
    roof.location = (0, 0, 1.3)
    apply_transform(roof)
    bevel(roof, 0.04, 3, 30)
    smooth(roof, 40)
    assign(roof, blue)
    fin = box_mesh("Fin", 0.9, 0.07, 0.14, 1.62)
    bevel(fin, 0.025, 3, 30)
    smooth(fin, 40)
    assign(fin, white)
    drop = sphere("MilkDrop", 0.14, 32, 20)

    def drop_shape(co):
        t = max(0.0, co.z / 0.14)
        k = 1.0 - 0.75 * t ** 1.3
        return Vector((co.x * k, co.y * 0.3, co.z * 1.25 + 0.6 * t * 0.0))
    deform(drop, drop_shape)
    drop.location = (0.0, -0.47, 0.70)
    smooth(drop)
    assign(drop, flat("DropMat", (1.0, 1.0, 1.0), rough=0.2, coat=0.6))
    return rotate_all([body, roof, fin, drop], (0, 0, math.radians(-28)))


def honey():
    pot_mat = material("Pot", [(0.0, (0.70, 0.32, 0.12)), (0.5, (0.88, 0.48, 0.18)), (1.0, (0.96, 0.62, 0.28))],
                       coord="z", lo=0.0, hi=1.2, rough=0.3, sss=0.15, coat=0.5)
    pot = lathe("Pot", [(0.0, 0.0), (0.42, 0.0), (0.56, 0.08), (0.66, 0.35), (0.67, 0.6), (0.6, 0.88), (0.5, 1.0),
                        (0.5, 1.06), (0.57, 1.1), (0.56, 1.16), (0.47, 1.16), (0.44, 1.1), (0.0, 1.1)], 72)
    subdivide(pot, 1)
    smooth(pot)
    assign(pot, pot_mat)
    # овальная этикетка с сотой спереди
    label = sphere("PotLabel", 1.0, 48, 24)
    label.scale = (0.34, 0.07, 0.22)
    label.location = (0.0, -0.645, 0.5)
    apply_transform(label)
    smooth(label)
    assign(label, material("PotLabelMat", [(0.0, (1.0, 0.92, 0.70)), (1.0, (1.0, 0.98, 0.88))], coord="z", lo=0.3,
                           hi=0.7, rough=0.35, coat=0.4))
    hexa = profile_prism("Hex", [(0.15 * math.cos(math.radians(60 * i + 30)), 0.15 * math.sin(math.radians(60 * i + 30)))
                                 for i in range(6)], 0.04, 0.0)
    bevel(hexa, 0.015, 2, 30)
    hexa.rotation_euler = (math.radians(90), 0, 0)
    hexa.location = (0.0, -0.70, 0.5)
    apply_transform(hexa)
    smooth(hexa, 40)
    gold = material("Honey", [(0.0, (0.95, 0.52, 0.04)), (0.6, (1.0, 0.70, 0.10)), (1.0, (1.0, 0.82, 0.30))],
                    coord="z", lo=0.6, hi=1.3, rough=0.08, sss=0.6, sss_radius=(1, 0.6, 0.1), coat=0.9,
                    coat_rough=0.03)
    top = sphere("HoneyTop", 0.55, 48, 24)
    deform(top, lambda co: Vector((co.x, co.y, max(co.z, -0.05) * 0.35 + 1.12)))
    smooth(top)
    assign(top, gold)
    assign(hexa, gold)
    parts = [pot, label, hexa, top]
    for i, (a, ln) in enumerate(((-58, 0.36), (-128, 0.24), (-20, 0.18))):
        th = math.radians(a)
        pts = []
        for k in range(14):
            t = k / 13
            z = 1.14 - ln * t
            rr = 0.565 + 0.02 * math.sin(t * 3) + 0.08 * max(0.0, (1.06 - z) / 0.2) if z < 1.06 else 0.58
            rr = 0.58 if z > 1.04 else min(0.69, 0.5 + 0.17 * (1.06 - z) / 0.4 + 0.06)
            pts.append((rr * math.cos(th), rr * math.sin(th), z))
        d = tube(f"Drip{i}", pts, 0.055, taper=(0.9, 1.25))
        smooth(d)
        assign(d, gold)
        parts.append(d)
        tip = sphere(f"DripTip{i}", 0.07, 24, 16)
        tip.location = pts[-1]
        smooth(tip)
        assign(tip, gold)
        parts.append(tip)
    wood = material("Dipper", [(0.0, (0.62, 0.36, 0.16)), (1.0, (0.82, 0.55, 0.28))], coord="z", lo=0.8, hi=2.0,
                    rough=0.45, coat=0.3)
    stick = capsule("Stick", 1.3, 0.065, 24, 16)
    stick.rotation_euler = (0, math.radians(-62), math.radians(25))
    stick.location = (0.18, 0.1, 1.45)
    smooth(stick)
    assign(stick, wood)
    parts.append(stick)
    return parts


def fries():
    red = material("FriesBox", [(0.0, (0.78, 0.06, 0.06)), (1.0, (0.96, 0.18, 0.12))], coord="z", lo=0.0, hi=1.0,
                   rough=0.3, coat=0.5)
    inner = flat("FriesInner", (0.45, 0.04, 0.04), rough=0.6)
    box = box_mesh("FriesBox", 1.0, 0.56, 1.0, 0.0, cuts=6)

    def taper(co):
        t = co.z / 1.0
        k = 0.72 + 0.28 * t
        # передняя и задняя стенки выше по краям, ниже в середине
        dip = 0.16 * math.cos(math.pi * co.x / 1.0) * t ** 4
        return Vector((co.x * k, co.y * (0.85 + 0.15 * t), co.z - dip))
    deform(box, taper)
    bevel(box, 0.03, 3, 30)
    smooth(box, 40)
    assign_faces(box, red, [(lambda n, c: n.z > 0.6 and c.z > 0.6, inner)])
    emblem = sphere("Emblem", 0.2, 32, 20)
    emblem.scale = (1.0, 0.2, 1.0)
    emblem.location = (0, -0.47, 0.42)
    apply_transform(emblem)
    smooth(emblem)
    assign(emblem, flat("EmblemMat", (1.0, 0.82, 0.18), rough=0.3, coat=0.5))
    fry = material("Fry", [(0.0, (1.0, 0.78, 0.22)), (0.75, (1.0, 0.85, 0.32)), (1.0, (0.92, 0.62, 0.16))],
                   coord="z", lo=0.6, hi=1.65, rough=0.35, sss=0.35, sss_radius=(1, 0.8, 0.2), coat=0.3)
    rnd = random.Random(4)
    parts = [box, emblem]
    k = 0
    for row, y in enumerate((0.12, -0.05, -0.18)):
        n = 6 if row != 1 else 7
        for i in range(n):
            x = -0.36 + 0.72 * i / (n - 1) + rnd.uniform(-0.03, 0.03)
            h = rnd.uniform(0.55, 0.85) - 0.08 * row
            f = box_mesh(f"Fry{k}", 0.13, 0.13, h, 0.0)
            bevel(f, 0.035, 3, 30)
            smooth(f, 40)
            assign(f, fry)
            f.rotation_euler = (math.radians(rnd.uniform(-8, 8)), math.radians(x * 28 + rnd.uniform(-6, 6)),
                                math.radians(rnd.uniform(-20, 20)))
            f.location = (x, y, 0.62)
            parts.append(f)
            k += 1
    return parts


# MARK: - Газировка, пончик, капкейк, печенье, мороженое

def smoothstep(e0, e1, x):
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def soda():
    cup_mat = material("Cup", [(0.0, (0.86, 0.10, 0.10)), (0.30, (0.95, 0.18, 0.15)), (0.31, (1.0, 1.0, 1.0)),
                               (0.47, (1.0, 1.0, 1.0)), (0.48, (0.95, 0.18, 0.15)), (1.0, (1.0, 0.30, 0.24))],
                       coord="z", lo=0.0, hi=1.3, rough=0.3, coat=0.5)
    cup = lathe("Cup", [(0.0, 0.0), (0.38, 0.0), (0.42, 0.04), (0.56, 1.3), (0.0, 1.3)], 72)
    subdivide(cup, 1)
    smooth(cup, 50)
    assign(cup, cup_mat)
    lid_mat = material("Lid", [(0.0, (0.90, 0.92, 0.96)), (1.0, (1.0, 1.0, 1.0))], coord="z", lo=1.28, hi=1.5,
                       rough=0.25, coat=0.5)
    lid = lathe("Lid", [(0.0, 1.27), (0.6, 1.27), (0.62, 1.31), (0.6, 1.36), (0.5, 1.38), (0.46, 1.46), (0.0, 1.48)], 72)
    subdivide(lid, 1)
    smooth(lid, 50)
    assign(lid, lid_mat)
    straw_mat = material("Straw", [(0.0, (1.0, 0.85, 0.2)), (1.0, (1.0, 0.75, 0.1))], coord="z", lo=1.3, hi=2.2,
                         rough=0.25, coat=0.6)
    pts = [(0.05 + 0.18 * t, 0.0, 1.3 + 0.75 * t) for t in [i / 10 for i in range(11)]]
    pts += [(0.23 + 0.2 * t, 0.0, 2.05 + 0.08 * math.sin(t * math.pi / 2)) for t in [i / 6 for i in range(1, 7)]]
    straw = tube("Straw", pts, 0.06)
    smooth(straw)
    assign(straw, straw_mat)
    return rotate_all([cup, lid, straw], (0, 0, math.radians(-30)))


def donut():
    major, minor = 0.62, 0.34
    dough = torus("Dough", major, minor, 96, 40)
    deform(dough, lambda co: Vector((co.x, co.y, co.z * 0.85)))
    smooth(dough)
    assign(dough, material("Dough", [(0.0, (0.80, 0.46, 0.18)), (0.5, (0.96, 0.66, 0.30)), (1.0, (1.0, 0.82, 0.5))],
                           coord="nz", lo=-1, hi=1, rough=0.45, sss=0.3, coat=0.2, bump=0.05, bump_scale=20))
    segs, ring = 128, 48
    verts, faces = [], []
    for i in range(segs):
        a = 2 * math.pi * i / segs
        thr = -0.05 + 0.16 * math.sin(6 * a) * 0.5 + 0.1 * math.sin(11 * a + 1.3)
        for j in range(ring):
            b = 2 * math.pi * j / ring
            sz = math.sin(b)
            g = smoothstep(thr - 0.12, thr + 0.05, sz)
            r = minor * (0.92 + 0.13 * g)
            x = (major + r * math.cos(b)) * math.cos(a)
            y = (major + r * math.cos(b)) * math.sin(a)
            verts.append((x, y, r * sz * 0.85 + 0.01 * g))
    for i in range(segs):
        for j in range(ring):
            a_, b_ = i * ring + j, ((i + 1) % segs) * ring + j
            c_, d_ = ((i + 1) % segs) * ring + (j + 1) % ring, i * ring + (j + 1) % ring
            faces.append((a_, b_, c_, d_))
    glaze = from_data("Glaze", verts, faces)
    smooth(glaze)
    assign(glaze, material("Glaze", [(0.0, (1.0, 0.45, 0.68)), (1.0, (1.0, 0.62, 0.80))], coord="z", lo=0.0, hi=0.32,
                           rough=0.12, sss=0.3, coat=0.8, coat_rough=0.04))
    colors = [(1.0, 1.0, 1.0), (0.3, 0.75, 1.0), (1.0, 0.85, 0.2), (0.45, 0.85, 0.4), (0.62, 0.4, 0.95)]
    mats = [flat(f"Spr{i}", c, rough=0.25, coat=0.5) for i, c in enumerate(colors)]

    def make(i, rnd):
        sp = capsule(f"Sprinkle{i}", 0.13, 0.025, 12, 8)
        sp.scale = (1, 1, 1)
        assign(smooth(sp), mats[rnd.randrange(len(mats))])
        return sp
    scatter_on(glaze, 34, make, seed=5, area=0.98, zmin=0.15, spacing=0.13)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def cupcake():
    wrap = lathe("Wrapper", [(0.0, 0.0), (0.4, 0.0), (0.42, 0.02), (0.56, 0.62), (0.0, 0.62)], 96)
    deform(wrap, lambda co: Vector((co.x, co.y, co.z)) * 1.0)

    def pleat(co):
        a = math.atan2(co.y, co.x)
        r = math.hypot(co.x, co.y)
        k = 1.0 + 0.045 * math.cos(24 * a) * (1 if r > 0.05 else 0)
        return Vector((co.x * k, co.y * k, co.z))
    deform(wrap, pleat)
    smooth(wrap, 60)
    assign(wrap, material("Wrapper", [(0.0, (0.30, 0.66, 0.96)), (1.0, (0.52, 0.82, 1.0))], coord="z", lo=0.0, hi=0.62,
                          rough=0.3, coat=0.4))
    cake = sphere("Cake", 0.57, 64, 32)
    deform(cake, lambda co: Vector((co.x, co.y, max(co.z, 0.0) * 0.45 + 0.58)))
    smooth(cake)
    assign(cake, material("CakeMat", [(0.0, (0.62, 0.34, 0.16)), (1.0, (0.78, 0.48, 0.24))], coord="z", lo=0.55,
                          hi=0.85, rough=0.5, bump=0.1, bump_scale=16))
    pts = []
    turns = 2.6
    for k in range(160):
        t = k / 159
        a = 2 * math.pi * turns * t
        r = 0.46 * (1 - t) ** 0.9 + 0.02
        pts.append((r * math.cos(a), r * math.sin(a), 0.74 + 0.62 * t ** 0.9))
    frost = tube("Frosting", pts, 0.17, taper=(1.0, 0.45))
    subdivide(frost, 1)
    smooth(frost)
    assign(frost, material("Frost", [(0.0, (1.0, 0.62, 0.78)), (1.0, (1.0, 0.82, 0.90))], coord="z", lo=0.7, hi=1.4,
                           rough=0.25, sss=0.3, coat=0.4))
    cherry = sphere("Cherry", 0.14, 48, 32)
    cherry.location = (0.0, 0.0, 1.44)
    smooth(cherry)
    assign(cherry, material("CherryMat", [(0.0, (0.72, 0.02, 0.06)), (1.0, (0.95, 0.10, 0.12))], coord="z", lo=1.3,
                            hi=1.58, rough=0.08, sss=0.3, coat=0.9))
    stem = tube("CherryStem", [(0.0, 0.0, 1.55), (0.03, 0.0, 1.66), (0.09, 0.0, 1.74)], 0.018)
    smooth(stem)
    assign(stem, flat("CherryStemMat", (0.36, 0.6, 0.2), rough=0.4))
    return [wrap, cake, frost, cherry, stem]


def cookie():
    ob = rounded_disc("Cookie", 1.0, 0.24, 2.6, 30)

    def shape(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.04 * math.sin(5 * a + 0.5) + 0.025 * math.sin(11 * a)
        return Vector((co.x * k, co.y * k, co.z))
    deform(ob, shape)
    push_normals(ob, lambda co, n: 0.03 * fbm(co * 2.4, 4))
    smooth(ob)
    assign(ob, material("CookieMat", [(0.0, (0.66, 0.36, 0.12)), (0.5, (0.82, 0.52, 0.22)), (1.0, (0.92, 0.66, 0.34))],
                        coord="nz", lo=-1, hi=1, rough=0.55, sss=0.15, coat=0.15, bump=0.25, bump_scale=10,
                        bump_detail=8, vary=0.25, vary_scale=5))
    choc = material("Chip", [(0.0, (0.22, 0.10, 0.05)), (1.0, (0.40, 0.20, 0.10))], coord="z", lo=-0.05, hi=0.08,
                    rough=0.25, coat=0.5)

    def make(i, rnd):
        c = sphere(f"Chip{i}", 1.0, 20, 12)
        c.scale = (rnd.uniform(0.09, 0.13), rnd.uniform(0.08, 0.11), 0.07)
        assign(smooth(c), choc)
        return c
    scatter_on(ob, 11, make, seed=9, area=0.82, spacing=0.3)
    parts = [o for o in bpy.data.objects if o.type == "MESH"]
    return rotate_all(parts, (math.radians(34), 0, 0))


def scoop(name, r, color_lo, color_hi, z0, seed=0):
    ob = sphere(name, r, 64, 40)

    def shape(co):
        a = math.atan2(co.y, co.x)
        u = co.z / r
        if u < -0.25:
            # волнистый подтаявший край снизу
            k = 1.0 + 0.07 * math.sin(9 * a + seed) + 0.05
            return Vector((co.x * k, co.y * k, -0.25 * r - (u + 0.25) * r * 0.25))
        return Vector((co.x, co.y, co.z * 0.92))
    deform(ob, shape)
    push_normals(ob, lambda co, n: 0.02 * fbm(co * 3 + Vector((seed, 0, 0))))
    subdivide(ob, 1)
    smooth(ob)
    ob.location = (0, 0, z0)
    assign(ob, material(f"{name}Mat", [(0.0, color_lo), (1.0, color_hi)], coord="z", lo=-r, hi=r, rough=0.35,
                        sss=0.4, sss_radius=(1, 0.7, 0.6), coat=0.3, bump=0.06, bump_scale=14))
    return ob


def icecream():
    cone = lathe("Cone", [(0.0, 0.0), (0.06, 0.05), (0.44, 1.12), (0.48, 1.16), (0.0, 1.16)], 72)
    subdivide(cone, 2)

    def waffle(co, n):
        a = math.atan2(co.y, co.x)
        u = a * 0.45 * 6
        v = co.z * 6
        g = max(0.0, math.cos(math.pi * (u + v)) ** 24) + max(0.0, math.cos(math.pi * (u - v)) ** 24)
        return -0.015 * min(1.0, g) if co.z < 1.1 else 0.0
    push_normals(cone, waffle)
    smooth(cone)
    assign(cone, material("ConeMat", [(0.0, (0.80, 0.50, 0.20)), (1.0, (0.96, 0.72, 0.38))], coord="z", lo=0.0,
                          hi=1.16, rough=0.45, sss=0.15, coat=0.2, bump=0.05, bump_scale=20))
    s1 = scoop("Scoop1", 0.5, (0.95, 0.42, 0.55), (1.0, 0.68, 0.76), 1.28, 0)
    s2 = scoop("Scoop2", 0.43, (0.46, 0.24, 0.12), (0.66, 0.40, 0.24), 1.86, 2)
    cherry = sphere("ICherry", 0.12, 48, 32)
    cherry.location = (0.02, 0.0, 2.3)
    smooth(cherry)
    assign(cherry, material("ICherryMat", [(0.0, (0.72, 0.02, 0.06)), (1.0, (0.95, 0.10, 0.12))], coord="z", lo=-0.12,
                            hi=0.12, rough=0.08, sss=0.3, coat=0.9))
    return rotate_all([cone, s1, s2, cherry], (math.radians(-8), 0, 0))


# MARK: - Кукуруза, маффин, корн-дог, вафля, пирог

def corn():
    cob = sphere("Cob", 1.0, 96, 64)
    rows = 16

    def shape(co):
        k = math.sqrt(max(0.0, 1 - co.z * co.z)) ** 0.6 if abs(co.z) < 1 else 0
        return Vector((co.x / max(1e-4, math.hypot(co.x, co.y)) * 0.36 * k if math.hypot(co.x, co.y) > 1e-6 else 0,
                       co.y / max(1e-4, math.hypot(co.x, co.y)) * 0.36 * k if math.hypot(co.x, co.y) > 1e-6 else 0,
                       co.z * 0.8))
    deform(cob, shape)
    subdivide(cob, 1)

    def kernels(co, n):
        a = math.atan2(co.y, co.x)
        u = a / (2 * math.pi) * rows
        v = co.z * 11 + 0.5 * (math.floor(u) % 2)
        f = abs(math.sin(math.pi * u)) * abs(math.sin(math.pi * v))
        return 0.035 * f ** 0.6 * min(1.0, (0.8 - abs(co.z)) * 6)
    push_normals(cob, kernels)
    smooth(cob)
    assign(cob, material("Kernels", [(0.0, (1.0, 0.70, 0.08)), (0.5, (1.0, 0.82, 0.18)), (1.0, (1.0, 0.90, 0.40))],
                         coord="z", lo=-0.8, hi=0.8, rough=0.2, sss=0.4, sss_radius=(1, 0.8, 0.2), coat=0.6,
                         coat_rough=0.06))
    husk = material("Husk", [(0.0, (0.20, 0.55, 0.14)), (0.6, (0.42, 0.76, 0.24)), (1.0, (0.66, 0.88, 0.40))],
                    coord="z", lo=-0.85, hi=0.4, rough=0.35, sss=0.3, coat=0.3)
    parts = [cob]
    for i, a in enumerate((0, 125, 235)):
        leaf = sphere(f"Husk{i}", 1.0, 48, 32)

        def lshape(co):
            # вытянутый вогнутый лист, низ у основания початка
            t = (co.z + 1) / 2
            w = 0.30 * math.sin(math.pi * min(1.0, t * 1.05)) ** 0.7 + 0.04
            return Vector((co.x * w, co.y * 0.07 + 0.25 * (co.x * w) ** 2 * 0, co.z * 0.75 - 0.3))
        deform(leaf, lshape)
        smooth(leaf)
        assign(leaf, husk)
        leaf.location = (0, -0.3, -0.12)
        leaf.rotation_euler = (math.radians(-14), 0, 0)
        rotate_all([leaf], (0, 0, math.radians(a)))
        parts.append(leaf)
    return rotate_all(parts, (math.radians(-12), math.radians(24), 0))


def muffin():
    wrap = lathe("MWrap", [(0.0, 0.0), (0.42, 0.0), (0.44, 0.02), (0.56, 0.55), (0.0, 0.55)], 96)

    def pleat(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.04 * math.cos(28 * a) * (1 if math.hypot(co.x, co.y) > 0.05 else 0)
        return Vector((co.x * k, co.y * k, co.z))
    deform(wrap, pleat)
    smooth(wrap, 60)
    assign(wrap, material("MWrapMat", [(0.0, (0.94, 0.64, 0.30)), (1.0, (1.0, 0.80, 0.50))], coord="z", lo=0.0,
                          hi=0.55, rough=0.4, coat=0.3))
    top = sphere("MTop", 1.0, 72, 48)

    def cap(co):
        if co.z < 0:
            return Vector((co.x * 0.62, co.y * 0.62, 0.5 + co.z * 0.05))
        r = 0.72
        return Vector((co.x * r, co.y * r, 0.5 + co.z * 0.55))
    deform(top, cap)
    push_normals(top, lambda co, n: 0.028 * fbm(co * 2.6, 3))
    subdivide(top, 1)
    smooth(top)
    mtop = material("MTopMat", [(0.0, (0.86, 0.56, 0.24)), (0.45, (0.92, 0.62, 0.28)), (1.0, (0.70, 0.38, 0.14))],
                    coord="z", lo=0.45, hi=1.06, rough=0.42, sss=0.25, coat=0.3, bump=0.25, bump_scale=10,
                    bump_detail=6, vary=0.18, vary_scale=4)
    add_speckles(mtop, (1.0, 0.95, 0.85), scale=60, threshold=0.68, strength=0.8)
    assign(top, mtop)
    berry = material("Berry", [(0.0, (0.16, 0.12, 0.42)), (1.0, (0.36, 0.30, 0.72))], coord="z", lo=-0.08, hi=0.08,
                     rough=0.2, sss=0.2, coat=0.6)

    def make(i, rnd):
        b = sphere(f"Berry{i}", 0.085, 24, 16)
        b.scale = (1, 1, 0.8)
        assign(smooth(b), berry)
        return b
    scatter_on(top, 9, make, seed=2, area=0.65, spacing=0.22)
    return [o for o in bpy.data.objects if o.type == "MESH"]


def corndog():
    batter = capsule("Batter", 1.7, 0.34, 64, 48)
    push_normals(batter, lambda co, n: 0.03 * fbm(co * 3.0, 4))
    smooth(batter)
    assign(batter, material("BatterMat", [(0.0, (0.80, 0.46, 0.14)), (0.5, (0.94, 0.64, 0.24)), (1.0, (1.0, 0.78, 0.38))],
                            coord="nz", lo=-1, hi=1, rough=0.45, sss=0.2, coat=0.35, bump=0.15, bump_scale=14,
                            vary=0.12))
    stick = capsule("CStick", 1.0, 0.055, 24, 16)
    stick.location = (-1.15, 0, 0)
    smooth(stick)
    assign(stick, material("CStickMat", [(0.0, (0.86, 0.68, 0.44)), (1.0, (0.96, 0.84, 0.62))], coord="nz", lo=-1,
                           hi=1, rough=0.5))
    pts = []
    for k in range(60):
        t = k / 59
        x = -0.62 + 1.24 * t
        y = -0.33 * math.cos(0.0)
        zz = 0.12 * math.sin(t * math.pi * 7)
        pts.append((x, -0.31 + 0.02 * abs(zz), 0.1 + zz))
    mustard = tube("Mustard", pts, 0.045)
    smooth(mustard)
    assign(mustard, material("MustardMat", [(0.0, (1.0, 0.78, 0.05)), (1.0, (1.0, 0.88, 0.25))], coord="z", lo=-0.1,
                             hi=0.3, rough=0.15, sss=0.3, coat=0.7))
    return rotate_all([batter, stick, mustard], (0, math.radians(-40), math.radians(-10)))


def waffle():
    size, cells = 1.7, 4
    slab = box_mesh("Waffle", size, size, 0.3, 0.0, cuts=56)
    bevel(slab, 0.08, 4, 30)

    def pits(co, n):
        if n.z < 0.7 or co.z < 0.2:
            return 0.0
        fx = (co.x / size + 0.5) * cells
        fy = (co.y / size + 0.5) * cells
        ux, uy = fx - math.floor(fx), fy - math.floor(fy)
        px = smoothstep(0.12, 0.24, ux) * smoothstep(0.12, 0.24, 1 - ux)
        py = smoothstep(0.12, 0.24, uy) * smoothstep(0.12, 0.24, 1 - uy)
        edge = smoothstep(0.0, 0.06, size / 2 - max(abs(co.x), abs(co.y)))
        return -0.12 * px * py * edge
    push_normals(slab, pits)
    subdivide(slab, 1)
    smooth(slab)
    assign(slab, material("WaffleMat", [(0.0, (0.80, 0.46, 0.14)), (0.6, (1.0, 0.80, 0.40)), (0.86, (0.92, 0.60, 0.22)),
                                        (1.0, (0.74, 0.40, 0.12))],
                          coord="z", lo=0.0, hi=0.31, rough=0.38, sss=0.25, coat=0.35, vary=0.08, bump=0.08,
                          bump_scale=16))
    butter = box_mesh("Butter", 0.42, 0.36, 0.16, 0.27)
    bevel(butter, 0.06, 4, 30)
    subdivide(butter, 1)
    smooth(butter)
    assign(butter, material("ButterMat", [(0.0, (1.0, 0.88, 0.45)), (1.0, (1.0, 0.95, 0.70))], coord="z", lo=0.27,
                            hi=0.43, rough=0.2, sss=0.4, coat=0.5))
    butter.rotation_euler = (0, 0, math.radians(20))
    return rotate_all([slab, butter], (math.radians(36), 0, math.radians(8)))


def pie():
    crust = material("PieCrust", [(0.0, (0.78, 0.44, 0.14)), (0.5, (0.94, 0.64, 0.26)), (1.0, (1.0, 0.78, 0.40))],
                     coord="z", lo=0.0, hi=0.45, rough=0.45, sss=0.2, coat=0.3, bump=0.06, bump_scale=18, vary=0.12)
    dish = lathe("Dish", [(0.0, 0.0), (0.7, 0.0), (0.82, 0.06), (0.98, 0.32), (0.98, 0.34), (0.0, 0.34)], 96)
    smooth(dish, 50)
    assign(dish, crust)
    filling = sphere("Filling", 0.9, 72, 36)
    deform(filling, lambda co: Vector((co.x, co.y, max(co.z, 0.0) * 0.12 + 0.3)))
    smooth(filling)
    assign(filling, material("Cherry", [(0.0, (0.62, 0.04, 0.08)), (1.0, (0.88, 0.12, 0.16))], coord="z", lo=0.3,
                             hi=0.42, rough=0.1, sss=0.4, coat=0.8, bump=0.1, bump_scale=8))
    rim = torus("Rim", 0.92, 0.1, 128, 24)

    def crimp(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.035 * math.sin(28 * a)
        return Vector((co.x * k, co.y * k, co.z * (1.0 + 0.3 * math.sin(28 * a)) + 0.36))
    deform(rim, crimp)
    smooth(rim)
    assign(rim, crust)
    parts = [dish, filling, rim]
    for d in (0, 1):
        for i, off in enumerate((-0.5, -0.17, 0.17, 0.5)):
            half = math.sqrt(max(0.0, 0.88 ** 2 - off ** 2))
            st = box_mesh(f"Strip{d}{i}", 2 * half, 0.16, 0.06, 0.0, cuts=12)
            deform(st, lambda co: Vector((co.x, co.y, co.z + 0.39 + 0.03 * math.cos(co.x * 1.6) + (0.02 if d else 0))))
            bevel(st, 0.025, 3, 30)
            smooth(st, 40)
            assign(st, crust)
            if d == 0:
                st.location = (0, off, 0)
            else:
                st.rotation_euler = (0, 0, math.radians(90))
                st.location = (off, 0, 0)
            parts.append(st)
    return rotate_all(parts, (math.radians(30), 0, 0))


# MARK: - Блюда

def dish_hotdog():
    halves = hotdog_bun_halves("DBun", 2.5, 0.44, 0.06, 14)
    sg = sausage_obj("DSausage", 2.75, 0.25, 0)
    sg.location = (0, 0, 0.30)
    pts = []
    for k in range(80):
        t = k / 79
        x = -1.0 + 2.0 * t
        pts.append((x, 0.12 * math.sin(t * math.pi * 9), 0.555 - 0.04 * abs(math.sin(t * math.pi * 9))))
    ket = tube("DKetchup", pts, 0.055)
    smooth(ket)
    assign(ket, material("DKetchupMat", [(0.0, (0.80, 0.06, 0.04)), (1.0, (0.96, 0.16, 0.08))], coord="z", lo=0.4,
                         hi=0.65, rough=0.1, sss=0.3, coat=0.8))
    return rotate_all(halves + [sg, ket], (0, 0, math.radians(-22)))


def tri_layer(name, legs, thick, z0, grow=0.0, wave=0.0, waves=0):
    c = legs / 3
    pts = []
    corners = [(0.0, 0.0), (legs, 0.0), (0.0, legs)]
    for i in range(3):
        (x0, y0), (x1, y1) = corners[i], corners[(i + 1) % 3]
        for k in range(24):
            t = k / 24
            pts.append((x0 + (x1 - x0) * t, y0 + (y1 - y0) * t))
    pts = [((x - c) * (1 + grow) + c, (y - c) * (1 + grow) + c) for x, y in pts]
    ob = profile_prism(name, pts, thick, z0)
    if wave:
        ob.data.update()
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-4],
                                  cuts=2)
        bm.to_mesh(ob.data)
        bm.free()

        def fn(co):
            a = math.atan2(co.y - c, co.x - c)
            return Vector((co.x, co.y, co.z + wave * math.sin(waves * a)))
        deform(ob, fn)
    return ob


def dish_sandwich():
    legs = 1.9
    crust = material("SCrust", [(0.0, (0.80, 0.45, 0.14)), (1.0, (0.93, 0.62, 0.25))], coord="z", lo=0.0, hi=0.9,
                     rough=0.5, sss=0.2, coat=0.2, bump=0.08, bump_scale=16)
    crumb = material("SCrumb", [(0.0, (1.0, 0.84, 0.56)), (1.0, (1.0, 0.90, 0.68))], coord="z", lo=0.0, hi=0.9,
                     rough=0.65, sss=0.25, bump=0.35, bump_scale=28, bump_detail=8)
    toast = material("SToast", [(0.0, (0.98, 0.78, 0.44)), (1.0, (0.96, 0.70, 0.36))], coord="r", lo=0.0, hi=1.6,
                     rough=0.55, sss=0.2, coat=0.15, bump=0.3, bump_scale=24, bump_detail=8, vary=0.15, vary_scale=4)
    add_speckles(toast, (0.84, 0.54, 0.24), scale=40, threshold=0.63, strength=0.6)
    hyp = Vector((1, 1, 0)).normalized()

    def bread_layer(name, z0):
        b = tri_layer(name, legs, 0.30, z0)
        bevel(b, 0.06, 4, 30)
        smooth(b, 40)
        # верх подрумянен, срез - мякиш, края - корочка
        assign_faces(b, crust, [(lambda n, c: n.z > 0.9 and c.z > 0.7, toast),
                                (lambda n, c: abs(n.z) > 0.9 or n.dot(hyp) > 0.9, crumb)])
        return b
    b1 = bread_layer("SBread1", 0.0)
    let = tri_layer("SLettuce", legs, 0.06, 0.30, grow=0.08, wave=0.045, waves=18)
    subdivide(let, 1)
    smooth(let)
    assign(let, material("SLetMat", [(0.0, (0.30, 0.70, 0.18)), (1.0, (0.55, 0.86, 0.28))], coord="z", lo=0.2, hi=0.35,
                         rough=0.3, sss=0.35, coat=0.35))
    hm = tri_layer("SHam", legs, 0.16, 0.36, grow=0.05, wave=0.025, waves=11)
    bevel(hm, 0.03, 3, 30)
    smooth(hm, 40)
    assign(hm, material("SHamMat", [(0.0, (0.96, 0.52, 0.56)), (1.0, (1.0, 0.70, 0.72))], coord="z", lo=0.3, hi=0.45,
                        rough=0.35, sss=0.4, coat=0.3))
    b2 = bread_layer("SBread2", 0.53)
    parts = [b1, let, hm, b2]
    c = legs / 3
    # шпажка с оливкой
    pick = capsule("Pick", 1.15, 0.022, 16, 12)
    pick.rotation_euler = (0, math.radians(90), 0)
    pick.location = (c, c, 0.78)
    apply_transform(pick)
    smooth(pick)
    assign(pick, flat("PickMat", (0.92, 0.80, 0.58), rough=0.5))
    olive = sphere("Olive", 0.11, 32, 20)
    olive.scale = (1, 1, 1.15)
    olive.location = (c, c, 1.3)
    apply_transform(olive)
    smooth(olive)
    assign(olive, material("OliveMat", [(0.0, (0.30, 0.42, 0.10)), (1.0, (0.50, 0.62, 0.18))], coord="z", lo=1.2,
                           hi=1.42, rough=0.15, sss=0.2, coat=0.7))
    pim = sphere("Pimento", 0.045, 20, 12)
    pim.scale = (1, 0.5, 1)
    pim.location = (c - 0.08, c - 0.08, 1.33)
    apply_transform(pim)
    smooth(pim)
    assign(pim, flat("PimentoMat", (0.90, 0.16, 0.10), rough=0.2, coat=0.6))
    parts += [pick, olive, pim]
    rotate_all(parts, (0, 0, math.radians(-135)), pivot=(c, c, 0.42))
    return rotate_all(parts, (math.radians(16), 0, 0), pivot=(c, c, 0.42))


def dish_sub():
    crust = material("SubCrust", [(0.0, (0.80, 0.46, 0.14)), (0.45, (0.93, 0.62, 0.24)), (1.0, (0.76, 0.42, 0.12))],
                     coord="nz", lo=-1, hi=1, rough=0.45, sss=0.2, coat=0.3, bump=0.1, bump_scale=14, vary=0.12)
    crumb = flat("SubCrumb", CRUMB, rough=0.6, sss=0.2, bump=0.3, bump_scale=30, bump_detail=6)
    parts = []
    for name, keep_up, dz in (("SubBottom", False, 0.0), ("SubTop", True, 0.34)):
        h = capsule(name, 2.7, 0.38, 64, 48, pinch=0.1)
        deform(h, lambda co: Vector((co.x, co.y, co.z * 0.9)))
        bisect(h, (0, 0, 0), (0, 0, -1) if keep_up else (0, 0, 1))
        subdivide(h, 1)
        smooth(h, 50)
        assign_faces(h, crust, [(lambda n, c, up=keep_up: (n.z < -0.9) if up else (n.z > 0.9), crumb)])
        h.location = (0, 0, dz)
        parts.append(h)
    let = polar_disc("SubLettuce", 16, 160, 1.3, 0.46)

    def ruffle(co):
        a = math.atan2(co.y / 0.46, co.x / 1.3)
        r = math.hypot(co.x / 1.3, co.y / 0.46)
        return Vector((co.x, co.y, 0.03 + 0.05 * math.sin(20 * a) * max(0.0, r - 0.7) / 0.3))
    deform(let, ruffle)
    solidify(let, 0.04)
    subdivide(let, 1)
    smooth(let)
    assign(let, material("SubLetMat", [(0.0, (0.55, 0.86, 0.28)), (1.0, (0.22, 0.62, 0.14))], coord="r", lo=0.0,
                         hi=1.3, rough=0.3, sss=0.35, coat=0.35))
    parts.append(let)
    ham_mat = material("SubHamMat", [(0.0, (0.94, 0.48, 0.54)), (1.0, (1.0, 0.68, 0.72))], coord="z", lo=0.05,
                       hi=0.3, rough=0.35, sss=0.4, coat=0.3)
    for i, x in enumerate((-0.85, -0.28, 0.28, 0.85)):
        hm = polar_disc(f"SubHam{i}", 12, 96, 0.34, 0.34)
        deform(hm, lambda co, i=i: Vector((co.x, co.y, 0.12 * (co.x / 0.34) ** 2 * 0 + 0.06 * math.sin(3 * co.x / 0.34 + i))))
        solidify(hm, 0.05)
        subdivide(hm, 1)
        smooth(hm)
        assign(hm, ham_mat)
        hm.location = (x, -0.12, 0.12)
        hm.rotation_euler = (math.radians(-25), 0, math.radians(i * 40))
        parts.append(hm)
    tom = material("SubTomato", [(0.0, (1.0, 0.45, 0.40)), (0.55, (0.96, 0.22, 0.14)), (1.0, (0.80, 0.08, 0.06))],
                   coord="r", lo=0.0, hi=0.22, rough=0.12, sss=0.4, coat=0.7)
    for i, x in enumerate((-0.6, 0.0, 0.6)):
        t = cylinder(f"SubTom{i}", 0.22, 0.06, 48)
        bevel(t, 0.02, 3, 30)
        smooth(t, 50)
        assign(t, tom)
        t.location = (x, -0.3, 0.2)
        t.rotation_euler = (math.radians(-35), 0, 0)
        parts.append(t)
    return rotate_all(parts, (0, 0, math.radians(-18)))


def dish_pancakes():
    parts = []
    pan = material("Pancake", [(0.0, (0.80, 0.46, 0.14)), (0.25, (0.96, 0.70, 0.36)), (0.5, (1.0, 0.86, 0.58)),
                               (0.75, (0.96, 0.70, 0.36)), (1.0, (0.82, 0.48, 0.16))],
                   coord="nz", lo=-1, hi=1, rough=0.45, sss=0.25, coat=0.25, bump=0.08, bump_scale=14)
    z = 0.0
    for i in range(4):
        p = rounded_disc(f"Pancake{i}", 0.95 - 0.02 * (i % 2), 0.2, 3.0, 26)
        push_normals(p, lambda co, n, i=i: 0.015 * fbm(co * 2.5 + Vector((i, 0, 0))))
        smooth(p)
        assign(p, pan)
        p.location = (0.03 * math.sin(i * 2.1), 0.03 * math.cos(i * 1.7), z + 0.1)
        z += 0.19
        parts.append(p)
    syrup = material("Syrup", [(0.0, (0.80, 0.38, 0.04)), (1.0, (1.0, 0.66, 0.12))], coord="z", lo=0.5, hi=0.85,
                     rough=0.06, sss=0.6, sss_radius=(1, 0.5, 0.1), coat=0.9, coat_rough=0.03)
    pool = sphere("Pool", 0.78, 64, 24)

    def pool_shape(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.08 * math.sin(5 * a + 0.4)
        return Vector((co.x * k, co.y * k, max(co.z, 0.0) * 0.06 + z + 0.0))
    deform(pool, pool_shape)
    smooth(pool)
    assign(pool, syrup)
    parts.append(pool)
    for i, (a, ln) in enumerate(((-100, 0.45), (-55, 0.28), (-145, 0.32), (20, 0.2))):
        th = math.radians(a)
        rr = 0.96
        pts = [(rr * math.cos(th), rr * math.sin(th), z + 0.02 - ln * t) for t in [k / 10 for k in range(11)]]
        pts[0] = (0.86 * math.cos(th), 0.86 * math.sin(th), z + 0.03)
        d = tube(f"SyrupDrip{i}", pts, 0.06, taper=(0.9, 1.2))
        smooth(d)
        assign(d, syrup)
        tip = sphere(f"SyrupTip{i}", 0.072, 24, 16)
        tip.location = pts[-1]
        smooth(tip)
        assign(tip, syrup)
        parts += [d, tip]
    butter = box_mesh("PButter", 0.42, 0.36, 0.17, z + 0.02)
    bevel(butter, 0.06, 4, 30)
    subdivide(butter, 1)
    smooth(butter)
    assign(butter, material("PButterMat", [(0.0, (1.0, 0.88, 0.45)), (1.0, (1.0, 0.95, 0.70))], coord="z", lo=z,
                            hi=z + 0.2, rough=0.2, sss=0.4, coat=0.5))
    butter.rotation_euler = (0, 0, math.radians(25))
    parts.append(butter)
    return parts


MODELS = {
    "bun": whole_bun,
    "patty": patty,
    "lettuce": lettuce,
    "cheese": cheese_wedge,
    "tomato": tomato,
    "sausage": sausage,
    "hotdog_bun": hotdog_bun,
    "ketchup": ketchup,
    "bread": bread,
    "ham": ham,
    "baguette": baguette,
    "egg": egg,
    "milk": milk,
    "honey": honey,
    "fries": fries,
    "soda": soda,
    "donut": donut,
    "cupcake": cupcake,
    "cookie": cookie,
    "icecream": icecream,
    "corn": corn,
    "muffin": muffin,
    "corndog": corndog,
    "waffle": waffle,
    "pie": pie,
    "dish_burger": lambda: dish_burger(False),
    "dish_cheeseburger": lambda: dish_burger(True),
    "dish_hotdog": dish_hotdog,
    "dish_sandwich": dish_sandwich,
    "dish_sub": dish_sub,
    "dish_pancakes": dish_pancakes,
}


# MARK: - Рендер

def render(sprite_id, out_dir, size=360, spin_frames=0, samples=96):
    scene = reset_scene(samples)
    objs = MODELS[sprite_id]()
    bpy.context.view_layer.update()
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    lo, hi, pts = R.bounds(meshes)
    center = (lo + hi) / 2
    pivot = bpy.data.objects.new("Pivot", None)
    scene.collection.objects.link(pivot)
    pivot.location = center
    bpy.context.view_layer.update()
    for o in meshes:
        if o.parent is None:
            mw = o.matrix_world.copy()
            o.parent = pivot
            o.matrix_parent_inverse = pivot.matrix_world.inverted()
            o.matrix_world = mw
    bpy.context.view_layer.update()
    if spin_frames:
        r = max((Vector((p.x, p.y, 0)) - Vector((center.x, center.y, 0))).length for p in pts)
        ring = [Vector((center.x + r * math.cos(a), center.y + r * math.sin(a), z))
                for a in [2 * math.pi * k / 16 for k in range(16)] for z in (lo.z, hi.z)]
        R.add_camera(scene, center, ring, azimuth=AZIMUTH, elevation=ELEVATION, margin=1.05)
    else:
        R.add_camera(scene, center, pts, azimuth=AZIMUTH, elevation=ELEVATION, margin=1.08)
    scene.render.resolution_x = size
    scene.render.resolution_y = size
    if spin_frames:
        os.makedirs(os.path.join(out_dir, sprite_id + "_spin"), exist_ok=True)
        for f in range(spin_frames):
            pivot.rotation_euler = (0, 0, 2 * math.pi * f / spin_frames)
            bpy.context.view_layer.update()
            scene.render.filepath = os.path.join(out_dir, sprite_id + "_spin", f"{sprite_id}_spin_{f:02d}.png")
            bpy.ops.render.render(write_still=True)
    else:
        scene.render.filepath = os.path.join(out_dir, sprite_id + ".png")
        bpy.ops.render.render(write_still=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--spin", action="store_true")
    ap.add_argument("--size", type=int, default=0)
    ap.add_argument("--samples", type=int, default=96)
    ap.add_argument("--spin-samples", type=int, default=40)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    ids = [s for s in args.only.split(",") if s] or list(MODELS)
    for sid in ids:
        dish = sid.startswith("dish_")
        size = args.size or (512 if dish else 360)
        render(sid, args.out, size, samples=args.samples)
        if dish and args.spin:
            render(sid, args.out, 320, spin_frames=24, samples=args.spin_samples)
        print("rendered", sid, flush=True)


if __name__ == "__main__":
    main()
