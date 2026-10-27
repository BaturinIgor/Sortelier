"""Полки и фон кухни для Sortelier.

Запуск:
  python environment.py shelf <папка вывода>
  python environment.py background <папка с GLB> <папка вывода> [--preview]
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


def flat_material(name, color, rough=0.6, coat=0.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1)
    bsdf.inputs["Roughness"].default_value = rough
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat
    return mat


def tile_material(name, c1, c2, mortar, scale=7.0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nodes, links = nt.nodes, nt.links
    bsdf = nodes["Principled BSDF"]
    coord = nodes.new("ShaderNodeNewGeometry")
    mapping = nodes.new("ShaderNodeMapping")
    # плитка "кабанчик" по мировым координатам стены: X вправо, Z вверх
    mapping.inputs["Rotation"].default_value = (math.radians(-90), 0, 0)
    brick = nodes.new("ShaderNodeTexBrick")
    brick.inputs["Scale"].default_value = scale
    brick.inputs["Color1"].default_value = (*c1, 1)
    brick.inputs["Color2"].default_value = (*c2, 1)
    brick.inputs["Mortar"].default_value = (*mortar, 1)
    brick.inputs["Mortar Size"].default_value = 0.012
    brick.inputs["Mortar Smooth"].default_value = 0.4
    brick.inputs["Bias"].default_value = 0.0
    brick.inputs["Brick Width"].default_value = 0.5
    brick.inputs["Row Height"].default_value = 0.25
    bump = nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.35
    bump.invert = True
    links.new(coord.outputs["Position"], mapping.inputs["Vector"])
    links.new(mapping.outputs["Vector"], brick.inputs["Vector"])
    links.new(brick.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(brick.outputs["Fac"], bump.inputs["Height"])
    links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    bsdf.inputs["Roughness"].default_value = 0.25
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


def render_background(src, out_dir, preview=False):
    scene = R.reset_scene()
    scene.cycles.samples = 24 if preview else 64
    scene.cycles.use_denoising = True
    width, height = (390, 844) if preview else (1170, 2532)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    world_h = 10.0
    world_w = world_h * width / height

    # стена из плитки
    wall = tile_material("Tiles", (0.38, 0.72, 0.68), (0.28, 0.62, 0.60), (0.62, 0.84, 0.80), scale=1.1)
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0.6, 0), rotation=(math.radians(90), 0, 0))
    plane = bpy.context.active_object
    plane.scale = (world_w + 2, world_h + 2, 1)
    plane.data.materials.append(wall)

    wood = wood_material("Counter", (0.40, 0.21, 0.10), (0.64, 0.37, 0.18), grain_scale=3.0)
    paint = flat_material("Cabinet", (0.96, 0.90, 0.80), rough=0.45, coat=0.2)
    brass = gold_material("Brass")

    # верхняя полка с посудой (за карточками заказов, видна по краям)
    ledge_z = 3.05
    box("Ledge", (world_w + 1, 0.7, 0.12), (0, 0.25, ledge_z), wood, bevel=0.03)
    for x in (-world_w / 2 + 0.45, world_w / 2 - 0.45):
        box("Bracket", (0.1, 0.45, 0.32), (x, 0.38, ledge_z - 0.22), wood, bevel=0.02)
    top = ledge_z + 0.06
    place(src, "pot", (-world_w / 2 + 0.55, 0.25, top), 1.5, 0.3)
    place(src, "mug", (-world_w / 2 + 1.25, 0.2, top), 1.5, -0.6)
    place(src, "bottle-oil", (world_w / 2 - 1.3, 0.25, top), 1.6)
    place(src, "pepper-mill", (world_w / 2 - 0.9, 0.2, top), 1.5)
    place(src, "can", (world_w / 2 - 0.45, 0.25, top), 1.5, 0.5)

    # рейлинг с утварью под самым верхом
    rail_z = 4.35
    bpy.ops.mesh.primitive_cylinder_add(radius=0.025, depth=world_w + 1, location=(0, 0.45, rail_z),
                                        rotation=(0, math.radians(90), 0))
    bpy.context.active_object.data.materials.append(brass)
    hang = rail_z - 0.04
    for model, x, sc in (("cooking-spatula", -0.5, 1.35), ("whisk", -0.12, 1.3), ("cooking-spoon", 0.24, 1.35),
                         ("cooking-fork", 0.58, 1.3)):
        # ручкой вверх: длинная ось модели X уходит в +Z
        place(src, model, (x, 0.38, hang - 0.34 * sc), sc, rot=(math.radians(90), math.radians(-90), 0))
        bpy.ops.mesh.primitive_torus_add(major_radius=0.035, minor_radius=0.008, location=(x, 0.38, hang + 0.02),
                                         rotation=(math.radians(90), 0, 0))
        bpy.context.active_object.data.materials.append(brass)

    # столешница и шкафчики внизу (за панелью бустеров)
    counter_z = -3.55
    box("Countertop", (world_w + 1, 1.2, 0.16), (0, -0.2, counter_z), wood, bevel=0.04)
    box("Cabinets", (world_w + 1, 1.0, 1.9), (0, 0.0, counter_z - 1.03), paint, bevel=0.02)
    for i, x in enumerate((-world_w / 4, world_w / 4)):
        box(f"Door{i}", (world_w / 2 - 0.2, 0.05, 1.5), (x, -0.52, counter_z - 1.0), paint, bevel=0.035)
        box(f"Handle{i}", (0.4, 0.05, 0.05), (x, -0.58, counter_z - 0.4), brass, bevel=0.015)
    surf = counter_z + 0.08
    place(src, "cutting-board", (-world_w / 2 + 0.7, -0.3, surf), 1.6, 0.2)
    place(src, "loaf-round", (-world_w / 2 + 0.7, -0.3, surf + 0.05), 1.5)
    place(src, "knife-block", (world_w / 2 - 0.5, -0.1, surf), 1.6, -0.5)
    place(src, "bowl", (world_w / 2 - 1.35, -0.35, surf), 1.6)
    place(src, "apple", (world_w / 2 - 1.45, -0.35, surf + 0.07), 1.3)
    place(src, "orange", (world_w / 2 - 1.22, -0.4, surf + 0.07), 1.3)

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

    # мягкий свет кухни: солнца из сцены продуктов здесь пересвечивают
    for o in [o for o in scene.objects if o.type == "LIGHT"]:
        bpy.data.objects.remove(o, do_unlink=True)
    bg = scene.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1.0, 0.95, 0.88, 1)
    bg.inputs[1].default_value = 0.55
    area = bpy.data.lights.new("Window", type="AREA")
    area.energy = 260
    area.size = 7
    area.color = (1.0, 0.92, 0.80)
    light = bpy.data.objects.new("Window", area)
    light.location = (-3.5, -7, 5)
    light.rotation_euler = (math.radians(58), 0, math.radians(-27))
    scene.collection.objects.link(light)

    name = "bg_kitchen_preview" if preview else "bg_kitchen"
    scene.render.filepath = os.path.join(out_dir, name + ".png")
    bpy.ops.render.render(write_still=True)


def main():
    args = sys.argv[1:]
    if args[0] == "shelf":
        os.makedirs(args[1], exist_ok=True)
        render_shelf(args[1], "shelf")
        render_shelf(args[1], "shelf_gold", gold=True)
    elif args[0] == "background":
        os.makedirs(args[2], exist_ok=True)
        render_background(args[1], args[2], preview="--preview" in args)


if __name__ == "__main__":
    main()
