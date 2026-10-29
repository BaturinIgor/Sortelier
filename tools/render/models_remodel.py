"""Переделка слабых продуктов (партия 1): котлета, салат, сосиски, булка для хот-дога, говядина, тесто, мука,
моцарелла, базилик, спагетти, гриссини, оливковое масло, красный лук, лук-порей.

Подключается последним в models.EXTENSIONS, поэтому эти id перекрывают прежние сборщики из models.py и
models_mexico.py. Свет, камера и мир общие (models.reset_scene), здесь только формы и материалы:
процедурная фактура (шум, вороной, прожилки, следы гриля), неровности формы, фаски, рассеяние и лак.
"""
import math
import random

import bpy
from mathutils import Matrix, Vector, noise

import models as M
from models import *  # noqa: F401,F403  помощники
import models_events as EV
import models_mexico as MX


# MARK: - Конструктор шейдера

def _is_socket(x):
    return isinstance(x, bpy.types.NodeSocket)


def _col(c):
    return (*lin(c), 1.0) if len(c) == 3 else c


class Sh:
    """Principled BSDF с удобными узлами: шум, вороной, маски, смешивание цветов, цепочка рельефа."""

    def __init__(self, name, rough=0.4, sss=0.0, sss_radius=(1.0, 0.5, 0.3), sss_scale=0.08, coat=0.0,
                 coat_rough=0.1, sheen=0.0, sheen_rough=0.5, spec=0.5, metal=0.0, transmission=0.0, ior=1.45):
        mat = bpy.data.materials.new(name)
        mat.use_nodes = True
        self.mat = mat
        self.nodes = mat.node_tree.nodes
        self.links = mat.node_tree.links
        b = self.bsdf = self.nodes["Principled BSDF"]
        b.inputs["Roughness"].default_value = rough
        b.inputs["Specular IOR Level"].default_value = spec
        b.inputs["Metallic"].default_value = metal
        b.inputs["IOR"].default_value = ior
        if sss:
            b.inputs["Subsurface Weight"].default_value = sss
            b.inputs["Subsurface Radius"].default_value = sss_radius
            b.inputs["Subsurface Scale"].default_value = sss_scale
        if coat:
            b.inputs["Coat Weight"].default_value = coat
            b.inputs["Coat Roughness"].default_value = coat_rough
        if sheen:
            b.inputs["Sheen Weight"].default_value = sheen
            b.inputs["Sheen Roughness"].default_value = sheen_rough
        if transmission:
            b.inputs["Transmission Weight"].default_value = transmission
        self._tc = None
        self._normal = None

    # входы: сокет или число/вектор/цвет
    def _in(self, sock, val):
        if _is_socket(val):
            self.links.new(val, sock)
        elif val is not None:
            sock.default_value = val

    def tc(self, out="Object"):
        if self._tc is None:
            self._tc = self.nodes.new("ShaderNodeTexCoord")
        return self._tc.outputs[out]

    def vec(self, vec):
        return self.tc("Object") if vec is None else (self.tc(vec) if isinstance(vec, str) else vec)

    def xyz(self, vec=None):
        sep = self.nodes.new("ShaderNodeSeparateXYZ")
        self.links.new(self.vec(vec), sep.inputs[0])
        return sep.outputs[0], sep.outputs[1], sep.outputs[2]

    def combine(self, x, y, z):
        n = self.nodes.new("ShaderNodeCombineXYZ")
        for i, v in enumerate((x, y, z)):
            self._in(n.inputs[i], v)
        return n.outputs[0]

    def mapping(self, vec=None, loc=(0, 0, 0), rot=(0, 0, 0), scale=(1, 1, 1)):
        mp = self.nodes.new("ShaderNodeMapping")
        self.links.new(self.vec(vec), mp.inputs["Vector"])
        mp.inputs["Location"].default_value = loc
        mp.inputs["Rotation"].default_value = rot
        mp.inputs["Scale"].default_value = scale
        return mp.outputs[0]

    def math(self, op, a, b=0.0, c=0.0, clamp=False):
        n = self.nodes.new("ShaderNodeMath")
        n.operation = op
        n.use_clamp = clamp
        self._in(n.inputs[0], a)
        self._in(n.inputs[1], b)
        self._in(n.inputs[2], c)
        return n.outputs[0]

    def vmath(self, op, a, b=None, scale=None):
        n = self.nodes.new("ShaderNodeVectorMath")
        n.operation = op
        self._in(n.inputs[0], a)
        if b is not None:
            self._in(n.inputs[1], b)
        if scale is not None:
            self._in(n.inputs[3], scale)
        return n.outputs["Value"] if op in ("LENGTH", "DOT_PRODUCT", "DISTANCE") else n.outputs["Vector"]

    def noise(self, vec=None, scale=5.0, detail=4.0, rough=0.5, distortion=0.0, kind="FBM", out=0, lac=2.0):
        n = self.nodes.new("ShaderNodeTexNoise")
        n.noise_type = kind
        self.links.new(self.vec(vec), n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Detail"].default_value = detail
        n.inputs["Roughness"].default_value = rough
        n.inputs["Lacunarity"].default_value = lac
        n.inputs["Distortion"].default_value = distortion
        return n.outputs[out]

    def voronoi(self, vec=None, scale=5.0, feature="F1", rand=1.0, out="Distance", metric="EUCLIDEAN"):
        n = self.nodes.new("ShaderNodeTexVoronoi")
        n.feature = feature
        n.distance = metric
        self.links.new(self.vec(vec), n.inputs["Vector"])
        n.inputs["Scale"].default_value = scale
        n.inputs["Randomness"].default_value = rand
        return n.outputs[out]

    def remap(self, x, a, b, c=0.0, d=1.0, smooth=True):
        n = self.nodes.new("ShaderNodeMapRange")
        n.interpolation_type = "SMOOTHSTEP" if smooth else "LINEAR"
        n.clamp = True
        self._in(n.inputs[0], x)
        n.inputs[1].default_value = a
        n.inputs[2].default_value = b
        n.inputs[3].default_value = c
        n.inputs[4].default_value = d
        return n.outputs[0]

    def ramp(self, x, stops, interp="LINEAR"):
        r = self.nodes.new("ShaderNodeValToRGB")
        r.color_ramp.interpolation = interp
        els = r.color_ramp.elements

        def cv(c):
            return (c, c, c, 1.0) if isinstance(c, (int, float)) else _col(c)
        els[0].position, els[0].color = stops[0][0], cv(stops[0][1])
        els[1].position, els[1].color = stops[-1][0], cv(stops[-1][1])
        for pos, c in stops[1:-1]:
            e = els.new(pos)
            e.color = cv(c)
        self._in(r.inputs["Fac"], x)
        return r.outputs["Color"]

    def mix(self, fac, a, b, blend="MIX"):
        n = self.nodes.new("ShaderNodeMix")
        n.data_type = "RGBA"
        n.blend_type = blend
        n.clamp_factor = True
        ins = [i for i in n.inputs if i.type == "RGBA"]
        self._in(n.inputs[0], fac)
        self._in(ins[0], a if _is_socket(a) else _col(a))
        self._in(ins[1], b if _is_socket(b) else _col(b))
        return [o for o in n.outputs if o.type == "RGBA"][0]

    def attr(self, name):
        n = self.nodes.new("ShaderNodeAttribute")
        n.attribute_name = name
        return n.outputs["Fac"]

    def color(self, sock):
        self._in(self.bsdf.inputs["Base Color"], sock if _is_socket(sock) else _col(sock))
        return self

    def set(self, name, val):
        self._in(self.bsdf.inputs[name], val)
        return self

    def bump(self, height, strength=0.3, distance=0.02, invert=False):
        b = self.nodes.new("ShaderNodeBump")
        b.invert = invert
        b.inputs["Strength"].default_value = strength
        b.inputs["Distance"].default_value = distance
        self._in(b.inputs["Height"], height)
        if self._normal is not None:
            self.links.new(self._normal, b.inputs["Normal"])
        self._normal = b.outputs["Normal"]
        self.links.new(self._normal, self.bsdf.inputs["Normal"])
        return self

    def rough_vary(self, lo, hi, scale=6.0, vec=None, detail=3.0):
        self.set("Roughness", self.remap(self.noise(vec, scale, detail), 0.3, 0.7, lo, hi))
        return self


def ss(e0, e1, x):
    return smoothstep(e0, e1, x)


# MARK: - Геометрия

def surface(name, nu, nv, fn):
    """Сетка по параметрам (u, v) от 0 до 1 с UV: u - вдоль листа, v - поперек. Нормаль = du x dv."""
    verts = []
    for i in range(nu + 1):
        for j in range(nv + 1):
            verts.append(tuple(fn(i / nu, j / nv)))
    faces = []
    for i in range(nu):
        for j in range(nv):
            a = i * (nv + 1) + j
            faces.append((a, a + nv + 1, a + nv + 2, a + 1))
    ob = from_data(name, verts, faces)
    uvl = ob.data.uv_layers.new(name="UVMap")
    loops = ob.data.loops
    for p in ob.data.polygons:
        for li in p.loop_indices:
            i, j = divmod(loops[li].vertex_index, nv + 1)
            uvl.data[li].uv = (i / nu, j / nv)
    return ob


def lathe_fn(name, rfn, z0, z1, n=64, segs=96, wobble=None):
    """Тело вращения по функции радиуса rfn(t), t 0..1 от z0 до z1; концы закрыты. wobble(a, t) - множитель радиуса."""
    prof = [(0.0, z0)]
    for k in range(n + 1):
        t = k / n
        prof.append((max(1e-4, rfn(t)), z0 + (z1 - z0) * t))
    prof.append((0.0, z1))
    ob = lathe(name, prof, segs)
    if wobble:
        def fn(co):
            a = math.atan2(co.y, co.x)
            t = (co.z - z0) / (z1 - z0)
            k = wobble(a, t)
            return Vector((co.x * k, co.y * k, co.z))
        deform(ob, fn)
    return ob


def to_axis_x(ob):
    """Тело вдоль Z кладем вдоль X."""
    ob.rotation_euler = (0, math.radians(90), 0)
    return apply_transform(ob)


def transform(objs, m):
    for o in objs:
        o.matrix_world = m @ o.matrix_world
    bpy.context.view_layer.update()
    return objs


def bake_all(objs):
    for o in objs:
        if o.type == "MESH":
            o.data.transform(o.matrix_world)
            o.matrix_world = Matrix.Identity(4)
    bpy.context.view_layer.update()
    return objs


def twine_mat(name, light=(0.96, 0.88, 0.70), dark=(0.80, 0.64, 0.42), stripes=None):
    """Бечевка: скрученные волокна (полоски по спирали в UV трубки)."""
    mat = material(name, [(0.0, light), (1.0, light)], rough=0.6, sheen=0.4, coat=0.1)
    stops = stripes or [(0.0, light), (0.45, light), (0.55, dark), (0.95, dark), (1.0, light)]
    EV.uv_pattern(mat, stops, fu=34.0, fv=3.0)
    return mat


def wrap_ring(name, center, axis_r, z_axis, r_tube, turns=1.0, n=120, rise=0.0, wob=0.0, seed=0):
    """Витки бечевки вокруг оси z_axis (единичный вектор) радиусом axis_r: точки для sweep."""
    zax = Vector(z_axis).normalized()
    xax = zax.orthogonal().normalized()
    yax = zax.cross(xax)
    pts = []
    for k in range(n + 1):
        t = k / n
        a = 2 * math.pi * turns * t
        rr = axis_r(a) if callable(axis_r) else axis_r
        rr += wob * noise.noise(Vector((math.cos(a), math.sin(a), seed)))
        p = Vector(center) + xax * rr * math.cos(a) + yax * rr * math.sin(a) + zax * (rise * (t - 0.5))
        pts.append(tuple(p))
    return pts


# MARK: - Котлета

def patty():
    """Котлета для бургера: неровный край, бугристый фарш, вдавленные следы решетки, темная корочка по ребру."""
    r, h = 1.0, 0.44
    ob = rounded_disc("Patty", r, h, 2.3, 44)
    ang = math.radians(62)
    spacing = 0.46

    def outline(a):
        return (1.0 + 0.035 * math.sin(3 * a + 0.7) + 0.022 * math.sin(5 * a + 2.1)
                + 0.03 * fbm(Vector((math.cos(a) * 1.7, math.sin(a) * 1.7, 0.3))))

    def shape(co):
        a = math.atan2(co.y, co.x)
        rr = math.hypot(co.x, co.y)
        k = outline(a)
        z = co.z
        if z > 0:
            z += 0.06 * (1 - min(1.0, rr / r) ** 2)
        else:
            z *= 0.9
        return Vector((co.x * k, co.y * k, z))
    deform(ob, shape)
    subdivide(ob, 1)
    push_normals(ob, lambda co, n: 0.02 * fbm(co * 2.6, 3) + 0.007 * fbm(co * 7.0, 2)
                 + 0.003 * noise.noise(co * 15.0))

    def groove(co, n):
        s = (co.x * math.cos(ang) + co.y * math.sin(ang)) / spacing + 0.5
        d = abs((s % 1.0) - 0.5)
        g = math.exp(-(d / 0.12) ** 2)
        return -0.022 * g * ss(0.55, 0.85, n.z)
    push_normals(ob, groove)
    smooth(ob)

    sh = Sh("PattyMat", rough=0.45, sss=0.15, sss_radius=(1.0, 0.35, 0.2), coat=0.4, coat_rough=0.2)
    _, _, nz = sh.xyz("Normal")
    wob = sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 3.5, 4), 0.5), 0.35)
    fac = sh.math("ADD", nz, wob)
    base = sh.ramp(fac, [(0.0, (0.28, 0.12, 0.05)), (0.25, (0.36, 0.16, 0.07)), (0.48, (0.46, 0.21, 0.09)),
                         (0.62, (0.27, 0.11, 0.05)), (0.72, (0.40, 0.18, 0.08)), (0.86, (0.54, 0.27, 0.12)),
                         (1.0, (0.60, 0.31, 0.14))])
    # кусочки фарша: ячейки вороного чуть светлее и темнее
    cells = sh.voronoi(None, 20.0, "F1", 1.0, "Color")
    cr, _, _ = sh.xyz(cells)
    base = sh.mix(sh.remap(cr, 0.6, 0.95, 0.0, 0.3), base, (0.70, 0.40, 0.22))
    base = sh.mix(sh.remap(cr, 0.25, 0.0, 0.0, 0.35), base, (0.26, 0.11, 0.05))
    # следы решетки
    x, y, _ = sh.xyz()
    s = sh.math("ADD", sh.math("MULTIPLY", sh.math("ADD", sh.math("MULTIPLY", x, math.cos(ang)),
                                                    sh.math("MULTIPLY", y, math.sin(ang))), 1 / spacing), 0.5)
    s = sh.math("ADD", s, sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 6.0, 3), 0.5), 0.12))
    d = sh.math("PINGPONG", s, 0.5)
    top = sh.remap(nz, 0.5, 0.8)
    halo = sh.math("MULTIPLY", sh.remap(d, 0.2, 0.1, 0.0, 0.7), top)
    grill = sh.math("MULTIPLY", sh.remap(d, 0.12, 0.075, 0.0, 1.0), top)
    base = sh.mix(halo, base, (0.32, 0.14, 0.06))
    base = sh.mix(grill, base, (0.17, 0.075, 0.035))
    sh.color(base)
    sh.set("Roughness", sh.remap(sh.noise(None, 5, 3), 0.3, 0.7, 0.35, 0.65))
    sh.bump(sh.voronoi(None, 20.0, "F1"), 0.25, 0.01, invert=True)
    sh.bump(sh.noise(None, 38.0, 4), 0.18, 0.006)
    sh.bump(grill, 0.25, 0.02, invert=True)
    assign(ob, sh.mat)
    return rotate_all([ob], (math.radians(20), 0, math.radians(-8)))


# MARK: - Сырой стейк

def beef():
    """Сырой стейк рибай: мраморные прожилки жира, жировой край вдоль одной стороны, влажный блеск."""
    H = 0.34
    outline = MX.polar_outline(lambda a: 1.0 + 0.12 * math.cos(a + 0.5) + 0.07 * math.cos(2 * a + 1.1)
                               + 0.05 * math.sin(3 * a + 0.4) + 0.025 * math.cos(5 * a + 2.0))
    outline = [(x * 1.12, y * 0.80) for x, y in outline]
    reach = MX.reach_fn(outline)
    ob = MX.outline_slab("Steak", outline, H, p=2.6, cuts=44)
    deform(ob, lambda co: Vector((co.x, co.y, co.z + H / 2)))
    subdivide(ob, 1)

    def fat_of(co):
        a = math.atan2(co.y, co.x)
        t = math.hypot(co.x, co.y) / max(1e-6, reach(a))
        # жир вдоль дальней левой стороны
        w = ss(0.15, 0.75, math.cos(a + math.radians(80)))
        band = 0.17 + 0.04 * math.sin(7 * a)
        return w * ss(1.0 - band - 0.04, 1.0 - band + 0.02, t)
    push_normals(ob, lambda co, n: 0.016 * fbm(co * 2.0, 3) + 0.005 * fbm(co * 9, 2) + 0.018 * fat_of(co))
    smooth(ob)
    EV.set_attr(ob, "fat", lambda co, n: fat_of(co))

    sh = Sh("SteakMat", rough=0.32, sss=0.3, sss_radius=(1.0, 0.25, 0.2), sss_scale=0.05, coat=0.6, coat_rough=0.08)
    _, _, nz = sh.xyz("Normal")
    meat = sh.ramp(sh.math("ADD", nz, sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 3, 4), 0.5), 0.5)),
                   [(0.0, (0.50, 0.04, 0.07)), (0.45, (0.66, 0.07, 0.10)), (0.8, (0.80, 0.12, 0.15)),
                    (1.0, (0.86, 0.18, 0.19))])
    # волокна мышцы
    fib = sh.noise(sh.mapping(None, scale=(1.5, 9.0, 1.5)), 6.0, 3)
    meat = sh.mix(sh.remap(fib, 0.45, 0.65, 0.0, 0.18), meat, (0.95, 0.32, 0.32))
    # мраморность: тонкие изогнутые прожилки
    v1 = sh.noise(None, 1.6, 6, 0.6, distortion=1.4)
    m1 = sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", v1, 0.5)), 0.014, 0.004, 0.0, 0.95)
    v2 = sh.noise(sh.mapping(None, loc=(3.1, 1.7, 0.4)), 3.6, 5, 0.6, distortion=1.0)
    m2 = sh.remap(sh.math("ABSOLUTE", sh.math("SUBTRACT", v2, 0.5)), 0.008, 0.002, 0.0, 0.6)
    flecks = sh.remap(sh.voronoi(None, 22.0, "F1"), 0.07, 0.03, 0.0, 0.7)
    marble = sh.math("MAXIMUM", sh.math("MAXIMUM", m1, m2), sh.math("MULTIPLY", flecks,
                                                                     sh.remap(sh.noise(None, 4, 2), 0.58, 0.68)))
    meat = sh.mix(marble, meat, (1.0, 0.90, 0.86))
    fat = sh.attr("fat")
    meat = sh.mix(fat, meat, sh.ramp(sh.noise(None, 8, 3), [(0.3, (1.0, 0.94, 0.86)), (0.7, (0.98, 0.86, 0.76))]))
    sh.color(meat)
    sh.set("Roughness", sh.remap(sh.noise(None, 7, 3), 0.3, 0.7, 0.22, 0.45))
    sh.bump(fib, 0.08, 0.01)
    sh.bump(marble, 0.12, 0.008)
    sh.bump(sh.noise(None, 40, 3), 0.08, 0.004)
    assign(ob, sh.mat)
    return rotate_all([ob], (math.radians(30), 0, math.radians(-14)))


# MARK: - Сосиски

def sausage_mat(name):
    sh = Sh(name, rough=0.3, sss=0.3, sss_radius=(1.0, 0.3, 0.2), sss_scale=0.06, coat=0.85, coat_rough=0.06,
            sheen=0.25, sheen_rough=0.3)
    _, _, nz = sh.xyz("Normal")
    base = sh.ramp(nz, [(0.0, (0.44, 0.11, 0.06)), (0.4, (0.62, 0.18, 0.09)), (0.75, (0.75, 0.27, 0.13)),
                        (1.0, (0.85, 0.38, 0.20))])
    # подрумяненные пятна
    brown = sh.remap(sh.noise(None, 2.4, 4, 0.55), 0.5, 0.72, 0.0, 0.55)
    base = sh.mix(brown, base, (0.50, 0.15, 0.07))
    # кусочки шпика и перец
    spots = sh.voronoi(None, 34.0, "F1", 1.0, "Distance")
    cells = sh.voronoi(None, 34.0, "F1", 1.0, "Color")
    cr, cg, _ = sh.xyz(cells)
    fatm = sh.math("MULTIPLY", sh.remap(spots, 0.16, 0.08), sh.remap(cr, 0.7, 0.8))
    base = sh.mix(sh.math("MULTIPLY", fatm, 0.45), base, (0.98, 0.70, 0.56))
    pep = sh.math("MULTIPLY", sh.remap(spots, 0.10, 0.05), sh.remap(cg, 0.86, 0.92))
    base = sh.mix(sh.math("MULTIPLY", pep, 0.7), base, (0.30, 0.10, 0.05))
    sh.color(base)
    sh.bump(sh.noise(None, 30.0, 3), 0.08, 0.005)
    sh.bump(spots, 0.06, 0.004, invert=True)
    return sh.mat


def sausage_link(name, L, R, mat, seed=0):
    """Колбаска вдоль Z от 0 до L: пухлое тело, перетянутые концы со складочками оболочки."""
    neck = 0.055

    def rfn(t):
        s = abs(2 * t - 1)
        body = R * (1 - s ** 4.5) ** 0.42
        tip = neck * (1 - ss(0.985, 1.0, s) * 0.6)
        return max(body, tip * ss(0.9, 0.97, s))

    def wob(a, t):
        s = abs(2 * t - 1)
        wr = ss(0.62, 0.92, s) * (1 - ss(0.97, 1.0, s))
        return (1.0 + 0.045 * wr * math.cos(11 * a + 6 * t + seed) + 0.01 * math.sin(2 * a + seed)
                + 0.012 * noise.noise(Vector((math.cos(a), math.sin(a), t * 4 + seed))))
    ob = lathe_fn(name, rfn, 0.0, L, 120, 96, wob)
    subdivide(ob, 1)
    smooth(ob)
    return assign(ob, mat)


def sausage():
    """Две пухлые сосиски-колбаски в связке, свободный конец перевязан бечевкой."""
    mat = sausage_mat("SausageMat")
    L, R = 1.35, 0.34
    a = sausage_link("Link0", L, R, mat, 0.3)
    b = sausage_link("Link1", L * 0.96, R * 0.98, mat, 1.7)
    to_axis_x(a)
    to_axis_x(b)
    a.location.x = -L - 0.02
    apply_transform(a)
    # перемычка: скрученная оболочка между звеньями
    twist = sausage_link("Twist", 0.16, 0.07, mat, 2.4)
    to_axis_x(twist)
    twist.location.x = -0.10
    apply_transform(twist)
    parts = [a, b, twist]
    # бечевка на свободном конце
    tw = twine_mat("SausageTwine")
    x_end = L * 0.96 + 0.01
    ring = EV.sweep("TieRing", wrap_ring("Tie", (x_end - 0.02, 0, 0), 0.08, (1, 0, 0), 0.03, 1.0, 64),
                    0.03, segs=12, step=0.01)
    assign(ring, tw)
    parts.append(ring)
    for i, (dy, dz) in enumerate(((0.10, -0.05), (-0.04, -0.12))):
        pts = EV.spline([(x_end, 0.0, -0.07), (x_end + 0.10, dy * 0.6, -0.10 + dz * 0.3),
                         (x_end + 0.18, dy, -0.16 + dz), (x_end + 0.22, dy * 1.2, -0.26 + dz)], 6)
        tail = EV.sweep(f"TieTail{i}", pts, lambda t: 0.028 * (1 - 0.25 * t), segs=10, step=0.01)
        assign(tail, tw)
        parts.append(tail)
    bake_all(parts)
    for o in parts:
        bend(o, 1.3)
    smooth(a), smooth(b), smooth(twist)
    rotate_all(parts, (0, 0, math.radians(-10)))
    return rotate_all(parts, (math.radians(22), 0, 0))


# MARK: - Булка для хот-дога

def hotdog_bun():
    """Раскрытая булка: надрез сверху, половинки соединены снизу, мягкий мякиш с порами, светлая полоса на боках."""
    L, R = 2.5, 0.46
    sh = Sh("HBunCrust", rough=0.36, sss=0.25, sss_radius=(1.0, 0.6, 0.3), coat=0.45, coat_rough=0.18)
    _, _, nz = sh.xyz("Normal")
    wob = sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 2.0, 2), 0.5), 0.16)
    crust = sh.ramp(sh.remap(sh.math("ADD", nz, wob), -1.0, 1.0, 0.0, 1.0, smooth=False),
                    [(0.0, (0.88, 0.56, 0.24)), (0.30, (0.96, 0.70, 0.36)), (0.44, (1.0, 0.88, 0.64)),
                     (0.56, (1.0, 0.86, 0.60)), (0.68, (0.97, 0.68, 0.30)), (0.85, (0.89, 0.54, 0.20)),
                     (1.0, (0.83, 0.47, 0.16))])
    sh.color(crust)
    sh.bump(sh.noise(None, 16, 4), 0.06, 0.01)
    sh.bump(sh.noise(None, 60, 2), 0.05, 0.003)
    crust_mat = sh.mat

    cm = Sh("HBunCrumb", rough=0.78, sss=0.3, sss_radius=(1.0, 0.8, 0.5))
    pores = cm.voronoi(None, 26.0, "F1")
    pores2 = cm.voronoi(cm.mapping(None, loc=(0.3, 0.7, 0.1)), 52.0, "F1")
    col = cm.ramp(cm.noise(None, 4, 3), [(0.3, (1.0, 0.93, 0.76)), (0.7, (0.99, 0.88, 0.68))])
    col = cm.mix(cm.remap(pores, 0.10, 0.02, 0.0, 0.85), col, (0.84, 0.64, 0.40))
    col = cm.mix(cm.remap(pores2, 0.08, 0.02, 0.0, 0.5), col, (0.92, 0.78, 0.56))
    cm.color(col)
    cm.bump(pores, 0.5, 0.02)
    cm.bump(pores2, 0.3, 0.01)
    cm.bump(cm.noise(None, 12, 3), 0.15, 0.01)
    crumb_mat = cm.mat

    parts = []
    hinge_z = -R * 0.62
    for side in (-1, 1):
        h = capsule(f"HBun{side}", L, R, 72, 64, pinch=0.08)

        def shp(co):
            u = co.x / (L / 2)
            z = co.z * 0.88
            if z < -0.55 * R:
                z = -0.55 * R + (z + 0.55 * R) * 0.45
            k = 1.0 + 0.03 * fbm(co * 2.0)
            return Vector((co.x * k, co.y * (1.0 - 0.04 * u * u), z + 0.03 * fbm(co * 1.5 + Vector((side, 0, 0)))))
        deform(h, shp)
        bisect(h, (0, 0, 0), (0, -side, 0))
        bevel(h, 0.06, 4, 50)
        subdivide(h, 1)
        # мякиш чуть выпуклый и неровный
        push_normals(h, lambda co, n, s=side: (0.025 * max(0.0, 1 - (co.x / (L / 2)) ** 2) + 0.01 * fbm(co * 6))
                     if n.y * s < -0.8 else 0.006 * fbm(co * 5))
        smooth(h)
        assign_faces(h, crust_mat, [(lambda n, c, s=side: n.y * s < -0.6, crumb_mat)])
        h.location = (0, side * 0.012, 0)
        rotate_all([h], (math.radians(-side * 27), 0, 0), pivot=(0, 0, hinge_z))
        parts.append(h)
    rotate_all(parts, (0, 0, math.radians(-18)))
    return rotate_all(parts, (math.radians(38), 0, 0))


# MARK: - Листья: общий шейдер с прожилками по UV

def leaf_veins(sh, N=7.0, K=1.4, rib=0.05, vein=0.06, reach=0.85):
    """Маски прожилок по UV листа: центральная (u вдоль листа, v поперек) и боковые, идущие к кончику."""
    u, v, _ = sh.xyz("UV")
    vc = sh.math("MULTIPLY", sh.math("ABSOLUTE", sh.math("SUBTRACT", v, 0.5)), 2.0)
    mid = sh.math("MULTIPLY", sh.remap(vc, rib, rib * 0.35), sh.remap(u, 0.0, 0.05))
    s = sh.math("SUBTRACT", sh.math("MULTIPLY", u, N), sh.math("MULTIPLY", vc, K))
    d = sh.math("PINGPONG", s, 0.5)
    lat = sh.remap(d, vein, vein * 0.3)
    lat = sh.math("MULTIPLY", lat, sh.remap(vc, reach, reach * 0.6))
    lat = sh.math("MULTIPLY", lat, sh.remap(u, 0.04, 0.14))
    lat = sh.math("MULTIPLY", lat, sh.remap(u, 0.97, 0.85))
    return u, vc, mid, lat


def leaf_shader(name, stops, edge, vein_col, N=7.0, K=1.4, raised=True, rough=0.3, sss=0.35, coat=0.5,
                rib=0.05, vein=0.06, edge_from=0.55, bump=0.25, pucker=0.0):
    sh = Sh(name, rough=rough, sss=sss, sss_radius=(0.5, 1.0, 0.3), sss_scale=0.05, coat=coat, coat_rough=0.1)
    u, vc, mid, lat = leaf_veins(sh, N, K, rib, vein)
    col = sh.ramp(u, stops)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(vc, edge_from, 1.0), 0.75), col, edge)
    col = sh.mix(sh.math("MULTIPLY", sh.noise("Object", 9.0, 3), 0.18), col, edge)
    veins = sh.math("MAXIMUM", mid, sh.math("MULTIPLY", lat, 0.8))
    col = sh.mix(veins, col, vein_col)
    sh.color(col)
    sh.bump(veins, bump, 0.01, invert=not raised)
    if pucker:
        sh.bump(sh.noise("Object", 14.0, 3), pucker, 0.01)
    sh.rough_vary(rough * 0.8, rough * 1.3, 8.0)
    return sh.mat


# MARK: - Салат

def lettuce_leaf_obj(name, L, W, cup, curl, ruffle, waves, seed, mat, nu=84, nv=34):
    def w_of(u):
        return W * (0.09 + 0.91 * (u ** 0.55) * max(0.0, 1 - u ** 3.2) ** 0.5)

    def fn(u, v):
        y0 = 2 * v - 1
        w = w_of(u)
        x = u * L
        a = math.atan2(y0 * w, (u - 0.45) * L)
        e = max(ss(0.4, 1.0, abs(y0)), ss(0.8, 1.0, u)) * ss(0.08, 0.4, u)
        rf = ruffle * (0.5 + 0.9 * u) * e
        nn = noise.noise(Vector((u * 3.0, y0 * 1.5, seed)))
        z = cup * y0 * y0 * w - curl * L * max(0.0, u - 0.5) ** 2 * 2.2
        z += rf * math.sin(waves * a + seed + 1.6 * nn) + 0.45 * rf * math.sin(2.3 * waves * a + 2 * seed)
        z += 0.025 * L * noise.noise(Vector((u * 4, y0 * 2, seed + 5)))
        yy = y0 * w * (1.0 + 0.07 * e * math.sin(1.4 * waves * a + seed * 0.7))
        return Vector((x, yy, z))
    ob = surface(name, nu, nv, fn)
    solidify(ob, 0.022, 0.0)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, mat)
    # толстая светлая жилка от основания
    pts = [fn(t, 0.5) for t in [k / 30 * 0.8 for k in range(31)]]
    rib = EV.sweep(f"{name}Rib", pts, lambda t: 0.05 * W * (1.0 - 0.8 * t) + 0.008, segs=12, step=0.015)
    return [ob, rib]


def place_leaf(objs, base, psi, phi, spin=0.0):
    """Лист вдоль +X лицом вверх: наклон phi от вертикали, азимут psi, основание в base."""
    m = (Matrix.Translation(base) @ Matrix.Rotation(psi, 4, "Z") @ Matrix.Rotation(-(math.pi / 2 - phi), 4, "Y")
         @ Matrix.Rotation(spin, 4, "X"))
    return transform(objs, m)


def lettuce():
    """Кочан листового салата: розетка гофрированных листьев, светлая сердцевина, светлые жилки."""
    outer = leaf_shader("LettuceOuter", [(0.0, (0.86, 0.94, 0.62)), (0.25, (0.58, 0.82, 0.26)),
                                         (0.7, (0.38, 0.70, 0.14)), (1.0, (0.30, 0.62, 0.10))],
                        (0.22, 0.54, 0.08), (0.84, 0.95, 0.60), N=6.0, K=1.2, rib=0.06, vein=0.07)
    middle = leaf_shader("LettuceMid", [(0.0, (0.90, 0.96, 0.66)), (0.3, (0.64, 0.86, 0.30)),
                                        (1.0, (0.40, 0.72, 0.15))],
                         (0.28, 0.60, 0.10), (0.86, 0.96, 0.62), N=6.0, K=1.2, rib=0.06, vein=0.07)
    inner = leaf_shader("LettuceInner", [(0.0, (0.94, 0.98, 0.72)), (0.4, (0.76, 0.92, 0.40)),
                                         (1.0, (0.58, 0.84, 0.24))],
                        (0.44, 0.76, 0.16), (0.92, 0.98, 0.70), N=5.0, K=1.1, rib=0.07, vein=0.07)
    rib_mat = material("LettuceRib", [(0.0, (0.94, 0.98, 0.80)), (1.0, (0.78, 0.92, 0.52))], coord="z", lo=0.0,
                       hi=1.0, rough=0.3, sss=0.4, sss_radius=(0.6, 1.0, 0.4), coat=0.5)
    parts = []
    rnd = random.Random(11)
    layers = [(5, 50, 1.22, 0.66, outer, 0.10, 0.0), (4, 30, 1.08, 0.58, middle, 0.06, 0.5),
              (3, 13, 0.88, 0.48, inner, 0.03, 0.2)]
    k = 0
    for n, phi, L, W, mat, r0, off in layers:
        for i in range(n):
            psi = 2 * math.pi * (i + off) / n + rnd.uniform(-0.12, 0.12)
            lf = lettuce_leaf_obj(f"Lettuce{k}", L * rnd.uniform(0.94, 1.06), W, 0.42, 0.20 + 0.1 * (phi > 40),
                                  0.055 * L, 15, k * 1.37, mat)
            assign(lf[1], rib_mat)
            place_leaf(lf, (r0 * math.cos(psi), r0 * math.sin(psi), 0.05), psi,
                       math.radians(phi + rnd.uniform(-5, 5)), rnd.uniform(-0.12, 0.12))
            parts += lf
            k += 1
    heart = sphere("LettuceHeart", 0.22, 48, 32)
    heart.scale = (1.0, 1.0, 1.25)
    heart.location = (0, 0, 0.42)
    apply_transform(heart)
    push_normals(heart, lambda co, n: 0.03 * fbm(co * 9))
    smooth(heart)
    assign(heart, inner)
    stump = lathe("LettuceStump", [(0.0, -0.06), (0.13, -0.06), (0.16, 0.0), (0.12, 0.14), (0.0, 0.16)], 32)
    smooth(stump)
    assign(stump, rib_mat)
    parts += [heart, stump]
    return rotate_all(parts, (math.radians(8), 0, math.radians(10)))


# MARK: - Базилик

BASIL_N, BASIL_K = 5.5, 1.3


def basil_mat(name, light=False):
    stops = ([(0.0, (0.52, 0.84, 0.30)), (0.35, (0.36, 0.74, 0.18)), (1.0, (0.24, 0.62, 0.12))] if light else
             [(0.0, (0.40, 0.76, 0.22)), (0.35, (0.26, 0.64, 0.14)), (1.0, (0.18, 0.54, 0.10))])
    return leaf_shader(name, stops, (0.12, 0.44, 0.07), (0.52, 0.86, 0.32), N=BASIL_N, K=BASIL_K, raised=False,
                       rough=0.32, sss=0.3, coat=0.65, rib=0.06, vein=0.06, edge_from=0.6, bump=0.35, pucker=0.06)


def basil_blade(name, L, W, mat, dome=0.55, arch=0.10, droop=0.12, pucker=0.022, seed=0.0, nu=56, nv=26):
    """Лист базилика вдоль +X: выпуклый, края загнуты вниз, вздутия между вдавленными жилками."""
    def w_of(u):
        return 0.5 * W * math.sin(math.pi * min(1.0, u) ** 0.78) ** 0.8 * (1 - 0.12 * u) + 0.004

    def fn(u, v):
        y0 = 2 * v - 1
        vc = abs(y0)
        w = w_of(u)
        z = -dome * w * vc ** 2 + arch * L * math.sin(math.pi * u) - droop * L * max(0.0, u - 0.55) ** 2 * 3
        z -= 0.018 * L * math.exp(-(vc / 0.1) ** 2) * ss(0.05, 0.2, u)
        sv = u * BASIL_N - vc * BASIL_K
        z += pucker * L * math.sin(math.pi * sv) ** 2 * ss(0.12, 0.3, vc) * (1 - ss(0.75, 1.0, vc)) * ss(0.08, 0.2, u)
        z += 0.015 * L * noise.noise(Vector((u * 3, y0, seed)))
        return Vector((u * L, y0 * w * (1 + 0.03 * math.sin(u * 30 + seed) * vc ** 4), z))
    ob = surface(name, nu, nv, fn)
    solidify(ob, 0.012 * L / 0.6, 0.0)
    subdivide(ob, 1)
    smooth(ob)
    return assign(ob, mat)


def basil_leaf_at(name, L, W, mat, at, psi, elev, roll=0.0, stem_mat=None, petiole=0.06, seed=0.0):
    """Лист с черешком в точке at, направлен по азимуту psi с подъемом elev."""
    blade = basil_blade(name, L, W, mat, seed=seed)
    parts = [blade]
    blade.location = (petiole, 0, 0)
    apply_transform(blade)
    if stem_mat is not None and petiole > 0:
        pt = EV.sweep(name + "Pet", [(0.0, 0.0, 0.0), (petiole * 0.6, 0.0, 0.01), (petiole + 0.02, 0.0, 0.0)],
                      0.012 * L / 0.5 + 0.006, segs=10, step=0.01)
        assign(pt, stem_mat)
        parts.append(pt)
    m = (Matrix.Translation(at) @ Matrix.Rotation(psi, 4, "Z") @ Matrix.Rotation(-elev, 4, "Y")
         @ Matrix.Rotation(roll, 4, "X"))
    return transform(parts, m)


def basil():
    """Веточка базилика: стебель, пары листьев накрест, молодые листики на макушке."""
    dark = basil_mat("BasilDark")
    light = basil_mat("BasilLight", True)
    stem_mat = material("BasilStemMat", [(0.0, (0.50, 0.72, 0.28)), (1.0, (0.36, 0.64, 0.20))], coord="z", lo=0.0,
                        hi=1.3, rough=0.35, sss=0.3, coat=0.4)
    path = [(0.0, 0.0, 0.0), (0.03, 0.0, 0.25), (0.04, 0.01, 0.55), (0.02, 0.0, 0.85), (-0.01, 0.0, 1.05)]
    stem = EV.sweep("BasilStem", EV.spline(path, 8), lambda t: 0.04 * (1 - 0.45 * t), segs=14, step=0.015)
    assign(stem, stem_mat)
    parts = [stem]

    def at(z):
        for i in range(len(path) - 1):
            if path[i][2] <= z <= path[i + 1][2]:
                t = (z - path[i][2]) / (path[i + 1][2] - path[i][2])
                return Vector(path[i]).lerp(Vector(path[i + 1]), t)
        return Vector(path[-1])
    nodes = [(0.24, 0.0, 0.80, 0.54, 8, dark), (0.55, math.pi / 2, 0.68, 0.48, 20, dark),
             (0.82, 0.2, 0.52, 0.38, 32, light)]
    k = 0
    for z, psi0, L, W, elev, mat in nodes:
        for side in (0, math.pi):
            parts += basil_leaf_at(f"Basil{k}", L, W, mat, at(z), psi0 + side, math.radians(elev),
                                   0.0, stem_mat, 0.07, seed=k * 1.3)
            k += 1
    for j, (psi, elev, L) in enumerate(((1.8, 58, 0.34), (1.8 + math.pi, 56, 0.32), (0.3, 70, 0.24))):
        parts += basil_leaf_at(f"BasilTop{j}", L, L * 0.66, light, at(1.02), psi, math.radians(elev), 0.0, None, 0.0,
                               seed=j + 7)
    rotate_all(parts, (0, 0, math.radians(32)))
    return rotate_all(parts, (math.radians(-4), math.radians(10), 0))


# MARK: - Моцарелла

def drape_on(target, objs, lift=0.01, keep=0.6):
    """Кладет тонкие детали (листья) на поверхность target: каждую вершину опускаем лучом сверху."""
    bpy.context.view_layer.update()
    tw = target.matrix_world
    inv = tw.inverted()
    down = (inv.to_3x3() @ Vector((0, 0, -1))).normalized()
    for o in objs:
        mw = o.matrix_world
        mwi = mw.inverted()
        z0 = min((mw @ v.co).z for v in o.data.vertices)
        for v in o.data.vertices:
            w = mw @ v.co
            ok, loc, _, _ = target.ray_cast(inv @ Vector((w.x, w.y, 20.0)), down)
            if ok:
                w.z = (tw @ loc).z + lift + (w.z - z0) * keep
            v.co = mwi @ w
        o.data.update()
    return objs



def mozzarella():
    """Шарик свежей моцареллы с узелком на макушке, ломтик рядом и листья базилика."""
    R = 0.72
    ob = sphere("Mozzarella", 1.0, 96, 72)

    def shp(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.035 * fbm(co * 1.4)
        x, y, z = co.x * R * k, co.y * R * k, co.z * R * 0.88
        if z < -0.45 * R:
            z = -0.45 * R + (z + 0.45 * R) * 0.35
        t = ss(0.80, 1.0, co.z)
        x *= 1 - 0.55 * t
        y *= 1 - 0.55 * t
        z += 0.13 * R * t ** 1.5
        f = ss(0.3, 0.88, co.z) * (1 - ss(0.94, 1.0, co.z))
        kk = 1.0 + 0.04 * f * math.cos(7 * a + 3 * co.z)
        return Vector((x * kk, y * kk, z))
    deform(ob, shp)
    smooth(ob)
    sh = Sh("MozzMat", rough=0.3, sss=0.75, sss_radius=(1.0, 1.0, 0.9), sss_scale=0.12, coat=0.6, coat_rough=0.1)
    _, _, z = sh.xyz()
    col = sh.ramp(z, [(0.0, (0.84, 0.84, 0.80)), (0.45, (0.95, 0.95, 0.92)), (1.0, (1.0, 1.0, 0.98))])
    col = sh.mix(sh.math("MULTIPLY", sh.noise(None, 5, 3), 0.25), col, (0.88, 0.89, 0.86))
    sh.color(col)
    sh.rough_vary(0.18, 0.42, 4)
    sh.bump(sh.noise(None, 7, 4), 0.06, 0.02)
    sh.bump(sh.noise(sh.mapping(None, scale=(1, 1, 4)), 20, 2), 0.04, 0.005)
    mozz = sh.mat
    assign(ob, mozz)
    parts = [ob]
    MX.ground(parts, 0.0)
    bpy.context.view_layer.update()
    _, ztop, _ = MX.z_range([ob])
    bm = basil_mat("MozzBasil")
    leaves = []
    for i, (psi, L, W, mat) in enumerate(((-118, 0.62, 0.42, bm), (-52, 0.58, 0.40, bm),
                                          (60, 0.40, 0.28, basil_mat("MozzBasilLight", True)))):
        lf = basil_leaf_at(f"MozzLeaf{i}", L, W, mat, (0.0, 0.0, ztop + 0.3), math.radians(psi), 0.0, 0.0, None,
                           0.0, seed=i + 1.0)
        a = math.radians(psi)
        for o in lf:
            o.location += Vector((0.06 * math.cos(a), 0.06 * math.sin(a), 0))
        leaves += lf
    drape_on(ob, leaves, 0.012, 0.7)
    parts += leaves
    return rotate_all(parts, (0, 0, math.radians(-8)))


# MARK: - Лук-порей

def leek_leaf(name, r_i, psi, z0, L, u_s, alpha_max, droop, mat, nu=110, nv=30, seed=0.0, width=1.0):
    """Лист порея: внизу обертка вокруг стебля (сходит на нет V-вырезом), выше желобок, лист отгибается наружу."""
    d = Vector((math.cos(psi), math.sin(psi), 0.0))
    zax = Vector((0, 0, 1))
    W = math.pi * r_i * width
    steps = 600
    path, frames = [], []
    pos = r_i * d + Vector((0, 0, z0))
    for k in range(steps + 1):
        u = k / steps
        al = alpha_max * ss(u_s * 0.9, u_s + 0.4, u) + droop * max(0.0, u - 0.55) ** 2
        T = d * math.sin(al) + zax * math.cos(al)
        N = d * math.cos(al) - zax * math.sin(al)
        path.append(pos.copy())
        frames.append((T, N))
        pos = pos + T * (L / steps)

    def fn(u, v):
        k = min(steps, int(round(u * steps)))
        P = path[k]
        T, N = frames[k]
        B = T.cross(N)
        if u < u_s:
            span = math.pi + 0.97 * math.pi * (1 - u / u_s) ** 1.2
            R = r_i
        else:
            span = 1.5 + (math.pi - 1.5) * (1 - ss(u_s, u_s + 0.3, u))
            wd = W * (1 - ss(0.75, 1.0, u) ** 1.5 * 0.7)
            R = wd / span
        th = (2 * v - 1) * span / 2
        C = P - N * R
        q = C + (N * math.cos(th) + B * math.sin(th)) * R
        q += N * 0.006 * noise.noise(Vector((u * 6, v * 3, seed)))
        return q
    ob = surface(name, nu, nv, fn)
    solidify(ob, 0.014, 0.0)
    subdivide(ob, 1)
    smooth(ob)
    return assign(ob, mat)


def leek():
    """Порей: белая ножка с прожилками, веер сине-зеленых листьев слоями, бородка корешков."""
    rs = 0.22
    sh = Sh("LeekShaft", rough=0.3, sss=0.45, sss_radius=(0.8, 1.0, 0.6), sss_scale=0.06, coat=0.5, coat_rough=0.12,
            sheen=0.2)
    _, _, z = sh.xyz()
    col = sh.ramp(sh.remap(z, 0.0, 1.5, smooth=False), [(0.0, (0.94, 0.93, 0.86)), (0.07, (0.99, 0.99, 0.95)),
                                                      (0.47, (0.97, 0.98, 0.90)), (0.73, (0.84, 0.93, 0.62)),
                                                      (1.0, (0.66, 0.84, 0.40))])
    ang = sh.math("ARCTAN2", *sh.xyz()[1::-1])
    st = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", ang, 16.0), sh.math(
        "MULTIPLY", sh.noise(None, 3, 2), 1.0)), 0.5)
    col = sh.mix(sh.remap(st, 0.12, 0.0, 0.0, 0.3), col, (0.80, 0.86, 0.68))
    sh.color(col)
    sh.bump(st, 0.06, 0.004, invert=True)
    shaft = lathe_fn("LeekShaft", lambda t: rs * (0.94 + 0.08 * ss(0.0, 0.06, t) - 0.05 * t), 0.0, 1.5, 70, 72)
    subdivide(shaft, 1)
    smooth(shaft)
    assign(shaft, sh.mat)
    parts = [shaft]
    lm = Sh("LeekLeafMat", rough=0.4, sss=0.3, sss_radius=(0.5, 1.0, 0.4), sss_scale=0.05, coat=0.35,
            coat_rough=0.18, sheen=0.35, sheen_rough=0.4)
    u, v, _ = lm.xyz("UV")
    col = lm.ramp(u, [(0.0, (0.84, 0.93, 0.62)), (0.2, (0.60, 0.80, 0.36)), (0.38, (0.28, 0.54, 0.28)),
                      (0.75, (0.18, 0.44, 0.26)), (1.0, (0.20, 0.46, 0.27))])
    stripes = lm.math("PINGPONG", lm.math("MULTIPLY", v, 22.0), 0.5)
    col = lm.mix(lm.remap(stripes, 0.12, 0.02, 0.0, 0.22), col, (0.66, 0.84, 0.56))
    col = lm.mix(lm.math("MULTIPLY", lm.noise("Object", 6, 3), 0.15), col, (0.16, 0.40, 0.22))
    lm.color(col)
    lm.bump(stripes, 0.08, 0.004)
    leaf_mat = lm.mat
    specs = [(1.04, 0.0, 1.00, 1.95, 0.2, math.radians(40), 1.6),
             (0.99, math.pi, 1.12, 1.85, 0.2, math.radians(32), 1.3),
             (0.93, 0.0, 1.24, 1.70, 0.2, math.radians(23), 1.0),
             (0.86, math.pi, 1.36, 1.50, 0.2, math.radians(14), 0.6),
             (0.78, 0.0, 1.46, 1.25, 0.2, math.radians(5), 0.3)]
    for i, (kr, psi, z0, L, us, am, dr) in enumerate(specs):
        parts.append(leek_leaf(f"LeekLeaf{i}", rs * kr, psi, z0, L, us, am, dr, leaf_mat, seed=i * 2.1,
                               width=0.95))
    root_mat = material("LeekRoots", [(0.0, (0.82, 0.74, 0.58)), (1.0, (0.96, 0.92, 0.82))], coord="z", lo=-0.35,
                        hi=0.0, rough=0.6, sss=0.2, sheen=0.3)
    plate = sphere("LeekPlate", rs * 0.95, 48, 24)
    deform(plate, lambda co: Vector((co.x, co.y, min(co.z, 0.0) * 0.35 + 0.01)))
    smooth(plate)
    assign(plate, root_mat)
    parts.append(plate)
    rnd = random.Random(5)
    for i in range(22):
        a = 2 * math.pi * i / 22 + rnd.uniform(-0.1, 0.1)
        r0 = rs * rnd.uniform(0.2, 0.75)
        ln = rnd.uniform(0.18, 0.34)
        out = rnd.uniform(0.5, 1.2)
        pts = [(math.cos(a) * (r0 + out * ln * t) + 0.03 * math.sin(9 * t + i), math.sin(a) * (r0 + out * ln * t),
                -0.02 - ln * t + 0.05 * t * t) for t in [k / 8 for k in range(9)]]
        rt = EV.sweep(f"LeekRoot{i}", pts, lambda t: 0.013 * (1 - 0.6 * t), segs=8, step=0.012)
        assign(rt, root_mat)
        parts.append(rt)
    rotate_all(parts, (0, math.radians(50), 0))
    return rotate_all(parts, (math.radians(8), 0, math.radians(-10)))


# MARK: - Тесто

def flour_patch(name, R, seed=0, heap=0.05):
    """Мучная россыпь на столе: тонкое пятно с неровным краем и холмиком."""
    ob = polar_disc(name, 26, 120, 1.0, 1.0)

    def fn(co):
        a = math.atan2(co.y, co.x)
        t = math.hypot(co.x, co.y)
        edge = 1.0 + 0.16 * fbm(Vector((math.cos(a) * 2.2, math.sin(a) * 2.2, seed))) + 0.06 * math.sin(5 * a + seed)
        r = t * R * edge
        z = heap * max(0.0, 1 - t * t) ** 1.5 + 0.012 * fbm(co * 6 + Vector((seed, 0, 0))) * max(0.0, 1 - t)
        return Vector((r * math.cos(a), r * math.sin(a), max(0.0, z)))
    deform(ob, fn)
    solidify(ob, 0.012, 1.0)
    smooth(ob)
    return ob


def powder_mat(name):
    sh = Sh(name, rough=0.85, sss=0.2, sss_radius=(1.0, 1.0, 1.0), sheen=0.5, sheen_rough=0.6)
    sh.color(sh.ramp(sh.noise(None, 6, 3), [(0.3, (1.0, 1.0, 0.98)), (0.7, (0.95, 0.94, 0.90))]))
    sh.bump(sh.noise(None, 30, 5), 0.35, 0.01)
    sh.bump(sh.voronoi(None, 60, "F1"), 0.2, 0.004, invert=True)
    return sh.mat


def dough():
    """Шар теста: мягкий, чуть осевший, со складкой-защипом сверху, пятна муки, мучная россыпь под ним."""
    R = 0.85
    ob = sphere("Dough", 1.0, 112, 80)

    def shp(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.045 * fbm(co * 1.2 + Vector((0.3, 0.1, 0.0))) + 0.02 * math.sin(2 * a + 0.4)
        z = co.z * 0.72 if co.z > 0 else co.z * 0.40
        sag = 1.0 + 0.13 * ss(0.3, -0.7, co.z)
        return Vector((co.x * k * R * sag, co.y * k * R * sag, z * R))
    deform(ob, shp)

    def crease(co, n):
        c = -0.10 + 0.14 * math.sin(1.4 * co.x + 0.3)
        d = co.y - c
        g = math.exp(-(d / 0.05) ** 2)
        lip = math.exp(-((d + 0.09) / 0.09) ** 2)
        m = ss(0.35, 0.75, n.z) * (1 - ss(0.45, 0.75, abs(co.x)))
        return (-0.06 * g + 0.035 * lip) * m + 0.008 * fbm(co * 5.0)
    push_normals(ob, crease)
    smooth(ob)
    sh = Sh("DoughMat", rough=0.5, sss=0.65, sss_radius=(1.0, 0.75, 0.45), sss_scale=0.15, sheen=0.45,
            sheen_rough=0.5, coat=0.15, coat_rough=0.3)
    _, _, z = sh.xyz()
    _, _, nz = sh.xyz("Normal")
    col = sh.ramp(sh.remap(z, -0.34, 0.62, smooth=False), [(0.0, (0.90, 0.70, 0.46)), (0.4, (0.98, 0.83, 0.60)),
                                                          (1.0, (1.0, 0.90, 0.72))])
    top = sh.remap(nz, 0.15, 0.7)
    dust = sh.math("MULTIPLY", sh.remap(sh.noise(None, 2.2, 5, 0.65), 0.40, 0.62, 0.0, 0.85),
                   sh.remap(nz, 0.45, 0.85))
    specks = sh.math("MULTIPLY", sh.remap(sh.voronoi(None, 55.0, "F1"), 0.14, 0.06), sh.remap(nz, 0.0, 0.5))
    flour = sh.math("MAXIMUM", dust, sh.math("MULTIPLY", specks, 0.9))
    col = sh.mix(flour, col, (1.0, 1.0, 0.98))
    sh.color(col)
    sh.set("Roughness", sh.remap(flour, 0.0, 1.0, 0.42, 0.9, smooth=False))
    sh.bump(sh.noise(None, 45, 4), 0.06, 0.004)
    sh.bump(flour, 0.15, 0.006)
    assign(ob, sh.mat)
    MX.ground([ob], 0.012)
    patch = flour_patch("DoughFlour", 0.98, 1.3, 0.05)
    patch.location = (0.16, -0.10, 0.0)
    assign(patch, powder_mat("DoughPowder"))
    parts = [ob, patch]
    rnd = random.Random(3)
    for i in range(5):
        a = rnd.uniform(-2.2, -0.2)
        r = rnd.uniform(0.95, 1.15)
        c = sphere(f"DoughClump{i}", rnd.uniform(0.03, 0.05), 16, 10)
        c.scale = (1, 1, 0.55)
        c.location = (r * math.cos(a) + 0.1, r * math.sin(a), 0.01)
        apply_transform(c)
        assign(smooth(c), patch.data.materials[0])
        parts.append(c)
    parts += rolling_pin("DoughPin", (-0.05, -0.92, 0.0), math.radians(-14))
    return rotate_all(parts, (math.radians(10), 0, math.radians(-6)))


def rolling_pin(name, at, yaw, L=1.9, r=0.12):
    """Скалка: светлое дерево с волокнами, ручки потемнее."""
    wood = Sh(name + "Wood", rough=0.45, coat=0.35, coat_rough=0.2, sss=0.1)
    x, y, z = wood.xyz()
    grain = wood.noise(wood.mapping(None, scale=(0.6, 9.0, 9.0)), 3.0, 4, 0.55, distortion=0.6)
    col = wood.ramp(grain, [(0.3, (0.96, 0.80, 0.56)), (0.5, (0.90, 0.70, 0.44)), (0.7, (0.98, 0.84, 0.60))])
    wood.color(col)
    wood.bump(grain, 0.08, 0.005)
    handle = Sh(name + "Handle", rough=0.4, coat=0.45, coat_rough=0.15)
    handle.color(handle.ramp(handle.noise(handle.mapping(None, scale=(0.6, 8, 8)), 3, 3),
                             [(0.3, (0.78, 0.50, 0.28)), (0.7, (0.66, 0.40, 0.20))]))
    barrel = lathe_fn(name, lambda t: r * (1 - ss(0.94, 1.0, abs(2 * t - 1)) * 0.35), -L * 0.32, L * 0.32, 40, 48)
    to_axis_x(barrel)
    smooth(barrel)
    assign(barrel, wood.mat)
    parts = [barrel]
    for side in (-1, 1):
        def hr(t):
            return 0.055 + 0.03 * ss(0.55, 0.85, t) * (1 - ss(0.9, 1.0, t)) + 0.012 * (1 - t)
        h = lathe_fn(f"{name}H{side}", lambda t: hr(t) * (1 - ss(0.95, 1.0, t) * 0.5), 0.0, L * 0.18, 30, 32)
        to_axis_x(h)
        if side < 0:
            h.rotation_euler = (0, 0, math.pi)
            apply_transform(h)
        h.location.x = side * (L * 0.32 - 0.01)
        apply_transform(h)
        smooth(h)
        assign(h, handle.mat)
        parts.append(h)
    MX.ground(parts, 0.0)
    rotate_all(parts, (0, 0, yaw))
    for o in parts:
        o.location += Vector(at)
    return parts


# MARK: - Мука

def ray_y(target, x, z, from_front=True):
    """Точка на поверхности target по лучу вдоль Y (спереди)."""
    o = Vector((x, -10.0 if from_front else 10.0, z))
    d = Vector((0, 1.0 if from_front else -1.0, 0))
    ok, loc, nor, _ = target.ray_cast(o, d)
    return (loc, nor) if ok else (Vector((x, 0, z)), Vector((0, -1, 0)))


def flour():
    """Крафтовый мешок муки: подвернутый край, горка муки внутри, этикетка с колосом, просыпанная мука."""
    import bmesh
    W, D, H = 0.92, 0.62, 1.12
    bag = box_mesh("FlourBag", W, D, H, 0.0, cuts=16)
    bm = bmesh.new()
    bm.from_mesh(bag.data)
    top = [f for f in bm.faces if f.normal.z > 0.9 and f.calc_center_median().z > H - 1e-3]
    bmesh.ops.delete(bm, geom=top, context="FACES")
    bm.to_mesh(bag.data)
    bm.free()

    def shp(co):
        t = max(0.0, co.z / H)
        bul = math.sin(math.pi * min(1.0, 0.1 + t * 0.95))
        x = co.x * (1 + 0.06 * bul)
        y = co.y * (1 + 0.16 * bul)
        side = ss(0.7, 1.0, abs(co.x) / (W / 2))
        g = math.exp(-(co.y / 0.13) ** 2) * side * ss(0.35, 0.98, t)
        x -= math.copysign(0.09 * g, co.x)
        return Vector((x, y, co.z))
    deform(bag, shp)
    bevel(bag, 0.03, 3, 35)
    solidify(bag, 0.03, -1.0)
    subdivide(bag, 1)
    push_normals(bag, lambda co, n: 0.012 * fbm(Vector((co.x * 3, co.y * 3, co.z * 1.3)), 3)
                 + 0.006 * abs(noise.noise(co * 6.0)) - 0.004)
    smooth(bag)
    kraft = Sh("FlourKraft", rough=0.68, sss=0.1, sheen=0.35, sheen_rough=0.5, coat=0.12, coat_rough=0.4)
    _, _, z = kraft.xyz()
    col = kraft.ramp(kraft.remap(z, 0.0, H, smooth=False), [(0.0, (0.80, 0.62, 0.40)), (1.0, (0.90, 0.74, 0.52))])
    col = kraft.mix(kraft.remap(kraft.noise(None, 3, 4), 0.4, 0.7, 0.0, 0.35), col, (0.74, 0.55, 0.34))
    fibers = kraft.noise(kraft.mapping(None, scale=(14, 14, 3)), 4, 2)
    col = kraft.mix(kraft.remap(fibers, 0.6, 0.75, 0.0, 0.25), col, (0.64, 0.46, 0.28))
    kraft.color(col)
    kraft.bump(kraft.noise(None, 5, 4), 0.12, 0.02)
    kraft.bump(fibers, 0.06, 0.004)
    assign(bag, kraft.mat)
    parts = [bag]
    # подвернутый край: валик по периметру горловины
    rim = []
    hw, hd, rc = W / 2, D / 2, 0.08
    corners = [(hw - rc, hd - rc, 0), (-hw + rc, hd - rc, 90), (-hw + rc, -hd + rc, 180), (hw - rc, -hd + rc, 270)]
    for cx, cy, a0 in corners:
        for k in range(12):
            a = math.radians(a0 + 90 * k / 11)
            rim.append((cx + rc * math.cos(a), cy + rc * math.sin(a)))
    rim = rim[6:] + rim[:7]
    pts = []
    for x, y in rim:
        q = shp(Vector((x, y, H)))
        pts.append((q.x, q.y, H - 0.02))
    fold = EV.sweep("FlourFold", pts, 0.075, segs=16, step=0.02, section=(0.75, 1.0))
    push_normals(fold, lambda co, n: 0.008 * fbm(co * 5))
    fold_mat = Sh("FlourFoldMat", rough=0.68, sheen=0.35, coat=0.1)
    fold_mat.color(fold_mat.ramp(fold_mat.noise(None, 4, 4), [(0.3, (0.86, 0.68, 0.46)), (0.7, (0.78, 0.60, 0.38))]))
    fold_mat.bump(fold_mat.noise(None, 8, 4), 0.15, 0.02)
    assign(fold, fold_mat.mat)
    parts.append(fold)
    # горка муки
    pmat = powder_mat("FlourPowder")
    mound = sphere("FlourMound", 1.0, 64, 32)

    def mshape(co):
        z = max(co.z, -0.2)
        q = shp(Vector((co.x * (hw - 0.01), co.y * (hd - 0.01), H)))
        return Vector((q.x * 0.97, q.y * 0.97, H - 0.06 + z * 0.24 + 0.03 * fbm(co * 3)))
    deform(mound, mshape)
    smooth(mound)
    assign(mound, pmat)
    parts.append(mound)
    # этикетка на лицевой стороне по форме мешка
    bpy.context.view_layer.update()
    lab = polar_disc("FlourLabel", 16, 96, 1.0, 1.0)
    lw, lh, lz = 0.30, 0.27, 0.50

    def lfn(co):
        a = math.atan2(co.y, co.x)
        t = math.hypot(co.x, co.y)
        e = 1.0 / ((abs(math.cos(a)) ** 5 + abs(math.sin(a)) ** 5) ** 0.2)
        x, zz = t * e * lw * math.cos(a), lz + t * e * lh * math.sin(a)
        loc, _ = ray_y(bag, x, zz)
        return Vector((x, loc.y - 0.006, zz))
    deform(lab, lfn)
    solidify(lab, 0.006, 1.0)
    smooth(lab)
    lm = Sh("FlourLabelMat", rough=0.45, coat=0.3, coat_rough=0.2, sss=0.05)
    _, _, lzz = lm.xyz()
    band = lm.remap(lzz, lz + lh * 0.52, lz + lh * 0.58)
    col = lm.mix(band, (0.99, 0.97, 0.92), (0.20, 0.42, 0.82))
    low = lm.remap(lzz, lz - lh * 0.62, lz - lh * 0.68)
    col = lm.mix(low, col, (0.20, 0.42, 0.82))
    lm.color(col)
    assign(lab, lm.mat)
    parts.append(lab)
    # колос на этикетке
    gold = material("FlourWheat", [(0.0, (0.90, 0.60, 0.18)), (1.0, (1.0, 0.80, 0.34))], coord="z", lo=lz - 0.15,
                    hi=lz + 0.15, rough=0.3, coat=0.6, sss=0.2)
    stalk = []
    for k in range(9):
        zz = lz - 0.16 + 0.30 * k / 8
        x = 0.025 * math.sin(k * 0.4)
        loc, _ = ray_y(bag, x, zz)
        stalk.append((x, loc.y - 0.02, zz))
    st = EV.sweep("WheatStalk", stalk, 0.011, segs=8, step=0.01)
    assign(st, gold)
    parts.append(st)
    for k in range(4):
        for side in (-1, 1):
            zz = lz - 0.06 + 0.055 * k + (0.02 if side > 0 else 0)
            x = side * 0.035 + 0.02 * math.sin(k * 0.4)
            loc, _ = ray_y(bag, x, zz)
            g = sphere(f"Grain{k}{side}", 1.0, 16, 10)
            g.scale = (0.022, 0.012, 0.042)
            g.rotation_euler = (0, math.radians(-side * 32), 0)
            g.location = (x, loc.y - 0.022, zz)
            apply_transform(g)
            assign(smooth(g), gold)
            parts.append(g)
    tipz = lz + 0.17
    loc, _ = ray_y(bag, 0.04, tipz)
    g = sphere("GrainTip", 1.0, 16, 10)
    g.scale = (0.02, 0.012, 0.04)
    g.location = (0.035, loc.y - 0.022, tipz)
    apply_transform(g)
    assign(smooth(g), gold)
    parts.append(g)
    # просыпанная мука у мешка
    heap = flour_patch("FlourSpill", 0.36, 2.0, 0.2)
    heap.location = (0.40, -0.52, 0.0)
    assign(heap, pmat)
    parts.append(heap)
    return rotate_all(parts, (0, 0, math.radians(-16)))


# MARK: - Спагетти

def pasta():
    """Пучок сухих спагетти: много тонких соломинок, у перевязки сужение, концы веером; бечевка с бантом."""
    rnd = random.Random(8)
    mats = []
    for i, (c0, c1) in enumerate((((1.0, 0.80, 0.30), (1.0, 0.88, 0.46)), ((0.98, 0.74, 0.24), (1.0, 0.84, 0.38)),
                                   ((1.0, 0.86, 0.40), (1.0, 0.92, 0.56)))):
        sh = Sh(f"Spaghetti{i}", rough=0.28, sss=0.2, sss_radius=(1.0, 0.7, 0.2), sss_scale=0.02, coat=0.5,
                coat_rough=0.1)
        sh.set("Emission Color", _col(c1))
        sh.set("Emission Strength", 0.08)
        x, _, _ = sh.xyz()
        sh.color(sh.ramp(sh.math("ABSOLUTE", x), [(0.0, c0), (1.0, c1)]))
        sh.bump(sh.noise(None, 40, 2), 0.05, 0.002)
        mats.append(sh.mat)
    L = 2.6
    parts = []
    n = 100
    for i in range(n):
        a = rnd.uniform(0, 2 * math.pi)
        r = 0.135 * math.sqrt(rnd.random())
        y0, z0 = r * math.cos(a), r * math.sin(a)
        spread = rnd.uniform(0.9, 1.5)
        xo = rnd.uniform(-0.07, 0.07)
        jy, jz = rnd.uniform(-1, 1), rnd.uniform(-1, 1)
        pts = []
        for k in range(15):
            t = -1 + 2 * k / 14
            f = 1 + spread * abs(t) ** 1.5
            pts.append((t * L / 2 + xo, y0 * f + 0.02 * jy * t, z0 * f + 0.02 * jz * t))
        st = tube(f"Spag{i}", pts, 0.019)
        assign(smooth(st), mats[i % 3])
        parts.append(st)
    tw = twine_mat("PastaTwine", light=(0.98, 0.96, 0.92), dark=(0.86, 0.14, 0.12))
    wrap = EV.sweep("PastaWrap", wrap_ring("PastaWrap", (0, 0, 0), 0.165, (1, 0, 0), 0.026, 3.0, 220, rise=0.13),
                    0.026, segs=12, step=0.01)
    assign(wrap, tw)
    parts.append(wrap)
    top = Vector((0.0, 0.0, 0.19))
    knot = sphere("PastaKnot", 0.045, 24, 16)
    knot.location = top
    assign(smooth(knot), tw)
    parts.append(knot)
    for side in (-1, 1):
        loop = [top + Vector((0.18 * side * (1 - math.cos(th)) * 0.5 + 0.02 * side,
                              0.0 + 0.10 * math.sin(th) * side * 0.4,
                              0.11 * math.sin(th) + 0.02 * (1 - math.cos(th)))) for th in
                [math.pi * 2 * k / 30 for k in range(31)]]
        lp = EV.sweep(f"PastaBow{side}", loop, 0.024, segs=12, step=0.01)
        assign(lp, tw)
        parts.append(lp)
        tail = EV.spline([tuple(top), tuple(top + Vector((0.06 * side, -0.05, -0.08))),
                          tuple(top + Vector((0.10 * side, -0.10, -0.20))), tuple(top + Vector((0.16 * side, -0.12, -0.30)))], 6)
        tl = EV.sweep(f"PastaTail{side}", tail, lambda t: 0.024 * (1 - 0.2 * t), segs=12, step=0.01)
        assign(tl, tw)
        parts.append(tl)
    rotate_all(parts, (math.radians(-90), 0, 0))
    rotate_all(parts, (0, math.radians(-50), 0))
    return rotate_all(parts, (math.radians(4), 0, math.radians(-22)))


# MARK: - Гриссини

def grissino_mat(name):
    sh = Sh(name, rough=0.5, sss=0.25, sss_radius=(1.0, 0.7, 0.35), coat=0.3, coat_rough=0.2)
    _, _, z = sh.xyz()
    col = sh.ramp(sh.noise(None, 4.0, 4), [(0.3, (0.99, 0.84, 0.54)), (0.55, (0.95, 0.73, 0.40)),
                                           (0.75, (0.84, 0.56, 0.27))])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(None, 12, 3), 0.55, 0.7), 0.6), col, (1.0, 0.90, 0.68))
    salt = sh.remap(sh.voronoi(None, 26.0, "F1"), 0.07, 0.035)
    col = sh.mix(sh.math("MULTIPLY", salt, 0.9), col, (1.0, 0.99, 0.96))
    sh.color(col)
    sh.bump(sh.noise(None, 22, 4), 0.25, 0.006)
    sh.bump(salt, 0.3, 0.004)
    return sh.mat


def grissino(name, L, r, seed, mat):
    def rfn(t):
        s = abs(2 * t - 1)
        end = (1 - s ** 14) ** 0.35
        return r * end * (1 + 0.09 * noise.noise(Vector((t * 11, seed, 0.3))) + 0.04 * math.sin(t * 60 + seed))

    def wob(a, t):
        return 1.0 + 0.05 * noise.noise(Vector((math.cos(a) * 0.8, math.sin(a) * 0.8, t * 14 + seed)))
    ob = lathe_fn(name, rfn, 0.0, L, 140, 20, wob)
    deform(ob, lambda co: Vector((co.x + 0.035 * math.sin(co.z * 1.7 + seed), co.y + 0.02 * math.sin(co.z * 2.3), co.z)))
    smooth(ob)
    return assign(ob, mat)


def grissini():
    """Пучок гриссини веером в бумажной ленте с итальянским триколором."""
    mat = grissino_mat("GrissinoMat")
    rnd = random.Random(4)
    parts = []
    n = 9
    zb = 0.64
    for i in range(n):
        f = (i - (n - 1) / 2) / ((n - 1) / 2)
        L = rnd.uniform(2.35, 2.6) - 0.15 * abs(f)
        g = grissino(f"Gris{i}", L, 0.06, i * 1.7, mat)
        # веер в плоскости к камере, перехвачен лентой на высоте zb: ниже ножки расходятся зеркально
        t = math.radians(17 * f + rnd.uniform(-1.5, 1.5))
        m = Matrix.Rotation(t, 4, "Y") @ Matrix.Rotation(math.radians(rnd.uniform(-3, 3)), 4, "X")
        p = m @ Vector((0, 0, zb))
        px, py = 0.08 * f, (0.04 if i % 2 else -0.04) + rnd.uniform(-0.01, 0.01)
        g.matrix_world = Matrix.Translation((px - p.x, py - p.y, zb - p.z)) @ m
        apply_transform(g)
        parts.append(g)
    MX.ground(parts)
    band_z0, band_h = 0.50, 0.28
    sh = Sh("GrisBand", rough=0.4, coat=0.35, coat_rough=0.2, sheen=0.2)
    x, y, z = sh.xyz()
    ang = sh.math("ARCTAN2", x, sh.math("MULTIPLY", y, -1.0))
    col = sh.mix(sh.remap(ang, -0.35, -0.30), (0.12, 0.56, 0.24), (0.99, 0.98, 0.95))
    col = sh.mix(sh.remap(ang, 0.30, 0.35), col, (0.86, 0.14, 0.14))
    edge = sh.math("MAXIMUM", sh.remap(z, band_z0 + 0.03, band_z0 + 0.02), sh.remap(z, band_z0 + band_h - 0.03,
                                                                                band_z0 + band_h - 0.02))
    col = sh.mix(sh.math("MULTIPLY", edge, 0.5), col, (0.86, 0.80, 0.68))
    sh.color(col)
    sh.bump(sh.noise(None, 10, 3), 0.1, 0.01)
    rb = 0.21
    band = lathe("GrisBand", [(rb - 0.012, band_z0), (rb + 0.01, band_z0 - 0.002), (rb + 0.016, band_z0 + 0.01),
                              (rb + 0.018, band_z0 + band_h - 0.01), (rb + 0.01, band_z0 + band_h + 0.002),
                              (rb - 0.012, band_z0 + band_h)], 96)
    deform(band, lambda co: Vector((co.x * (1 + 0.012 * math.sin(7 * math.atan2(co.y, co.x))),
                                    co.y * 0.62 * (1 + 0.012 * math.sin(7 * math.atan2(co.y, co.x))), co.z)))
    subdivide(band, 1)
    smooth(band)
    assign(band, sh.mat)
    parts.append(band)
    rotate_all(parts, (0, 0, math.radians(-8)))
    return rotate_all(parts, (math.radians(4), 0, 0))


# MARK: - Оливковое масло

def olive_mat(name, dark=False):
    if dark:
        stops = [(0.0, (0.16, 0.06, 0.12)), (1.0, (0.40, 0.18, 0.30))]
    else:
        stops = [(0.0, (0.40, 0.50, 0.06)), (0.6, (0.58, 0.68, 0.14)), (1.0, (0.74, 0.80, 0.30))]
    sh = Sh(name, rough=0.18, sss=0.3, sss_radius=(0.6, 1.0, 0.2), coat=0.85, coat_rough=0.05)
    _, _, nz = sh.xyz("Normal")
    col = sh.ramp(sh.remap(nz, -1, 1, smooth=False), stops)
    dots = sh.remap(sh.voronoi(None, 24, "F1"), 0.06, 0.03)
    col = sh.mix(sh.math("MULTIPLY", dots, 0.35), col, (0.86, 0.88, 0.62) if not dark else (0.55, 0.40, 0.48))
    sh.color(col)
    return sh.mat


def olive_branch(name, origin, yaw=0.0):
    twig_mat = material(name + "Twig", [(0.0, (0.46, 0.36, 0.22)), (1.0, (0.58, 0.50, 0.32))], coord="x", lo=-0.5,
                        hi=0.5, rough=0.5, coat=0.2)
    pts = EV.spline([(-0.45, 0.0, 0.0), (-0.15, 0.03, 0.02), (0.15, 0.0, 0.03), (0.42, -0.04, 0.02)], 8)
    twig = EV.sweep(name + "TwigMesh", pts, lambda t: 0.022 * (1 - 0.5 * t), segs=10, step=0.01)
    assign(twig, twig_mat)
    parts = [twig]
    leaf_stops = [(0.0, (0.40, 0.54, 0.26)), (0.6, (0.50, 0.62, 0.32)), (1.0, (0.62, 0.72, 0.44))]
    for i, (x, a, ln) in enumerate(((-0.30, 60, 0.42), (-0.05, -55, 0.46), (0.18, 50, 0.40), (0.38, -20, 0.36))):
        lf = EV.leaf(f"{name}Leaf{i}", ln, 0.11, fold=0.12, curl=0.05, thick=0.014, stops=leaf_stops, petiole=0.03)
        rotate_all(lf, (0, math.radians(-12), math.radians(a)))
        for o in lf:
            o.location += Vector((x, 0.0, 0.03))
        parts += lf
    for i, (x, y, dark) in enumerate(((-0.12, -0.13, False), (0.10, -0.12, True), (0.26, 0.10, False))):
        o = sphere(f"{name}Olive{i}", 1.0, 32, 20)
        o.scale = (0.10, 0.075, 0.075)
        o.rotation_euler = (0, 0, math.radians(20 + 40 * i))
        o.location = (x, y, 0.075)
        apply_transform(o)
        assign(smooth(o), olive_mat(f"{name}OliveMat{i}", dark))
        parts.append(o)
    rotate_all(parts, (0, 0, yaw))
    for o in parts:
        o.location += Vector(origin)
    return parts


def olive_oil():
    """Бутылка масла: стекло с золотисто-зеленым маслом внутри, пробка с бечевкой, этикетка, веточка с оливками."""
    prof = [(0.0, 0.0), (0.36, 0.0), (0.40, 0.03), (0.42, 0.10), (0.42, 0.88), (0.40, 0.98), (0.32, 1.12),
            (0.20, 1.26), (0.135, 1.36), (0.125, 1.46), (0.125, 1.64), (0.145, 1.66), (0.145, 1.71), (0.0, 1.71)]
    glass = lathe("OilGlass", prof, 96)
    subdivide(glass, 1)
    smooth(glass)
    assign(glass, EV.glass_mat("OilGlassMat", tint=(0.96, 0.99, 0.92), center=0.08, edge=0.75))
    inner = [(0.0, 0.03), (0.38, 0.03), (0.395, 0.10), (0.395, 0.88), (0.375, 0.98), (0.29, 1.10), (0.0, 1.10)]
    oil = lathe("Oil", inner, 96)
    subdivide(oil, 1)
    smooth(oil)
    sh = Sh("OilMat", rough=0.12, sss=0.7, sss_radius=(1.0, 0.9, 0.2), sss_scale=0.2, coat=0.8, coat_rough=0.04)
    x, _, z = sh.xyz()
    col = sh.ramp(sh.remap(z, 0.0, 1.1, smooth=False), [(0.0, (0.52, 0.56, 0.06)), (0.55, (0.76, 0.76, 0.12)),
                                                        (1.0, (0.96, 0.86, 0.30))])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(x, 0.12, 0.30), sh.remap(x, 0.36, 0.30)), col, (1.0, 0.95, 0.55))
    sh.color(col)
    sh.set("Emission Color", _col((0.85, 0.80, 0.20)))
    sh.set("Emission Strength", 0.12)
    assign(oil, sh.mat)
    parts = [glass, oil]
    cork = lathe_fn("OilCork", lambda t: 0.118 * (1 + 0.04 * t) * (1 - ss(0.85, 1.0, t) * 0.25), 1.60, 1.88, 24, 48)
    smooth(cork)
    cm = Sh("CorkMat", rough=0.75, sheen=0.3)
    cm.color(cm.mix(cm.remap(cm.voronoi(None, 30, "F1"), 0.12, 0.04, 0.0, 0.8),
                    cm.ramp(cm.noise(None, 8, 4), [(0.3, (0.86, 0.66, 0.42)), (0.7, (0.74, 0.54, 0.32))]),
                    (0.50, 0.34, 0.18)))
    cm.bump(cm.voronoi(None, 30, "F1"), 0.4, 0.01)
    assign(cork, cm.mat)
    parts.append(cork)
    tw = twine_mat("OilTwine")
    wrap = EV.sweep("OilWrap", wrap_ring("OilWrap", (0, 0, 1.5), 0.145, (0, 0, 1), 0.02, 3.0, 160, rise=0.1),
                    0.02, segs=10, step=0.008)
    assign(wrap, tw)
    parts.append(wrap)
    # этикетка спереди: часть цилиндра с аркой сверху
    lr = 0.428
    th0 = math.radians(64)

    def lfn(u, v):
        th = (2 * u - 1) * th0
        z = 0.30 + v * (0.40 + 0.07 * math.cos(th / th0 * math.pi / 2) ** 2)
        return Vector((lr * math.sin(th), -lr * math.cos(th), z))
    lab = surface("OilLabel", 48, 20, lfn)
    solidify(lab, 0.006, 1.0)
    smooth(lab)
    lm = Sh("OilLabelMat", rough=0.4, coat=0.35, coat_rough=0.15)
    lu, lv, _ = lm.xyz("UV")
    du = lm.math("MINIMUM", lu, lm.math("SUBTRACT", 1.0, lu))
    dv = lm.math("MINIMUM", lv, lm.math("SUBTRACT", 1.0, lv))
    border = lm.math("MAXIMUM", lm.remap(du, 0.05, 0.035), lm.remap(dv, 0.08, 0.055))
    inner_b = lm.math("MAXIMUM", lm.remap(du, 0.075, 0.065), lm.remap(dv, 0.12, 0.105))
    col = lm.mix(border, (0.99, 0.95, 0.84), (0.20, 0.42, 0.16))
    col = lm.mix(lm.math("MULTIPLY", lm.math("SUBTRACT", inner_b, border), 0.9), col, (0.80, 0.64, 0.24))
    lm.color(col)
    assign(lab, lm.mat)
    parts.append(lab)
    # оливки и листики на этикетке
    em = olive_mat("LabelOliveMat")
    for i, (x, z, s_) in enumerate(((-0.07, 0.50, 1.0), (0.06, 0.47, 0.9))):
        o = sphere(f"LabelOlive{i}", 1.0, 24, 16)
        o.scale = (0.055 * s_, 0.025, 0.07 * s_)
        o.rotation_euler = (0, math.radians(25 if i else -20), 0)
        y = -math.sqrt(max(0.0, lr * lr - x * x)) - 0.012
        o.location = (x, y, z)
        apply_transform(o)
        assign(smooth(o), em)
        parts.append(o)
    lf_mat = flat("LabelLeafMat", (0.36, 0.56, 0.22), rough=0.3, coat=0.5)
    for i, (x, z, a) in enumerate(((-0.02, 0.60, 35), (0.06, 0.61, -40), (-0.11, 0.59, 60))):
        l_ = sphere(f"LabelLeaf{i}", 1.0, 20, 10)
        l_.scale = (0.022, 0.012, 0.06)
        l_.rotation_euler = (0, math.radians(a), 0)
        y = -math.sqrt(max(0.0, lr * lr - x * x)) - 0.01
        l_.location = (x, y, z)
        apply_transform(l_)
        assign(smooth(l_), lf_mat)
        parts.append(l_)
    parts += olive_branch("OilBranch", (0.48, -0.40, 0.0), math.radians(-25))
    return rotate_all(parts, (0, 0, math.radians(-10)))


# MARK: - Красный лук

def onion_skin(name):
    sh = Sh(name, rough=0.32, sss=0.25, sss_radius=(1.0, 0.4, 0.6), sss_scale=0.05, coat=0.5, coat_rough=0.15,
            sheen=0.5, sheen_rough=0.35)
    x, y, z = sh.xyz()
    col = sh.ramp(sh.remap(z, -0.55, 0.9, smooth=False),
                  [(0.0, (0.40, 0.07, 0.20)), (0.3, (0.56, 0.11, 0.29)), (0.65, (0.70, 0.18, 0.38)),
                   (0.88, (0.80, 0.42, 0.50)), (1.0, (0.86, 0.62, 0.56))])
    ang = sh.math("ARCTAN2", y, x)
    warp = sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 2.5, 3), 0.5), 0.6)
    s1 = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", ang, 9.0), warp), 0.5)
    lines = sh.remap(s1, 0.09, 0.02)
    col = sh.mix(sh.math("MULTIPLY", lines, 0.55), col, (0.92, 0.62, 0.74))
    s2 = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", ang, 23.0), sh.math("MULTIPLY", warp, 1.7)), 0.5)
    col = sh.mix(sh.math("MULTIPLY", sh.remap(s2, 0.08, 0.02), 0.35), col, (0.34, 0.05, 0.16))
    dry = sh.math("MULTIPLY", sh.remap(sh.noise(None, 3.0, 4), 0.56, 0.68),
                  sh.math("MAXIMUM", sh.remap(z, 0.35, 0.7), sh.remap(z, -0.25, -0.45)))
    col = sh.mix(sh.math("MULTIPLY", dry, 0.8), col, (0.84, 0.58, 0.50))
    sh.color(col)
    sh.set("Roughness", sh.remap(dry, 0.0, 1.0, 0.3, 0.6, smooth=False))
    sh.bump(lines, 0.08, 0.004)
    sh.bump(sh.noise(None, 18, 3), 0.06, 0.004)
    return sh.mat


def onion_face_crisp(name, n=6):
    """Срез красной луковицы: белая мякоть, четкие фиолетовые каемки слоев, к середине слои теснее."""
    ob = polar_disc(name, 150, 200, 1.0, 1.0)
    white = (1.0, 0.97, 0.98)
    pink = (0.96, 0.80, 0.88)
    purple = (0.56, 0.08, 0.32)

    def ring(t):
        return (t ** 0.85 * n + 0.25) % 1.0

    def col(co, nrm):
        t = math.hypot(co.x, co.y)
        if t > 0.965:
            return purple
        f = ring(t)
        base = MX.mix(white, (0.98, 0.90, 0.94), t)
        if f > 0.80:
            return MX.mix(purple, (0.70, 0.18, 0.44), ss(0.95, 1.0, f))
        return MX.mix(base, pink, ss(0.55, 0.80, f))
    MX.vcol(ob, col)

    def fn(co):
        t = math.hypot(co.x, co.y)
        phi = math.atan2(co.x, co.y)
        r = MX.onion_r(abs(phi)) * 0.995 * t
        f = ring(t)
        return Vector((r * math.sin(phi), -0.005 * math.sin(math.pi * f), r * math.cos(phi) * 0.92))
    deform(ob, fn)
    smooth(ob)
    assign(ob, MX.vmat(f"{name}Mat", rough=0.12, sss=0.4, sss_radius=(1, 0.8, 0.9), coat=0.75, coat_rough=0.05))
    return ob


def onion():
    """Красная луковица с бумажистой шелухой, сухим хвостиком и корешками, рядом половинка со слоями."""
    skin = onion_skin("RedOnionSkin")
    whole = MX.onion_bulb("RedOnion")
    push_normals(whole, lambda co, n: 0.012 * fbm(co * 2.2, 3))
    smooth(whole)
    assign(whole, skin)
    top_z = 0.62 * 1.55 * 0.92
    paper = Sh("OnionNeckMat", rough=0.5, sss=0.3, sheen=0.5, coat=0.2)
    pu, pv, _ = paper.xyz("UV")
    pc = paper.ramp(pu, [(0.0, (0.74, 0.30, 0.40)), (0.5, (0.84, 0.58, 0.50)), (1.0, (0.88, 0.70, 0.56))])
    pc = paper.mix(paper.remap(paper.math("PINGPONG", paper.math("MULTIPLY", pv, 6.0), 0.5), 0.1, 0.0, 0.0, 0.4), pc,
                   (0.62, 0.30, 0.30))
    paper.color(pc)
    neck = []
    for i, (bx, by, h, tw_) in enumerate(((0.10, 0.02, 0.30, 0.0), (0.04, -0.06, 0.24, 1.2), (-0.06, 0.04, 0.2, 2.4))):
        pts = [(0.03 * math.cos(tw_ + 3 * t) * (1 - t) + bx * t * t, 0.03 * math.sin(tw_ + 3 * t) * (1 - t) + by * t * t,
                top_z - 0.07 + h * t) for t in [k / 10 for k in range(11)]]
        st = EV.sweep(f"OnionNeck{i}", pts, lambda t: 0.04 * (1 - 0.75 * t), segs=12, step=0.01, section=(1.0, 0.45))
        assign(st, paper.mat)
        neck.append(st)
    root_mat = material("OnionRootMat", [(0.0, (0.80, 0.68, 0.50)), (1.0, (0.94, 0.88, 0.74))], coord="z", lo=-0.75,
                        hi=-0.5, rough=0.6, sheen=0.3)
    plate = sphere("OnionPlate", 0.13, 24, 12)
    plate.scale = (1, 1, 0.3)
    plate.location = (0, 0, -0.51)
    apply_transform(plate)
    assign(smooth(plate), root_mat)
    roots = [plate]
    rnd = random.Random(2)
    for i in range(12):
        a = 2 * math.pi * i / 12 + rnd.uniform(-0.2, 0.2)
        ln = rnd.uniform(0.08, 0.16)
        pts = [(math.cos(a) * (0.06 + ln * t), math.sin(a) * (0.06 + ln * t) + 0.02 * math.sin(6 * t + i),
                -0.52 - 0.06 * t + 0.04 * t * t) for t in [k / 6 for k in range(7)]]
        rt = EV.sweep(f"OnionRoot{i}", pts, lambda t: 0.012 * (1 - 0.5 * t), segs=8, step=0.01)
        assign(rt, root_mat)
        roots.append(rt)
    wp = [whole] + neck + roots
    MX.ground(wp)
    for o in wp:
        o.location += Vector((-0.30, 0.35, 0))
    half = MX.onion_bulb("RedOnionHalf")
    bisect(half, (0, 0, 0), (0, 1, 0), fill=False)
    smooth(half)
    assign(half, skin)
    face = onion_face_crisp("RedOnionFace")
    face.location = (0, 0.0, 0)
    apply_transform(face)
    hp = [half, face]
    rotate_all(hp, (math.radians(180), 0, 0))
    rotate_all(hp, (math.radians(-90 + 40), 0, 0))
    for o in hp:
        o.location += Vector((0.44, -0.44, 0))
    MX.ground(hp)
    return wp + hp


M.MODELS.update({
    "patty": patty,
    "beef": beef,
    "sausage": sausage,
    "hotdog_bun": hotdog_bun,
    "lettuce": lettuce,
    "basil": basil,
    "mozzarella": mozzarella,
    "leek": leek,
    "dough": dough,
    "flour": flour,
    "pasta": pasta,
    "grissini": grissini,
    "olive_oil": olive_oil,
    "onion": onion,
})


# ======================================================================================================
# Партия 2: японская кухня, Мексика, пекарня, итальянские сладости и кофе.
# ======================================================================================================

import bmesh as _bm  # noqa: E402
import models_bakery as BK  # noqa: E402


def weld(ob, dist=1e-5):
    """Сшивает совпавшие вершины (шов замкнутой по v сетки)."""
    bm = _bm.new()
    bm.from_mesh(ob.data)
    _bm.ops.remove_doubles(bm, verts=bm.verts, dist=dist)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    return ob


def join_one(objs, name, mat):
    """Сливает много мелких деталей одного материала в один меш."""
    bpy.context.view_layer.update()
    bm = _bm.new()
    for o in objs:
        me = o.data.copy()
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for o in objs:
        bpy.data.objects.remove(o, do_unlink=True)
    ob = link(bpy.data.objects.new(name, me))
    smooth(ob)
    return assign(ob, mat)


def ceramic_sh(name, stops, z0, z1, rough=0.14):
    sh = Sh(name, rough=rough, coat=0.8, coat_rough=0.05)
    _, _, z = sh.xyz()
    sh.color(sh.ramp(sh.remap(z, z0, z1, smooth=False), stops))
    return sh


def angle_sock(sh):
    x, y, _ = sh.xyz()
    return sh.math("ARCTAN2", y, x)


# MARK: - Рис

def rice():
    """Пиала риса: горка из отдельных блестящих зерен, синяя глазурь снаружи, палочки поперек."""
    prof = [(0.0, 0.0), (0.30, 0.0), (0.33, 0.015), (0.335, 0.07), (0.31, 0.10), (0.36, 0.12), (0.55, 0.24),
            (0.70, 0.42), (0.78, 0.60), (0.80, 0.69), (0.787, 0.715), (0.765, 0.70), (0.745, 0.61), (0.665, 0.44),
            (0.50, 0.28), (0.30, 0.20), (0.0, 0.19)]
    bowl = lathe("RiceBowl", prof, 128)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = Sh("RiceBowlOut", rough=0.12, coat=0.85, coat_rough=0.04)
    _, _, z = out.xyz()
    col = out.ramp(out.remap(z, 0.0, 0.72, smooth=False), [(0.0, (0.12, 0.20, 0.52)), (0.6, (0.18, 0.30, 0.68)),
                                                          (1.0, (0.26, 0.40, 0.80))])
    ang = angle_sock(out)
    wave = out.math("SINE", out.math("ADD", out.math("MULTIPLY", ang, 12.0), out.math("MULTIPLY", z, 18.0)))
    band = out.math("MULTIPLY", out.remap(z, 0.34, 0.38), out.remap(z, 0.50, 0.46))
    dots = out.math("MULTIPLY", out.remap(wave, 0.75, 0.9), band)
    col = out.mix(dots, col, (0.96, 0.97, 1.0))
    col = out.mix(out.math("MULTIPLY", out.remap(z, 0.64, 0.67), 1.0), col, (0.97, 0.97, 1.0))
    col = out.mix(out.remap(z, 0.11, 0.08), col, (0.95, 0.93, 0.88))
    out.color(col)
    inn = ceramic_sh("RiceBowlIn", [(0.0, (0.92, 0.93, 0.96)), (1.0, (1.0, 1.0, 1.0))], 0.2, 0.72)
    BK.inner_faces(bowl, out.mat, inn.mat, 0.15)
    parts = [bowl]
    rice_sh = Sh("RiceBase", rough=0.35, sss=0.6, sss_radius=(1.0, 1.0, 1.0), sss_scale=0.03, coat=0.4)
    rice_sh.color((0.97, 0.97, 0.95))
    rice_sh.bump(rice_sh.voronoi(None, 40, "F1"), 0.5, 0.01, invert=True)
    mound = polar_disc("RiceMound", 30, 128, 0.765, 0.765)

    def mshape(co):
        rr = min(1.0, math.hypot(co.x, co.y) / 0.765)
        return Vector((co.x, co.y, 0.60 + 0.30 * max(0.0, 1 - rr * rr) ** 0.8 + 0.015 * fbm(co * 5)))
    deform(mound, mshape)
    smooth(mound)
    assign(mound, rice_sh.mat)
    parts.append(mound)
    gsh = Sh("RiceGrain", rough=0.2, sss=0.5, sss_radius=(1.0, 1.0, 0.95), sss_scale=0.02, coat=0.7, coat_rough=0.05)
    gsh.set("Emission Color", _col((1.0, 1.0, 0.98)))
    gsh.set("Emission Strength", 0.06)
    _, _, gz = gsh.xyz()
    gsh.color(gsh.ramp(gsh.remap(gz, -0.03, 0.03, smooth=False), [(0.0, (0.93, 0.93, 0.93)), (1.0, (1.0, 1.0, 0.99))]))
    grains = []

    def make(i, rnd):
        g = sphere(f"Grain{len(grains)}", 1.0, 14, 8)
        s = rnd.uniform(0.9, 1.1)
        g.scale = (0.078 * s, 0.036 * s, 0.03 * s)
        g.rotation_euler = (rnd.uniform(-0.35, 0.35), rnd.uniform(-0.3, 0.3), 0)
        apply_transform(g)
        deform(g, lambda co: Vector((co.x, co.y, co.z + 0.06 * co.x * co.x / 0.078)))
        g.location.z += 0.012
        assign(g, gsh.mat)
        grains.append(g)
        return g
    scatter_on(mound, 300, make, seed=3, area=0.74, spacing=0.055, zmin=0.6)
    scatter_on(mound, 160, make, seed=8, area=0.72, spacing=0.0, zmin=0.6)
    parts.append(join_one(grains, "RiceGrains", gsh.mat))
    # палочки: лакированные, сужаются к кончику
    lac = Sh("ChopLacquer", rough=0.18, coat=0.9, coat_rough=0.04)
    lx, _, _ = lac.xyz()
    lac.color(lac.mix(lac.remap(lx, 0.55, 0.60), (0.80, 0.12, 0.10), (0.16, 0.08, 0.06)))
    for i, dy in enumerate((-0.06, 0.06)):
        st = lathe_fn(f"Chop{i}", lambda t: 0.034 * (1 - 0.55 * t) * (1 - ss(0.985, 1.0, t) * 0.5)
                      * (1 - ss(0.015, 0.0, t) * 0.4), -0.95, 0.95, 60, 20)
        to_axis_x(st)
        deform(st, lambda co: Vector((-co.x, co.y, co.z)))
        smooth(st)
        assign(st, lac.mat)
        st.rotation_euler = (0, math.radians(-3 + 2 * i), math.radians(-24 + 7 * i))
        st.location = (0.02, 0.26 + dy, 0.93 + 0.035)
        parts.append(st)
    return rotate_all(parts, (0, 0, math.radians(-6)))


# MARK: - Лосось

def salmon_sh(name, phase=0.0):
    sh = Sh(name, rough=0.26, sss=0.55, sss_radius=(1.0, 0.4, 0.2), sss_scale=0.06, coat=0.7, coat_rough=0.07)
    x, y, z = sh.xyz()
    flesh = sh.ramp(sh.noise(None, 3, 3), [(0.3, (1.0, 0.42, 0.18)), (0.7, (1.0, 0.52, 0.26))])
    s = sh.math("ADD", sh.math("MULTIPLY", x, 1.0), sh.math("MULTIPLY", sh.math("ABSOLUTE", sh.math("SUBTRACT", y, 0.05)),
                                                            0.85))
    s = sh.math("ADD", s, sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 2.5, 2), 0.5), 0.08))
    d = sh.math("PINGPONG", sh.math("ADD", sh.math("MULTIPLY", s, 6.5), phase), 0.5)
    lines = sh.remap(d, 0.10, 0.04)
    col = sh.mix(sh.math("MULTIPLY", lines, 0.92), flesh, (1.0, 0.90, 0.82))
    sh.color(col)
    sh.bump(lines, 0.08, 0.006)
    sh.bump(sh.noise(sh.mapping(None, scale=(1, 6, 1)), 12, 2), 0.04, 0.004)
    return sh


def fish():
    """Кусок филе лосося для суши: оранжевая мякоть с белыми прожилками жира, серебристая кожа; ломтики сашими на шисо."""
    W, D = 1.5, 0.85

    def rr_out(a):
        c, s_ = math.cos(a), math.sin(a)
        return 1.0 / ((abs(c) / (W / 2)) ** 5 + (abs(s_) / (D / 2)) ** 5) ** 0.2
    outline = MX.polar_outline(rr_out, 160)
    ob = MX.outline_slab("Salmon", outline, 1.0, p=3.2, cuts=40)

    def shp(co):
        h = 0.40 + 0.14 * (co.y / (D / 2))
        z = (co.z + 0.5) * h
        return Vector((co.x * (1 + 0.04 * co.z), co.y, z))
    deform(ob, shp)
    subdivide(ob, 1)
    push_normals(ob, lambda co, n: 0.01 * fbm(co * 3))
    smooth(ob)
    flesh = salmon_sh("SalmonFlesh")
    skin = Sh("SalmonSkin", rough=0.2, coat=0.8, coat_rough=0.05, metal=0.3)
    _, sy, _ = skin.xyz()
    skin.color(skin.ramp(skin.noise(None, 20, 2), [(0.3, (0.30, 0.32, 0.38)), (0.7, (0.62, 0.66, 0.72))]))
    assign_faces(ob, flesh.mat, [(lambda n, c: c.z < 0.045, skin.mat)])
    parts = [ob]
    # лист шисо под филе выглядывает спереди справа и сзади слева
    shiso = EV.leaf("Shiso", 1.25, 0.86, fold=0.04, curl=0.03, thick=0.016, serr=0.6, petiole=0.08,
                    stops=[(0.0, (0.20, 0.54, 0.12)), (0.6, (0.30, 0.66, 0.18)), (1.0, (0.40, 0.74, 0.24))])
    rotate_all(shiso, (0, 0, math.radians(-150)))
    for o in shiso:
        o.location += Vector((0.95, 0.42, -0.012))
    parts += shiso
    ob.location.z += 0.03
    return rotate_all(parts, (math.radians(8), 0, math.radians(-14)))


# MARK: - Соевый соус

def soy():
    """Бутылочка соевого соуса: прозрачное стекло, темный соус с красноватым просветом, красная крышка с носиками."""
    prof = [(0.0, 0.0), (0.37, 0.0), (0.41, 0.03), (0.43, 0.12), (0.43, 0.30), (0.40, 0.52), (0.33, 0.74),
            (0.24, 0.90), (0.17, 1.02), (0.15, 1.12), (0.15, 1.20), (0.0, 1.20)]
    glass = lathe("SoyGlass", prof, 96)
    subdivide(glass, 1)
    smooth(glass)
    assign(glass, EV.glass_mat("SoyGlassMat", tint=(0.98, 0.97, 0.95), center=0.06, edge=0.8))
    inner = [(0.0, 0.035), (0.385, 0.035), (0.405, 0.12), (0.405, 0.30), (0.375, 0.52), (0.31, 0.72), (0.27, 0.80),
             (0.0, 0.80)]
    liq = lathe("SoyLiquid", inner, 96)
    subdivide(liq, 1)
    smooth(liq)
    sh = Sh("SoySauce", rough=0.06, sss=0.5, sss_radius=(1.0, 0.25, 0.08), sss_scale=0.15, coat=0.9, coat_rough=0.03)
    x, _, z = sh.xyz()
    col = sh.ramp(sh.remap(z, 0.0, 0.8, smooth=False), [(0.0, (0.12, 0.04, 0.02)), (1.0, (0.22, 0.08, 0.03))])
    lw = sh.nodes.new("ShaderNodeLayerWeight")
    lw.inputs["Blend"].default_value = 0.35
    col = sh.mix(sh.remap(lw.outputs["Facing"], 0.45, 0.95, 0.0, 0.85), col, (0.62, 0.18, 0.05))
    sh.color(col)
    assign(liq, sh.mat)
    red = Sh("SoyCapRed", rough=0.2, coat=0.75, coat_rough=0.06, sss=0.1)
    _, _, cz = red.xyz()
    red.color(red.ramp(red.remap(cz, 1.0, 1.45, smooth=False), [(0.0, (0.72, 0.05, 0.05)), (1.0, (0.96, 0.16, 0.12))]))
    cap = lathe("SoyCap", [(0.0, 1.04), (0.19, 1.04), (0.205, 1.06), (0.205, 1.14), (0.19, 1.17), (0.16, 1.24),
                           (0.12, 1.30), (0.07, 1.33), (0.0, 1.335)], 64)
    subdivide(cap, 1)
    smooth(cap)
    assign(cap, red.mat)
    # рифление по краю крышки
    ribs = lathe("SoyCapRibs", [(0.206, 1.065), (0.212, 1.07), (0.212, 1.135), (0.206, 1.14)], 64)
    deform(ribs, lambda co: Vector((co.x * (1 + 0.025 * math.cos(32 * math.atan2(co.y, co.x))),
                                    co.y * (1 + 0.025 * math.cos(32 * math.atan2(co.y, co.x))), co.z)))
    smooth(ribs)
    assign(ribs, red.mat)
    parts = [glass, liq, cap, ribs]
    for i, (sx, h, r) in enumerate(((1, 0.12, 0.035), (-1, 0.07, 0.025))):
        sp = lathe_fn(f"SoySpout{i}", lambda t, r=r: r * (1 - 0.35 * t), 0.0, h, 12, 24)
        sp.rotation_euler = (0, math.radians(sx * 32), 0)
        sp.location = (sx * 0.05, 0.0, 1.29)
        apply_transform(sp)
        smooth(sp)
        assign(sp, red.mat)
        parts.append(sp)
    return rotate_all(parts, (0, 0, math.radians(-90 + 20)))


# MARK: - Эдамаме

def edamame_pod(name, L, W, T, mat, beans=3, seed=0.0, curve=2.6, nu=110, nv=48):
    cs = [(k + 0.5) / beans for k in range(beans)]

    def bump(u):
        return max(math.exp(-((u - c) / (0.42 / beans)) ** 2) for c in cs)

    def fn(u, v):
        e = math.sin(math.pi * min(1.0, max(0.0, u))) ** 0.5
        e *= 1 - 0.25 * ss(0.8, 1.0, u)
        b = bump(u)
        phi = 2 * math.pi * v
        c, s_ = math.cos(phi), math.sin(phi)
        w = W / 2 * e * (0.66 + 0.34 * b)
        t = T / 2 * e * (0.30 + 0.70 * b)
        seam = 1 + 0.07 * math.exp(-(s_ / 0.2) ** 2)
        y = w * c * seam
        z = t * s_ * (1 - 0.2 * math.exp(-(s_ / 0.25) ** 2))
        z += 0.01 * noise.noise(Vector((u * 6, c, seed)))
        return Vector((u * L, y, z + T / 2))
    ob = surface(name, nu, nv, fn)
    weld(ob)
    smooth(ob)
    bend(ob, curve)
    assign(ob, mat)
    return ob


def edamame():
    """Горстка стручков эдамаме: яркие, бархатистые, с бугорками бобов и хлопьями соли."""
    sh = Sh("EdamamePod", rough=0.45, sss=0.35, sss_radius=(0.5, 1.0, 0.3), sss_scale=0.05, sheen=0.9,
            sheen_rough=0.3, coat=0.25, coat_rough=0.2)
    _, _, nz = sh.xyz("Normal")
    col = sh.ramp(sh.remap(nz, -1, 1, smooth=False), [(0.0, (0.14, 0.38, 0.05)), (0.5, (0.26, 0.58, 0.08)),
                                                      (1.0, (0.44, 0.76, 0.16))])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.voronoi(None, 30, "F1"), 0.06, 0.02), 0.5), col, (0.30, 0.54, 0.12))
    sh.color(col)
    sh.bump(sh.noise(None, 60, 3), 0.15, 0.003)
    pod_mat = sh.mat
    salt_mat = material("EdaSalt", [(0.0, (0.95, 0.96, 0.98)), (1.0, (1.0, 1.0, 1.0))], rough=0.15, coat=0.6, sss=0.3)
    stem_mat = material("EdaStem", [(0.0, (0.46, 0.62, 0.20)), (1.0, (0.62, 0.74, 0.30))], rough=0.5, sheen=0.5)
    parts, pods = [], []
    specs = [(-0.15, 0.32, 10, 1.05, 3, 0.0), (0.22, 0.02, -25, 1.0, 3, 1.0), (-0.32, -0.16, 30, 0.92, 2, 2.0),
             (0.10, -0.36, -6, 1.02, 3, 4.0), (0.02, 0.06, 78, 0.98, 3, 3.0)]
    for i, (x, y, rz, L, nb, sd) in enumerate(specs):
        p = edamame_pod(f"Pod{i}", L, 0.32, 0.23, pod_mat, nb, sd, 2.0 + 0.4 * i)
        st = lathe_fn(f"PodStem{i}", lambda t: 0.035 * (1 - 0.3 * t), 0.0, 0.09, 8, 16)
        st.rotation_euler = (0, math.radians(-90), 0)
        st.location = (0.01, 0, 0.115)
        apply_transform(st)
        smooth(st)
        assign(st, stem_mat)
        grp = [p, st]
        for o in grp:
            o.location.x -= 0.5 * L
        rotate_all(grp, (0, 0, math.radians(rz)))
        for o in grp:
            o.location += Vector((x, y, 0))
        bpy.context.view_layer.update()
        MX.drop(grp, pods, floor=0.0, step=0.01, top=1.4)
        pods.append(p)
        parts += grp
    salts = []

    def make(i, rnd):
        c = MX.rcube(f"Salt{i}", *(rnd.uniform(0.012, 0.022) for _ in range(3)), p=3.0, cuts=2)
        c.rotation_euler = (rnd.uniform(0, 3), rnd.uniform(0, 3), 0)
        assign(c, salt_mat)
        salts.append(c)
        return c
    for k, p in enumerate(pods):
        scatter_on(p, 12, make, seed=k + 4, area=1.0, spacing=0.06)
    parts.append(join_one(salts, "EdaSalts", salt_mat))
    bean_mat = material("EdaBean", [(0.0, (0.56, 0.82, 0.30)), (1.0, (0.76, 0.94, 0.48))], coord="z", lo=0.0, hi=0.12,
                        rough=0.25, sss=0.4, sss_radius=(0.6, 1.0, 0.3), coat=0.6)
    for i, (x, y) in enumerate(((0.66, -0.52), (0.48, -0.66))):
        b = sphere(f"EdaBean{i}", 1.0, 32, 20)
        b.scale = (0.11, 0.085, 0.07)
        b.rotation_euler = (0, 0, math.radians(30 + 50 * i))
        b.location = (x, y, 0.07)
        apply_transform(b)
        assign(smooth(b), bean_mat)
        parts.append(b)
    return rotate_all(parts, (math.radians(12), 0, math.radians(-8)))


# MARK: - Гёдза

def gyoza_obj(name, L, B, H, mat, pleats=6, seed=0.0, curve=1.3, nu=150, nv=96):
    """Полумесяц: пухлое тело с плоским дном, сверху тонкий гребень-защип с волнами, на передней стороне складки."""
    qf = 0.16

    def fn(u, v):
        e = math.sin(math.pi * u) ** 0.5
        h = H * e ** 0.6
        zf = 0.66 * h
        b = B * e
        q = 2 * v if v <= 0.5 else 2 * (1 - v)
        side = -1.0 if v <= 0.5 else 1.0
        wav = math.sin(2 * math.pi * pleats * u + seed)
        if q < qf:
            k = q / qf
            z = h - (h - zf) * k
            y = (0.014 + 0.03 * k) * e
            shift = 0.045 * e * wav
            z += 0.04 * H * e * (0.5 + 0.5 * wav) * (1 - k)
        else:
            k = (q - qf) / (1 - qf)
            beta = k * math.pi
            if beta <= math.pi / 2:
                z = zf * (0.5 + 0.5 * math.cos(beta))
            else:
                z = zf * 0.5 * (1 - (-math.cos(beta)) ** 0.45)
            y = max(0.044 * e, b * math.sin(beta) ** 0.85 * (1 + 0.12 * k))
            fold = (0.5 + 0.5 * math.sin(2 * math.pi * (pleats * u + 0.8 * k) + seed)) ** 3
            amp = math.exp(-k / 0.45)
            if side < 0:
                y += 0.32 * b * amp * fold
                z += 0.03 * H * amp * fold
            shift = 0.045 * e * wav * math.exp(-k / 0.08)
        return Vector(((u - 0.5) * L, side * y + shift, z))
    ob = surface(name, nu, nv, fn)
    weld(ob, 1e-4)
    push_normals(ob, lambda co, n: 0.003 * fbm(co * 10))
    smooth(ob)
    bend(ob, curve)
    return assign(ob, mat)


def gyoza():
    """Три гёдза: тонкое тесто со складочками по гребню, донышко обжарено до золотисто-коричневой корочки."""
    H = 0.46
    sh = Sh("GyozaMat", rough=0.38, sss=0.55, sss_radius=(1.0, 0.85, 0.6), sss_scale=0.06, coat=0.5, coat_rough=0.1)
    _, _, z = sh.xyz()
    wob = sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 5, 3), 0.5), 0.10)
    zz = sh.math("ADD", z, wob)
    col = sh.ramp(sh.remap(zz, 0.0, H, smooth=False), [(0.0, (0.46, 0.22, 0.06)), (0.06, (0.68, 0.38, 0.11)),
                                                       (0.16, (0.90, 0.60, 0.22)), (0.26, (0.99, 0.82, 0.54)),
                                                       (0.40, (1.0, 0.88, 0.68)), (1.0, (1.0, 0.92, 0.78))])
    spots = sh.math("MULTIPLY", sh.remap(sh.noise(None, 9, 3), 0.6, 0.72, 0.0, 0.6), sh.remap(z, 0.2, 0.1))
    col = sh.mix(spots, col, (0.56, 0.28, 0.08))
    sh.color(col)
    sh.bump(sh.noise(None, 28, 4), 0.07, 0.004)
    sh.rough_vary(0.28, 0.5, 6)
    parts = []
    specs = [(-0.42, 0.30, -8, 0.0, 0), (0.42, 0.34, 10, 0.0, 1), (0.0, -0.36, -2, 0.0, 2)]
    for i, (x, y, rz, tilt, sd) in enumerate(specs):
        g = gyoza_obj(f"Gyoza{i}", 1.2, 0.27, H, sh.mat, 6, sd * 1.7, 1.25 + 0.1 * i)
        g.rotation_euler = (math.radians(tilt), 0, math.radians(rz))
        g.location = (x, y, 0)
        parts.append(g)
    # передняя гёдза завалилась набок: видно поджаристое донышко
    front = parts[2]
    front.rotation_euler = (math.radians(-62), 0, math.radians(-4))
    bpy.context.view_layer.update()
    MX.ground([front], 0.0)
    front.location.y -= 0.12
    return rotate_all(parts, (math.radians(10), 0, math.radians(-6)))


M.MODELS.update({
    "rice": rice,
    "fish": fish,
    "soy": soy,
    "edamame": edamame,
    "gyoza": gyoza,
})


# MARK: - Темпура

def tempura_obj(name, L, R, mat, tail_mat, seed=0.0):
    """Креветка в кляре: изогнутое тело, к хвосту тоньше, рваный хрустящий кляр, красный хвостик веером."""
    pts = EV.spline([(L * 0.5, 0.0, 0.0), (L * 0.18, 0.06, 0.0), (-L * 0.18, 0.05, 0.0), (-L * 0.46, -0.03, 0.0)], 10)

    def rfn(t):
        return R * (1 - 0.5 * t ** 1.4) * (1 - 0.35 * ss(0.92, 1.0, t))
    body = EV.sweep(name, pts, rfn, segs=40, step=0.014)
    subdivide(body, 1)
    off = Vector((seed * 3.1, seed * 1.3, 0))

    def crag(co, n):
        return (0.05 * max(0.0, fbm(co * 4.5 + off, 4)) + 0.03 * abs(noise.noise(co * 10 + off))
                + 0.012 * fbm(co * 22 + off, 2))
    EV.set_attr(body, "crag", lambda co, n: min(1.0, crag(co, n) / 0.07))
    push_normals(body, crag)
    smooth(body)
    assign(body, mat)
    parts = [body]
    bits = []

    def make(i, rnd):
        b = sphere(f"{name}Bit{len(bits)}", 1.0, 12, 8)
        sz = rnd.uniform(0.03, 0.06)
        b.scale = (sz * rnd.uniform(0.8, 1.6), sz, sz * rnd.uniform(0.5, 0.9))
        apply_transform(b)
        push_normals(b, lambda co, n: 0.01 * noise.noise(co * 40))
        bits.append(b)
        return b
    scatter_on(body, 45, make, seed=int(seed * 10) + 1, area=1.2, spacing=0.06)
    for b in bits:
        b.data.update()
    jb = join_one(bits, f"{name}Bits", mat)
    EV.set_attr(jb, "crag", lambda co, n: 0.72)
    parts.append(jb)
    # хвост: кольцо панциря и три лопасти
    end = Vector(pts[-1])
    tdir = (Vector(pts[-1]) - Vector(pts[-3])).normalized()
    ring = sphere(f"{name}TailRing", 1.0, 24, 16)
    ring.scale = (0.08, 0.075, 0.07)
    ring.location = end + tdir * 0.02
    apply_transform(ring)
    assign(smooth(ring), tail_mat)
    parts.append(ring)
    base_ang = math.atan2(tdir.y, tdir.x)
    for k, (da, ln, w) in enumerate(((-0.6, 0.36, 0.12), (0.0, 0.42, 0.11), (0.6, 0.36, 0.12))):
        f = sphere(f"{name}Fan{k}", 1.0, 24, 12)
        f.scale = (ln / 2, w, 0.025)
        apply_transform(f)
        deform(f, lambda co: Vector((co.x, co.y * (0.5 + 0.5 * (co.x / ln + 0.5)), co.z + 0.25 * (co.x / ln) ** 2)))
        f.rotation_euler = (math.radians(10 * (k - 1)), math.radians(-18), base_ang + da)
        f.location = end + tdir * 0.05 + Vector((math.cos(base_ang + da), math.sin(base_ang + da), 0)) * ln * 0.45
        apply_transform(f)
        assign(smooth(f), tail_mat)
        parts.append(f)
    return parts


def tempura():
    """Две креветки темпура: золотистый неровный кляр с крошками, красно-оранжевые хвостики."""
    sh = Sh("TempuraBatter", rough=0.45, sss=0.3, sss_radius=(1.0, 0.8, 0.4), sss_scale=0.04, coat=0.35, coat_rough=0.2)
    crag = sh.attr("crag")
    col = sh.ramp(crag, [(0.0, (0.90, 0.62, 0.24)), (0.35, (0.98, 0.80, 0.42)), (0.7, (1.0, 0.88, 0.56)),
                         (1.0, (1.0, 0.92, 0.64))])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(None, 6, 3), 0.6, 0.72), 0.5), col, (0.82, 0.50, 0.16))
    sh.color(col)
    sh.bump(sh.noise(None, 45, 4), 0.25, 0.004)
    sh.rough_vary(0.35, 0.6, 9)
    tl = Sh("TempuraTail", rough=0.25, sss=0.5, sss_radius=(1.0, 0.4, 0.3), coat=0.7, coat_rough=0.06)
    _, _, tz = tl.xyz()
    tl.color(tl.ramp(tl.noise(None, 6, 2), [(0.3, (0.92, 0.22, 0.10)), (0.7, (1.0, 0.40, 0.20))]))
    a = tempura_obj("TempA", 1.8, 0.25, sh.mat, tl.mat, 0.0)
    b = tempura_obj("TempB", 1.7, 0.24, sh.mat, tl.mat, 1.0)
    for o in a + b:
        o.location.z += 0.25
    rotate_all(a, (0, 0, math.radians(206)))
    rotate_all(b, (0, 0, math.radians(150)))
    for o in a:
        o.location += Vector((0.05, 0.34, 0))
    for o in b:
        o.location += Vector((-0.05, -0.34, 0))
    bpy.context.view_layer.update()
    MX.ground(a, 0.0)
    MX.drop(b, a, floor=0.0, step=0.01, top=1.5)
    return rotate_all(a + b, (math.radians(10), 0, math.radians(-14)))


# MARK: - Моти

def mochi_obj(name, R, lo, hi, seed=0.0):
    ob = sphere(name, 1.0, 80, 56)
    off = Vector((seed, seed * 0.7, 0))

    def shp(co):
        a = math.atan2(co.y, co.x)
        k = 1.0 + 0.04 * fbm(co * 1.3 + off) + 0.015 * math.sin(3 * a + seed)
        z = co.z * 0.74 if co.z > 0 else co.z * 0.30
        sag = 1.0 + 0.12 * ss(0.25, -0.6, co.z)
        return Vector((co.x * R * k * sag, co.y * R * k * sag, (z + 0.30) * R))
    deform(ob, shp)
    push_normals(ob, lambda co, n: 0.006 * fbm(co * 6 / R + off) - 0.008 * ss(0.3, 0.0, n.z) * (0.5 + 0.5 * math.sin(
        14 * math.atan2(co.y, co.x) + seed)) * (1 - ss(-0.6, -0.3, n.z)))
    smooth(ob)
    sh = Sh(name + "Mat", rough=0.55, sss=0.75, sss_radius=(1.0, 0.9, 0.85), sss_scale=0.15, sheen=0.7,
            sheen_rough=0.4, coat=0.1, coat_rough=0.3)
    _, _, z = sh.xyz()
    _, _, nz = sh.xyz("Normal")
    col = sh.ramp(sh.remap(z, 0.0, 1.04 * R, smooth=False), [(0.0, lo), (1.0, hi)])
    dust = sh.math("MULTIPLY", sh.remap(sh.noise(None, 2.5 / R, 5, 0.65), 0.50, 0.68, 0.0, 0.7), sh.remap(nz, 0.35, 0.85))
    specks = sh.remap(sh.voronoi(None, 50 / R, "F1"), 0.12, 0.05, 0.0, 0.9)
    flour = sh.math("MAXIMUM", dust, sh.math("MULTIPLY", specks, sh.remap(nz, -0.3, 0.3)))
    col = sh.mix(flour, col, (1.0, 1.0, 0.99))
    sh.color(col)
    sh.set("Roughness", sh.remap(flour, 0.0, 1.0, 0.45, 0.9, smooth=False))
    sh.bump(flour, 0.12, 0.005)
    sh.bump(sh.noise(None, 40, 3), 0.05, 0.003)
    return assign(ob, sh.mat)


def mochi():
    """Три дайфуку пастельных цветов: мягкие, чуть осевшие, присыпаны крахмалом; верхний лежит на двух нижних."""
    a = mochi_obj("MochiPink", 0.55, (0.98, 0.64, 0.74), (1.0, 0.80, 0.86), 0.0)
    b = mochi_obj("MochiGreen", 0.55, (0.62, 0.80, 0.42), (0.80, 0.92, 0.62), 1.3)
    c = mochi_obj("MochiWhite", 0.52, (0.94, 0.92, 0.90), (1.0, 1.0, 0.98), 2.6)
    a.location = (-0.36, -0.10, 0)
    b.location = (0.38, -0.06, 0)
    c.location = (0.0, 0.22, 0)
    bpy.context.view_layer.update()
    MX.drop([c], [a, b], floor=0.0, step=0.01, top=1.5)
    c.location.z -= 0.06
    return rotate_all([a, b, c], (math.radians(6), 0, math.radians(-8)))


# MARK: - Тайяки

def taiyaki_outline(n=80):
    pts = []
    for k in range(n + 1):
        x = 0.92 - 1.50 * k / n
        e = max(0.0, 1 - ((x - 0.12) / 0.82) ** 2)
        y = 0.47 * e ** 0.5 + 0.09 * math.exp(-((x + 0.08) / 0.22) ** 2)
        pts.append((x, max(y, 0.17)))
    pts += [(-0.70, 0.24), (-0.84, 0.36), (-0.98, 0.44), (-1.04, 0.40), (-1.0, 0.24), (-0.95, 0.10), (-0.93, 0.0)]
    bot = [(x, -y) for x, y in reversed(pts)][1:]
    out = pts + bot
    return out[:-1]


def taiyaki_relief(x, y):
    """Рисунок формы: чешуя, жабра, глаз, лучи хвоста и плавника. 0..1."""
    r = 0.0
    if -0.5 < x < 0.42:
        u = (x + 0.5) / 0.15
        col_i = math.floor(u)
        v = y / 0.15 + 0.5 * (col_i % 2)
        fu, fv = u - col_i, v - math.floor(v) - 0.5
        d = math.hypot(fu, fv)
        r = max(r, math.exp(-((d - 0.62) / 0.12) ** 2) * (fu > 0.05) * ss(0.42, 0.30, x))
    dg = math.hypot((x - 0.86) / 1.0, y * 1.1)
    if x < 0.62:
        r = max(r, math.exp(-((dg - 0.42) / 0.035) ** 2) * ss(0.42, 0.30, abs(y)))
    de = math.hypot(x - 0.66, y - 0.15)
    r = max(r, math.exp(-((de - 0.075) / 0.018) ** 2), ss(0.04, 0.02, de) * 0.9)
    if x < -0.62:
        al = math.atan2(y, -(x + 0.62))
        r = max(r, (0.5 + 0.5 * math.cos(al * 12)) ** 3 * ss(-0.62, -0.72, x))
    if -0.32 < x < 0.12 and y > 0.36:
        r = max(r, (0.5 + 0.5 * math.cos(x * 42)) ** 3 * ss(0.36, 0.42, y))
    return min(1.0, r)


def taiyaki():
    """Тайяки: золотистая вафля-рыбка с рельефом формы - чешуя, жабра, глаз, плавники, тонкий хрустящий край."""
    outline = taiyaki_outline()
    ob = MX.outline_slab("Taiyaki", outline, 1.0, p=2.4, cuts=84, center=(-0.55, 0.0))

    def dome(x, y):
        return max(0.0, 1 - ((x - 0.12) / 0.86) ** 2 - (y / 0.5) ** 2)

    def shp(co):
        d = dome(co.x, co.y)
        half = 0.05 + 0.17 * d ** 0.6
        return Vector((co.x, co.y, co.z * 2 * half))
    deform(ob, shp)
    subdivide(ob, 1)

    def rel(co, n):
        if n.z < 0.3:
            return 0.0
        return 0.028 * taiyaki_relief(co.x, co.y) * ss(0.3, 0.6, n.z)
    EV.set_attr(ob, "relief", lambda co, n: taiyaki_relief(co.x, co.y) * ss(0.3, 0.6, n.z))
    push_normals(ob, rel)
    push_normals(ob, lambda co, n: 0.006 * fbm(co * 6))
    smooth(ob)
    sh = Sh("TaiyakiMat", rough=0.42, sss=0.25, sss_radius=(1.0, 0.6, 0.3), coat=0.45, coat_rough=0.12)
    _, _, nz = sh.xyz("Normal")
    x, y, z = sh.xyz()
    col = sh.ramp(sh.remap(sh.math("ADD", nz, sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 4, 3), 0.5), 0.5)),
                           -1, 1, smooth=False),
                  [(0.0, (0.76, 0.44, 0.15)), (0.4, (0.99, 0.80, 0.46)), (0.55, (1.0, 0.86, 0.56)),
                   (0.75, (0.96, 0.68, 0.30)), (1.0, (0.88, 0.56, 0.22))])
    col = sh.mix(sh.math("MULTIPLY", sh.attr("relief"), 0.8), col, (0.70, 0.38, 0.12))
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(None, 7, 3), 0.62, 0.75), 0.4), col, (0.70, 0.38, 0.12))
    sh.color(col)
    sh.bump(sh.noise(None, 30, 4), 0.12, 0.004)
    sh.rough_vary(0.32, 0.55, 8)
    assign(ob, sh.mat)
    return rotate_all([ob], (math.radians(58), 0, math.radians(-10)))


# MARK: - Эспрессо

def coffee_bean(name, mat, s=0.11):
    b = sphere(name, 1.0, 32, 20)
    b.scale = (s, s * 0.72, s * 0.5)
    apply_transform(b)
    push_normals(b, lambda co, n: -0.022 * s / 0.11 * math.exp(-(co.y / (0.012 * s / 0.11)) ** 2) * ss(0.0, 0.3, n.z)
                 * (1 - ss(0.8, 1.0, abs(co.x) / s)))
    smooth(b)
    return assign(b, mat)


def espresso():
    """Эспрессо: толстостенная чашечка, крема с тигровым рисунком и темной каймой, ложечка и зерна на блюдце."""
    white = ceramic_sh("EspPorcelain", [(0.0, (0.90, 0.91, 0.94)), (1.0, (1.0, 1.0, 1.0))], 0.0, 0.8)
    saucer = lathe("EspSaucer", [(0.0, 0.0), (0.42, 0.0), (0.45, 0.02), (0.46, 0.04), (0.50, 0.05), (0.80, 0.11),
                                 (0.95, 0.17), (0.98, 0.19), (0.965, 0.205), (0.93, 0.19), (0.78, 0.14), (0.52, 0.10),
                                 (0.30, 0.095), (0.0, 0.095)], 128)
    subdivide(saucer, 1)
    smooth(saucer, 50)
    sau = Sh("EspSaucerMat", rough=0.12, coat=0.85, coat_rough=0.04)
    _, _, sz_ = sau.xyz()
    rr = sau.vmath("LENGTH", sau.combine(*sau.xyz()[:2], 0.0))
    scol = sau.ramp(sau.remap(sz_, 0.0, 0.2, smooth=False), [(0.0, (0.88, 0.89, 0.93)), (1.0, (1.0, 1.0, 1.0))])
    scol = sau.mix(sau.math("MULTIPLY", sau.remap(rr, 0.90, 0.92), sau.remap(rr, 0.95, 0.93)), scol, (0.70, 0.24, 0.12))
    sau.color(scol)
    assign(saucer, sau.mat)
    zc = 0.095
    cup_prof = [(0.0, zc), (0.17, zc), (0.19, zc + 0.01), (0.20, zc + 0.05), (0.24, zc + 0.07), (0.32, zc + 0.16),
                (0.37, zc + 0.30), (0.39, zc + 0.46), (0.40, zc + 0.56), (0.395, zc + 0.585), (0.37, zc + 0.585),
                (0.355, zc + 0.50), (0.33, zc + 0.32), (0.27, zc + 0.20), (0.0, zc + 0.16)]
    cup = lathe("EspCup", cup_prof, 128)
    subdivide(cup, 1)
    smooth(cup, 50)
    assign(cup, white.mat)
    lz = zc + 0.47
    crema = polar_disc("EspCrema", 30, 128, 0.355, 0.355)
    deform(crema, lambda co: Vector((co.x, co.y, lz + 0.012 * (1 - (math.hypot(co.x, co.y) / 0.355) ** 2)
                                     + 0.004 * fbm(co * 20))))
    smooth(crema)
    cm = Sh("EspCremaMat", rough=0.35, sss=0.3, sss_radius=(1.0, 0.6, 0.3), coat=0.5, coat_rough=0.1)
    cx, cy, _ = cm.xyz()
    r2 = cm.vmath("LENGTH", cm.combine(cx, cy, 0.0))
    marb = cm.noise(cm.mapping(None, scale=(1.0, 1.0, 1.0)), 7.0, 5, 0.6, distortion=2.5)
    col = cm.ramp(marb, [(0.25, (0.62, 0.34, 0.12)), (0.45, (0.82, 0.54, 0.24)), (0.6, (0.92, 0.70, 0.40)),
                         (0.8, (0.70, 0.42, 0.16))])
    col = cm.mix(cm.remap(r2, 0.26, 0.345), col, (0.32, 0.15, 0.05))
    bub = cm.remap(cm.voronoi(None, 60, "F1"), 0.10, 0.05, 0.0, 0.35)
    col = cm.mix(cm.math("MULTIPLY", bub, cm.remap(r2, 0.33, 0.28)), col, (0.96, 0.84, 0.62))
    cm.color(col)
    cm.bump(bub, 0.2, 0.003)
    assign(crema, cm.mat)
    hp = EV.spline([(0.36, 0.0, zc + 0.46), (0.52, 0.0, zc + 0.47), (0.58, 0.0, zc + 0.36), (0.50, 0.0, zc + 0.24),
                    (0.34, 0.0, zc + 0.22)], 8)
    handle = EV.sweep("EspHandle", hp, lambda t: 0.045 - 0.012 * math.sin(math.pi * t), segs=16, step=0.01,
                      section=(1.0, 0.75))
    assign(handle, white.mat)
    cupset = [cup, crema, handle]
    for o in cupset:
        o.scale = (1.22, 1.22, 1.22)
        o.location.z -= zc * 0.22
        apply_transform(o)
    parts = [saucer] + cupset
    steel = Sh("EspSpoon", rough=0.15, metal=1.0)
    steel.color((0.86, 0.87, 0.90))
    spath = [(-0.08, 0.0, 0.0), (0.12, 0.0, 0.01), (0.30, 0.0, 0.03)]
    stem = EV.sweep("SpoonStem", EV.spline(spath, 6), lambda t: 0.018 + 0.012 * t, segs=12, step=0.01,
                    section=(1.0, 0.45))
    bowl_ = sphere("SpoonBowl", 1.0, 32, 20)
    bowl_.scale = (0.12, 0.075, 0.03)
    bowl_.location = (-0.20, 0, 0.02)
    apply_transform(bowl_)
    smooth(bowl_)
    sp = [stem, bowl_]
    for o in sp:
        assign(o, steel.mat)
    rotate_all(sp, (0, 0, math.radians(-30)))
    for o in sp:
        o.location += Vector((0.60, -0.30, 0.0))
    bpy.context.view_layer.update()
    MX.drop(sp, [saucer], floor=0.0, step=0.005, top=0.6)
    parts += sp
    bean = Sh("CoffeeBean", rough=0.25, coat=0.7, coat_rough=0.08)
    bean.color(bean.ramp(bean.noise(None, 20, 2), [(0.3, (0.30, 0.15, 0.06)), (0.7, (0.42, 0.22, 0.09))]))
    for i, (x, y, rz) in enumerate(((-0.62, -0.38, 30), (-0.46, -0.60, -40))):
        b = coffee_bean(f"EspBean{i}", bean.mat)
        b.rotation_euler = (0, 0, math.radians(rz))
        b.location = (x, y, 0.4)
        bpy.context.view_layer.update()
        MX.drop([b], [saucer], floor=0.0, step=0.005, top=0.5)
        parts.append(b)
    return rotate_all(parts, (0, 0, math.radians(-24)))


# MARK: - Канноли

def scatter_dir(target, count, make, axis, center, radius, seed=1, spacing=0.0):
    """Россыпь по поверхности лучом вдоль -axis из круга радиуса radius вокруг center (для торцов)."""
    rnd = random.Random(seed)
    ax = Vector(axis).normalized()
    u = ax.orthogonal().normalized()
    w = ax.cross(u)
    bpy.context.view_layer.update()
    inv = target.matrix_world.inverted()
    placed = []
    tries = 0
    while len(placed) < count and tries < count * 80:
        tries += 1
        a = rnd.uniform(0, 2 * math.pi)
        r = radius * math.sqrt(rnd.random())
        o = Vector(center) + ax * 5.0 + u * r * math.cos(a) + w * r * math.sin(a)
        ok, loc, nor, _ = target.ray_cast(inv @ o, (inv.to_3x3() @ -ax).normalized())
        if not ok:
            continue
        loc = target.matrix_world @ loc
        nor = (target.matrix_world.to_3x3() @ nor).normalized()
        if nor.dot(ax) < 0.2:
            continue
        if spacing and any((loc - q).length < spacing for q in placed):
            continue
        placed.append(loc)
        ob = make(len(placed) - 1, rnd)
        q = nor.to_track_quat("Z", "Y")
        spin = Matrix.Rotation(rnd.uniform(0, 2 * math.pi), 4, "Z")
        ob.matrix_world = Matrix.Translation(loc) @ q.to_matrix().to_4x4() @ spin @ ob.matrix_basis
    return placed


def cannoli_obj(prefix, shell_mat, cream_mat, choc_mat, pist_mat, sugar_mat_, seed=0):
    L, R = 1.35, 0.22
    shell = lathe_fn(prefix + "Shell", lambda t: R * (1 + 0.16 * (2 * t - 1) ** 2), -L / 2, L / 2, 80, 64,
                     lambda a, t: 1.0 + 0.02 * noise.noise(Vector((math.cos(a), math.sin(a), t * 5 + seed))))
    to_axis_x(shell)
    # полая трубка: срезаем торцы, даем толщину
    bm = _bm.new()
    bm.from_mesh(shell.data)
    kill = [f for f in bm.faces if abs(f.normal.x) > 0.9 and abs(f.calc_center_median().x) > L / 2 - 0.01]
    _bm.ops.delete(bm, geom=kill, context="FACES")
    bm.to_mesh(shell.data)
    bm.free()
    solidify(shell, 0.035, -1.0)
    subdivide(shell, 1)
    off = Vector((seed * 2.3, 0, 0))
    push_normals(shell, lambda co, n: 0.012 * max(0.0, fbm(co * 9 + off, 3)) if math.hypot(co.y, co.z) > R * 0.95 else 0.0)
    smooth(shell)
    assign(shell, shell_mat)
    parts = [shell]
    ends = []
    for side in (-1, 1):
        def rf(t):
            return R * 1.05 * (1 - ss(0.55, 1.0, t) ** 1.6 * 0.9)

        def rib(a, t, s=side):
            return 1.0 + 0.13 * math.cos(8 * a + s * 2.5 * t) * ss(0.15, 0.45, t)
        c = lathe_fn(f"{prefix}Cream{side}", rf, 0.0, 0.40, 50, 96, rib)
        to_axis_x(c)
        if side < 0:
            c.rotation_euler = (0, 0, math.pi)
            apply_transform(c)
        c.location.x = side * (L / 2 - 0.12)
        apply_transform(c)
        push_normals(c, lambda co, n: 0.006 * fbm(co * 12))
        smooth(c)
        assign(c, cream_mat)
        parts.append(c)
        ends.append((c, side))
    bits = []

    def make_choc(i, rnd):
        b = sphere(f"{prefix}Choc{len(bits)}", 1.0, 12, 8)
        b.scale = (0.03, 0.03, 0.035)
        apply_transform(b)
        deform(b, lambda co: Vector((co.x * (1 - 0.5 * max(0.0, co.z / 0.035)), co.y * (1 - 0.5 * max(0.0, co.z / 0.035)),
                                     co.z)))
        bits.append((b, choc_mat))
        return b

    def make_pist(i, rnd):
        b = MX.rcube(f"{prefix}Pist{len(bits)}", rnd.uniform(0.025, 0.04), rnd.uniform(0.02, 0.03), 0.018, p=3.0, cuts=2)
        b.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, 3))
        bits.append((b, pist_mat))
        return b
    for c, side in ends:
        cen = Vector((side * (L / 2 + 0.12), 0, 0))
        scatter_dir(c, 9, make_choc, (side, 0, 0), cen, 0.2, seed=seed * 7 + (side > 0) + 1, spacing=0.07)
        scatter_dir(c, 7, make_pist, (side, 0, 0), cen, 0.2, seed=seed * 7 + (side > 0) + 11, spacing=0.06)
    choc = join_one([b for b, m in bits if m is choc_mat], prefix + "Chocs", choc_mat)
    pist = join_one([b for b, m in bits if m is pist_mat], prefix + "Pists", pist_mat)
    parts += [choc, pist]
    return parts


def cannoli():
    """Два канноли: пузырчатая хрустящая трубочка в сахарной пудре, рикотта звездочкой с крошкой шоколада и фисташки."""
    sh = Sh("CannoliShell", rough=0.45, sss=0.2, sss_radius=(1.0, 0.6, 0.3), coat=0.45, coat_rough=0.15)
    _, _, nz = sh.xyz("Normal")
    blist = sh.voronoi(None, 22, "F1")
    col = sh.ramp(sh.noise(None, 5, 3), [(0.3, (0.92, 0.62, 0.28)), (0.6, (0.84, 0.50, 0.20)), (0.8, (0.70, 0.38, 0.13))])
    col = sh.mix(sh.remap(blist, 0.18, 0.05, 0.0, 0.6), col, (0.62, 0.30, 0.08))
    sugar_m = sh.math("MULTIPLY", sh.remap(sh.noise(None, 6, 4), 0.48, 0.62), sh.remap(nz, 0.35, 0.75))
    col = sh.mix(sugar_m, col, (1.0, 0.99, 0.97))
    sh.color(col)
    sh.set("Roughness", sh.remap(sugar_m, 0.0, 1.0, 0.4, 0.9, smooth=False))
    sh.bump(blist, 0.5, 0.012, invert=True)
    sh.bump(sh.noise(None, 40, 3), 0.1, 0.003)
    cr = Sh("CannoliRicotta", rough=0.45, sss=0.7, sss_radius=(1.0, 0.95, 0.85), sss_scale=0.08, coat=0.2, sheen=0.3)
    cr.color(cr.ramp(cr.noise(None, 8, 3), [(0.3, (1.0, 0.98, 0.93)), (0.7, (0.97, 0.94, 0.86))]))
    cr.bump(cr.voronoi(None, 70, "F1"), 0.15, 0.003, invert=True)
    choc = material("CannoliChoc", [(0.0, (0.18, 0.08, 0.04)), (1.0, (0.32, 0.16, 0.07))], rough=0.3, coat=0.5)
    pist = material("CannoliPist", [(0.0, (0.40, 0.62, 0.18)), (1.0, (0.62, 0.80, 0.30))], rough=0.35, coat=0.4,
                    sss=0.2)
    a = cannoli_obj("CanA", sh.mat, cr.mat, choc, pist, None, 0)
    b = cannoli_obj("CanB", sh.mat, cr.mat, choc, pist, None, 1)
    for o in a + b:
        o.location.z += 0.3
    rotate_all(a, (0, 0, math.radians(-28)))
    rotate_all(b, (0, 0, math.radians(22)))
    for o in a:
        o.location += Vector((0.0, 0.26, 0))
    for o in b:
        o.location += Vector((0.05, -0.25, 0))
    bpy.context.view_layer.update()
    MX.ground(a, 0.0)
    MX.drop(b, a, floor=0.0, step=0.01, top=1.6)
    return rotate_all(a + b, (math.radians(8), 0, math.radians(-8)))


M.MODELS.update({
    "tempura": tempura,
    "mochi": mochi,
    "taiyaki": taiyaki,
    "espresso": espresso,
    "cannoli": cannoli,
})


# MARK: - Мексика: общие материалы

def terracotta_sh(name, z0, z1, band=None, dots=None):
    """Неглазурованная терракота снаружи: теплый градиент, пятнистость, расписной кремовый поясок с точками."""
    sh = Sh(name, rough=0.55, coat=0.25, coat_rough=0.3, sss=0.05)
    _, _, z = sh.xyz()
    col = sh.ramp(sh.remap(z, z0, z1, smooth=False), [(0.0, (0.58, 0.24, 0.10)), (0.6, (0.80, 0.40, 0.18)),
                                                     (1.0, (0.90, 0.52, 0.26))])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.noise(None, 6, 4), 0.45, 0.7), 0.35), col, (0.66, 0.28, 0.12))
    if band:
        b0, b1 = band
        bm_ = sh.math("MULTIPLY", sh.remap(z, b0 - 0.006, b0), sh.remap(z, b1 + 0.006, b1))
        col = sh.mix(bm_, col, (1.0, 0.92, 0.74))
    if dots:
        dz, n, rad = dots
        ang = angle_sock(sh)
        ph = sh.math("PINGPONG", sh.math("MULTIPLY", ang, n / (2 * math.pi)), 0.5)
        dd = sh.vmath("LENGTH", sh.combine(sh.math("MULTIPLY", ph, 2 * math.pi / n * 0.8), sh.math("SUBTRACT", z, dz), 0.0))
        col = sh.mix(sh.remap(dd, rad, rad * 0.7), col, (1.0, 0.92, 0.74))
    sh.color(col)
    sh.bump(sh.noise(None, 25, 4), 0.12, 0.004)
    return sh


def glazed_in_sh(name):
    sh = Sh(name, rough=0.14, coat=0.85, coat_rough=0.05)
    sh.color(sh.ramp(sh.noise(None, 5, 3), [(0.3, (0.50, 0.24, 0.10)), (0.7, (0.62, 0.32, 0.14))]))
    return sh


# MARK: - Маса

def masa_dough_sh(name, z0, z1):
    sh = Sh(name, rough=0.6, sss=0.55, sss_radius=(1.0, 0.8, 0.4), sss_scale=0.08, sheen=0.4, sheen_rough=0.5,
            coat=0.08, coat_rough=0.4)
    _, _, z = sh.xyz()
    col = sh.ramp(sh.remap(z, z0, z1, smooth=False), [(0.0, (0.92, 0.68, 0.24)), (0.5, (0.99, 0.80, 0.36)),
                                                     (1.0, (1.0, 0.88, 0.50))])
    grit = sh.remap(sh.voronoi(None, 70, "F1"), 0.12, 0.05, 0.0, 0.6)
    col = sh.mix(sh.math("MULTIPLY", grit, sh.remap(sh.noise(None, 9, 2), 0.4, 0.6)), col, (0.90, 0.66, 0.26))
    col = sh.mix(sh.math("MULTIPLY", sh.remap(sh.voronoi(None, 40, "F1"), 0.08, 0.03), 0.5), col, (1.0, 0.96, 0.80))
    sh.color(col)
    sh.bump(grit, 0.25, 0.003)
    sh.bump(sh.noise(None, 14, 4), 0.12, 0.008)
    return sh


def masa():
    """Миска кукурузного теста масы: зернистое тесто с вмятинами и трещинками, шарики теста на сухом початочном листе."""
    prof = [(0.0, 0.0), (0.34, 0.0), (0.38, 0.02), (0.40, 0.06), (0.56, 0.16), (0.72, 0.32), (0.80, 0.46),
            (0.83, 0.54), (0.81, 0.58), (0.76, 0.57), (0.72, 0.49), (0.62, 0.35), (0.46, 0.21), (0.0, 0.18)]
    bowl = lathe("MasaBowl", prof, 128)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = terracotta_sh("MasaBowlOut", 0.0, 0.58, band=(0.40, 0.43), dots=(0.30, 18, 0.025))
    BK.inner_faces(bowl, out.mat, glazed_in_sh("MasaBowlIn").mat, 0.15)
    parts = [bowl]
    dough_ = sphere("Masa", 0.70, 96, 64)

    def shape(co):
        z = co.z * 0.66 if co.z > 0 else co.z * 0.3
        return Vector((co.x, co.y, z + 0.44))
    deform(dough_, shape)

    def dents(co, n):
        d = 0.03 * fbm(co * 2.2) + 0.006 * fbm(co * 9)
        for cx, cy in ((0.14, -0.20), (-0.22, 0.04), (0.02, 0.22)):
            d -= 0.055 * math.exp(-((co.x - cx) ** 2 + (co.y - cy) ** 2) / 0.012)
        d -= 0.012 * max(0.0, 1 - abs(noise.noise(co * 5.0)) / 0.08) * ss(0.3, 0.8, n.z)
        return d
    push_normals(dough_, dents)
    smooth(dough_)
    dsh = masa_dough_sh("MasaMat", 0.3, 0.92)
    assign(dough_, dsh.mat)
    parts.append(dough_)
    h1 = MX.husk_leaf("MasaHusk", 1.6, 0.55, cup=0.12)
    h1.rotation_euler = (0, 0, math.radians(150))
    h1.location = (-0.75, 0.55, 0.0)
    h2 = MX.husk_leaf("MasaHusk2", 1.3, 0.50, cup=0.10)
    h2.rotation_euler = (0, 0, math.radians(-25))
    h2.location = (0.95, -0.45, 0.0)
    parts += [h1, h2]
    bpy.context.view_layer.update()
    MX.ground([h1], 0.0)
    MX.ground([h2], 0.0)
    bsh = masa_dough_sh("MasaBallMat", 0.0, 0.3)
    for i, (x, y) in enumerate(((0.88, -0.55), (1.16, -0.42))):
        b = sphere(f"MasaBall{i}", 0.17, 48, 32)
        b.scale = (1, 1, 0.82)
        apply_transform(b)
        push_normals(b, lambda co, n: 0.008 * fbm(co * 10))
        smooth(b)
        assign(b, bsh.mat)
        b.location = (x, y, 0.5)
        bpy.context.view_layer.update()
        MX.drop([b], [h1, h2], floor=0.0, step=0.006, top=0.6)
        parts.append(b)
    return rotate_all(parts, (0, 0, math.radians(-12)))


# MARK: - Тортильи

def tortilla_sh(name):
    sh = Sh(name, rough=0.55, sss=0.35, sss_radius=(1.0, 0.8, 0.5), sss_scale=0.04, sheen=0.3, coat=0.1, coat_rough=0.4)
    x, y, _ = sh.xyz()
    rr = sh.vmath("LENGTH", sh.combine(x, y, 0.0))
    col = sh.ramp(sh.remap(rr, 0.0, 1.0, smooth=False), [(0.0, (1.0, 0.89, 0.58)), (0.75, (0.99, 0.85, 0.52)),
                                                        (1.0, (0.94, 0.74, 0.40))])
    grain = sh.remap(sh.voronoi(None, 80, "F1"), 0.1, 0.04, 0.0, 0.4)
    col = sh.mix(grain, col, (0.92, 0.72, 0.38))
    cells = sh.voronoi(None, 5.5, "F1", 1.0, "Distance")
    rnd_c = sh.xyz(sh.voronoi(None, 5.5, "F1", 1.0, "Color"))[0]
    sel = sh.remap(rnd_c, 0.30, 0.40)
    halo = sh.math("MULTIPLY", sh.remap(cells, 0.36, 0.18, 0.0, 0.65), sel)
    core = sh.math("MULTIPLY", sh.remap(sh.math("ADD", cells, sh.math("MULTIPLY", sh.noise(None, 20, 3), 0.08)), 0.19,
                                        0.10), sel)
    col = sh.mix(halo, col, (0.78, 0.50, 0.20))
    col = sh.mix(core, col, (0.34, 0.17, 0.06))
    small = sh.math("MULTIPLY", sh.remap(sh.voronoi(None, 16, "F1"), 0.07, 0.03), sh.remap(sh.noise(None, 4, 2), 0.5, 0.6))
    col = sh.mix(sh.math("MULTIPLY", small, 0.8), col, (0.50, 0.28, 0.10))
    sh.color(col)
    sh.bump(sh.math("MAXIMUM", core, small), 0.2, 0.006)
    sh.bump(sh.noise(None, 25, 4), 0.1, 0.004)
    return sh


def tortilla():
    """Стопка мягких кукурузных тортилий: края чуть свисают волной, сверху подпалины с комаля и пузырьки."""
    mats = [tortilla_sh(f"TortillaMat{i}").mat for i in range(2)]
    parts = []
    n = 5
    for i in range(n):
        ob = polar_disc(f"Tortilla{i}", 34, 180, 1.0, 1.0)
        rnd = random.Random(i * 7 + 1)
        ph = rnd.uniform(0, 6.28)
        droop = 0.03 + 0.03 * i

        def shp(co, ph=ph, droop=droop):
            a = math.atan2(co.y, co.x)
            rr = math.hypot(co.x, co.y)
            k = 1.0 + 0.025 * math.sin(3 * a + ph) + 0.012 * math.sin(7 * a + 2 * ph)
            z = -droop * ss(0.55, 1.0, rr) * (0.7 + 0.3 * math.sin(4 * a + ph)) + 0.02 * math.sin(2 * a + ph) * rr ** 3
            z += 0.008 * fbm(co * 4 + Vector((ph, 0, 0)))
            return Vector((co.x * k, co.y * k, z))
        deform(ob, shp)
        solidify(ob, 0.04, 1.0)
        subdivide(ob, 1)
        smooth(ob)
        assign(ob, mats[i % 2])
        ob.rotation_euler = (0, 0, i * 1.1)
        ob.location = (0.05 * math.cos(i * 2.3), 0.05 * math.sin(i * 2.3), 0.30 + i * 0.05)
        parts.append(ob)
    bpy.context.view_layer.update()
    placed = []
    for ob in parts:
        if placed:
            MX.drop([ob], placed, floor=0.0, step=0.004, top=ob.location.z + 0.3)
        else:
            MX.ground([ob], 0.0)
        placed.append(ob)
    # сверху тортилья, сложенная пополам
    top = polar_disc("TortillaFold", 34, 180, 0.95, 0.95)
    deform(top, lambda co: Vector((co.x * (1 + 0.02 * math.sin(3 * math.atan2(co.y, co.x))),
                                   co.y * (1 + 0.02 * math.sin(3 * math.atan2(co.y, co.x))), 0.008 * fbm(co * 4))))
    deform(top, MX.fold_fn(-0.02, 0.05, math.radians(172)))
    solidify(top, 0.04, 1.0)
    subdivide(top, 1)
    smooth(top)
    assign(top, mats[0])
    top.rotation_euler = (0, 0, math.radians(-100))
    top.location = (0.05, -0.12, 1.0)
    bpy.context.view_layer.update()
    MX.drop([top], parts, floor=0.0, step=0.004, top=0.8)
    parts.append(top)
    return rotate_all(parts, (math.radians(24), 0, math.radians(-10)))


# MARK: - Фасоль

def beans():
    """Глиняная миска с горкой блестящей черной фасоли, листики кинзы, пара фасолин рядом."""
    prof = [(0.0, 0.0), (0.36, 0.0), (0.40, 0.02), (0.42, 0.07), (0.60, 0.18), (0.76, 0.38), (0.82, 0.56),
            (0.83, 0.64), (0.81, 0.68), (0.76, 0.67), (0.73, 0.56), (0.64, 0.38), (0.46, 0.22), (0.0, 0.19)]
    bowl = lathe("BeanBowl", prof, 128)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = terracotta_sh("BeanBowlOut", 0.0, 0.68, band=(0.46, 0.50), dots=(0.34, 20, 0.024))
    BK.inner_faces(bowl, out.mat, glazed_in_sh("BeanBowlIn").mat, 0.15)
    parts = [bowl]
    for i, sx in enumerate((-1, 1)):
        h = torus(f"BeanHandle{i}", 0.10, 0.035, 48, 16)
        h.rotation_euler = (math.radians(90), 0, 0)
        h.location = (sx * 0.84, 0, 0.52)
        apply_transform(h)
        assign(smooth(h), out.mat)
        parts.append(h)
    mound = polar_disc("BeanMound", 28, 128, 0.75, 0.75)
    deform(mound, lambda co: Vector((co.x, co.y, 0.58 + 0.26 * max(0.0, 1 - (math.hypot(co.x, co.y) / 0.75) ** 2) ** 0.8)))
    smooth(mound)
    assign(mound, flat("BeanSauce", (0.10, 0.05, 0.07), rough=0.15, coat=0.9, coat_rough=0.04))
    parts.append(mound)
    bsh = Sh("BlackBean", rough=0.14, coat=0.9, coat_rough=0.04, sss=0.1, sss_radius=(0.6, 0.3, 0.5))
    _, _, nz = bsh.xyz("Normal")
    bcol = bsh.ramp(bsh.remap(nz, -1, 1, smooth=False), [(0.0, (0.06, 0.03, 0.05)), (0.6, (0.16, 0.08, 0.13)),
                                                        (1.0, (0.30, 0.16, 0.24))])
    x, y, z = bsh.xyz()
    hil = bsh.vmath("LENGTH", bsh.combine(x, bsh.math("SUBTRACT", y, -0.045), bsh.math("SUBTRACT", z, 0.0)))
    bcol = bsh.mix(bsh.remap(hil, 0.022, 0.014), bcol, (0.92, 0.90, 0.86))
    bsh.color(bcol)
    beans_ = []

    def bean_obj(nm):
        b = sphere(nm, 1.0, 20, 12)
        b.scale = (0.092, 0.058, 0.05)
        apply_transform(b)
        bend(b, 0.32)
        return b

    def make(i, rnd):
        b = bean_obj(f"Bean{len(beans_)}")
        b.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), 0)
        b.location.z += 0.02
        beans_.append(b)
        return b
    scatter_on(mound, 130, make, seed=6, area=0.74, spacing=0.095, zmin=0.58)
    scatter_on(mound, 70, make, seed=9, area=0.70, spacing=0.0, zmin=0.62)
    parts.append(join_one(beans_, "Beans", bsh.mat))
    for i, (x_, y_, rz) in enumerate(((0.72, -0.78, 20), (0.95, -0.62, -50), (0.55, -0.95, 80))):
        b = bean_obj(f"BeanOut{i}")
        assign(b, bsh.mat)
        smooth(b)
        b.rotation_euler = (0, 0, math.radians(rz))
        b.location = (x_, y_, 0.044)
        parts.append(b)
    herb = MX.herb_mat("BeanHerb")
    bpy.context.view_layer.update()
    for i, (x_, y_, rz, s_) in enumerate(((-0.12, -0.10, 30, 0.16), (0.10, 0.05, -60, 0.13))):
        c = MX.cilantro(f"BeanCil{i}", s_)
        c.rotation_euler = (math.radians(12), 0, math.radians(rz))
        c.location = (x_, y_, 1.2)
        assign(c, herb)
        bpy.context.view_layer.update()
        MX.drop([c], [p for p in parts if p.name.startswith("Beans")], floor=0.5, step=0.005, top=1.1)
        parts.append(c)
    return rotate_all(parts, (0, 0, math.radians(-8)))


# MARK: - Тамале

def tamale():
    """Тамале: кукурузный лист лодочкой раскрыт, видна зернистая маса с красной начинкой; хвост перевязан полоской листа."""
    parts = MX.tamale()
    husk, fill, tie = parts[0], parts[1], parts[2]
    # исходный tamale уже повернут: работаем в его локальной системе через обратный поворот
    back = Matrix.Rotation(math.radians(-10), 4, "X") @ Matrix.Rotation(math.radians(22), 4, "Z")
    for o in parts:
        o.matrix_world = back @ o.matrix_world
    bpy.context.view_layer.update()
    bake_all(parts)
    dsh = masa_dough_sh("TamaleMasa", 0.15, 0.75)
    assign(fill, dsh.mat)
    # кармашек с красной начинкой в масе вдоль верха
    zc = 0.42
    red = Sh("TamaleRed", rough=0.3, sss=0.4, sss_radius=(1.0, 0.3, 0.2), coat=0.6, coat_rough=0.1)
    red.color(red.ramp(red.noise(None, 14, 4), [(0.3, (0.58, 0.12, 0.06)), (0.6, (0.74, 0.20, 0.08)),
                                                (0.8, (0.86, 0.32, 0.12))]))
    red.bump(red.noise(None, 30, 4), 0.4, 0.01)
    bpy.context.view_layer.update()
    rf = polar_disc("TamaleRedFill", 20, 120, 1.0, 1.0)

    def pocket(co):
        a = math.atan2(co.y, co.x)
        t = math.hypot(co.x, co.y)
        k = 1.0 + 0.12 * fbm(Vector((math.cos(a) * 2, math.sin(a) * 2, 0.5)))
        x = -0.42 + co.x * 0.60 * k
        y = co.y * 0.15 * k
        ok, loc, _, _ = fill.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))
        zt = loc.z if ok else zc + 0.28
        return Vector((x, y, zt - 0.006 + 0.03 * max(0.0, 1 - t * t) + 0.012 * fbm(co * 6)))
    deform(rf, pocket)
    solidify(rf, 0.02, 1.0)
    smooth(rf)
    assign(rf, red.mat)
    # рыхлые волокна мяса сверху начинки
    shreds = []
    rnd = random.Random(4)
    for i in range(14):
        x = rnd.uniform(-0.90, 0.06)
        y = rnd.uniform(-0.06, 0.06)
        a = rnd.uniform(-0.6, 0.6)
        ok, loc, _, _ = rf.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))
        zt = (loc.z if ok else zc + 0.3) + 0.008
        pts = [(x + 0.07 * math.cos(a) * s_, y + 0.07 * math.sin(a) * s_, zt + 0.01 * math.sin(s_ * 3))
               for s_ in (-1.0, -0.3, 0.3, 1.0)]
        sh_ = EV.sweep(f"Shred{i}", pts, 0.013, segs=8, step=0.01)
        shreds.append(sh_)
    sj = join_one(shreds, "TamaleShreds", red.mat)
    parts += [rf, sj]
    return rotate_all(parts, (math.radians(16), 0, math.radians(-24)))


# MARK: - Орчата

def horchata():
    """Стакан орчаты: сливочный рисовый напиток с корицей сверху, лед, палочка корицы, капли конденсата на стекле."""
    prof = [(0.0, 0.0), (0.40, 0.0), (0.43, 0.03), (0.44, 0.08), (0.48, 1.45), (0.455, 1.46), (0.42, 0.14),
            (0.40, 0.12), (0.0, 0.12)]
    glass = lathe("HorGlass", prof, 96)
    subdivide(glass, 1)
    smooth(glass, 50)
    assign(glass, MX.glass_mat("HorGlassMat"))
    milk_ = lathe("HorMilk", [(0.0, 0.125), (0.415, 0.125), (0.448, 1.22), (0.0, 1.22)], 96)
    smooth(milk_, 50)
    m = Sh("HorMilkMat", rough=0.3, sss=0.2, sss_radius=(1.0, 0.9, 0.7), sss_scale=0.05, coat=0.3, coat_rough=0.15)
    _, _, z = m.xyz()
    mcol = m.ramp(m.remap(z, 0.1, 1.22, smooth=False), [(0.0, (0.95, 0.82, 0.62)), (0.6, (1.0, 0.92, 0.78)),
                                                        (1.0, (1.0, 0.95, 0.86))])
    m.color(mcol)
    m.set("Emission Color", _col((1.0, 0.94, 0.84)))
    m.set("Emission Strength", 0.5)
    assign(milk_, m.mat)
    top = polar_disc("HorTop", 24, 96, 0.447, 0.447)
    deform(top, lambda co: Vector((co.x, co.y, 1.222 + 0.008 * fbm(co * 8))))
    smooth(top)
    t = Sh("HorTopMat", rough=0.5, sss=0.15, sss_radius=(1.0, 0.9, 0.7), sheen=0.4)
    tcol = t.ramp(t.noise(None, 5, 3), [(0.3, (1.0, 0.95, 0.86)), (0.7, (0.98, 0.90, 0.78))])
    dust = t.remap(t.noise(None, 3.5, 5, 0.6), 0.5, 0.66, 0.0, 0.8)
    tcol = t.mix(dust, tcol, (0.78, 0.48, 0.24))
    sp = t.remap(t.voronoi(None, 50, "F1"), 0.1, 0.04, 0.0, 0.9)
    tcol = t.mix(sp, tcol, (0.52, 0.26, 0.10))
    t.color(tcol)
    t.set("Emission Color", _col((1.0, 0.94, 0.84)))
    t.set("Emission Strength", 0.2)
    assign(top, t.mat)
    parts = [glass, milk_, top]
    for i, (x, y, rot) in enumerate(((-0.17, -0.10, (0.3, 0.2, 0.5)), (0.14, -0.14, (-0.2, 0.4, 1.2)),
                                     (-0.02, 0.18, (0.5, -0.3, 0.2)))):
        c = MX.ice_cube(f"HorIce{i}", 0.14, rot)
        c.location = (x, y, 1.26)
        parts.append(c)
    # ободок из сахара с корицей по краю стакана
    rim = torus("HorRim", 0.466, 0.032, 128, 16)
    rim.scale = (1, 1, 1.3)
    rim.location = (0, 0, 1.425)
    apply_transform(rim)
    push_normals(rim, lambda co, n: 0.008 * fbm(co * 30))
    smooth(rim)
    rs = Sh("HorRimMat", rough=0.7, sss=0.2, sheen=0.4)
    rcol = rs.ramp(rs.noise(None, 30, 3), [(0.3, (0.96, 0.84, 0.64)), (0.7, (0.86, 0.62, 0.36))])
    rcol = rs.mix(rs.remap(rs.voronoi(None, 90, "F1"), 0.12, 0.05), rcol, (0.52, 0.26, 0.10))
    rs.color(rcol)
    rs.bump(rs.voronoi(None, 90, "F1"), 0.5, 0.004, invert=True)
    assign(rim, rs.mat)
    parts.append(rim)
    cin = EV.cinnamon_stick("HorCinnamon", 1.5, 0.075)
    cin.rotation_euler = (0, math.radians(-68), math.radians(30))
    cin.location = (0.12, 0.10, 1.45)
    parts.append(cin)
    cin2 = EV.cinnamon_stick("HorCinnamon2", 0.8, 0.065)
    cin2.rotation_euler = (0, 0, math.radians(18))
    cin2.location = (0.40, -0.55, 0.065)
    parts.append(cin2)
    return rotate_all(parts, (0, 0, math.radians(-14)))


M.MODELS.update({
    "masa": masa,
    "tortilla": tortilla,
    "beans": beans,
    "tamale": tamale,
    "horchata": horchata,
})


# MARK: - Сахар

def sugar_crystal_sh(name):
    """Рафинад: белый, зернистый; часть кристалликов блестит."""
    sh = Sh(name, rough=0.5, sss=0.35, sss_radius=(1.0, 1.0, 1.0), sss_scale=0.04, coat=0.15, coat_rough=0.2)
    cells = sh.voronoi(None, 70, "F1", 1.0, "Color")
    cr, cg, _ = sh.xyz(cells)
    _, _, nz = sh.xyz("Normal")
    col = sh.ramp(sh.remap(nz, -1, 1, smooth=False), [(0.0, (0.86, 0.88, 0.93)), (1.0, (1.0, 1.0, 1.0))])
    col = sh.mix(sh.math("MULTIPLY", sh.remap(cr, 0.0, 1.0), 0.25), col, (0.84, 0.86, 0.92))
    sh.color(col)
    sh.set("Roughness", sh.remap(cg, 0.80, 0.86, 0.55, 0.06))
    sh.bump(sh.voronoi(None, 70, "F1"), 0.35, 0.004)
    sh.bump(sh.noise(None, 120, 2), 0.15, 0.002)
    return sh.mat


def sugar():
    """Сахарница с кобальтовым узором, горка искрящегося рафинада, серебряные щипцы, пара кубиков рядом."""
    prof = [(0.0, 0.0), (0.30, 0.0), (0.33, 0.02), (0.34, 0.06), (0.31, 0.09), (0.36, 0.12), (0.50, 0.21),
            (0.60, 0.34), (0.625, 0.45), (0.60, 0.56), (0.555, 0.65), (0.56, 0.70), (0.565, 0.725), (0.54, 0.74),
            (0.515, 0.715), (0.52, 0.62), (0.555, 0.47), (0.50, 0.30), (0.32, 0.2), (0.0, 0.18)]
    bowl = lathe("SugarBowl", prof, 128)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = Sh("SugarPorcelain", rough=0.12, coat=0.85, coat_rough=0.04)
    _, _, z = out.xyz()
    col = out.ramp(out.remap(z, 0.0, 0.74, smooth=False), [(0.0, (0.88, 0.90, 0.96)), (1.0, (1.0, 1.0, 1.0))])
    cobalt = (0.14, 0.28, 0.72)
    bands = out.math("MAXIMUM", out.remap(z, 0.665, 0.68), out.remap(z, 0.10, 0.085))
    bands = out.math("MAXIMUM", bands, out.math("MULTIPLY", out.remap(z, 0.535, 0.545), out.remap(z, 0.575, 0.565)))
    ang = angle_sock(out)
    vine = out.math("SUBTRACT", z, out.math("ADD", 0.40, out.math("MULTIPLY", out.math("SINE", out.math("MULTIPLY", ang, 8)),
                                                                     0.05)))
    vine_m = out.remap(out.math("ABSOLUTE", vine), 0.012, 0.006)
    ph = out.math("PINGPONG", out.math("MULTIPLY", ang, 8 / (2 * math.pi)), 0.5)
    flower = out.vmath("LENGTH", out.combine(out.math("MULTIPLY", out.math("SUBTRACT", ph, 0.25), 0.62),
                                             out.math("SUBTRACT", z, 0.40), 0.0))
    fl_m = out.remap(flower, 0.045, 0.035)
    col = out.mix(out.math("MAXIMUM", out.math("MAXIMUM", bands, vine_m), fl_m), col, cobalt)
    out.color(col)
    inn = ceramic_sh("SugarPorcelainIn", [(0.0, (0.90, 0.92, 0.97)), (1.0, (1.0, 1.0, 1.0))], 0.2, 0.74)
    BK.inner_faces(bowl, out.mat, inn.mat, 0.15)
    parts = [bowl]
    for i, sx in enumerate((-1, 1)):
        h = torus(f"SugarHandle{i}", 0.11, 0.032, 48, 16)
        h.rotation_euler = (math.radians(90), 0, 0)
        h.location = (sx * 0.64, 0, 0.5)
        apply_transform(h)
        assign(smooth(h), inn.mat)
        parts.append(h)
    smat = sugar_crystal_sh("SugarCubeMat")
    rnd = random.Random(3)
    cubes = []
    inside = [(0.0, 0.0, 0.2)]
    for k in range(5):
        a_ = 2 * math.pi * k / 5 + 0.3
        inside.append((0.27 * math.cos(a_), 0.27 * math.sin(a_), rnd.uniform(0, 1.5)))
    for k in range(3):
        a_ = 2 * math.pi * k / 3 + 0.9
        inside.append((0.13 * math.cos(a_), 0.13 * math.sin(a_), rnd.uniform(0, 1.5)))
    for i, (x, y, rz) in enumerate(inside):
        c = BK.sugar_cube(f"SugarIn{i}", 0.21, smat)
        c.rotation_euler = (rnd.uniform(-0.2, 0.2), rnd.uniform(-0.2, 0.2), rz)
        c.location = (x, y, 1.6)
        bpy.context.view_layer.update()
        MX.drop([c], [bowl] + cubes, floor=0.2, step=0.006, top=1.5)
        cubes.append(c)
    parts += cubes
    for i, (x, y, rz) in enumerate(((0.66, -0.62, 0.4), (0.40, -0.80, -0.3), (0.56, -0.80, 0.9))):
        c = BK.sugar_cube(f"SugarOut{i}", 0.21, smat)
        c.rotation_euler = (0, 0, rz)
        c.location = (x, y, 0.6)
        bpy.context.view_layer.update()
        MX.drop([c], [o for o in parts if o.name.startswith("SugarOut")], floor=0.0, step=0.008, top=0.5)
        parts.append(c)
    # крышка прислонена к сахарнице слева
    lid = lathe("SugarLid", [(0.0, 0.0), (0.56, 0.0), (0.575, 0.02), (0.55, 0.05), (0.42, 0.13), (0.22, 0.18),
                             (0.10, 0.19), (0.09, 0.23), (0.12, 0.27), (0.10, 0.32), (0.0, 0.33)], 96)
    subdivide(lid, 1)
    smooth(lid, 50)
    lm = Sh("SugarLidMat", rough=0.12, coat=0.85, coat_rough=0.04)
    _, _, lz = lm.xyz()
    lcol = lm.ramp(lm.remap(lz, 0.0, 0.33, smooth=False), [(0.0, (0.90, 0.92, 0.97)), (1.0, (1.0, 1.0, 1.0))])
    lcol = lm.mix(lm.remap(lz, 0.05, 0.035), lcol, cobalt)
    lcol = lm.mix(lm.remap(lz, 0.19, 0.20), lcol, cobalt)
    lcol = lm.mix(lm.math("MULTIPLY", lm.remap(lz, 0.095, 0.10), lm.remap(lz, 0.12, 0.115)), lcol, cobalt)
    lm.color(lcol)
    assign(lid, lm.mat)
    lid.rotation_euler = (0, math.radians(-68), math.radians(20))
    lid.location = (-1.05, 0.12, 0.6)
    bpy.context.view_layer.update()
    MX.ground([lid], 0.0)
    MX.nudge([lid], [bowl], (-1, 0, 0), 0.01)
    parts.append(lid)
    return rotate_all(parts, (0, 0, math.radians(8)))


# MARK: - Взбитые сливки

def whip_obj(name, R, H, z0, seed=0.0):
    ob = polar_disc(name, 56, 240, R, R)

    def shape(co):
        r = min(1.0, math.hypot(co.x, co.y) / R)
        a = math.atan2(co.y, co.x)
        h = H * max(0.0, 1 - r * r) ** 0.65
        sw = math.sin(5 * a + 13 * r + seed + 1.5 * fbm(co * 1.5))
        h += 0.09 * sw * (1 - r) ** 0.6 * ss(0.05, 0.25, r)
        pk = math.exp(-(r / 0.24) ** 2)
        h += 0.50 * pk ** 1.3
        dx = 0.16 * pk ** 4
        dy = -0.08 * pk ** 4
        return Vector((co.x + dx, co.y + dy, z0 + h))
    deform(ob, shape)
    solidify(ob, 0.16, -1.0)
    subdivide(ob, 1)
    smooth(ob)
    return ob


def cream():
    """Миска взбитых сливок: пышная шапка со спиральными складками и загнутым пиком, венчик со сливками."""
    bowl = lathe("CreamBowl", [(0.0, 0.0), (0.36, 0.0), (0.39, 0.02), (0.40, 0.07), (0.38, 0.09), (0.52, 0.16),
                               (0.74, 0.36), (0.86, 0.56), (0.90, 0.64), (0.885, 0.665), (0.855, 0.66), (0.82, 0.58),
                               (0.70, 0.38), (0.48, 0.20), (0.0, 0.16)], 128)
    subdivide(bowl, 1)
    smooth(bowl, 50)
    out = Sh("CreamBowlOut", rough=0.14, coat=0.85, coat_rough=0.05)
    _, _, z = out.xyz()
    col = out.ramp(out.remap(z, 0.0, 0.66, smooth=False), [(0.0, (0.40, 0.62, 0.90)), (0.7, (0.56, 0.76, 0.98)),
                                                          (1.0, (0.70, 0.86, 1.0))])
    col = out.mix(out.math("MULTIPLY", out.remap(out.voronoi(None, 40, "F1"), 0.06, 0.02), 0.6), col, (0.28, 0.46, 0.78))
    col = out.mix(out.remap(z, 0.62, 0.645), col, (0.98, 0.98, 1.0))
    out.color(col)
    inn = ceramic_sh("CreamBowlIn", [(0.0, (0.92, 0.94, 0.98)), (1.0, (1.0, 1.0, 1.0))], 0.1, 0.66)
    BK.inner_faces(bowl, out.mat, inn.mat, 0.12)
    wm = Sh("WhipMat", rough=0.38, sss=0.75, sss_radius=(1.0, 0.95, 0.85), sss_scale=0.12, coat=0.25, coat_rough=0.15,
            sheen=0.3)
    _, _, nz = wm.xyz("Normal")
    wm.color(wm.ramp(wm.remap(nz, -0.3, 1.0, smooth=False), [(0.0, (0.94, 0.90, 0.82)), (0.5, (0.99, 0.97, 0.92)),
                                                             (1.0, (1.0, 1.0, 0.98))]))
    wm.bump(wm.noise(None, 30, 3), 0.05, 0.004)
    mound = whip_obj("Whip", 0.86, 0.36, 0.58, 2.0)
    assign(mound, wm.mat)
    parts = [bowl, mound]
    wk = BK.whisk("Whisk")
    blobs = []
    for i, (x, y, z_, r) in enumerate(((0.0, 0.0, -0.62, 0.09), (0.08, 0.06, -0.52, 0.06), (-0.07, -0.03, -0.55, 0.07),
                                       (0.03, -0.09, -0.45, 0.05))):
        b = sphere(f"WhiskCream{i}", r, 32, 20)
        b.location = (x, y, z_)
        apply_transform(b)
        push_normals(b, lambda co, n: 0.012 * fbm(co * 14))
        smooth(b)
        blobs.append(b)
    wk.append(join_one(blobs, "WhiskCream", wm.mat))
    rotate_all(wk, (math.radians(-24), math.radians(36), 0))
    for o in wk:
        o.location += Vector((0.44, 0.22, 1.36))
    parts += wk
    return rotate_all(parts, (0, 0, math.radians(-10)))


# MARK: - Масло

def butter():
    """Брусок сливочного масла на масленке: срез, следы ножа сверху, завиток, нож с мазком масла."""
    dish = BK.rr_lathe("ButterDish", [(0.0, 0.0), (0.80, 0.0), (0.85, 0.02), (0.87, 0.06), (0.96, 0.15), (1.0, 0.19),
                                      (0.975, 0.205), (0.90, 0.12), (0.86, 0.095), (0.0, 0.09)], 1.05, 0.74, 5.0, 160)
    subdivide(dish, 1)
    smooth(dish, 50)
    dm = Sh("ButterDishMat", rough=0.12, coat=0.85, coat_rough=0.04)
    _, _, z = dm.xyz()
    dcol = dm.ramp(dm.remap(z, 0.0, 0.21, smooth=False), [(0.0, (0.36, 0.66, 0.70)), (0.6, (0.56, 0.84, 0.86)),
                                                         (1.0, (0.76, 0.94, 0.94))])
    dcol = dm.mix(dm.math("MULTIPLY", dm.remap(dm.voronoi(None, 35, "F1"), 0.05, 0.02), 0.5), dcol, (0.30, 0.56, 0.60))
    dm.color(dcol)
    assign(dish, dm.mat)
    bm_ = Sh("ButterMat", rough=0.3, sss=0.6, sss_radius=(1.0, 0.8, 0.4), sss_scale=0.1, coat=0.35, coat_rough=0.14)
    x, y, z = bm_.xyz()
    _, _, nz = bm_.xyz("Normal")
    bcol = bm_.ramp(bm_.remap(z, 0.09, 0.51, smooth=False), [(0.0, (1.0, 0.80, 0.34)), (1.0, (1.0, 0.91, 0.56))])
    scrape = bm_.math("PINGPONG", bm_.math("ADD", bm_.math("MULTIPLY", x, 9.0),
                                           bm_.math("MULTIPLY", bm_.noise(None, 3, 2), 1.2)), 0.5)
    top = bm_.remap(nz, 0.6, 0.9)
    bcol = bm_.mix(bm_.math("MULTIPLY", bm_.remap(scrape, 0.1, 0.0, 0.0, 0.25), top), bcol, (1.0, 0.96, 0.74))
    bm_.color(bcol)
    bm_.bump(bm_.math("MULTIPLY", scrape, top), 0.15, 0.01)
    bm_.bump(bm_.noise(None, 20, 3), 0.05, 0.004)
    block = box_mesh("Butter", 1.10, 0.58, 0.42, 0.09, cuts=8)
    bevel(block, 0.06, 5, 30)
    subdivide(block, 1)
    push_normals(block, lambda co, n: 0.006 * fbm(co * 3.0) + (0.01 * math.sin(co.x * 28) * ss(0.4, 0.5, co.z)
                                                              if n.z > 0.8 else 0.0))
    smooth(block)
    assign(block, bm_.mat)
    # отрезанный ломтик чуть отодвинут
    sl = box_mesh("ButterSlice", 0.16, 0.58, 0.42, 0.09, cuts=4)
    bevel(sl, 0.05, 4, 30)
    subdivide(sl, 1)
    smooth(sl)
    assign(sl, bm_.mat)
    sl.rotation_euler = (0, math.radians(8), 0)
    sl.location = (0.70, 0.0, 0.0)
    curl = BK.butter_curl("ButterCurl", 0.42, 0.16, 1.35)
    curl.rotation_euler = (0, 0, math.radians(-48))
    curl.location = (0.0, -0.02, 0.51 + 0.16 + 0.012)
    apply_transform(curl)
    cm = Sh("ButterCurlMat", rough=0.25, sss=0.6, sss_radius=(1.0, 0.8, 0.4), sss_scale=0.1, coat=0.4)
    _, _, cz = cm.xyz()
    cm.color(cm.ramp(cm.remap(cz, 0.5, 0.85, smooth=False), [(0.0, (1.0, 0.82, 0.36)), (1.0, (1.0, 0.95, 0.70))]))
    assign(curl, cm.mat)
    parts = [dish, block, sl, curl]
    steel = Sh("ButterKnife", rough=0.14, metal=1.0)
    steel.color((0.86, 0.87, 0.90))
    blade = MX.outline_slab("KnifeBlade", [(0.36 * math.cos(t) * (1 if math.cos(t) > 0 else 1.0), 0.06 * math.sin(t))
                                           for t in [2 * math.pi * k / 64 for k in range(64)]], 0.016, p=2.5, cuts=16)
    smooth(blade)
    assign(blade, steel.mat)
    handle = lathe_fn("KnifeHandle", lambda t: 0.045 * (1 - 0.2 * t) * (1 - ss(0.94, 1.0, t) * 0.4), 0.0, 0.5, 30, 24)
    to_axis_x(handle)
    handle.location.x = 0.34
    apply_transform(handle)
    smooth(handle)
    wood = Sh("KnifeWood", rough=0.4, coat=0.4)
    wood.color(wood.ramp(wood.noise(wood.mapping(None, scale=(0.5, 8, 8)), 3, 3),
                         [(0.3, (0.70, 0.44, 0.24)), (0.7, (0.56, 0.32, 0.16))]))
    assign(handle, wood.mat)
    smear = sphere("KnifeSmear", 1.0, 32, 16)
    smear.scale = (0.16, 0.045, 0.018)
    smear.location = (-0.12, 0.0, 0.012)
    apply_transform(smear)
    push_normals(smear, lambda co, n: 0.006 * fbm(co * 20))
    smooth(smear)
    assign(smear, bm_.mat)
    kn = [blade, handle, smear]
    rotate_all(kn, (math.radians(-6), math.radians(-4), math.radians(-24)))
    for o in kn:
        o.location += Vector((-0.38, -0.56, 0.17))
    parts += kn
    return rotate_all(parts, (0, 0, math.radians(18)))


# MARK: - Маршмеллоу

def mallow_sh(name, lo, hi, twist=None):
    sh = Sh(name, rough=0.6, sss=0.8, sss_radius=(1.0, 0.9, 0.85), sss_scale=0.12, sheen=0.7, sheen_rough=0.4,
            coat=0.08, coat_rough=0.3)
    x, y, z = sh.xyz()
    col = sh.ramp(sh.remap(z, -0.25, 0.25, smooth=False), [(0.0, lo), (1.0, hi)])
    if twist:
        ang = sh.math("ARCTAN2", y, x)
        st = sh.math("SINE", sh.math("ADD", sh.math("MULTIPLY", ang, 2.0), sh.math("MULTIPLY", z, 14.0)))
        col = sh.mix(sh.remap(st, -0.15, 0.15), col, twist)
    dust = sh.math("MAXIMUM", sh.remap(sh.noise(None, 7, 5, 0.6), 0.58, 0.72, 0.0, 0.6),
                   sh.remap(sh.voronoi(None, 60, "F1"), 0.1, 0.04, 0.0, 0.5))
    col = sh.mix(dust, col, (1.0, 1.0, 1.0))
    sh.color(col)
    sh.set("Roughness", sh.remap(dust, 0.0, 1.0, 0.5, 0.9, smooth=False))
    sh.bump(sh.noise(None, 50, 3), 0.08, 0.003)
    sh.bump(dust, 0.08, 0.003)
    return sh.mat


def marshmallow():
    """Горстка маршмеллоу: мягкие розовые и белые цилиндрики в крахмальной пудре."""
    white = mallow_sh("MallowWhite", (0.90, 0.89, 0.93), (1.0, 0.99, 0.97))
    pink = mallow_sh("MallowPink", (0.97, 0.60, 0.72), (1.0, 0.78, 0.85))
    specs = [(white, (-0.30, 0.12), (0, 0, 0.3)), (pink, (0.28, 0.18), (0, 0, 1.1)),
             (white, (0.0, -0.40), (0, math.radians(90), math.radians(-8))),
             (pink, (0.0, 0.15), (0, math.radians(90), math.radians(18))),
             (white, (0.66, -0.44), (0, math.radians(90), math.radians(-40)))]
    pieces = []
    for i, (mt, (x, y), rot) in enumerate(specs):
        m = rounded_disc(f"Mallow{i}", 0.26, 0.44, 4.2, 22)
        off = Vector((i * 1.3, 0, 0))
        push_normals(m, lambda co, n: 0.012 * fbm(co * 4 + off))
        subdivide(m, 1)
        smooth(m)
        assign(m, mt)
        m.rotation_euler = rot
        m.location = (x, y, 2.5)
        bpy.context.view_layer.update()
        if pieces:
            MX.drop([m], pieces, floor=0.0, step=0.008, top=2.0)
        else:
            MX.ground([m], 0.0)
        pieces.append(m)
    return rotate_all(pieces, (0, 0, math.radians(-10)))


# MARK: - Мадлен

def madeleine2(name, ridged, L=0.68, W=0.54, H=0.2, seed=0.0):
    """Мадлен: ракушка с бороздками-лучами или горбик сверху и румяный край."""
    ob = quad_sphere(name, 52)
    hy = -0.95 * L
    N = 40

    def shape(co):
        x, y, z = co.x, co.y, co.z
        w = W * (0.50 + 0.50 * (y + 1) / 2)
        X, Y = x * w, y * L
        dy = Y - hy
        phi = math.atan2(X, dy)
        lobe = 1 + 0.025 * math.cos(N * phi) * ss(0.4, 0.8, (y + 1) / 2)
        X, Y = X * lobe, hy + dy * lobe
        if z > 0:
            Z = z * H
            if ridged:
                rib = 0.5 + 0.5 * math.cos(N * phi)
                Z += 0.04 * rib * ss(0.08, 0.35, math.hypot(X, dy)) * min(1.0, z * 3) ** 0.6
            else:
                Z = z * H * 0.8 + 0.16 * math.exp(-((X / 0.20) ** 2 + ((Y + 0.05) / 0.26) ** 2)) * min(1.0, z * 2.5)
        else:
            Z = z * H * 0.35
        return Vector((X, Y, Z + H * 0.35))
    deform(ob, shape)
    subdivide(ob, 1)
    push_normals(ob, lambda co, n: 0.004 * fbm(co * 8 + Vector((seed, 0, 0))))
    smooth(ob)

    def valley(co):
        dy = co.y - hy
        phi = math.atan2(co.x, dy)
        return (0.5 - 0.5 * math.cos(N * phi)) * ss(0.08, 0.35, math.hypot(co.x, dy)) if ridged else 0.0
    EV.set_attr(ob, "valley", lambda co, n: valley(co))
    sh = Sh(name + "Mat", rough=0.38, sss=0.3, sss_radius=(1.0, 0.6, 0.3), coat=0.45, coat_rough=0.12)
    x, y, z = sh.xyz()
    _, _, nz = sh.xyz("Normal")
    if ridged:
        col = sh.ramp(sh.remap(nz, -1, 1, smooth=False), [(0.0, (0.74, 0.40, 0.12)), (0.5, (0.90, 0.56, 0.20)),
                                                          (0.8, (0.98, 0.72, 0.32)), (1.0, (1.0, 0.80, 0.42))])
        col = sh.mix(sh.math("MULTIPLY", sh.attr("valley"), 0.8), col, (0.78, 0.42, 0.13))
    else:
        rr = sh.vmath("LENGTH", sh.combine(sh.math("DIVIDE", x, W), sh.math("DIVIDE", sh.math("ADD", y, 0.05), L), 0.0))
        col = sh.ramp(sh.math("ADD", rr, sh.math("MULTIPLY", sh.math("SUBTRACT", sh.noise(None, 4, 3), 0.5), 0.25)),
                      [(0.0, (1.0, 0.86, 0.54)), (0.45, (0.99, 0.78, 0.42)), (0.75, (0.88, 0.52, 0.18)),
                       (0.95, (0.70, 0.36, 0.10))])
        col = sh.mix(sh.remap(nz, 0.3, -0.2), col, (0.74, 0.40, 0.12))
    sh.color(col)
    sh.bump(sh.noise(None, 26, 4), 0.1, 0.004)
    sh.bump(sh.voronoi(None, 60, "F1"), 0.08, 0.002, invert=True)
    return assign(ob, sh.mat)


def madeleine():
    """Две мадлен: одна лежит горбиком вверх с румяным краем, вторая прислонена ракушкой с бороздками к камере."""
    a = madeleine2("MadHump", False, seed=0.0)
    a.rotation_euler = (math.radians(52), 0, math.radians(-22))
    a.location = (-0.40, -0.36, 0.4)
    b = madeleine2("MadShell", True, seed=1.0)
    b.rotation_euler = (math.radians(64), 0, math.radians(16))
    b.location = (0.30, 0.25, 0.40)
    bpy.context.view_layer.update()
    MX.ground([a], 0.0)
    MX.ground([b], 0.0)
    MX.nudge([b], [a], (0.5, 1, 0), 0.01)
    return rotate_all([a, b], (math.radians(6), 0, math.radians(-6)))


M.MODELS.update({
    "sugar": sugar,
    "cream": cream,
    "butter": butter,
    "marshmallow": marshmallow,
    "madeleine": madeleine,
})
