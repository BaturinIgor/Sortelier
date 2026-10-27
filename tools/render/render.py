"""Рендер спрайтов Sortelier из Kenney Food Kit (CC0).

Запуск: python render.py <папка с GLB> <папка вывода> [--only id,id] [--spin]
Нужен Blender как модуль Python (pip install bpy).
"""
import math
import sys
import os
import argparse

import bpy
from mathutils import Vector

ELEVATION = math.radians(28)
AZIMUTH = math.radians(28)

# id спрайта -> (файл модели, какие части оставить, сдвиги частей по высоте)
ITEMS = {
    # ингредиенты кухни 1
    "bun": ("burger", ["bun-bottom", "bun-top"], {"bun-top": -0.128}),
    "patty": ("meat-patty", None, None),
    "lettuce": ("cabbage", None, None),
    "cheese": ("cheese-cut", None, None),
    "tomato": ("tomato", None, None),
    "sausage": ("meat-sausage", None, None),
    "hotdog_bun": ("hot-dog", ["hot-dog"], None),
    "ketchup": ("bottle-ketchup", None, None),
    "bread": ("bread", None, None),
    "ham": ("whole-ham", None, None),
    "baguette": ("loaf-baguette", None, None),
    "egg": ("egg", None, None),
    "milk": ("carton", None, None),
    "honey": ("honey", None, None),
    # готовые продукты для заказов тройками
    "fries": ("fries", None, None),
    "soda": ("soda-can", None, None),
    "donut": ("donut-sprinkles", None, None),
    "cupcake": ("cupcake", None, None),
    "cookie": ("cookie-chocolate", None, None),
    "icecream": ("ice-cream", None, None),
    "corn": ("corn", None, None),
    "muffin": ("muffin", None, None),
    "corndog": ("corn-dog", None, None),
    "waffle": ("waffle", None, None),
    "pie": ("pie", None, None),
    # заготовки для цепочек (биом 2)
    "meat_raw": ("meat-raw", None, None),
    "bacon_raw": ("bacon-raw", None, None),
    "bacon": ("bacon", None, None),
}

DISHES = {
    "dish_burger": ("burger", None, None),
    "dish_cheeseburger": ("burger-cheese", None, None),
    "dish_hotdog": ("hot-dog", None, None),
    "dish_sandwich": ("sandwich", None, None),
    "dish_sub": ("sub", None, None),
    "dish_pancakes": ("pancakes", None, None),
}


def reset_scene():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64
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
    bg.inputs[0].default_value = (1.0, 0.98, 0.95, 1.0)
    bg.inputs[1].default_value = 0.5

    def sun(name, energy, rotation, color):
        light = bpy.data.lights.new(name, type="SUN")
        light.energy = energy
        light.color = color
        light.angle = math.radians(12)
        obj = bpy.data.objects.new(name, light)
        obj.rotation_euler = rotation
        scene.collection.objects.link(obj)

    # теплый ключевой свет, холодная заливка и контровой для бликов по краю
    sun("Key", 4.2, (math.radians(48), 0, math.radians(-40)), (1.0, 0.96, 0.9))
    sun("Fill", 1.3, (math.radians(70), 0, math.radians(75)), (0.85, 0.9, 1.0))
    sun("Rim", 3.5, (math.radians(-60), 0, math.radians(20)), (1.0, 1.0, 1.0))
    return scene


def import_model(path, keep, offsets):
    bpy.ops.import_scene.gltf(filepath=path)
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if keep:
        for o in list(meshes):
            base = o.name.split(".")[0]
            if base not in keep:
                bpy.data.objects.remove(o, do_unlink=True)
        meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if offsets:
        for o in meshes:
            base = o.name.split(".")[0]
            if base in offsets:
                o.location.z += offsets[base] if o.parent is None else 0
                if o.parent is not None:
                    o.matrix_world.translation.z += offsets[base]
    bpy.context.view_layer.update()
    return meshes


def polish(meshes, subdivide=True, matte=False):
    """Глянцевые материалы, сглаживание и подразделение: модели становятся круглее.
    Плоским продуктам глянец дает пересвет, им матовый материал."""
    import bmesh
    for o in meshes:
        for slot in o.material_slots:
            m = slot.material
            if not m or not m.use_nodes:
                continue
            b = m.node_tree.nodes.get("Principled BSDF")
            if b:
                b.inputs["Roughness"].default_value = 0.7 if matte else 0.35
                if "Specular IOR Level" in b.inputs:
                    b.inputs["Specular IOR Level"].default_value = 0.3 if matte else 0.6
                if "Coat Weight" in b.inputs:
                    b.inputs["Coat Weight"].default_value = 0.0 if matte else 0.25
        if subdivide:
            bm = bmesh.new()
            bm.from_mesh(o.data)
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.0005)
            bm.to_mesh(o.data)
            bm.free()
        o.data.shade_smooth()
        o.data.set_sharp_from_angle(angle=math.radians(40))
        if subdivide:
            mod = o.modifiers.new("Subd", "SUBSURF")
            mod.levels = 1
            mod.render_levels = 1
            mod.uv_smooth = "PRESERVE_BOUNDARIES"
            mod.boundary_smooth = "PRESERVE_CORNERS"


# модели, которые от подразделения теряют форму
NO_SUBDIV = {"cheese", "waffle", "bacon", "bacon_raw", "meat_raw", "patty", "pie", "bread"}
# плоские продукты, которым глянец дает пересвет
MATTE = {"bread", "cheese", "cookie", "meat_raw", "patty", "pie", "waffle", "bacon", "bacon_raw",
         "dish_pancakes", "dish_sandwich"}


def bounds(meshes):
    pts = []
    for o in meshes:
        pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi, pts


def add_camera(scene, target, pts, azimuth=AZIMUTH, elevation=ELEVATION, margin=1.12, aspect=1.0):
    cam_data = bpy.data.cameras.new("Cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("Cam", cam_data)
    scene.collection.objects.link(cam)
    direction = Vector((
        math.sin(azimuth) * math.cos(elevation),
        -math.cos(azimuth) * math.cos(elevation),
        math.sin(elevation),
    ))
    cam.location = target + direction * 10
    cam.rotation_euler = (-direction).to_track_quat("-Z", "Y").to_euler()
    bpy.context.view_layer.update()
    inv = cam.matrix_world.inverted()
    local = [inv @ p for p in pts]
    w = max(p.x for p in local) - min(p.x for p in local)
    h = max(p.y for p in local) - min(p.y for p in local)
    cx = (max(p.x for p in local) + min(p.x for p in local)) / 2
    cy = (max(p.y for p in local) + min(p.y for p in local)) / 2
    cam.location += cam.matrix_world.to_quaternion() @ Vector((cx, cy, 0))
    cam_data.ortho_scale = max(w / aspect if aspect >= 1 else w, h * aspect if aspect >= 1 else h / aspect) * margin
    if aspect >= 1:
        cam_data.ortho_scale = max(w, h * aspect) * margin
    else:
        cam_data.ortho_scale = max(w / aspect, h) * margin
    scene.camera = cam
    return cam


def render_item(src_dir, out_dir, sprite_id, spec, size, spin_frames=0):
    model, keep, offsets = spec
    scene = reset_scene()
    meshes = import_model(os.path.join(src_dir, model + ".glb"), keep, offsets)
    polish(meshes, subdivide=sprite_id not in NO_SUBDIV, matte=sprite_id in MATTE)
    lo, hi, pts = bounds(meshes)
    center = (lo + hi) / 2
    # опорная точка вращения в центре модели
    pivot = bpy.data.objects.new("Pivot", None)
    scene.collection.objects.link(pivot)
    pivot.location = center
    bpy.context.view_layer.update()
    roots = {o for o in bpy.data.objects if o.parent is None and o is not pivot and o.type in ("MESH", "EMPTY")}
    for o in roots:
        mw = o.matrix_world.copy()
        o.parent = pivot
        o.matrix_parent_inverse = pivot.matrix_world.inverted()
        o.matrix_world = mw
    bpy.context.view_layer.update()

    if spin_frames:
        # кадр вмещает модель при любом повороте
        r = max((Vector((p.x, p.y, 0)) - Vector((center.x, center.y, 0))).length for p in pts)
        ring = []
        for k in range(16):
            a = 2 * math.pi * k / 16
            for z in (lo.z, hi.z):
                ring.append(Vector((center.x + r * math.cos(a), center.y + r * math.sin(a), z)))
        add_camera(scene, center, ring, margin=1.05)
    else:
        add_camera(scene, center, pts)

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


def wood_material(name, color, rough=0.6):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    bsdf = mat.node_tree.nodes["Principled BSDF"]
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    return mat


def box(name, size, loc, mat, bevel=0.03):
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


def render_shelf(out_dir, name, colors, width=720, height=330):
    scene = reset_scene()
    front, back, side = colors
    m_front = wood_material("Front", front)
    m_back = wood_material("Back", back, 0.8)
    m_side = wood_material("Side", side)
    W, D, H = 3.3, 1.0, 1.25
    T = 0.12
    inner = W - 2 * T - 0.004
    objs = [
        box("Bottom", (inner, D, 0.14), (0, 0, 0.07), m_front),
        box("Lip", (inner, 0.1, 0.1), (0, -D / 2 + 0.05, 0.19), m_front, 0.025),
        box("Back", (inner, 0.08, H - 0.142), (0, D / 2 - 0.04, 0.142 + (H - 0.142) / 2), m_back),
        box("SideL", (T, D, H), (-W / 2 + T / 2, 0, H / 2), m_side),
        box("SideR", (T, D, H), (W / 2 - T / 2, 0, H / 2), m_side),
    ]
    bpy.context.view_layer.update()
    lo, hi, pts = bounds(objs)
    add_camera(scene, (lo + hi) / 2, pts, azimuth=0, elevation=math.radians(18), margin=1.04, aspect=width / height)
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.filepath = os.path.join(out_dir, name + ".png")
    bpy.ops.render.render(write_still=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("src")
    parser.add_argument("out")
    parser.add_argument("--only", default="")
    parser.add_argument("--spin", action="store_true")
    parser.add_argument("--shelf", action="store_true")
    args = parser.parse_args(sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:])
    os.makedirs(args.out, exist_ok=True)
    only = set(filter(None, args.only.split(",")))

    if args.shelf:
        render_shelf(args.out, "shelf", ((0.66, 0.40, 0.21), (0.42, 0.25, 0.13), (0.58, 0.35, 0.18)))
        render_shelf(args.out, "shelf_gold", ((0.95, 0.70, 0.18), (0.70, 0.48, 0.10), (0.88, 0.62, 0.15)))
        return

    for sprite_id, spec in ITEMS.items():
        if only and sprite_id not in only:
            continue
        render_item(args.src, args.out, sprite_id, spec, 360)
    for sprite_id, spec in DISHES.items():
        if only and sprite_id not in only:
            continue
        render_item(args.src, args.out, sprite_id, spec, 512)
        if args.spin:
            render_item(args.src, args.out, sprite_id, spec, 320, spin_frames=24)


if __name__ == "__main__":
    main()
