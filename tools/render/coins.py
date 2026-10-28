"""Монеты, кучи монет и сундуки с картами для магазина и альбома.

Кучи насыпаются физикой Blender (rigid body): монеты падают на невидимый холм,
ложатся естественно и не проходят друг сквозь друга.
Подключается из models.py: функции попадают в MODELS.
"""
import math
import os
import random

import bpy
import bmesh
from mathutils import Euler, Matrix, Vector

import models as M

FONT = "/usr/share/fonts/truetype/google-fonts/Poppins-Bold.ttf"
COIN_R = 0.42


# MARK: - Свет и материалы

def gold_world(strength=0.7):
    """Окружение с градиентом: светлый верх, темный низ. На металле это дает читаемые переходы."""
    w = bpy.context.scene.world
    nt = w.node_tree
    nodes, links = nt.nodes, nt.links
    bg = nodes["Background"]
    tc = nodes.new("ShaderNodeTexCoord")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(tc.outputs["Generated"], sep.inputs[0])
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = -0.4
    mr.inputs["From Max"].default_value = 0.9
    links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.22, 0.15, 0.1, 1)
    els[1].position, els[1].color = 1.0, (0.95, 0.88, 0.78, 1)
    mid = els.new(0.45)
    mid.color = (0.55, 0.47, 0.38, 1)
    links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bg.inputs["Color"])
    bg.inputs["Strength"].default_value = strength


def world_mat(name, stops, rough=0.3, metal=0.85, coat=0.0, lo=-1.0, hi=1.0):
    """Материал с цветом по нормали в мировых координатах: верх светлее, бока темнее.
    Работает и для повернутых копий монет (у material() нормаль объекта)."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    geo = nodes.new("ShaderNodeNewGeometry")
    sep = nodes.new("ShaderNodeSeparateXYZ")
    links.new(geo.outputs["Normal"], sep.inputs[0])
    mr = nodes.new("ShaderNodeMapRange")
    mr.inputs["From Min"].default_value = lo
    mr.inputs["From Max"].default_value = hi
    links.new(sep.outputs["Z"], mr.inputs["Value"])
    ramp = nodes.new("ShaderNodeValToRGB")
    els = ramp.color_ramp.elements
    els[0].position, els[0].color = stops[0][0], (*M.lin(stops[0][1]), 1)
    els[1].position, els[1].color = stops[-1][0], (*M.lin(stops[-1][1]), 1)
    for pos, col in stops[1:-1]:
        e = els.new(pos)
        e.color = (*M.lin(col), 1)
    links.new(mr.outputs["Result"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    if coat:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.1
    return mat


_GOLD = {}


def gold_set():
    """Три оттенка золота: бортик и буква светлые, поле монеты чуть глубже."""
    if not _GOLD:
        _GOLD["rim"] = world_mat("GoldRim", [(0.0, (0.72, 0.38, 0.04)), (0.5, (1.0, 0.66, 0.10)),
                                             (1.0, (1.0, 0.80, 0.22))], rough=0.28)
        _GOLD["face"] = world_mat("GoldFace", [(0.0, (0.66, 0.34, 0.04)), (0.5, (0.95, 0.58, 0.08)),
                                               (1.0, (1.0, 0.72, 0.16))], rough=0.38)
        _GOLD["mark"] = world_mat("GoldMark", [(0.0, (0.80, 0.46, 0.06)), (0.5, (1.0, 0.74, 0.16)),
                                               (1.0, (1.0, 0.86, 0.34))], rough=0.24)
    return _GOLD


def reset_cache():
    _GOLD.clear()
    _COIN.clear()
    _PROXY.clear()


# MARK: - Монета

def text_mesh(name, text, size, depth, bevel):
    cu = bpy.data.curves.new(name, "FONT")
    cu.body = text
    if os.path.exists(FONT):
        cu.font = bpy.data.fonts.load(FONT, check_existing=True)
    cu.size = size
    cu.align_x = "CENTER"
    cu.align_y = "CENTER"
    cu.extrude = depth
    cu.bevel_depth = bevel
    cu.bevel_resolution = 2
    cu.resolution_u = 8
    ob = M.link(bpy.data.objects.new(name + "Curve", cu))
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg))
    bpy.data.objects.remove(ob)
    return me


_COIN = {}


def coin_mesh(r=COIN_R):
    """Одна сетка на все монеты: толстый диск, выпуклый бортик, утопленное поле, буква S с двух сторон."""
    key = round(r, 3)
    if key in _COIN:
        return _COIN[key]
    k = r / COIN_R
    prof = [(0.0, -0.040), (0.28, -0.040), (0.300, -0.044), (0.318, -0.054), (0.335, -0.060), (0.385, -0.062),
            (0.405, -0.057), (0.417, -0.045), (0.420, -0.030), (0.420, 0.030), (0.417, 0.045), (0.405, 0.057),
            (0.385, 0.062), (0.335, 0.060), (0.318, 0.054), (0.300, 0.044), (0.28, 0.040), (0.0, 0.040)]
    prof = [(a * k, b * k) for a, b in prof]
    segs = 144
    body = M.lathe("CoinBody", prof, segs)
    # насечки на ребре: 36 бороздок по окружности
    for v in body.data.vertices:
        rr = math.hypot(v.co.x, v.co.y)
        if rr > 0.415 * k and abs(v.co.z) < 0.031 * k:
            a = math.atan2(v.co.y, v.co.x)
            cut = 0.012 * k * (0.5 + 0.5 * math.cos(36 * a)) ** 2
            v.co.x *= (rr - cut) / rr
            v.co.y *= (rr - cut) / rr
    bm = bmesh.new()
    bm.from_mesh(body.data)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(body.data)
    bm.free()
    gold = gold_set()
    body.data.materials.append(gold["rim"])
    body.data.materials.append(gold["face"])
    body.data.materials.append(gold["mark"])
    for p in body.data.polygons:
        c = p.center
        if math.hypot(c.x, c.y) < 0.30 * k and abs(p.normal.z) > 0.9:
            p.material_index = 1
    M.smooth(body, 50)
    # буква S сверху и снизу
    depth, bev = 0.008 * k, 0.006 * k
    for side in (1, -1):
        me = text_mesh("CoinS", "S", 0.62 * k, depth, bev)
        ob = M.link(bpy.data.objects.new("CoinMark", me))
        ob.location = (0, 0, side * (0.040 * k + depth))
        if side < 0:
            ob.rotation_euler = (math.pi, 0, 0)
        M.apply_transform(ob)
        ob.data.materials.clear()
        ob.data.materials.append(gold["mark"])
        M.smooth(ob, 40)
        bpy.ops.object.select_all(action="DESELECT")
        ob.select_set(True)
        body.select_set(True)
        bpy.context.view_layer.objects.active = body
        bpy.ops.object.join()
    me = body.data
    me.name = f"Coin{key}"
    bpy.data.objects.remove(body)
    _COIN[key] = me
    return me


def coin(name, matrix=None, r=COIN_R, loc=None, rot=None):
    ob = M.link(bpy.data.objects.new(name, coin_mesh(r)))
    if matrix is not None:
        ob.matrix_world = matrix
    else:
        ob.location = loc or (0, 0, 0)
        ob.rotation_euler = rot or (0, 0, 0)
    return ob


def stack(prefix, x, y, n, rnd, r=COIN_R, z0=0.0, jitter=0.025):
    """Ровная стопка: монеты чуть сдвинуты и повернуты, как сложенные руками."""
    h = 0.124 * r / COIN_R
    out = []
    for i in range(n):
        out.append(coin(f"{prefix}{i}", loc=(x + rnd.uniform(-jitter, jitter), y + rnd.uniform(-jitter, jitter),
                                             z0 + h / 2 + i * h),
                        rot=(rnd.uniform(-0.03, 0.03), rnd.uniform(-0.03, 0.03), rnd.uniform(0, 6.28))))
    return out


# MARK: - Физика

def _rb_world(frames):
    scene = bpy.context.scene
    if scene.rigidbody_world is None:
        bpy.ops.rigidbody.world_add()
    rw = scene.rigidbody_world
    rw.substeps_per_frame = 30
    rw.solver_iterations = 30
    rw.point_cache.frame_start = 1
    rw.point_cache.frame_end = frames
    scene.frame_start = 1
    scene.frame_end = frames
    return rw


def _add_body(obs, kind, shape, friction=0.9, restitution=0.0, mass=1.0):
    bpy.ops.object.select_all(action="DESELECT")
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0]
    bpy.ops.rigidbody.objects_add(type=kind)
    for o in obs:
        rb = o.rigid_body
        rb.collision_shape = shape
        rb.friction = friction
        rb.restitution = restitution
        rb.use_margin = True
        rb.collision_margin = 0.002
        if kind == "ACTIVE":
            rb.mass = mass
            rb.linear_damping = 0.15
            rb.angular_damping = 0.8


_PROXY = {}


def proxy_mesh():
    """Упрощенная монета для физики: 16-гранный цилиндр, столкновения выпуклой оболочкой стабильнее цилиндров."""
    if "m" not in _PROXY or _PROXY["m"].name not in bpy.data.meshes:
        bm = bmesh.new()
        bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=COIN_R, radius2=COIN_R, depth=0.124)
        me = bpy.data.meshes.new("CoinProxy")
        bm.to_mesh(me)
        bm.free()
        _PROXY["m"] = me
    return _PROXY["m"]


def simulate(dynamic, static, frames=360, shapes=None):
    """dynamic: падающие объекты, static: опоры. Возвращает объекты в итоговых позах, физику убирает.
    Монеты на время расчета получают упрощенную сетку."""
    _rb_world(frames)
    shapes = dict(shapes or {})
    swapped = {}
    for o in list(dynamic) + list(static):
        if o.type == "MESH" and o.data.name.startswith("Coin") and o.data.name != "CoinProxy":
            swapped[o.name] = o.data
            o.data = proxy_mesh()
            shapes[o.name] = "CONVEX_HULL"
    groups = {}
    for o in dynamic:
        groups.setdefault(shapes.get(o.name, "CYLINDER"), []).append(o)
    for shape, obs in groups.items():
        _add_body(obs, "ACTIVE", shape)
    sgroups = {}
    for o in static:
        sgroups.setdefault(shapes.get(o.name, "MESH"), []).append(o)
    for shape, obs in sgroups.items():
        _add_body(obs, "PASSIVE", shape)
    scene = bpy.context.scene
    for f in range(1, frames + 1):
        scene.frame_set(f)
    final = {o.name: o.matrix_world.copy() for o in dynamic}
    bpy.ops.rigidbody.world_remove()
    for o in dynamic + static:
        if o.rigid_body:
            bpy.context.view_layer.objects.active = o
            bpy.ops.object.select_all(action="DESELECT")
            o.select_set(True)
            bpy.ops.rigidbody.object_remove()
    for o in dynamic:
        o.matrix_world = final[o.name]
    for o in list(dynamic) + list(static):
        if o.name in swapped:
            o.data = swapped[o.name]
    bpy.context.view_layer.update()
    far = [o.name for o in dynamic if o.matrix_world.translation.length > 6 or o.matrix_world.translation.z < -0.5]
    if far:
        print("simulate: lost", len(far), [(o.name, tuple(round(v, 1) for v in o.matrix_world.translation))
                                           for o in dynamic if o.name in far][:6], flush=True)
        keep = [o for o in dynamic if o.name not in far]
        for o in [o for o in dynamic if o.name in far]:
            bpy.data.objects.remove(o)
        dynamic = keep
    return dynamic


def drop_spawns(n, radius, z0, rnd, cx=0.0, cy=0.0, gap=0.3):
    """Падающие монеты слоями: в слое монеты не касаются друг друга, слои разнесены по высоте."""
    out = []
    layer = 0
    while len(out) < n:
        placed = []
        tries = 0
        while len(out) < n and tries < 60:
            tries += 1
            a = rnd.uniform(0, 6.28)
            d = radius * math.sqrt(rnd.random())
            x, y = cx + d * math.cos(a), cy + d * math.sin(a)
            if all(math.hypot(x - px, y - py) > 2 * COIN_R + 0.06 for px, py in placed):
                placed.append((x, y))
                out.append(((x, y, z0 + layer * gap),
                            (rnd.uniform(-0.12, 0.12), rnd.uniform(-0.12, 0.12), rnd.uniform(0, 6.28))))
        layer += 1
    return out


def mound(name, radius, height, z0=0.0, cx=0.0, cy=0.0, sx=1.0, sy=1.0):
    """Пологий холм под кучей (профиль косинусом: без крутых краев, монеты не соскальзывают)."""
    prof = [(0.0, z0 - 0.02), (radius, z0 - 0.02)]
    for i in range(1, 17):
        t = i / 16
        rr = radius * (1 - t)
        prof.append((rr, z0 + height * (1 + math.cos(math.pi * rr / radius)) / 2))
    ob = M.lathe(name, prof, 48)
    ob.scale = (sx, sy, 1)
    ob.location = (cx, cy, 0)
    M.apply_transform(ob)
    return ob


def ground(name="Ground", size=12.0):
    g = M.box_mesh(name, size, size, 0.2, -0.2)
    return g


def surface_z(x, y, top=20.0):
    """Высота верхней поверхности сцены в точке (луч сверху вниз)."""
    dg = bpy.context.evaluated_depsgraph_get()
    hit, loc, nor, _, _, _ = bpy.context.scene.ray_cast(dg, Vector((x, y, top)), Vector((0, 0, -1)))
    return (loc.z, nor) if hit else (0.0, Vector((0, 0, 1)))


def deposit(prefix, n, radius, rnd, cx=0.0, cy=0.0, sx=1.0, sy=1.0, per_wave=5, frames=70, statics=(),
            ring=None, tilt=0.1):
    """Монеты падают партиями прямо на текущую поверхность и укладываются чешуей.
    ring=(r0, r1): бросать в кольце (для монет вокруг кучи)."""
    placed = []
    statics = list(statics)
    k = 0
    while k < n:
        wave = []
        spots = []
        tries = 0
        while len(wave) < min(per_wave, n - k) and tries < 80:
            tries += 1
            if ring:
                a = rnd.uniform(-2.7, -0.45)
                d = rnd.uniform(*ring)
            else:
                a = rnd.uniform(0, 6.28)
                d = radius * math.sqrt(rnd.random())
            x, y = cx + d * math.cos(a) * sx, cy + d * math.sin(a) * sy
            if any(math.hypot(x - px, y - py) < 2 * COIN_R + 0.04 for px, py in spots):
                continue
            # самая высокая точка под монетой: старт чуть выше, чтобы не задеть соседей
            hz = max(surface_z(x + COIN_R * u, y + COIN_R * v)[0]
                     for u, v in ((0, 0), (1, 0), (-1, 0), (0, 1), (0, -1), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7),
                                  (-0.7, -0.7)))
            spots.append((x, y))
            wave.append(coin(f"{prefix}{k}", loc=(x, y, hz + 0.2),
                             rot=(rnd.uniform(-tilt, tilt), rnd.uniform(-tilt, tilt), rnd.uniform(0, 6.28))))
            k += 1
        if not wave:
            break
        wave = simulate(wave, statics, frames=frames,
                        shapes={**{o.name: "CYLINDER" for o in statics if o.data.name.startswith("Coin")},
                                **{o.name: "BOX" for o in statics if "Ground" in o.name}})
        statics += wave
        placed += wave
    return placed


def coin_pile(prefix, n, radius, height, rnd, z0=0.0, cx=0.0, cy=0.0, extra_static=(), sx=1.0, sy=1.0,
              core_visible=True, spill=0, statics=()):
    """Куча монет: невысокий холм, на него партиями насыпаются монеты. spill: монеты вокруг кучи."""
    core = mound(prefix + "Core", radius, height, z0, cx, cy, sx, sy)
    gr = ground(prefix + "Ground")
    base = [core, gr] + list(extra_static) + list(statics)
    coins_ = deposit(prefix, n, radius, rnd, cx, cy, sx, sy, statics=base)
    if spill:
        coins_ += deposit(prefix + "s", spill, radius, rnd, cx, cy, sx, sy, per_wave=3, statics=base + coins_,
                          ring=(radius * 1.1, radius * 1.45))
    bpy.data.objects.remove(gr)
    # монеты, укатившиеся далеко или назад, без пола выглядят парящими: убираем
    keep = []
    for c in coins_:
        p = c.matrix_world.translation
        dx, dy = (p.x - cx) / sx, (p.y - cy) / sy
        dist = math.hypot(dx, dy)
        if dist > radius * 1.6 or (dy > 0 and dist > radius * 1.05):
            bpy.data.objects.remove(c)
        else:
            keep.append(c)
    coins_ = keep
    if core_visible:
        # холм остается подложкой: в щелях между монетами видно золото
        M.assign(core, gold_set()["face"])
        M.smooth(core)
    else:
        bpy.data.objects.remove(core)
        core = None
    return coins_ + ([core] if core else [])


def shadow_catcher(size=8.0, z=0.0):
    """Пол-ловец тени: в спрайте остается только мягкая тень, сам пол прозрачный."""
    h = size / 2
    pl = M.from_data("ShadowCatcher", [(-h, -h, z), (h, -h, z), (h, h, z), (-h, h, z)], [(0, 1, 2, 3)])
    pl.is_shadow_catcher = True
    # пол не должен подсвечивать монеты снизу и сам не виден в отражениях
    pl.visible_glossy = False
    pl.visible_diffuse = False
    pl["no_bounds"] = True
    return pl


# MARK: - Модели магазина

def _prep():
    reset_cache()
    gold_world()


def coin_icon():
    """Одна монета для интерфейса: почти фронтально, слегка под углом."""
    _prep()
    c = coin("Icon")
    # повернуть ось монеты к камере (камера спереди-сверху), немного довернуть для объема
    cam = Vector((math.sin(M.AZIMUTH) * math.cos(M.ELEVATION), -math.cos(M.AZIMUTH) * math.cos(M.ELEVATION),
                  math.sin(M.ELEVATION)))
    q = cam.to_track_quat("Z", "Y")
    c.matrix_world = q.to_matrix().to_4x4() @ Euler((math.radians(-14), math.radians(10), 0)).to_matrix().to_4x4()
    return [c]


def coins_stack():
    _prep()
    rnd = random.Random(3)
    parts = []
    parts += stack("A", -0.42, 0.18, 8, rnd)
    parts += stack("B", 0.42, 0.12, 6, rnd)
    parts += stack("C", -0.02, -0.42, 4, rnd)
    loose = [coin("L0", loc=(0.30, -0.72, 1.6), rot=(1.2, 0.2, 0.4)),
             coin("L1", loc=(-0.9, -0.55, 2.4), rot=(0.3, 0.1, 1.0))]
    gr = ground("SG")
    loose = simulate(loose, parts + [gr], shapes={gr.name: "BOX"})
    bpy.data.objects.remove(gr)
    return parts + loose + [shadow_catcher()]


def coins_pile():
    _prep()
    rnd = random.Random(8)
    st = stack("P", 1.0, -0.25, 5, rnd)
    parts = coin_pile("H", 28, 0.85, 0.55, rnd, extra_static=st, spill=3)
    return M.rotate_all(parts + st + [shadow_catcher()], (math.radians(16), 0, 0))


def coins_mountain():
    _prep()
    rnd = random.Random(21)
    bars = []
    for i, (x, y, a) in enumerate(((-0.35, 0.1, 0.3), (0.3, 0.25, -0.5))):
        b = gold_bar(f"Bar{i}")
        b.location = (x * 0.8, y * 0.5 - 0.1, 2.0 + i * 0.5)
        b.rotation_euler = (0, 0, a)
        bars.append(b)
    gems = []
    colors = [(0.95, 0.15, 0.30), (0.15, 0.55, 1.0), (0.2, 0.85, 0.4), (0.7, 0.3, 1.0)]
    for i in range(5):
        g = gem(f"Gem{i}", colors[i % 4], 0.2)
        a = rnd.uniform(0, 6.28)
        g.location = (0.35 * math.cos(a), 0.35 * math.sin(a) - 0.2, 2.2 + i * 0.4)
        g.rotation_euler = (rnd.uniform(0, 1), rnd.uniform(0, 1), rnd.uniform(0, 6))
        gems.append(g)
    parts = coin_pile("Mt", 80, 1.35, 1.0, rnd, spill=5)
    core = [p for p in parts if p.name == "MtCore"]
    pile_coins = [p for p in parts if p.name != "MtCore"]
    gr = ground("MG")
    loose = simulate(bars + gems, pile_coins + core + [gr],
             shapes={**{b.name: "BOX" for b in bars}, **{g.name: "CONVEX_HULL" for g in gems},
                     **{p.name: "CYLINDER" for p in pile_coins}, gr.name: "BOX"})
    bpy.data.objects.remove(gr)
    return M.rotate_all(parts + loose + [shadow_catcher()], (math.radians(14), 0, 0))


def gold_bar(name):
    """Слиток: усеченная пирамида с фаской."""
    w0, d0, w1, d1, h = 0.62, 0.32, 0.48, 0.2, 0.18
    verts = [(-w0 / 2, -d0 / 2, 0), (w0 / 2, -d0 / 2, 0), (w0 / 2, d0 / 2, 0), (-w0 / 2, d0 / 2, 0),
             (-w1 / 2, -d1 / 2, h), (w1 / 2, -d1 / 2, h), (w1 / 2, d1 / 2, h), (-w1 / 2, d1 / 2, h)]
    faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    ob = M.from_data(name, verts, faces)
    ob.data.transform(Matrix.Translation((0, 0, -h / 2)))
    M.bevel(ob, 0.025, 3, 30)
    M.bake(ob)
    M.smooth(ob, 40)
    M.assign(ob, gold_set()["rim"])
    return ob


def gem(name, color, r):
    """Граненый камень: корона и павильон."""
    n = 8
    verts = [(0, 0, -r * 0.9)]
    for i in range(n):
        a = 2 * math.pi * i / n
        verts.append((r * math.cos(a), r * math.sin(a), 0))
    for i in range(n):
        a = 2 * math.pi * (i + 0.5) / n
        verts.append((r * 0.6 * math.cos(a), r * 0.6 * math.sin(a), r * 0.35))
    faces = []
    for i in range(n):
        faces.append((0, 1 + (i + 1) % n, 1 + i))
        faces.append((1 + i, 1 + (i + 1) % n, 1 + n + i))
        faces.append((1 + (i + 1) % n, 1 + n + (i + 1) % n, 1 + n + i))
    faces.append(tuple(1 + n + i for i in range(n)))
    ob = M.from_data(name, verts, faces)
    mat = M.material(name + "Mat", [(0.0, tuple(c * 0.5 for c in color)), (1.0, color)], coord="nz", lo=-1, hi=1,
                     rough=0.05, coat=1.0, transmission=0.4)
    M.assign(ob, mat)
    return ob


def scale_all(objs, k):
    for o in objs:
        o.matrix_world = Matrix.Scale(k, 4) @ o.matrix_world
    bpy.context.view_layer.update()
    return objs


def coins_chest():
    """Открытый сундук, доверху засыпанный монетами, и несколько монет перед ним."""
    _prep()
    rnd = random.Random(12)
    parts = M.chest_obj("coins", is_open=True, filled="none")
    # сундук строится повернутым: возвращаем прямо, насыпаем, потом поворачиваем обратно
    M.rotate_all(parts, (0, 0, math.radians(18)))
    k = 1.9
    scale_all(parts, k)
    w, d, h = 1.7 * k, 1.1 * k, 0.85 * k
    pile = coin_pile("Ch", 34, w / 2 - 0.2, 0.45, rnd, z0=h - 0.12, sx=1.0, sy=(d / 2 - 0.2) / (w / 2 - 0.2),
                     statics=parts, spill=0)
    gr = ground("ChGround")
    spill = deposit("ChS", 5, w / 2, rnd, 0, -d / 2 - 0.55, 1.0, 0.35, per_wave=3,
                    statics=parts + pile + [gr], ring=(0.0, 1.0))
    bpy.data.objects.remove(gr)
    out = parts + pile + spill + [shadow_catcher(12)]
    M.rotate_all(out, (0, 0, math.radians(-18)))
    return M.rotate_all(out, (math.radians(8), 0, 0))


def sack_mat():
    """Мешковина: плетение рельефом, низ чуть темнее."""
    mat = M.material("Sack", [(0.0, (0.42, 0.29, 0.12)), (0.55, (0.64, 0.49, 0.25)), (1.0, (0.74, 0.60, 0.36))],
                     coord="z", lo=0.0, hi=2.6, rough=0.9, vary=0.12, vary_scale=5)
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    tc = nodes.new("ShaderNodeTexCoord")
    waves = []
    for axis in ("X", "Z"):
        wv = nodes.new("ShaderNodeTexWave")
        wv.wave_type = "BANDS"
        wv.bands_direction = axis if axis != "Z" else "Z"
        wv.inputs["Scale"].default_value = 11
        wv.inputs["Distortion"].default_value = 1.5
        wv.inputs["Detail"].default_value = 1.0
        links.new(tc.outputs["Object"], wv.inputs["Vector"])
        waves.append(wv)
    mul = nodes.new("ShaderNodeMath")
    mul.operation = "ADD"
    links.new(waves[0].outputs["Fac"], mul.inputs[0])
    links.new(waves[1].outputs["Fac"], mul.inputs[1])
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.7
    bump.inputs["Distance"].default_value = 0.02
    links.new(mul.outputs[0], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Sheen Weight"].default_value = 0.15
    return mat


def coins_bag():
    """Мешок с монетами: завязанное горло с оборками, веревка, монета-значок, монеты у основания."""
    _prep()
    rnd = random.Random(31)
    k = 1.45
    prof = [(0.0, 0.0), (0.55, 0.02), (0.85, 0.22), (0.97, 0.55), (0.93, 0.9), (0.72, 1.18), (0.42, 1.36),
            (0.27, 1.45), (0.36, 1.58), (0.52, 1.74), (0.56, 1.84), (0.38, 1.88), (0.0, 1.8)]
    bag = M.lathe("Bag", [(a * k, b * k) for a, b in prof], 96)

    def folds(co, n):
        a = math.atan2(co.y, co.x)
        z = co.z / k
        if z > 1.42:  # оборка над веревкой: неровные складки ткани
            wave = math.sin(a * 6 + 0.7) + 0.6 * math.sin(a * 11 + 2.1) + 0.35 * math.sin(a * 17 + z * 6)
            return 0.05 * k * wave * min(1.0, (z - 1.42) * 4)
        if z > 0.95:  # складки, стянутые к горлу
            return 0.035 * k * math.sin(a * 7 + z * 2) * (z - 0.95) / 0.5
        return 0.012 * k * math.sin(a * 5 + z * 4)
    M.subdivide(bag, 1)
    M.push_normals(bag, folds)
    M.smooth(bag)
    M.assign(bag, sack_mat())
    rope = M.torus("Rope", 0.29 * k, 0.065 * k, 64, 16)
    rope.location = (0, 0, 1.45 * k)
    M.apply_transform(rope)
    rope_mat = M.material("RopeMat", [(0.0, (0.45, 0.16, 0.08)), (1.0, (0.78, 0.30, 0.16))], coord="nz", lo=-1,
                          hi=1, rough=0.7, bump=0.5, bump_scale=70)
    M.assign(M.smooth(rope), rope_mat)
    knot = M.sphere("Knot", 0.11 * k, 24, 12)
    knot.location = (0.05 * k, -0.33 * k, 1.44 * k)
    knot.scale = (1.2, 0.8, 0.9)
    M.apply_transform(knot)
    M.assign(M.smooth(knot), rope_mat)
    # значок: монета, пришитая к мешку спереди
    badge = coin("Badge")
    front = Vector((0, -0.95 * k - 0.05, 0.86 * k))
    badge.matrix_world = (Matrix.Translation(front) @ Euler((math.radians(80), 0, math.radians(4))).to_matrix().to_4x4()
                          @ Matrix.Scale(1.25, 4))
    parts = [bag, rope, knot, badge]
    gr = ground("BagGround")
    st = stack("BS", 1.15 * k, -0.35 * k, 3, rnd)
    spill = deposit("BagS", 6, 1.0, rnd, 0.0, -1.0 * k - 0.4, 1.0, 0.4, per_wave=3, statics=parts + st + [gr],
                    ring=(0.0, 1.2))
    bpy.data.objects.remove(gr)
    out = parts + st + spill + [shadow_catcher(12)]
    # значком к камере (камера чуть справа)
    M.rotate_all(out, (0, 0, math.radians(12)))
    return M.rotate_all(out, (math.radians(6), 0, 0))


MODELS = {
    "coin_icon": coin_icon,
    "coins_bag": coins_bag,
    "coins_chest": coins_chest,
    "coins_stack": coins_stack,
    "coins_pile": coins_pile,
    "coins_mountain": coins_mountain,
}


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--only", default="")
    ap.add_argument("--size", type=int, default=360)
    ap.add_argument("--samples", type=int, default=96)
    args = ap.parse_args()
    M.MODELS.update(MODELS)
    ids = [s for s in args.only.split(",") if s] or list(MODELS)
    for sid in ids:
        M.render(sid, args.out, args.size, samples=args.samples)
        print("rendered", sid, flush=True)


if __name__ == "__main__":
    main()
