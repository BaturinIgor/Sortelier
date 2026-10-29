"""Фон кухни, версия 2: плитка из настоящей геометрии, ручные предметы на полке и столешнице, свет.

Вызывается из environment.py (render_background). Камера, кадр и раскладка прежние: рейлинг z=4.35, полка z=3.05,
столешница z=-3.55, поэтому интерфейс поверх фона не сдвигается. Все цвета здесь в sRGB, как в models.py;
цвета STYLES из environment.py линейные и переводятся через srgb().

Предметы собираются в начале координат (низ на z=0, лицом к камере по -Y) и ставятся put(): меняется только
matrix_world, поэтому процедурные текстуры в координатах объекта не плывут.
"""
import math
import random

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

import models as M
import icons as I
import models_events as EV
import models_remodel as RM
import models_match3 as M3

Sh = RM.Sh


# MARK: - Помощники

def srgb(c):
    """Линейный цвет -> sRGB (палитры STYLES линейные)."""
    return tuple(1.055 * v ** (1 / 2.4) - 0.055 if v > 0.0031308 else 12.92 * v for v in c)


def mix_c(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def put(objs, x=0.0, y=0.0, z=0.0, rz=0.0, s=1.0, rx=0.0, ry=0.0):
    """Ставит группу предметов, собранную в начале координат."""
    m = Matrix.Translation((x, y, z)) @ Euler((rx, ry, rz), "XYZ").to_matrix().to_4x4() @ Matrix.Scale(s, 4)
    for o in objs:
        o.matrix_world = m @ o.matrix_world
    bpy.context.view_layer.update()
    return objs


def rbox(name, sx, sy, sz, mat, bev=0.02, segs=3, loc=(0, 0, 0)):
    """Брусок с центром основания в loc (низ на loc.z)."""
    ob = M.box_mesh(name, sx, sy, sz, 0.0)
    ob.location = loc
    M.apply_transform(ob)
    if bev:
        M.bevel(ob, bev, segs, 30)
    M.smooth(ob, 30)
    return M.assign(ob, mat)


def lathe_s(name, ctrl, segs=64, n=5):
    """Тело вращения по плавной кривой через (радиус, высота); концы на оси."""
    pts = [(max(0.0, r), z) for r, _, z in EV.spline([(r, 0.0, z) for r, z in ctrl], n)]
    return M.lathe(name, [(0.0, ctrl[0][1])] + pts + [(0.0, ctrl[-1][1])], segs)


def shell(name, ctrl, segs=64, n=5):
    """Открытый сосуд: профиль снаружи вверх и внутри вниз одной кривой (кромка скруглена сплайном)."""
    pts = [(max(0.0, r), z) for r, _, z in EV.spline([(r, 0.0, z) for r, z in ctrl], n)]
    return M.lathe(name, [(0.0, ctrl[0][1])] + pts + [(0.0, ctrl[-1][1])], segs)


def faces_mat(ob, rules):
    """Добавляет материалы граням по условию rules = [(fn(center, normal), mat)]."""
    for _, m in rules:
        ob.data.materials.append(m)
    for p in ob.data.polygons:
        for k, (cond, _) in enumerate(rules):
            if cond(p.center, p.normal):
                p.material_index = k + 1
                break
    return ob


# MARK: - Материалы

def ceramic(name, color, rough=0.16, coat=0.6, mottle=0.06, scale=7.0):
    """Глазурь: верх светлее (как toy), легкие пятна глазури и неровный глянец."""
    mat = I.toy(name, color, rough=rough, coat=coat)
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    b = nodes["Principled BSDF"]
    tc = nodes.new("ShaderNodeTexCoord")
    nz = nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = scale
    nz.inputs["Detail"].default_value = 3.0
    links.new(tc.outputs["Object"], nz.inputs["Vector"])
    if mottle:
        src = b.inputs["Base Color"].links[0].from_socket
        hsv = nodes.new("ShaderNodeHueSaturation")
        mr = nodes.new("ShaderNodeMapRange")
        mr.inputs[1].default_value, mr.inputs[2].default_value = 0.3, 0.7
        mr.inputs[3].default_value, mr.inputs[4].default_value = 1 - mottle, 1 + mottle
        links.new(nz.outputs["Fac"], mr.inputs[0])
        links.new(mr.outputs[0], hsv.inputs["Value"])
        links.new(src, hsv.inputs["Color"])
        links.new(hsv.outputs["Color"], b.inputs["Base Color"])
    mr2 = nodes.new("ShaderNodeMapRange")
    mr2.inputs[1].default_value, mr2.inputs[2].default_value = 0.35, 0.65
    mr2.inputs[3].default_value, mr2.inputs[4].default_value = rough * 0.6, rough * 1.6
    links.new(nz.outputs["Fac"], mr2.inputs[0])
    links.new(mr2.outputs[0], b.inputs["Roughness"])
    return mat


def metal(name, color, rough=0.25, hammered=0.0, brushed=False):
    """Металл: медь, латунь, сталь. hammered - кованые лунки (вороной), brushed - шлифовка."""
    sh = Sh(name, rough=rough, metal=1.0, coat=0.25, coat_rough=0.08)
    sh.color(color)
    sh.rough_vary(rough * 0.7, rough * 1.35, scale=9.0)
    if hammered:
        sh.bump(sh.voronoi(None, 26.0, out="Distance"), strength=hammered, distance=0.01)
    if brushed:
        sh.bump(sh.noise(sh.mapping(None, scale=(1.0, 1.0, 60.0)), 40.0, 2.0), strength=0.04, distance=0.005)
    return sh.mat


def wood_sh(name, light, dark, axis="x", scale=1.0, rough=0.45, coat=0.12, seed=0.0, rings=3.0, soft=0.0):
    """Дерево: полосы волокон с искажением, мелкие поры, глянец неровный. Цвета sRGB. soft - мягче прожилки."""
    dark = mix_c(dark, light, soft)
    sh = Sh(name, rough=rough, coat=coat, coat_rough=0.25)
    st = {"x": (0.08, 1.0, 1.0), "y": (1.0, 0.08, 1.0), "z": (1.0, 1.0, 0.08)}[axis]
    p = sh.mapping(None, loc=(seed, seed * 0.7, seed * 1.3), scale=tuple(v * scale for v in st))
    wave = sh.nodes.new("ShaderNodeTexWave")
    wave.wave_type = "RINGS"
    wave.rings_direction = "SPHERICAL"
    wave.inputs["Scale"].default_value = rings
    wave.inputs["Distortion"].default_value = 6.0
    wave.inputs["Detail"].default_value = 3.0
    wave.inputs["Detail Scale"].default_value = 1.5
    sh.links.new(p, wave.inputs["Vector"])
    g = wave.outputs["Fac"]
    fine = sh.noise(sh.mapping(None, scale=tuple(v * scale * 6 for v in st)), 30.0, 2.0)
    tone = sh.noise(None, 2.0 * scale, 3.0)
    base = sh.ramp(g, [(0.0, dark), (0.22, mix_c(dark, light, 0.7)), (0.6, mix_c(dark, light, 0.9)), (1.0, light)])
    base = sh.mix(sh.remap(fine, 0.45, 0.75, 0.0, 0.35), base, mix_c(dark, (0, 0, 0), 0.15), "MULTIPLY")
    base = sh.mix(sh.remap(tone, 0.3, 0.7, 0.0, 0.25), base, light, "MIX")
    sh.color(base)
    sh.set("Roughness", sh.remap(g, 0.2, 0.9, rough * 1.2, rough * 0.8))
    sh.bump(g, strength=0.06, distance=0.01)
    sh.bump(fine, strength=0.05, distance=0.004)
    return sh.mat


def paint_sh(name, color, rough=0.42, coat=0.15):
    """Крашеное дерево шкафчиков: едва заметные мазки кисти по вертикали и неровный глянец."""
    sh = Sh(name, rough=rough, coat=coat, coat_rough=0.2)
    v = sh.noise(None, 1.2, 2.0)
    base = sh.mix(sh.remap(v, 0.3, 0.7, 0.0, 1.0), I.shade(color, 0.985), tuple(min(1.0, c * 1.015 + 0.005) for c in color))
    sh.color(base)
    sh.rough_vary(rough * 0.9, rough * 1.1, scale=2.0)
    brush = sh.noise(sh.mapping(None, scale=(14.0, 14.0, 0.6)), 6.0, 3.0)
    sh.bump(brush, strength=0.025, distance=0.004)
    return sh.mat


def glass_mat(name, tint=(0.93, 0.97, 1.0), edge=(0.78, 0.88, 0.96), center=0.04, rim=0.8):
    return M3.glass(name, tint=tint, edge=edge, center=center, rim=rim)


def glow_mat(name, color, strength=6.0):
    return M3.glow_mat(name, color, strength)


def fill_mat(name, kind):
    """Содержимое банок: фасоль, макароны, чечевица, рис, кофе, конфеты, печенье."""
    spec = {
        "beans": ((0.62, 0.14, 0.10), (0.36, 0.07, 0.05), 46.0),
        "pasta": ((1.0, 0.86, 0.42), (0.96, 0.70, 0.28), 16.0),
        "lentils": ((0.96, 0.50, 0.18), (0.78, 0.32, 0.10), 70.0),
        "rice": ((0.98, 0.97, 0.92), (0.86, 0.84, 0.78), 90.0),
        "coffee": ((0.36, 0.20, 0.11), (0.18, 0.09, 0.05), 55.0),
        "candy": ((0.98, 0.40, 0.55), (0.36, 0.70, 0.98), 36.0),
        "cookies": ((0.86, 0.60, 0.32), (0.60, 0.36, 0.16), 18.0),
        "sugar": ((1.0, 1.0, 0.98), (0.90, 0.90, 0.88), 140.0),
        "flour": ((1.0, 0.98, 0.94), (0.92, 0.89, 0.84), 160.0),
        "tea": ((0.42, 0.52, 0.22), (0.22, 0.30, 0.10), 80.0),
    }[kind]
    hi, lo, sc = spec
    sh = Sh(name, rough=0.4, coat=0.3)
    cell = sh.voronoi(None, sc, out="Distance")
    rnd = sh.voronoi(None, sc, out="Color")
    if kind == "candy":
        col = sh.ramp(sh.math("MULTIPLY", sh.xyz(rnd)[0], 1.0),
                      [(0.0, (0.98, 0.36, 0.50)), (0.33, (1.0, 0.80, 0.20)), (0.66, (0.36, 0.72, 0.98)),
                       (1.0, (0.50, 0.85, 0.40))], "CONSTANT")
    else:
        col = sh.mix(sh.xyz(rnd)[0], lo, hi)
    col = sh.mix(sh.remap(cell, 0.3, 0.5, 0.0, 0.55), col, I.shade(lo, 0.55), "MIX")
    sh.color(col)
    sh.bump(sh.remap(cell, 0.0, 0.5, 1.0, 0.0), strength=0.6, distance=0.01)
    return sh.mat


# MARK: - Стена из плитки

def tile_wall(st, x0=-2.75, x1=2.75, z0=-3.9, z1=5.6, y_face=0.57, seed=7):
    """Плитка отдельной геометрией: скругленные края, легкий "подушечный" выпуклый лицевой край,
    каждая плитка чуть повернута (блики гуляют, как у ручной плитки). Атрибут tile: случайные числа и класс."""
    lay = st.get("layout", "subway")
    tw, th = {"subway": (0.455, 0.227), "square": (0.36, 0.36), "mosaic": (0.29, 0.29), "cotto": (0.42, 0.42),
              "checker": (0.30, 0.30), "brick": (0.5, 0.2)}[lay]
    gap = st.get("gap", 0.016)
    depth = 0.05
    pillow = st.get("pillow", 0.006)
    tilt = math.radians(st.get("tilt", 1.0))
    rnd = random.Random(seed)
    bm = bmesh.new()
    layer = bm.verts.layers.float_color.new("tile")
    rows = int((z1 - z0) / th) + 1
    cols = int((x1 - x0) / tw) + 2
    band = st.get("band")  # (z_lo, z_hi) полоса другого класса (шахматка закусочной)
    # шаблон плитки: куб, все грани поделены 3x3 (для выпуклой лицевой стороны)
    tb = bmesh.new()
    bmesh.ops.create_cube(tb, size=1.0)
    bmesh.ops.subdivide_edges(tb, edges=tb.edges[:], cuts=2, use_grid_fill=True)
    tb.verts.index_update()
    tv = [tuple(v.co) for v in tb.verts]
    tf = [[v.index for v in f.verts] for f in tb.faces]
    tb.free()
    for r in range(rows):
        zc = z0 + (r + 0.5) * th
        off = (tw / 2 if (r % 2 and lay in ("subway", "brick")) else 0.0)
        for c in range(-1, cols):
            xc = x0 + (c + 0.5) * tw + off
            if xc < x0 - tw or xc > x1 + tw:
                continue
            klass = (r + c) % 2 if lay == "checker" else 2
            if band:
                inside = any(lo <= zc <= hi for lo, hi in band)
                klass = ((r + c) % 2) if inside else 2
                if not inside and any(lo <= zc <= hi for lo, hi in st.get("stripe", ())):
                    klass = 3
            sx, sz = tw - gap, th - gap
            m = (Matrix.Translation((xc, y_face + depth / 2 + rnd.uniform(-0.003, 0.003), zc))
                 @ Euler((rnd.uniform(-tilt, tilt), rnd.uniform(-tilt * 0.4, tilt * 0.4), rnd.uniform(-tilt, tilt)))
                 .to_matrix().to_4x4())
            col = (rnd.random(), rnd.random(), float(klass) / 3.0, rnd.random())
            vs = []
            for lx, ly, lz in tv:
                # лицевая грань чуть выпуклая: середина ближе к камере
                if ly < -0.49:
                    ly -= pillow / depth * (1 - (2 * lx) ** 2) * (1 - (2 * lz) ** 2)
                v = bm.verts.new(m @ Vector((lx * sx, ly * depth, lz * sz)))
                v[layer] = col
                vs.append(v)
            for f in tf:
                bm.faces.new([vs[i] for i in f])
    me = bpy.data.meshes.new("Tiles")
    bm.to_mesh(me)
    bm.free()
    ob = M.link(bpy.data.objects.new("Tiles", me))
    mod = ob.modifiers.new("bev", "BEVEL")
    mod.width = st.get("bevel", 0.022)
    mod.segments = 4
    mod.limit_method = "ANGLE"
    mod.angle_limit = math.radians(30)
    mod.profile = 0.6
    mod.harden_normals = False
    M.bake(ob)
    M.smooth(ob)
    M.assign(ob, tile_mat(st))
    grout = rbox("Grout", x1 - x0 + 1.0, 0.04, z1 - z0 + 1.0, grout_mat(st), bev=0.0,
                 loc=((x0 + x1) / 2, y_face + depth * 0.62, z0 - 0.5))
    return [ob, grout]


def tile_mat(st):
    """Глазурь плитки: цвет по плитке из атрибута, светлее по скругленному краю, пятна глазури, неровный глянец."""
    c1, c2 = st["tiles"][0], st["tiles"][1]
    sh = Sh("TileGlaze", rough=st.get("tile_rough", 0.12), coat=st.get("tile_coat", 0.35), coat_rough=0.06)
    at = sh.nodes.new("ShaderNodeAttribute")
    at.attribute_type = "GEOMETRY"
    at.attribute_name = "tile"
    r1, r2, klass = sh.xyz(at.outputs["Vector"])
    a4 = at.outputs["Alpha"]
    if st.get("layout") == "checker" or st.get("band"):
        # класс 0 и 1 - шахматка, 2 - основное поле
        cA = (*st["check"][0], 1) if st.get("check") else (*c1, 1)
        cB = (*st["check"][1], 1) if st.get("check") else (*c2, 1)
        chk = sh.mix(sh.math("GREATER_THAN", klass, 0.17), cA, cB)
        fieldc = sh.mix(r1, (*c1, 1), (*c2, 1))
        base = sh.mix(sh.math("GREATER_THAN", klass, 0.5), chk, fieldc)
        if st.get("stripe_col"):
            base = sh.mix(sh.math("GREATER_THAN", klass, 0.83), base, (*st["stripe_col"], 1))
    else:
        base = sh.mix(r1, (*c1, 1), (*c2, 1))
        if st.get("accent"):
            # редкие плитки другого оттенка (ручная кладка)
            acc = sh.math("GREATER_THAN", a4, 1.0 - st["accent"][1])
            base = sh.mix(acc, base, (*st["accent"][0], 1))
    hsv = sh.nodes.new("ShaderNodeHueSaturation")
    vj = st.get("val_jitter", 0.10)
    sh.links.new(base, hsv.inputs["Color"])
    sh._in(hsv.inputs["Hue"], sh.math("ADD", sh.math("MULTIPLY", sh.math("SUBTRACT", r2, 0.5), st.get("hue_jitter", 0.02)), 0.5))
    sh._in(hsv.inputs["Saturation"], sh.math("ADD", sh.math("MULTIPLY", sh.math("SUBTRACT", a4, 0.5), 0.12), 1.0))
    sh._in(hsv.inputs["Value"], sh.math("ADD", sh.math("MULTIPLY", sh.math("SUBTRACT", r2, 0.5), vj), 1.0))
    col = hsv.outputs["Color"]
    # пятна глазури внутри плитки
    geo = sh.nodes.new("ShaderNodeNewGeometry")
    mott = sh.noise(geo.outputs["Position"], st.get("mottle_scale", 4.5), 4.0, 0.6)
    col = sh.mix(sh.remap(mott, 0.3, 0.75, 0.0, st.get("mottle", 0.22)), col, I.shade((1, 1, 1), 1.0), "OVERLAY")
    # край: глазурь тоньше - светлее и чуть прозрачнее по цвету
    facing = sh.vmath("DOT_PRODUCT", geo.outputs["Normal"], (0.0, -1.0, 0.0))
    edge = sh.remap(facing, 0.97, 0.80, 0.0, 1.0)
    edge_col = st.get("edge_col")
    if edge_col:
        col = sh.mix(sh.math("MULTIPLY", edge, st.get("edge", 0.55)), col, (*edge_col, 1))
    else:
        col = sh.mix(sh.math("MULTIPLY", edge, st.get("edge", 0.45)), col, I.shade((1, 1, 1), 1.0), "SCREEN")
    sh.color(col)
    rough = st.get("tile_rough", 0.12)
    sh.set("Roughness", sh.remap(sh.noise(geo.outputs["Position"], 7.0, 3.0), 0.3, 0.7, rough * 0.6, rough * 1.8))
    # "апельсиновая корка" глазури
    sh.bump(sh.noise(geo.outputs["Position"], 70.0, 2.0), strength=0.03, distance=0.003)
    return sh.mat


def grout_mat(st):
    g = st.get("grout") or st["tiles"][2]
    sh = Sh("Grout", rough=0.9)
    n = sh.noise(None, 40.0, 3.0)
    sh.color(sh.mix(sh.remap(n, 0.3, 0.7, 0.0, 1.0), (*[v * 0.82 for v in g], 1), (*g, 1)))
    sh.bump(sh.noise(None, 160.0, 2.0), strength=0.3, distance=0.004)
    return sh.mat


# MARK: - Мебель

LEDGE_Z = 3.05      # середина толщины полки (верх 3.11)
LEDGE_TOP = 3.11
RAIL_Z = 4.35
COUNTER_Z = -3.55   # середина столешницы (верх -3.47)
COUNTER_TOP = -3.47
WALL_Y = 0.57


def make_bracket(name, x, mat, iron=False):
    """Кронштейн: строим профиль прямо в координатах (y, z) и выдавливаем по X."""
    y0, y1, ztop, zlow = WALL_Y, 0.10, LEDGE_Z - 0.06, LEDGE_Z - 0.48
    w = 0.07 if not iron else 0.04
    prof = [(y0, ztop), (y1, ztop), (y1, ztop - 0.045)]
    n = 14
    for k in range(1, n + 1):
        a = math.radians(90 * k / n)
        prof.append((y1 + (y0 - y1) * (1 - math.cos(a)), ztop - 0.045 - (ztop - 0.045 - zlow) * math.sin(a)))
    if iron:
        inner = []
        for k in range(n, 0, -1):
            a = math.radians(90 * k / n)
            inner.append((y1 + 0.05 + (y0 - 0.04 - y1 - 0.05) * (1 - math.cos(a)),
                          ztop - 0.08 - (ztop - 0.08 - zlow - 0.07) * math.sin(a)))
        prof = prof + [(y0 - 0.04, zlow + 0.07)] + inner[1:] + [(y1 + 0.05, ztop - 0.08), (y0, ztop - 0.08)]
        prof = prof[:]
    verts = [(x - w / 2, y, z) for y, z in prof] + [(x + w / 2, y, z) for y, z in prof]
    m = len(prof)
    faces = [tuple(range(m)), tuple(range(2 * m - 1, m - 1, -1))]
    for i in range(m):
        j = (i + 1) % m
        faces.append((i, m + i, m + j, j))
    ob = M.from_data(name, verts, faces)
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(ob.data)
    bm.free()
    M.bevel(ob, 0.012 if not iron else 0.008, 3, 30)
    M.smooth(ob, 30)
    return M.assign(ob, mat)


def shelf_ledge(st, world_w, wood):
    parts = [rbox("Ledge", world_w + 1, 0.64, 0.12, wood, bev=0.03, segs=4, loc=(0, WALL_Y - 0.32, LEDGE_Z - 0.06))]
    iron = st.get("bracket") == "iron"
    bmat = metal("BracketIron", (0.10, 0.09, 0.09), rough=0.45) if iron else wood
    for k, x in enumerate((-world_w / 2 + 0.45, world_w / 2 - 0.45)):
        parts.append(make_bracket(f"Bracket{k}", x, bmat, iron))
    return parts


def s_hook(name, x, mat, z_rod=RAIL_Z, y_rod=0.45, drop=0.12):
    """S-крючок на рейлинге: верхняя дуга вокруг трубки, нижняя открыта к камере."""
    pts = []
    for k in range(13):
        a = math.radians(-40 + 220 * k / 12)
        pts.append((x, y_rod + 0.042 * math.cos(a), z_rod + 0.042 * math.sin(a)))
    pts.reverse()
    zb = z_rod - drop
    pts += [(x, y_rod - 0.0, z_rod - 0.05), (x, y_rod, zb + 0.03)]
    for k in range(10):
        a = math.radians(180 + 200 * k / 9)
        pts.append((x, y_rod - 0.03 + 0.03 * math.cos(a) * -1, zb + 0.03 * math.sin(a)))
    return M.assign(EV.sweep(name, pts, 0.0065, segs=10), mat)


def rail(st, world_w, metal_mat):
    rod = M.cylinder("Rail", 0.024, world_w + 1, 32)
    rod.rotation_euler = (0, math.radians(90), 0)
    rod.location = (0, 0.45, RAIL_Z)
    M.apply_transform(rod)
    parts = [M.assign(M.smooth(rod), metal_mat)]
    for k, x in enumerate((-1.75, 1.75)):
        post = M.cylinder(f"RailPost{k}", 0.016, 0.14, 16)
        post.rotation_euler = (math.radians(90), 0, 0)
        post.location = (x, 0.51, RAIL_Z)
        M.apply_transform(post)
        parts.append(M.assign(M.smooth(post), metal_mat))
        fl = M.cylinder(f"RailFlange{k}", 0.045, 0.025, 32)
        fl.rotation_euler = (math.radians(90), 0, 0)
        fl.location = (x, WALL_Y - 0.012, RAIL_Z)
        M.apply_transform(fl)
        M.bevel(fl, 0.008, 2, 30)
        parts.append(M.assign(M.smooth(fl, 30), metal_mat))
        ring = M.torus(f"RailRing{k}", 0.026, 0.008, 24, 8)
        ring.rotation_euler = (0, math.radians(90), 0)
        ring.location = (x, 0.45, RAIL_Z)
        M.apply_transform(ring)
        parts.append(M.assign(M.smooth(ring), metal_mat))
    return parts


def shaker_door(name, x, z0, w, h, paint, y_front=-0.5, frame=0.12, lattice=None):
    """Дверца в стиле шейкер: утопленная филенка и рамка со скругленными ребрами.
    lattice - материал бумаги: дверца-сёдзи с решеткой из реек."""
    parts = [rbox(name, w, 0.04, h, lattice or paint, bev=0.012, loc=(x, y_front - 0.02, z0))]
    t = 0.028
    yf = y_front - 0.04 - t / 2 + 0.002
    if lattice:
        iw, ih = w - 2 * frame, h - 2 * frame
        nx = max(2, round(iw / 0.2))
        nz = max(1, round(ih / 0.32))
        for i in range(1, nx):
            parts.append(rbox(f"{name}V{i}", 0.022, t * 0.7, ih, paint, bev=0.006, loc=(x - iw / 2 + iw * i / nx, yf + 0.004, z0 + frame)))
        for j in range(1, nz):
            parts.append(rbox(f"{name}H{j}", iw, t * 0.6, 0.022, paint, bev=0.006, loc=(x, yf + 0.006, z0 + frame + ih * j / nz - 0.011)))
    for k, (cx, cz, sx, sz) in enumerate(((x - w / 2 + frame / 2, z0, frame, h), (x + w / 2 - frame / 2, z0, frame, h),
                                          (x, z0, w - 2 * frame + 0.01, frame),
                                          (x, z0 + h - frame, w - 2 * frame + 0.01, frame))):
        parts.append(rbox(f"{name}F{k}", sx, t, sz, paint, bev=0.01, segs=3, loc=(cx, yf, cz)))
    return parts


def knob(name, x, z, mat, y_front=-0.565, r=0.042):
    k = lathe_s(name, [(0.012, 0.0), (0.018, 0.02), (0.016, 0.04), (r, 0.065), (r * 0.95, 0.085), (0.0, 0.095)], 32, 4)
    k.rotation_euler = (math.radians(90), 0, 0)
    k.location = (x, y_front, z)
    M.apply_transform(k)
    return M.assign(M.smooth(k), mat)


def bar_pull(name, x, z, length, mat, y_front=-0.565, vertical=False):
    r = 0.016
    pts = []
    for k in range(17):
        t = k / 16
        u = -length / 2 + length * t
        d = 0.06 * min(1.0, min(t, 1 - t) * 8) ** 0.6
        pts.append((x + (0 if vertical else u), y_front - d, z + (u if vertical else 0)))
    return M.assign(EV.sweep(name, pts, r, segs=16), mat)


def cabinets(st, world_w, paint, metal_mat, top_mat, edge_mat=None):
    parts = []
    W = world_w + 1
    top = rbox("Countertop", W, 1.2, 0.16, top_mat, bev=0.035, segs=4, loc=(0, -0.2, COUNTER_Z - 0.08))
    parts.append(top)
    if edge_mat:
        # хромированная кромка столешницы закусочной
        e = rbox("CounterEdge", W, 0.03, 0.12, edge_mat, bev=0.01, loc=(0, -0.8, COUNTER_Z - 0.06))
        parts.append(e)
        for k, dz in enumerate((-0.035, 0.0, 0.035)):
            g = M.cylinder(f"Groove{k}", 0.006, W, 12)
            g.rotation_euler = (0, math.radians(90), 0)
            g.location = (0, -0.818, COUNTER_Z + dz)
            M.apply_transform(g)
            parts.append(M.assign(M.smooth(g), edge_mat))
    body = rbox("Carcass", W, 1.0, 1.95, paint, bev=0.02, loc=(0, 0.0, COUNTER_Z - 0.08 - 1.95))
    parts.append(body)
    yf = -0.5
    zt = COUNTER_Z - 0.1
    dh, gap = 0.34, 0.04
    handle = st.get("handle", "knob")
    paper = None
    if st.get("door") == "lattice":
        paper = Sh("Washi", rough=0.8, sheen=0.3)
        paper.color(paper.mix(paper.remap(paper.noise(None, 90.0, 3.0), 0.3, 0.7, 0.0, 0.5), (0.98, 0.96, 0.91), (0.94, 0.91, 0.84)))
        b = paper.bsdf
        b.inputs["Emission Color"].default_value = (1.0, 0.92, 0.78, 1)
        b.inputs["Emission Strength"].default_value = 0.08
        paper = paper.mat
    for i, x in enumerate((-world_w / 4, world_w / 4)):
        w = world_w / 2 - 0.12
        # ящик
        zd = zt - gap - dh
        parts += shaker_door(f"Drawer{i}", x, zd, w, dh, paint, yf, frame=0.075)
        # дверца
        zdoor = zd - gap - 1.5
        parts += shaker_door(f"Door{i}", x, zdoor, w, 1.5, paint, yf, frame=0.13, lattice=paper)
        if handle == "bar":
            parts.append(bar_pull(f"DrawerPull{i}", x, zd + dh / 2, 0.42, metal_mat))
            parts.append(bar_pull(f"DoorPull{i}", x + (w / 2 - 0.2) * (1 if i == 0 else -1), zdoor + 1.5 - 0.35, 0.3,
                                  metal_mat, vertical=True))
        else:
            parts.append(knob(f"DrawerKnob{i}", x, zd + dh / 2, metal_mat))
            parts.append(knob(f"DoorKnob{i}", x + (w / 2 - 0.2) * (1 if i == 0 else -1), zdoor + 1.5 - 0.3, metal_mat))
    return parts


# MARK: - Свет

def lighting(scene, st):
    for o in [o for o in scene.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    w = scene.world
    nt = w.node_tree
    nodes, links = nt.nodes, nt.links
    bg = nodes["Background"]
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Generated"], sep.inputs[0])
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.5
    mr.inputs["From Max"].default_value = 0.8
    links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nodes.new("ShaderNodeValToRGB")
    wc = st["world"][0]
    els = ramp.color_ramp.elements
    els[0].color = (*[v * 0.45 for v in wc], 1)
    els[1].color = (*[min(1.0, v * 1.1) for v in wc], 1)
    links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = st["world"][1] * st.get("world_k", 1.15)

    def area(name, energy, loc, target, size, color, size_y=None):
        L = bpy.data.lights.new(name, type="AREA")
        L.energy = energy
        L.color = color
        if size_y:
            L.shape = "RECTANGLE"
            L.size, L.size_y = size, size_y
        else:
            L.size = size
        ob = bpy.data.objects.new(name, L)
        ob.location = loc
        d = Vector(target) - Vector(loc)
        ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()
        ob.visible_camera = False
        scene.collection.objects.link(ob)
        return ob

    def no_spec(ob):
        # подсветка не отражается в глянцевой плитке полосой: только мягкий рассеянный свет
        ob.visible_glossy = False
        return ob

    lc, le = st["light"]
    k = st.get("key_k", 1.0)
    # окно сверху слева: скользящий свет по плитке проявляет фаски
    area("Key", le * 0.95 * k, (-3.2, -4.5, 6.5), (0.6, 0.6, 1.0), st.get("key_size", 2.5), lc)
    # мягкая заливка справа, чуть холоднее
    fill = tuple(min(1.0, c * 0.92 + 0.06) for c in (lc[2], lc[1], lc[0]))
    area("Fill", le * 0.35 * k, (5.5, -7.0, -0.5), (0.0, 0.5, 0.0), 9.0, mix_c(lc, fill, 0.5))
    if st.get("lamps"):
        # теплая подсветка под полкой и над столешницей: широкая полоса света, без пятен
        no_spec(area("UnderShelf", st.get("strip_e", 60), (0.0, 0.12, LEDGE_Z - 0.09), (0.0, 0.5, LEDGE_Z - 2.0), 4.6,
                     (1.0, 0.70, 0.40), size_y=0.08))
        no_spec(area("CounterWash", st.get("wash_e", 70), (0.0, -0.6, -1.2), (0.0, 0.3, COUNTER_TOP), 6.0,
                     (1.0, 0.72, 0.42), size_y=1.2))
        # сама светодиодная планка под полкой
        strip = rbox("LedStrip", 4.8, 0.03, 0.012, glow_mat("LedGlow", (1.0, 0.80, 0.55), 6.0), bev=0.004,
                     loc=(0.0, 0.12, LEDGE_Z - 0.075))
        strip.visible_shadow = False


# MARK: - Предметы: посуда и банки

def stock_pot(name, body_mat, r=0.3, h=0.3, rim_mat=None, lid_mat=None, knob_mat=None):
    """Кастрюля с крышкой: тело с закатанной кромкой, ручки-петли по бокам, крышка-купол с кнопкой."""
    body = M.lathe(name, [(0.0, 0.0), (r * 0.86, 0.0), (r * 0.97, 0.015), (r, 0.05), (r, h - 0.03), (r + 0.012, h - 0.012),
                          (r + 0.008, h), (r - 0.015, h), (r - 0.015, h - 0.04), (0.0, h - 0.04)], 96)
    M.subdivide(body, 1)
    M.smooth(body)
    M.assign(body, body_mat)
    if rim_mat:
        faces_mat(body, [(lambda c, n: c.z > h - 0.028, rim_mat)])
    lid = lathe_s(name + "Lid", [(r + 0.008, h - 0.004), (r * 0.94, h + 0.025), (r * 0.6, h + 0.07), (r * 0.25, h + 0.09),
                                 (0.0, h + 0.095)], 96, 4)
    M.assign(M.smooth(lid), lid_mat or body_mat)
    kn = lathe_s(name + "Knob", [(0.03, h + 0.08), (0.025, h + 0.11), (0.05, h + 0.13), (0.045, h + 0.155),
                                 (0.0, h + 0.16)], 32, 4)
    M.assign(M.smooth(kn), knob_mat or rim_mat or body_mat)
    parts = [body, lid, kn]
    for s in (-1, 1):
        arc = []
        for k in range(15):
            a = math.pi * k / 14
            arc.append((s * (r + 0.005 + 0.07 * math.sin(a)), 0.0, h - 0.04 - 0.07 + 0.07 * math.cos(a) * 0.8))
        hd = EV.sweep(f"{name}Handle{s}", arc, 0.016, segs=16)
        parts.append(M.assign(hd, knob_mat or rim_mat or body_mat))
    return parts


def plate_obj(name, r, mat, rim_mat=None, deep=0.0):
    ob = M.lathe(name, [(0.0, 0.0), (r * 0.5, 0.0), (r * 0.56, 0.008), (r * 0.6, 0.02), (r * 0.66, 0.026 + deep),
                        (r * 0.95, 0.05 + deep), (r, 0.058 + deep), (r * 0.985, 0.066 + deep), (r * 0.94, 0.06 + deep),
                        (r * 0.66, 0.036 + deep), (r * 0.62, 0.03), (0.0, 0.03)], 96)
    M.subdivide(ob, 1)
    M.smooth(ob)
    M.assign(ob, mat)
    if rim_mat:
        faces_mat(ob, [(lambda c, n: math.hypot(c.x, c.y) > r * 0.9, rim_mat)])
    return ob


def plate_stack(name, n, r, mat, rim_mat=None):
    parts = []
    for k in range(n):
        p = plate_obj(f"{name}{k}", r, mat, rim_mat)
        put([p], 0.0, 0.0, k * 0.034, rz=k * 0.7)
        parts.append(p)
    return parts


def bowl_obj(name, r, h, mat, rim_mat=None, inner_mat=None):
    ob = shell(name, [(r * 0.45, 0.0), (r * 0.5, 0.012), (r * 0.52, 0.03), (r * 0.8, h * 0.35), (r * 0.97, h * 0.8),
                      (r, h), (r * 0.96, h * 1.01), (r * 0.92, h * 0.82), (r * 0.72, h * 0.4), (r * 0.4, h * 0.2)], 96, 5)
    M.smooth(ob)
    M.assign(ob, mat)
    rules = []
    if rim_mat:
        rules.append((lambda c, n: c.z > h * 0.9, rim_mat))
    if inner_mat:
        rules.append((lambda c, n: (n.x * c.x + n.y * c.y) < 0 and c.z > h * 0.18, inner_mat))
    if rules:
        faces_mat(ob, rules)
    return ob


def bowl_stack(name, n, r, h, mat, rim_mat=None):
    parts = []
    for k in range(n):
        b = bowl_obj(f"{name}{k}", r, h, mat, rim_mat)
        put([b], 0.0, 0.0, k * h * 0.42)
        parts.append(b)
    return parts


def deco_plate(name, r, base, ink, motif="flower"):
    """Расписная тарелка, стоит на ребре у стены: ободок, поясок с точками, цветок в центре."""
    sh = Sh(name + "Paint", rough=0.12, coat=0.7, coat_rough=0.05)
    x, y, z = sh.xyz()
    rad = sh.vmath("LENGTH", sh.combine(x, y, 0.0))
    ang = sh.math("ARCTAN2", y, x)
    t = sh.math("DIVIDE", rad, r)
    ring1 = sh.math("MULTIPLY", sh.remap(t, 0.90, 0.93), sh.remap(t, 1.01, 0.98))
    ring2 = sh.math("MULTIPLY", sh.remap(t, 0.60, 0.625), sh.remap(t, 0.66, 0.635))
    # точки в поясе
    ph = sh.math("PINGPONG", sh.math("MULTIPLY", ang, 18 / (2 * math.pi)), 0.5)
    dd = sh.vmath("LENGTH", sh.combine(sh.math("MULTIPLY", ph, 2 * math.pi / 18 * r * 0.78),
                                       sh.math("SUBTRACT", rad, r * 0.78), 0.0))
    dots = sh.remap(dd, r * 0.045, r * 0.03)
    if motif == "flower":
        petal = sh.math("MULTIPLY", sh.math("ABSOLUTE", sh.math("COSINE", sh.math("MULTIPLY", ang, 3.0))), r * 0.42)
        flower = sh.remap(sh.math("SUBTRACT", rad, petal), 0.01, -0.01)
        eye = sh.remap(rad, r * 0.1, r * 0.08)
    else:
        # волны сэйгайха условно: три кольца в центре
        flower = sh.math("MULTIPLY", sh.remap(t, 0.2, 0.23), sh.remap(t, 0.32, 0.29))
        eye = sh.remap(t, 0.1, 0.08)
    ink_m = sh.math("MAXIMUM", sh.math("MAXIMUM", ring1, ring2), sh.math("MAXIMUM", dots, flower))
    col = sh.mix(ink_m, base, ink)
    col = sh.mix(eye, col, (1.0, 0.80, 0.25))
    sh.color(col)
    ob = plate_obj(name, r, sh.mat, deep=0.01)
    return [ob]


def glass_jar(name, h, r, kind, fill=0.72, lid="wood", lid_col=(0.80, 0.52, 0.28), label=True, cloth=None):
    """Стеклянная банка с крупой: стекло с бликами по краю, содержимое с фактурой, крышка, бумажная этикетка."""
    jar = lathe_s(name, [(r * 0.92, 0.0), (r, 0.025), (r, h * 0.5), (r * 0.995, h - 0.06), (r * 0.9, h - 0.03),
                         (r * 0.88, h)], 64, 5)
    M.smooth(jar)
    M.assign(jar, glass_mat(name + "Glass"))
    jar.visible_shadow = False
    fz = max(0.05, h * fill)
    content = lathe_s(name + "Fill", [(r * 0.86, 0.012), (r - 0.012, 0.03), (r - 0.012, fz - 0.03), (r * 0.75, fz),
                                      (r * 0.3, fz + 0.012), (0.0, fz + 0.014)], 48, 4)
    M.assign(M.smooth(content), fill_mat(name + "FillM", kind))
    parts = [jar, content]
    if lid == "wood":
        lm = wood_sh(name + "Lid", (0.86, 0.62, 0.36), (0.62, 0.38, 0.18), axis="x", scale=4.0)
        ld = M.cylinder(name + "LidC", r * 0.96, 0.07, 64)
        ld.location = (0, 0, h + 0.03)
        M.apply_transform(ld)
        M.bevel(ld, 0.015, 3, 30)
        M.assign(M.smooth(ld, 30), lm)
        kb = M.sphere(name + "LidKnob", 0.032, 24, 12)
        kb.scale = (1, 1, 0.75)
        kb.location = (0, 0, h + 0.075)
        M.apply_transform(kb)
        parts += [ld, M.assign(M.smooth(kb), lm)]
    elif lid == "metal":
        ld = M.cylinder(name + "LidC", r * 0.95, 0.06, 96)
        ld.location = (0, 0, h + 0.022)
        M.apply_transform(ld)
        M.push_normals(ld, lambda co, n: -0.004 * (0.5 + 0.5 * math.cos(math.atan2(co.y, co.x) * 40))
                       if abs(n.z) < 0.5 else 0.0)
        M.bevel(ld, 0.01, 3, 30)
        parts.append(M.assign(M.smooth(ld, 30), metal(name + "LidM", lid_col, rough=0.28)))
    if cloth:
        # тканевая шапочка в клетку с бечевкой
        cl = M.polar_disc(name + "Cloth", 14, 72, 1.0, 1.0)
        rr = r * 1.0

        def drape(co):
            t = math.hypot(co.x, co.y)
            a = math.atan2(co.y, co.x)
            if t * 1.55 * rr <= rr:
                rad, z = t * 1.55 * rr, h + 0.06 + 0.02 * (1 - (t * 1.55) ** 2)
            else:
                d = t * 1.55 * rr - rr
                rad = rr + 0.012 + 0.03 * math.sin(a * 7) * min(1.0, d / 0.06)
                z = h + 0.06 - d * 1.1
            return Vector((rad * math.cos(a), rad * math.sin(a), z))
        M.deform(cl, drape)
        M.solidify(cl, 0.006)
        M.smooth(cl)
        csh = Sh(name + "Gingham", rough=0.65, sheen=0.4)
        cx, cy, cz = csh.xyz()
        sx_ = csh.math("GREATER_THAN", csh.math("PINGPONG", csh.math("MULTIPLY", cx, 9.0), 0.5), 0.25)
        sy_ = csh.math("GREATER_THAN", csh.math("PINGPONG", csh.math("MULTIPLY", csh.math("ADD", cy, cz), 9.0), 0.5), 0.25)
        both = csh.math("ADD", sx_, sy_)
        csh.color(csh.ramp(csh.math("MULTIPLY", both, 0.5), [(0.0, (0.98, 0.95, 0.90)), (0.5, mix_c(cloth, (1, 1, 1), 0.45)),
                                                              (1.0, cloth)], "CONSTANT"))
        M.assign(cl, csh.mat)
        tie = M.torus(name + "Tie", rr + 0.02, 0.008, 64, 8)
        tie.location = (0, 0, h + 0.035)
        M.apply_transform(tie)
        parts += [cl, M.assign(M.smooth(tie), ceramic(name + "TieM", (0.92, 0.84, 0.66), rough=0.6, coat=0.0))]
    if label:
        lb = label_patch(name + "Label", r + 0.004, h * 0.28, h * 0.62, 0.55,
                         ceramic(name + "Paper", (0.98, 0.94, 0.84), rough=0.55, coat=0.0, mottle=0.03))
        parts.append(lb)
    return parts


def label_patch(name, r, z0, z1, half_angle, mat, ink=(0.45, 0.30, 0.20)):
    """Бумажная этикетка на цилиндре лицом к камере (-Y): кусочек обечайки с полоской "надписи"."""
    nu, nv = 16, 4
    verts, faces = [], []
    for i in range(nu + 1):
        a = -math.pi / 2 - half_angle + 2 * half_angle * i / nu
        for j in range(nv + 1):
            verts.append((r * math.cos(a), r * math.sin(a), z0 + (z1 - z0) * j / nv))
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + 1, a + nv + 2, a + nv + 1))
    ob = M.from_data(name, verts, faces)
    M.solidify(ob, 0.003)
    M.smooth(ob)
    sh = Sh(name + "Ink", rough=0.55)
    x, y, z = sh.xyz()
    zm = (z0 + z1) / 2
    line = sh.math("MULTIPLY", sh.remap(z, zm - 0.012, zm - 0.008), sh.remap(z, zm + 0.012, zm + 0.008))
    line = sh.math("MULTIPLY", line, sh.remap(sh.math("ABSOLUTE", x), r * 0.55 * half_angle * 1.4, r * 0.5 * half_angle * 1.3))
    border = sh.math("MAXIMUM", sh.remap(z, z0 + 0.012, z0 + 0.008), sh.remap(z, z1 - 0.012, z1 - 0.008))
    paper = (0.98, 0.94, 0.84)
    sh.color(sh.mix(sh.math("MAXIMUM", line, sh.math("MULTIPLY", border, 0.8)), paper, ink))
    return M.assign(ob, sh.mat)


def bottle_oil(name, h=0.46, r=0.07, oil=(0.92, 0.70, 0.16), glass_tint=(0.86, 0.95, 0.80)):
    gl = lathe_s(name, [(r * 0.9, 0.0), (r, 0.02), (r, h * 0.55), (r * 0.8, h * 0.68), (r * 0.36, h * 0.78),
                        (r * 0.32, h * 0.92), (r * 0.36, h * 0.95), (r * 0.34, h)], 48, 5)
    M.assign(M.smooth(gl), glass_mat(name + "Glass", tint=glass_tint, edge=mix_c(glass_tint, (0.6, 0.8, 0.5), 0.4)))
    gl.visible_shadow = False
    oilm = I.toy(name + "Oil", oil, rough=0.1, coat=0.8)
    b = oilm.node_tree.nodes["Principled BSDF"]
    b.inputs["Emission Color"].default_value = (*M.lin(oil), 1)
    b.inputs["Emission Strength"].default_value = 0.25
    content = lathe_s(name + "OilBody", [(r * 0.86, 0.012), (r - 0.01, 0.03), (r - 0.01, h * 0.52), (r * 0.7, h * 0.62),
                                         (0.0, h * 0.63)], 48, 4)
    M.assign(M.smooth(content), oilm)
    cork = M.cylinder(name + "Cork", r * 0.34, 0.07, 32)
    cork.location = (0, 0, h + 0.015)
    M.apply_transform(cork)
    M.bevel(cork, 0.008, 2, 30)
    csh = Sh(name + "CorkM", rough=0.7)
    csh.color(csh.mix(csh.remap(csh.noise(None, 90.0, 2.0), 0.55, 0.62), (0.80, 0.60, 0.38), (0.55, 0.36, 0.20)))
    csh.bump(csh.noise(None, 90.0, 2.0), 0.3, 0.003)
    M.assign(M.smooth(cork, 30), csh.mat)
    lb = label_patch(name + "Label", r + 0.004, h * 0.18, h * 0.42, 0.7,
                     ceramic(name + "Paper", (0.98, 0.94, 0.84), rough=0.55, coat=0.0, mottle=0.03), ink=(0.30, 0.45, 0.18))
    return [gl, content, cork, lb]


def books(name, specs, lean=True):
    """Поваренные книги корешками к камере: обложка, блок страниц, золотые полоски на корешке.
    specs: [(толщина, высота, цвет sRGB)]."""
    parts = []
    x = 0.0
    gold = metal(name + "Gold", (1.0, 0.78, 0.32), rough=0.25)
    pages = ceramic(name + "Pages", (0.98, 0.95, 0.86), rough=0.7, coat=0.0, mottle=0.02)
    for k, (t, hgt, col) in enumerate(specs):
        cov = ceramic(f"{name}Cover{k}", col, rough=0.45, coat=0.25, mottle=0.05)
        grp = [rbox(f"{name}B{k}", t, 0.32, hgt, cov, bev=0.012, loc=(0, 0, 0)),
               rbox(f"{name}P{k}", t - 0.014, 0.3, hgt - 0.012, pages, bev=0.004, loc=(0, 0.006, 0.006))]
        for j, zb in enumerate((hgt * 0.12, hgt * 0.82)):
            grp.append(rbox(f"{name}G{k}{j}", t * 0.86, 0.01, 0.018, gold, bev=0.004, loc=(0, -0.162, zb)))
        if k == len(specs) - 1 and lean:
            # последняя книга наклонена и опирается на соседку
            ang = math.radians(-14)
            put(grp, 0, 0, 0, ry=ang)
            dx = x + hgt * math.sin(-ang) * 0 + t / 2 + 0.01
            put(grp, dx + hgt * 0.12, 0, 0)
        else:
            put(grp, x + t / 2, 0, 0)
        x += t + 0.004
        parts += grp
    put(parts, -x / 2, 0, 0)
    return parts


def kettle(name, color, r=0.21, handle_col=(0.20, 0.14, 0.10)):
    body_m = ceramic(name + "Enamel", color, rough=0.14, coat=0.8)
    body = lathe_s(name, [(r * 0.75, 0.0), (r * 0.95, 0.03), (r, 0.11), (r * 0.9, 0.2), (r * 0.6, 0.26), (r * 0.42, 0.28)],
                   64, 5)
    M.assign(M.smooth(body), body_m)
    lid = lathe_s(name + "Lid", [(r * 0.44, 0.27), (r * 0.38, 0.295), (r * 0.12, 0.31), (0.0, 0.312)], 48, 4)
    knb = M.sphere(name + "Knob", 0.03, 24, 12)
    knb.location = (0, 0, 0.33)
    M.apply_transform(knb)
    dark = ceramic(name + "Dark", handle_col, rough=0.3, coat=0.5)
    spout_pts = EV.spline([(r * 0.8, 0.0, 0.08), (r * 1.15, 0.0, 0.15), (r * 1.4, 0.0, 0.24), (r * 1.62, 0.0, 0.3)], 6)
    spout = EV.sweep(name + "Spout", spout_pts, lambda t: 0.045 - 0.025 * t, segs=20)
    hpts = EV.spline([(-r * 0.62, 0.0, 0.25), (-r * 0.55, 0.0, 0.4), (0.0, 0.0, 0.46), (r * 0.55, 0.0, 0.4),
                      (r * 0.62, 0.0, 0.25)], 8)
    handle = EV.sweep(name + "Handle", hpts, 0.02, segs=16)
    return [body, M.assign(M.smooth(lid), body_m), M.assign(M.smooth(knb), dark), M.assign(spout, body_m),
            M.assign(handle, dark)]


def mug(name, color, r=0.075, h=0.15, fill=None, inner=(0.97, 0.95, 0.9)):
    m = ceramic(name + "M", color, rough=0.14, coat=0.7)
    body = shell(name, [(r * 0.9, 0.0), (r, 0.02), (r * 1.02, h * 0.6), (r, h), (r - 0.012, h), (r - 0.014, h * 0.6),
                        (r * 0.82, 0.03)], 64, 4)
    M.assign(M.smooth(body), m)
    faces_mat(body, [(lambda c, n: (n.x * c.x + n.y * c.y) < 0 and c.z > 0.03, ceramic(name + "In", inner))])
    pts = [(r * 0.95 + 0.05 * math.sin(math.pi * k / 16), 0.0, h * 0.78 - h * 0.55 * k / 16) for k in range(17)]
    handle = EV.sweep(name + "Handle", pts, 0.012, segs=12)
    parts = [body, M.assign(handle, m)]
    if fill:
        f = M.cylinder(name + "Fill", r - 0.013, 0.01, 48)
        f.location = (0, 0, h - 0.025)
        M.apply_transform(f)
        parts.append(M.assign(M.smooth(f), ceramic(name + "FillM", fill, rough=0.2, coat=0.3, mottle=0.08)))
    return parts


def fruit_bowl(name, bowl_col, rim_col=None, kinds=("apple", "orange", "lemon", "apple", "orange")):
    r, h = 0.34, 0.15
    parts = [bowl_obj(name, r, h, ceramic(name + "M", bowl_col), ceramic(name + "Rim", rim_col) if rim_col else None)]
    spots = [(-0.14, -0.02, 0.0), (0.13, -0.04, 0.0), (0.0, 0.1, 0.02), (-0.05, -0.12, 0.08), (0.08, 0.08, 0.13)]
    for k, ((x, y, dz), kind) in enumerate(zip(spots, kinds)):
        rr = 0.12 if kind != "lemon" else 0.1
        parts += M3.fruit(f"{name}F{k}", kind, (x, y, h * 0.45 + rr * 0.9 + dz), rr)
    return parts


def wooden_spoon(name, L=0.5, mat=None, flat=False):
    h = EV.sweep(name + "Handle", [(0, 0, L * t / 10) for t in range(11)], lambda t: 0.016 - 0.004 * t, segs=16)
    head = M.sphere(name + "Head", 1.0, 32, 16)
    head.scale = (0.05, 0.02 if not flat else 0.012, 0.075)
    head.location = (0, 0, L + 0.06)
    M.apply_transform(head)
    if not flat:
        M.deform(head, lambda co: co + Vector((0, 0.012 * (1 - ((co.x / 0.05) ** 2 + ((co.z - L - 0.06) / 0.075) ** 2)), 0)))
    M.smooth(head)
    return [M.assign(h, mat), M.assign(head, mat)]


def crock(name, color, r=0.13, h=0.3, tools=True):
    """Горшок для лопаток: глазурь, деревянные ложки и венчик торчат вверх веером."""
    m = ceramic(name + "M", color, rough=0.16)
    body = shell(name, [(r * 0.92, 0.0), (r, 0.03), (r * 1.06, h * 0.5), (r, h * 0.92), (r * 1.06, h), (r * 0.94, h),
                        (r * 0.9, h * 0.9), (r * 0.85, 0.05)], 64, 4)
    M.assign(M.smooth(body), m)
    faces_mat(body, [(lambda c, n: (n.x * c.x + n.y * c.y) < 0 and c.z > 0.06, ceramic(name + "In", I.shade(color, 0.6)))])
    parts = [body]
    if tools:
        wm = wood_sh(name + "Wood", (0.92, 0.70, 0.44), (0.70, 0.46, 0.24), axis="z", scale=6.0)
        for k, (ax, ay, L, flat) in enumerate(((-16, 6, 0.42, False), (10, -4, 0.46, True), (-2, 10, 0.38, False))):
            sp = wooden_spoon(f"{name}Spoon{k}", L, wm, flat)
            put(sp, 0, 0, 0.05, rx=math.radians(ay), ry=math.radians(ax))
            put(sp, (k - 1) * 0.04, 0.0, 0.0)
            parts += sp
        steel = metal(name + "Steel", (0.86, 0.87, 0.9), rough=0.2)
        wh = M3.beater(name + "Whisk", 0.0, 0.0, steel, z_top=0.0)
        hd = M.cylinder(name + "WhiskHandle", 0.018, 0.3, 24)
        hd.location = (0, 0, 0.12)
        M.apply_transform(hd)
        wh.append(M.assign(M.smooth(hd), steel))
        put(wh, 0, 0, 0, rx=math.radians(180))
        put(wh, 0.0, 0.0, 0.16, s=0.42)
        put(wh, 0.06, 0.02, 0.0, ry=math.radians(22))
        parts += wh
    return parts


def terracotta_pot(name, r=0.13, h=0.22):
    sh = RM.terracotta_sh(name + "M", 0.0, h)
    pot = shell(name, [(r * 0.75, 0.0), (r * 0.8, 0.015), (r * 0.95, h * 0.75), (r * 0.96, h * 0.78), (r * 1.1, h * 0.8),
                       (r * 1.12, h), (r * 1.02, h), (r * 0.98, h * 0.85)], 64, 3)
    M.assign(M.smooth(pot), sh.mat)
    soil = M.cylinder(name + "Soil", r * 0.98, 0.02, 48)
    soil.location = (0, 0, h * 0.86)
    M.apply_transform(soil)
    soil_m = M.material(name + "SoilM", [(0.0, (0.22, 0.13, 0.08)), (1.0, (0.34, 0.21, 0.12))], coord="z", lo=0, hi=1,
                        rough=0.9, bump=0.6, bump_scale=60, vary=0.4, vary_scale=30)
    return [pot, M.assign(soil, soil_m)]


def herb_plant(name, r=0.13, h=0.22, n=11, size=1.0, seed=3, kind="basil", pot=True):
    rnd = random.Random(seed)
    parts = terracotta_pot(name + "Pot", r, h) if pot else []
    top = h * 0.87
    stops = [(0.0, (0.16, 0.46, 0.12)), (0.6, (0.30, 0.66, 0.20)), (1.0, (0.48, 0.80, 0.28))]
    for k in range(n):
        if kind == "blades":
            L = size * rnd.uniform(0.38, 0.6)
            lf = EV.leaf(f"{name}L{k}", length=L, width=L * 0.16, fold=0.25, curl=-0.04, thick=0.012,
                         stops=[(0.0, (0.14, 0.40, 0.12)), (0.6, (0.24, 0.58, 0.18)), (1.0, (0.44, 0.74, 0.26))],
                         petiole=0.02)
            el = math.radians(rnd.uniform(62, 84))
        else:
            L = size * rnd.uniform(0.16, 0.24)
            lf = EV.leaf(f"{name}L{k}", length=L, width=L * 0.62, fold=0.14, curl=0.08, thick=0.012, stops=stops,
                         petiole=0.03)
            el = math.radians(rnd.uniform(18, 62) if k > 3 else rnd.uniform(55, 75))
        yaw = 2 * math.pi * k / n + rnd.uniform(-0.3, 0.3)
        put(lf, 0, 0, 0, ry=-el)
        put(lf, 0, 0, 0, rz=yaw)
        rr = rnd.uniform(0.0, r * 0.45)
        put(lf, rr * math.cos(yaw), rr * math.sin(yaw), top + (rnd.uniform(0.04, 0.16) * size if kind != "blades" else 0.0))
        parts += lf
    return parts


def string_lights(name, pts, n, bulb=(1.0, 0.78, 0.42), wire=(0.12, 0.16, 0.10), strength=10.0, r=0.026):
    """Гирлянда: провод по кривой и теплые лампочки-капли вниз."""
    wpts = EV.spline(pts, 10)
    w = EV.sweep(name + "Wire", wpts, 0.006, segs=8)
    parts = [M.assign(w, ceramic(name + "WireM", wire, rough=0.4, coat=0.2, mottle=0.0))]
    P = [Vector(p) for p in wpts]
    cum = [0.0]
    for a, b in zip(P, P[1:]):
        cum.append(cum[-1] + (b - a).length)
    L = cum[-1]
    glow = glow_mat(name + "Glow", bulb, strength)
    cap = metal(name + "Cap", (0.75, 0.62, 0.32), rough=0.3)
    import bisect as _b
    for k in range(n):
        s = L * (k + 0.5) / n
        i = min(max(_b.bisect_right(cum, s) - 1, 0), len(P) - 2)
        t = (s - cum[i]) / max(1e-6, cum[i + 1] - cum[i])
        p = P[i].lerp(P[i + 1], t)
        b = lathe_s(f"{name}B{k}", [(0.0, -2.2 * r), (r * 0.55, -1.8 * r), (r, -0.9 * r), (r * 0.8, -0.1 * r), (r * 0.5, 0.15 * r)],
                    24, 3)
        M.assign(M.smooth(b), glow)
        c = M.cylinder(f"{name}C{k}", r * 0.5, r * 0.6, 16)
        c.location = (0, 0, 0.3 * r)
        M.apply_transform(c)
        M.assign(M.smooth(c), cap)
        grp = [b, c]
        put(grp, p.x, p.y - 0.004, p.z - 0.004, ry=math.radians((k % 3 - 1) * 12))
        parts += grp
    return parts


def pepper_mill(name, wood=((0.80, 0.50, 0.28), (0.56, 0.30, 0.14)), h=0.5):
    """Перечная мельница: точеное дерево, стальной верх с гайкой."""
    wm = wood_sh(name + "Wood", wood[0], wood[1], axis="z", scale=5.0, rough=0.3, coat=0.5)
    body = lathe_s(name, [(0.075, 0.0), (0.08, 0.03), (0.07, 0.07), (0.055, h * 0.3), (0.05, h * 0.5), (0.062, h * 0.66),
                          (0.075, h * 0.8), (0.07, h * 0.88), (0.05, h * 0.92)], 48, 5)
    M.assign(M.smooth(body), wm)
    steel = metal(name + "Steel", (0.9, 0.9, 0.92), rough=0.2)
    nut = lathe_s(name + "Nut", [(0.02, h * 0.91), (0.026, h * 0.93), (0.024, h * 0.97), (0.0, h * 0.98)], 24, 3)
    ring = M.torus(name + "Ring", 0.074, 0.008, 48, 8)
    ring.location = (0, 0, h * 0.84)
    M.apply_transform(ring)
    return [body, M.assign(M.smooth(nut), steel), M.assign(M.smooth(ring), steel)]


def bread_mat(name, top=(0.80, 0.46, 0.18), side=(0.95, 0.70, 0.40)):
    sh = Sh(name, rough=0.6, sss=0.08, coat=0.15)
    x, y, z = sh.xyz()
    nz = sh.noise(None, 9.0, 4.0)
    col = sh.ramp(sh.remap(z, 0.0, 0.22, smooth=False), [(0.0, side), (0.55, mix_c(top, side, 0.4)), (1.0, top)])
    col = sh.mix(sh.remap(nz, 0.35, 0.7, 0.0, 0.35), col, I.shade(top, 0.7), "MULTIPLY")
    # мучная пыль
    fl = sh.remap(sh.noise(None, 22.0, 3.0), 0.58, 0.68, 0.0, 0.75)
    col = sh.mix(sh.math("MULTIPLY", fl, sh.remap(z, 0.12, 0.2)), col, (0.98, 0.95, 0.88))
    sh.color(col)
    sh.bump(sh.noise(None, 30.0, 4.0), 0.4, 0.01)
    return sh


def boule(name, r=0.26, h=0.22):
    """Круглый хлеб с крестовым надрезом: на надрезе светлый мякиш-гребень."""
    ob = M.quad_sphere(name, 28)
    M.deform(ob, lambda co: Vector((co.x * r, co.y * r, max(co.z, -0.25) * h * (1.0 if co.z > 0 else 0.4) + h * 0.1)))

    def score(co):
        d = min(abs(co.x * 0.7 + co.y * 0.7), abs(co.x * 0.7 - co.y * 0.7))
        return -0.035 * math.exp(-(d / 0.025) ** 2) * max(0.0, (co.z - h * 0.35) / h) * 2.0
    M.push_normals(ob, lambda co, n: score(co) + 0.006 * M.fbm(co * 12))
    M.smooth(ob)
    sh = bread_mat(name + "M")
    x, y, z = sh.xyz()
    d1 = sh.math("ABSOLUTE", sh.math("ADD", sh.math("MULTIPLY", x, 0.7), sh.math("MULTIPLY", y, 0.7)))
    d2 = sh.math("ABSOLUTE", sh.math("SUBTRACT", sh.math("MULTIPLY", x, 0.7), sh.math("MULTIPLY", y, 0.7)))
    cut = sh.math("MULTIPLY", sh.remap(sh.math("MINIMUM", d1, d2), 0.03, 0.012), sh.remap(z, h * 0.5, h * 0.8))
    base = sh.bsdf.inputs["Base Color"].links[0].from_socket
    sh.color(sh.mix(cut, base, (1.0, 0.86, 0.6)))
    return [M.assign(ob, sh.mat)]


def round_board(name, r=0.36, wood=((0.88, 0.62, 0.36), (0.66, 0.40, 0.20))):
    wm = wood_sh(name + "W", wood[0], wood[1], axis="x", scale=3.0, rough=0.5, coat=0.1, seed=1.7)
    b = M.cylinder(name, r, 0.05, 96)
    b.location = (0, 0, 0.025)
    M.apply_transform(b)
    M.bevel(b, 0.015, 3, 30)
    hd = rbox(name + "Handle", 0.22, 0.09, 0.05, wm, bev=0.02, loc=(-r - 0.08, 0.0, 0.0))
    hole = M.cylinder(name + "Hole", 0.02, 0.2, 24)
    hole.location = (-r - 0.14, 0.0, 0.03)
    M.apply_transform(hole)
    M.boolean_cut(hd, [hole])
    return [M.assign(M.smooth(b, 30), wm), M.smooth(hd, 30)]


def knife_block(name, wood=((0.80, 0.52, 0.30), (0.56, 0.32, 0.16))):
    wm = wood_sh(name + "W", wood[0], wood[1], axis="z", scale=7.0, rough=0.4, coat=0.3, seed=2.2, rings=6.0, soft=0.35)
    blk = rbox(name, 0.3, 0.42, 0.42, wm, bev=0.03, segs=4)
    M.deform(blk, lambda co: co + Vector((0, co.z * 0.35, 0)))
    parts = [blk]
    handle_m = ceramic(name + "Handle", (0.18, 0.14, 0.13), rough=0.3, coat=0.6, mottle=0.02)
    steel = metal(name + "Steel", (0.88, 0.89, 0.92), rough=0.18)
    for k, (x, l) in enumerate(((-0.085, 0.2), (0.0, 0.24), (0.085, 0.18))):
        hd = M.capsule(f"{name}H{k}", l, 0.032, 24, 16)
        hd.rotation_euler = (0, math.radians(90), 0)
        M.apply_transform(hd)
        hd.scale = (0.8, 1.0, 1.0)
        M.apply_transform(hd)
        hd.location = (x, 0.0, 0.42 + l / 2 - 0.01)
        M.apply_transform(hd)
        bo = M.cylinder(f"{name}Bo{k}", 0.03, 0.03, 24)
        bo.scale = (0.8, 1.0, 1.0)
        bo.location = (x, 0.0, 0.43)
        M.apply_transform(bo)
        grp = [M.assign(M.smooth(hd), handle_m), M.assign(M.smooth(bo), steel)]
        rv = M.sphere(f"{name}Rv{k}", 0.008, 12, 6)
        rv.location = (x - 0.026, 0.0, 0.42 + l * 0.6)
        M.apply_transform(rv)
        grp.append(M.assign(rv, steel))
        put(grp, 0, 0, 0, rx=math.radians(-19))
        put(grp, 0, 0.02, 0.0)
        parts += grp
    return parts


LS, CS = 1.2, 1.15  # предметы на полке и на столешнице чуть крупнее натуральной величины: читаются на телефоне


def L(objs, x, y=0.24, rz=0.0, s=1.0):
    """На полку."""
    return put(objs, x, y, LEDGE_TOP, rz=rz, s=s * LS)


def Cn(objs, x, y=-0.25, rz=0.0, s=1.0):
    """На столешницу."""
    return put(objs, x, y, COUNTER_TOP, rz=rz, s=s * CS)


def hishaku(name):
    """Бамбуковый ковшик: стаканчик и длинная ручка, висит на крючке."""
    bm_ = bamboo_sh(name + "B", (0.94, 0.82, 0.56), (0.78, 0.60, 0.34), 40.0)
    cup = shell(name, [(0.06, 0.0), (0.065, 0.01), (0.065, 0.11), (0.056, 0.11), (0.056, 0.012)], 48, 2)
    M.assign(M.smooth(cup), bm_)
    put([cup], 0, 0, 0, ry=math.radians(90))
    hd = M.cylinder(name + "H", 0.011, 0.55, 16)
    hd.location = (0, 0, 0.32)
    M.apply_transform(hd)
    return [cup, M.assign(M.smooth(hd), bm_)]


def catenary(x0, x1, z, sag, y, n=12):
    return [(x0 + (x1 - x0) * k / n, y, z - sag * (1 - (2 * k / n - 1) ** 2)) for k in range(n + 1)]


# MARK: - Сборка сцены

def oak():
    return wood_sh("Oak", (0.88, 0.64, 0.40), (0.64, 0.38, 0.19), axis="x", scale=1.2, rough=0.42, coat=0.15)


def base_scene(st, world_w):
    """Стена, полка, рейлинг, столешница и шкафчики: общее для всех стилей."""
    parts = tile_wall(st)
    wood = st.get("wood_mat")
    if wood == "dark":
        wood = wood_sh("DarkOak", (0.52, 0.32, 0.18), (0.32, 0.18, 0.09), axis="x", scale=1.2, rough=0.4, coat=0.25)
    elif not wood:
        wood = oak()
    parts += shelf_ledge(st, world_w, wood)
    mcol = {"brass": (0.98, 0.74, 0.34), "steel": (0.86, 0.88, 0.92), "copper": (0.96, 0.56, 0.36),
            "chrome": (0.94, 0.95, 0.97), "iron": (0.16, 0.15, 0.15)}[st["metal"]]
    metal_mat = metal("Hardware", mcol, rough=0.22 if st["metal"] != "iron" else 0.45)
    parts += rail(st, world_w, metal_mat)
    paint = paint_sh("CabinetPaint", srgb(st["cabinet"]))
    top = st.get("top_mat")
    if top == "marble":
        top = marble_sh("Marble")
    elif top == "laminate":
        top = laminate_sh("Laminate")
    elif top == "dark":
        top = wood_sh("DarkTop", (0.56, 0.34, 0.18), (0.36, 0.20, 0.10), axis="x", scale=1.6, rough=0.35, coat=0.3, seed=3.0,
                      rings=5.0, soft=0.4)
    else:
        top = wood_sh("Butcher", (0.90, 0.66, 0.42), (0.66, 0.40, 0.20), axis="x", scale=1.6, rough=0.4, coat=0.2, seed=3.0,
                      rings=5.0, soft=0.45)
    edge = chrome("CounterChrome") if st.get("edge_mat") == "chrome" else None
    parts += cabinets(st, world_w, paint, metal_mat, top, edge)
    return parts, metal_mat


def hang_ring(name, mat, r=0.024):
    ring = M.torus(name, r, 0.006, 32, 8)
    ring.rotation_euler = (math.radians(90), 0, 0)
    M.apply_transform(ring)
    return M.assign(M.smooth(ring), mat)


def ladle(name, steel):
    """Половник: стальная ручка с кольцом, черпак внизу открыт вверх."""
    pts = EV.spline([(0.0, 0.0, -0.02), (0.0, 0.0, -0.3), (0.0, -0.01, -0.5), (0.0, -0.05, -0.56)], 8)
    hd = EV.sweep(name + "H", pts, 0.02, segs=12, section=(1.0, 0.55), up=(0, -1, 0))
    bowl = M.sphere(name + "Bowl", 0.085, 48, 24)
    M.bisect(bowl, (0, 0, 0), (0, 0, 1), fill=False)
    M.solidify(bowl, 0.008)
    bowl.location = (0.0, -0.12, -0.56)
    M.apply_transform(bowl)
    return [M.assign(hd, steel), M.assign(M.smooth(bowl), steel), hang_ring(name + "Ring", steel)]


def turner(name, steel, handle_m):
    """Лопатка с прорезями: стальная головка, деревянная ручка с отверстием."""
    head_pts = M3.round_poly([(-0.06, 0.0), (0.06, 0.0), (0.1, -0.2), (-0.1, -0.2)], 0.03, 6)
    cutters = [M3.slot_cutter(f"{name}Slot{k}", x, -0.11, 0.022, 0.12) for k, x in enumerate((-0.045, 0.0, 0.045))]
    head = M3.cut_slab(name + "Head", head_pts, 0.012, 0.004, steel, cutters)
    head.location.z -= 0.32
    M.apply_transform(head)
    neck = I.slab(name + "Neck", [(-0.012, 0.0), (0.012, 0.0), (0.03, -0.1), (-0.03, -0.1)], 0.01, 0.003, steel)
    neck.location.z -= 0.22
    M.apply_transform(neck)
    hp = M3.round_poly([(-0.022, 0.0), (0.022, 0.0), (0.027, -0.24), (-0.027, -0.24)], 0.018, 6)
    hole = M3.slot_cutter(name + "Hole", 0.0, -0.03, 0.018, 0.018)
    handle = M3.cut_slab(name + "Handle", hp, 0.03, 0.01, handle_m, [hole])
    handle.location.z += 0.0
    M.apply_transform(handle)
    return [head, neck, handle]


def whisk_hang(name, steel, handle_m):
    parts = M3.beater(name, 0.0, 0.0, steel, z_top=0.0)
    hd = lathe_s(name + "Hd", [(0.03, -0.02), (0.042, 0.06), (0.04, 0.3), (0.034, 0.38), (0.02, 0.4)], 32, 4)
    parts.append(M.assign(M.smooth(hd), handle_m))
    put(parts, 0, 0, 0, s=0.38)
    put(parts, 0, 0, -0.17)
    parts.append(hang_ring(name + "Ring", steel))
    return parts


def spoon_hang(name, wood_m, cord):
    sp = wooden_spoon(name, 0.36, wood_m)
    put(sp, 0, 0, 0, rx=math.radians(180))
    put(sp, 0, 0, -0.03)
    loop = M.torus(name + "Loop", 0.022, 0.005, 24, 6)
    loop.rotation_euler = (math.radians(90), 0, 0)
    M.apply_transform(loop)
    return sp + [M.assign(M.smooth(loop), cord)]


def hang_utensils(kenney, metal_mat, xs=(-0.5, -0.12, 0.24, 0.58)):
    """Утварь на рейлинге, собранная вручную: половник, лопатка с прорезями, венчик, деревянная ложка."""
    steel = metal("UtensilSteel", (0.90, 0.91, 0.94), rough=0.18)
    handle_m = wood_sh("UtensilHandle", (0.86, 0.58, 0.32), (0.62, 0.36, 0.16), axis="z", scale=6.0, rough=0.35, coat=0.4,
                       rings=6.0, soft=0.3)
    spoon_m = wood_sh("UtensilSpoon", (0.94, 0.74, 0.48), (0.74, 0.50, 0.28), axis="z", scale=6.0, rough=0.4, coat=0.3,
                      rings=6.0, soft=0.3)
    cord = ceramic("UtensilCord", (0.82, 0.22, 0.20), rough=0.6, coat=0.0, mottle=0.0)
    makers = (lambda: ladle("Ladle", steel), lambda: turner("Turner", steel, handle_m),
              lambda: whisk_hang("Whisk", steel, handle_m), lambda: spoon_hang("Spoon", spoon_m, cord))
    parts = []
    for make, x in zip(makers, xs):
        u = make()
        # предмет висит кольцом на нижнем крючке S-образного крючка
        put(u, x, 0.415, RAIL_Z - 0.16, s=1.15)
        parts += u
        parts.append(s_hook(f"Hook{x}", x, metal_mat))
    return parts


def dress_kitchen(st, kenney, metal_mat):
    """Кухня по умолчанию: бирюзовая плитка, медь и терракота, банки с крупами, живой базилик.
    Остальные стили без своей раскладки получают ее же, роспись посуды в цвет их плитки."""
    P = []
    ink = I.shade(srgb(st["tiles"][0]), 0.8) if st.get("generic") else (0.20, 0.52, 0.62)
    P += hang_utensils(kenney, metal_mat)
    copper = metal("Copper", (0.96, 0.52, 0.32), rough=0.24, hammered=0.25)
    P += L(stock_pot("Pot", copper, 0.25, 0.26, knob_mat=metal("Brass", (0.98, 0.76, 0.36), rough=0.2)), -1.84, 0.26)
    P += put(deco_plate("Plate", 0.3, (0.98, 0.96, 0.90), ink), -1.22, 0.47, LEDGE_TOP + 0.3 * 0.97,
             rx=math.radians(76))
    P += L(glass_jar("JarPasta", 0.46, 0.105, "pasta", 0.78, lid="wood"), -1.3, 0.14)
    P += L(glass_jar("JarBeans", 0.3, 0.1, "beans", 0.7, lid=None, cloth=(0.86, 0.22, 0.24)), -0.94, 0.2)
    P += L(bowl_stack("Bowls", 3, 0.17, 0.11, ceramic("BowlW", (0.98, 0.96, 0.92)), ceramic("BowlRim", ink)),
           -0.42, 0.24)
    P += L(herb_plant("Basil", 0.12, 0.2, n=12, size=1.0, seed=5), 0.08, 0.26)
    P += L(bottle_oil("Oil", 0.48, 0.068), 0.66, 0.24)
    P += L(pepper_mill("Mill"), 1.04, 0.24)
    P += L(books("Books", [(0.075, 0.46, (0.20, 0.46, 0.66)), (0.09, 0.5, (0.90, 0.36, 0.26)),
                           (0.07, 0.42, (0.96, 0.78, 0.30)), (0.08, 0.44, (0.36, 0.62, 0.40))]), 1.66, 0.28)
    P += Cn(round_board("Board"), -1.62, rz=math.radians(-8))
    P += put(boule("Bread"), -1.62, -0.25, COUNTER_TOP + 0.05 * CS, s=CS)
    P += Cn(crock("Crock", (0.96, 0.92, 0.84)), -0.82, -0.05, s=1.1)
    P += Cn(fruit_bowl("Fruit", (0.98, 0.96, 0.92), ink), 0.02, -0.32, s=1.05)
    P += Cn(kettle("Kettle", (0.95, 0.40, 0.30)), 0.95, -0.15, rz=math.radians(-10))
    P += Cn(knife_block("Knives"), 1.78, 0.0, rz=math.radians(-24))
    return P


DRESS = {"kitchen": dress_kitchen}


def build(style, st, src, kenney, world_w):
    parts, metal_mat = base_scene(st, world_w)
    if style not in DRESS:
        st = dict(st, generic=True)
    dress = DRESS.get(style, dress_kitchen)
    parts += dress(st, kenney, metal_mat)
    return parts


# MARK: - Свечение ламп

def bloom(path, threshold=0.92, radius=0.012, strength=0.55):
    """Мягкое свечение вокруг самых ярких точек (лампочки гирлянды, огоньки свечей). numpy, без PIL."""
    import numpy as np
    img = bpy.data.images.load(path, check_existing=False)
    w, h = img.size
    px = np.empty(w * h * 4, dtype=np.float32)
    img.pixels.foreach_get(px)
    a = px.reshape(h, w, 4)
    rgb = a[..., :3]
    lum = rgb.max(-1)
    mask = np.clip((lum - threshold) / (1 - threshold), 0, 1)[..., None] * rgb
    if mask.max() <= 0:
        bpy.data.images.remove(img)
        return
    r = max(2, int(radius * w))
    blur = mask
    for _ in range(3):
        for ax in (0, 1):
            c = np.cumsum(np.pad(blur, [(r + 1, r) if i == ax else (0, 0) for i in range(3)], mode="edge"), axis=ax)
            if ax == 0:
                blur = (c[2 * r + 1:] - c[:-2 * r - 1]) / (2 * r + 1)
            else:
                blur = (c[:, 2 * r + 1:] - c[:, :-2 * r - 1]) / (2 * r + 1)
    glow = np.clip(blur * strength * 4.0, 0, 1)
    a[..., :3] = 1 - (1 - rgb) * (1 - glow)
    img.pixels.foreach_set(a.reshape(-1))
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


# Дополнения к STYLES из environment.py: раскладка плитки, глазурь, столешница, ручки.
STYLE_EXTRA = {
    "kitchen": dict(layout="subway", edge=0.3, val_jitter=0.12, mottle=0.2, world_k=0.9),
}


# MARK: - Япония

def cloth_sh(name, base, motif=None, mon=False, sheen=0.5):
    """Хлопок норэн: индиго с белой волной внизу и гербом-кругом на средней полке (UV панели)."""
    sh = Sh(name, rough=0.7, sheen=sheen, sheen_rough=0.4)
    u, v, _ = sh.xyz(sh.tc("UV"))
    col = base
    if motif:
        wave = sh.math("ADD", v, sh.math("MULTIPLY", sh.math("SINE", sh.math("MULTIPLY", u, 2 * math.pi * 2.0)), 0.025))
        band = sh.math("MULTIPLY", sh.remap(wave, 0.70, 0.72), sh.remap(wave, 0.80, 0.78))
        band2 = sh.remap(wave, 0.86, 0.88)
        m = sh.math("MAXIMUM", band, band2)
        if mon:
            d = sh.vmath("LENGTH", sh.combine(sh.math("MULTIPLY", sh.math("SUBTRACT", u, 0.5), 1.0),
                                              sh.math("MULTIPLY", sh.math("SUBTRACT", v, 0.36), 1.25), 0.0))
            ring = sh.math("MULTIPLY", sh.remap(d, 0.16, 0.175), sh.remap(d, 0.235, 0.22))
            dot = sh.remap(d, 0.075, 0.06)
            m = sh.math("MAXIMUM", m, sh.math("MAXIMUM", ring, dot))
        col = sh.mix(m, base, motif)
    sh.color(col)
    sh.bump(sh.noise(sh.mapping(sh.tc("UV"), scale=(60.0, 60.0, 1.0)), 4.0, 2.0), 0.15, 0.003)
    return sh.mat


def noren(name, x0, x1, z_top, length, base, motif, panels=3, gap=0.035, y=0.42):
    parts = []
    W = (x1 - x0 - gap * (panels - 1)) / panels
    for k in range(panels):
        cx = x0 + W / 2 + k * (W + gap)

        def fn(u, v, cx=cx, k=k):
            fold = 0.022 * math.sin(2 * math.pi * u * 2.5 + k * 1.3) * (0.25 + 0.75 * v)
            return Vector((cx - W / 2 + W * u + 0.01 * v * (u - 0.5), y + fold, z_top - length * v))
        ob = RM.surface(f"{name}{k}", 36, 18, fn)
        M.solidify(ob, 0.008)
        M.smooth(ob)
        M.assign(ob, cloth_sh(f"{name}M{k}", base, motif, mon=(k == panels // 2)))
        parts.append(ob)
        sl = rbox(f"{name}Sleeve{k}", W, 0.07, 0.09, cloth_sh(f"{name}S{k}", base), bev=0.03, loc=(cx, 0.45, z_top - 0.04))
        parts.append(sl)
    return parts


def iron_mat(name, col=(0.20, 0.18, 0.17)):
    sh = Sh(name, rough=0.5, metal=0.6, coat=0.2, coat_rough=0.3)
    n = sh.noise(None, 8.0, 3.0)
    sh.color(sh.mix(sh.remap(n, 0.55, 0.7, 0.0, 0.35), col, (0.30, 0.36, 0.34)))
    sh.rough_vary(0.4, 0.62, 6.0)
    sh.bump(sh.noise(None, 50.0, 3.0), 0.2, 0.004)
    return sh.mat


def tetsubin(name, r=0.2):
    """Чугунный чайник: приплюснутое тело в пупырышках (араре), носик, дужка-ручка, крышка."""
    body = lathe_s(name, [(r * 0.62, 0.0), (r * 0.9, 0.03), (r, 0.1), (r * 0.92, 0.18), (r * 0.62, 0.22), (r * 0.42, 0.23)],
                   96, 6)
    M.subdivide(body, 1)

    def arare(co, n):
        a = math.atan2(co.y, co.x)
        z = co.z
        if z < 0.03 or z > 0.2:
            return 0.0
        row = round((z - 0.03) / 0.022)
        ph = (row % 2) * 0.5
        u = (a / (2 * math.pi) * 34 + ph) % 1.0 - 0.5
        w = (z - 0.03) / 0.022 - row
        return 0.008 * math.exp(-((u / 0.28) ** 2 + (w / 0.3) ** 2))
    M.push_normals(body, arare)
    m = iron_mat(name + "M")
    M.assign(M.smooth(body), m)
    lid = lathe_s(name + "Lid", [(r * 0.45, 0.225), (r * 0.38, 0.245), (r * 0.15, 0.255), (0.0, 0.257)], 48, 4)
    knb = M.sphere(name + "Knob", 0.025, 16, 8)
    knb.location = (0, 0, 0.27)
    M.apply_transform(knb)
    sp = EV.sweep(name + "Spout", EV.spline([(r * 0.8, 0.0, 0.08), (r * 1.18, 0.0, 0.13), (r * 1.4, 0.0, 0.19)], 6),
                  lambda t: 0.035 - 0.015 * t, segs=16)
    hp = EV.spline([(-r * 0.7, 0.0, 0.2), (-r * 0.75, 0.0, 0.33), (0.0, 0.0, 0.42), (r * 0.75, 0.0, 0.33),
                    (r * 0.7, 0.0, 0.2)], 8)
    hd = EV.sweep(name + "Bail", hp, 0.014, segs=12)
    return [body, M.assign(M.smooth(lid), m), M.assign(M.smooth(knb), m), M.assign(sp, m), M.assign(hd, m)]


def patterned_ceramic(name, base, ink, kind="stripes", z0=0.0, z1=0.3, n=6):
    sh = Sh(name, rough=0.14, coat=0.7, coat_rough=0.05)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    if kind == "stripes":
        m = sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", ang, n / (2 * math.pi)), 0.5), 0.12, 0.08)
    elif kind == "bands":
        t = sh.remap(z, z0, z1, smooth=False)
        m = sh.math("MAXIMUM", sh.math("MULTIPLY", sh.remap(t, 0.15, 0.18), sh.remap(t, 0.25, 0.22)),
                    sh.math("MULTIPLY", sh.remap(t, 0.62, 0.65), sh.remap(t, 0.8, 0.77)))
    else:  # dots
        ph = sh.math("PINGPONG", sh.math("MULTIPLY", ang, n / (2 * math.pi)), 0.5)
        dz = sh.math("SUBTRACT", z, (z0 + z1) / 2)
        dd = sh.vmath("LENGTH", sh.combine(sh.math("MULTIPLY", ph, 0.5), sh.math("MULTIPLY", dz, 3.0), 0.0))
        m = sh.remap(dd, 0.09, 0.07)
    sh.color(sh.mix(m, base, ink))
    return sh.mat


def tokkuri_set(name, glaze=(0.97, 0.95, 0.90), ink=(0.16, 0.26, 0.56)):
    m = patterned_ceramic(name + "M", glaze, ink, "bands", 0.0, 0.3)
    bottle = lathe_s(name, [(0.06, 0.0), (0.085, 0.03), (0.1, 0.1), (0.085, 0.17), (0.035, 0.24), (0.03, 0.27),
                            (0.045, 0.3)], 64, 5)
    M.assign(M.smooth(bottle), m)
    parts = [bottle]
    for k, x in enumerate((0.17, 0.3)):
        cup = shell(f"{name}Cup{k}", [(0.03, 0.0), (0.035, 0.01), (0.05, 0.04), (0.055, 0.065), (0.048, 0.066),
                                      (0.042, 0.04), (0.025, 0.015)], 48, 3)
        M.assign(M.smooth(cup), patterned_ceramic(f"{name}CM{k}", glaze, ink, "dots", 0.01, 0.06, 5))
        put([cup], x, -0.06 * k, 0.0)
        parts.append(cup)
    return parts


def kokeshi(name, h=0.3):
    """Кокэси: деревянная куколка, красные цветы на теле, черные волосы."""
    wsh = Sh(name + "Body", rough=0.35, coat=0.6)
    x, y, z = wsh.xyz()
    ang = wsh.math("ARCTAN2", y, x)
    base = (0.96, 0.84, 0.62)
    t = wsh.remap(z, 0.0, h * 0.7, smooth=False)
    band = wsh.math("MULTIPLY", wsh.remap(t, 0.08, 0.1), wsh.remap(t, 0.2, 0.18))
    ph = wsh.math("PINGPONG", wsh.math("MULTIPLY", ang, 5 / (2 * math.pi)), 0.5)
    fl = wsh.vmath("LENGTH", wsh.combine(wsh.math("MULTIPLY", ph, 0.5), wsh.math("MULTIPLY", wsh.math("SUBTRACT", t, 0.55), 1.3), 0.0))
    petals = wsh.remap(fl, 0.16, 0.13)
    eye = wsh.remap(fl, 0.05, 0.04)
    col = wsh.mix(band, base, (0.90, 0.20, 0.22))
    col = wsh.mix(wsh.math("MULTIPLY", wsh.remap(t, 0.85, 0.88), 1.0), col, (0.90, 0.20, 0.22))
    col = wsh.mix(petals, col, (0.92, 0.24, 0.28))
    col = wsh.mix(eye, col, (1.0, 0.80, 0.30))
    wsh.color(col)
    body = lathe_s(name, [(0.055, 0.0), (0.06, 0.01), (0.058, h * 0.3), (0.05, h * 0.6), (0.042, h * 0.68)], 48, 4)
    M.assign(M.smooth(body), wsh.mat)
    hsh = Sh(name + "Head", rough=0.3, coat=0.6)
    hx, hy, hz = hsh.xyz()
    # волосы: макушка и челка, лицо открыто к камере (-Y)
    hair = hsh.math("MAXIMUM", hsh.remap(hz, 0.02, 0.035), hsh.remap(hy, -0.02, 0.01))
    face_mask = hsh.math("MULTIPLY", hsh.remap(hz, 0.03, 0.015), hsh.remap(hy, 0.0, -0.03))
    hair = hsh.math("MULTIPLY", hair, hsh.math("SUBTRACT", 1.0, face_mask))
    col = hsh.mix(hair, (0.99, 0.92, 0.82), (0.10, 0.08, 0.08))
    # румянец
    ch = hsh.vmath("LENGTH", hsh.combine(hsh.math("SUBTRACT", hsh.math("ABSOLUTE", hx), 0.032), hsh.math("ADD", hy, 0.06),
                                         hsh.math("ADD", hz, 0.012)))
    col = hsh.mix(hsh.remap(ch, 0.018, 0.008), col, (0.98, 0.55, 0.55))
    hsh.color(col)
    head = M.sphere(name + "HeadO", 0.068, 32, 16)
    head.scale = (1.0, 0.95, 0.92)
    M.apply_transform(head)
    M.assign(M.smooth(head), hsh.mat)
    put([head], 0, 0, h * 0.68 + 0.055)
    return [body, head]


def bamboo_sh(name, light=(0.92, 0.78, 0.50), dark=(0.74, 0.56, 0.30), slats=90.0):
    sh = Sh(name, rough=0.45, coat=0.25)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    s = sh.math("PINGPONG", sh.math("MULTIPLY", ang, slats / (2 * math.pi)), 0.5)
    weave = sh.math("PINGPONG", sh.math("MULTIPLY", z, 40.0), 0.5)
    col = sh.mix(sh.remap(s, 0.42, 0.5, 0.0, 0.6), light, dark)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(weave, 0.4, 0.5), 0.25), col, dark)
    sh.color(col)
    sh.bump(sh.math("MULTIPLY", s, 1.0), 0.3, 0.004)
    return sh.mat


def steamer(name, r=0.24):
    parts = []
    bm_ = bamboo_sh(name + "B")
    rim_m = bamboo_sh(name + "R", (0.86, 0.68, 0.40), (0.70, 0.50, 0.26), 6.0)
    for k in range(2):
        ring = shell(f"{name}T{k}", [(r * 0.98, 0.0), (r, 0.005), (r, 0.11), (r - 0.012, 0.11), (r - 0.012, 0.01)], 96, 2)
        M.assign(M.smooth(ring), bm_)
        put([ring], 0, 0, k * 0.115)
        parts.append(ring)
        for j, zz in enumerate((0.012, 0.1)):
            t = M.torus(f"{name}Band{k}{j}", r + 0.002, 0.008, 96, 8)
            t.location = (0, 0, k * 0.115 + zz)
            M.apply_transform(t)
            parts.append(M.assign(M.smooth(t), rim_m))
    lid = lathe_s(name + "Lid", [(r + 0.004, 0.23), (r * 0.98, 0.26), (r * 0.7, 0.3), (r * 0.3, 0.315), (0.0, 0.317)], 96, 4)
    M.assign(M.smooth(lid), bamboo_sh(name + "L", slats=140.0))
    parts.append(lid)
    return parts


def matcha_set(name):
    bowl = bowl_obj(name, 0.16, 0.12, ceramic(name + "M", (0.36, 0.28, 0.22), rough=0.2),
                    ceramic(name + "Rim", (0.74, 0.62, 0.48), rough=0.3))
    tea = M.cylinder(name + "Tea", 0.14, 0.01, 48)
    tea.location = (0, 0, 0.095)
    M.apply_transform(tea)
    tsh = Sh(name + "Froth", rough=0.5)
    tsh.color(tsh.mix(tsh.remap(tsh.noise(None, 40.0, 3.0), 0.4, 0.7), (0.46, 0.64, 0.20), (0.72, 0.84, 0.40)))
    M.assign(M.smooth(tea), tsh.mat)
    # венчик тясэн рядом
    ch = lathe_s(name + "Chasen", [(0.012, 0.0), (0.045, 0.02), (0.055, 0.06), (0.045, 0.1), (0.022, 0.12), (0.02, 0.2),
                                   (0.018, 0.22)], 48, 4)
    M.assign(M.smooth(ch), bamboo_sh(name + "CB", (0.94, 0.84, 0.60), (0.80, 0.66, 0.40), 60.0))
    put([ch], 0.26, -0.02, 0.0)
    return [bowl, tea, ch]


def kyusu(name, color=(0.62, 0.30, 0.18)):
    m = ceramic(name + "M", color, rough=0.3, coat=0.3)
    body = lathe_s(name, [(0.1, 0.0), (0.13, 0.02), (0.145, 0.07), (0.12, 0.13), (0.07, 0.15)], 64, 5)
    lid = lathe_s(name + "Lid", [(0.075, 0.145), (0.06, 0.16), (0.02, 0.17), (0.0, 0.172)], 48, 3)
    kn = M.sphere(name + "Kn", 0.018, 16, 8)
    kn.location = (0, 0, 0.18)
    M.apply_transform(kn)
    sp = EV.sweep(name + "Sp", EV.spline([(0.12, 0.0, 0.06), (0.18, 0.0, 0.1), (0.21, 0.0, 0.14)], 6),
                  lambda t: 0.026 - 0.01 * t, segs=14)
    # боковая ручка смотрит к камере и влево
    hd = M.capsule(name + "Hd", 0.16, 0.024, 24, 12)
    hd.location = (-0.17, 0.0, 0.08)
    M.apply_transform(hd)
    put([hd], 0, 0, 0, rz=math.radians(-55))
    return [M.assign(M.smooth(body), m), M.assign(M.smooth(lid), m), M.assign(M.smooth(kn), m), M.assign(sp, m),
            M.assign(M.smooth(hd), m)]


def bonsai(name, pot_col=(0.22, 0.40, 0.62)):
    pot = rbox(name + "Pot", 0.42, 0.24, 0.1, ceramic(name + "PM", pot_col, rough=0.18), bev=0.02)
    moss = M.cylinder(name + "Moss", 0.17, 0.02, 48)
    moss.scale = (1.0, 0.45, 1.0)
    moss.location = (0, 0, 0.1)
    M.apply_transform(moss)
    mm = M.material(name + "MossM", [(0.0, (0.30, 0.48, 0.16)), (1.0, (0.44, 0.62, 0.22))], coord="z", lo=0, hi=1,
                    rough=0.8, bump=0.6, bump_scale=60, vary=0.4, vary_scale=40)
    trunk_pts = EV.spline([(0.02, 0.0, 0.1), (-0.04, 0.0, 0.2), (0.05, 0.0, 0.3), (0.14, 0.0, 0.36)], 8)
    tr = EV.sweep(name + "Trunk", trunk_pts, lambda t: 0.035 - 0.022 * t, segs=16)
    br = EV.sweep(name + "Branch", EV.spline([(-0.01, 0.0, 0.25), (-0.1, 0.0, 0.3), (-0.18, 0.0, 0.31)], 6),
                  lambda t: 0.016 - 0.008 * t, segs=12)
    bark = wood_sh(name + "Bark", (0.50, 0.36, 0.26), (0.30, 0.20, 0.14), axis="z", scale=6.0, rough=0.7, coat=0.0)
    parts = [pot, M.assign(moss, mm), M.assign(tr, bark), M.assign(br, bark)]
    leaf_m = M.material(name + "Leaf", [(0.0, (0.16, 0.40, 0.14)), (1.0, (0.36, 0.64, 0.22))], coord="z", lo=-0.05,
                        hi=0.06, rough=0.55, sss=0.2, bump=0.8, bump_scale=70, vary=0.25, vary_scale=12)
    for k, (x, z, rx_, rz_) in enumerate(((0.15, 0.4, 0.13, 0.06), (-0.19, 0.34, 0.11, 0.05), (0.0, 0.45, 0.1, 0.05))):
        pad = M.quad_sphere(f"{name}Pad{k}", 12)
        M.deform(pad, lambda co, a=rx_, c=rz_: Vector((co.x * a, co.y * a * 0.8, max(co.z, -0.4) * c)))
        M.push_normals(pad, lambda co, n: 0.012 * M.fbm(co * 30))
        M.smooth(pad)
        pad.location = (x, 0.0, z)
        parts.append(M.assign(pad, leaf_m))
    return parts


def dress_japan(st, kenney, metal_mat):
    """Япония: мозаика индиго, норэн на рейлинге, чугунный чайник, токкури, кокэси, бамбуковая пароварка, бонсай."""
    P = []
    P += noren("Noren", -1.05, 1.05, RAIL_Z + 0.03, 0.62, (0.16, 0.24, 0.46), (0.96, 0.94, 0.88))
    P.append(s_hook("HookL", -1.7, metal_mat))
    P += put(hishaku("Ladle"), -1.7, 0.39, RAIL_Z - 0.75, s=1.1)
    P += L(tetsubin("Tetsu"), -1.86, 0.24, s=1.05)
    P += put(deco_plate("Plate", 0.3, (0.97, 0.95, 0.90), (0.16, 0.26, 0.56), motif="waves"), -1.2, 0.47,
             LEDGE_TOP + 0.3 * 0.97, rx=math.radians(76))
    P += L(bowl_stack("Bowls", 3, 0.16, 0.1, ceramic("BowlW", (0.97, 0.95, 0.90)), ceramic("BowlRim", (0.16, 0.26, 0.56))),
           -1.22, 0.14)
    P += L(tokkuri_set("Sake"), -0.66, 0.22)
    P += L(herb_plant("Bamboo", 0.11, 0.18, n=9, size=1.0, seed=8, kind="blades"), 0.2, 0.28)
    P += L(glass_jar("Rice", 0.36, 0.11, "rice", 0.75, lid="wood"), 0.78, 0.22)
    P += L(glass_jar("Tea", 0.26, 0.09, "tea", 0.7, lid="metal", lid_col=(0.30, 0.40, 0.30)), 1.14, 0.2)
    P += L(kokeshi("Kokeshi"), 1.56, 0.22)
    P += L(kokeshi("Kokeshi2", 0.24), 1.84, 0.28, rz=math.radians(10))
    P += Cn(steamer("Steamer"), -1.62, -0.12)
    P += Cn(kyusu("Kyusu"), -0.8, -0.25, s=1.25)
    P += Cn(matcha_set("Matcha"), 0.0, -0.3, s=1.25)
    P += Cn(fruit_bowl("Fruit", (0.97, 0.95, 0.90), (0.16, 0.26, 0.56), kinds=("orange", "orange", "lemon", "orange",
                                                                            "orange")), 0.92, -0.25)
    P += Cn(bonsai("Bonsai"), 1.74, -0.05, s=1.3)
    return P


DRESS["japan"] = dress_japan
STYLE_EXTRA["japan"] = dict(layout="mosaic", edge=0.45, edge_col=(0.26, 0.34, 0.54), val_jitter=0.22, hue_jitter=0.03,
                            mottle=0.25, mottle_scale=7.0, tilt=1.4, pillow=0.005, bevel=0.02, gap=0.016,
                            grout=(0.42, 0.45, 0.50),
                            accent=((0.18, 0.30, 0.56), 0.12), door="lattice", handle="bar",
                            wood_mat=None, world_k=1.0)


# MARK: - Италия

def straw_sh(name, light=(0.96, 0.84, 0.56), dark=(0.78, 0.60, 0.32)):
    """Плетеная солома: ряды стежков вокруг оси."""
    sh = Sh(name, rough=0.6, sheen=0.3)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    row = sh.math("PINGPONG", sh.math("MULTIPLY", z, 55.0), 0.5)
    st_ = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", ang, 40 / (2 * math.pi)),
                                      sh.math("MULTIPLY", sh.math("FLOOR", sh.math("MULTIPLY", z, 110.0)), 0.5)), 0.5)
    m = sh.math("MULTIPLY", sh.remap(row, 0.5, 0.3), sh.remap(st_, 0.5, 0.2))
    sh.color(sh.mix(m, dark, light))
    sh.bump(m, 0.5, 0.004)
    return sh.mat


def fiasco(name):
    """Кьянти в соломенной оплетке: круглое брюшко, длинное горлышко, красный колпачок."""
    gl = lathe_s(name, [(0.03, 0.0), (0.12, 0.04), (0.15, 0.14), (0.12, 0.25), (0.05, 0.31), (0.034, 0.36), (0.032, 0.5),
                        (0.036, 0.52)], 64, 5)
    M.assign(M.smooth(gl), I.toy(name + "Glass", (0.30, 0.42, 0.20), rough=0.06, coat=1.0))
    straw = lathe_s(name + "Straw", [(0.035, -0.002), (0.125, 0.04), (0.155, 0.13), (0.14, 0.2), (0.11, 0.24)], 64, 4)
    M.assign(M.smooth(straw), straw_sh(name + "S"))
    cap = lathe_s(name + "Cap", [(0.038, 0.47), (0.04, 0.5), (0.04, 0.54), (0.0, 0.545)], 32, 3)
    M.assign(M.smooth(cap), I.toy(name + "CapM", (0.86, 0.12, 0.14), rough=0.3, coat=0.6))
    lb = label_patch(name + "Lb", 0.152, 0.13, 0.19, 0.5, ceramic(name + "P", (0.98, 0.94, 0.84), rough=0.5, coat=0.0),
                     ink=(0.70, 0.12, 0.12))
    return [gl, straw, cap, lb]


def garlic_bulb(name, r=0.07):
    ob = M.sphere(name, r, 32, 20)

    def shape(co):
        a = math.atan2(co.y, co.x)
        t = co.z / r
        lobe = 1 + 0.07 * math.cos(8 * a)
        k = (1 - max(0.0, t) ** 2 * 0.35) * lobe
        z = co.z * 0.9 + (r * 0.55 * max(0.0, t) ** 4)
        return Vector((co.x * k, co.y * k, z))
    M.deform(ob, shape)
    M.smooth(ob)
    sh = Sh(name + "M", rough=0.45, sss=0.15, coat=0.3)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", y, x)
    stripe = sh.remap(sh.math("PINGPONG", sh.math("MULTIPLY", ang, 8 / (2 * math.pi)), 0.5), 0.1, 0.0)
    col = sh.mix(sh.math("MULTIPLY", stripe, sh.remap(z, -r * 0.2, r * 0.6)), (0.98, 0.95, 0.90), (0.72, 0.46, 0.66))
    sh.color(col)
    tip = M.cylinder(name + "Tip", 0.008, 0.05, 8)
    tip.location = (0, 0, r * 1.05)
    M.apply_transform(tip)
    return [M.assign(ob, sh.mat), M.assign(tip, ceramic(name + "TipM", (0.86, 0.78, 0.60), rough=0.6, coat=0.0))]


def garlic_braid(name, length=0.62):
    """Косичка чеснока: соломенный жгут и головки по очереди вправо-влево."""
    rope = EV.sweep(name + "Rope", [(0.0, 0.0, -length * k / 12) for k in range(13)], 0.022, segs=12)
    parts = [M.assign(rope, straw_sh(name + "RopeM"))]
    for k in range(7):
        z = -0.08 - k * (length - 0.12) / 6
        side = 1 if k % 2 else -1
        b = garlic_bulb(f"{name}B{k}", 0.065 - 0.003 * k)
        put(b, 0, 0, 0, ry=math.radians(side * 70 + 180), rx=math.radians(-15))
        put(b, side * 0.055, -0.03, z)
        parts += b
    return parts


def chili(name, L=0.16, r=0.022):
    pts = EV.spline([(0.0, 0.0, 0.0), (0.01, 0.0, -L * 0.4), (0.03, 0.0, -L * 0.8), (0.055, 0.0, -L)], 6)
    ob = EV.sweep(name, pts, lambda t: r * (1 - t ** 1.6 * 0.92), segs=16)
    stem = M.cylinder(name + "St", 0.007, 0.03, 8)
    stem.location = (0, 0, 0.012)
    M.apply_transform(stem)
    return [M.assign(ob, I.toy(name + "M", (0.88, 0.10, 0.08), rough=0.15, coat=0.9)),
            M.assign(stem, I.toy(name + "StM", (0.30, 0.56, 0.18)))]


def chili_string(name, length=0.6):
    cord = EV.sweep(name + "Cord", [(0.0, 0.0, -length * k / 10) for k in range(11)], 0.006, segs=8)
    parts = [M.assign(cord, ceramic(name + "CordM", (0.92, 0.84, 0.66), rough=0.6, coat=0.0))]
    rnd = random.Random(4)
    for k in range(11):
        z = -0.04 - k * (length - 0.08) / 10
        c = chili(f"{name}C{k}")
        put(c, 0, 0, 0, rz=math.radians(rnd.uniform(0, 360)), ry=math.radians(rnd.uniform(-25, 25)))
        put(c, 0, 0, z)
        parts += c
    return parts


def spaghetti_jar(name, h=0.4, r=0.09):
    jar = lathe_s(name, [(r * 0.92, 0.0), (r, 0.02), (r, h - 0.02), (r * 0.96, h)], 48, 3)
    M.assign(M.smooth(jar), glass_mat(name + "G"))
    jar.visible_shadow = False
    pm = I.toy(name + "Pasta", (0.98, 0.84, 0.40), rough=0.25, coat=0.6)
    parts = [jar]
    rnd = random.Random(9)
    for k in range(46):
        a = rnd.uniform(0, 2 * math.pi)
        rr = math.sqrt(rnd.random()) * (r - 0.012)
        stick = M.cylinder(f"{name}S{k}", 0.0055, h + 0.14 + rnd.uniform(-0.03, 0.03), 6)
        stick.location = (rr * math.cos(a), rr * math.sin(a), (h + 0.14) / 2 + 0.01)
        stick.rotation_euler = (rnd.uniform(-0.05, 0.05), rnd.uniform(-0.05, 0.05), 0)
        M.apply_transform(stick)
        parts.append(M.assign(stick, pm))
    return parts


def tomato_tin(name, r=0.085, h=0.2):
    tin = M.lathe(name, [(0.0, 0.0), (r - 0.004, 0.0), (r, 0.006), (r - 0.003, 0.014), (r, 0.022), (r, h - 0.022),
                         (r - 0.003, h - 0.014), (r, h - 0.006), (r - 0.004, h), (0.0, h)], 64)
    M.assign(M.smooth(tin, 40), metal(name + "M", (0.86, 0.87, 0.9), rough=0.25))
    sh = Sh(name + "Lbl", rough=0.35, coat=0.5)
    x, y, z = sh.xyz()
    d = sh.vmath("LENGTH", sh.combine(x, sh.math("MULTIPLY", sh.math("SUBTRACT", z, h * 0.48), 1.0), 0.0))
    front = sh.math("GREATER_THAN", sh.math("MULTIPLY", y, -1.0), 0.0)
    tom = sh.math("MULTIPLY", sh.remap(d, 0.05, 0.045), front)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(z, h * 0.75, h * 0.78), 1.0), (0.86, 0.12, 0.10), (0.98, 0.94, 0.84))
    col = sh.mix(tom, col, (0.98, 0.30, 0.18))
    leafm = sh.math("MULTIPLY", sh.remap(sh.vmath("LENGTH", sh.combine(sh.math("SUBTRACT", x, 0.012), 0.0,
                                                                       sh.math("SUBTRACT", z, h * 0.48 + 0.048))), 0.016, 0.012), front)
    col = sh.mix(leafm, col, (0.30, 0.62, 0.20))
    sh.color(col)
    lb = M.lathe(name + "L", [(r + 0.002, 0.03), (r + 0.002, h - 0.03)], 64)
    M.solidify(lb, 0.002)
    return [tin, M.assign(M.smooth(lb), sh.mat)]


def moka(name):
    """Гейзерная кофеварка: восьмигранная, алюминий, черная ручка и кнопка."""
    al = metal(name + "Al", (0.80, 0.81, 0.84), rough=0.32, brushed=True)
    dark = ceramic(name + "Dark", (0.12, 0.11, 0.11), rough=0.35, coat=0.4, mottle=0.0)
    low = M.lathe(name + "Low", [(0.0, 0.0), (0.105, 0.0), (0.11, 0.01), (0.08, 0.16), (0.075, 0.17), (0.0, 0.17)], 8)
    up = M.lathe(name + "Up", [(0.0, 0.17), (0.07, 0.17), (0.085, 0.19), (0.1, 0.33), (0.105, 0.34), (0.0, 0.34)], 8)
    lid = M.lathe(name + "Lid", [(0.0, 0.34), (0.105, 0.34), (0.08, 0.37), (0.0, 0.375)], 8)
    for o in (low, up, lid):
        put([o], 0, 0, 0, rz=math.radians(22.5))
        M.apply_transform(o)
        M.bevel(o, 0.006, 2, 30)
        M.assign(M.smooth(o, 30), al)
    kn = lathe_s(name + "Kn", [(0.02, 0.37), (0.03, 0.385), (0.022, 0.41), (0.0, 0.415)], 24, 3)
    hd = EV.sweep(name + "Hd", EV.spline([(-0.09, 0.0, 0.3), (-0.17, 0.0, 0.29), (-0.18, 0.0, 0.2), (-0.12, 0.0, 0.19)], 6),
                  0.018, segs=12, section=(1.0, 0.6))
    sp = M.lathe(name + "Sp", [(0.0, 0.29), (0.03, 0.29), (0.02, 0.34), (0.0, 0.345)], 3)
    sp.scale = (1.6, 0.6, 1.0)
    sp.location = (0.09, 0.0, 0.0)
    M.apply_transform(sp)
    return [low, up, lid, M.assign(M.smooth(kn), dark), M.assign(hd, dark), M.assign(M.smooth(sp, 30), al)]


def marble_sh(name, base=(0.97, 0.96, 0.94), vein=(0.66, 0.66, 0.70)):
    """Мрамор: тонкие ветвящиеся прожилки по изолиниям шума и легкая облачность."""
    sh = Sh(name, rough=0.12, coat=0.6, coat_rough=0.04)
    n1 = sh.noise(None, 1.8, 8.0, 0.55, distortion=1.2)
    n2 = sh.noise(sh.mapping(None, loc=(3.1, 1.7, 0.4)), 3.5, 6.0, 0.6, distortion=0.8)
    v1 = sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", n1, 0.5)), 0.012, 0.0)
    v2 = sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", n2, 0.5)), 0.006, 0.0)
    v = sh.math("MAXIMUM", sh.math("MULTIPLY", v1, 0.75), sh.math("MULTIPLY", v2, 0.4))
    cloud = sh.noise(None, 0.8, 4.0)
    col = sh.mix(sh.remap(cloud, 0.35, 0.7, 0.0, 0.25), base, (0.88, 0.88, 0.90))
    col = sh.mix(v, col, vein)
    sh.color(col)
    return sh.mat


def mortar(name):
    m = marble_sh(name + "M")
    bowl = shell(name, [(0.1, 0.0), (0.12, 0.01), (0.15, 0.08), (0.15, 0.14), (0.13, 0.15), (0.11, 0.09), (0.05, 0.05)],
                 64, 4)
    pest = M.capsule(name + "Pestle", 0.26, 0.032, 24, 16)
    pest.rotation_euler = (0, math.radians(-55), 0)
    pest.location = (0.05, 0.0, 0.18)
    M.apply_transform(pest)
    return [M.assign(M.smooth(bowl), m), M.assign(M.smooth(pest), m)]


def tomatoes_on_board(name):
    parts = round_board(name + "Board", 0.3)
    for k, (x, y, s_) in enumerate(((-0.08, 0.05, 0.12), (0.1, 0.02, 0.11), (0.0, -0.12, 0.1))):
        before = set(bpy.data.objects)
        M.tomato()
        tom = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        put(tom, x, y, 0.05 + 0.82 * s_, s=s_, rz=k * 1.3)
        parts += tom
    for k, (x, y, a) in enumerate(((0.18, -0.12, 30), (-0.2, -0.08, 160))):
        lf = EV.leaf(f"{name}Basil{k}", length=0.12, width=0.07, fold=0.15, curl=0.1, thick=0.008, petiole=0.02)
        put(lf, x, y, 0.055, rz=math.radians(a))
        parts += lf
    return parts


def cheese_wheel(name, r=0.2, h=0.13):
    """Головка пармезана: темная корка с точечной надписью, спереди вырезан клин со светлой зернистой мякотью."""
    rind = Sh(name + "Rind", rough=0.55, coat=0.2)
    dots = rind.remap(rind.voronoi(rind.mapping(None, scale=(1, 1, 3)), 30.0, out="Distance"), 0.12, 0.06)
    rind.color(rind.mix(rind.math("MULTIPLY", dots, 0.6), (0.92, 0.66, 0.28), (0.66, 0.40, 0.14)))
    rind.bump(rind.noise(None, 40.0, 3.0), 0.2, 0.004)
    paste = Sh(name + "Paste", rough=0.6, sss=0.1)
    paste.color(paste.mix(paste.remap(paste.noise(None, 60.0, 3.0), 0.4, 0.7), (1.0, 0.90, 0.56), (0.96, 0.80, 0.42)))
    paste.bump(paste.voronoi(None, 70.0, out="Distance"), 0.35, 0.004)
    w = M.cylinder(name, r, h, 96)
    w.location = (0, 0, h / 2)
    M.apply_transform(w)
    M.deform(w, lambda co: Vector((co.x * (1 + 0.06 * math.sin(math.pi * co.z / h)), co.y * (1 + 0.06 * math.sin(math.pi * co.z / h)), co.z)))
    M.bevel(w, 0.03, 4, 30)
    wedge = M.profile_prism(name + "Cut", [(0.0, 0.0), (0.5 * math.cos(math.radians(-70)), 0.5 * math.sin(math.radians(-70))),
                                           (0.5 * math.cos(math.radians(-25)), 0.5 * math.sin(math.radians(-25)))], 1.0, -0.3)
    M.boolean_cut(w, [wedge])
    M.smooth(w, 30)
    M.assign(w, rind.mat)
    faces_mat(w, [(lambda c, n: abs(n.z) < 0.6 and abs(n.x * c.x + n.y * c.y) < 0.5 * max(1e-6, math.hypot(c.x, c.y)),
                   paste.mat)])
    return [w]


def dress_italy(st, kenney, metal_mat):
    """Италия: терракотовая плитка котто, косички чеснока и перца, кьянти, спагетти, мока, мраморная столешница."""
    P = []
    P += hang_utensils(kenney, metal_mat, xs=(-0.36, -0.02, 0.32, 0.64))
    for x in (-1.12, 1.18):
        P.append(s_hook(f"HookG{x}", x, metal_mat))
    P += put(garlic_braid("Garlic"), -1.12, 0.40, RAIL_Z - 0.13, s=1.1)
    P += put(chili_string("Chili"), 1.18, 0.40, RAIL_Z - 0.13, s=1.05)
    P += L(fiasco("Chianti"), -1.88, 0.26, s=1.05)
    P += L(spaghetti_jar("Spag"), -1.42, 0.24)
    P += put(deco_plate("Plate", 0.3, (0.99, 0.95, 0.84), (0.16, 0.38, 0.70)), -0.85, 0.47, LEDGE_TOP + 0.3 * 0.97,
             rx=math.radians(76))
    P += L(tomato_tin("Tin"), -0.86, 0.12)
    P += L(tomato_tin("Tin2"), -0.6, 0.2, rz=0.6)
    P += L(herb_plant("Basil", 0.12, 0.2, n=13, size=1.0, seed=11), 0.12, 0.26)
    P += L(bottle_oil("Oil", 0.5, 0.07), 0.66, 0.24)
    P += L(cheese_wheel("Parm"), 1.18, 0.22)
    P += L(pepper_mill("Mill", wood=((0.62, 0.34, 0.18), (0.40, 0.20, 0.10))), 1.84, 0.24)
    P += Cn(tomatoes_on_board("Toms"), -1.6, -0.25, s=1.15)
    P += Cn(mortar("Mortar"), -0.72, -0.15, s=1.15)
    P += Cn(fruit_bowl("Lemons", (0.99, 0.95, 0.84), (0.16, 0.38, 0.70), kinds=("lemon", "lemon", "orange", "lemon",
                                                                             "lemon")), 0.1, -0.32)
    P += Cn(moka("Moka"), 0.98, -0.15, s=1.25)
    P += Cn(herb_plant("Basil2", 0.13, 0.22, n=12, seed=2), 1.74, -0.05)
    return P


DRESS["italy"] = dress_italy
STYLE_EXTRA["italy"] = dict(layout="cotto", tile_rough=0.3, tile_coat=0.15, val_jitter=0.12, hue_jitter=0.02, mottle=0.2,
                            mottle_scale=6.0, edge=0.25, tilt=1.2, pillow=0.004, bevel=0.016, gap=0.02,
                            accent=((0.62, 0.25, 0.10), 0.07), bracket="iron", handle="knob",
                            top_mat="marble")


# MARK: - Закусочная

def chrome(name):
    sh = Sh(name, rough=0.08, metal=1.0, coat=0.3, coat_rough=0.03)
    sh.color((0.92, 0.93, 0.95))
    sh.rough_vary(0.05, 0.14, scale=6.0)
    return sh.mat


def milkshake(name, shake=(0.98, 0.62, 0.72)):
    """Молочный коктейль: стакан на ножке с ребрами, шапка сливок спиралью, вишня, трубочка в полоску."""
    glass = lathe_s(name, [(0.07, 0.0), (0.075, 0.01), (0.02, 0.03), (0.018, 0.08), (0.04, 0.1), (0.075, 0.2),
                           (0.085, 0.3), (0.088, 0.33)], 64, 4)

    def flutes(co, n):
        if co.z < 0.1:
            return 0.0
        return 0.004 * math.cos(math.atan2(co.y, co.x) * 12)
    M.push_normals(glass, flutes)
    M.assign(M.smooth(glass), glass_mat(name + "G", tint=(0.96, 0.98, 1.0), center=0.12))
    glass.visible_shadow = False
    fill = lathe_s(name + "Fill", [(0.03, 0.095), (0.068, 0.19), (0.078, 0.3), (0.06, 0.32), (0.0, 0.325)], 48, 4)
    M.assign(M.smooth(fill), ceramic(name + "Shake", shake, rough=0.35, coat=0.3, mottle=0.04))
    cream = M.lathe(name + "Cream", [(0.0, 0.3)] + [(0.085 * (1 - k / 24) + 0.012 * math.sin(k * 1.3) ** 2, 0.3 + 0.13 * (k / 24) ** 0.9)
                                                    for k in range(25)] + [(0.0, 0.43)], 48)
    M.deform(cream, lambda co: co + Vector((0, 0, 0.012 * math.sin(math.atan2(co.y, co.x) * 3 + co.z * 60))))
    M.smooth(cream)
    M.assign(cream, ceramic(name + "CreamM", (1.0, 0.98, 0.95), rough=0.4, coat=0.2, mottle=0.02))
    cherry = M.sphere(name + "Cherry", 0.032, 24, 12)
    cherry.location = (0.0, -0.01, 0.46)
    M.apply_transform(cherry)
    stem = EV.sweep(name + "Stem", EV.spline([(0.0, -0.01, 0.48), (0.01, -0.01, 0.52), (0.03, -0.01, 0.55)], 4), 0.004)
    straw = EV.sweep(name + "Straw", [(0.03 + 0.04 * t / 10, 0.0, 0.15 + 0.42 * t / 10) for t in range(11)], 0.011, segs=12)
    ssh = Sh(name + "StrawM", rough=0.25, coat=0.6)
    u, v, _ = ssh.xyz(ssh.tc("UV"))
    stripe = ssh.math("GREATER_THAN", ssh.math("PINGPONG", ssh.math("ADD", ssh.math("MULTIPLY", u, 18.0), v), 0.5), 0.25)
    ssh.color(ssh.mix(stripe, (0.98, 0.98, 0.98), (0.92, 0.16, 0.20)))
    return [glass, fill, cream, M.assign(M.smooth(cherry), I.toy(name + "ChM", (0.86, 0.06, 0.12), rough=0.08, coat=1.0)),
            M.assign(stem, I.toy(name + "StM", (0.40, 0.22, 0.10))), M.assign(straw, ssh.mat)]


def squeeze_bottle(name, color):
    m = I.toy(name + "M", color, rough=0.18, coat=0.8)
    body = lathe_s(name, [(0.055, 0.0), (0.062, 0.02), (0.062, 0.2), (0.05, 0.24), (0.028, 0.26)], 48, 4)
    cap = lathe_s(name + "Cap", [(0.03, 0.25), (0.03, 0.29), (0.014, 0.33), (0.006, 0.37), (0.0, 0.375)], 32, 3)
    return [M.assign(M.smooth(body), m), M.assign(M.smooth(cap), m)]


def napkin_holder(name):
    ch = chrome(name + "Cr")
    body = rbox(name, 0.28, 0.12, 0.18, ch, bev=0.035, segs=4)
    nap = rbox(name + "Nap", 0.22, 0.1, 0.06, ceramic(name + "N", (0.99, 0.99, 0.98), rough=0.8, coat=0.0, mottle=0.0),
               bev=0.01, loc=(0, 0, 0.16))
    win = rbox(name + "Win", 0.2, 0.01, 0.09, ceramic(name + "W", (0.99, 0.99, 0.98), rough=0.7, coat=0.0, mottle=0.0),
               bev=0.004, loc=(0, -0.058, 0.05))
    return [body, nap, win]


def sugar_pourer(name):
    gl = lathe_s(name, [(0.055, 0.0), (0.06, 0.01), (0.06, 0.16), (0.055, 0.17)], 48, 3)
    M.assign(M.smooth(gl), glass_mat(name + "G"))
    gl.visible_shadow = False
    fill = lathe_s(name + "F", [(0.05, 0.008), (0.05, 0.11), (0.0, 0.112)], 32, 2)
    M.assign(M.smooth(fill), fill_mat(name + "S", "sugar"))
    top = lathe_s(name + "T", [(0.062, 0.16), (0.064, 0.18), (0.04, 0.23), (0.0, 0.235)], 48, 3)
    sp = M.cylinder(name + "Sp", 0.008, 0.08, 12)
    sp.rotation_euler = (0, math.radians(35), 0)
    sp.location = (0.03, 0.0, 0.24)
    M.apply_transform(sp)
    ch = chrome(name + "C")
    return [gl, fill, M.assign(M.smooth(top), ch), M.assign(M.smooth(sp), ch)]


def cake_dome(name):
    """Тортница на ножке со стеклянным колпаком, внутри вишневый пирог."""
    stand = lathe_s(name, [(0.12, 0.0), (0.1, 0.02), (0.04, 0.05), (0.035, 0.12), (0.06, 0.135), (0.3, 0.14), (0.31, 0.155),
                           (0.29, 0.16), (0.0, 0.16)], 96, 4)
    M.assign(M.smooth(stand), ceramic(name + "St", (0.98, 0.97, 0.94), rough=0.12))
    before = set(bpy.data.objects)
    M.pie()
    pie = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
    put(pie, 0, 0, 0, rx=math.radians(-30))
    put(pie, 0, 0, 0.16, s=0.24)
    dome = lathe_s(name + "Dome", [(0.3, 0.155), (0.3, 0.2), (0.28, 0.32), (0.2, 0.42), (0.08, 0.46), (0.0, 0.465)], 96, 5)
    M.assign(M.smooth(dome), glass_mat(name + "G", center=0.02, rim=0.7))
    dome.visible_shadow = False
    kn = M.sphere(name + "Kn", 0.035, 24, 12)
    kn.location = (0, 0, 0.49)
    M.apply_transform(kn)
    return [stand, dome, M.assign(M.smooth(kn), chrome(name + "KnM"))] + pie


def toaster(name, color=(0.92, 0.93, 0.95)):
    ch = chrome(name + "Cr")
    body = rbox(name, 0.42, 0.24, 0.26, ch, bev=0.07, segs=6)
    dark = ceramic(name + "D", (0.10, 0.10, 0.11), rough=0.3, coat=0.4, mottle=0.0)
    parts = [body]
    toast = bread_mat(name + "Toast", (0.78, 0.48, 0.20), (0.96, 0.80, 0.52))
    for k, x in enumerate((-0.08, 0.08)):
        parts.append(rbox(f"{name}Slot{k}", 0.05, 0.17, 0.02, dark, bev=0.008, loc=(x, 0.0, 0.255)))
        sl = I.slab(f"{name}T{k}", M3.round_poly([(-0.07, 0.0), (0.07, 0.0), (0.075, 0.13), (0.0, 0.16), (-0.075, 0.13)], 0.03, 6),
                    0.03, 0.01, toast.mat)
        put([sl], 0, 0, 0, rz=math.radians(90))
        put([sl], x, 0.0, 0.2)
        parts.append(sl)
    lever = rbox(name + "Lever", 0.03, 0.06, 0.04, dark, bev=0.01, loc=(0.23, 0.0, 0.16))
    knob_ = M.cylinder(name + "Knob", 0.02, 0.02, 24)
    knob_.rotation_euler = (math.radians(90), 0, 0)
    knob_.location = (0.12, -0.125, 0.08)
    M.apply_transform(knob_)
    parts += [lever, M.assign(M.smooth(knob_), dark)]
    return parts


def coffee_pot(name):
    gl = lathe_s(name, [(0.08, 0.0), (0.12, 0.03), (0.13, 0.1), (0.1, 0.17), (0.07, 0.2), (0.075, 0.22)], 64, 5)
    M.assign(M.smooth(gl), glass_mat(name + "G"))
    gl.visible_shadow = False
    cof = lathe_s(name + "C", [(0.08, 0.008), (0.115, 0.03), (0.122, 0.09), (0.0, 0.092)], 48, 3)
    M.assign(M.smooth(cof), ceramic(name + "CoffeeM", (0.30, 0.15, 0.07), rough=0.1, coat=0.8, mottle=0.0))
    dark = ceramic(name + "D", (0.10, 0.10, 0.11), rough=0.3, coat=0.4, mottle=0.0)
    collar = lathe_s(name + "Col", [(0.076, 0.17), (0.082, 0.2), (0.08, 0.25), (0.05, 0.27), (0.0, 0.272)], 48, 3)
    hd = EV.sweep(name + "Hd", EV.spline([(-0.08, 0.0, 0.22), (-0.17, 0.0, 0.2), (-0.17, 0.0, 0.08), (-0.11, 0.0, 0.05)], 6),
                  0.016, segs=12)
    return [gl, cof, M.assign(M.smooth(collar), dark), M.assign(hd, dark)]


def spindle_mixer(name, color=(0.56, 0.86, 0.76)):
    """Ретро-миксер для коктейлей: мятная стойка, мотор сверху, стальной стакан на подставке."""
    body = ceramic(name + "M", color, rough=0.14, coat=0.8)
    ch = chrome(name + "Cr")
    base = rbox(name + "Base", 0.22, 0.26, 0.06, body, bev=0.025)
    col = rbox(name + "Col", 0.09, 0.09, 0.48, body, bev=0.035, loc=(0.0, 0.06, 0.04))
    head = M.capsule(name + "Head", 0.3, 0.07, 32, 16)
    head.location = (0.05, 0.0, 0.52)
    M.apply_transform(head)
    M.assign(M.smooth(head), body)
    band_ = M.torus(name + "Band", 0.072, 0.01, 32, 8)
    band_.rotation_euler = (0, math.radians(90), 0)
    band_.location = (0.12, 0.0, 0.52)
    M.apply_transform(band_)
    sp = M.cylinder(name + "Spindle", 0.008, 0.2, 12)
    sp.location = (0.12, 0.0, 0.38)
    M.apply_transform(sp)
    cup = shell(name + "Cup", [(0.045, 0.06), (0.05, 0.07), (0.065, 0.24), (0.06, 0.245), (0.04, 0.08)], 48, 3)
    put([cup], 0.12, 0.0, 0.0)
    return [base, col, head, M.assign(M.smooth(band_), ch), M.assign(sp, ch), M.assign(M.smooth(cup), ch)]


def laminate_sh(name):
    """Ретро-пластик столешницы: сливочный фон, бирюзовые и розовые "бумеранги", золотые крапинки."""
    sh = Sh(name, rough=0.22, coat=0.5)
    cell = sh.voronoi(None, 6.0, out="Color")
    dist = sh.voronoi(None, 6.0, out="Distance")
    r, g, b = sh.xyz(cell)
    shape = sh.remap(dist, 0.16, 0.12)
    pick = sh.math("GREATER_THAN", r, 0.55)
    col = sh.mix(sh.math("MULTIPLY", shape, pick), (0.98, 0.95, 0.88),
                 sh.mix(sh.math("GREATER_THAN", g, 0.5), (0.98, 0.62, 0.66), (0.40, 0.80, 0.78)))
    fleck = sh.remap(sh.noise(None, 80.0, 2.0), 0.7, 0.72)
    col = sh.mix(sh.math("MULTIPLY", fleck, 0.7), col, (0.90, 0.72, 0.30))
    sh.color(col)
    return sh.mat


def dress_diner(st, kenney, metal_mat):
    """Закусочная 50-х: сливочная плитка с шахматными поясами, хром, коктейли, кетчуп и горчица, пирог под колпаком."""
    P = []
    P += hang_utensils(kenney, metal_mat)
    P += L(milkshake("ShakePink"), -1.98, 0.24)
    P += L(milkshake("ShakeChoc", (0.62, 0.38, 0.24)), -1.68, 0.3)
    P += L(squeeze_bottle("Ketchup", (0.90, 0.10, 0.10)), -1.2, 0.24)
    P += L(squeeze_bottle("Mustard", (1.0, 0.78, 0.10)), -1.0, 0.28)
    P += L(plate_stack("Plates", 4, 0.2, ceramic("PlW", (0.99, 0.98, 0.95)), ceramic("PlR", (0.86, 0.10, 0.12))), -0.42, 0.24)
    P += L(napkin_holder("Napkins"), 0.16, 0.26)
    P += L(sugar_pourer("Sugar"), 0.62, 0.24)
    P += kenney("shaker-salt", (0.92, 0.2, LEDGE_TOP), 1.45)
    P += kenney("shaker-pepper", (1.1, 0.24, LEDGE_TOP), 1.45)
    P += L(mug("Mug1", (0.99, 0.98, 0.95)), 1.42, 0.24)
    P += L(mug("Mug2", (0.99, 0.98, 0.95)), 1.58, 0.3, rz=1.2)
    P += L(spindle_mixer("Mixer"), 1.92, 0.22, s=1.05)
    P += Cn(cake_dome("Cake"), -1.6, -0.2, s=1.1)
    P += Cn(toaster("Toaster"), -0.62, -0.1, rz=math.radians(8))
    P += Cn(milkshake("ShakeMint", (0.62, 0.90, 0.76)), 0.1, -0.35)
    P += Cn(coffee_pot("Coffee"), 0.95, -0.2, s=1.2)
    P += Cn(napkin_holder("Napkins2"), 1.75, -0.1, rz=math.radians(-15))
    return P


DRESS["diner"] = dress_diner
STYLE_EXTRA["diner"] = dict(layout="checker", band=((2.25, 2.9), (-3.9, -2.75)), stripe=((1.95, 2.25), (-2.75, -2.45)),
                            check=((0.90, 0.86, 0.78), (0.035, 0.035, 0.045)), stripe_col=(0.70, 0.04, 0.05),
                            tiles=((0.92, 0.89, 0.82), (0.86, 0.82, 0.74), (0.55, 0.55, 0.55)),
                            val_jitter=0.06, mottle=0.12, edge=0.2, tilt=0.6, handle="bar", top_mat="laminate",
                            edge_mat="chrome", metal="chrome", tile_rough=0.08)


# MARK: - Зима

def needle_sprig(name, n=7, L=0.07, seed=0, mat=None):
    rnd = random.Random(seed)
    parts = []
    for k in range(n):
        c = M.lathe(f"{name}{k}", [(0.0, 0.0), (0.009, 0.004), (0.006, L * 0.6), (0.0, L)], 6)
        put([c], 0, 0, 0, rx=rnd.uniform(-1.3, 1.3), ry=rnd.uniform(-1.3, 1.3), rz=rnd.uniform(0, 6.28))
        M.apply_transform(c)
        parts.append(c)
    # один меш на веточку: меньше объектов
    for o in parts:
        o.select_set(False)
    bpy.context.view_layer.objects.active = parts[0]
    for o in parts:
        o.select_set(True)
    bpy.ops.object.join()
    ob = bpy.context.view_layer.objects.active
    ob.name = name
    M.smooth(ob)
    return M.assign(ob, mat)


def pine_mat(name):
    sh = Sh(name, rough=0.45, sss=0.1, coat=0.3)
    sh.color(sh.mix(sh.remap(sh.noise(None, 20.0, 3.0), 0.3, 0.7), (0.08, 0.30, 0.16), (0.20, 0.50, 0.26)))
    return sh.mat


def bauble(name, r, color):
    b = M.sphere(name, r, 24, 12)
    m = I.toy(name + "M", color, rough=0.08, coat=1.0, metal=0.3)
    cap = M.cylinder(name + "Cap", r * 0.3, r * 0.3, 12)
    cap.location = (0, 0, r * 1.0)
    M.apply_transform(cap)
    return [M.assign(M.smooth(b), m), M.assign(M.smooth(cap), metal(name + "CapM", (0.98, 0.78, 0.36), rough=0.2))]


def pine_garland(name, pts, density=0.03, seed=2, baubles=()):
    """Еловая гирлянда вдоль кривой: веточки из хвоинок, шарики, ягоды."""
    rnd = random.Random(seed)
    wpts = [Vector(p) for p in EV.spline(pts, 10)]
    mat = pine_mat(name + "Pine")
    parts = []
    cum = [0.0]
    for a, b in zip(wpts, wpts[1:]):
        cum.append(cum[-1] + (b - a).length)
    Ltot = cum[-1]
    import bisect as _b
    n = int(Ltot / density)
    template = needle_sprig(name + "Tpl", 9, 0.085, seed, mat)
    for k in range(n):
        s = Ltot * k / n
        i = min(max(_b.bisect_right(cum, s) - 1, 0), len(wpts) - 2)
        p = wpts[i].lerp(wpts[i + 1], (s - cum[i]) / max(1e-6, cum[i + 1] - cum[i]))
        for j in range(2):
            ob = template.copy()
            ob.data = template.data
            bpy.context.scene.collection.objects.link(ob)
            ob.matrix_world = (Matrix.Translation(p + Vector((rnd.uniform(-0.02, 0.02), rnd.uniform(-0.03, 0.01),
                                                                 rnd.uniform(-0.02, 0.02))))
                               @ Euler((rnd.uniform(0, 6.28), rnd.uniform(0, 6.28), rnd.uniform(0, 6.28))).to_matrix().to_4x4()
                               @ Matrix.Scale(rnd.uniform(0.9, 1.25), 4))
            parts.append(ob)
    bpy.data.objects.remove(template)
    for k, (t, col, r) in enumerate(baubles):
        s = Ltot * t
        i = min(max(_b.bisect_right(cum, s) - 1, 0), len(wpts) - 2)
        p = wpts[i].lerp(wpts[i + 1], (s - cum[i]) / max(1e-6, cum[i + 1] - cum[i]))
        b = bauble(f"{name}Ball{k}", r, col)
        put(b, p.x, p.y - 0.06, p.z - r - 0.02)
        parts += b
    return parts


def fir_tree(name, h=0.6):
    """Елочка в горшке: ярусы-конусы с зубчатым краем, шарики, золотая звезда."""
    parts = []
    pot = shell(name + "Pot", [(0.08, 0.0), (0.09, 0.01), (0.11, 0.12), (0.12, 0.13), (0.115, 0.14), (0.1, 0.12)], 48, 3)
    M.assign(M.smooth(pot), ceramic(name + "PotM", (0.86, 0.16, 0.18), rough=0.2))
    parts.append(pot)
    trunk = M.cylinder(name + "Trunk", 0.02, 0.1, 12)
    trunk.location = (0, 0, 0.17)
    M.apply_transform(trunk)
    parts.append(M.assign(trunk, wood_sh(name + "TrunkM", (0.56, 0.36, 0.20), (0.40, 0.24, 0.12), axis="z")))
    pm = pine_mat(name + "Pine")
    tiers = [(0.18, 0.2, 0.2), (0.15, 0.32, 0.18), (0.11, 0.43, 0.16), (0.07, 0.53, 0.12)]
    for k, (r, z, th) in enumerate(tiers):
        c = M.lathe(f"{name}T{k}", [(0.0, z - 0.02), (r, z), (r * 0.6, z + th * 0.45), (0.0, z + th)], 64)
        M.subdivide(c, 1)
        M.deform(c, lambda co, r=r, z=z: co + Vector((0, 0, -0.025 * (0.5 + 0.5 * math.cos(math.atan2(co.y, co.x) * 9))
                                                      * min(1.0, math.hypot(co.x, co.y) / r) ** 3)))
        M.push_normals(c, lambda co, n: 0.006 * M.fbm(co * 40))
        M.smooth(c)
        parts.append(M.assign(c, pm))
    cols = [(0.92, 0.16, 0.20), (0.98, 0.78, 0.24), (0.30, 0.56, 0.92), (0.92, 0.16, 0.20), (0.98, 0.78, 0.24)]
    for k, (a, z, r) in enumerate(((-100, 0.24, 0.15), (-60, 0.35, 0.12), (-130, 0.37, 0.115), (-80, 0.46, 0.085),
                                   (-30, 0.25, 0.155))):
        b = bauble(f"{name}B{k}", 0.025, cols[k])
        put(b, r * math.cos(math.radians(a)), r * math.sin(math.radians(a)), z)
        parts += b
    star = I.slab(name + "Star", I.star_pts(0.06, 0.028), 0.025, 0.008, I.gold())
    put([star], 0, 0, 0.68)
    parts.append(star)
    return parts


def ginger_sh(name):
    sh = Sh(name, rough=0.55, coat=0.15)
    n = sh.noise(None, 30.0, 3.0)
    sh.color(sh.mix(sh.remap(n, 0.3, 0.7), (0.62, 0.34, 0.14), (0.78, 0.48, 0.22)))
    sh.bump(sh.noise(None, 60.0, 3.0), 0.3, 0.004)
    return sh.mat


def icing_mat(name):
    return ceramic(name, (1.0, 0.99, 0.97), rough=0.3, coat=0.4, mottle=0.0)


def gingerbread_house(name):
    """Пряничный домик фасадом к камере: щипец, два ската под снегом, глазурь по карнизу, окна светятся."""
    gm = ginger_sh(name + "G")
    ic = icing_mat(name + "I")
    W, D, H = 0.3, 0.26, 0.17
    ang = math.radians(40)
    parts = [rbox(name, W, D, H, gm, bev=0.012)]
    rise = (W / 2) * math.tan(ang)
    gable = M.profile_prism(name + "Gable", [(-W / 2, 0.0), (W / 2, 0.0), (0.0, rise)], D, -D / 2)
    gable.rotation_euler = (math.radians(90), 0, 0)
    gable.location = (0, 0, H - 0.002)
    M.apply_transform(gable)
    M.bevel(gable, 0.008, 2, 30)
    parts.append(M.assign(M.smooth(gable, 30), gm))
    span = (W / 2 + 0.05) / math.cos(ang)
    for s_ in (-1, 1):
        for k, (thick, mat, off, grow) in enumerate(((0.03, gm, 0.0, 0.0), (0.024, ic, 0.026, 0.012))):
            sl = rbox(f"{name}Roof{s_}{k}", span + grow, D + 0.07 + grow, thick, mat, bev=0.01 if k == 0 else 0.011,
                      loc=(0, 0, -thick / 2))
            nrm = Vector((s_ * math.sin(ang), 0.0, math.cos(ang)))
            c = Vector((s_ * span / 2 * math.cos(ang) - s_ * 0.012, 0.0, H + rise - span / 2 * math.sin(ang) + 0.012)) + nrm * (0.015 + off)
            put([sl], 0, 0, 0, ry=s_ * ang)
            put([sl], c.x, c.y, c.z)
            parts.append(sl)
    # глазурь каплями по переднему краю крыши
    pts = []
    for k in range(25):
        t = k / 24
        x = -W / 2 - 0.05 + (W + 0.1) * t
        z = H + rise - abs(x) * math.tan(ang) + 0.02 - 0.012 * abs(math.sin(k * 1.9))
        pts.append((x, -D / 2 - 0.045, z))
    parts.append(M.assign(EV.sweep(name + "Icing", pts, 0.009, segs=8), ic))
    door = rbox(name + "Door", 0.07, 0.01, 0.1, ceramic(name + "Dr", (0.90, 0.22, 0.24)), bev=0.008, loc=(0, -D / 2 - 0.004, 0.0))
    parts.append(door)
    glow = glow_mat(name + "Win", (1.0, 0.82, 0.40), 2.5)
    for x in (-0.095, 0.095):
        parts.append(rbox(f"{name}W{x}", 0.05, 0.01, 0.05, glow, bev=0.006, loc=(x, -D / 2 - 0.004, 0.08)))
    rw = rbox(name + "RoundWin", 0.05, 0.01, 0.05, glow, bev=0.02, loc=(0, -D / 2 - 0.004, H + 0.02))
    parts.append(rw)
    for k, (x, c) in enumerate(((-0.11, (0.30, 0.70, 0.30)), (-0.035, (0.95, 0.20, 0.25)), (0.035, (1.0, 0.80, 0.20)),
                                (0.11, (0.30, 0.55, 0.95)))):
        d = M.sphere(f"{name}Drop{k}", 0.013, 12, 6)
        d.location = (x, -D / 2 - 0.006, 0.15)
        M.apply_transform(d)
        parts.append(M.assign(d, I.toy(f"{name}DM{k}", c, rough=0.15, coat=0.9)))
    return parts


def candy_cane(name, L=0.32):
    pts = [(0.0, 0.0, L * k / 10) for k in range(11)]
    pts += [(0.045 - 0.045 * math.cos(math.pi * k / 10), 0.0, L + 0.045 * math.sin(math.pi * k / 10)) for k in range(1, 11)]
    pts += [(0.09, 0.0, L - 0.04)]
    ob = EV.sweep(name, pts, 0.014, segs=16)
    sh = Sh(name + "M", rough=0.12, coat=0.9)
    u, v, _ = sh.xyz(sh.tc("UV"))
    st_ = sh.math("GREATER_THAN", sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", u, 22.0), v), 0.5), 0.3)
    sh.color(sh.mix(st_, (0.99, 0.98, 0.96), (0.88, 0.10, 0.14)))
    return [M.assign(ob, sh.mat)]


def cane_jar(name):
    parts = glass_jar(name, 0.24, 0.1, "candy", 0.55, lid=None, label=False)
    for k, (x, a) in enumerate(((-0.03, -12), (0.02, 8), (0.0, 20), (0.04, -4))):
        c = candy_cane(f"{name}C{k}", 0.3 + 0.03 * k)
        put(c, 0, 0, 0, ry=math.radians(a), rz=math.radians(k * 70))
        put(c, x, 0.0, 0.03)
        parts += c
    return parts


def gift(name, w, d, h, color, ribbon):
    m = ceramic(name + "M", color, rough=0.25, coat=0.5, mottle=0.02)
    rm = ceramic(name + "R", ribbon, rough=0.2, coat=0.7, mottle=0.0)
    parts = [rbox(name, w, d, h, m, bev=0.012)]
    parts.append(rbox(name + "Rx", w + 0.006, 0.03, h + 0.006, rm, bev=0.006, loc=(0, 0, -0.003)))
    parts.append(rbox(name + "Ry", 0.03, d + 0.006, h + 0.006, rm, bev=0.006, loc=(0, 0, -0.003)))
    for s in (-1, 1):
        loop = M.torus(f"{name}Bow{s}", 0.03, 0.01, 32, 8)
        loop.scale = (1.0, 0.6, 1.0)
        loop.rotation_euler = (math.radians(90), math.radians(s * 35), 0)
        loop.location = (s * 0.03, 0.0, h + 0.022)
        M.apply_transform(loop)
        parts.append(M.assign(M.smooth(loop), rm))
    return parts


def gingerbread_man(name, s=1.0):
    pts = []
    for k in range(40):
        a = 2 * math.pi * k / 40
        pts.append((0.0 + 0.035 * math.cos(a), 0.085 + 0.035 * math.sin(a)))
    body = [(-0.03, 0.05), (-0.075, 0.035), (-0.08, 0.012), (-0.03, 0.01), (-0.045, -0.06), (-0.025, -0.07),
            (0.0, -0.02), (0.025, -0.07), (0.045, -0.06), (0.03, 0.01), (0.08, 0.012), (0.075, 0.035), (0.03, 0.05)]
    outline = M3.closed_spline(body + [(0.03, 0.06), (0.0, 0.125), (-0.03, 0.06)], 6)
    gm = ginger_sh(name + "G")
    # стоит лицом к камере и чуть откинут назад: камера фона смотрит почти горизонтально
    ob = I.slab(name, outline, 0.022, 0.009, gm)
    ic = icing_mat(name + "I")
    parts = [ob]
    for k, (x, z) in enumerate(((-0.012, 0.09), (0.012, 0.09), (0.0, 0.03), (0.0, 0.0))):
        d = M.sphere(f"{name}D{k}", 0.007, 10, 5)
        d.location = (x, -0.012, z)
        M.apply_transform(d)
        parts.append(M.assign(d, ic))
    smile = EV.sweep(name + "Smile", [(0.012 * math.cos(math.radians(a)), -0.012, 0.08 + 0.008 * math.sin(math.radians(a)))
                                      for a in range(200, 341, 20)], 0.003, segs=6)
    parts.append(M.assign(smile, ic))
    put(parts, 0, 0, 0.07, rx=math.radians(-18))
    return parts


def cookie_plate(name):
    parts = [plate_obj(name, 0.26, ceramic(name + "P", (0.99, 0.98, 0.95)), ceramic(name + "R", (0.86, 0.14, 0.16)))]
    for k, (x, y, a) in enumerate(((-0.1, 0.06, 12), (0.1, 0.05, -10), (0.0, -0.06, 0))):
        g = gingerbread_man(f"{name}G{k}")
        put(g, x, y, 0.03, rz=math.radians(a))
        parts += g
    return parts


def candle(name, r=0.04, h=0.14, wax=(0.99, 0.96, 0.90), glass=True):
    parts = []
    c = lathe_s(name, [(r, 0.0), (r, h - 0.01), (r * 0.9, h), (r * 0.3, h - 0.008), (0.0, h - 0.006)], 32, 3)
    wm = ceramic(name + "W", wax, rough=0.4, coat=0.1, mottle=0.02)
    b = wm.node_tree.nodes["Principled BSDF"]
    b.inputs["Subsurface Weight"].default_value = 0.4
    b.inputs["Subsurface Radius"].default_value = (1.0, 0.6, 0.3)
    b.inputs["Subsurface Scale"].default_value = 0.02
    parts.append(M.assign(M.smooth(c), wm))
    fl = lathe_s(name + "Flame", [(0.0, h + 0.005), (0.011, h + 0.02), (0.008, h + 0.04), (0.0, h + 0.06)], 16, 4)
    parts.append(M.assign(M.smooth(fl), glow_mat(name + "FlM", (1.0, 0.72, 0.30), 18.0)))
    L_ = bpy.data.lights.new(name + "Light", type="POINT")
    L_.energy = 6.0
    L_.color = (1.0, 0.66, 0.32)
    L_.shadow_soft_size = 0.02
    lo = bpy.data.objects.new(name + "Light", L_)
    lo.location = (0, -0.03, h + 0.035)
    bpy.context.scene.collection.objects.link(lo)
    parts.append(lo)
    if glass:
        jar = lathe_s(name + "Jar", [(r + 0.02, 0.0), (r + 0.03, 0.01), (r + 0.032, h * 0.8), (r + 0.03, h + 0.04)], 32, 3)
        M.assign(M.smooth(jar), glass_mat(name + "G", tint=(1.0, 0.95, 0.88)))
        jar.visible_shadow = False
        parts.append(jar)
    return parts


def lantern(name, metal_col=(0.18, 0.17, 0.17)):
    """Фонарь со свечой: металлический каркас, стеклянные стенки, колечко сверху."""
    m = metal(name + "M", metal_col, rough=0.4)
    parts = [rbox(name + "Base", 0.2, 0.2, 0.03, m, bev=0.01)]
    for x in (-0.085, 0.085):
        for y in (-0.085, 0.085):
            parts.append(rbox(f"{name}P{x}{y}", 0.016, 0.016, 0.26, m, bev=0.004, loc=(x, y, 0.03)))
    roof = M.lathe(name + "Roof", [(0.0, 0.29), (0.13, 0.29), (0.0, 0.38)], 4)
    put([roof], 0, 0, 0, rz=math.radians(45))
    M.apply_transform(roof)
    M.bevel(roof, 0.01, 2, 30)
    parts.append(M.assign(M.smooth(roof, 30), m))
    ring = M.torus(name + "Ring", 0.03, 0.008, 24, 8)
    ring.rotation_euler = (math.radians(90), 0, 0)
    ring.location = (0, 0, 0.41)
    M.apply_transform(ring)
    parts.append(M.assign(M.smooth(ring), m))
    gl = rbox(name + "Glass", 0.17, 0.17, 0.26, glass_mat(name + "G", tint=(1.0, 0.97, 0.9), center=0.05, rim=0.5), bev=0.0,
              loc=(0, 0, 0.03))
    gl.visible_shadow = False
    parts.append(gl)
    parts += put(candle(name + "Candle", 0.035, 0.12, glass=False), 0, 0, 0.03)
    return parts


def cocoa_mug(name, color):
    parts = mug(name, color, 0.085, 0.16, fill=(0.46, 0.26, 0.14))
    rnd = random.Random(len(name))
    wm = ceramic(name + "Marsh", (1.0, 0.98, 0.96), rough=0.6, coat=0.0, mottle=0.02)
    for k in range(5):
        mm = rbox(f"{name}Mm{k}", 0.028, 0.028, 0.026, wm, bev=0.008, segs=3)
        put([mm], rnd.uniform(-0.04, 0.04), rnd.uniform(-0.04, 0.04), 0.14, rz=rnd.uniform(0, 3), rx=rnd.uniform(-0.3, 0.3))
        parts.append(mm)
    return parts


def dress_winter(st, kenney, metal_mat):
    """Зима: еловая гирлянда с шарами и огоньками, елочка, пряничный домик, какао, леденцы, подарки."""
    P = []
    y = 0.36
    pts = []
    for k, (x0, x1) in enumerate(((-2.6, -1.3), (-1.3, 0.0), (0.0, 1.3), (1.3, 2.6))):
        pts += catenary(x0, x1, RAIL_Z - 0.02, 0.22, y, 8)[(1 if k else 0):]
    P += pine_garland("Garland", pts, density=0.035, baubles=[(0.12, (0.92, 0.16, 0.20), 0.045), (0.25, (0.98, 0.78, 0.24), 0.04),
                                                               (0.38, (0.92, 0.16, 0.20), 0.05), (0.5, (0.30, 0.56, 0.92), 0.04),
                                                               (0.62, (0.92, 0.16, 0.20), 0.05), (0.75, (0.98, 0.78, 0.24), 0.04),
                                                               (0.88, (0.92, 0.16, 0.20), 0.045)])
    P += string_lights("Lights", [(p[0], p[1] - 0.06, p[2] + 0.01 * math.sin(p[0] * 9)) for p in pts], 26,
                       bulb=(1.0, 0.74, 0.40), strength=3.5)
    for x in (-1.3, 0.0, 1.3):
        bow = M.torus(f"Tie{x}", 0.035, 0.012, 24, 8)
        bow.rotation_euler = (math.radians(90), 0, 0)
        bow.location = (x, 0.3, RAIL_Z - 0.02)
        M.apply_transform(bow)
        P.append(M.assign(M.smooth(bow), ceramic(f"TieM{x}", (0.86, 0.12, 0.16), rough=0.3)))
    P += L(fir_tree("Tree"), -1.86, 0.26, s=1.05)
    P += L(cocoa_mug("Cocoa1", (0.86, 0.16, 0.18)), -1.34, 0.22)
    P += L(cocoa_mug("Cocoa2", (0.98, 0.97, 0.94)), -1.06, 0.3, rz=0.8)
    P += L(gingerbread_house("House"), -0.38, 0.26, s=1.1)
    P += L(candle("Candle", 0.045, 0.16), 0.3, 0.22)
    P += L(cane_jar("Canes"), 0.78, 0.24)
    P += L(gift("Gift1", 0.26, 0.22, 0.18, (0.20, 0.50, 0.40), (0.98, 0.84, 0.40)), 1.5, 0.26)
    P += put(gift("Gift2", 0.18, 0.16, 0.13, (0.88, 0.16, 0.20), (0.99, 0.97, 0.94)), 1.52, 0.26, LEDGE_TOP + 0.18 * LS + 0.004,
             rz=0.35, s=LS)
    P += L(gift("Gift3", 0.14, 0.14, 0.2, (0.30, 0.52, 0.86), (0.98, 0.84, 0.40)), 1.9, 0.24, rz=-0.3)
    P += Cn(cookie_plate("Cookies"), -1.6, -0.25, s=1.2)
    P += Cn(crock("Crock", (0.94, 0.96, 0.99)), -0.8, -0.05, s=1.1)
    P += Cn(fruit_bowl("Clementines", (0.98, 0.97, 0.94), (0.86, 0.14, 0.16), kinds=("orange", "orange", "orange", "orange",
                                                                                   "orange")), 0.06, -0.32, s=1.05)
    P += Cn(kettle("Kettle", (0.88, 0.16, 0.18), handle_col=(0.15, 0.12, 0.1)), 0.95, -0.15, rz=math.radians(-10))
    P += Cn(lantern("Lantern"), 1.76, -0.05, s=1.2)
    return P


DRESS["winter"] = dress_winter
STYLE_EXTRA["winter"] = dict(layout="subway", edge=0.45, edge_col=(0.86, 0.93, 1.0), val_jitter=0.12, hue_jitter=0.02,
                             mottle=0.22, tiles=((0.40, 0.62, 0.90), (0.32, 0.54, 0.84), (0.93, 0.96, 1.0)),
                             handle="knob", world_k=0.95, bloom=True)


# MARK: - Ночь

def dress_night(st, kenney, metal_mat):
    """Ночная кухня: темная глянцевая плитка, теплая подсветка под полкой, гирлянда на рейлинге, фонарь и свечи."""
    P = []
    P += hang_utensils(kenney, metal_mat)
    pts = []
    for k, (x0, x1) in enumerate(((-2.6, -1.0), (-1.0, 0.9), (0.9, 2.6))):
        pts += catenary(x0, x1, RAIL_Z + 0.02, 0.3, 0.38, 10)[(1 if k else 0):]
    P += string_lights("Lights", pts, 22, bulb=(1.0, 0.70, 0.36), wire=(0.08, 0.07, 0.06), strength=3.5)
    P += L(lantern("Lantern", (0.70, 0.52, 0.26)), -1.88, 0.26, s=1.05)
    P += L(glass_jar("Honey", 0.3, 0.1, "cookies", 0.65, lid="metal", lid_col=(0.85, 0.66, 0.32)), -1.36, 0.22)
    P += L(glass_jar("Coffee", 0.4, 0.1, "coffee", 0.8, lid="wood"), -1.06, 0.18)
    P += L(bowl_stack("Bowls", 3, 0.16, 0.1, ceramic("BowlW", (0.95, 0.92, 0.86)), ceramic("BowlRim", (0.14, 0.20, 0.40))),
           -0.42, 0.24)
    P += L(herb_plant("Plant", 0.12, 0.2, n=12, seed=13), 0.12, 0.26)
    P += L(candle("Candle1", 0.04, 0.18, glass=False), 0.62, 0.24)
    P += L(candle("Candle2", 0.04, 0.12, glass=False), 0.74, 0.3)
    P += L(books("Books", [(0.075, 0.46, (0.30, 0.22, 0.48)), (0.09, 0.5, (0.74, 0.30, 0.22)),
                           (0.07, 0.42, (0.86, 0.68, 0.30)), (0.08, 0.44, (0.22, 0.42, 0.36))]), 1.2, 0.28)
    P += L(pepper_mill("Mill"), 1.66, 0.24)
    P += L(mug("Mug", (0.20, 0.30, 0.56)), 1.98, 0.24)
    P += Cn(kettle("Kettle", (0.20, 0.30, 0.56), handle_col=(0.12, 0.10, 0.09)), -1.6, -0.15, rz=math.radians(-10))
    P += Cn(cocoa_mug("Cocoa1", (0.95, 0.92, 0.86)), -0.86, -0.25)
    P += Cn(cocoa_mug("Cocoa2", (0.86, 0.36, 0.26)), -0.6, -0.12, rz=0.9)
    P += Cn(glass_jar("Cookies", 0.34, 0.13, "cookies", 0.75, lid=None, cloth=(0.20, 0.30, 0.56)), 0.08, -0.15)
    P += Cn(round_board("Board"), 0.95, -0.25, rz=math.radians(-8))
    P += put(boule("Bread"), 0.95, -0.25, COUNTER_TOP + 0.05 * CS, s=CS)
    P += Cn(candle("Candle3", 0.05, 0.16), 1.76, -0.1)
    return P


DRESS["night"] = dress_night
STYLE_EXTRA["night"] = dict(layout="subway", edge=0.35, edge_col=(0.22, 0.28, 0.46), val_jitter=0.16, hue_jitter=0.012,
                            mottle=0.25, tile_rough=0.08, tile_coat=0.6, lamps=True, strip_e=60, wash_e=70,
                            key_k=0.45, world_k=1.25, bloom=True, handle="knob",
                            wood_mat="dark", top_mat="dark")
