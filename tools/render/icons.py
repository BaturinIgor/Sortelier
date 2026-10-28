"""Объемные иконки интерфейса: бустеры, жизни, энергия, звезды, вкладки меню.

Каждая иконка - простая игрушечная форма с глянцем, лицом к камере.
Запуск: python tools/render/icons.py <папка> [--only icon_hint,icon_heart]
Упаковка: python3 tools/render/pack.py <папка> (icon_* кладутся по центру 192x192).
"""
import math
import os
import random

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

import models as M
import coins as C

BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


# MARK: - Материалы

def shade(c, k):
    return tuple(max(0.0, min(1.0, v * k)) for v in c)


def toy(name, color, rough=0.3, coat=0.7, metal=0.0):
    """Глянцевый пластик: верх светлее, низ темнее (по нормали в мире)."""
    return C.world_mat(name, [(0.0, shade(color, 0.55)), (0.5, color), (1.0, tuple(min(1, v * 1.18 + 0.06) for v in color))],
                       rough=rough, metal=metal, coat=coat)


def gold():
    """Яркое игрушечное золото (у монет оно темнее и металличнее)."""
    return C.world_mat("IconGold", [(0.0, (0.86, 0.52, 0.06)), (0.5, (1.0, 0.76, 0.16)), (1.0, (1.0, 0.92, 0.52))],
                       rough=0.24, metal=0.55, coat=0.5)


def white(name="White"):
    return toy(name, (0.97, 0.96, 0.94), rough=0.35, coat=0.5)


# MARK: - Формы

def stand_up(ob):
    """Форма построена в XY (толщина по Z): ставим лицом к камере (к -Y)."""
    ob.rotation_euler = (math.radians(90), 0, 0)
    M.apply_transform(ob)
    return ob


def slab(name, pts, depth, bev, mat, segs=5, y=0.0):
    """Плоская фигура с толщиной и скругленными краями ("подушка")."""
    ob = M.profile_prism(name, pts, depth, -depth / 2)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    if bev > 0:
        mod = ob.modifiers.new("bevel", "BEVEL")
        mod.width = bev
        mod.segments = segs
        mod.limit_method = "ANGLE"
        mod.angle_limit = math.radians(30)
        mod.profile = 0.5
        M.bake(ob)
    M.smooth(ob, 35)
    stand_up(ob)
    ob.location.y += y
    M.apply_transform(ob)
    M.assign(ob, mat)
    return ob


def tube(name, pts, radius, mat, res=8):
    """Трубка вдоль ломаной (точки в плоскости XZ), концы закрыты."""
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = radius
    cu.bevel_resolution = res
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(pts) - 1)
    for p, co in zip(sp.points, pts):
        p.co = (co[0], co[1], co[2], 1)
    ob = M.link(bpy.data.objects.new(name + "Curve", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    out = M.link(bpy.data.objects.new(name, me))
    M.smooth(out)
    M.assign(out, mat)
    return out


def cone_head(name, tip, direction, radius, length, mat):
    """Наконечник стрелки: конус от основания к острию по направлению."""
    d = Vector(direction).normalized()
    ob = M.cylinder(name, 1.0, 1.0, 40)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=40, radius1=radius, radius2=0.0, depth=length)
    bm.to_mesh(ob.data)
    bm.free()
    M.bevel(ob, 0.03, 3, 40)
    M.bake(ob)
    M.smooth(ob, 40)
    q = d.to_track_quat("Z", "Y")
    base = Vector(tip) - d * length / 2
    ob.matrix_world = Matrix.Translation(base) @ q.to_matrix().to_4x4()
    M.assign(ob, mat)
    return ob


def arc(cx, cz, r, a0, a1, n=48, y=0.0):
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)), y,
             cz + r * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def glyph(name, text, size, depth, mat, font=BOLD):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    if os.path.exists(font):
        cu.font = bpy.data.fonts.load(font, check_existing=True)
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = depth
    cu.bevel_depth = depth * 0.6
    cu.bevel_resolution = 3
    ob = M.link(bpy.data.objects.new(name + "Curve", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    out = M.link(bpy.data.objects.new(name, me))
    stand_up(out)
    M.smooth(out, 40)
    M.assign(out, mat)
    return out


def star_pts(r_out=1.0, r_in=0.48, n=5, rot=90):
    pts = []
    for k in range(n * 2):
        a = math.radians(rot + k * 180 / n)
        r = r_out if k % 2 == 0 else r_in
        pts.append((r * math.cos(a), r * math.sin(a)))
    return pts


def heart_pts(scale=1.0, n=120):
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x = 16 * math.sin(t) ** 3
        y = 13 * math.cos(t) - 5 * math.cos(2 * t) - 2 * math.cos(3 * t) - math.cos(4 * t)
        pts.append((x / 17 * scale, (y + 2) / 17 * scale))
    return pts


def rounded_rect(w, h, r, n=10):
    pts = []
    for cx, cy, a0 in ((w / 2 - r, h / 2 - r, 0), (-w / 2 + r, h / 2 - r, 90), (-w / 2 + r, -h / 2 + r, 180),
                       (w / 2 - r, -h / 2 + r, 270)):
        for i in range(n + 1):
            a = math.radians(a0 + 90 * i / n)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def disc(name, r, depth, mat, y=0.0, bev=None):
    pts = [(r * math.cos(2 * math.pi * i / 64), r * math.sin(2 * math.pi * i / 64)) for i in range(64)]
    return slab(name, pts, depth, bev if bev is not None else depth * 0.45, mat, y=y)


def plus_badge(name, r=0.36, color=(0.36, 0.78, 0.30), loc=(0, 0, 0)):
    parts = [disc(name + "Disc", r, 0.2, toy(name + "Mat", color))]
    w = r * 0.28
    for i, (sx, sz) in enumerate(((r * 1.25, w), (w, r * 1.25))):
        b = M.box_mesh(f"{name}Bar{i}", sx, 0.08, sz, -sz / 2)
        b.location = (0, -0.11, 0)
        M.apply_transform(b)
        M.bevel(b, w * 0.45, 4, 30)
        M.bake(b)
        M.smooth(b, 30)
        M.assign(b, white(name + "W"))
        parts.append(b)
    for p in parts:
        p.location = Vector(p.location) + Vector(loc)
        M.apply_transform(p)
    return parts


def finish(parts, tilt=8):
    """Иконку чуть разворачиваем к камере, чтобы был виден объем."""
    return M.rotate_all(parts, (math.radians(tilt), 0, math.radians(-8)))


def _prep():
    C.reset_cache()
    C.gold_world(0.8)


# MARK: - Иконки

def icon_hint():
    _prep()
    metal = toy("Metal", (0.72, 0.76, 0.84), rough=0.25, coat=0.3, metal=0.6)
    base = [(0.0, 0.0), (0.15, 0.0), (0.19, 0.03), (0.2, 0.07), (0.23, 0.09), (0.23, 0.13), (0.2, 0.15), (0.23, 0.17),
            (0.23, 0.21), (0.2, 0.23), (0.23, 0.25), (0.23, 0.29), (0.26, 0.33), (0.0, 0.33)]
    b = M.lathe("Base", base, 64)
    M.smooth(b, 40)
    M.assign(b, metal)
    glass = [(0.0, 0.32), (0.26, 0.32), (0.3, 0.44), (0.42, 0.62), (0.52, 0.82), (0.55, 0.98), (0.52, 1.14),
             (0.42, 1.3), (0.26, 1.4), (0.0, 1.43)]
    g = M.lathe("Bulb", glass, 64)
    M.subdivide(g, 1)
    M.smooth(g)
    mat = toy("BulbMat", (1.0, 0.82, 0.18), rough=0.18, coat=1.0)
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Emission Color"].default_value = (1.0, 0.7, 0.15, 1)
    bsdf.inputs["Emission Strength"].default_value = 0.35
    M.assign(g, mat)
    # блик на стекле
    shine = tube("Shine", arc(0, 0.98, 0.36, 120, 175, 20, y=-0.42), 0.035, white("ShineW"))
    return finish([b, g, shine], tilt=4)


def icon_undo():
    _prep()
    mat = toy("Blue", (0.30, 0.62, 1.0))
    path = arc(0.05, 0.0, 0.62, -35, 205, 60)
    t = tube("Arc", path, 0.17, mat)
    end = Vector(path[-1])
    prev = Vector(path[-4])
    d = (end - prev).normalized()
    head = cone_head("Head", end + d * 0.42, d, 0.36, 0.5, mat)
    return finish([t, head])


def icon_shuffle():
    _prep()
    mat = toy("Green", (0.32, 0.80, 0.34))
    mat2 = toy("Green2", (0.22, 0.66, 0.30))
    parts = []
    for i, (z0, z1, y, m) in enumerate(((0.42, -0.42, -0.12, mat), (-0.42, 0.42, 0.12, mat2))):
        pts = []
        for k in range(41):
            t = k / 40
            x = -0.85 + 1.45 * t
            s = 0.5 - 0.5 * math.cos(math.pi * t)
            pts.append((x, y, z0 + (z1 - z0) * s))
        parts.append(tube(f"S{i}", pts, 0.13, m))
        end = Vector(pts[-1])
        parts.append(cone_head(f"H{i}", end + Vector((0.4, 0, 0)), (1, 0, 0), 0.3, 0.42, m))
    return finish(parts)


def icon_shelf():
    _prep()
    wood = M.material("Wood", [(0.0, (0.55, 0.32, 0.15)), (1.0, (0.82, 0.55, 0.30))], coord="z", lo=-0.3, hi=0.3,
                      rough=0.5, coat=0.4, bump=0.15, bump_scale=10, vary=0.12, vary_scale=4)
    plank = M.box_mesh("Plank", 1.7, 0.6, 0.22, -0.11)
    M.bevel(plank, 0.06, 4, 30)
    M.bake(plank)
    M.smooth(plank, 30)
    M.assign(plank, wood)
    parts = [plank]
    for i, x in enumerate((-0.55, 0.55)):
        br = M.box_mesh(f"Br{i}", 0.14, 0.4, 0.5, -0.6)
        br.location = (x, 0.08, 0)
        M.apply_transform(br)
        M.bevel(br, 0.04, 3, 30)
        M.bake(br)
        M.assign(M.smooth(br, 30), wood)
        parts.append(br)
    parts += plus_badge("Plus", 0.42, loc=(0.62, -0.25, 0.48))
    return finish(parts)


def icon_pause():
    _prep()
    wood = toy("Cap", (0.62, 0.38, 0.18), rough=0.45, coat=0.4)
    parts = []
    for i, z in enumerate((0.0, 1.5)):
        c = M.cylinder(f"Cap{i}", 0.62, 0.16, 48)
        c.location = (0, 0, z)
        M.apply_transform(c)
        M.bevel(c, 0.05, 3, 30)
        M.bake(c)
        M.assign(M.smooth(c, 30), wood)
        parts.append(c)
    prof = [(0.0, 0.08), (0.48, 0.08), (0.5, 0.25), (0.42, 0.5), (0.14, 0.72), (0.1, 0.75), (0.14, 0.78), (0.42, 1.0),
            (0.5, 1.25), (0.48, 1.42), (0.0, 1.42)]
    glass = M.lathe("Glass", prof, 64)
    M.subdivide(glass, 1)
    M.smooth(glass)
    gm = M.material("GlassMat", [(0.0, (0.75, 0.88, 1.0)), (1.0, (0.92, 0.97, 1.0))], coord="nz", lo=-1, hi=1,
                    rough=0.05, coat=1.0, transmission=0.85)
    M.assign(glass, gm)
    sand = toy("Sand", (1.0, 0.72, 0.25), rough=0.6, coat=0.1)
    s1 = M.lathe("SandLow", [(0.0, 0.1), (0.44, 0.1), (0.42, 0.25), (0.0, 0.5)], 48)
    s2 = M.lathe("SandTop", [(0.0, 1.05), (0.3, 1.12), (0.4, 1.2), (0.0, 1.22)], 48)
    for s in (s1, s2):
        M.assign(M.smooth(s), sand)
    posts = []
    for i, a in enumerate((45, 135, 225, 315)):
        p = M.cylinder(f"Post{i}", 0.05, 1.5, 16)
        p.location = (0.58 * math.cos(math.radians(a)), 0.58 * math.sin(math.radians(a)), 0.75)
        M.apply_transform(p)
        M.assign(M.smooth(p), wood)
        posts.append(p)
    return finish(parts + [glass, s1, s2] + posts, tilt=6)


def icon_heart():
    _prep()
    h = slab("Heart", heart_pts(1.0), 0.5, 0.22, toy("Red", (0.95, 0.22, 0.32)), segs=8)
    return finish([h])


def icon_unlimited():
    _prep()
    h = slab("Heart", heart_pts(1.0), 0.5, 0.22, toy("Red", (0.95, 0.22, 0.32)), segs=8)
    # знак бесконечности: лемниската Бернулли трубкой
    pts = []
    for i in range(121):
        t = 2 * math.pi * i / 120
        d = 1 + math.sin(t) ** 2
        pts.append((0.42 * math.cos(t) / d, -0.3, 0.1 + 0.42 * math.sin(t) * math.cos(t) / d))
    inf = tube("Inf", pts, 0.09, white())
    return finish([h, inf])


def icon_energy():
    _prep()
    pts = [(0.18, 1.0), (-0.52, -0.08), (-0.06, -0.08), (-0.26, -1.0), (0.52, 0.12), (0.06, 0.12), (0.38, 1.0)]
    b = slab("Bolt", pts, 0.34, 0.1, toy("Yellow", (1.0, 0.78, 0.12)), segs=6)
    return finish([b])


def icon_star():
    _prep()
    s = slab("Star", star_pts(1.0, 0.5), 0.36, 0.13, gold(), segs=6)
    return finish([s])


def icon_check():
    _prep()
    parts = [disc("Badge", 0.8, 0.26, toy("Green", (0.32, 0.78, 0.36)))]
    parts.append(tube("Tick", [(-0.38, -0.16, 0.0), (-0.1, -0.16, -0.27), (0.4, -0.16, 0.3)], 0.1, white()))
    return finish(parts)


def icon_plus():
    _prep()
    return finish(plus_badge("P", 0.8))


def icon_lock():
    _prep()
    g = gold()
    body = M.box_mesh("Body", 1.1, 0.5, 0.85, -0.55)
    M.bevel(body, 0.12, 5, 30)
    M.bake(body)
    M.assign(M.smooth(body, 30), g)
    shackle = tube("Shackle", [(-0.32, 0, 0.1), (-0.32, 0, 0.35)] + arc(0, 0.35, 0.32, 180, 0, 30)[1:] + [(0.32, 0, 0.1)],
                   0.09, toy("Steel", (0.72, 0.76, 0.84), metal=0.6, rough=0.2))
    hole = M.cylinder("Hole", 0.1, 0.1, 24)
    hole.rotation_euler = (math.radians(90), 0, 0)
    hole.location = (0, -0.27, -0.08)
    M.apply_transform(hole)
    M.assign(hole, M.flat("HoleMat", (0.25, 0.14, 0.05), rough=0.6))
    return finish([body, shackle, hole])


def icon_trophy():
    _prep()
    g = gold()
    cup = M.lathe("Cup", [(0.0, 0.0), (0.55, 0.0), (0.55, 0.12), (0.3, 0.16), (0.12, 0.3), (0.1, 0.5), (0.2, 0.62),
                          (0.45, 0.72), (0.62, 0.95), (0.68, 1.3), (0.6, 1.32), (0.0, 1.32)], 64)
    M.smooth(cup, 45)
    M.assign(cup, g)
    parts = [cup]
    for i, s in enumerate((-1, 1)):
        hd = tube(f"Handle{i}", arc(s * 0.66, 1.0, 0.24, -80 if s > 0 else 100, 80 if s > 0 else 260, 24), 0.07, g)
        parts.append(hd)
    st = slab("Emblem", star_pts(0.22, 0.1), 0.08, 0.02, toy("RedStar", (0.95, 0.3, 0.25)), y=-0.7)
    st.location = (0, 0, 0.98)
    M.apply_transform(st)
    parts.append(st)
    return finish(parts, tilt=6)


def icon_gift():
    _prep()
    red = toy("Red", (0.92, 0.25, 0.30))
    yellow = toy("Ribbon", (1.0, 0.80, 0.22))
    box = M.box_mesh("Box", 1.2, 1.0, 0.85, 0.0)
    M.bevel(box, 0.08, 4, 30)
    M.bake(box)
    M.assign(M.smooth(box, 30), red)
    lid = M.box_mesh("Lid", 1.34, 1.12, 0.26, 0.82)
    M.bevel(lid, 0.08, 4, 30)
    M.bake(lid)
    M.assign(M.smooth(lid, 30), red)
    parts = [box, lid]
    for i, (sx, sy) in enumerate(((0.26, 1.16), (1.38, 0.26))):
        r = M.box_mesh(f"Rib{i}", sx, sy, 1.12, -0.01)
        M.bevel(r, 0.04, 3, 30)
        M.bake(r)
        M.assign(M.smooth(r, 30), yellow)
        parts.append(r)
    # бант: две петли лицом к камере, слегка разведены в стороны
    for i, side in enumerate((-1, 1)):
        loop = M.torus(f"Bow{i}", 0.22, 0.08, 48, 12)
        loop.scale = (1.0, 0.8, 1.0)
        loop.rotation_euler = (math.radians(90), math.radians(side * 35), 0)
        loop.location = (side * 0.22, -0.1, 1.3)
        M.apply_transform(loop)
        M.assign(M.smooth(loop), yellow)
        parts.append(loop)
    knot = M.sphere("Knot", 0.13, 24, 12)
    knot.location = (0, -0.08, 1.2)
    M.apply_transform(knot)
    M.assign(M.smooth(knot), yellow)
    parts.append(knot)
    return finish(parts, tilt=14)


def icon_calendar():
    _prep()
    page = slab("Page", rounded_rect(1.4, 1.3, 0.16), 0.22, 0.06, white())
    top = slab("Top", rounded_rect(1.4, 0.36, 0.14), 0.26, 0.06, toy("Red", (0.92, 0.3, 0.3)))
    top.location = (0, 0, 0.55)
    M.apply_transform(top)
    parts = [page, top]
    for i, x in enumerate((-0.38, 0.38)):
        ring = tube(f"Ring{i}", arc(x, 0.72, 0.1, 200, -20, 16, y=-0.14), 0.04,
                    toy("Steel", (0.72, 0.76, 0.84), metal=0.6, rough=0.2))
        parts.append(ring)
    k = 0
    for r in range(3):
        for c in range(4):
            sq = M.box_mesh(f"D{k}", 0.2, 0.06, 0.16, -0.08)
            sq.location = (-0.45 + c * 0.3, -0.14, 0.17 - r * 0.25)
            M.apply_transform(sq)
            M.bevel(sq, 0.03, 2, 30)
            M.bake(sq)
            col = (1.0, 0.62, 0.2) if (r, c) == (1, 2) else (0.9, 0.86, 0.8)
            M.assign(M.smooth(sq, 30), toy(f"DM{k}", col))
            parts.append(sq)
            k += 1
    return finish(parts)


def icon_book():
    _prep()
    cover = toy("Cover", (0.88, 0.36, 0.22))
    pages = toy("Pages", (0.98, 0.95, 0.86), rough=0.6, coat=0.1)
    back = M.box_mesh("Back", 1.1, 0.42, 1.4, -0.7)
    M.bevel(back, 0.06, 3, 30)
    M.bake(back)
    M.assign(M.smooth(back, 30), cover)
    pg = M.box_mesh("PagesBlock", 1.0, 0.34, 1.3, -0.65)
    pg.location = (0.08, 0, 0)
    M.apply_transform(pg)
    M.bevel(pg, 0.02, 2, 30)
    M.bake(pg)
    M.assign(pg, pages)
    # обложка спереди чуть больше блока страниц
    front = M.box_mesh("Front", 1.12, 0.08, 1.42, -0.71)
    front.location = (0.0, -0.22, 0)
    M.apply_transform(front)
    M.bevel(front, 0.04, 3, 30)
    M.bake(front)
    M.assign(M.smooth(front, 30), cover)
    # поварской колпак на обложке
    w = white("Hat")
    hat = []
    for i, (x, z, r) in enumerate(((-0.17, 0.2, 0.17), (0.17, 0.2, 0.17), (0.0, 0.3, 0.2))):
        s = M.sphere(f"Puff{i}", r, 32, 16)
        s.scale = (1, 0.45, 1)
        s.location = (x, -0.28, z)
        M.apply_transform(s)
        M.assign(M.smooth(s), w)
        hat.append(s)
    band = M.box_mesh("Band", 0.42, 0.1, 0.18, -0.12)
    band.location = (0, -0.28, 0)
    M.apply_transform(band)
    M.bevel(band, 0.04, 3, 30)
    M.bake(band)
    M.assign(M.smooth(band, 30), w)
    mark = M.box_mesh("Ribbon", 0.12, 0.04, 0.5, -1.0)
    mark.location = (0.32, -0.05, 0)
    M.apply_transform(mark)
    M.assign(mark, toy("Mark", (0.25, 0.55, 0.95)))
    return finish([back, pg, front, band, mark] + hat, tilt=6)


def icon_map():
    _prep()
    land = toy("Land", (0.55, 0.82, 0.42), rough=0.5, coat=0.3)
    sea = toy("Sea", (0.45, 0.72, 0.98), rough=0.5, coat=0.3)
    parts = []
    for i, (x, a, m) in enumerate(((-0.52, 18, land), (0.0, -18, sea), (0.52, 18, land))):
        p = M.box_mesh(f"Panel{i}", 0.56, 0.05, 1.3, -0.65)
        p.rotation_euler = (0, 0, math.radians(a))
        p.location = (x, 0.0, 0)
        M.apply_transform(p)
        M.bevel(p, 0.02, 2, 30)
        M.bake(p)
        M.assign(p, m)
        parts.append(p)
    path = []
    for k in range(9):
        x = -0.6 + k * 0.15
        path.append((x, -0.16, -0.35 + 0.25 * math.sin(k * 0.9)))
    for k, co in enumerate(path[::2]):
        d = M.sphere(f"Dot{k}", 0.045, 12, 8)
        d.location = co
        M.apply_transform(d)
        M.assign(d, toy("DotMat", (0.95, 0.35, 0.3)))
        parts.append(d)
    pin = M.sphere("Pin", 0.24, 32, 16)
    pin.location = (0.32, -0.35, 0.5)
    M.apply_transform(pin)
    red = toy("PinRed", (0.95, 0.25, 0.28))
    M.assign(M.smooth(pin), red)
    tip = cone_head("PinTip", (0.32, -0.35, 0.05), (0, 0, -1), 0.17, 0.38, red)
    dot = M.sphere("PinDot", 0.09, 16, 8)
    dot.location = (0.32, -0.57, 0.52)
    M.apply_transform(dot)
    M.assign(M.smooth(dot), white("PinW"))
    return finish(parts + [pin, tip, dot], tilt=6)


def icon_cards():
    _prep()
    star = gold()
    parts = []
    for i, (fan, col) in enumerate(((-16, M.CARD_COLORS[2]), (0, M.CARD_COLORS[3]), (16, M.CARD_COLORS[4]))):
        card = M.album_card(f"C{i}", col[0], col[1], star)
        m = (Matrix.Translation((0, 0.1 - i * 0.05, -0.35)) @ Euler((0, math.radians(fan), 0)).to_matrix().to_4x4()
             @ Matrix.Translation((0, 0, 0.0)))
        for o in card:
            o.matrix_world = m @ o.matrix_world
        parts += card
    M.rotate_all(parts, (0, 0, 0))
    for o in parts:
        o.matrix_world = Matrix.Scale(1.8, 4) @ o.matrix_world
    return finish(parts, tilt=2)


def icon_ticket():
    _prep()
    tk = slab("Ticket", rounded_rect(1.7, 0.95, 0.14), 0.18, 0.05, toy("Gold", (1.0, 0.74, 0.18), coat=0.9))
    for i, x in enumerate((-0.85, 0.85)):
        cut = M.cylinder(f"Notch{i}", 0.17, 1.0, 40)
        cut.rotation_euler = (math.radians(90), 0, 0)
        cut.location = (x, 0, 0)
        M.apply_transform(cut)
        mod = tk.modifiers.new(f"notch{i}", "BOOLEAN")
        mod.operation = "DIFFERENCE"
        mod.object = cut
        M.bake(tk)
        bpy.data.objects.remove(cut)
    M.smooth(tk, 35)
    st = slab("Star", star_pts(0.3, 0.14), 0.1, 0.03, toy("RedStar", (0.95, 0.32, 0.25)), y=-0.12)
    st.location = (-0.15, 0, 0)
    M.apply_transform(st)
    parts = [tk, st]
    for k in range(5):
        d = M.box_mesh(f"Perf{k}", 0.035, 0.04, 0.1, -0.05)
        d.location = (0.48, -0.1, -0.32 + k * 0.16)
        M.apply_transform(d)
        M.assign(d, toy("PerfMat", (0.75, 0.45, 0.08)))
        parts.append(d)
    return finish(parts)


def icon_flag():
    _prep()
    pole = M.cylinder("Pole", 0.05, 1.9, 24)
    pole.location = (-0.75, 0, 0.0)
    M.apply_transform(pole)
    M.assign(M.smooth(pole), toy("PoleMat", (0.45, 0.3, 0.2), rough=0.4))
    knob = M.sphere("Knob", 0.1, 24, 12)
    knob.location = (-0.75, 0, 0.98)
    M.apply_transform(knob)
    M.assign(M.smooth(knob), gold())
    cloth = M.box_mesh("Cloth", 1.3, 0.04, 0.9, 0.0, cuts=12)
    cloth.location = (-0.1, 0, 0.0)
    M.apply_transform(cloth)
    for v in cloth.data.vertices:
        t = (v.co.x + 0.75) / 1.3
        v.co.y += 0.12 * math.sin(t * 5.5) * t
        v.co.z += 0.05 * math.sin(t * 4)
    M.smooth(cloth)
    mat = bpy.data.materials.new("Checker")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ch = nt.nodes.new("ShaderNodeTexChecker")
    ch.inputs["Scale"].default_value = 3.0
    ch.inputs["Color1"].default_value = (0.02, 0.02, 0.03, 1)
    ch.inputs["Color2"].default_value = (0.95, 0.95, 0.95, 1)
    nt.links.new(tc.outputs["Object"], ch.inputs["Vector"])
    nt.links.new(ch.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Coat Weight"].default_value = 0.4
    M.assign(cloth, mat)
    return finish([pole, knob, cloth], tilt=6)


def icon_gear():
    _prep()
    pts = []
    teeth = 8
    for i in range(teeth * 4):
        a = 2 * math.pi * i / (teeth * 4)
        r = 1.0 if (i % 4) in (1, 2) else 0.78
        pts.append((r * math.cos(a), r * math.sin(a)))
    g = slab("Gear", pts, 0.36, 0.06, toy("Steel", (0.62, 0.68, 0.80), metal=0.3, rough=0.3), segs=4)
    hole = M.cylinder("Hole", 0.3, 1.0, 48)
    hole.rotation_euler = (math.radians(90), 0, 0)
    M.apply_transform(hole)
    mod = g.modifiers.new("hole", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = hole
    M.bake(g)
    bpy.data.objects.remove(hole)
    M.smooth(g, 35)
    return finish([g])


def icon_medal():
    _prep()
    parts = []
    for i, (x, a, col) in enumerate(((-0.22, -14, (0.92, 0.28, 0.3)), (0.22, 14, (0.28, 0.5, 0.95)))):
        rb = slab(f"Rib{i}", [(-0.18, 0.0), (0.18, 0.0), (0.18, -0.95), (0.0, -0.78), (-0.18, -0.95)], 0.08, 0.02,
                  toy(f"RibM{i}", col), y=0.1)
        rb.rotation_euler = (0, math.radians(a), 0)
        rb.location = (x, 0, -0.1)
        M.apply_transform(rb)
        parts.append(rb)
    pts = []
    for i in range(48):
        a = 2 * math.pi * i / 48
        r = 0.72 + 0.06 * math.cos(a * 12)
        pts.append((r * math.cos(a), r * math.sin(a)))
    ros = slab("Rosette", pts, 0.2, 0.05, gold())
    ros.location = (0, 0, 0.2)
    M.apply_transform(ros)
    st = slab("Star", star_pts(0.34, 0.16), 0.1, 0.03, toy("Cream", (1.0, 0.92, 0.6)), y=-0.13)
    st.location = (0, 0, 0.2)
    M.apply_transform(st)
    return finish(parts + [ros, st])


def icon_ad():
    _prep()
    screen = slab("Screen", rounded_rect(1.6, 1.15, 0.28), 0.3, 0.1, toy("Purple", (0.55, 0.36, 0.95)), segs=6)
    play = slab("Play", [(-0.22, 0.32), (0.34, 0.0), (-0.22, -0.32)], 0.1, 0.05, white(), y=-0.18)
    return finish([screen, play])


def icon_palette():
    _prep()
    pts = []
    for i in range(80):
        a = 2 * math.pi * i / 80
        r = 0.95 + 0.12 * math.cos(2 * a) - (0.28 if abs(math.atan2(math.sin(a - 5.6), math.cos(a - 5.6))) < 0.35 else 0)
        pts.append((r * math.cos(a) * 1.1, r * math.sin(a) * 0.85))
    pal = slab("Palette", pts, 0.16, 0.05, M.material("PalWood", [(0.0, (0.72, 0.5, 0.28)), (1.0, (0.9, 0.7, 0.45))],
                                                        coord="nz", lo=-1, hi=1, rough=0.45, coat=0.4))
    hole = M.cylinder("Hole", 0.14, 1.0, 32)
    hole.rotation_euler = (math.radians(90), 0, 0)
    hole.location = (-0.48, 0, -0.25)
    M.apply_transform(hole)
    mod = pal.modifiers.new("hole", "BOOLEAN")
    mod.operation = "DIFFERENCE"
    mod.object = hole
    M.bake(pal)
    bpy.data.objects.remove(hole)
    parts = [pal]
    cols = [(0.95, 0.25, 0.3), (1.0, 0.78, 0.15), (0.3, 0.8, 0.35), (0.3, 0.55, 1.0), (0.7, 0.35, 0.95)]
    for i, (x, z) in enumerate(((-0.45, 0.32), (-0.05, 0.48), (0.38, 0.38), (0.62, 0.02), (0.3, -0.38))):
        d = M.sphere(f"Paint{i}", 0.17, 32, 16)
        d.scale = (1, 0.5, 0.85)
        d.location = (x, -0.1, z)
        M.apply_transform(d)
        M.assign(M.smooth(d), toy(f"PM{i}", cols[i], rough=0.15, coat=1.0))
        parts.append(d)
    return finish(parts)


MODELS = {name: fn for name, fn in globals().items() if name.startswith("icon_") and callable(fn)}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--size", type=int, default=256)
    ap.add_argument("--samples", type=int, default=64)
    args = ap.parse_args()
    M.MODELS.update(MODELS)
    ids = [s for s in args.only.split(",") if s] or list(MODELS)
    for sid in ids:
        M.render(sid, args.out, args.size, samples=args.samples)
        print("rendered", sid, flush=True)


if __name__ == "__main__":
    main()
