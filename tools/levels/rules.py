"""Правила Sortelier и решатель уровней.

Правила здесь должны совпадать с Sortelier/Game/Board.swift:
- у полки 3 слота в переднем ряду и сколько угодно рядов за ним;
- ход: взять продукт из переднего ряда одной полки и положить в пустой слот переднего ряда другой;
- полный передний ряд срабатывает, если это тройка одинаковых или набор под рецепт,
  и в очереди уровня есть покупатель, который это ждет;
- пустой передний ряд сразу заменяется следующим рядом;
- победа: обслужены все покупатели; поражение: на полках нет ни одного свободного слота.

Терпение: у каждого покупателя за прилавком (первые COUNTER в очереди) после каждого хода
терпение уменьшается на 1. Чаевые при обслуживании: ceil(tip_max * осталось / максимум), при нуле 0.
На решаемость терпение не влияет, только на монеты.

Биомы 2 и 3:
- рецепт из трех одинаковых (онигири = рис x3) проверяется раньше тройки;
- цепочка: три одинаковых сырых продукта в переднем ряду превращаются в один (мука x3 -> тесто),
  он встает в средний слот, срабатывает сразу и без покупателя;
- лед "rice@2": продукт нельзя брать, пока не обслужено 2 покупателя (собрать на месте можно);
- замок полки locks[s]: в полку нельзя класть и из нее нельзя брать, пока не обслужено locks[s];
- гурман: чаевые x GOURMET_MULT.

Биомы 4 и 5 (класс Obstacles):
- замок с ключом keys[s]: полка закрыта, пока не обслужен заказ с этим продуктом или блюдом;
- цепь (a, b): положил продукт на одну полку пары - вторая заблокирована, пока первая не сработает;
  когда обе полки хоть раз сработали, цепь снимается.
"""
from __future__ import annotations

import heapq
import math
from collections import Counter
from dataclasses import dataclass

SLOTS = 3
COUNTER = 3
GOURMET_MULT = 5


def base(c):
    """Продукт без отметки льда: "rice@2" -> "rice"."""
    return c.split("@", 1)[0] if c else c


def ice_of(c):
    """Сколько покупателей надо обслужить, чтобы лед растаял."""
    return int(c.split("@", 1)[1]) if c and "@" in c else 0


@dataclass(frozen=True)
class Order:
    kind: str  # "triple" или "dish"
    target: str  # id продукта или блюда

    def to_json(self):
        return {"kind": self.kind, "target": self.target}


class Catalog:
    def __init__(self, data):
        self.items = {i["id"]: i for i in data["items"]}
        self.dishes = {d["id"]: d for d in data["dishes"]}
        self.recipe_index = {tuple(sorted(d["ingredients"])): d["id"] for d in data["dishes"]}
        self.chains = {i["id"]: i["chain"] for i in data["items"] if i.get("chain")}

    def result_of(self, three):
        """Что дает полный ряд: ("triple", id), ("dish", id) или None."""
        if None in three:
            return None
        b = [base(c) for c in three]
        dish = self.recipe_index.get(tuple(sorted(b)))
        if dish:
            return ("dish", dish)
        if b[0] == b[1] == b[2]:
            return ("triple", b[0])
        return None

    def transform_of(self, three):
        """Цепочка: во что превращается полный ряд из трех одинаковых сырых продуктов."""
        if None in three:
            return None
        b = [base(c) for c in three]
        if b[0] == b[1] == b[2]:
            return self.chains.get(b[0])
        return None


def normalize(shelves):
    """Убирает пустые передние ряды. shelves: list[list[list]] (ряд 0 - передний)."""
    out = []
    for layers in shelves:
        layers = [list(l) for l in layers]
        while len(layers) > 1 and all(c is None for c in layers[0]):
            layers.pop(0)
        out.append(layers)
    return out


def sprite(order):
    """Имя спрайта заказа: продукт или "dish_<блюдо>". Так же обозначается ключ замка."""
    return "dish_" + order.target if order.kind == "dish" else order.target


class Obstacles:
    """Неизменная часть уровня: замки по числу обслуженных, замки с ключом и цепи.

    - locks[s]: полка закрыта, пока не обслужено locks[s] покупателей;
    - keys[s]: полка закрыта, пока не обслужен заказ с этим спрайтом (продукт-ключ на замке);
    - chains: пары полок (a, b). Положил продукт на a - полка b заблокирована, пока a не сработает
      (и наоборот). Когда обе полки хоть раз сработали, цепь снимается.
    Состояние цепей cst: для каждой цепи (last, fired_a, fired_b) или None, если цепь снята.
    """

    def __init__(self, orders, locks=None, keys=None, chains=None):
        self.total = len(orders)
        self.locks = list(locks or [])
        self.keys = list(keys or [])
        self.key_total = Counter(sprite(o) for o in orders)
        self.chains = [tuple(c) for c in (chains or [])]

    @property
    def ordered(self):
        """Полки нельзя переставлять при сравнении состояний: у них разные препятствия."""
        return bool(any(self.locks) or any(self.keys) or self.chains)

    def start(self):
        return tuple((None, False, False) for _ in self.chains)

    def served(self, orders):
        return self.total - len(orders)

    def locked(self, s, orders):
        if s < len(self.locks) and self.locks[s] > self.served(orders):
            return True
        key = self.keys[s] if s < len(self.keys) else None
        return bool(key) and sum(1 for o in orders if sprite(o) == key) == self.key_total[key]

    def blocked(self, s, cst):
        for (a, b), st in zip(self.chains, cst):
            if st is None:
                continue
            if (s == a and st[0] == b) or (s == b and st[0] == a):
                return True
        return False

    def closed(self, s, orders, cst):
        return self.locked(s, orders) or self.blocked(s, cst)

    def placed(self, cst, dst):
        out = list(cst)
        for i, ((a, b), st) in enumerate(zip(self.chains, cst)):
            if st is not None and dst in (a, b):
                out[i] = (dst, st[1], st[2])
        return tuple(out)

    def fired(self, cst, shelf):
        out = list(cst)
        for i, ((a, b), st) in enumerate(zip(self.chains, cst)):
            if st is None or shelf not in (a, b):
                continue
            last = None if st[0] == shelf else st[0]
            fa = st[1] or shelf == a
            fb = st[2] or shelf == b
            out[i] = None if (fa and fb) else (last, fa, fb)
        return tuple(out)


NO_OBSTACLES = None


def settle(catalog, shelves, orders, changed):
    """Срабатывания на полках из changed, пока что-то срабатывает. Возвращает число срабатываний."""
    return len(settle_detail(catalog, shelves, orders, changed))


def settle_detail(catalog, shelves, orders, changed):
    """То же, но возвращает [(индекс покупателя в очереди на момент обслуживания, полка)]."""
    fired = []
    queue = list(changed)
    while queue:
        s = queue.pop()
        front = shelves[s][0]
        made = catalog.transform_of(front)
        if made:
            shelves[s][0] = [None, made, None]
            continue
        res = catalog.result_of(front)
        if res is None:
            continue
        idx = next((k for k, o in enumerate(orders) if (o.kind, o.target) == res), None)
        if idx is None:
            continue
        orders.pop(idx)
        shelves[s][0] = [None] * SLOTS
        if len(shelves[s]) > 1:
            shelves[s].pop(0)
        fired.append((idx, s))
        queue.append(s)
    return fired


def thaw(shelves, served):
    """Убирает растаявшие отметки льда, чтобы одинаковые состояния совпадали."""
    for layers in shelves:
        for layer in layers:
            for k, c in enumerate(layer):
                if c and "@" in c and ice_of(c) <= served:
                    layer[k] = base(c)


def apply_move_detail(catalog, shelves, orders, src, slot, dst, obs, cst=()):
    """Делает ход. Возвращает (новые полки, новые заказы, [(индекс, полка)] обслуженных, состояние цепей) или None."""
    if src == dst:
        return None
    if obs.closed(src, orders, cst) or obs.closed(dst, orders, cst):
        return None
    served = obs.served(orders)
    item = shelves[src][0][slot]
    if item is None or ice_of(item) > served:
        return None
    if None not in shelves[dst][0]:
        return None
    shelves = [[list(l) for l in layers] for layers in shelves]
    orders = list(orders)
    shelves[src][0][slot] = None
    j = shelves[dst][0].index(None)
    shelves[dst][0][j] = item
    cst = obs.placed(cst, dst)
    changed = []
    if all(c is None for c in shelves[src][0]) and len(shelves[src]) > 1:
        shelves[src].pop(0)
        changed.append(src)
    changed.append(dst)
    fired = settle_detail(catalog, shelves, orders, changed)
    for _, shelf in fired:
        cst = obs.fired(cst, shelf)
    thaw(shelves, obs.served(orders))
    return shelves, orders, fired, cst


def has_free_slot(shelves):
    return any(None in layers[0] for layers in shelves)


def legal_moves(shelves, orders, obs, cst=()):
    served = obs.served(orders)
    moves = []
    free_dst = [d for d, layers in enumerate(shelves) if None in layers[0] and not obs.closed(d, orders, cst)]
    for s, layers in enumerate(shelves):
        if obs.closed(s, orders, cst):
            continue
        seen = set()
        for k, item in enumerate(layers[0]):
            if item is None or item in seen or ice_of(item) > served:
                continue
            seen.add(item)
            for d in free_dst:
                if d != s:
                    moves.append((s, k, d))
    return moves


def has_move(shelves, orders, obs, cst=()):
    """Есть ли хоть один ход: незамороженный продукт и свободный слот на другой открытой полке."""
    return bool(legal_moves(shelves, orders, obs, cst))


def key_of(shelves, orders, cst=(), ordered=False):
    shelf_keys = []
    for layers in shelves:
        front = tuple(sorted((c or "") for c in layers[0]))
        rest = tuple(tuple(c or "" for c in l) for l in layers[1:])
        shelf_keys.append((front, rest))
    shelf_part = tuple(shelf_keys) if ordered else tuple(sorted(shelf_keys))
    return (shelf_part, tuple(sorted((o.kind, o.target) for o in orders)), cst)


def heuristic(catalog, shelves, orders):
    """Чем меньше, тем ближе к решению."""
    score = len(orders) * 10.0
    buried = 0
    for layers in shelves:
        front = [base(c) for c in layers[0] if c]
        cnt = Counter(front)
        # пары одинаковых в переднем ряду приближают тройку
        for item, n in cnt.items():
            if n >= 2:
                score -= 1.5
        # набор из двух разных ингредиентов одного рецепта
        if len(front) == 2:
            for d in catalog.dishes.values():
                ings = d["ingredients"]
                if all(f in ings for f in front) and front[0] != front[1]:
                    score -= 1.0
                    break
        for depth, l in enumerate(layers[1:], start=1):
            buried += depth * sum(1 for c in l if c)
    free = sum(layers[0].count(None) for layers in shelves)
    if free == 0:
        score += 50
    return score + buried * 0.08 - free * 0.2


def make_obstacles(orders, locks=None, keys=None, chains=None):
    return Obstacles(orders, locks, keys, chains)


def solve(catalog, shelves, orders, beam=160, max_depth=400, locks=None, keys=None, chains=None):
    """Лучевой поиск. Возвращает список ходов или None."""
    shelves = normalize(shelves)
    orders = list(orders)
    obs = Obstacles(orders, locks, keys, chains)
    cst = obs.start()
    for _, shelf in settle_detail(catalog, shelves, orders, range(len(shelves))):
        cst = obs.fired(cst, shelf)
    frontier = [(heuristic(catalog, shelves, orders), 0, shelves, orders, cst, [])]
    seen = {key_of(shelves, orders, cst, obs.ordered)}
    counter = 0
    for _ in range(max_depth):
        candidates = []
        for _, _, sh, od, cs, path in frontier:
            if not od:
                return path
            for (s, k, d) in legal_moves(sh, od, obs, cs):
                res = apply_move_detail(catalog, sh, od, s, k, d, obs, cs)
                if res is None:
                    continue
                nsh, nod, fired, ncs = res
                key = key_of(nsh, nod, ncs, obs.ordered)
                if key in seen:
                    continue
                seen.add(key)
                if not nod:
                    return path + [(s, k, d)]
                if not has_move(nsh, nod, obs, ncs):
                    continue
                counter += 1
                h = heuristic(catalog, nsh, nod) - len(fired) * 3
                candidates.append((h, counter, nsh, nod, ncs, path + [(s, k, d)]))
        if not candidates:
            return None
        frontier = heapq.nsmallest(beam, candidates, key=lambda c: (c[0], c[1]))
    return None


COMBO_WINDOW = 3


def tip_for(left, patience, tip_max):
    if patience <= 0 or tip_max <= 0 or left <= 0:
        return 0
    return int(math.ceil(tip_max * left / patience - 1e-9))


def replay_score(catalog, shelves, orders, path, coins_per_order=5, combo_bonus=2, combo_from=3,
                 patience=0, tip_max=0, detail=False, locks=None, gourmet=(), keys=None, chains=None):
    """Монеты за прохождение по правилам игры (без бонуса за экономию ходов).

    Серия: срабатывание не дальше COMBO_WINDOW ходов от предыдущего продолжает серию.
    С третьего срабатывания серии каждое дает +combo_bonus. Чаевые - по терпению (см. выше).
    """
    shelves = normalize(shelves)
    orders = list(orders)
    obs = Obstacles(orders, locks, keys, chains)
    cst = obs.start()
    for _, shelf in settle_detail(catalog, shelves, orders, range(len(shelves))):
        cst = obs.fired(cst, shelf)
    pat = [patience] * len(orders)
    gm = [i in gourmet for i in range(len(orders))]
    coins = tips = 0
    combo = 0
    since = 99
    for (s, k, d) in path:
        shelves, orders, fired, cst = apply_move_detail(catalog, shelves, orders, s, k, d, obs, cst)
        since += 1
        for idx, _ in fired:
            tip = tip_for(pat.pop(idx), patience, tip_max) * (GOURMET_MULT if gm.pop(idx) else 1)
            tips += tip
            combo = combo + 1 if (combo > 0 and since <= COMBO_WINDOW) else 1
            since = 0
            coins += coins_per_order + tip
            if combo >= combo_from:
                coins += combo_bonus
        for i in range(min(COUNTER, len(pat))):
            pat[i] = max(0, pat[i] - 1)
    assert not orders
    return (coins, tips) if detail else coins
