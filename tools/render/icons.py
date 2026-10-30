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


def icon_pause():
    """Песочные часы: прозрачное стекло с бликами, золотистый песок горкой и струйкой, точеные деревянные стойки."""
    _prep()
    import models_match3 as M3
    wood = M3.wood("Cap", (0.74, 0.44, 0.20), axis="x", rough=0.35, coat=0.6, grain=0.3)
    post_m = M3.wood("Post", (0.70, 0.40, 0.18), axis="z", rough=0.35, coat=0.6, grain=0.25)
    parts = []
    for i, z in enumerate((0.0, 1.5)):
        c = M3.lathe_smooth(f"Cap{i}", [(0.6, z - 0.08), (0.64, z - 0.05), (0.66, z + 0.0), (0.64, z + 0.05), (0.6, z + 0.08)],
                            64, 4)
        parts.append(M.assign(M.smooth(c), wood))
    prof = [(0.48, 0.08), (0.5, 0.25), (0.42, 0.5), (0.14, 0.72), (0.1, 0.75), (0.14, 0.78), (0.42, 1.0), (0.5, 1.25),
            (0.48, 1.42)]
    glass = M3.lathe_smooth("Glass", prof, 96, 5)
    M.smooth(glass)
    M.assign(glass, M3.glass("GlassMat", tint=(0.96, 0.98, 1.0), edge=(0.80, 0.90, 1.0), center=0.05, rim=0.75))
    glass.visible_shadow = False
    sand = candy("Sand", (1.0, 0.70, 0.22), rough=0.5, coat=0.2)
    nz = sand.node_tree.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 80.0
    bp = sand.node_tree.nodes.new("ShaderNodeBump")
    bp.inputs["Strength"].default_value = 0.3
    sand.node_tree.links.new(nz.outputs["Fac"], bp.inputs["Height"])
    sand.node_tree.links.new(bp.outputs["Normal"], sand.node_tree.nodes["Principled BSDF"].inputs["Normal"])
    low = M3.lathe_smooth("SandLow", [(0.46, 0.1), (0.47, 0.2), (0.32, 0.32), (0.12, 0.4), (0.02, 0.43)], 64, 4)
    top = M3.lathe_smooth("SandTop", [(0.12, 0.8), (0.3, 0.9), (0.42, 1.02), (0.36, 1.06), (0.16, 1.0), (0.02, 0.97)], 64, 4)
    stream = M.cylinder("Stream", 0.018, 0.36, 12)
    stream.location = (0, 0, 0.6)
    M.apply_transform(stream)
    for o in (low, top, stream):
        M.assign(M.smooth(o), sand)
    posts = []
    for i, a in enumerate((45, 135, 225, 315)):
        p = M3.lathe_smooth(f"Post{i}", [(0.045, 0.06), (0.06, 0.18), (0.04, 0.4), (0.07, 0.75), (0.04, 1.1), (0.06, 1.32),
                                         (0.045, 1.44)], 24, 4)
        p.location = (0.6 * math.cos(math.radians(a)), 0.6 * math.sin(math.radians(a)), 0.0)
        M.apply_transform(p)
        posts.append(M.assign(M.smooth(p), post_m))
    hl = shine("Shine", [(-0.3 + 0.005 * k, -0.36, 1.05 + 0.04 * k) for k in range(6)], 0.025)
    hl2 = shine("Shine2", [(-0.34 + 0.01 * k, -0.37, 0.2 + 0.04 * k) for k in range(5)], 0.02)
    return finish(parts + [glass, low, top, stream, hl, hl2] + posts, tilt=6)


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
    """Билет ивента: золотой билет с красной граненой звездой и кремовой рамкой, красный корешок через перфорацию."""
    _prep()
    H, T = 0.98, 0.2
    pieces = []
    for name, cx, w, col in (("Main", -0.23, 1.3, (1.0, 0.76, 0.18)), ("Stub", 0.675, 0.41, (0.98, 0.38, 0.30))):
        pc = slab(name, ccw(rounded_rect(w, H, 0.12, 8)), T, 0.06, candy(name + "M", col, rough=0.2), segs=5)
        pc.location.x += cx
        M.apply_transform(pc)
        pieces.append(pc)
    for i, x in enumerate((-0.88, 0.88)):
        cut = M.cylinder(f"Notch{i}", 0.13, 1.0, 48)
        cut.rotation_euler = (math.radians(90), 0, 0)
        cut.location = (x, 0, 0)
        M.apply_transform(cut)
        M.boolean_cut(pieces[i], [cut])
        M.smooth(pieces[i], 35)
    st = faceted_star("Star", 0.3, 0.15, front=0.12, back=0.02, rim=0.06, tip=0.03)
    st.location = (-0.17, -0.12, 0.0)
    M.apply_transform(st)
    M.assign(st, C.world_mat("StarRed", [(0.0, (0.70, 0.08, 0.08)), (0.5, (0.95, 0.22, 0.20)), (1.0, (1.0, 0.55, 0.45))],
                             rough=0.16, metal=0.0, coat=0.9))
    cream = candy("Cream", (1.0, 0.95, 0.84), rough=0.3, coat=0.5)
    rr = rounded_rect(0.88, 0.74, 0.08, 6)
    frame = tube("Frame", [(x - 0.17, -0.105, z) for x, z in rr + rr[:1]], 0.017, cream, res=6)
    parts = pieces + [st, frame]
    for k, z in enumerate((0.2, 0.0, -0.2)):
        bar = slab(f"Line{k}", rounded_rect(0.2 if k != 1 else 0.14, 0.06, 0.029, 6), 0.04, 0.015, cream, segs=3, y=-0.105)
        bar.location = (0.675, bar.location.y, z)
        M.apply_transform(bar)
        parts.append(bar)
    parts.append(shine("Shine", [(-0.56 + 0.07 * k, -0.115, 0.3) for k in range(4)], 0.02))
    M.rotate_all(parts, (0, math.radians(-12), 0))
    return finish(parts, tilt=8)


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


def icon_crown():
    _prep()
    g = gold()
    pts = [(-0.95, -0.45), (0.95, -0.45), (1.05, 0.55), (0.55, 0.12), (0.0, 0.75), (-0.55, 0.12), (-1.05, 0.55)]
    body = slab("Crown", pts, 0.42, 0.1, g, segs=5)
    band = M.box_mesh("Band", 2.0, 0.5, 0.24, -0.62)
    M.bevel(band, 0.07, 4, 30)
    M.bake(band)
    M.assign(M.smooth(band, 30), g)
    parts = [body, band]
    cols = [(0.95, 0.2, 0.3), (0.2, 0.55, 1.0), (0.95, 0.2, 0.3)]
    for i, x in enumerate((-0.55, 0.0, 0.55)):
        gem_ = M.sphere(f"Gem{i}", 0.13, 24, 12)
        gem_.scale = (1, 0.6, 1)
        gem_.location = (x, -0.27, -0.5)
        M.apply_transform(gem_)
        M.assign(M.smooth(gem_), toy(f"GemM{i}", cols[i], rough=0.08, coat=1.0))
        parts.append(gem_)
    for i, (x, z) in enumerate(((-1.05, 0.62), (0.0, 0.84), (1.05, 0.62))):
        b = M.sphere(f"Ball{i}", 0.13, 24, 12)
        b.location = (x, 0, z)
        M.apply_transform(b)
        M.assign(M.smooth(b), g)
        parts.append(b)
    return finish(parts, tilt=6)


def icon_chef():
    _prep()
    w = white("Hat")
    parts = []
    for i, (x, z, r) in enumerate(((-0.42, 0.35, 0.42), (0.42, 0.35, 0.42), (0.0, 0.62, 0.5), (-0.2, 0.2, 0.38),
                                   (0.2, 0.2, 0.38))):
        s_ = M.sphere(f"Puff{i}", r, 40, 20)
        s_.scale = (1, 0.8, 1)
        s_.location = (x, 0, z)
        M.apply_transform(s_)
        M.assign(M.smooth(s_), w)
        parts.append(s_)
    band = M.cylinder("Band", 0.62, 0.45, 48)
    band.scale = (1, 0.8, 1)
    band.location = (0, 0, -0.18)
    M.apply_transform(band)
    M.bevel(band, 0.06, 4, 30)
    M.bake(band)
    M.assign(M.smooth(band, 30), w)
    stripe = M.torus("Stripe", 0.63, 0.05, 48, 10)
    stripe.scale = (1, 0.8, 1)
    stripe.location = (0, 0, -0.1)
    M.apply_transform(stripe)
    M.assign(M.smooth(stripe), toy("Stripe", (0.95, 0.5, 0.15)))
    parts += [band, stripe]
    return finish(parts, tilt=8)


def icon_music():
    _prep()
    mat = toy("Note", (0.55, 0.38, 0.95))
    parts = []
    for i, (x, z) in enumerate(((-0.45, -0.55), (0.45, -0.38))):
        h = M.sphere(f"Head{i}", 0.3, 40, 20)
        h.scale = (1.25, 0.7, 0.9)
        h.rotation_euler = (0, math.radians(-25), 0)
        h.location = (x, 0, z)
        M.apply_transform(h)
        M.assign(M.smooth(h), mat)
        st = M.cylinder(f"Stem{i}", 0.07, 1.1, 24)
        st.location = (x + 0.3, 0, z + 0.55)
        M.apply_transform(st)
        M.assign(M.smooth(st), mat)
        parts += [h, st]
    beam = slab("Beam", [(-0.22, 0.95), (0.82, 1.12), (0.82, 0.86), (-0.22, 0.69)], 0.16, 0.05, mat)
    parts.append(beam)
    return finish(parts)


def icon_sound():
    _prep()
    body = toy("Speaker", (0.95, 0.55, 0.2))
    box = M.box_mesh("Box", 0.42, 0.42, 0.55, -0.275)
    box.location = (-0.55, 0, 0)
    M.apply_transform(box)
    M.bevel(box, 0.06, 3, 30)
    M.bake(box)
    M.assign(M.smooth(box, 30), body)
    cone = slab("Cone", [(-0.36, 0.3), (0.05, 0.62), (0.05, -0.62), (-0.36, -0.3)], 0.4, 0.06, body)
    parts = [box, cone]
    for i, r in enumerate((0.38, 0.66)):
        parts.append(tube(f"Wave{i}", arc(0.1, 0.0, r, -45, 45, 24, y=-0.05), 0.07, toy(f"WaveM{i}", (0.3, 0.62, 1.0))))
    return finish(parts)


def icon_haptics():
    _prep()
    phone = slab("Phone", rounded_rect(0.8, 1.4, 0.16), 0.18, 0.05, toy("Case", (0.3, 0.32, 0.4)))
    screen = slab("Screen", rounded_rect(0.62, 1.16, 0.1), 0.04, 0.0, toy("Glass", (0.45, 0.75, 1.0), rough=0.1), y=-0.1)
    parts = [phone, screen]
    for side in (-1, 1):
        for k, r in enumerate((0.0, 0.18)):
            pts = [(side * (0.58 + r), -0.02, z) for z in (-0.35, -0.18, 0.0, 0.18, 0.35)]
            pts = [(p[0] + side * 0.05 * (1 if j % 2 else -1), p[1], p[2]) for j, p in enumerate(pts)]
            parts.append(tube(f"Buzz{side}{k}", pts, 0.045, toy("BuzzM", (0.95, 0.55, 0.2))))
    return finish(parts)


def icon_globe():
    _prep()
    sea = toy("Sea", (0.3, 0.62, 1.0))
    ball = M.sphere("Globe", 0.85, 64, 32)
    M.assign(M.smooth(ball), sea)
    land = toy("Land", (0.42, 0.8, 0.38), rough=0.45)
    parts = [ball]
    rnd = random.Random(4)
    for i, (a, b, r) in enumerate(((200, 20, 0.32), (250, -25, 0.24), (300, 30, 0.2), (240, 45, 0.18))):
        blob = M.sphere(f"Land{i}", r, 32, 16)
        th, ph = math.radians(a), math.radians(b)
        blob.scale = (1.0, 0.35, 0.8)
        blob.location = (0.78 * math.cos(ph) * math.cos(th + math.pi / 2), 0.78 * math.cos(ph) * math.sin(th + math.pi / 2) * 1.0,
                         0.78 * math.sin(ph))
        blob.rotation_euler = (0, 0, th)
        M.apply_transform(blob)
        M.assign(M.smooth(blob), land)
        parts.append(blob)
    ring = M.torus("Meridian", 0.95, 0.05, 64, 10)
    ring.rotation_euler = (0, math.radians(90), math.radians(30))
    M.apply_transform(ring)
    M.assign(M.smooth(ring), gold())
    parts.append(ring)
    return finish(parts)


def icon_flame():
    _prep()
    def flame_pts(r, h, tip=0.18, n=24):
        def bez(p0, c, p1, k):
            return [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * c[0] + t * t * p1[0],
                     (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * c[1] + t * t * p1[1]) for t in [i / k for i in range(1, k)]]
        pts = [(r * math.cos(math.radians(a)), r * math.sin(math.radians(a))) for a in range(180, 361, 10)]
        pts += bez((r, 0.0), (r * 1.05, h * 0.5), (tip * r, h), n)
        pts.append((tip * r, h))
        pts += bez((tip * r, h), (-r * 0.95, h * 0.62), (-r, 0.0), n)
        return pts
    outer = slab("Outer", flame_pts(0.62, 1.25), 0.42, 0.14, toy("Orange", (1.0, 0.45, 0.12)), segs=6)
    inner = slab("Inner", [(x * 0.55, y * 0.55 - 0.2) for x, y in flame_pts(0.62, 1.25)], 0.2, 0.08,
                 toy("Yellow", (1.0, 0.85, 0.2)), segs=5, y=-0.18)
    return finish([outer, inner])


def icon_snowflake():
    _prep()
    ice = toy("Ice", (0.55, 0.82, 1.0), rough=0.15, coat=1.0)
    parts = []
    for k in range(6):
        a = math.radians(90 + 60 * k)
        d = (math.cos(a), 0, math.sin(a))
        parts.append(tube(f"Arm{k}", [(0, 0, 0), (d[0] * 0.95, 0, d[2] * 0.95)], 0.07, ice))
        for j, t in enumerate((0.45, 0.7)):
            base = (d[0] * t, 0, d[2] * t)
            for side in (-1, 1):
                b = a + side * math.radians(45)
                tip = (base[0] + math.cos(b) * 0.25, 0, base[2] + math.sin(b) * 0.25)
                parts.append(tube(f"Br{k}{j}{side}", [base, tip], 0.05, ice))
    hub = M.sphere("Hub", 0.14, 24, 12)
    M.assign(M.smooth(hub), ice)
    parts.append(hub)
    return finish(parts)


# MARK: - Надутые формы (версия 2: звезда, сердце, значки, замок, шестеренка, стрелки)

def round_corners(pts, r, n=6):
    """Многоугольник со скругленными углами (квадратичная кривая у каждой вершины)."""
    out = []
    m = len(pts)
    for i in range(m):
        a, p, b = Vector(pts[i - 1]), Vector(pts[i]), Vector(pts[(i + 1) % m])
        da, db = (a - p), (b - p)
        ra, rb = min(r, da.length * 0.45), min(r, db.length * 0.45)
        p0, p1 = p + da.normalized() * ra, p + db.normalized() * rb
        for k in range(n + 1):
            t = k / n
            q = p0 * (1 - t) ** 2 + p * 2 * (1 - t) * t + p1 * t * t
            out.append((q.x, q.y))
    return out


def ccw(pts):
    area = sum(pts[i - 1][0] * pts[i][1] - pts[i][0] * pts[i - 1][1] for i in range(len(pts)))
    return pts if area > 0 else list(reversed(pts))


def radial(outline, center=(0.0, 0.0), samples=1440):
    """Радиус контура по углу (луч из центра; контур звездный относительно центра)."""
    cx, cy = center
    segs = [((x0 - cx, y0 - cy), (x1 - cx, y1 - cy)) for (x0, y0), (x1, y1) in zip(outline, outline[1:] + outline[:1])]
    table = []
    for k in range(samples):
        a = 2 * math.pi * k / samples
        dx, dy = math.cos(a), math.sin(a)
        best = 0.0
        for (ax, ay), (bx, by) in segs:
            ex, ey = bx - ax, by - ay
            den = dx * ey - dy * ex
            if abs(den) < 1e-12:
                continue
            t = (ax * ey - ay * ex) / den
            u = (ax * dy - ay * dx) / den
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = t if best == 0.0 else min(best, t)
        table.append(best)

    def R(a):
        f = (a % (2 * math.pi)) / (2 * math.pi) * samples
        i = int(f)
        w = f - i
        return table[i % samples] * (1 - w) + table[(i + 1) % samples] * w
    return R


def inflate(name, outline, front, back=None, center=(0.0, 0.0), ridge=0.0, ridge_n=5, ridge_phase=90.0, power=1.0,
            segs=360, rings=72):
    """Надутая игрушечная фигура по контуру: в сечении эллипс, фронт толще тыла.
    Строится в XY (толщина по Z) и встает лицом к камере, как slab()."""
    R = radial(outline, center)
    back = front * 0.6 if back is None else back
    ob = M.sphere(name, 1.0, segs, rings)

    def f(co):
        a = math.atan2(co.y, co.x)
        rr = R(a)
        z = co.z
        t = math.sqrt(max(0.0, 1 - z * z))
        if z > 0:
            zz = front * z ** power
            if ridge:
                w = max(0.0, math.cos(ridge_n * (a - math.radians(ridge_phase))))
                zz *= 1 + ridge * (w ** 6) * t
        else:
            zz = back * z
        return Vector((center[0] + rr * co.x, center[1] + rr * co.y, zz))
    M.deform(ob, f)
    M.smooth(ob)
    stand_up(ob)
    ob["R"] = 0
    return ob, R


def surface_y(R, front, x, z, center=(0.0, 0.0), power=1.0):
    """Глубина надутой поверхности (по -Y) в точке (x, z) лицевой стороны."""
    dx, dz = x - center[0], z - center[1]
    rr = R(math.atan2(dz, dx)) or 1.0
    t = min(1.0, math.hypot(dx, dz) / rr)
    return -front * math.sqrt(max(0.0, 1 - t * t)) ** power


def shine(name, pts, radius, strength=1.0):
    """Белый блик-полоска (как на лампочке и банке)."""
    mat = M.flat(name + "M", (1.0, 1.0, 1.0), rough=0.3)
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (1.0, 1.0, 1.0, 1)
    b.inputs["Emission Strength"].default_value = strength
    return tube(name, pts, radius, mat, res=6)


def shine_on(name, R, front, center, pts2d, radius, lift=0.012, power=1.0, strength=1.0):
    pts = [(x, surface_y(R, front, x, z, center, power) - lift, z) for x, z in pts2d]
    return shine(name, pts, radius, strength)


def candy(name, color, rough=0.16, coat=1.0, sss=0.0):
    mat = toy(name, color, rough=rough, coat=coat)
    if sss:
        b = mat.node_tree.nodes["Principled BSDF"]
        b.inputs["Subsurface Weight"].default_value = sss
        b.inputs["Subsurface Radius"].default_value = (1.0, 0.3, 0.25)
        b.inputs["Subsurface Scale"].default_value = 0.05
    return mat


def bright_gold(name="StarGold"):
    return C.world_mat(name, [(0.0, (0.90, 0.50, 0.04)), (0.45, (1.0, 0.74, 0.12)), (0.75, (1.0, 0.86, 0.30)),
                              (1.0, (1.0, 0.97, 0.70))], rough=0.18, metal=0.45, coat=0.8)


def band(path, w0, w1=None, head=None, tail_round=True):
    """Полоса вдоль ломаной в плоскости XY шириной 2w; head=(длина, полуширина) - наконечник стрелки."""
    w1 = w0 if w1 is None else w1
    P = [Vector((x, y)) for x, y in path]
    n = len(P)
    left, right = [], []
    for i, p in enumerate(P):
        d = (P[min(i + 1, n - 1)] - P[max(i - 1, 0)]).normalized()
        nrm = Vector((-d.y, d.x))
        w = w0 + (w1 - w0) * i / (n - 1)
        left.append(p + nrm * w)
        right.append(p - nrm * w)
    out = list(left)
    if head:
        L, hw = head
        d = (P[-1] - P[-2]).normalized()
        nrm = Vector((-d.y, d.x))
        out += [P[-1] + nrm * hw, P[-1] + d * L, P[-1] - nrm * hw]
    out += list(reversed(right))
    if tail_round:
        d = (P[1] - P[0]).normalized()
        nrm = Vector((-d.y, d.x))
        for k in range(1, 10):
            a = math.pi * k / 10
            out.append(P[0] - nrm * w0 * math.cos(a) - d * w0 * math.sin(a))
    return [(v.x, v.y) for v in out]


def layered(name, outline, depth, bev, color, rim_color, rim=0.07, y=0.0, segs=8, rim_depth=None):
    """Фигура с темной окантовкой позади: на 30 точках силуэт остается четким."""
    pts = ccw(outline)
    front = slab(name, pts, depth, bev, candy(name + "M", color), segs=segs, y=y)
    back_pts = EV_offset(pts, -rim)
    rd = rim_depth if rim_depth is not None else depth * 0.8
    back = slab(name + "Rim", back_pts, rd, min(bev, rd * 0.45), candy(name + "RimM", rim_color, rough=0.3, coat=0.5),
                segs=segs, y=y + depth * 0.25)
    return [front, back]


def EV_offset(pts, d):
    import models_events as EV
    return EV.outline_offset(pts, d)


def badge(name, color, ring):
    """Круглый значок: темное кольцо-основание и надутый купол."""
    base = disc(name + "Base", 1.0, 0.3, candy(name + "BaseM", ring, rough=0.25, coat=0.7), bev=0.12)
    circle = [(0.84 * math.cos(2 * math.pi * k / 96), 0.84 * math.sin(2 * math.pi * k / 96)) for k in range(96)]
    dome, R = inflate(name + "Dome", circle, 0.26, 0.05, segs=128, rings=48)
    M.assign(dome, candy(name + "DomeM", color, rough=0.14))
    dome.location.y -= 0.1
    M.apply_transform(dome)
    hl = shine(name + "Shine", arc(0, 0, 0.66, 112, 158, 20, y=-0.28), 0.045)
    return [base, dome, hl]


def symbol_slab(name, pts, depth=0.12, bev=0.05, y=-0.38, color=(0.99, 0.98, 0.95)):
    return slab(name, ccw(pts), depth, bev, candy(name + "M", color, rough=0.25, coat=0.6), segs=6, y=y)


# MARK: - Иконки (версия 2)

def faceted_star(name, r_out=1.0, r_in=0.5, front=0.42, back=0.16, rim=0.14, tip=0.08):
    """Граненая звезда: лучи с ребром посередине, светлые и темные грани; кончики и ребра чуть скруглены."""
    outline = round_corners(star_pts(r_out, r_in), tip, 4)
    n = len(outline)
    verts = [(0.0, 0.0, front + rim / 2), (0.0, 0.0, -back - rim / 2)]
    verts += [(x, y, rim / 2) for x, y in outline] + [(x, y, -rim / 2) for x, y in outline]
    faces = []
    for i in range(n):
        j = (i + 1) % n
        faces.append((0, 2 + i, 2 + j))
        faces.append((1, 2 + n + j, 2 + n + i))
        faces.append((2 + i, 2 + n + i, 2 + n + j, 2 + j))
    ob = M.from_data(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    mod = ob.modifiers.new("bevel", "BEVEL")
    mod.width = 0.045
    mod.segments = 4
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(20)
    M.bake(ob)
    M.smooth(ob, 28)
    stand_up(ob)
    return ob


def icon_star():
    """Звезда: граненая (светлые и темные грани читаются даже на 30 точках), яркое полированное золото."""
    _prep()
    s = faceted_star("Star")
    M.assign(s, bright_gold())
    return finish([s], tilt=10)


def heart_outline():
    return ccw(heart_pts(1.0, 200))


def icon_heart():
    """Сердце-жизнь: надутая карамель с глубоким цветом и бликом на левой половинке."""
    _prep()
    c = (0.0, -0.08)
    h, R = inflate("Heart", heart_outline(), 0.44, 0.24, center=c, power=0.85)
    M.assign(h, candy("Red", (0.96, 0.18, 0.30), rough=0.14, sss=0.15))
    hl = shine_on("Shine", R, 0.44, c, [(-0.62 + 0.04 * k, 0.36 + 0.07 * k - 0.006 * k * k) for k in range(8)], 0.045,
                  power=0.85)
    dot = shine_on("Dot", R, 0.44, c, [(-0.3, 0.62), (-0.27, 0.63)], 0.035, power=0.85)
    return finish([h, hl, dot], tilt=8)


def icon_unlimited():
    """Безлимит: то же сердце и золотая бесконечность, лежащая по его поверхности."""
    _prep()
    c = (0.0, -0.08)
    h, R = inflate("Heart", heart_outline(), 0.44, 0.24, center=c, power=0.85)
    M.assign(h, candy("Red", (0.96, 0.18, 0.30), rough=0.14, sss=0.15))
    pts = []
    for i in range(161):
        t = 2 * math.pi * i / 160
        d = 1 + math.sin(t) ** 2
        x, z = 0.5 * math.cos(t) / d, 0.06 + 0.5 * math.sin(t) * math.cos(t) / d
        pts.append((x, surface_y(R, 0.44, x, z, c, 0.85) - 0.07, z))
    inf = tube("Inf", pts, 0.085, bright_gold("InfGold"), res=8)
    hl = shine_on("Shine", R, 0.44, c, [(-0.66 + 0.04 * k, 0.4 + 0.06 * k - 0.005 * k * k) for k in range(7)], 0.04,
                  power=0.85)
    return finish([h, inf, hl], tilt=8)


def icon_energy():
    """Энергия: толстая молния, желтая с оранжевой окантовкой, блик по верхней грани."""
    _prep()
    pts = [(0.22, 1.0), (-0.56, -0.1), (-0.06, -0.1), (-0.3, -1.0), (0.58, 0.14), (0.08, 0.14), (0.42, 1.0)]
    pts = round_corners(ccw(pts), 0.07, 5)
    parts = layered("Bolt", pts, 0.38, 0.13, (1.0, 0.82, 0.16), (0.96, 0.46, 0.08), rim=0.08)
    parts.append(shine("Shine", [(0.16 - 0.06 * k, -0.21, 0.82 - 0.11 * k) for k in range(6)], 0.03))
    return finish(parts, tilt=8)


def arrow_head(name, base, d, L, hw, depth, mat, y=0.0):
    """Плоский наконечник стрелки со скругленными углами: основание в base (x, z), острие по направлению d."""
    pts = round_corners([(0.0, -hw), (L, 0.0), (0.0, hw)], 0.07, 5)
    h = slab(name, pts, depth, depth * 0.3, mat, segs=5)
    th = math.atan2(d[1], d[0])
    h.rotation_euler = (0, -th, 0)
    M.apply_transform(h)
    h.location = (base[0], y, base[1])
    M.apply_transform(h)
    return h


def icon_undo():
    """Отмена: глянцевая дуга-трубка против часовой и широкий плоский наконечник вниз-влево."""
    _prep()
    mat = candy("Blue", (0.28, 0.62, 1.0), rough=0.14)
    rc, r = 0.52, 0.17
    path = arc(0.05, 0.08, rc, -35, 176, 64)
    body = tube("Arc", path, r, mat, res=10)
    end, prev = Vector(path[-1]), Vector(path[-3])
    d = (end - prev).normalized()
    head = arrow_head("Head", (end.x - d.x * 0.04, end.z - d.z * 0.04), (d.x, d.z), 0.5, 0.42, 0.26, mat)
    hl = shine("Shine", arc(0.05, 0.08, rc + 0.04, 62, 118, 16, y=-0.19), 0.03)
    return finish([body, head, hl], tilt=8)


def icon_shuffle():
    """Перемешать: две глянцевые трубки крест-накрест с прямыми концами и плоскими наконечниками."""
    _prep()
    parts = []
    for i, (z0, z1, col, y) in enumerate(((0.5, -0.5, (0.20, 0.68, 0.48), 0.18), (-0.5, 0.5, (0.42, 0.88, 0.36), -0.18))):
        mat = candy(f"Green{i}", col, rough=0.14)
        path = []
        for k in range(49):
            x = -0.92 + 1.3 * k / 48
            t = min(1.0, max(0.0, (x + 0.62) / 0.9))
            s_ = t * t * (3 - 2 * t)
            path.append((x, y, z0 + (z1 - z0) * s_))
        parts.append(tube(f"S{i}", path, 0.12, mat, res=10))
        parts.append(arrow_head(f"H{i}", (0.34, z1), (1.0, 0.0), 0.42, 0.33, 0.2, mat, y=y))
        parts.append(shine(f"Shine{i}", [(-0.86 + 0.06 * k, y - 0.13, z0 + 0.05) for k in range(5)], 0.022))
    return finish(parts, tilt=8)


def icon_check():
    """Готово: зеленый значок с куполом и белой галочкой."""
    _prep()
    parts = badge("Badge", (0.36, 0.84, 0.36), (0.14, 0.52, 0.20))
    tick = band([(-0.4, 0.02), (-0.12, -0.26), (0.42, 0.32)], 0.11, 0.11, tail_round=True)
    parts.append(symbol_slab("Tick", round_corners(tick, 0.03, 3)))
    return finish(parts, tilt=8)


def icon_plus():
    """Плюс: тот же значок, белый крест."""
    _prep()
    parts = badge("Badge", (0.36, 0.84, 0.36), (0.14, 0.52, 0.20))
    parts += cross_bars("Cross", 0.13, 0.46)
    return finish(parts, tilt=8)


def cross_bars(name, w, L, y=-0.38):
    """Белый крест из двух скругленных брусков (выпуклые контуры: без швов на вогнутых углах)."""
    return [symbol_slab(name + "H", rounded_rect(2 * L, 2 * w, w * 0.9, 8), y=y),
            symbol_slab(name + "V", rounded_rect(2 * w, 2 * L, w * 0.9, 8), y=y - 0.002)]


def plus_badge2(name, r, loc):
    parts = badge(name, (0.36, 0.84, 0.36), (0.14, 0.52, 0.20))
    parts += cross_bars(name + "Cross", 0.14, 0.48)
    for p in parts:
        p.matrix_world = Matrix.Translation(loc) @ Matrix.Scale(r, 4) @ p.matrix_world
        M.apply_transform(p)
    return parts


def icon_shelf():
    """Дополнительная полка: деревянная полочка как в игре (рамка, задник) и зеленый плюс."""
    _prep()
    import models_match3 as M3
    frame = M3.wood("Frame", (0.80, 0.48, 0.24), axis="x", rough=0.4, coat=0.5, grain=0.3)
    side = M3.wood("Side", (0.74, 0.44, 0.22), axis="z", rough=0.4, coat=0.5, grain=0.3)
    inside = M3.wood("Inside", (0.46, 0.26, 0.12), axis="x", rough=0.6, coat=0.1, grain=0.25)
    W, H, D, T = 1.7, 0.95, 0.6, 0.13
    parts = [M3.rbox("Bottom", -W / 2, W / 2, -D / 2, D / 2, 0.0, T, frame, 0.04),
             M3.rbox("Top", -W / 2, W / 2, -D / 2, D / 2, H - T, H, frame, 0.04),
             M3.rbox("SideL", -W / 2, -W / 2 + T, -D / 2, D / 2, 0.0, H, side, 0.04),
             M3.rbox("SideR", W / 2 - T, W / 2, -D / 2, D / 2, 0.0, H, side, 0.04),
             M3.rbox("Back", -W / 2 + T, W / 2 - T, D / 2 - 0.06, D / 2, T, H - T, inside, 0.0)]
    # три фишки-продукта внутри, чтобы читалось как полка игры
    for k, (x, col) in enumerate(((-0.42, (0.95, 0.24, 0.24)), (0.0, (1.0, 0.76, 0.18)), (0.42, (0.40, 0.78, 0.30)))):
        b = M.sphere(f"Item{k}", 0.2, 32, 16)
        b.scale = (1.0, 1.0, 1.05)
        b.location = (x, 0.0, T + 0.2)
        M.apply_transform(b)
        parts.append(M.assign(M.smooth(b), candy(f"ItemM{k}", col, rough=0.16)))
    parts = M.rotate_all(parts, (0, 0, math.radians(14)))
    parts += plus_badge2("Plus", 0.44, (0.66, -0.45, 0.92))
    return finish(parts, tilt=10)


def icon_lock():
    """Замок: золотой корпус-подушка, скважина с ободком, заклепки, толстая стальная дужка."""
    _prep()
    g = bright_gold("LockGold")
    body = slab("Body", ccw(rounded_rect(1.36, 1.04, 0.3, 12)), 0.56, 0.18, g, segs=8)
    steel = C.world_mat("Steel", [(0.0, (0.46, 0.50, 0.60)), (0.5, (0.78, 0.82, 0.90)), (1.0, (0.98, 0.99, 1.0))],
                        rough=0.16, metal=0.8, coat=0.6)
    sh = tube("Shackle", [(-0.36, 0.0, 0.3), (-0.36, 0.0, 0.62)] + arc(0, 0.62, 0.36, 180, 0, 32)[1:] + [(0.36, 0.0, 0.3)],
              0.11, steel, res=10)
    for p in (body,):
        p.location.z -= 0.2
        M.apply_transform(p)
    dark = candy("Hole", (0.22, 0.12, 0.04), rough=0.5, coat=0.2)
    key = [(0.14 * math.cos(math.radians(a)), 0.05 + 0.14 * math.sin(math.radians(a))) for a in range(-60, 241, 10)]
    key += [(-0.07, -0.26), (0.07, -0.26)]
    hole = slab("Key", ccw(round_corners(key, 0.03, 3)), 0.06, 0.02, dark, segs=3, y=-0.29)
    hole.location.z -= 0.22
    M.apply_transform(hole)
    rim = M.torus("KeyRim", 0.21, 0.035, 64, 12)
    rim.rotation_euler = (math.radians(90), 0, 0)
    rim.location = (0, -0.29, -0.17)
    M.apply_transform(rim)
    M.assign(M.smooth(rim), g)
    parts = [body, sh, hole, rim]
    for k, (x, z) in enumerate(((-0.5, 0.18), (0.5, 0.18), (-0.5, -0.56), (0.5, -0.56))):
        rv = M.sphere(f"Rivet{k}", 0.06, 24, 12)
        rv.scale = (1, 0.6, 1)
        rv.location = (x, -0.27, z)
        M.apply_transform(rv)
        parts.append(M.assign(M.smooth(rv), g))
    parts.append(shine("Shine", [(-0.5 + 0.06 * k, -0.3, 0.12 + 0.01 * k) for k in range(6)], 0.03))
    return finish(parts, tilt=8)


def icon_gear():
    """Настройки: стальная шестеренка со скругленными зубцами, канавка, ступица с золотой гайкой."""
    _prep()
    teeth = 9
    pts = []
    for i in range(540):
        a = 2 * math.pi * i / 540
        ph = (a * teeth / (2 * math.pi)) % 1.0
        d = min(abs(ph - 0.5), 0.5)
        k = 1.0 - min(1.0, max(0.0, (d - 0.16) / 0.12))
        k = k * k * (3 - 2 * k)
        r = 0.76 + 0.24 * k
        pts.append((r * math.cos(a), r * math.sin(a)))
    steel = C.world_mat("GearSteel", [(0.0, (0.36, 0.42, 0.56)), (0.5, (0.64, 0.72, 0.86)), (1.0, (0.92, 0.95, 1.0))],
                        rough=0.22, metal=0.6, coat=0.6)
    g = slab("Gear", ccw(pts), 0.36, 0.07, steel, segs=5)
    groove = M.torus("Groove", 0.56, 0.045, 96, 12)
    groove.rotation_euler = (math.radians(90), 0, 0)
    groove.location = (0, -0.17, 0)
    M.apply_transform(groove)
    M.assign(M.smooth(groove), C.world_mat("GrooveM", [(0.0, (0.22, 0.26, 0.36)), (1.0, (0.46, 0.52, 0.66))], rough=0.3,
                                          metal=0.5, coat=0.3))
    hub = disc("Hub", 0.4, 0.22, steel, y=-0.16, bev=0.08)
    nut = M.lathe("Nut", [(0.0, 0.0), (0.2, 0.0), (0.2, 0.12), (0.0, 0.12)], 6)
    M.bevel(nut, 0.025, 3, 30)
    M.smooth(nut, 30)
    nut.rotation_euler = (math.radians(90), 0, 0)
    nut.location = (0, -0.26, 0)
    M.apply_transform(nut)
    M.assign(nut, bright_gold("NutGold"))
    hole = M.cylinder("NutHole", 0.08, 0.06, 32)
    hole.rotation_euler = (math.radians(90), 0, 0)
    hole.location = (0, -0.385, 0)
    M.apply_transform(hole)
    M.assign(M.smooth(hole), candy("NutHoleM", (0.30, 0.20, 0.08), rough=0.4))
    hl = shine("Shine", arc(0, 0, 0.82, 110, 150, 14, y=-0.2), 0.03)
    return finish([g, groove, hub, nut, hole, hl], tilt=8)


def map_mat(name):
    """Карта: зеленая суша с пятнами, извилистая река, пунктир маршрута; координаты мира (сгибы непрерывны)."""
    import models_remodel as RM
    sh = RM.Sh(name, rough=0.45, coat=0.3)
    geo = sh.nodes.new("ShaderNodeNewGeometry")
    x, y, z = sh.xyz(geo.outputs["Position"])
    land = sh.mix(sh.remap(sh.noise(geo.outputs["Position"], 2.5, 3.0), 0.45, 0.6), (0.50, 0.82, 0.36), (0.66, 0.90, 0.44))
    river_c = sh.math("ADD", sh.math("MULTIPLY", sh.math("SINE", sh.math("MULTIPLY", x, 3.2)), 0.22), 0.18)
    dr = sh.math("ABSOLUTE", sh.math("SUBTRACT", z, river_c))
    col = sh.mix(sh.remap(dr, 0.13, 0.11), land, (0.36, 0.66, 0.98))
    col = sh.mix(sh.math("MULTIPLY", sh.remap(dr, 0.16, 0.13), sh.remap(dr, 0.11, 0.13)), col, (0.96, 0.90, 0.66))
    # пунктир маршрута: синусоида, точки по x
    path_c = sh.math("SUBTRACT", sh.math("MULTIPLY", sh.math("SINE", sh.math("ADD", sh.math("MULTIPLY", x, 2.4), 2.0)), 0.18), 0.32)
    dp = sh.math("ABSOLUTE", sh.math("SUBTRACT", z, path_c))
    dash = sh.math("GREATER_THAN", sh.math("PINGPONG", sh.math("MULTIPLY", x, 7.0), 0.5), 0.22)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(dp, 0.035, 0.025), dash), col, (0.92, 0.22, 0.20))
    # деревья-точки
    tr = sh.voronoi(geo.outputs["Position"], 4.0, out="Distance")
    col = sh.mix(sh.math("MULTIPLY", sh.remap(tr, 0.09, 0.07), sh.remap(dr, 0.2, 0.25)), col, (0.24, 0.58, 0.24))
    sh.color(col)
    return sh.mat


def icon_map():
    """Карта: сложенная гармошкой бумага с рекой и пунктиром, красная булавка."""
    _prep()
    paper = candy("Paper", (0.98, 0.94, 0.82), rough=0.6, coat=0.1)
    mm = map_mat("MapPrint")
    parts = []
    W = 0.6
    for i, (x, a) in enumerate(((-W, 16), (0.0, -16), (W, 16))):
        p = M.box_mesh(f"Panel{i}", W + 0.004, 0.05, 1.36, -0.68)
        M.bevel(p, 0.012, 2, 30)
        p.rotation_euler = (0, 0, math.radians(a))
        p.location = (x, 0.0, 0)
        M.apply_transform(p)
        M.assign(p, paper)
        p.data.materials.append(mm)
        for poly in p.data.polygons:
            if poly.normal.y < -0.8:
                poly.material_index = 1
        parts.append(p)
    red = candy("PinRed", (0.95, 0.20, 0.24), rough=0.12)
    pin = M.sphere("Pin", 0.26, 48, 24)
    pin.location = (0.34, -0.42, 0.5)
    M.apply_transform(pin)
    M.assign(M.smooth(pin), red)
    tip = cone_head("PinTip", (0.34, -0.36, 0.02), (0, 0.05, -1), 0.18, 0.42, red)
    dot = M.sphere("PinDot", 0.1, 24, 12)
    dot.location = (0.34, -0.66, 0.53)
    M.apply_transform(dot)
    M.assign(M.smooth(dot), white("PinW"))
    hl = shine("Shine", arc(0.34, 0.5, 0.2, 110, 160, 10, y=-0.6), 0.025)
    return finish(parts + [pin, tip, dot, hl], tilt=6)


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
