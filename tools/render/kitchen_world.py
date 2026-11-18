"""Фоны кухонь 6-10: Китай, Индия, Корея, Испания, Греция.

Подключается из environment.py после kitchen_themes.py. Каждая кухня - своя плитка и шкафчики (STYLES в environment.py)
и своя раскладка: утварь из kitchen.py плюс продукты и блюда самой кухни (модели из models_world.py) на полке
и столешнице.
"""
import math

import kitchen as K
import kitchen_themes as KT
from kitchen import Cn, L, ceramic, glass_jar, metal, put

prod = KT.prod


def dress_china(st, kenney, metal_mat):
    """Китай: красная плитка, бамбуковые пароварки, чайник, бок-чой, баоцзы и бабл-ти."""
    P = []
    P += K.hang_utensils(kenney, metal_mat)
    blue = (0.12, 0.26, 0.62)
    P += L(K.bowl_stack("Bowls", 3, 0.17, 0.11, ceramic("BowlW", (0.98, 0.97, 0.94)), ceramic("BowlRim", blue)), -1.84, 0.24)
    P += put(K.deco_plate("Plate", 0.3, (0.98, 0.97, 0.94), blue), -1.2, 0.47, K.LEDGE_TOP + 0.3 * 0.97, rx=math.radians(76))
    P += L(glass_jar("Rice", 0.4, 0.1, "rice", 0.75, lid="wood"), -1.24, 0.14)
    P += L(prod("soybeans", 0.2), -0.55, 0.24)
    P += L(prod("bubble_tea", 0.24), 0.05, 0.24)
    P += L(prod("tanghulu", 0.3, rz=0.3), 0.6, 0.24)
    P += L(K.terracotta_pot("Pot2", 0.1, 0.16) + put(K.herb_plant("Scallion", 0.1, 0.16, n=10, seed=8, pot=False), 0, 0, -0.02),
           1.1, 0.26)
    P += L(prod("fortune_cookie", 0.16), 1.75, 0.24)
    P += Cn(prod("dish_dim_sum", 0.42), -1.55, -0.2)
    P += Cn(prod("bok_choy", 0.22, rz=0.4), -0.75, -0.1)
    P += Cn(prod("bao", 0.18), 0.0, -0.35)
    P += Cn(K.kettle("Kettle", (0.20, 0.42, 0.30)), 0.85, -0.15, rz=math.radians(-10))
    P += Cn(prod("ginger", 0.17), 1.7, -0.3)
    return P


def dress_india(st, kenney, metal_mat):
    """Индия: плитка цвета павлиньего пера, медная посуда, манго, ласси и чай."""
    P = []
    P += K.hang_utensils(kenney, metal_mat)
    copper = metal("Copper", (0.96, 0.52, 0.32), rough=0.24, hammered=0.25)
    P += L(K.stock_pot("Pot", copper, 0.25, 0.26, knob_mat=metal("Brass", (0.98, 0.76, 0.36), rough=0.2)), -1.84, 0.26)
    P += L(glass_jar("Lentils", 0.36, 0.1, "beans", 0.72, lid="metal", lid_col=(0.92, 0.62, 0.20)), -1.24, 0.16)
    P += L(prod("lentils", 0.22), -0.62, 0.24)
    P += L(prod("dish_lassi", 0.28), 0.0, 0.24)
    P += L(prod("masala_chai", 0.18), 0.5, 0.24)
    P += L(K.terracotta_pot("Pot2", 0.1, 0.16) + put(K.herb_plant("Coriander", 0.1, 0.16, n=12, seed=13, pot=False), 0, 0, -0.02),
           1.08, 0.26)
    P += L(prod("ladoo", 0.2), 1.75, 0.24)
    P += Cn(prod("dish_dal", 0.44), -1.55, -0.2)
    P += Cn(prod("mango", 0.2, rz=0.5), -0.7, -0.25)
    P += Cn(prod("naan", 0.26), 0.05, -0.1)
    P += Cn(K.stock_pot("Pot3", copper, 0.22, 0.2), 0.95, -0.1)
    P += Cn(prod("samosa", 0.16), 1.75, -0.3)
    return P


def dress_korea(st, kenney, metal_mat):
    """Корея: селадоновая плитка, банки кимчи и кочхуджана, капуста, банановое молоко."""
    P = []
    P += K.hang_utensils(kenney, metal_mat)
    ink = (0.30, 0.52, 0.44)
    P += L(K.bowl_stack("Bowls", 3, 0.17, 0.11, ceramic("BowlW", (0.97, 0.98, 0.96)), ceramic("BowlRim", ink)), -1.84, 0.24)
    P += put(K.deco_plate("Plate", 0.3, (0.97, 0.98, 0.96), ink), -1.2, 0.47, K.LEDGE_TOP + 0.3 * 0.97, rx=math.radians(76))
    P += L(prod("kimchi", 0.26), -1.2, 0.18)
    P += L(prod("gochujang", 0.2), -0.55, 0.24)
    P += L(prod("banana_milk", 0.22), 0.05, 0.24)
    P += L(prod("seaweed", 0.24), 0.62, 0.24)
    P += L(K.terracotta_pot("Pot2", 0.1, 0.16) + put(K.herb_plant("Perilla", 0.1, 0.16, n=10, seed=17, pot=False), 0, 0, -0.02),
           1.12, 0.26)
    P += L(prod("dalgona", 0.18), 1.75, 0.24)
    P += Cn(prod("dish_bibimbap", 0.42), -1.55, -0.2)
    P += Cn(prod("cabbage", 0.3, rz=0.3), -0.7, -0.15)
    P += Cn(prod("rice_cake", 0.2), 0.05, -0.35)
    P += Cn(K.kettle("Kettle", (0.86, 0.86, 0.88)), 0.9, -0.15, rz=math.radians(-10))
    P += Cn(prod("cucumber", 0.22, rz=0.2), 1.72, -0.3)
    return P


def dress_spain(st, kenney, metal_mat):
    """Испания: синие изразцы, апельсины, чоризо, оливковое масло и паэлья на столешнице."""
    P = []
    P += K.hang_utensils(kenney, metal_mat)
    blue = (0.10, 0.26, 0.66)
    P += put(K.deco_plate("Plate", 0.3, (0.98, 0.96, 0.90), blue), -1.84, 0.47, K.LEDGE_TOP + 0.3 * 0.97, rx=math.radians(76))
    P += L(prod("saffron", 0.18), -1.2, 0.2)
    P += L(K.bottle_oil("Oil", 0.48, 0.068), -0.62, 0.24)
    P += L(prod("chorizo", 0.24), 0.0, 0.24)
    P += L(K.bowl_stack("Bowls", 3, 0.16, 0.1, ceramic("BowlT", (0.86, 0.46, 0.24)), ceramic("BowlRim", blue)), 0.62, 0.24)
    P += L(K.terracotta_pot("Pot2", 0.1, 0.16) + put(K.herb_plant("Rosemary", 0.1, 0.16, n=12, seed=19, pot=False), 0, 0, -0.02),
           1.12, 0.26)
    P += L(prod("garlic", 0.16), 1.75, 0.24)
    P += Cn(prod("dish_paella", 0.5), -1.45, -0.2)
    P += Cn(K.fruit_bowl("Oranges", (0.98, 0.96, 0.90), blue, kinds=("orange", "orange", "lemon", "orange", "orange")), -0.35, -0.3)
    P += Cn(prod("orange", 0.18), 0.4, -0.35)
    P += Cn(prod("pepper", 0.17, rz=0.4), 0.95, -0.2)
    P += Cn(K.crock("Crock", (0.96, 0.92, 0.84)), 1.75, -0.05, s=1.1)
    return P


def dress_greece(st, kenney, metal_mat):
    """Греция: бело-голубая плитка, оливки, инжир, фета, йогурт и кулури."""
    P = []
    P += K.hang_utensils(kenney, metal_mat)
    blue = (0.08, 0.28, 0.66)
    P += L(K.bowl_stack("Bowls", 3, 0.17, 0.11, ceramic("BowlW", (0.98, 0.98, 1.0)), ceramic("BowlRim", blue)), -1.84, 0.24)
    P += put(K.deco_plate("Plate", 0.3, (0.98, 0.98, 1.0), blue), -1.2, 0.47, K.LEDGE_TOP + 0.3 * 0.97, rx=math.radians(76))
    P += L(glass_jar("Olives", 0.36, 0.1, "pickles", 0.8, lid="metal", lid_col=(0.10, 0.28, 0.66)), -1.24, 0.16)
    P += L(K.bottle_oil("Oil", 0.48, 0.068), -0.62, 0.24)
    P += L(prod("yogurt", 0.2), 0.0, 0.24)
    P += L(prod("frappe", 0.26), 0.55, 0.24)
    P += L(K.terracotta_pot("Pot2", 0.1, 0.16) + put(K.herb_plant("Oregano", 0.1, 0.16, n=12, seed=23, pot=False), 0, 0, -0.02),
           1.1, 0.26)
    P += L(prod("koulouri", 0.2), 1.75, 0.24)
    P += Cn(prod("dish_greek_salad", 0.44), -1.55, -0.2)
    P += Cn(prod("figs", 0.2), -0.7, -0.3)
    P += Cn(prod("feta", 0.18), 0.05, -0.3)
    P += Cn(prod("eggplant", 0.24, rz=0.3), 0.9, -0.2)
    P += Cn(K.crock("Crock", (0.98, 0.98, 1.0)), 1.75, -0.05, s=1.1)
    return P


K.DRESS.update({"china": dress_china, "india": dress_india, "korea": dress_korea, "spain": dress_spain,
                "greece": dress_greece})
K.STYLE_EXTRA.update({
    "china": dict(layout="square", edge=0.3, edge_col=(0.86, 0.64, 0.24), val_jitter=0.12, hue_jitter=0.015, mottle=0.2,
                  tile_rough=0.12, tile_coat=0.4, handle="knob", wood_mat="dark"),
    "india": dict(layout="mosaic", edge=0.4, edge_col=(0.90, 0.70, 0.30), val_jitter=0.2, hue_jitter=0.03, mottle=0.2,
                  handle="knob"),
    "korea": dict(layout="subway", edge=0.35, val_jitter=0.1, hue_jitter=0.015, mottle=0.18, handle="bar"),
    "spain": dict(layout="square", band=((2.3, 2.95), (-3.9, -2.8)), talavera=True, val_jitter=0.1, hue_jitter=0.02,
                  mottle=0.2, edge=0.3, handle="knob", tile_rough=0.12),
    "greece": dict(layout="subway", edge=0.4, edge_col=(0.70, 0.80, 0.95), val_jitter=0.06, mottle=0.12, handle="knob",
                   top_mat="marble"),
})
