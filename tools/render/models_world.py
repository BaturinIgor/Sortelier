"""Кухни 6-10 (Китай, Индия, Корея, Испания, Греция): ингредиенты, закуски и блюда.

Модели собраны из тех же помощников, что и models.py; общие для кухонь заготовки (миска, стакан, банка,
тарелка с горкой, россыпь деталей) - в начале файла.
"""
import math
import random

import bpy
from mathutils import Vector

import models as M
from models import *  # noqa: F401,F403  помощники


# MARK: - Помощники

def grad(name, lo_c, hi_c, coord="z", lo=0.0, hi=1.0, **kw):
    """Материал с двухцветным градиентом."""
    return material(name, [(0.0, lo_c), (1.0, hi_c)], coord=coord, lo=lo, hi=hi, **kw)


def ball(name, r, loc, mat, scale=(1, 1, 1), segs=32, rings=20, rot=(0, 0, 0)):
    ob = sphere(name, r, segs, rings)
    ob.scale = scale
    ob.rotation_euler = rot
    ob.location = loc
    apply_transform(ob)
    return assign(smooth(ob), mat)


def rod(name, pts, r, mat, taper=(1.0, 1.0)):
    return assign(smooth(tube(name, pts, r, taper)), mat)


def lathe_obj(name, prof, mat, segs=72, sub=1, sharp=50):
    ob = lathe(name, prof, segs)
    if sub:
        subdivide(ob, sub)
    smooth(ob, sharp)
    return assign(ob, mat)


def disc(name, r, z, mat, h=0.04, segs=72, wobble=0.0, seed=0.0):
    ob = cylinder(name, r, h, segs)
    ob.location = (0, 0, z)
    apply_transform(ob)
    if wobble:
        push_normals(ob, lambda co, n: wobble * fbm(co * 6 + Vector((seed, 0, 0))) if n.z > 0.5 else 0.0)
    return assign(smooth(ob, 50), mat)


def bowl(name, r=1.0, h=0.62, outer=((0.92, 0.92, 0.94), (1.0, 1.0, 1.0)), band=None, foot=True):
    """Миска: профиль от ножки к краю. Возвращает (объект, высота края)."""
    prof = [(0.0, 0.0), (r * 0.42, 0.0), (r * 0.46, 0.06)] if foot else [(0.0, 0.0), (r * 0.5, 0.0)]
    prof += [(r * 0.52, 0.1), (r * 0.9, h * 0.68), (r, h), (r * 0.95, h + 0.02), (r * 0.86, h * 0.7), (0.0, h * 0.5)]
    stops = [(0.0, outer[0]), (1.0, outer[1])]
    if band:
        stops = [(0.0, outer[0]), (0.7, outer[1]), (0.72, band), (0.86, band), (0.88, outer[1]), (1.0, outer[1])]
    ob = lathe_obj(name, prof, material(name + "Mat", stops, coord="z", lo=0.0, hi=h, rough=0.18, coat=0.7))
    return ob, h


def glass_cup(name, r0, r1, h, tint=(0.95, 0.98, 1.0)):
    """Прозрачный стакан без дна внутри: содержимое видно через стенку."""
    prof = [(0.0, 0.0), (r0, 0.0), (r0 + 0.01, 0.05), (r1, h), (r1 - 0.03, h), (r0 - 0.03, 0.06), (0.0, 0.06)]
    mat = grad(name + "Mat", tint, (1.0, 1.0, 1.0), lo=0.0, hi=h, rough=0.02, transmission=1.0, coat=0.5)
    return lathe_obj(name, prof, mat, 72, 1, 60)


def liquid(name, r0, r1, z0, z1, mat, segs=72):
    """Содержимое стакана: усеченный конус от z0 до z1 (радиусы стакана в начале и конце)."""
    prof = [(0.0, z0), (r0, z0), (r1, z1), (0.0, z1)]
    return lathe_obj(name, prof, mat, segs, 1, 60)


def straw(name, x, y, z0, z1, color, lean=12, stripes=None):
    a = math.radians(lean)
    pts = [(x, y, z0), (x + math.sin(a) * (z1 - z0), y, z1)]
    mat = flat(name + "Mat", color, rough=0.3, coat=0.5)
    if stripes:
        add_stripes(mat, stripes, scale=6, angle=40, width=0.3, nz_min=-1.0, strength=1.0)
    return rod(name, pts, 0.06, mat)


def mound(name, r, h, mat, z=0.0, p=2.2, bumps=0.03, seed=0.0, squash=(1.0, 1.0)):
    """Горка (рис, начинка) на тарелке или в миске."""
    ob = sphere(name, 1.0, 64, 32)

    def shape(co):
        zz = max(0.0, co.z)
        rr = math.hypot(co.x, co.y)
        k = (1 - zz ** p) ** (1 / p) if zz < 1 else 0.0
        k = max(k, 0.0)
        d = rr if rr > 1e-6 else 1.0
        return Vector((co.x / d * k * r * squash[0] if rr > 1e-6 else 0.0,
                       co.y / d * k * r * squash[1] if rr > 1e-6 else 0.0, z + zz * h))
    deform(ob, shape)
    if bumps:
        push_normals(ob, lambda co, n: bumps * fbm(co * 7 + Vector((seed, seed, 0))))
    return assign(smooth(ob), mat)


def sprinkle(target_objs, count, make, seed, area, zmin=-1e9, spacing=0.0):
    """Россыпь деталей по самому верхнему объекту из target_objs."""
    return scatter_on(target_objs, count, make, seed=seed, area=area, zmin=zmin, spacing=spacing)


def grain(mat, size=0.03, stretch=2.2):
    def make(i, rnd):
        g = sphere(f"G{mat.name}{i}", size, 10, 6)
        g.scale = (1.0, 1.0, stretch)
        g.rotation_euler = (rnd.uniform(0, 3), rnd.uniform(0, 3), 0)
        apply_transform(g)
        return assign(smooth(g), mat)
    return make


def leaf_blob(name, rx, ry, mat, loc, rot, cup=0.15, ruffle=0.02):
    ob = polar_disc(name, 14, 72, rx, ry)

    def shape(co):
        r2 = (co.x / rx) ** 2 + (co.y / ry) ** 2
        a = math.atan2(co.y, co.x)
        return Vector((co.x, co.y, cup * r2 + ruffle * math.sin(a * 11) * r2))
    deform(ob, shape)
    solidify(ob, 0.02)
    ob.location = loc
    ob.rotation_euler = rot
    apply_transform(ob)
    return assign(smooth(ob), mat)


def chopsticks(z, color=(0.62, 0.28, 0.14), x=0.35, y=0.05, yaw=-28):
    mat = flat("Sticks" + str(z), color, rough=0.35, coat=0.5)
    out = []
    for i, dy in enumerate((-0.05, 0.05)):
        cs = capsule(f"Chop{z}{i}", 2.0, 0.03, 16, 12)
        cs.rotation_euler = (0, math.radians(-8), math.radians(yaw + i * 4))
        cs.location = (x, y + dy, z)
        apply_transform(cs)
        out.append(assign(smooth(cs), mat))
    return out


def jar(name, r, h, glass=(0.96, 0.98, 1.0), lid=(0.85, 0.1, 0.08), label=(0.98, 0.95, 0.86)):
    """Пузатая банка с крышкой и этикеткой. Возвращает части; содержимое кладет вызывающий."""
    body = lathe_obj(name, [(0.0, 0.0), (r * 0.9, 0.0), (r, 0.08), (r * 1.02, h * 0.5), (r, h * 0.9), (r * 0.82, h),
                            (0.0, h)], grad(name + "Glass", glass, (1, 1, 1), hi=h, rough=0.04, transmission=0.9, coat=0.6))
    cap = lathe_obj(name + "Lid", [(0.0, h - 0.02), (r * 0.86, h - 0.02), (r * 0.9, h + 0.04), (r * 0.88, h + 0.2),
                                   (0.0, h + 0.22)], grad(name + "LidMat", tuple(c * 0.8 for c in lid), lid, lo=h, hi=h + 0.22,
                                                          rough=0.2, coat=0.6))
    lab = lathe_obj(name + "Label", [(r * 1.025, h * 0.3), (r * 1.035, h * 0.32), (r * 1.035, h * 0.62),
                                     (r * 1.025, h * 0.64)], flat(name + "LabelMat", label, rough=0.4), 72, 0)
    return [body, cap, lab]


def plate_round(name="Plate", r=1.2, color=(0.97, 0.97, 0.98), rim=None):
    stops = [(0.0, color), (1.0, color)] if not rim else [(0.0, color), (0.8, color), (0.85, rim), (1.0, rim)]
    ob = lathe(name, [(0.0, 0.0), (r * 0.62, 0.0), (r * 0.66, 0.03), (r * 0.7, 0.07), (r * 0.98, 0.16), (r, 0.2),
                      (r * 0.96, 0.21), (r * 0.68, 0.1), (0.0, 0.09)], 96)
    subdivide(ob, 1)
    smooth(ob, 50)
    return assign(ob, material(name + "Mat", stops, coord="r", lo=0.0, hi=r, rough=0.15, coat=0.8))


def steamer(name, r=1.0, h=0.5):
    """Бамбуковая корзинка для димсамов."""
    wood = grad(name + "Bamboo", (0.72, 0.52, 0.28), (0.92, 0.76, 0.46), lo=0.0, hi=h, rough=0.5, coat=0.2, vary=0.15)
    add_stripes(wood, (0.62, 0.42, 0.20), scale=6, angle=0, width=0.12, nz_min=-1.0, strength=0.6)
    ring = lathe_obj(name, [(0.0, 0.0), (r, 0.0), (r * 1.02, 0.04), (r * 1.02, h), (r * 0.94, h), (r * 0.94, 0.08),
                            (0.0, 0.08)], wood, 96, 1, 40)
    return ring, h


def bottle(name, r, h, neck, mat_body, mat_cap):
    body = lathe_obj(name, [(0.0, 0.0), (r * 0.9, 0.0), (r, 0.06), (r, h * 0.62), (neck * 1.2, h * 0.86), (neck, h * 0.92),
                            (neck, h), (0.0, h)], mat_body)
    cap = lathe_obj(name + "Cap", [(0.0, h - 0.01), (neck * 1.15, h - 0.01), (neck * 1.2, h + 0.04),
                                   (neck * 1.15, h + 0.14), (0.0, h + 0.15)], mat_cap)
    return [body, cap]


def tilt(objs, x=-12, z=0):
    return rotate_all(objs, (math.radians(x), 0, math.radians(z)))


# MARK: - Китайская кухня (биом 6)

def soybeans():
    """Горсть соевых бобов в деревянной мерке."""
    scoop = lathe_obj("SoyScoop", [(0.0, 0.0), (0.62, 0.0), (0.7, 0.05), (0.85, 0.42), (0.8, 0.44), (0.62, 0.1),
                                   (0.0, 0.1)], grad("SoyScoopWood", (0.58, 0.36, 0.18), (0.80, 0.56, 0.30), hi=0.45,
                                                     rough=0.45, coat=0.3, vary=0.2))
    bean = grad("SoyBean", (0.86, 0.72, 0.42), (0.98, 0.88, 0.60), coord="nz", lo=-1, hi=1, rough=0.25, sss=0.3, coat=0.6)
    hilum = flat("SoyHilum", (0.55, 0.38, 0.22), rough=0.4)
    rnd = random.Random(6)
    parts = [scoop]
    pts = []
    for ring_n, rr, z in ((1, 0.0, 0.2), (6, 0.3, 0.2), (11, 0.6, 0.3), (6, 0.32, 0.36), (1, 0.0, 0.42)):
        for i in range(ring_n):
            a = 2 * math.pi * i / max(1, ring_n) + rnd.uniform(-0.2, 0.2)
            pts.append((rr * math.cos(a), rr * math.sin(a), z + rnd.uniform(-0.02, 0.03)))
    for i, (x, y, z) in enumerate(pts):
        rot = (rnd.uniform(0, 3), rnd.uniform(0, 3), rnd.uniform(0, 3))
        parts.append(ball(f"Bean{i}", 0.15, (x, y, z), bean, (1.0, 0.82, 0.78), 24, 14, rot))
    parts.append(ball("BeanTop", 0.15, (0.38, 0.65, 0.05), bean, (1.0, 0.82, 0.78), 24, 14))
    parts.append(ball("BeanTopH", 0.05, (0.38, 0.52, 0.06), hilum, (1.2, 0.4, 0.6), 12, 8))
    return tilt(parts, -14, -10)


def tofu():
    """Кубики тофу: белые, чуть пористые, с каплей соуса."""
    mat = grad("TofuMat", (0.92, 0.90, 0.82), (1.0, 0.99, 0.94), lo=0.0, hi=0.9, rough=0.35, sss=0.6,
               sss_radius=(1, 0.95, 0.8), bump=0.2, bump_scale=40)
    parts = []
    from models_mexico import rcube
    for i, (x, y, z, rz) in enumerate(((-0.42, 0.0, 0.0, 8), (0.42, 0.05, 0.0, -10), (0.0, -0.05, 0.62, 18))):
        c = rcube(f"Tofu{i}", 0.4, 0.4, 0.3, 6.0, 8)
        c.location = (x, y, z + 0.3)
        c.rotation_euler = (0, 0, math.radians(rz))
        apply_transform(c)
        parts.append(assign(c, mat))
    leek = flat("TofuLeek", (0.45, 0.78, 0.28), rough=0.3, coat=0.4)
    for i, (x, y) in enumerate(((-0.08, -0.12), (0.12, 0.08))):
        r = torus(f"TofuRing{i}", 0.06, 0.02, 24, 10)
        r.location = (x, y, 1.23)
        apply_transform(r)
        parts.append(assign(smooth(r), leek))
    return tilt(parts, -8, 15)


def noodles():
    """Пучок сухой лапши, перевязанный бумажной лентой."""
    mat = grad("NoodleDry", (0.96, 0.84, 0.52), (1.0, 0.93, 0.70), coord="z", lo=-1, hi=1, rough=0.3, sss=0.4, coat=0.4)
    parts = []
    rnd = random.Random(3)
    for i in range(46):
        a = rnd.uniform(0, 2 * math.pi)
        r = 0.32 * math.sqrt(rnd.random())
        x, y = r * math.cos(a), r * math.sin(a)
        wave = rnd.uniform(0, 6)
        pts = [(x + 0.03 * math.sin(t * 9 + wave) * (1 - abs(t)), y + 0.03 * math.cos(t * 7 + wave), t * 0.95)
               for t in [k / 20 - 0.5 for k in range(21)]]
        pts = [(px * (1 - 0.35 * math.exp(-(pz / 0.18) ** 2)), py * (1 - 0.35 * math.exp(-(pz / 0.18) ** 2)), pz)
               for px, py, pz in pts]
        parts.append(rod(f"Nd{i}", pts, 0.028, mat))
    band = lathe_obj("NoodleBand", [(0.24, -0.1), (0.26, -0.09), (0.26, 0.09), (0.24, 0.1)],
                     flat("NoodleBandMat", (0.86, 0.12, 0.10), rough=0.35, coat=0.3), 72, 0)
    parts.append(band)
    rotate_all(parts, (0, math.radians(78), math.radians(-20)))
    return ground_all(parts)


def bok_choy():
    stalk = grad("BokStalk", (0.90, 0.96, 0.84), (0.72, 0.90, 0.56), lo=0.0, hi=1.4, rough=0.3, sss=0.5, coat=0.5)
    leafm = grad("BokLeaf", (0.30, 0.62, 0.20), (0.18, 0.46, 0.12), lo=0.8, hi=2.0, rough=0.35, sss=0.4, coat=0.4,
                 bump=0.15, bump_scale=10)
    parts = []
    for i in range(7):
        a = 2 * math.pi * i / 7
        lean = 0.12 + 0.08 * (i % 2)
        st = capsule(f"BokSt{i}", 1.3, 0.16, 32, 20)
        st.scale = (1.0, 1.0, 0.55)
        st.rotation_euler = (0, math.radians(-90 + 0), 0)
        apply_transform(st)
        st.rotation_euler = (lean * math.sin(a) * 2, -lean * math.cos(a) * 2, a)
        st.location = (0.1 * math.cos(a), 0.1 * math.sin(a), 0.65)
        apply_transform(st)
        parts.append(assign(smooth(st), stalk))
        lf = sphere(f"BokLf{i}", 1.0, 32, 20)
        lf.scale = (0.42, 0.13, 0.55)
        lf.rotation_euler = (lean * math.sin(a) * 2.6, -lean * math.cos(a) * 2.6, a + math.pi / 2)
        lf.location = (0.32 * math.cos(a), 0.32 * math.sin(a), 1.55)
        apply_transform(lf)
        push_normals(lf, lambda co, n: 0.02 * fbm(co * 8))
        parts.append(assign(smooth(lf), leafm))
    return tilt(parts, -6)


def shrimp():
    """Креветка запятой: сегменты панциря, хвост веером."""
    shell = grad("ShrimpShell", (1.0, 0.50, 0.30), (1.0, 0.72, 0.52), coord="nz", lo=-1, hi=1, rough=0.2, sss=0.5,
                 coat=0.8)
    add_stripes(shell, (1.0, 0.90, 0.80), scale=3.5, angle=90, width=0.14, nz_min=-1.0, strength=0.7)
    parts = []
    n = 9
    for i in range(n):
        t = i / (n - 1)
        a = math.radians(200 * t - 20)
        R = 0.62
        r = 0.30 * (1 - 0.6 * t) + 0.03
        parts.append(ball(f"Seg{i}", r, (R * math.cos(a), 0, R * math.sin(a) + 0.7), shell, (1.0, 0.9, 1.0), 32, 20))
    tail = flat("ShrimpTail", (0.96, 0.36, 0.18), rough=0.2, coat=0.8)
    a = math.radians(185)
    for k, ang in enumerate((-30, 0, 30)):
        parts.append(ball(f"Tail{k}", 0.2, (0.62 * math.cos(a) - 0.12, 0.08 * (k - 1), 0.62 * math.sin(a) + 0.62),
                          tail, (0.5, 0.25, 1.0), 20, 12, (math.radians(ang), 0, 0)))
    eye = flat("ShrimpEye", (0.1, 0.06, 0.05), rough=0.1, coat=1.0)
    parts.append(ball("Eye", 0.05, (0.66, -0.2, 0.62), eye))
    return tilt(parts, 0, 0)


def ginger():
    """Корень имбиря: несколько шишковатых долей и срез."""
    skin = grad("GingerSkin", (0.78, 0.60, 0.34), (0.92, 0.78, 0.50), lo=-0.4, hi=0.6, rough=0.55, coat=0.2,
                bump=0.3, bump_scale=14, vary=0.15)
    add_stripes(skin, (0.66, 0.48, 0.26), scale=7, angle=0, width=0.06, nz_min=-1.0, strength=0.5)
    flesh = flat("GingerFlesh", (0.99, 0.88, 0.52), rough=0.35, sss=0.5, coat=0.3)
    parts = []
    lobes = [((0, 0, 0), (0.55, 0.32, 0.30), 0), ((0.5, 0.05, 0.12), (0.34, 0.26, 0.24), 30),
             ((-0.45, 0.02, 0.18), (0.32, 0.25, 0.26), -40), ((0.12, 0.0, 0.42), (0.22, 0.2, 0.28), 10),
             ((0.82, 0.08, 0.32), (0.2, 0.18, 0.2), 50)]
    for i, (loc, sc, rot) in enumerate(lobes):
        ob = ball(f"Gin{i}", 1.0, loc, skin, sc, 40, 24, (0, math.radians(rot), 0))
        push_normals(ob, lambda co, n: 0.03 * fbm(co * 4))
        parts.append(ob)
    cut = ball("GinCut", 1.0, (-0.74, 0.0, 0.26), flesh, (0.05, 0.22, 0.22), 32, 20)
    parts.append(cut)
    return tilt(ground_all(parts), -10, -15)


def ground_all(parts):
    bpy.context.view_layer.update()
    lo = min((o.matrix_world @ v.co).z for o in parts for v in o.data.vertices)
    for o in parts:
        o.location.z -= lo
    bpy.context.view_layer.update()
    return parts


def bao():
    """Паровая булочка баоцзы со складками на макушке."""
    ob = sphere("Bao", 0.8, 72, 48)

    def shape(co):
        a = math.atan2(co.y, co.x)
        zz = max(0.0, co.z / 0.8)
        pleat = 1 + 0.05 * math.cos(a * 14) * zz ** 2
        z = co.z * (0.78 if co.z > 0 else 0.35)
        z += 0.1 * zz ** 6
        return Vector((co.x * pleat, co.y * pleat, z))
    deform(ob, shape)
    smooth(ob)
    assign(ob, grad("BaoDough", (0.94, 0.92, 0.88), (1.0, 1.0, 0.98), lo=-0.3, hi=0.7, rough=0.45, sss=0.6,
                    sss_radius=(1, 0.95, 0.9), sheen=0.3))
    dot = flat("BaoDot", (0.92, 0.20, 0.22), rough=0.3, coat=0.4)
    return tilt([ob, ball("BaoDotO", 0.07, (0, 0, 0.73), dot, (1, 1, 0.4))], -8)


def spring_roll():
    """Две хрустящие спринг-роллы на листке салата."""
    crisp = grad("RollCrisp", (0.82, 0.50, 0.16), (0.98, 0.76, 0.36), coord="nz", lo=-1, hi=1, rough=0.45, coat=0.4,
                 bump=0.5, bump_scale=18)
    parts = []
    for i, (y, z, rz) in enumerate(((0.0, 0.25, 20), (0.25, 0.62, 5))):
        c = capsule(f"Roll{i}", 1.8, 0.27, 48, 32, pinch=0.4)
        c.rotation_euler = (0, 0, math.radians(rz))
        c.location = (0, y, z)
        apply_transform(c)
        push_normals(c, lambda co, n: 0.02 * fbm(co * 6))
        parts.append(assign(smooth(c), crisp))
    return tilt(parts, -16, -12)


def fortune_cookie():
    ob = polar_disc("Fortune", 24, 96, 0.8, 0.8)

    def shape(co):
        x, y = co.x, co.y
        # складываем круг пополам и сгибаем: края вверх, середина вдавлена
        z = 0.55 * (y / 0.8) ** 2 - 0.25 * math.exp(-(x / 0.25) ** 2) * (1 - (y / 0.8) ** 2)
        xx = x * (1 - 0.35 * abs(y) / 0.8)
        return Vector((xx, y * 0.6, z + 0.3 * abs(x) ** 1.5))
    deform(ob, shape)
    solidify(ob, 0.06)
    subdivide(ob, 1)
    smooth(ob)
    assign(ob, grad("FortuneMat", (0.90, 0.62, 0.24), (0.99, 0.84, 0.50), coord="z", lo=0.0, hi=0.6, rough=0.35, coat=0.5,
                    vary=0.2))
    paper = box_mesh("FortunePaper", 0.6, 0.02, 0.12, 0.0)
    paper.location = (0.55, 0.0, 0.18)
    paper.rotation_euler = (0, math.radians(-15), 0)
    apply_transform(paper)
    assign(paper, flat("FortunePaperMat", (1.0, 1.0, 0.98), rough=0.5))
    return tilt([ob, paper], -20, 10)


def bubble_tea():
    cup = glass_cup("BobaCup", 0.48, 0.6, 1.5)
    tea = liquid("BobaTea", 0.46, 0.56, 0.06, 1.3, grad("BobaTeaMat", (0.80, 0.56, 0.36), (0.94, 0.80, 0.62), lo=0.0,
                                                          hi=1.3, rough=0.1, sss=0.5, coat=0.6))
    pearl = flat("Pearl", (0.12, 0.07, 0.05), rough=0.05, coat=1.0)
    rnd = random.Random(2)
    parts = [cup, tea]
    for i in range(16):
        a = rnd.uniform(0, 2 * math.pi)
        r = 0.4
        parts.append(ball(f"Pearl{i}", 0.085, (r * math.cos(a), r * math.sin(a), 0.14 + 0.13 * (i // 6)), pearl, segs=16,
                          rings=10))
    lid = lathe_obj("BobaLid", [(0.0, 1.5), (0.62, 1.5), (0.63, 1.54), (0.5, 1.62), (0.0, 1.64)],
                    grad("BobaLidMat", (0.95, 0.97, 1.0), (1, 1, 1), lo=1.5, hi=1.64, rough=0.05, transmission=0.8))
    parts.append(lid)
    parts.append(straw("BobaStraw", 0.1, 0.0, 0.3, 2.2, (0.98, 0.42, 0.52), 10))
    return parts


def mooncake():
    """Лунный пряник: высокая шайба с рельефным цветком сверху и рифленым бортом."""
    ob = rounded_disc("Moon", 0.85, 0.55, 5.0, 32)

    def shape(co):
        a = math.atan2(co.y, co.x)
        r = math.hypot(co.x, co.y)
        k = 1 + 0.035 * math.cos(a * 16)
        z = co.z + 0.28
        if co.z > 0.2:
            z += 0.04 * math.cos(r * 18) * max(0.0, 1 - r / 0.62)
        return Vector((co.x * k, co.y * k, z))
    deform(ob, shape)
    smooth(ob)
    assign(ob, grad("MoonMat", (0.66, 0.36, 0.14), (0.90, 0.62, 0.30), coord="nz", lo=-0.2, hi=1.0, rough=0.35, coat=0.6,
                    vary=0.15))
    return tilt([ob], -18)


def tanghulu():
    """Засахаренные ягоды на шпажке."""
    glaze = grad("Tanghulu", (0.80, 0.06, 0.08), (1.0, 0.30, 0.26), coord="nz", lo=-1, hi=1, rough=0.02, coat=1.0,
                 coat_rough=0.01, sss=0.4)
    stick = flat("TangStick", (0.88, 0.74, 0.50), rough=0.5)
    parts = [rod("TangSk", [(0, 0, 0.0), (0, 0, 2.2)], 0.035, stick)]
    for i in range(4):
        b = ball(f"Haw{i}", 0.27, (0, 0, 0.55 + i * 0.45), glaze, (1, 1, 0.92), 40, 24)
        push_normals(b, lambda co, n: 0.012 * fbm(co * 9))
        parts.append(b)
    return rotate_all(parts, (0, math.radians(-18), 0))


def dish_mapo_tofu():
    b, h = bowl("MapoBowl", 1.0, 0.6, ((0.12, 0.12, 0.14), (0.24, 0.24, 0.28)))
    sauce = disc("MapoSauce", 0.94, h - 0.06, grad("MapoSauceMat", (0.70, 0.10, 0.04), (0.92, 0.28, 0.10), coord="r", hi=0.9,
                                                    rough=0.08, coat=0.9, sss=0.3), wobble=0.01)
    tofu_m = grad("MapoTofu", (0.94, 0.90, 0.78), (1.0, 0.98, 0.92), lo=h - 0.1, hi=h + 0.1, rough=0.3, sss=0.6)
    from models_mexico import rcube
    parts = [b, sauce]
    rnd = random.Random(4)
    for i in range(9):
        a = 2 * math.pi * i / 9 + rnd.uniform(-0.2, 0.2)
        r = 0.55 if i % 2 else 0.25
        c = rcube(f"MTofu{i}", 0.13, 0.13, 0.11, 6.0, 6)
        c.rotation_euler = (0, 0, rnd.uniform(0, 1.5))
        c.location = (r * math.cos(a), r * math.sin(a), h - 0.02)
        apply_transform(c)
        parts.append(assign(c, tofu_m))
    leek = flat("MapoLeek", (0.45, 0.80, 0.28), rough=0.3, coat=0.4)
    for i in range(7):
        a = rnd.uniform(0, 6.28)
        r = torus(f"MRing{i}", 0.05, 0.018, 20, 10)
        r.location = (rnd.uniform(0.1, 0.7) * math.cos(a), rnd.uniform(0.1, 0.7) * math.sin(a), h + 0.07)
        apply_transform(r)
        parts.append(assign(smooth(r), leek))
    return parts


def dish_fried_rice():
    p = plate_round("FRPlate", 1.2, (0.97, 0.97, 0.98), (0.20, 0.36, 0.72))
    rice_m = grad("FRRice", (0.92, 0.76, 0.42), (1.0, 0.90, 0.62), lo=0.1, hi=0.8, rough=0.4, sss=0.4, bump=0.6,
                  bump_scale=40)
    m = mound("FRMound", 0.85, 0.62, rice_m, z=0.08, bumps=0.04)
    parts = [p, m]
    egg = flat("FREgg", (1.0, 0.84, 0.25), rough=0.35, sss=0.3)
    pea = flat("FRPea", (0.40, 0.75, 0.25), rough=0.25, coat=0.6)
    carrot = flat("FRCarrot", (1.0, 0.52, 0.12), rough=0.3, coat=0.5)

    def make(i, rnd):
        kind = i % 3
        if kind == 0:
            g = sphere(f"FRe{i}", 0.07, 12, 8)
            g.scale = (1.2, 1.0, 0.6)
            apply_transform(g)
            return assign(smooth(g), egg)
        if kind == 1:
            return assign(smooth(sphere(f"FRp{i}", 0.05, 12, 8)), pea)
        g = box_mesh(f"FRc{i}", 0.08, 0.08, 0.08, -0.04)
        bevel(g, 0.015, 2)
        return assign(smooth(g), carrot)
    scatter_on(m, 36, make, seed=5, area=0.8, spacing=0.09)
    return parts + [o for o in bpy.data.objects if o.name.startswith(("FRe", "FRp", "FRc")) and o not in parts]


def dish_chow_mein():
    b, h = bowl("CMBowl", 1.0, 0.55, ((0.96, 0.96, 0.98), (1.0, 1.0, 1.0)), band=(0.82, 0.14, 0.12))
    noodle = grad("CMNoodle", (0.76, 0.48, 0.16), (0.94, 0.70, 0.34), lo=h - 0.1, hi=h + 0.3, rough=0.25, sss=0.4,
                  coat=0.6)
    parts = [b]
    rnd = random.Random(8)
    for i in range(22):
        a0 = rnd.uniform(0, 6.28)
        rr = rnd.uniform(0.1, 0.75)
        pts = []
        for k in range(30):
            t = k / 29
            a = a0 + t * rnd.uniform(1.2, 2.4)
            r = rr * (1 - 0.2 * t)
            pts.append((r * math.cos(a), r * math.sin(a), h + 0.04 + 0.25 * (1 - (r / 0.85) ** 2) + 0.04 * math.sin(t * 9)))
        parts.append(rod(f"CMn{i}", pts, 0.04, noodle))
    leaf = grad("CMBok", (0.28, 0.60, 0.20), (0.50, 0.82, 0.32), lo=h, hi=h + 0.4, rough=0.3, coat=0.4, sss=0.3)
    stalk = flat("CMBokSt", (0.86, 0.95, 0.76), rough=0.3, sss=0.4)
    for i, (x, y, rz) in enumerate(((0.35, -0.3, 30), (-0.4, 0.15, -50))):
        parts.append(leaf_blob(f"CMLf{i}", 0.32, 0.18, leaf, (x, y, h + 0.3), (math.radians(-20), 0, math.radians(rz))))
        parts.append(ball(f"CMSt{i}", 0.2, (x + 0.12, y - 0.05, h + 0.26), stalk, (1.0, 0.45, 0.3), 24, 12,
                          (0, 0, math.radians(rz))))
    parts += chopsticks(h + 0.42)
    return parts


def dish_dim_sum():
    s, h = steamer("DSSteamer", 1.0, 0.45)
    paper = disc("DSPaper", 0.92, 0.1, flat("DSPaperMat", (0.98, 0.95, 0.86), rough=0.6), h=0.02)
    wrap = grad("DSWrap", (0.94, 0.90, 0.86), (1.0, 0.98, 0.96), lo=0.1, hi=0.6, rough=0.15, sss=0.8,
                sss_radius=(1, 0.6, 0.5), coat=0.6)
    fill = flat("DSFill", (1.0, 0.62, 0.50), rough=0.3)
    parts = [s, paper]
    for i, (x, y) in enumerate(((-0.4, -0.3), (0.4, -0.3), (0.0, 0.38), (0.0, -0.05))):
        d = sphere(f"DS{i}", 0.32, 48, 32)

        def shape(co):
            a = math.atan2(co.y, co.x)
            zz = co.z / 0.32
            pleat = 1 + 0.06 * math.cos(a * 10) * max(0, zz) ** 2
            return Vector((co.x * pleat, co.y * pleat, (co.z * (1.1 if co.z > 0 else 0.4)) + 0.4))
        deform(d, shape)
        d.location = (x, y, 0.0 if i < 3 else 0.12)
        apply_transform(d)
        parts.append(assign(smooth(d), wrap))
        parts.append(ball(f"DSf{i}", 0.08, (x, y, 0.76 + (0.12 if i == 3 else 0)), fill, (1, 1, 0.5), 16, 10))
    return parts


def dish_hot_pot():
    pot = lathe_obj("HPPot", [(0.0, 0.0), (0.9, 0.0), (1.0, 0.08), (1.05, 0.5), (1.1, 0.56), (1.02, 0.58), (0.95, 0.4), (0.0, 0.3)],
                    grad("HPPotMat", (0.45, 0.46, 0.50), (0.80, 0.82, 0.86), lo=0.0, hi=0.58, rough=0.2, metal=0.8))
    divider = box_mesh("HPDiv", 1.96, 0.04, 0.5, 0.05)
    assign(divider, flat("HPDivMat", (0.72, 0.74, 0.78), rough=0.2, metal=0.8))
    red = grad("HPRed", (0.72, 0.08, 0.04), (0.94, 0.26, 0.10), coord="r", hi=1.0, rough=0.05, coat=0.9)
    white = grad("HPWhite", (0.96, 0.88, 0.70), (1.0, 0.96, 0.86), coord="r", hi=1.0, rough=0.05, coat=0.9, sss=0.4)
    broth_r = disc("HPBrothR", 0.98, 0.48, red)
    bisect(broth_r, (0, 0, 0), (0, -1, 0))
    broth_w = disc("HPBrothW", 0.98, 0.48, white)
    bisect(broth_w, (0, 0, 0), (0, 1, 0))
    parts = [pot, divider, broth_r, broth_w]
    chili = flat("HPChili", (0.85, 0.05, 0.04), rough=0.2, coat=0.8)
    shroom = grad("HPShroom", (0.55, 0.36, 0.20), (0.80, 0.62, 0.40), lo=0.45, hi=0.62, rough=0.3, coat=0.4)
    tofu_m = flat("HPTofu", (1.0, 0.98, 0.92), rough=0.3, sss=0.6)
    shrimp_m = grad("HPShrimp", (1.0, 0.45, 0.28), (1.0, 0.70, 0.52), coord="nz", lo=-1, hi=1, rough=0.2, coat=0.7)
    from models_mexico import rcube
    for i, (x, y) in enumerate(((-0.5, 0.5), (0.3, 0.6), (-0.1, 0.3))):
        parts.append(ball(f"HPc{i}", 0.08, (x, y, 0.53), chili, (2.0, 0.6, 0.6), 16, 10, (0, 0, i)))
    for i, (x, y) in enumerate(((0.45, -0.45), (-0.35, -0.55))):
        c = rcube(f"HPt{i}", 0.14, 0.14, 0.09, 6.0, 6)
        c.location = (x, y, 0.53)
        apply_transform(c)
        parts.append(assign(c, tofu_m))
    for i, (x, y) in enumerate(((0.6, 0.3), (-0.6, -0.2), (0.05, -0.3))):
        parts.append(ball(f"HPm{i}", 0.13, (x, y, 0.53), shroom, (1, 1, 0.5), 24, 12))
    for i, (x, y) in enumerate(((0.05, 0.7), (0.65, -0.1))):
        t = torus(f"HPs{i}", 0.12, 0.06, 24, 12)
        bisect(t, (0, 0, 0), (-1, 0, 0))
        t.location = (x, y, 0.54)
        apply_transform(t)
        parts.append(assign(smooth(t), shrimp_m))
    return parts


M.MODELS.update({
    "soybeans": soybeans, "tofu": tofu, "noodles": noodles, "bok_choy": bok_choy, "shrimp": shrimp, "ginger": ginger,
    "bao": bao, "spring_roll": spring_roll, "fortune_cookie": fortune_cookie, "bubble_tea": bubble_tea,
    "mooncake": mooncake, "tanghulu": tanghulu,
    "dish_mapo_tofu": dish_mapo_tofu, "dish_fried_rice": dish_fried_rice, "dish_chow_mein": dish_chow_mein,
    "dish_dim_sum": dish_dim_sum, "dish_hot_pot": dish_hot_pot,
})


# MARK: - Индийская кухня (биом 7)

def copper_bowl(name, r=1.0, h=0.55):
    mat = grad(name + "Cu", (0.62, 0.30, 0.14), (0.95, 0.60, 0.36), lo=0.0, hi=h, rough=0.22, metal=0.85, coat=0.3)
    ob = lathe_obj(name, [(0.0, 0.0), (r * 0.5, 0.0), (r * 0.56, 0.06), (r * 0.94, h * 0.6), (r, h), (r * 1.06, h + 0.03),
                          (r * 1.0, h + 0.06), (r * 0.9, h * 0.75), (0.0, h * 0.5)], mat)
    return ob, h


def curry_in(name, r, z, c_lo, c_hi):
    return disc(name, r, z, grad(name + "Mat", c_lo, c_hi, coord="r", hi=r, rough=0.1, coat=0.8, sss=0.4,
                                  bump=0.15, bump_scale=8), wobble=0.012)


def chicken():
    """Жареная куриная ножка."""
    meat = grad("ChickMeat", (0.70, 0.34, 0.10), (0.96, 0.62, 0.26), coord="nz", lo=-0.6, hi=1.0, rough=0.35, coat=0.6,
                bump=0.35, bump_scale=10, vary=0.25)
    bone = grad("ChickBone", (0.92, 0.88, 0.78), (1.0, 0.98, 0.92), coord="x", lo=0.3, hi=1.2, rough=0.35, sss=0.3)
    drum = sphere("Drum", 1.0, 64, 40)

    def shape(co):
        t = (co.x + 1) / 2  # 0 у толстого конца
        k = 0.55 * (1 - 0.62 * t ** 1.6)
        return Vector((co.x * 0.75, co.y * k, co.z * k * 0.9))
    deform(drum, shape)
    push_normals(drum, lambda co, n: 0.025 * fbm(co * 5))
    assign(smooth(drum), meat)
    shaft = rod("Bone", [(0.55, 0, 0), (1.05, 0, 0.0)], 0.07, bone)
    knob1 = ball("Knob1", 0.1, (1.08, 0.06, 0.0), bone)
    knob2 = ball("Knob2", 0.1, (1.08, -0.06, 0.0), bone)
    parts = [drum, shaft, knob1, knob2]
    rotate_all(parts, (0, math.radians(-22), math.radians(-25)))
    return ground_all(parts)


def paneer():
    """Брусок панира с полосками тандури."""
    from models_mexico import rcube
    blk = rcube("Paneer", 0.62, 0.42, 0.34, 7.0, 10)
    blk.location = (0, 0, 0.34)
    apply_transform(blk)
    mat = grad("PaneerMat", (0.96, 0.92, 0.80), (1.0, 0.98, 0.90), lo=0.0, hi=0.7, rough=0.4, sss=0.5, bump=0.2,
               bump_scale=30)
    add_stripes(mat, (0.86, 0.42, 0.12), scale=2.6, angle=35, width=0.16, nz_min=0.6, strength=0.85)
    assign(blk, mat)
    leaf = flat("PaneerLeaf", (0.30, 0.66, 0.22), rough=0.3, coat=0.4)
    l1 = leaf_blob("PanLeaf", 0.16, 0.1, leaf, (0.2, -0.05, 0.69), (0, 0, 0.6), cup=0.05)
    return tilt([blk, l1], -10, 18)


def spinach():
    """Горка листьев шпината."""
    mat = grad("Spinach", (0.10, 0.36, 0.10), (0.26, 0.62, 0.20), lo=0.0, hi=1.0, rough=0.3, coat=0.6, sss=0.3)
    vein = flat("SpinVein", (0.62, 0.84, 0.44), rough=0.3)
    parts = []
    rnd = random.Random(11)
    spots = [(0, 0, 0.55, 0), (0.4, 0.1, 0.35, 40), (-0.4, 0.05, 0.38, -40), (0.15, -0.3, 0.3, 80), (-0.2, 0.3, 0.42, 150),
             (0.25, 0.35, 0.3, 200), (-0.3, -0.3, 0.25, 260)]
    for i, (x, y, z, a) in enumerate(spots):
        lf = leaf_blob(f"Sp{i}", 0.5, 0.34, mat, (x, y, z), (math.radians(rnd.uniform(-40, 40)), math.radians(rnd.uniform(-30, 30)),
                                                            math.radians(a)), cup=0.18, ruffle=0.03)
        parts.append(lf)
    stem = rod("SpStem", [(0.0, 0.0, 0.4), (0.0, -0.55, 0.2)], 0.035, vein)
    return tilt(ground_all(parts + [stem]), -18)


def lentils():
    """Красная чечевица в латунной мисочке."""
    b, h = bowl("LentBowl", 0.8, 0.42, ((0.70, 0.50, 0.16), (0.96, 0.80, 0.40)), foot=False)
    b.data.materials[0].node_tree.nodes["Principled BSDF"].inputs["Metallic"].default_value = 0.85
    lent = grad("Lentil", (0.92, 0.42, 0.14), (1.0, 0.62, 0.30), coord="nz", lo=-1, hi=1, rough=0.35, coat=0.4)
    m = mound("LentMound", 0.72, 0.32, flat("LentBase", (0.94, 0.48, 0.18), rough=0.5), z=h - 0.08, bumps=0.0)
    parts = [b, m]

    def make(i, rnd):
        g = sphere(f"Lent{i}", 0.05, 12, 8)
        g.scale = (1.0, 1.0, 0.45)
        apply_transform(g)
        return assign(smooth(g), lent)
    scatter_on(m, 140, make, seed=3, area=0.72, spacing=0.06)
    parts += [o for o in bpy.data.objects if o.name.startswith("Lent") and o.type == "MESH" and o not in parts]
    return tilt(parts, -10)


def mango():
    skin = material("Mango", [(0.0, (0.95, 0.70, 0.10)), (0.5, (1.0, 0.56, 0.12)), (0.8, (0.92, 0.30, 0.14)),
                              (1.0, (0.60, 0.70, 0.20))], coord="x", lo=-0.9, hi=0.9, rough=0.22, sss=0.4, coat=0.6, vary=0.1)
    ob = sphere("Mango", 1.0, 64, 40)

    def shape(co):
        x, y, z = co
        bulge = 1 + 0.18 * x
        return Vector((x * 0.85 + 0.12 * z * z, y * 0.62 * bulge, z * 0.68 * bulge))
    deform(ob, shape)
    assign(smooth(ob), skin)
    leaf = grad("MangoLeaf", (0.16, 0.48, 0.14), (0.36, 0.70, 0.24), lo=0.5, hi=1.0, rough=0.3, coat=0.5)
    stem = rod("MangoStem", [(0.78, 0, 0.35), (0.86, 0, 0.55)], 0.04, flat("MangoStemMat", (0.42, 0.30, 0.16), rough=0.5))
    lf = leaf_blob("MangoLf", 0.42, 0.14, leaf, (0.5, 0.1, 0.68), (math.radians(10), math.radians(-20), math.radians(150)),
                   cup=0.08)
    parts = [ob, stem, lf]
    rotate_all(parts, (0, math.radians(-10), math.radians(-15)))
    return ground_all(parts)


def samosa():
    """Самоса: пухлая пирамидка из теста."""
    ob = sphere("Samosa", 1.0, 64, 40)

    def shape(co):
        a = math.atan2(co.y, co.x)
        tri = 1.0 / max(0.55, math.cos((a % (2 * math.pi / 3)) - math.pi / 3)) ** 0.85
        zz = co.z
        k = (1 - max(0.0, zz)) ** 0.9 if zz > 0 else 1.0
        return Vector((co.x * tri * 0.75 * k + 0.0, co.y * tri * 0.75 * k, zz * (0.95 if zz > 0 else 0.25) + 0.25))
    deform(ob, shape)
    push_normals(ob, lambda co, n: 0.02 * fbm(co * 6))
    assign(smooth(ob), grad("SamosaMat", (0.80, 0.48, 0.14), (0.98, 0.78, 0.40), coord="nz", lo=-0.5, hi=1.0, rough=0.4,
                            coat=0.4, bump=0.4, bump_scale=14, vary=0.15))
    return tilt([ob], -6, 20)


def naan():
    ob = polar_disc("Naan", 20, 96, 1.0, 0.65)

    def shape(co):
        x, y = co.x, co.y
        r = math.hypot(x, y / 0.65)
        z = 0.22 * (1 - r ** 2) + 0.06 * fbm(Vector((x * 3, y * 3, 0)))
        return Vector((x * (1 + 0.25 * x), y * (1 - 0.3 * x), z))
    deform(ob, shape)
    solidify(ob, 0.1)
    subdivide(ob, 1)
    smooth(ob)
    mat = grad("NaanMat", (0.94, 0.80, 0.52), (0.99, 0.90, 0.68), coord="z", lo=0.0, hi=0.2, rough=0.5, sss=0.3, sheen=0.3)
    add_speckles(mat, (0.46, 0.26, 0.10), scale=9, threshold=0.7, strength=0.8)
    assign(ob, mat)
    ob.rotation_euler = (math.radians(68), 0, math.radians(-12))
    apply_transform(ob)
    return ground_all([ob])


def masala_chai():
    """Чай в глиняном стаканчике кулхад."""
    cup = lathe_obj("Kulhad", [(0.0, 0.0), (0.32, 0.0), (0.36, 0.05), (0.52, 0.9), (0.55, 0.95), (0.5, 0.96), (0.47, 0.88),
                               (0.0, 0.82)], grad("KulhadMat", (0.62, 0.28, 0.14), (0.84, 0.46, 0.26), lo=0.0, hi=0.96,
                                                  rough=0.65, vary=0.15, bump=0.2))
    tea = disc("Chai", 0.48, 0.88, grad("ChaiMat", (0.76, 0.52, 0.30), (0.88, 0.68, 0.46), coord="r", hi=0.48, rough=0.1,
                                         coat=0.7, sss=0.3))
    stick = rod("Cinn", [(0.25, 0.1, 0.8), (0.45, 0.15, 1.35)], 0.05, flat("CinnMat", (0.56, 0.28, 0.12), rough=0.6))
    return tilt([cup, tea, stick], -12)


def jalebi():
    """Две спирали джалеби."""
    mat = grad("Jalebi", (0.96, 0.46, 0.04), (1.0, 0.72, 0.14), coord="nz", lo=-1, hi=1, rough=0.06, coat=1.0, sss=0.4)
    parts = []
    for j, (cx, cy, cz, tiltx) in enumerate(((0.0, 0.0, 0.12, 0), (0.25, 0.3, 0.45, 35))):
        pts = []
        for k in range(120):
            t = k / 119
            a = t * 2.6 * 2 * math.pi
            r = 0.08 + 0.52 * t
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a), cz + 0.02 * math.sin(a * 3)))
        o = rod(f"Jal{j}", pts, 0.09, mat)
        if tiltx:
            rotate_all([o], (math.radians(tiltx), 0, 0), (cx, cy, cz))
        parts.append(o)
    return tilt(ground_all(parts), -12)


def ladoo():
    mat = grad("Ladoo", (0.98, 0.66, 0.10), (1.0, 0.84, 0.32), coord="nz", lo=-1, hi=1, rough=0.7, sss=0.3,
               bump=1.0, bump_scale=26)
    add_speckles(mat, (1.0, 0.94, 0.70), scale=30, threshold=0.62, strength=0.9)
    nut = flat("LadooNut", (0.56, 0.78, 0.30), rough=0.4)
    parts = []
    for i, (x, y, z) in enumerate(((-0.36, -0.1, 0.32), (0.36, -0.1, 0.32), (0.0, 0.3, 0.32), (0.0, 0.05, 0.86))):
        parts.append(ball(f"Ladoo{i}", 0.34, (x, y, z), mat, segs=48, rings=30))
        parts.append(ball(f"LNut{i}", 0.06, (x + 0.05, y - 0.12, z + 0.3), nut, (1.4, 1.0, 0.5)))
    return tilt(parts, -10)


def gulab_jamun():
    b, h = bowl("GJBowl", 0.95, 0.5, ((0.92, 0.92, 0.94), (1.0, 1.0, 1.0)), band=(0.20, 0.42, 0.76))
    syrup = disc("GJSyrup", 0.86, h - 0.08, grad("GJSyrupMat", (0.86, 0.50, 0.12), (0.98, 0.72, 0.28), coord="r", hi=0.9,
                                                 rough=0.03, coat=1.0, sss=0.3))
    ball_m = grad("GJBall", (0.36, 0.14, 0.05), (0.62, 0.30, 0.10), coord="nz", lo=-1, hi=1, rough=0.12, coat=0.9)
    parts = [b, syrup]
    for i, (x, y) in enumerate(((-0.32, -0.15), (0.3, -0.18), (0.0, 0.3))):
        parts.append(ball(f"GJ{i}", 0.3, (x, y, h + 0.08), ball_m, (1, 1, 0.9), 48, 30))
    return tilt(parts, -10)


def dish_butter_chicken():
    b, h = copper_bowl("BCBowl", 1.0, 0.5)
    curry = curry_in("BCCurry", 0.95, h - 0.04, (0.86, 0.36, 0.08), (0.98, 0.56, 0.20))
    meat = grad("BCMeat", (0.76, 0.30, 0.08), (0.92, 0.48, 0.18), coord="nz", lo=-1, hi=1, rough=0.3, coat=0.6, bump=0.3)
    from models_mexico import rcube
    parts = [b, curry]
    rnd = random.Random(9)
    for i in range(6):
        a = 2 * math.pi * i / 6 + 0.3
        c = rcube(f"BCm{i}", 0.17, 0.15, 0.12, 3.0, 6)
        c.rotation_euler = (rnd.uniform(-0.3, 0.3), rnd.uniform(-0.3, 0.3), rnd.uniform(0, 3))
        c.location = (0.5 * math.cos(a), 0.5 * math.sin(a), h + 0.02)
        apply_transform(c)
        parts.append(assign(c, meat))
    cream = flat("BCCream", (1.0, 0.98, 0.92), rough=0.2, sss=0.4, coat=0.5)
    pts = [(0.3 * t * math.cos(t * 9), 0.3 * t * math.sin(t * 9), h + 0.0) for t in [k / 40 for k in range(41)]]
    parts.append(rod("BCSwirl", pts, 0.035, cream))
    leaf = flat("BCLeaf", (0.24, 0.62, 0.18), rough=0.3, coat=0.4)
    for i, (x, y) in enumerate(((0.1, 0.2), (-0.15, -0.1), (0.25, -0.25))):
        parts.append(leaf_blob(f"BCl{i}", 0.08, 0.06, leaf, (x, y, h + 0.04), (0, 0, i), cup=0.02))
    return parts


def dish_lassi():
    cup = glass_cup("LassiCup", 0.42, 0.55, 1.55)
    drink = liquid("Lassi", 0.4, 0.51, 0.06, 1.38, grad("LassiMat", (1.0, 0.70, 0.14), (1.0, 0.84, 0.36), lo=0.0, hi=1.4,
                                                          rough=0.2, sss=0.6, coat=0.4))
    foam = disc("LassiFoam", 0.52, 1.4, flat("LassiFoamMat", (1.0, 0.92, 0.66), rough=0.5, sss=0.4), h=0.06, wobble=0.02)
    slice_ = sphere("LassiMango", 0.3, 32, 20)
    slice_.scale = (1.0, 0.35, 0.7)
    slice_.location = (0.5, 0.0, 1.55)
    apply_transform(slice_)
    bisect(slice_, (0.5, 0, 1.55), (0, 0, -1))
    assign(smooth(slice_), flat("LassiMangoMat", (1.0, 0.62, 0.08), rough=0.2, sss=0.5, coat=0.5))
    mint = flat("LassiMint", (0.25, 0.65, 0.22), rough=0.3, coat=0.4)
    l1 = leaf_blob("LassiLf", 0.14, 0.08, mint, (-0.1, 0.05, 1.46), (0.3, 0, 0.5), cup=0.04)
    return [cup, drink, foam, slice_, l1, straw("LassiStraw", -0.15, 0.1, 0.4, 2.1, (1.0, 1.0, 1.0), 14,
                                               stripes=(0.95, 0.45, 0.10))]


def dish_biryani():
    pot = lathe_obj("Handi", [(0.0, 0.0), (0.6, 0.0), (0.9, 0.25), (1.0, 0.5), (0.86, 0.72), (0.84, 0.78), (0.9, 0.82),
                              (0.86, 0.86), (0.78, 0.7), (0.0, 0.55)],
                    grad("HandiMat", (0.50, 0.24, 0.10), (0.86, 0.54, 0.30), lo=0.0, hi=0.86, rough=0.25, metal=0.8))
    white = grad("BiryW", (0.96, 0.92, 0.82), (1.0, 0.98, 0.92), lo=0.6, hi=1.2, rough=0.4, sss=0.4, bump=0.7, bump_scale=50)
    rice_m = mound("BiryMound", 0.82, 0.48, white, z=0.68, bumps=0.03)
    yellow = flat("BiryY", (1.0, 0.74, 0.16), rough=0.4, sss=0.3)
    parts = [pot, rice_m]

    def make(i, rnd):
        g = sphere(f"BirG{i}", 0.03, 8, 6)
        g.scale = (1.0, 1.0, 2.4)
        g.rotation_euler = (rnd.uniform(0, 3), rnd.uniform(0, 3), 0)
        apply_transform(g)
        return assign(smooth(g), yellow)
    scatter_on(rice_m, 160, make, seed=2, area=0.8, spacing=0.035)
    parts += [o for o in bpy.data.objects if o.name.startswith("BirG")]
    egg_w = ball("BiryEgg", 0.2, (0.25, -0.2, 1.08), flat("BiryEggW", (1, 0.99, 0.95), rough=0.3, sss=0.4),
                 (1.0, 1.0, 1.3), 32, 20)
    bisect(egg_w, (0.25, -0.2, 1.1), (0.3, -0.6, 0.8))
    yolk = ball("BiryYolk", 0.1, (0.3, -0.29, 1.15), flat("BiryYolkM", (1.0, 0.60, 0.08), rough=0.3, sss=0.3),
                (1, 0.5, 1), 24, 16)
    leaf = flat("BiryLeaf", (0.24, 0.62, 0.18), rough=0.3, coat=0.4)
    parts += [egg_w, yolk, leaf_blob("BiryLf", 0.1, 0.07, leaf, (-0.15, 0.1, 1.17), (0.2, 0, 1), cup=0.03)]
    return parts


def dish_palak_paneer():
    b, h = bowl("PPBowl", 1.0, 0.52, ((0.20, 0.20, 0.22), (0.34, 0.34, 0.38)))
    curry = curry_in("PPCurry", 0.95, h - 0.04, (0.18, 0.42, 0.10), (0.34, 0.60, 0.18))
    from models_mexico import rcube
    cube = flat("PPCube", (0.98, 0.94, 0.84), rough=0.35, sss=0.5)
    parts = [b, curry]
    rnd = random.Random(7)
    for i in range(7):
        a = 2 * math.pi * i / 7
        r = 0.5 if i else 0.0
        c = rcube(f"PPc{i}", 0.13, 0.13, 0.1, 6.0, 6)
        c.rotation_euler = (0, 0, rnd.uniform(0, 1.5))
        c.location = (r * math.cos(a), r * math.sin(a), h + 0.02)
        apply_transform(c)
        parts.append(assign(c, cube))
    cream = flat("PPCream", (1.0, 0.98, 0.94), rough=0.2, coat=0.5)
    pts = [(-0.6 + 1.2 * t, 0.2 * math.sin(t * 8), h + 0.0) for t in [k / 30 for k in range(31)]]
    parts.append(rod("PPCr", pts, 0.03, cream))
    return parts


def dish_dal():
    b, h = copper_bowl("DalBowl", 0.95, 0.5)
    dal = curry_in("DalSoup", 0.9, h - 0.04, (0.96, 0.66, 0.10), (1.0, 0.80, 0.30))
    parts = [b, dal]
    seed = flat("DalSeed", (0.30, 0.18, 0.08), rough=0.4)
    chili = flat("DalChili", (0.70, 0.10, 0.04), rough=0.3, coat=0.6)
    leaf = flat("DalLeaf", (0.24, 0.62, 0.18), rough=0.3, coat=0.4)
    rnd = random.Random(12)
    for i in range(18):
        a, r = rnd.uniform(0, 6.28), 0.5 * math.sqrt(rnd.random())
        parts.append(ball(f"DalS{i}", 0.03, (r * math.cos(a), r * math.sin(a), h + 0.01), seed, (1.4, 1, 0.6), 10, 6))
    parts.append(ball("DalCh", 0.08, (0.2, 0.1, h + 0.03), chili, (2.4, 0.7, 0.6), 16, 10, (0, 0, 0.6)))
    for i, (x, y) in enumerate(((-0.25, 0.15), (0.0, -0.25), (0.3, -0.1), (-0.1, 0.35))):
        parts.append(leaf_blob(f"DalL{i}", 0.08, 0.06, leaf, (x, y, h + 0.03), (0, 0, i), cup=0.03))
    return parts


M.MODELS.update({
    "chicken": chicken, "paneer": paneer, "spinach": spinach, "lentils": lentils, "mango": mango,
    "samosa": samosa, "naan": naan, "masala_chai": masala_chai, "jalebi": jalebi, "ladoo": ladoo,
    "gulab_jamun": gulab_jamun,
    "dish_butter_chicken": dish_butter_chicken, "dish_lassi": dish_lassi, "dish_biryani": dish_biryani,
    "dish_palak_paneer": dish_palak_paneer, "dish_dal": dish_dal,
})


# MARK: - Корейская кухня (биом 8)

def cabbage():
    """Пекинская капуста: вытянутый кочан, белые черешки и волнистый зеленый верх."""
    parts = []
    white = grad("NapaWhite", (0.94, 0.96, 0.86), (0.80, 0.92, 0.58), lo=0.0, hi=1.6, rough=0.3, sss=0.5, coat=0.4)
    green = grad("NapaGreen", (0.66, 0.86, 0.36), (0.42, 0.72, 0.22), lo=1.0, hi=2.0, rough=0.35, sss=0.4, coat=0.4,
                 bump=0.4, bump_scale=12)
    for i in range(6):
        a = 2 * math.pi * i / 6
        w = 0.5 - 0.04 * (i % 2)
        ob = sphere(f"Napa{i}", 1.0, 48, 32)

        def shape(co, w=w):
            t = (co.z + 1) / 2
            k = w * (0.75 + 0.35 * math.sin(math.pi * min(1.0, t * 1.1)))
            ruffle = 0.05 * math.sin(math.atan2(co.y, co.x) * 9) * max(0.0, t - 0.55) * 2
            return Vector((co.x * k * 0.9 + ruffle, co.y * k * 0.45, (co.z + 1) * 0.95))
        deform(ob, shape)
        ob.location = (0.12 * math.cos(a), 0.12 * math.sin(a), 0)
        ob.rotation_euler = (0.08 * math.sin(a), -0.08 * math.cos(a), a)
        apply_transform(ob)
        smooth(ob)
        assign_faces(ob, white, [(lambda n, c: c.z > 1.0, green)])
        parts.append(ob)
    rotate_all(parts, (0, math.radians(70), math.radians(-15)))
    return ground_all(parts)


def kimchi():
    parts = jar("KimchiJar", 0.62, 1.05, lid=(0.20, 0.55, 0.28), label=(0.98, 0.96, 0.90))
    red = grad("KimchiRed", (0.80, 0.16, 0.06), (0.96, 0.40, 0.16), lo=0.0, hi=1.0, rough=0.3, sss=0.4, coat=0.6,
               bump=0.4, bump_scale=10)
    rnd = random.Random(4)
    for i in range(14):
        a, r = rnd.uniform(0, 6.28), rnd.uniform(0.15, 0.45)
        z = 0.15 + 0.11 * (i // 3)
        parts.append(ball(f"Kim{i}", 0.2, (r * math.cos(a), r * math.sin(a), z), red, (1.0, 0.5, 0.4), 24, 14,
                          (rnd.uniform(0, 3), rnd.uniform(0, 3), 0)))
    return tilt(parts, -8)


def gochujang():
    """Красная квадратная баночка пасты с открытой крышкой."""
    from models_mexico import rcube
    tub = rcube("GTub", 0.6, 0.5, 0.36, 5.0, 10)
    tub.location = (0, 0, 0.36)
    apply_transform(tub)
    assign_faces(tub, grad("GTubMat", (0.70, 0.08, 0.06), (0.92, 0.18, 0.12), lo=0.0, hi=0.72, rough=0.25, coat=0.6),
                 [(lambda n, c: n.z > 0.8 and c.z > 0.7, grad("GPaste", (0.56, 0.06, 0.04), (0.76, 0.14, 0.08), coord="x",
                                                              lo=-0.5, hi=0.5, rough=0.15, coat=0.9, bump=0.3))])
    label = box_mesh("GLabel", 0.7, 0.02, 0.28, 0.2)
    label.location = (0, -0.5, 0)
    apply_transform(label)
    assign(label, flat("GLabelMat", (0.99, 0.94, 0.80), rough=0.4))
    spoon = rod("GSpoon", [(0.2, 0.0, 0.74), (0.55, 0.15, 1.2)], 0.04, flat("GSpoonMat", (0.85, 0.86, 0.9), rough=0.2,
                                                                               metal=0.8))
    return tilt([tub, label, spoon], -10, 20)


def seaweed():
    """Стопка листов нори."""
    nori = grad("Nori", (0.04, 0.10, 0.06), (0.12, 0.24, 0.12), coord="nz", lo=-1, hi=1, rough=0.45, coat=0.3,
                bump=0.3, bump_scale=16)
    parts = []
    for i in range(6):
        sh = box_mesh(f"Nori{i}", 1.4, 1.0, 0.04, i * 0.05, cuts=6)
        bevel(sh, 0.015, 2)
        sh.rotation_euler = (0, 0, math.radians(-6 + i * 3))
        apply_transform(sh)
        push_normals(sh, lambda co, n: 0.015 * fbm(co * 5))
        parts.append(assign(smooth(sh), nori))
    band = box_mesh("NoriBand", 0.32, 1.06, 0.34, -0.02)
    assign(band, flat("NoriBandMat", (0.96, 0.30, 0.18), rough=0.4))
    return ground_all(rotate_all(parts + [band], (math.radians(40), 0, math.radians(15))))


def cucumber():
    skin = grad("Cuke", (0.12, 0.40, 0.10), (0.30, 0.62, 0.18), coord="nz", lo=-1, hi=1, rough=0.25, coat=0.6, sss=0.3,
                bump=0.4, bump_scale=10)
    add_stripes(skin, (0.48, 0.74, 0.30), scale=4, angle=0, width=0.1, nz_min=-1.0, strength=0.5)
    c = capsule("Cuke", 2.0, 0.3, 48, 32, pinch=0.2)
    bend(c, 4.0)
    push_normals(c, lambda co, n: 0.012 * fbm(co * 8))
    assign(smooth(c), skin)
    flesh = grad("CukeFlesh", (0.92, 0.98, 0.70), (0.70, 0.88, 0.40), coord="r", lo=0.0, hi=0.3, rough=0.25, sss=0.5,
                 coat=0.5)
    sl = cylinder("CukeSlice", 0.28, 0.08, 48)
    sl.rotation_euler = (math.radians(70), 0, 0)
    sl.location = (0.55, -0.45, 0.25)
    apply_transform(sl)
    parts = [c, assign(smooth(sl, 50), flesh)]
    rotate_all(parts, (0, 0, math.radians(-20)))
    return ground_all(parts)


def rice_cake():
    """Палочки ттока."""
    mat = grad("Tteok", (0.92, 0.92, 0.88), (1.0, 1.0, 0.98), coord="nz", lo=-1, hi=1, rough=0.25, sss=0.7,
               sss_radius=(1, 1, 0.95), coat=0.5)
    parts = []
    for i, (x, y, z, rz) in enumerate(((-0.0, -0.25, 0.14, 0), (0.0, 0.05, 0.14, 4), (0.0, 0.35, 0.14, -4),
                                       (0.05, -0.1, 0.4, 8), (0.0, 0.2, 0.4, -6), (0.05, 0.05, 0.66, 2))):
        c = capsule(f"Tteok{i}", 1.4, 0.14, 40, 24, pinch=0.6)
        c.rotation_euler = (0, 0, math.radians(rz))
        c.location = (x, y, z)
        apply_transform(c)
        parts.append(assign(smooth(c), mat))
    return tilt(parts, -16, -25)


def hotteok():
    ob = rounded_disc("Hotteok", 0.85, 0.28, 3.0, 28)
    deform(ob, lambda co: Vector((co.x, co.y, co.z + 0.14 + 0.04 * (1 - (co.x ** 2 + co.y ** 2) / 0.72))))
    push_normals(ob, lambda co, n: 0.02 * fbm(co * 5))
    mat = grad("HotteokMat", (0.72, 0.40, 0.12), (0.96, 0.72, 0.36), coord="nz", lo=-0.2, hi=1.0, rough=0.25, coat=0.7,
               vary=0.25, vary_scale=4)
    assign(smooth(ob), mat)
    syrup = flat("HotSyrup", (0.52, 0.22, 0.06), rough=0.05, coat=1.0)
    pts = [(0.3 * math.cos(t * 6.28), 0.2 * math.sin(t * 6.28) - 0.1, 0.33) for t in [k / 30 for k in range(31)]]
    seeds = flat("HotSeed", (0.36, 0.58, 0.20), rough=0.4)
    parts = [ob, rod("HotDrip", pts, 0.05, syrup)]
    for i in range(6):
        a = i * 1.1
        parts.append(ball(f"HotS{i}", 0.04, (0.18 * math.cos(a), 0.12 * math.sin(a) - 0.1, 0.36), seeds, (1.2, 0.8, 0.5)))
    return ground_all(rotate_all(parts, (math.radians(52), 0, math.radians(10))))


def banana_milk():
    body = grad("BMilk", (0.98, 0.84, 0.26), (1.0, 0.92, 0.50), lo=0.0, hi=1.1, rough=0.25, sss=0.4, coat=0.5)
    ob = lathe_obj("BMBody", [(0.0, 0.0), (0.42, 0.0), (0.5, 0.08), (0.55, 0.45), (0.5, 0.82), (0.36, 0.98), (0.3, 1.04),
                              (0.0, 1.04)], body)
    foil = lathe_obj("BMFoil", [(0.0, 1.03), (0.3, 1.03), (0.32, 1.07), (0.0, 1.08)],
                     flat("BMFoilMat", (0.98, 0.98, 1.0), rough=0.2, metal=0.6))
    label = lathe_obj("BMLabel", [(0.555, 0.3), (0.565, 0.32), (0.565, 0.6), (0.555, 0.62)],
                      flat("BMLabelMat", (1.0, 1.0, 1.0), rough=0.4), 72, 0)
    return [ob, foil, label, straw("BMStraw", 0.1, 0.0, 0.9, 1.6, (0.98, 0.85, 0.30), 18)]


def dalgona():
    disc_ = rounded_disc("Dalgona", 0.8, 0.12, 3.0, 28)
    deform(disc_, lambda co: Vector((co.x * (1 + 0.03 * math.sin(math.atan2(co.y, co.x) * 7)),
                                     co.y * (1 + 0.03 * math.sin(math.atan2(co.y, co.x) * 7)), co.z + 0.06)))
    mat = grad("DalgonaMat", (0.80, 0.48, 0.10), (0.98, 0.72, 0.28), coord="r", lo=0.0, hi=0.8, rough=0.15, coat=0.8,
               sss=0.3, bump=0.3, bump_scale=30)
    assign(smooth(disc_), mat)
    pts = []
    for k in range(11):
        a = math.pi / 2 + k * math.pi / 5
        r = 0.42 if k % 2 == 0 else 0.18
        pts.append((r * math.cos(a), r * math.sin(a)))
    star = profile_prism("DalStar", pts, 0.02, 0.115)
    assign(star, flat("DalStarMat", (0.62, 0.32, 0.06), rough=0.3, coat=0.6))
    stick = rod("DalStick", [(0.0, 0.0, 0.06), (0.0, -1.3, 0.06)], 0.035, flat("DalStickMat", (0.92, 0.80, 0.56), rough=0.5))
    parts = [disc_, star, stick]
    rotate_all(parts, (math.radians(70), 0, math.radians(-10)))
    return ground_all(parts)


def bingsu():
    b, h = bowl("BingBowl", 0.85, 0.5, ((0.92, 0.95, 1.0), (1.0, 1.0, 1.0)), band=(0.55, 0.75, 0.95))
    ice = mound("BingIce", 0.82, 0.7, grad("BingIceMat", (0.98, 0.96, 0.96), (1.0, 1.0, 1.0), lo=0.4, hi=1.2, rough=0.6,
                                         sss=0.6, sss_radius=(0.9, 0.9, 1.0), bump=0.8, bump_scale=30), z=h - 0.05, bumps=0.04)
    bean = grad("RedBean", (0.40, 0.08, 0.10), (0.58, 0.16, 0.16), coord="nz", lo=-1, hi=1, rough=0.2, coat=0.8)
    straw_m = grad("BingStraw", (0.85, 0.08, 0.14), (1.0, 0.30, 0.30), coord="nz", lo=-1, hi=1, rough=0.2, coat=0.8, sss=0.4)
    parts = [b, ice]
    for i in range(12):
        a, r = i * 2.4, 0.18 * math.sqrt(i / 12 + 0.1)
        parts.append(ball(f"BingB{i}", 0.07, (r * math.cos(a), r * math.sin(a), h + 0.64), bean, (1.2, 0.9, 0.8), 16, 10))
    for i, (x, y) in enumerate(((0.35, -0.3), (-0.3, -0.35))):
        parts.append(ball(f"BingS{i}", 0.13, (x, y, h + 0.4), straw_m, (1, 1, 1.2), 24, 16))
    mochi = flat("BingMochi", (1.0, 0.98, 0.94), rough=0.4, sss=0.5)
    from models_mexico import rcube
    for i, (x, y) in enumerate(((0.12, 0.2), (-0.15, 0.25))):
        c = rcube(f"BingM{i}", 0.08, 0.08, 0.08, 5.0, 5)
        c.location = (x, y, h + 0.66)
        apply_transform(c)
        parts.append(assign(c, mochi))
    return parts


def yakgwa():
    """Медовое печенье-цветок якгва с ядрышками кедра."""
    ob = rounded_disc("Yakgwa", 0.75, 0.32, 3.0, 28)

    def shape(co):
        a = math.atan2(co.y, co.x)
        k = 1 + 0.16 * math.cos(a * 8)
        return Vector((co.x * k, co.y * k, co.z + 0.16))
    deform(ob, shape)
    push_normals(ob, lambda co, n: 0.012 * fbm(co * 10))
    assign(smooth(ob), grad("YakgwaMat", (0.50, 0.22, 0.06), (0.78, 0.44, 0.14), coord="nz", lo=-0.5, hi=1.0, rough=0.08,
                            coat=1.0, sss=0.3, bump=0.3, bump_scale=24))
    nut = flat("YakNut", (0.98, 0.92, 0.76), rough=0.3)
    parts = [ob]
    for i in range(3):
        a = i * 2.1
        parts.append(ball(f"YakN{i}", 0.06, (0.08 * math.cos(a), 0.08 * math.sin(a), 0.33), nut, (1.4, 0.8, 0.5), 16, 10,
                          (0, 0, a)))
    return ground_all(rotate_all(parts, (math.radians(50), 0, 0)))


def hodugwaja():
    """Пирожные-грецкие орехи в бумажном пакетике."""
    mat = grad("Hodu", (0.62, 0.34, 0.12), (0.86, 0.58, 0.28), coord="nz", lo=-1, hi=1, rough=0.35, coat=0.5,
               bump=0.6, bump_scale=9)
    parts = []
    for i, (x, y, z) in enumerate(((-0.3, 0.0, 0.26), (0.3, 0.0, 0.26), (0.0, 0.25, 0.26), (0.0, 0.0, 0.66))):
        ob = sphere(f"Hodu{i}", 0.3, 48, 30)
        push_normals(ob, lambda co, n: 0.03 * math.sin(co.x * 30) * math.sin(co.y * 26) + 0.02 * fbm(co * 6))
        ob.location = (x, y, z)
        apply_transform(ob)
        parts.append(assign(smooth(ob), mat))
        ridge = torus(f"HoduR{i}", 0.3, 0.02, 48, 8)
        ridge.rotation_euler = (math.radians(90), 0, 0)
        ridge.location = (x, y, z)
        apply_transform(ridge)
        parts.append(assign(smooth(ridge), mat))
    return tilt(parts, -12, 10)


def dish_kimchi_pancake():
    p = plate_round("KPPlate", 1.2, (0.97, 0.97, 0.98), (0.20, 0.30, 0.55))
    cake = rounded_disc("KPCake", 0.98, 0.14, 3.0, 32)
    cake.location = (0, 0, 0.18)
    apply_transform(cake)
    push_normals(cake, lambda co, n: 0.02 * fbm(co * 4))
    mat = grad("KPCakeMat", (0.86, 0.36, 0.08), (0.98, 0.58, 0.20), coord="r", lo=0.0, hi=1.0, rough=0.3, coat=0.6,
               vary=0.3, vary_scale=5)
    add_speckles(mat, (0.70, 0.12, 0.06), scale=8, threshold=0.6, strength=0.8)
    assign(smooth(cake), mat)
    leek = flat("KPLeek", (0.40, 0.72, 0.24), rough=0.3, coat=0.5)
    parts = [p, cake]
    for i in range(6):
        y = -0.5 + i * 0.2
        parts.append(rod(f"KPL{i}", [(-0.6 + 0.1 * (i % 2), y, 0.27), (0.6, y + 0.1, 0.27)], 0.03, leek))
    return parts


def dish_bibimbap():
    pot = lathe_obj("Dolsot", [(0.0, 0.0), (0.7, 0.0), (0.95, 0.2), (1.02, 0.55), (0.98, 0.62), (0.9, 0.5), (0.0, 0.42)],
                    grad("DolsotMat", (0.12, 0.12, 0.13), (0.30, 0.30, 0.32), lo=0.0, hi=0.62, rough=0.45, coat=0.3))
    rice_d = disc("BBRice", 0.9, 0.5, flat("BBRiceM", (1.0, 0.98, 0.94), rough=0.5, sss=0.4, bump=0.5, bump_scale=40),
                  h=0.06)
    parts = [pot, rice_d]
    colors = [(0.30, 0.62, 0.20), (1.0, 0.56, 0.12), (0.62, 0.36, 0.18), (0.96, 0.92, 0.70), (0.80, 0.14, 0.08)]
    for i, col in enumerate(colors):
        a = 2 * math.pi * i / 5
        m = mound(f"BBTop{i}", 0.3, 0.14, flat(f"BBTopM{i}", col, rough=0.35, coat=0.5, bump=0.4, bump_scale=30),
                  z=0.52, bumps=0.02)
        m.location = (0.55 * math.cos(a), 0.55 * math.sin(a), 0)
        parts.append(m)
    white = ball("BBEggW", 0.34, (0, 0, 0.58), flat("BBEggWM", (1.0, 0.99, 0.95), rough=0.25, sss=0.4, coat=0.4),
                 (1.0, 1.0, 0.18), 48, 24)
    yolk = ball("BBYolk", 0.14, (0.0, -0.04, 0.63), flat("BBYolkM", (1.0, 0.62, 0.06), rough=0.15, coat=0.8, sss=0.4),
                (1, 1, 0.6), 32, 20)
    return parts + [white, yolk]


def dish_kimbap():
    board = box_mesh("KBBoard", 2.4, 1.3, 0.14, 0.0, cuts=4)
    bevel(board, 0.04, 3)
    assign(smooth(board), grad("KBBoardMat", (0.66, 0.44, 0.22), (0.86, 0.64, 0.36), coord="x", lo=-1.2, hi=1.2,
                               rough=0.5, vary=0.2))
    nori = flat("KBNori", (0.06, 0.10, 0.06), rough=0.4, coat=0.3)
    rice_m = flat("KBRice", (1.0, 0.99, 0.96), rough=0.5, sss=0.3, bump=0.4, bump_scale=60)
    fills = [(1.0, 0.82, 0.12), (1.0, 0.50, 0.10), (0.30, 0.64, 0.18), (0.80, 0.24, 0.30)]
    parts = [board]
    for i in range(5):
        x = -0.85 + i * 0.42
        lean = 0 if i < 4 else 50
        outer = cylinder(f"KBOut{i}", 0.3, 0.26, 48)
        outer.rotation_euler = (math.radians(90 - lean), 0, 0)
        outer.location = (x, 0, 0.44)
        apply_transform(outer)
        assign(smooth(outer, 50), nori)
        inner = cylinder(f"KBIn{i}", 0.27, 0.27, 48)
        inner.rotation_euler = (math.radians(90 - lean), 0, 0)
        inner.location = (x, -0.0, 0.44)
        apply_transform(inner)
        assign(smooth(inner, 50), rice_m)
        parts += [outer, inner]
        for k, col in enumerate(fills):
            a = k * 1.57 + 0.6
            f = cylinder(f"KBF{i}{k}", 0.055, 0.28, 16)
            f.rotation_euler = (math.radians(90 - lean), 0, 0)
            f.location = (x + 0.1 * math.cos(a), -0.0, 0.44 + 0.1 * math.sin(a))
            apply_transform(f)
            parts.append(assign(smooth(f, 50), flat(f"KBFM{i}{k}", col, rough=0.3, coat=0.5)))
    return rotate_all(parts, (0, 0, math.radians(-8)))


def dish_bulgogi():
    plate = lathe_obj("BGPlate", [(0.0, 0.0), (1.1, 0.0), (1.2, 0.08), (1.18, 0.16), (1.08, 0.12), (0.0, 0.1)],
                      grad("BGPlateMat", (0.12, 0.12, 0.13), (0.28, 0.28, 0.30), lo=0.0, hi=0.16, rough=0.4, metal=0.5))
    wood = lathe_obj("BGWood", [(0.0, -0.12), (1.25, -0.12), (1.3, -0.06), (1.28, 0.0), (0.0, 0.0)],
                     grad("BGWoodMat", (0.50, 0.30, 0.14), (0.70, 0.46, 0.22), lo=-0.12, hi=0.0, rough=0.5))
    beef = grad("BGBeef", (0.40, 0.18, 0.08), (0.62, 0.32, 0.14), coord="nz", lo=-1, hi=1, rough=0.2, coat=0.8,
                bump=0.4, bump_scale=10)
    onion = flat("BGOnion", (0.98, 0.92, 0.80), rough=0.2, sss=0.5, coat=0.6)
    parts = [plate, wood]
    rnd = random.Random(14)
    for i in range(16):
        a, r = rnd.uniform(0, 6.28), 0.75 * math.sqrt(rnd.random())
        s = rounded_disc(f"BGs{i}", 0.25, 0.05, 2.5, 10)
        s.scale = (1.4, 0.6, 1)
        s.rotation_euler = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), rnd.uniform(0, 3))
        s.location = (r * math.cos(a), r * math.sin(a), 0.16 + 0.04 * (i % 3))
        apply_transform(s)
        push_normals(s, lambda co, n: 0.02 * fbm(co * 6))
        parts.append(assign(smooth(s), beef))
    for i in range(6):
        a, r = rnd.uniform(0, 6.28), 0.6 * math.sqrt(rnd.random())
        t = torus(f"BGo{i}", 0.16, 0.025, 32, 8)
        bisect(t, (0, 0, 0), (0, -1, 0))
        t.rotation_euler = (0, 0, rnd.uniform(0, 3))
        t.location = (r * math.cos(a), r * math.sin(a), 0.28)
        apply_transform(t)
        parts.append(assign(smooth(t), onion))
    sesame = flat("BGSes", (1.0, 0.96, 0.84), rough=0.3)
    for i in range(20):
        a, r = rnd.uniform(0, 6.28), 0.6 * math.sqrt(rnd.random())
        parts.append(ball(f"BGse{i}", 0.025, (r * math.cos(a), r * math.sin(a), 0.32), sesame, (1.5, 0.8, 0.5), 8, 6))
    return parts


def dish_tteokbokki():
    p = plate_round("TBPlate", 1.2, (0.97, 0.97, 0.98))
    sauce = disc("TBSauce", 0.85, 0.12, grad("TBSauceM", (0.82, 0.10, 0.04), (0.98, 0.30, 0.10), coord="r", hi=0.85,
                                              rough=0.05, coat=1.0), h=0.06, wobble=0.015)
    cake = grad("TBCake", (0.96, 0.55, 0.42), (1.0, 0.86, 0.80), coord="nz", lo=-1, hi=1, rough=0.1, sss=0.6, coat=0.9)
    parts = [p, sauce]
    rnd = random.Random(21)
    for i in range(11):
        a, r = rnd.uniform(0, 6.28), 0.55 * math.sqrt(rnd.random())
        c = capsule(f"TBc{i}", 0.6, 0.1, 24, 16, pinch=0.5)
        c.rotation_euler = (0, 0, rnd.uniform(0, 3))
        c.location = (r * math.cos(a), r * math.sin(a), 0.22 + 0.06 * (i % 3))
        apply_transform(c)
        parts.append(assign(smooth(c), cake))
    egg = ball("TBEgg", 0.22, (0.4, 0.3, 0.3), flat("TBEggW", (1.0, 0.99, 0.95), rough=0.3, sss=0.4), (1, 1, 1.25), 32, 20)
    bisect(egg, (0.4, 0.3, 0.3), (0, -1, 0))
    yolk = ball("TBYolk", 0.11, (0.4, 0.29, 0.3), flat("TBYolkM", (1.0, 0.70, 0.12), rough=0.4), (1, 0.3, 1), 20, 12)
    leek = flat("TBLeek", (0.40, 0.75, 0.25), rough=0.3, coat=0.5)
    for i in range(5):
        a = rnd.uniform(0, 6.28)
        t = torus(f"TBr{i}", 0.05, 0.018, 20, 8)
        t.location = (0.5 * math.cos(a), 0.5 * math.sin(a), 0.36)
        apply_transform(t)
        parts.append(assign(smooth(t), leek))
    return parts + [egg, yolk]


M.MODELS.update({
    "cabbage": cabbage, "kimchi": kimchi, "gochujang": gochujang, "seaweed": seaweed, "cucumber": cucumber,
    "rice_cake": rice_cake, "hotteok": hotteok, "banana_milk": banana_milk, "dalgona": dalgona, "bingsu": bingsu,
    "yakgwa": yakgwa, "hodugwaja": hodugwaja,
    "dish_kimchi_pancake": dish_kimchi_pancake, "dish_bibimbap": dish_bibimbap, "dish_kimbap": dish_kimbap,
    "dish_bulgogi": dish_bulgogi, "dish_tteokbokki": dish_tteokbokki,
})


# MARK: - Испанская кухня (биом 9)

def saffron():
    """Стеклянная баночка с нитями шафрана и цветок крокуса."""
    vial = lathe_obj("SafVial", [(0.0, 0.0), (0.36, 0.0), (0.4, 0.06), (0.4, 0.86), (0.3, 0.95), (0.0, 0.95)],
                     grad("SafGlass", (0.96, 0.98, 1.0), (1, 1, 1), hi=0.95, rough=0.03, transmission=0.95, coat=0.6))
    cork = lathe_obj("SafCork", [(0.0, 0.9), (0.29, 0.9), (0.31, 1.25), (0.0, 1.27)],
                     grad("SafCorkM", (0.70, 0.50, 0.30), (0.86, 0.66, 0.42), lo=0.9, hi=1.27, rough=0.8, bump=0.6,
                          bump_scale=40))
    thread = grad("SafThread", (0.72, 0.08, 0.04), (0.96, 0.30, 0.08), coord="z", lo=0.0, hi=0.8, rough=0.3, coat=0.4)
    parts = [vial, cork]
    rnd = random.Random(5)
    for i in range(34):
        a, r = rnd.uniform(0, 6.28), 0.3 * math.sqrt(rnd.random())
        z = rnd.uniform(0.08, 0.6)
        b = rnd.uniform(0, 6.28)
        p0 = (r * math.cos(a), r * math.sin(a), z)
        p1 = (p0[0] + 0.16 * math.cos(b), p0[1] + 0.16 * math.sin(b), z + rnd.uniform(-0.05, 0.12))
        parts.append(rod(f"Saf{i}", [p0, p1], 0.018, thread, (1.0, 1.8)))
    petal = grad("Crocus", (0.52, 0.30, 0.78), (0.78, 0.62, 0.95), lo=0.0, hi=0.5, rough=0.3, sss=0.5, coat=0.3)
    for i in range(5):
        a = 2 * math.pi * i / 5
        parts.append(ball(f"CrocP{i}", 0.2, (0.62 + 0.12 * math.cos(a), -0.15 + 0.12 * math.sin(a), 0.18), petal,
                          (0.5, 0.3, 1.0), 24, 14, (0.5 * math.sin(a), -0.5 * math.cos(a), 0)))
    return tilt(parts, -8)


def potato():
    ob = sphere("Potato", 1.0, 64, 40)
    deform(ob, lambda co: Vector((co.x * 0.85, co.y * 0.6, co.z * 0.5)) + 0.08 * Vector((fbm(co * 1.5), fbm(co * 1.6 + Vector((3, 0, 0))), fbm(co * 1.4 + Vector((0, 5, 0))))))
    push_normals(ob, lambda co, n: 0.012 * fbm(co * 8))
    mat = grad("PotatoMat", (0.66, 0.46, 0.24), (0.86, 0.68, 0.42), coord="nz", lo=-1, hi=1, rough=0.6, vary=0.2,
               bump=0.3, bump_scale=14)
    add_speckles(mat, (0.50, 0.32, 0.16), scale=10, threshold=0.72, strength=0.7)
    parts = [assign(smooth(ob), mat)]
    rotate_all(parts, (0, 0, math.radians(-20)))
    return ground_all(parts)


def garlic():
    skin = grad("Garlic", (0.96, 0.92, 0.86), (1.0, 0.99, 0.97), coord="z", lo=0.0, hi=1.2, rough=0.4, sss=0.5, coat=0.3)
    add_stripes(skin, (0.84, 0.70, 0.78), scale=8, angle=90, width=0.08, nz_min=-1.0, strength=0.5)
    ob = sphere("Garlic", 1.0, 72, 48)

    def shape(co):
        a = math.atan2(co.y, co.x)
        t = (co.z + 1) / 2
        lobes = 1 + 0.07 * math.cos(a * 8)
        k = 0.62 * lobes * (1 - 0.75 * max(0.0, t - 0.55) ** 1.2)
        return Vector((co.x * k, co.y * k, co.z * 0.55 + 0.55 + 0.35 * max(0.0, t - 0.6)))
    deform(ob, shape)
    assign(smooth(ob), skin)
    tip = rod("GarlicTip", [(0, 0, 1.1), (0.03, 0, 1.32)], 0.05, skin, (1.0, 0.5))
    roots = flat("GarlicRoot", (0.86, 0.78, 0.64), rough=0.6)
    parts = [ob, tip]
    for i in range(7):
        a = i * 0.9
        parts.append(rod(f"GRoot{i}", [(0.05 * math.cos(a), 0.05 * math.sin(a), 0.03), (0.16 * math.cos(a), 0.16 * math.sin(a), -0.02)],
                         0.012, roots))
    return tilt(ground_all(parts), -6)


def chorizo():
    mat = grad("Chorizo", (0.56, 0.08, 0.06), (0.80, 0.20, 0.10), coord="nz", lo=-1, hi=1, rough=0.3, coat=0.6,
               bump=0.4, bump_scale=12, vary=0.2)
    c = capsule("Chorizo", 2.0, 0.28, 48, 32, pinch=0.3)
    bend(c, 1.0)
    push_normals(c, lambda co, n: 0.015 * fbm(co * 6))
    assign(smooth(c), mat)
    string = flat("ChorString", (0.96, 0.92, 0.84), rough=0.7)
    parts = [c]
    bpy.context.view_layer.update()
    xs = [v.co for v in c.data.vertices]
    lo = min(xs, key=lambda v: v.x)
    parts.append(rod("ChorTie", [(lo.x + 0.02, lo.y, lo.z), (lo.x - 0.15, lo.y, lo.z + 0.1)], 0.02, string))
    cut = cylinder("ChorSlice", 0.26, 0.08, 48)
    cut.rotation_euler = (math.radians(75), 0, 0)
    cut.location = (0.4, -0.65, 0.26)
    apply_transform(cut)
    inner = grad("ChorInner", (0.78, 0.14, 0.08), (0.92, 0.30, 0.16), coord="r", lo=0.0, hi=0.26, rough=0.4)
    add_speckles(inner, (1.0, 0.88, 0.80), scale=40, threshold=0.66, strength=0.9)
    parts.append(assign(smooth(cut, 50), inner))
    rotate_all(parts, (0, 0, math.radians(-10)))
    return ground_all(parts)


def pepper():
    """Красный сладкий перец."""
    ob = sphere("Pepper", 1.0, 72, 48)

    def shape(co):
        a = math.atan2(co.y, co.x)
        t = (co.z + 1) / 2
        lobes = 1 + 0.1 * math.cos(a * 4) * (1 - t * 0.5)
        k = 0.7 * lobes * (0.8 + 0.25 * math.sin(math.pi * min(1.0, t * 1.2)))
        z = co.z * 0.75 + 0.75
        if t > 0.85:
            z -= 0.12 * (t - 0.85) / 0.15
        return Vector((co.x * k, co.y * k, z))
    deform(ob, shape)
    assign(smooth(ob), grad("PepperMat", (0.70, 0.04, 0.04), (0.96, 0.16, 0.08), coord="nz", lo=-1, hi=1, rough=0.1,
                            coat=0.9, coat_rough=0.03, sss=0.3))
    stem = grad("PepStem", (0.16, 0.42, 0.12), (0.36, 0.62, 0.20), lo=1.3, hi=1.7, rough=0.3, coat=0.5)
    cap = ball("PepCap", 0.22, (0, 0, 1.38), stem, (1, 1, 0.3))
    st = rod("PepSt", [(0, 0, 1.38), (0.05, 0, 1.55), (0.15, 0, 1.62)], 0.06, stem)
    return tilt([ob, cap, st], -8, 20)


def orange():
    skin = grad("Orange", (0.96, 0.46, 0.04), (1.0, 0.62, 0.12), coord="nz", lo=-1, hi=1, rough=0.35, coat=0.5,
                bump=0.5, bump_scale=60, sss=0.3)
    ob = sphere("Orange", 0.75, 72, 48)
    ob.location = (0, 0, 0.75)
    apply_transform(ob)
    leaf = grad("OrLeaf", (0.14, 0.44, 0.12), (0.30, 0.66, 0.20), lo=1.3, hi=1.6, rough=0.3, coat=0.6)
    lf = leaf_blob("OrLf", 0.34, 0.14, leaf, (0.25, 0.0, 1.5), (math.radians(10), math.radians(-25), math.radians(20)),
                   cup=0.06)
    st = rod("OrSt", [(0, 0, 1.47), (0.04, 0, 1.58)], 0.03, flat("OrStM", (0.40, 0.32, 0.16), rough=0.5))
    half = cylinder("OrHalf", 0.5, 0.1, 48)
    half.rotation_euler = (math.radians(70), 0, 0)
    half.location = (0.65, -0.55, 0.45)
    apply_transform(half)
    pulp = material("OrPulp", [(0.0, (1.0, 0.78, 0.30)), (0.85, (1.0, 0.56, 0.08)), (0.9, (1.0, 0.96, 0.86)),
                               (1.0, (0.98, 0.50, 0.06))], coord="r_xz", lo=0.0, hi=0.5, rough=0.2, coat=0.7, sss=0.5)
    return tilt([assign(smooth(ob), skin), lf, st, assign(smooth(half, 50), pulp)], -4, -10)


def patatas_bravas():
    cone = lathe_obj("BravasDish", [(0.0, 0.0), (0.6, 0.0), (0.9, 0.3), (0.86, 0.32), (0.0, 0.2)],
                     grad("BravasClay", (0.62, 0.28, 0.12), (0.82, 0.44, 0.22), lo=0.0, hi=0.32, rough=0.5, coat=0.3))
    from models_mexico import rcube
    potm = grad("BravasPot", (0.90, 0.62, 0.20), (1.0, 0.82, 0.42), coord="nz", lo=-1, hi=1, rough=0.4, coat=0.4,
                bump=0.3, bump_scale=20)
    parts = [cone]
    rnd = random.Random(3)
    pos = [(-0.3, -0.2, 0.3), (0.2, -0.25, 0.3), (0.35, 0.15, 0.3), (-0.2, 0.25, 0.3), (0.0, 0.0, 0.48), (-0.15, -0.1, 0.62),
           (0.15, 0.05, 0.66)]
    for i, (x, y, z) in enumerate(pos):
        c = rcube(f"Brav{i}", 0.18, 0.17, 0.16, 4.0, 6)
        c.rotation_euler = (rnd.uniform(-0.5, 0.5), rnd.uniform(-0.5, 0.5), rnd.uniform(0, 3))
        c.location = (x, y, z)
        apply_transform(c)
        parts.append(assign(c, potm))
    sauce = flat("BravasSauce", (0.86, 0.18, 0.06), rough=0.1, coat=0.9)
    aioli = flat("BravasAioli", (1.0, 0.98, 0.90), rough=0.2, coat=0.6)
    parts.append(ball("BravS", 0.2, (0.0, -0.05, 0.82), sauce, (1.4, 1.0, 0.35), 32, 16))
    parts.append(ball("BravA", 0.11, (0.1, -0.1, 0.9), aioli, (1.2, 1.0, 0.4), 24, 12))
    parts.append(rod("BravPick", [(0.3, 0.1, 0.6), (0.55, 0.25, 1.2)], 0.02, flat("BravPickM", (0.90, 0.78, 0.56), rough=0.5)))
    return tilt(parts, -8)


def croquetas():
    mat = grad("Croq", (0.72, 0.40, 0.10), (0.96, 0.68, 0.30), coord="nz", lo=-1, hi=1, rough=0.6, bump=1.0, bump_scale=40,
               vary=0.2)
    parts = []
    for i, (x, y, z, rz) in enumerate(((-0.2, -0.25, 0.25, 15), (0.25, 0.05, 0.25, -10), (0.0, -0.05, 0.66, 40))):
        c = capsule(f"Croq{i}", 0.95, 0.26, 40, 24)
        c.rotation_euler = (0, 0, math.radians(rz))
        c.location = (x, y, z)
        apply_transform(c)
        parts.append(assign(smooth(c), mat))
    return tilt(parts, -10, 0)


def turron():
    from models_mexico import rcube
    bar = rcube("Turron", 0.85, 0.38, 0.22, 7.0, 10)
    bar.location = (0, 0, 0.22)
    apply_transform(bar)
    mat = grad("TurronMat", (0.92, 0.84, 0.64), (1.0, 0.95, 0.80), lo=0.0, hi=0.44, rough=0.35, sss=0.4, coat=0.3)
    assign(bar, mat)
    wafer = flat("TurronWafer", (1.0, 1.0, 0.98), rough=0.6)
    top = box_mesh("TurWafer", 1.66, 0.72, 0.02, 0.43)
    almond = grad("Almond", (0.62, 0.38, 0.18), (0.82, 0.56, 0.32), coord="nz", lo=-1, hi=1, rough=0.4, coat=0.3)
    parts = [bar, assign(top, wafer)]
    for i, (x, y) in enumerate(((-0.5, -0.38), (0.0, -0.38), (0.5, -0.38), (-0.25, -0.39), (0.28, -0.385))):
        z = 0.22 + (0.07 if i < 3 else -0.08)
        parts.append(ball(f"Alm{i}", 0.1, (x, y, z), almond, (1.0, 0.45, 0.62), 20, 12))
    return tilt(parts, -10, 18)


def crema_catalana():
    dish = lathe_obj("CCDish", [(0.0, 0.0), (0.68, 0.0), (0.78, 0.04), (0.82, 0.34), (0.76, 0.36), (0.7, 0.24), (0.0, 0.2)],
                     grad("CCClay", (0.60, 0.26, 0.10), (0.82, 0.44, 0.20), lo=0.0, hi=0.36, rough=0.4, coat=0.5))
    cream = disc("CCTop", 0.72, 0.28, grad("CCCaramel", (0.86, 0.48, 0.08), (0.98, 0.72, 0.24), coord="r", lo=0.0, hi=0.72,
                                            rough=0.03, coat=1.0, vary=0.3, vary_scale=6), h=0.04)
    cinn = rod("CCStick", [(-0.2, 0.2, 0.33), (0.35, -0.05, 0.36)], 0.045, flat("CCCinn", (0.56, 0.28, 0.12), rough=0.6))
    return ground_all(rotate_all([dish, cream, cinn], (math.radians(38), 0, 0)))


def empanada():
    """Эмпанада: полумесяц из теста с защипом по дуге."""
    ob = rounded_disc("Empanada", 0.95, 0.5, 2.2, 32)
    deform(ob, lambda co: Vector((co.x, co.y * 1.0 + 0.0, co.z * (1 - 0.7 * (co.x ** 2 + co.y ** 2) / 0.9) + 0.25)))
    bisect(ob, (0, -0.05, 0), (0, -1, 0))
    push_normals(ob, lambda co, n: 0.015 * fbm(co * 6))
    smooth(ob)
    dough_m = grad("EmpDough", (0.82, 0.48, 0.14), (0.98, 0.74, 0.34), coord="nz", lo=-0.5, hi=1.0, rough=0.4, coat=0.5,
                   vary=0.15)
    assign(ob, dough_m)
    parts = [ob]
    for i in range(15):
        a = math.pi * (0.03 + 0.94 * i / 14)
        parts.append(ball(f"EmpCr{i}", 0.1, (0.93 * math.cos(a), 0.93 * math.sin(a) - 0.02, 0.25), dough_m,
                          (0.6, 1.0, 0.7), 16, 10, (0, 0, a)))
    rotate_all(parts, (math.radians(55), 0, math.radians(-8)))
    return ground_all(parts)


def ensaimada():
    pts = []
    for k in range(140):
        t = k / 139
        a = t * 2.4 * 2 * math.pi
        r = 0.08 + 0.58 * t
        pts.append((r * math.cos(a), r * math.sin(a), 0.2 + 0.18 * (1 - t)))
    mat = grad("Ensa", (0.84, 0.54, 0.20), (0.98, 0.80, 0.48), coord="nz", lo=-0.5, hi=1.0, rough=0.5, sss=0.3)
    add_speckles(mat, (1.0, 1.0, 1.0), scale=30, threshold=0.55, strength=1.0)
    coil = rod("EnsaCoil", pts, 0.18, mat, (0.8, 1.0))
    return ground_all(rotate_all([coil], (math.radians(50), 0, 0)))


def dish_paella():
    import models_recipe as RC
    parts = RC.recipe_paella()
    shrimp_m = grad("PaShrimp", (1.0, 0.42, 0.22), (1.0, 0.68, 0.48), coord="nz", lo=-1, hi=1, rough=0.2, coat=0.8, sss=0.4)
    add_stripes(shrimp_m, (1.0, 0.86, 0.76), scale=5, angle=90, width=0.14, nz_min=-1.0, strength=0.6)
    for i in range(5):
        a = 2 * math.pi * i / 5 + 0.3
        t = torus(f"PaS{i}", 0.2, 0.09, 32, 16)
        bisect(t, (0, 0, 0), (-1, 0, 0))
        t.scale = (1, 1, 0.8)
        t.rotation_euler = (0, 0, a)
        t.location = (0.7 * math.cos(a), 0.7 * math.sin(a), 0.3)
        apply_transform(t)
        parts.append(assign(smooth(t), shrimp_m))
    lemon = cylinder("PaLemon", 0.3, 0.12, 48)
    bisect(lemon, (0, 0, 0), (0, -1, 0))
    lemon.rotation_euler = (math.radians(70), 0, 0)
    lemon.location = (0.0, 0.0, 0.36)
    apply_transform(lemon)
    parts.append(assign(smooth(lemon, 50), material("PaLemonM", [(0.0, (1.0, 0.92, 0.50)), (0.85, (1.0, 0.86, 0.20)),
                                                                 (0.9, (1.0, 0.98, 0.9)), (1.0, (0.98, 0.84, 0.10))],
                                                    coord="r_xz", lo=0.0, hi=0.3, rough=0.2, coat=0.6, sss=0.4)))
    red = flat("PaPepper", (0.86, 0.12, 0.06), rough=0.2, coat=0.7)
    for i in range(6):
        a = 2 * math.pi * i / 6
        parts.append(ball(f"PaP{i}", 0.12, (0.35 * math.cos(a), 0.35 * math.sin(a), 0.27), red, (2.0, 0.4, 0.25), 16, 10,
                          (0, 0, a)))
    return parts


def dish_orange_juice():
    cup = glass_cup("OJCup", 0.42, 0.52, 1.5)
    juice = liquid("OJ", 0.4, 0.49, 0.06, 1.32, grad("OJMat", (1.0, 0.52, 0.04), (1.0, 0.70, 0.16), lo=0.0, hi=1.32,
                                                        rough=0.1, sss=0.6, coat=0.6))
    sl = cylinder("OJSlice", 0.34, 0.08, 48)
    sl.rotation_euler = (math.radians(90), 0, math.radians(10))
    sl.location = (0.5, -0.05, 1.42)
    apply_transform(sl)
    pulp = material("OJPulp", [(0.0, (1.0, 0.78, 0.30)), (0.84, (1.0, 0.56, 0.08)), (0.9, (1.0, 0.96, 0.86)),
                               (1.0, (0.98, 0.50, 0.06))], coord="r_xz", lo=0.0, hi=0.34, rough=0.2, coat=0.7, sss=0.5)
    return [cup, juice, assign(smooth(sl, 50), pulp), straw("OJStraw", -0.12, 0.05, 0.4, 2.0, (0.20, 0.62, 0.30), 12)]


def dish_spanish_omelette():
    p = plate_round("SOPlate", 1.2, (0.97, 0.97, 0.98), (0.16, 0.34, 0.70))
    outer = grad("SOOuter", (0.86, 0.56, 0.14), (0.98, 0.78, 0.32), coord="nz", lo=-0.5, hi=1.0, rough=0.35, coat=0.5,
                 vary=0.3, vary_scale=4)
    inner = grad("SOInner", (1.0, 0.86, 0.46), (1.0, 0.94, 0.66), coord="z", lo=0.1, hi=0.5, rough=0.5, sss=0.3)
    add_speckles(inner, (0.98, 0.98, 0.86), scale=14, threshold=0.6, strength=0.8)

    def piece(name, planes, shift=(0, 0, 0)):
        ob = rounded_disc(name, 0.9, 0.42, 3.0, 32)
        ob.location = (0, 0, 0.32)
        apply_transform(ob)
        push_normals(ob, lambda co, n: 0.02 * fbm(co * 4))
        for no in planes:
            bisect(ob, (0, 0, 0), no)
        ob.location = shift
        apply_transform(ob)
        smooth(ob)
        return assign_faces(ob, outer, [(lambda n, c: abs(n.z) < 0.3 and math.hypot(c.x - shift[0], c.y - shift[1]) < 0.84,
                                         inner)])
    # торт без клина = две половины по разным плоскостям, клин выдвинут вперед
    n1, n2 = (0.5, -0.86, 0), (-0.5, -0.86, 0)
    a = piece("SOCakeA", [n1])
    b = piece("SOCakeB", [n2])
    w = piece("SOWedge", [(-0.5, 0.86, 0), (0.5, 0.86, 0)], (0.0, -0.3, 0.0))
    return [p, a, b, w]


def dish_gazpacho():
    b, h = bowl("GzBowl", 0.95, 0.55, ((0.82, 0.90, 0.96), (0.96, 0.98, 1.0)), band=(0.20, 0.42, 0.76))
    soup = curry_in("GzSoup", 0.9, h - 0.05, (0.86, 0.22, 0.10), (0.96, 0.42, 0.20))
    cuke = grad("GzCuke", (0.40, 0.70, 0.22), (0.80, 0.94, 0.50), coord="nz", lo=-1, hi=1, rough=0.3, coat=0.5)
    pep = flat("GzPep", (0.98, 0.84, 0.18), rough=0.3, coat=0.5)
    oil = flat("GzOil", (0.80, 0.70, 0.14), rough=0.05, coat=1.0)
    from models_mexico import rcube
    parts = [b, soup]
    rnd = random.Random(6)
    for i in range(10):
        a, r = rnd.uniform(0, 6.28), 0.55 * math.sqrt(rnd.random())
        c = rcube(f"GzC{i}", 0.06, 0.06, 0.05, 5.0, 4)
        c.location = (r * math.cos(a), r * math.sin(a), h - 0.0)
        apply_transform(c)
        parts.append(assign(c, cuke if i % 2 else pep))
    pts = [(0.4 * math.cos(t * 4), 0.3 * math.sin(t * 4), h - 0.02) for t in [k / 25 for k in range(26)]]
    parts.append(rod("GzDrizzle", pts, 0.02, oil))
    basil = flat("GzBasil", (0.24, 0.60, 0.20), rough=0.3, coat=0.5)
    parts.append(leaf_blob("GzLf", 0.16, 0.1, basil, (0.0, 0.05, h + 0.0), (0.2, 0, 0.4), cup=0.05))
    return parts


def dish_gambas():
    dish = lathe_obj("GamDish", [(0.0, 0.0), (0.8, 0.0), (0.95, 0.06), (1.05, 0.36), (1.0, 0.4), (0.92, 0.3), (0.0, 0.22)],
                     grad("GamClay", (0.58, 0.24, 0.10), (0.82, 0.42, 0.18), lo=0.0, hi=0.4, rough=0.4, coat=0.5))
    oil = disc("GamOil", 0.94, 0.3, grad("GamOilM", (0.92, 0.56, 0.08), (1.0, 0.74, 0.20), coord="r", hi=0.94, rough=0.02,
                                          coat=1.0, sss=0.3), h=0.03)
    shrimp_m = grad("GamShrimp", (1.0, 0.42, 0.22), (1.0, 0.68, 0.48), coord="nz", lo=-1, hi=1, rough=0.15, coat=0.9, sss=0.4)
    add_stripes(shrimp_m, (1.0, 0.86, 0.76), scale=5, angle=90, width=0.14, nz_min=-1.0, strength=0.6)
    parts = [dish, oil]
    for i in range(6):
        a = 2 * math.pi * i / 6
        t = torus(f"GamS{i}", 0.22, 0.1, 32, 16)
        bisect(t, (0, 0, 0), (-1, 0, 0))
        t.rotation_euler = (0, 0, a)
        t.location = (0.5 * math.cos(a), 0.5 * math.sin(a), 0.36)
        apply_transform(t)
        parts.append(assign(smooth(t), shrimp_m))
    garlic_m = flat("GamGarlic", (1.0, 0.94, 0.78), rough=0.3, sss=0.4)
    chili = flat("GamChili", (0.82, 0.06, 0.04), rough=0.2, coat=0.8)
    leaf = flat("GamParsley", (0.24, 0.60, 0.18), rough=0.3, coat=0.5)
    rnd = random.Random(1)
    for i in range(10):
        a, r = rnd.uniform(0, 6.28), 0.35 * math.sqrt(rnd.random())
        m = (garlic_m, chili, leaf)[i % 3]
        parts.append(ball(f"GamG{i}", 0.05, (r * math.cos(a), r * math.sin(a), 0.34), m, (1.4, 1.0, 0.5), 12, 8))
    return parts


def dish_bocadillo():
    bread = grad("BocBread", (0.80, 0.46, 0.14), (0.96, 0.70, 0.34), coord="nz", lo=-0.5, hi=1.0, rough=0.5, coat=0.3,
                 vary=0.2)
    crumb = flat("BocCrumb", (1.0, 0.94, 0.80), rough=0.7)
    bottom = capsule("BocBot", 2.4, 0.3, 64, 32, pinch=0.3)
    bisect(bottom, (0, 0, 0), (0, 0, 1))
    bottom.location = (0, 0, 0.3)
    apply_transform(bottom)
    assign_faces(smooth(bottom), bread, [(lambda n, c: n.z > 0.8, crumb)])
    top = capsule("BocTop", 2.4, 0.3, 64, 32, pinch=0.3)
    bisect(top, (0, 0, 0), (0, 0, -1))
    top.location = (0, 0.05, 0.52)
    top.rotation_euler = (math.radians(-12), 0, 0)
    apply_transform(top)
    assign_faces(smooth(top), bread, [(lambda n, c: n.z < -0.8, crumb)])
    chor = grad("BocChor", (0.70, 0.12, 0.06), (0.88, 0.26, 0.12), coord="r_xz", lo=0.0, hi=0.24, rough=0.3, coat=0.5)
    add_speckles(chor, (1.0, 0.88, 0.80), scale=40, threshold=0.66, strength=0.8)
    pep = flat("BocPep", (0.92, 0.12, 0.06), rough=0.15, coat=0.8)
    parts = [bottom, top]
    for i in range(6):
        x = -0.85 + i * 0.34
        s = cylinder(f"BocC{i}", 0.22, 0.04, 32)
        s.rotation_euler = (math.radians(-60), 0, 0)
        s.location = (x, -0.12, 0.36)
        apply_transform(s)
        parts.append(assign(smooth(s, 50), chor))
    for i in range(3):
        x = -0.6 + i * 0.6
        parts.append(ball(f"BocP{i}", 0.25, (x + 0.15, -0.2, 0.33), pep, (1.0, 0.4, 0.12), 24, 12, (0.6, 0, 0)))
    return rotate_all(parts, (0, 0, math.radians(-12)))


M.MODELS.update({
    "saffron": saffron, "potato": potato, "garlic": garlic, "chorizo": chorizo, "pepper": pepper, "orange": orange,
    "patatas_bravas": patatas_bravas, "croquetas": croquetas, "turron": turron, "crema_catalana": crema_catalana,
    "empanada": empanada, "ensaimada": ensaimada,
    "dish_paella": dish_paella, "dish_orange_juice": dish_orange_juice, "dish_spanish_omelette": dish_spanish_omelette,
    "dish_gazpacho": dish_gazpacho, "dish_gambas": dish_gambas, "dish_bocadillo": dish_bocadillo,
})


# MARK: - Греческая кухня (биом 10)

def feta():
    from models_mexico import rcube
    blk = rcube("Feta", 0.6, 0.45, 0.3, 6.0, 10)
    blk.location = (0, 0, 0.3)
    apply_transform(blk)
    push_normals(blk, lambda co, n: 0.012 * fbm(co * 9))
    mat = grad("FetaMat", (0.94, 0.94, 0.90), (1.0, 1.0, 0.98), lo=0.0, hi=0.6, rough=0.5, sss=0.5, bump=0.6,
               bump_scale=35)
    assign(smooth(blk), mat)
    oil = flat("FetaOil", (0.84, 0.74, 0.20), rough=0.05, coat=1.0)
    herb = flat("FetaHerb", (0.30, 0.46, 0.16), rough=0.5)
    parts = [blk, ball("FetaOilP", 0.32, (0.05, 0.0, 0.6), oil, (1.3, 1.0, 0.06), 32, 12)]
    rnd = random.Random(3)
    for i in range(16):
        parts.append(ball(f"FetaH{i}", 0.022, (rnd.uniform(-0.45, 0.45), rnd.uniform(-0.3, 0.3), 0.61), herb, (1.6, 1, 0.5),
                          8, 6))
    return tilt(parts, -16, 15)


def pita():
    """Стопка пит с карманом."""
    mat = grad("PitaMat", (0.92, 0.74, 0.44), (0.99, 0.88, 0.64), coord="nz", lo=-1, hi=1, rough=0.55, sss=0.3, sheen=0.3)
    add_speckles(mat, (0.62, 0.40, 0.18), scale=8, threshold=0.72, strength=0.7)
    parts = []
    for i in range(3):
        d = rounded_disc(f"Pita{i}", 0.85, 0.14, 2.6, 28)
        d.location = (0.04 * i, -0.02 * i, 0.07 + 0.13 * i)
        apply_transform(d)
        push_normals(d, lambda co, n: 0.015 * fbm(co * 4 + Vector((i, 0, 0))))
        parts.append(assign(smooth(d), mat))
    return ground_all(rotate_all(parts, (math.radians(48), 0, math.radians(-10))))


def lamb():
    """Ребрышко ягненка на косточке."""
    meat = grad("LambMeat", (0.56, 0.24, 0.12), (0.80, 0.46, 0.26), coord="nz", lo=-0.5, hi=1.0, rough=0.35, coat=0.6,
                bump=0.4, bump_scale=10)
    add_stripes(meat, (0.36, 0.16, 0.08), scale=3.0, angle=45, width=0.12, nz_min=0.5, strength=0.8)
    fat = flat("LambFat", (0.98, 0.92, 0.80), rough=0.4, sss=0.4)
    bone = flat("LambBone", (0.98, 0.96, 0.90), rough=0.35, sss=0.3)
    ob = rounded_disc("LambChop", 0.6, 0.3, 2.8, 24)
    deform(ob, lambda co: Vector((co.x * (1 + 0.2 * co.y), co.y * 0.9, co.z + 0.15)))
    push_normals(ob, lambda co, n: 0.015 * fbm(co * 5))
    assign(smooth(ob), meat)
    rim = torus("LambFatRim", 0.56, 0.07, 64, 12)
    rim.scale = (1.0, 0.9, 1.0)
    rim.location = (0, 0, 0.15)
    apply_transform(rim)
    bisect(rim, (0, 0.1, 0), (0, 1, 0))
    parts = [ob, assign(smooth(rim), fat)]
    parts.append(rod("LambBone", [(0.0, 0.3, 0.15), (0.0, 1.15, 0.2)], 0.075, bone))
    parts.append(ball("LambKnob", 0.12, (0.0, 1.18, 0.2), bone, (1.3, 1, 1)))
    return ground_all(rotate_all(parts, (math.radians(42), 0, math.radians(-35))))


def eggplant():
    skin = grad("Eggplant", (0.22, 0.06, 0.26), (0.46, 0.18, 0.50), coord="nz", lo=-1, hi=1, rough=0.1, coat=1.0,
                coat_rough=0.02, sss=0.2)
    ob = sphere("Eggplant", 1.0, 72, 48)

    def shape(co):
        t = min(1.0, max(0.0, (co.x + 1) / 2))
        k = 0.32 + 0.3 * t ** 1.4
        return Vector((co.x * 0.95 + 0.12 * (1 - t) ** 2, co.y * k, co.z * k + 0.2 * (1 - t) ** 2))
    deform(ob, shape)
    assign(smooth(ob), skin)
    green = grad("EggpCap", (0.24, 0.44, 0.14), (0.42, 0.62, 0.22), coord="x", lo=-1.1, hi=-0.8, rough=0.4, coat=0.3)
    cap = sphere("EggpCapS", 0.3, 32, 16)

    def cshape(co):
        a = math.atan2(co.z, co.y)
        k = 1 + 0.25 * math.cos(a * 5)
        return Vector((co.x * 0.7 - 0.95, co.y * k, co.z * k + 0.25))
    deform(cap, cshape)
    bisect(cap, (-1.0, 0, 0), (1, 0, 0))
    stem = rod("EggpStem", [(-1.05, 0, 0.25), (-1.3, 0, 0.35)], 0.06, green)
    parts = [ob, assign(smooth(cap), green), stem]
    rotate_all(parts, (0, math.radians(-10), math.radians(-20)))
    return ground_all(parts)


def yogurt():
    pot = lathe_obj("YogPot", [(0.0, 0.0), (0.5, 0.0), (0.56, 0.06), (0.62, 0.8), (0.66, 0.84), (0.6, 0.86), (0.55, 0.8),
                               (0.0, 0.7)], grad("YogPotMat", (0.86, 0.90, 0.96), (0.98, 0.99, 1.0), lo=0.0, hi=0.86,
                                                 rough=0.25, coat=0.6))
    band = lathe_obj("YogBand", [(0.575, 0.3), (0.595, 0.32), (0.61, 0.55), (0.59, 0.57)],
                     flat("YogBandMat", (0.16, 0.38, 0.76), rough=0.3), 72, 0)
    cream = mound("YogTop", 0.58, 0.2, grad("YogCream", (0.98, 0.98, 0.96), (1.0, 1.0, 1.0), lo=0.8, hi=1.0, rough=0.3,
                                            sss=0.6), z=0.78, bumps=0.02)
    honey = flat("YogHoney", (0.96, 0.66, 0.10), rough=0.03, coat=1.0, sss=0.3)
    pts = [(0.25 * math.cos(t * 6.28) * (1 - t * 0.5), 0.25 * math.sin(t * 6.28) * (1 - t * 0.5), 0.94 + 0.03 * t)
           for t in [k / 30 for k in range(31)]]
    spoon = rod("YogSpoon", [(0.2, 0.1, 0.9), (0.6, 0.3, 1.5)], 0.04, flat("YogSpoonM", (0.86, 0.87, 0.9), rough=0.2,
                                                                              metal=0.8))
    return tilt([pot, band, cream, rod("YogDrip", pts, 0.04, honey), spoon], -10)


def baklava():
    pastry = grad("Baklava", (0.80, 0.46, 0.12), (0.98, 0.74, 0.32), coord="z", lo=0.0, hi=0.5, rough=0.15, coat=0.9,
                  sss=0.3)
    add_stripes(pastry, (0.62, 0.34, 0.08), scale=10, angle=0, width=0.1, nz_min=-1.0, strength=0.5)
    nut = grad("Pistachio", (0.40, 0.62, 0.20), (0.62, 0.80, 0.32), coord="nz", lo=-1, hi=1, rough=0.4)
    parts = []
    for i, (x, y, z) in enumerate(((-0.45, 0.0, 0.0), (0.45, 0.0, 0.0), (0.0, 0.1, 0.42))):
        pts = [(0.48, 0.0), (0.0, 0.32), (-0.48, 0.0), (0.0, -0.32)]
        pr = profile_prism(f"Bak{i}", pts, 0.38, 0.0)
        bevel(pr, 0.04, 3)
        subdivide(pr, 1)
        pr.location = (x, y, z)
        apply_transform(pr)
        parts.append(assign(smooth(pr, 40), pastry))
        parts.append(mound(f"BakN{i}", 0.14, 0.08, nut, z=z + 0.37, bumps=0.02))
        parts[-1].location = (x, y, 0)
    return tilt(parts, -16, 10)


def koulouri():
    ring = torus("Koulouri", 0.62, 0.17, 96, 24)
    ring.location = (0, 0, 0.17)
    apply_transform(ring)
    push_normals(ring, lambda co, n: 0.015 * fbm(co * 5))
    mat = grad("KoulMat", (0.74, 0.40, 0.12), (0.92, 0.62, 0.28), coord="nz", lo=-1, hi=1, rough=0.4, coat=0.5)
    add_speckles(mat, (1.0, 0.94, 0.78), scale=55, threshold=0.6, strength=1.0)
    assign(smooth(ring), mat)
    return ground_all(rotate_all([ring], (math.radians(55), 0, 0)))


def frappe():
    cup = glass_cup("FrapCup", 0.4, 0.52, 1.6)
    coffee = liquid("FrapCoffee", 0.38, 0.46, 0.06, 1.0, grad("FrapCofM", (0.36, 0.18, 0.08), (0.56, 0.32, 0.16), lo=0.0,
                                                                  hi=1.0, rough=0.1, coat=0.6, sss=0.3))
    foam = liquid("FrapFoam", 0.46, 0.5, 1.0, 1.48, grad("FrapFoamM", (0.86, 0.70, 0.50), (0.96, 0.88, 0.74), lo=1.0,
                                                         hi=1.48, rough=0.6, sss=0.5, bump=0.3, bump_scale=40))
    ice = grad("FrapIce", (0.92, 0.96, 1.0), (1, 1, 1), rough=0.05, transmission=0.8, coat=0.5)
    parts = [cup, coffee, foam]
    for i, (x, y, z) in enumerate(((0.15, -0.15, 0.7), (-0.18, -0.1, 0.5), (0.05, 0.15, 0.85))):
        b = box_mesh(f"FrapIce{i}", 0.22, 0.22, 0.22, z)
        b.location = (x, y, 0)
        bevel(b, 0.04, 2)
        apply_transform(b)
        parts.append(assign(smooth(b), ice))
    parts.append(straw("FrapStraw", 0.12, 0.0, 0.4, 2.2, (0.20, 0.42, 0.80), 10))
    return parts


def loukoumades():
    b, h = bowl("LoukBowl", 0.9, 0.4, ((0.20, 0.38, 0.72), (0.96, 0.97, 0.98)), foot=False)
    ballm = grad("Louk", (0.78, 0.44, 0.10), (0.96, 0.70, 0.28), coord="nz", lo=-1, hi=1, rough=0.06, coat=1.0, sss=0.3)
    honey = flat("LoukHoney", (0.92, 0.58, 0.08), rough=0.03, coat=1.0)
    cinn = flat("LoukCinn", (0.48, 0.24, 0.10), rough=0.6)
    parts = [b]
    pos = [(-0.35, -0.15, h), (0.3, -0.2, h), (0.0, 0.3, h), (-0.05, -0.05, h + 0.3), (0.35, 0.2, h - 0.02)]
    for i, (x, y, z) in enumerate(pos):
        o = ball(f"Louk{i}", 0.25, (x, y, z), ballm, (1, 1, 0.92), 40, 24)
        push_normals(o, lambda co, n: 0.02 * fbm(co * 6))
        parts.append(o)
    pts = [(-0.4 + 0.8 * t, 0.15 * math.sin(t * 9), h + 0.42 - 0.1 * abs(math.sin(t * 3))) for t in [k / 30 for k in range(31)]]
    parts.append(rod("LoukDrizzle", pts, 0.035, honey))
    rnd = random.Random(2)
    for i in range(14):
        parts.append(ball(f"LoukC{i}", 0.02, (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.3, 0.3), h + 0.5), cinn, segs=8,
                          rings=6))
    return tilt(parts, -10)


def figs():
    skin = grad("Fig", (0.30, 0.10, 0.24), (0.52, 0.24, 0.40), coord="z", lo=0.0, hi=1.0, rough=0.35, coat=0.4, sss=0.3,
                vary=0.2)
    parts = []
    whole = sphere("Fig", 0.5, 64, 40)

    def shape(co):
        t = min(1.0, max(0.0, (co.z / 0.5 + 1) / 2))
        k = 1.0 - 0.6 * max(0.0, t - 0.55) ** 1.1
        return Vector((co.x * k, co.y * k, co.z * 1.1 + 0.55 + 0.25 * max(0.0, t - 0.7)))
    deform(whole, shape)
    whole.location = (-0.3, 0.15, 0)
    apply_transform(whole)
    parts.append(assign(smooth(whole), skin))
    parts.append(rod("FigStem", [(-0.3, 0.15, 1.22), (-0.25, 0.15, 1.36)], 0.04, flat("FigStemM", (0.40, 0.46, 0.20),
                                                                                          rough=0.5)))
    half = sphere("FigHalf", 0.45, 64, 40)
    deform(half, shape)
    bisect(half, (0, 0, 0), (0, 1, 0))
    half.rotation_euler = (math.radians(80), 0, math.radians(10))
    half.location = (0.45, -0.25, 0.3)
    apply_transform(half)
    pulp = grad("FigPulp", (0.88, 0.20, 0.28), (1.0, 0.70, 0.62), coord="z", lo=0.2, hi=0.7, rough=0.3, sss=0.5, coat=0.4)
    add_speckles(pulp, (1.0, 0.92, 0.70), scale=30, threshold=0.62, strength=0.9)
    assign_faces(half, skin, [(lambda n, c: n.y < -0.5 or n.z > 0.6, pulp)])
    parts.append(smooth(half))
    return ground_all(parts)


def melomakarona():
    mat = grad("Melo", (0.52, 0.26, 0.08), (0.80, 0.48, 0.18), coord="nz", lo=-1, hi=1, rough=0.2, coat=0.8, sss=0.2)
    nut = grad("MeloNut", (0.62, 0.42, 0.22), (0.86, 0.66, 0.42), coord="nz", lo=-1, hi=1, rough=0.6)
    parts = []
    for i, (x, y, z, rz) in enumerate(((-0.35, 0.0, 0.0, 10), (0.38, 0.05, 0.0, -15), (0.0, 0.0, 0.34, 80))):
        o = sphere(f"Melo{i}", 1.0, 48, 30)
        o.scale = (0.42, 0.28, 0.2)
        o.rotation_euler = (0, 0, math.radians(rz))
        o.location = (x, y, z + 0.2)
        apply_transform(o)
        push_normals(o, lambda co, n: 0.012 * fbm(co * 8))
        parts.append(assign(smooth(o), mat))
        rnd = random.Random(i)
        for k in range(10):
            parts.append(ball(f"MeloN{i}{k}", 0.035, (x + rnd.uniform(-0.25, 0.25), y + rnd.uniform(-0.15, 0.15), z + 0.39),
                              nut, (1.3, 1.0, 0.7), 10, 6, (rnd.uniform(0, 3), 0, 0)))
    return tilt(parts, -18)


def dish_spanakopita():
    p = plate_round("SPPlate", 1.2, (0.97, 0.97, 0.98), (0.16, 0.34, 0.70))
    phyllo = grad("SPPhyllo", (0.86, 0.56, 0.18), (0.98, 0.80, 0.42), coord="nz", lo=-0.5, hi=1.0, rough=0.35, coat=0.5,
                  bump=0.6, bump_scale=14)
    green = grad("SPGreen", (0.20, 0.42, 0.12), (0.36, 0.60, 0.22), lo=0.15, hi=0.5, rough=0.5)
    add_speckles(green, (1.0, 1.0, 0.96), scale=12, threshold=0.6, strength=0.9)
    parts = [p]
    for i, (x, y, rz) in enumerate(((-0.42, 0.1, 10), (0.4, -0.05, -20), (0.0, 0.45, 70))):
        pts = [(-0.45, -0.32), (0.45, -0.32), (0.0, 0.42)]
        pr = profile_prism(f"SP{i}", pts, 0.38, 0.1)
        bevel(pr, 0.05, 3)
        subdivide(pr, 2)
        pr.rotation_euler = (0, 0, math.radians(rz))
        pr.location = (x, y, 0.0 if i < 2 else 0.1)
        apply_transform(pr)
        push_normals(pr, lambda co, n: 0.015 * fbm(co * 6))
        smooth(pr)
        assign_faces(pr, phyllo, [(lambda n, c: abs(n.z) < 0.4 and 0.2 < c.z < 0.42, green)])
        parts.append(pr)
    return parts


def dish_greek_salad():
    b, h = bowl("GSBowl", 1.0, 0.5, ((0.92, 0.94, 0.98), (1.0, 1.0, 1.0)), band=(0.16, 0.36, 0.74))
    lettuce = disc("GSBase", 0.92, h - 0.05, flat("GSBaseM", (0.56, 0.80, 0.30), rough=0.4), wobble=0.03)
    tom = grad("GSTom", (0.82, 0.10, 0.06), (0.98, 0.30, 0.16), coord="nz", lo=-1, hi=1, rough=0.15, coat=0.8, sss=0.4)
    cuke = material("GSCuke", [(0.0, (0.92, 0.98, 0.72)), (0.8, (0.76, 0.90, 0.46)), (0.85, (0.20, 0.50, 0.14)),
                               (1.0, (0.20, 0.50, 0.14))], coord="r_xz", lo=0.0, hi=0.17, rough=0.2, coat=0.6, sss=0.4)
    olive = flat("GSOlive", (0.18, 0.10, 0.16), rough=0.1, coat=0.9)
    onion = flat("GSOnion", (0.78, 0.40, 0.66), rough=0.2, coat=0.6, sss=0.4)
    from models_mexico import rcube
    parts = [b, lettuce]
    rnd = random.Random(10)
    for i in range(7):
        a = 2 * math.pi * i / 7 + 0.2
        r = 0.62
        w = sphere(f"GSt{i}", 0.17, 32, 20)
        bisect(w, (0, 0, 0), (0, 0, -1))
        w.rotation_euler = (rnd.uniform(-0.6, 0.6), rnd.uniform(-0.6, 0.6), a)
        w.location = (r * math.cos(a), r * math.sin(a), h + 0.0)
        apply_transform(w)
        parts.append(assign(smooth(w), tom))
    for i in range(6):
        a = 2 * math.pi * i / 6 + 0.6
        c = cylinder(f"GSc{i}", 0.17, 0.07, 32)
        c.rotation_euler = (math.radians(60) + rnd.uniform(-0.3, 0.3), 0, a)
        c.location = (0.36 * math.cos(a), 0.36 * math.sin(a), h + 0.08)
        apply_transform(c)
        parts.append(assign(smooth(c, 50), cuke))
    for i in range(6):
        a = rnd.uniform(0, 6.28)
        parts.append(ball(f"GSo{i}", 0.08, (0.5 * math.cos(a), 0.5 * math.sin(a), h + 0.15), olive, (1, 1, 1.3), 20, 12))
    for i in range(4):
        t = torus(f"GSon{i}", 0.13, 0.02, 32, 8)
        t.rotation_euler = (rnd.uniform(-0.4, 0.4), 0, 0)
        t.location = (rnd.uniform(-0.4, 0.4), rnd.uniform(-0.4, 0.4), h + 0.17)
        apply_transform(t)
        parts.append(assign(smooth(t), onion))
    f = rcube("GSFeta", 0.32, 0.24, 0.12, 6.0, 8)
    f.location = (0, 0, h + 0.28)
    f.rotation_euler = (0, 0, 0.4)
    apply_transform(f)
    parts.append(assign(f, grad("GSFetaM", (0.94, 0.94, 0.90), (1.0, 1.0, 0.98), lo=h + 0.1, hi=h + 0.4, rough=0.5,
                                sss=0.5, bump=0.5, bump_scale=35)))
    herb = flat("GSHerb", (0.30, 0.46, 0.16), rough=0.5)
    for i in range(10):
        parts.append(ball(f"GSh{i}", 0.02, (rnd.uniform(-0.25, 0.25), rnd.uniform(-0.18, 0.18), h + 0.41), herb, segs=8,
                          rings=6))
    return parts


def dish_gyros():
    """Гирос в пите, завернутый в бумагу."""
    pita_m = grad("GyPita", (0.90, 0.70, 0.40), (0.99, 0.86, 0.60), coord="nz", lo=-1, hi=1, rough=0.55, sss=0.3)
    add_speckles(pita_m, (0.62, 0.40, 0.18), scale=8, threshold=0.72, strength=0.7)
    paper = grad("GyPaper", (0.96, 0.94, 0.90), (1.0, 1.0, 0.98), lo=0.0, hi=1.0, rough=0.6)
    add_stripes(paper, (0.16, 0.36, 0.74), scale=3, angle=0, width=0.12, nz_min=-1.0, strength=0.9)
    cone = lathe_obj("GyPaperC", [(0.0, 0.0), (0.12, 0.0), (0.55, 1.0), (0.53, 1.0), (0.1, 0.03), (0.0, 0.03)], paper, 64, 1)
    wrap = lathe_obj("GyWrap", [(0.0, 0.2), (0.2, 0.2), (0.62, 1.25), (0.58, 1.28), (0.0, 1.0)], pita_m, 64, 1)
    meat = grad("GyMeat", (0.48, 0.22, 0.08), (0.72, 0.40, 0.16), coord="nz", lo=-1, hi=1, rough=0.35, coat=0.5,
                bump=0.4, bump_scale=10)
    tom = flat("GyTom", (0.90, 0.16, 0.08), rough=0.2, coat=0.6)
    onion = flat("GyOnion", (0.98, 0.94, 0.96), rough=0.2, sss=0.4)
    fry = grad("GyFry", (0.96, 0.74, 0.24), (1.0, 0.88, 0.46), lo=1.1, hi=1.7, rough=0.4)
    sauce = flat("GySauce", (1.0, 1.0, 0.96), rough=0.3, sss=0.4)
    parts = [cone, wrap]
    rnd = random.Random(4)
    for i in range(10):
        a, r = rnd.uniform(0, 6.28), 0.35 * math.sqrt(rnd.random())
        parts.append(ball(f"GyM{i}", 0.13, (r * math.cos(a), r * math.sin(a), 1.25 + 0.05 * (i % 3)), meat, (1.5, 0.6, 0.4),
                          16, 10, (rnd.uniform(-0.5, 0.5), 0, a)))
    for i in range(3):
        a = 2.1 * i
        parts.append(ball(f"GyT{i}", 0.12, (0.3 * math.cos(a), 0.3 * math.sin(a) - 0.1, 1.37), tom, (1.0, 1.0, 0.4), 16, 10))
    for i in range(5):
        a = rnd.uniform(0, 6.28)
        parts.append(rod(f"GyF{i}", [(0.15 * math.cos(a), 0.15 * math.sin(a), 1.2),
                                     (0.25 * math.cos(a), 0.25 * math.sin(a), 1.75)], 0.045, fry))
    parts.append(ball("GySauce", 0.18, (0.0, -0.1, 1.42), sauce, (1.2, 1.0, 0.3), 24, 12))
    t = torus("GyOn", 0.12, 0.02, 24, 8)
    t.location = (0.12, -0.2, 1.46)
    apply_transform(t)
    parts.append(assign(smooth(t), onion))
    return rotate_all(parts, (0, math.radians(-8), 0))


def dish_tzatziki():
    b, h = bowl("TzBowl", 0.95, 0.5, ((0.20, 0.38, 0.72), (0.98, 0.98, 1.0)))
    cream = mound("TzCream", 0.88, 0.18, grad("TzCreamM", (0.96, 0.97, 0.94), (1.0, 1.0, 1.0), lo=h, hi=h + 0.2, rough=0.35,
                                             sss=0.6), z=h - 0.06, bumps=0.025)
    cuke = flat("TzCuke", (0.40, 0.68, 0.24), rough=0.3, coat=0.5)
    oil = flat("TzOil", (0.80, 0.70, 0.12), rough=0.05, coat=1.0)
    dill = flat("TzDill", (0.30, 0.56, 0.18), rough=0.4)
    parts = [b, cream]
    rnd = random.Random(8)
    for i in range(20):
        a, r = rnd.uniform(0, 6.28), 0.6 * math.sqrt(rnd.random())
        z = h - 0.06 + 0.18 * (1 - (r / 0.88) ** 2.2) ** 0.45 + 0.01
        parts.append(ball(f"TzC{i}", 0.03, (r * math.cos(a), r * math.sin(a), z), cuke, (1.4, 1.0, 0.5), 8, 6))
    parts.append(ball("TzOilPool", 0.2, (0.0, 0.0, h + 0.12), oil, (1.3, 1.0, 0.08), 32, 10))
    for i in range(5):
        a = i * 1.25
        parts.append(rod(f"TzD{i}", [(0.05 * math.cos(a), 0.05 * math.sin(a), h + 0.14),
                                     (0.22 * math.cos(a), 0.22 * math.sin(a), h + 0.16)], 0.012, dill))
    olive = flat("TzOlive", (0.18, 0.10, 0.16), rough=0.1, coat=0.9)
    parts.append(ball("TzOl", 0.07, (0.12, -0.1, h + 0.16), olive, (1, 1, 1.3), 16, 10))
    return parts


def dish_moussaka():
    dish = lathe_obj("MsDish", [(0.0, 0.0), (0.9, 0.0), (1.0, 0.06), (1.08, 0.5), (1.02, 0.52), (0.95, 0.12), (0.0, 0.1)],
                     grad("MsClay", (0.62, 0.30, 0.12), (0.86, 0.50, 0.24), lo=0.0, hi=0.52, rough=0.35, coat=0.6),
                     segs=4, sub=2)
    dish.rotation_euler = (0, 0, math.radians(45))
    apply_transform(dish)
    layers = [(0.1, 0.2, (0.36, 0.14, 0.28), (0.52, 0.24, 0.40)), (0.2, 0.32, (0.48, 0.22, 0.10), (0.66, 0.34, 0.16)),
              (0.32, 0.4, (0.36, 0.14, 0.28), (0.52, 0.24, 0.40)), (0.4, 0.58, (0.96, 0.84, 0.56), (1.0, 0.94, 0.74))]
    parts = [dish]
    for i, (z0, z1, c0, c1) in enumerate(layers):
        blk = box_mesh(f"MsL{i}", 1.36, 1.36, z1 - z0, z0, cuts=4)
        bevel(blk, 0.03 if i < 3 else 0.08, 3)
        m = grad(f"MsLM{i}", c0, c1, lo=z0, hi=z1, rough=0.4 if i < 3 else 0.35, coat=0.4, sss=0.3)
        if i == 3:
            add_speckles(m, (0.80, 0.52, 0.18), scale=7, threshold=0.62, strength=0.9)
            push_normals(blk, lambda co, n: 0.02 * fbm(co * 4) if n.z > 0.5 else 0.0)
        parts.append(assign(smooth(blk, 40), m))
    # вырезанный кусок спереди открывает слои
    for o in parts[1:]:
        bisect(o, (0.0, -0.25, 0), (0, -1, 0))
    herb = flat("MsHerb", (0.30, 0.56, 0.18), rough=0.4)
    parts.append(leaf_blob("MsLf", 0.12, 0.07, herb, (0.1, 0.1, 0.62), (0, 0, 0.6), cup=0.03))
    return parts


M.MODELS.update({
    "feta": feta, "pita": pita, "lamb": lamb, "eggplant": eggplant, "yogurt": yogurt,
    "baklava": baklava, "koulouri": koulouri, "frappe": frappe, "loukoumades": loukoumades, "figs": figs,
    "melomakarona": melomakarona,
    "dish_spanakopita": dish_spanakopita, "dish_greek_salad": dish_greek_salad, "dish_gyros": dish_gyros,
    "dish_tzatziki": dish_tzatziki, "dish_moussaka": dish_moussaka,
})
