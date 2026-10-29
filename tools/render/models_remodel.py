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
                     (0.56, (1.0, 0.86, 0.60)), (0.68, (0.96, 0.64, 0.28)), (0.85, (0.86, 0.48, 0.17)),
                     (1.0, (0.80, 0.42, 0.14))])
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
