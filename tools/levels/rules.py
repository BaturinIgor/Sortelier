"""Правила Sortelier и решатель уровней.

Правила здесь должны совпадать с Sortelier/Game/Board.swift:
- у полки 3 слота в переднем ряду и сколько угодно рядов за ним;
- ход: взять продукт из переднего ряда одной полки и положить в пустой слот переднего ряда другой;
- полный передний ряд срабатывает, если это тройка одинаковых или набор под рецепт,
  и в очереди уровня есть покупатель, который это ждет;
- пустой передний ряд сразу заменяется следующим рядом;
- победа: обслужены все покупатели; поражение: на полках нет ни одного свободного слота.
"""
from __future__ import annotations

import heapq
from collections import Counter
from dataclasses import dataclass

SLOTS = 3


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

    def result_of(self, three):
        """Что дает полный ряд: ("triple", id), ("dish", id) или None."""
        if None in three:
            return None
        if three[0] == three[1] == three[2]:
            return ("triple", three[0])
        dish = self.recipe_index.get(tuple(sorted(three)))
        if dish:
            return ("dish", dish)
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


def settle(catalog, shelves, orders, changed):
    """Срабатывания на полках из changed, пока что-то срабатывает. Возвращает число срабатываний."""
    fired = 0
    queue = list(changed)
    while queue:
        s = queue.pop()
        front = shelves[s][0]
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
        fired += 1
        queue.append(s)
    return fired


def apply_move(catalog, shelves, orders, src, slot, dst):
    """Делает ход. Возвращает (новые полки, новые заказы, сколько сработало) или None."""
    if src == dst:
        return None
    item = shelves[src][0][slot]
    if item is None:
        return None
    if None not in shelves[dst][0]:
        return None
    shelves = [[list(l) for l in layers] for layers in shelves]
    orders = list(orders)
    shelves[src][0][slot] = None
    j = shelves[dst][0].index(None)
    shelves[dst][0][j] = item
    changed = []
    if all(c is None for c in shelves[src][0]) and len(shelves[src]) > 1:
        shelves[src].pop(0)
        changed.append(src)
    changed.append(dst)
    fired = settle(catalog, shelves, orders, changed)
    return shelves, orders, fired


def has_free_slot(shelves):
    return any(None in layers[0] for layers in shelves)


def key_of(shelves, orders):
    shelf_keys = []
    for layers in shelves:
        front = tuple(sorted((c or "") for c in layers[0]))
        rest = tuple(tuple(c or "" for c in l) for l in layers[1:])
        shelf_keys.append((front, rest))
    return (tuple(sorted(shelf_keys)), tuple(sorted((o.kind, o.target) for o in orders)))


def heuristic(catalog, shelves, orders):
    """Чем меньше, тем ближе к решению."""
    need = Counter()
    for o in orders:
        if o.kind == "triple":
            need[o.target] += 3
        else:
            for ing in catalog.dishes[o.target]["ingredients"]:
                need[ing] += 1
    score = len(orders) * 10.0
    buried = 0
    for layers in shelves:
        front = [c for c in layers[0] if c]
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


def legal_moves(shelves):
    moves = []
    free_dst = [d for d, layers in enumerate(shelves) if None in layers[0]]
    for s, layers in enumerate(shelves):
        seen = set()
        for k, item in enumerate(layers[0]):
            if item is None or item in seen:
                continue
            seen.add(item)
            for d in free_dst:
                if d != s:
                    moves.append((s, k, d))
    return moves


def solve(catalog, shelves, orders, beam=160, max_depth=400):
    """Лучевой поиск. Возвращает список ходов или None."""
    shelves = normalize(shelves)
    orders = list(orders)
    settle(catalog, shelves, orders, range(len(shelves)))
    frontier = [(heuristic(catalog, shelves, orders), 0, shelves, orders, [])]
    seen = {key_of(shelves, orders)}
    counter = 0
    for _ in range(max_depth):
        candidates = []
        for _, _, sh, od, path in frontier:
            if not od:
                return path
            for (s, k, d) in legal_moves(sh):
                res = apply_move(catalog, sh, od, s, k, d)
                if res is None:
                    continue
                nsh, nod, fired = res
                key = key_of(nsh, nod)
                if key in seen:
                    continue
                seen.add(key)
                if not nod:
                    return path + [(s, k, d)]
                if not has_free_slot(nsh):
                    continue
                counter += 1
                h = heuristic(catalog, nsh, nod) - fired * 3
                candidates.append((h, counter, nsh, nod, path + [(s, k, d)]))
        if not candidates:
            return None
        frontier = heapq.nsmallest(beam, candidates, key=lambda c: (c[0], c[1]))
    return None


COMBO_WINDOW = 3


def replay_score(catalog, shelves, orders, path, coins_per_order=5, combo_bonus=2, combo_from=3):
    """Монеты за прохождение по правилам игры (без бонуса за экономию ходов).

    Серия: срабатывание не дальше COMBO_WINDOW ходов от предыдущего продолжает серию.
    С третьего срабатывания серии каждое дает +combo_bonus.
    """
    shelves = normalize(shelves)
    orders = list(orders)
    settle(catalog, shelves, orders, range(len(shelves)))
    coins = 0
    combo = 0
    since = 99
    for (s, k, d) in path:
        shelves, orders, fired = apply_move(catalog, shelves, orders, s, k, d)
        since += 1
        for _ in range(fired):
            combo = combo + 1 if (combo > 0 and since <= COMBO_WINDOW) else 1
            since = 0
            coins += coins_per_order
            if combo >= combo_from:
                coins += combo_bonus
    assert not orders
    return coins
