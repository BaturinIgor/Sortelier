"""Полки и фон кухни для Sortelier.

Запуск:
  python environment.py shelf <папка вывода>
  python environment.py background <папка с GLB> <папка вывода> [--style=kitchen,japan] [--preview] [--samples=40]
      [--border=x0,x1,y0,y1]
Сцена фона (плитка, предметы, свет) собирается в kitchen.py; здесь палитры стилей, камера и запуск.
"""
import math
import os
import sys

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

sys.path.insert(0, os.path.dirname(__file__))
import render as R  # noqa: E402


# MARK: - Материалы

def wood_material(name, dark, light, grain_scale=6.0, coat=0.35, rough=0.42):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    coord = nodes.new("ShaderNodeTexCoord")
    mapping = nodes.new("ShaderNodeMapping")
    mapping.inputs["Scale"].default_value = (0.22, grain_scale, grain_scale)
    noise = nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 1.6
    noise.inputs["Detail"].default_value = 8.0
    wave = nodes.new("ShaderNodeTexWave")
    wave.wave_type = "BANDS"
    wave.bands_direction = "Y"
    wave.inputs["Scale"].default_value = 1.1
    wave.inputs["Distortion"].default_value = 3.0
    wave.inputs["Detail"].default_value = 3.0
    ramp = nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (*dark, 1)
    ramp.color_ramp.elements[1].color = (*light, 1)
    ramp.color_ramp.elements[0].position = 0.25
    ramp.color_ramp.elements[1].position = 0.85
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.08
    links.new(coord.outputs["Object"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], noise.inputs["Vector"])
    links.new(noise.outputs["Color"], wave.inputs["Vector"])
    links.new(wave.outputs["Fac"], ramp.inputs["Fac"])
    links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(wave.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = rough
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
        bsdf.inputs["Coat Roughness"].default_value = 0.12
    return mat


def gold_material(name):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (0.95, 0.58, 0.10, 1)
    bsdf.inputs["Metallic"].default_value = 0.55
    bsdf.inputs["Roughness"].default_value = 0.3
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = 0.6
        bsdf.inputs["Coat Roughness"].default_value = 0.08
    return mat


def box(name, size, loc, mat, bevel=0.025):
    bpy.ops.mesh.primitive_cube_add(size=1, location=loc)
    o = bpy.context.active_object
    o.name = name
    o.scale = size
    bpy.ops.object.transform_apply(scale=True)
    mod = o.modifiers.new("Bevel", "BEVEL")
    mod.width = bevel
    mod.segments = 3
    mod.harden_normals = True
    o.data.materials.append(mat)
    return o


# MARK: - Полка

W, D, H, T = 3.3, 1.0, 1.45, 0.14


def render_shelf(out_dir, name, gold=False, width=720):
    scene = R.reset_scene()
    scene.cycles.samples = 96
    frame = gold_material("Gold") if gold else wood_material("Frame", (0.20, 0.09, 0.035), (0.36, 0.17, 0.07), grain_scale=3.5)
    inside = wood_material("Inside", (0.13, 0.06, 0.025), (0.22, 0.11, 0.05), grain_scale=2.5, coat=0.1, rough=0.65)
    floor = wood_material("Floor", (0.30, 0.15, 0.06), (0.48, 0.26, 0.11), grain_scale=3.0)
    inner = W - 2 * T
    objs = [
        box("Bottom", (inner + 0.002, D, T), (0, 0, T / 2), floor),
        box("Top", (inner + 0.002, D, T), (0, 0, H - T / 2), frame),
        box("Back", (inner + 0.002, 0.08, H - 2 * T + 0.002), (0, D / 2 - 0.04, H / 2), inside),
        box("SideL", (T, D, H), (-W / 2 + T / 2, 0, H / 2), frame),
        box("SideR", (T, D, H), (W / 2 - T / 2, 0, H / 2), frame),
    ]
    bpy.context.view_layer.update()
    lo, hi, pts = R.bounds(objs)
    target = (lo + hi) / 2
    cam = R.add_camera(scene, target, pts, azimuth=0, elevation=math.radians(18), margin=1.02)
    # кадр по ширине полки, высота по пропорции модели
    inv = cam.matrix_world.inverted()
    local = [inv @ p for p in pts]
    w = max(p.x for p in local) - min(p.x for p in local)
    h = max(p.y for p in local) - min(p.y for p in local)
    aspect = w / h
    height = int(round(width / aspect))
    cam.data.ortho_scale = w * 1.02
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.filepath = os.path.join(out_dir, name + ".png")
    bpy.ops.render.render(write_still=True)
    bpy.context.view_layer.update()

    def at(p):
        v = world_to_camera_view(scene, cam, Vector(p))
        return round(v.x, 4), round(v.y, 4)

    marks = {
        "size": (width, height),
        "innerLeft": at((-W / 2 + T, -D / 2, T))[0],
        "innerRight": at((W / 2 - T, -D / 2, T))[0],
        "frontFloor": at((0, -D / 2 + 0.22, T))[1],
        "backFloor": at((0, 0.12, T))[1],
        "innerTop": at((0, -D / 2, H - T))[1],
    }
    print("SHELF", name, marks)
    return marks


def render_counter(out_dir, name="counter", width=1170):
    """Столешница прилавка над полками: вид спереди сверху, на всю ширину экрана."""
    scene = R.reset_scene()
    scene.cycles.samples = 96
    # сверху столешница ловит прямой свет и выгорает: убираем экспозицию
    scene.view_settings.exposure = -1.1
    top = wood_material("CounterTop", (0.24, 0.11, 0.045), (0.42, 0.21, 0.09), grain_scale=2.5, coat=0.06, rough=0.6)
    front = wood_material("CounterFront", (0.15, 0.065, 0.028), (0.27, 0.13, 0.055), grain_scale=3.0, coat=0.06, rough=0.6)
    brass = gold_material("Trim")
    W = 6.0
    objs = [
        box("Top", (W + 0.4, 0.34, 0.1), (0, 0, 0.0), top, bevel=0.03),
        box("Front", (W + 0.4, 0.06, 0.32), (0, -0.15, -0.21), front, bevel=0.02),
        box("Trim", (W + 0.4, 0.03, 0.03), (0, -0.175, -0.065), brass, bevel=0.01),
    ]
    bpy.context.view_layer.update()
    lo, hi, pts = R.bounds(objs)
    cam = R.add_camera(scene, (lo + hi) / 2, pts, azimuth=0, elevation=math.radians(32), margin=1.0)
    inv = cam.matrix_world.inverted()
    local = [inv @ p for p in pts]
    h = max(p.y for p in local) - min(p.y for p in local)
    cam.data.ortho_scale = W
    scene.render.resolution_x = width
    scene.render.resolution_y = int(round(width * h / W))
    scene.render.filepath = os.path.join(out_dir, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("COUNTER", scene.render.resolution_x, scene.render.resolution_y)


# MARK: - Фон кухни

def place(src, model, loc, scale=3.0, rot_z=0.0, polish=True, rot=None):
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=os.path.join(src, model + ".glb"))
    new = [o for o in bpy.data.objects if o not in before]
    meshes = [o for o in new if o.type == "MESH"]
    if polish:
        R.polish(meshes, subdivide=True)
    roots = [o for o in new if o.parent is None]
    for o in roots:
        o.scale = (scale, scale, scale)
        o.rotation_mode = "XYZ"  # glTF приходит с кватернионом, euler иначе игнорируется
        o.rotation_euler = rot if rot else (0, 0, rot_z)
        o.location = loc
    bpy.context.view_layer.update()
    return meshes


# Стили кухни: плитка, шкафчики, металл, свет. Цвета линейные, как в шейдерах Blender.
STYLES = {
    "kitchen": dict(tiles=((0.38, 0.72, 0.68), (0.28, 0.62, 0.60), (0.62, 0.84, 0.80)), cabinet=(0.96, 0.90, 0.80),
                    metal="brass", world=((1.0, 0.95, 0.88), 0.55), light=((1.0, 0.92, 0.80), 260), checker=False),
    "peach": dict(tiles=((0.96, 0.52, 0.40), (0.90, 0.46, 0.36), (1.0, 0.82, 0.74)), cabinet=(0.98, 0.94, 0.88),
                  metal="brass", world=((1.0, 0.95, 0.90), 0.55), light=((1.0, 0.92, 0.82), 260), checker=False),
    "lavender": dict(tiles=((0.52, 0.42, 0.86), (0.46, 0.37, 0.80), (0.82, 0.78, 0.96)), cabinet=(0.95, 0.94, 1.0),
                     metal="steel", world=((0.96, 0.95, 1.0), 0.55), light=((0.98, 0.95, 1.0), 260), checker=False),
    "night": dict(tiles=((0.05, 0.08, 0.17), (0.04, 0.06, 0.14), (0.12, 0.15, 0.26)), cabinet=(0.20, 0.12, 0.07),
                  metal="brass", world=((0.30, 0.38, 0.65), 0.18), light=((1.0, 0.70, 0.40), 330), checker=False),
    "autumn": dict(tiles=((0.80, 0.34, 0.10), (0.70, 0.28, 0.08), (0.96, 0.80, 0.60)), cabinet=(0.10, 0.24, 0.14),
                   metal="brass", world=((1.0, 0.92, 0.80), 0.5), light=((1.0, 0.84, 0.62), 280), checker=False),
    "winter": dict(tiles=((0.52, 0.74, 0.96), (0.44, 0.66, 0.90), (0.95, 0.97, 1.0)), cabinet=(0.95, 0.97, 1.0),
                   metal="steel", world=((0.92, 0.96, 1.0), 0.6), light=((0.95, 0.97, 1.0), 250), checker=False),
    "sweets": dict(tiles=((0.95, 0.42, 0.60), (0.88, 0.36, 0.55), (1.0, 0.86, 0.92)), cabinet=(0.62, 0.90, 0.80),
                   metal="brass", world=((1.0, 0.95, 0.96), 0.55), light=((1.0, 0.94, 0.94), 260), checker=False),
    "bbq": dict(tiles=((0.52, 0.14, 0.07), (0.44, 0.11, 0.05), (0.55, 0.52, 0.48)), cabinet=(0.24, 0.12, 0.05),
                metal="steel", world=((1.0, 0.93, 0.85), 0.5), light=((1.0, 0.86, 0.70), 300), checker=False),
    "diner": dict(tiles=((0.90, 0.86, 0.78), (0.06, 0.06, 0.075), (0.5, 0.5, 0.5)), cabinet=(0.80, 0.06, 0.06),
                  metal="steel", world=((1.0, 0.97, 0.92), 0.55), light=((1.0, 0.95, 0.88), 260), checker=True),
    # биомы: японская и итальянская кухни, награда гурмана
    "japan": dict(tiles=((0.12, 0.20, 0.42), (0.09, 0.16, 0.36), (0.92, 0.90, 0.84)), cabinet=(0.90, 0.80, 0.62),
                  metal="steel", world=((1.0, 0.96, 0.92), 0.55), light=((1.0, 0.94, 0.86), 270), checker=False),
    "italy": dict(tiles=((0.80, 0.36, 0.16), (0.70, 0.30, 0.13), (0.96, 0.90, 0.76)), cabinet=(0.34, 0.42, 0.16),
                  metal="brass", world=((1.0, 0.95, 0.86), 0.55), light=((1.0, 0.90, 0.74), 280), checker=False),
    "gourmet": dict(tiles=((0.03, 0.22, 0.15), (0.02, 0.18, 0.12), (0.80, 0.62, 0.30)), cabinet=(0.06, 0.06, 0.07),
                    metal="brass", world=((1.0, 0.95, 0.88), 0.5), light=((1.0, 0.88, 0.70), 300), checker=False),
    # мексиканская кухня: солнечная плитка цвета бархатцев, кобальтовые шкафчики
    "mexico": dict(tiles=((0.95, 0.60, 0.07), (0.88, 0.50, 0.05), (0.97, 0.93, 0.84)), cabinet=(0.07, 0.22, 0.62),
                   metal="brass", world=((1.0, 0.95, 0.86), 0.55), light=((1.0, 0.90, 0.72), 290), checker=False),
    # французская пекарня: сливочная плитка, темно-синие шкафчики с латунью
    "bakery": dict(tiles=((0.93, 0.83, 0.66), (0.87, 0.76, 0.58), (0.99, 0.97, 0.93)), cabinet=(0.08, 0.13, 0.30),
                   metal="brass", world=((1.0, 0.97, 0.94), 0.6), light=((1.0, 0.95, 0.88), 260), checker=False),
    # хэллоуин: фиолетовая плитка с оранжевыми швами, темные шкафчики, теплые лампы
    "halloween": dict(tiles=((0.16, 0.05, 0.26), (0.12, 0.04, 0.21), (0.85, 0.36, 0.04)), cabinet=(0.07, 0.05, 0.07),
                      metal="brass", world=((0.45, 0.30, 0.70), 0.22), light=((1.0, 0.62, 0.30), 320), checker=False,
                      lamps=True),
}


def render_background(src, out_dir, preview=False, style="kitchen", samples=64, border=None):
    """Фон кухни (версия 2, сцена собирается в kitchen.py). border=(x0, x1, y0, y1) - рендер части кадра."""
    import kitchen as K
    st = dict(STYLES[style])
    st.update(K.STYLE_EXTRA.get(style, {}))
    scene = R.reset_scene()
    scene.cycles.samples = 24 if preview else samples
    scene.cycles.use_denoising = True
    scene.cycles.film_transparent_glass = False
    scene.cycles.max_bounces = 6
    scene.cycles.diffuse_bounces = 3
    scene.cycles.glossy_bounces = 3
    scene.cycles.transparent_max_bounces = 12
    scene.cycles.adaptive_threshold = 0.02
    width, height = (390, 844) if preview else (1170, 2532)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    world_h = 10.0
    world_w = world_h * width / height

    def kenney(model, loc, scale=3.0, rot_z=0.0, rot=None):
        return place(src, model, loc, scale, rot_z, rot=rot)

    K.build(style, st, src, kenney, world_w)

    # фронтальная ортокамера на всю высоту экрана
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = world_h
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    tilt = math.radians(6)
    cam.location = (0, -12 * math.cos(tilt), 12 * math.sin(tilt))
    cam.rotation_euler = (math.radians(90) - tilt, 0, 0)
    scene.camera = cam
    scene.render.film_transparent = False
    K.lighting(scene, st)
    if border:
        scene.render.use_border = True
        scene.render.use_crop_to_border = True
        scene.render.border_min_x, scene.render.border_max_x, scene.render.border_min_y, scene.render.border_max_y = border
    name = f"bg_{style}" + ("_preview" if preview else "") + ("_crop" if border else "")
    scene.render.filepath = os.path.join(out_dir, name + ".png")
    bpy.ops.render.render(write_still=True)
    if not border and st.get("bloom"):
        K.bloom(scene.render.filepath)


def main():
    args = sys.argv[1:]
    if args[0] == "shelf":
        os.makedirs(args[1], exist_ok=True)
        render_shelf(args[1], "shelf")
        render_shelf(args[1], "shelf_gold", gold=True)
    elif args[0] == "counter":
        os.makedirs(args[1], exist_ok=True)
        render_counter(args[1])
    elif args[0] == "background":
        os.makedirs(args[2], exist_ok=True)
        styles = [a.split("=", 1)[1] for a in args if a.startswith("--style=")] or ["kitchen"]
        samples = int(next((a.split("=", 1)[1] for a in args if a.startswith("--samples=")), "64"))
        border = next((tuple(float(v) for v in a.split("=", 1)[1].split(",")) for a in args
                       if a.startswith("--border=")), None)
        for style in styles[0].split(","):
            render_background(args[1], args[2], preview="--preview" in args, style=style, samples=samples,
                              border=border)


if __name__ == "__main__":
    main()
