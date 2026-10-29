"""Правила мини-игры "Рынок" (3 в ряд). Совпадают с Sortelier/Game/Match3Board.swift.

Поле до 8x9, клетки задаются строками (cells), символы:
  .  обычная клетка        -  дыра (клетки нет, фишки пролетают сквозь нее вниз)
  1 2 3  ящик в 1-3 слоя (вместо фишки, бьется соседними совпадениями и взрывами)
  i I  фишка во льду в 1-2 слоя (не двигается и не падает, удар снимает слой)
  j  пятно варенья под фишкой (смывается, когда клетку задевает совпадение или взрыв)
  k  варенье и лед в 1 слой

Ход - обмен двух соседних фишек. Ход засчитывается, если появилось совпадение или в обмене участвует спецфишка.
Тап по спецфишке тоже ход: она срабатывает на месте.

Совпадения: ряды от 3 по горизонтали и вертикали и квадраты 2x2 одного цвета. Пересекающиеся фигуры одного цвета -
одна группа. Что получается из группы (по старшинству):
- ряд от 5 - радужный пончик R (убирает все фишки одного цвета);
- горизонтальный и вертикальный ряды вместе (уголок, Т, крест) - бомба B (взрыв 5x5);
- ряд из 4 - скалка H (горизонтальный ряд) или V (вертикальный), сносит свой ряд или столбец;
- квадрат 2x2 - венчик W: бьет свою клетку и 4 соседние, потом летит к цели уровня и бьет ее.

Комбо при обмене двух спецфишек (срабатывают в клетке, куда тянули):
скалка + скалка - крест; скалка + бомба - 3 ряда и 3 столбца; бомба + бомба - взрыв 7x7;
венчик + скалка/бомба - венчик уносит ее к цели; венчик + венчик - три венчика;
пончик + скалка/бомба/венчик - все фишки самого частого цвета становятся такими спецфишками и срабатывают;
пончик + пончик - все поле.

После ударов фишки падают вниз (сквозь дыры), сверху столбца появляются новые; если клетку не заполнить сверху
(над ней ящик или лед), в нее соскальзывает фишка по диагонали. Если ходов нет, поле перемешивается.
"""
from __future__ import annotations

import random

DIRS = ((-1, 0), (1, 0), (0, -1), (0, 1))
SPECIALS = ("H", "V", "B", "W", "R")


class Board:
    def __init__(self, level, seed, specials=()):
        self.rows = len(level["cells"])
        self.cols = len(level["cells"][0])
        self.names = level["colors"]
        self.colors = list(range(len(self.names)))
        self.rng = random.Random(seed)
        self.goal_list = level["goals"]
        cells = level["cells"]
        self.valid = [[cells[r][c] != "-" for c in range(self.cols)] for r in range(self.rows)]
        self.crate = [[int(ch) if ch in "123" else 0 for ch in row] for row in cells]
        self.ice = [[{"i": 1, "I": 2, "k": 1}.get(ch, 0) for ch in row] for row in cells]
        self.jam = [[1 if ch in "jk" else 0 for ch in row] for row in cells]
        self.tile = [[None] * self.cols for _ in range(self.rows)]
        self.got = {"crate": 0, "ice": 0, "jam": 0}
        self.got_colors = [0] * len(self.colors)
        self.moves = 0
        self.fill_initial()
        self.place_specials(specials)

    def clone(self):
        b = Board.__new__(Board)
        b.rows, b.cols, b.names, b.colors, b.goal_list = self.rows, self.cols, self.names, self.colors, self.goal_list
        b.rng = random.Random()
        b.rng.setstate(self.rng.getstate())
        b.valid = self.valid
        b.crate = [row[:] for row in self.crate]
        b.ice = [row[:] for row in self.ice]
        b.jam = [row[:] for row in self.jam]
        b.tile = [row[:] for row in self.tile]
        b.got = dict(self.got)
        b.got_colors = self.got_colors[:]
        b.moves = self.moves
        return b

    # MARK: - Поле

    def inside(self, r, c):
        return 0 <= r < self.rows and 0 <= c < self.cols and self.valid[r][c]

    def color(self, r, c):
        if not (0 <= r < self.rows and 0 <= c < self.cols):
            return None
        t = self.tile[r][c]
        return t if isinstance(t, int) else None

    def special(self, r, c):
        t = self.tile[r][c]
        return t if isinstance(t, str) else None

    def movable(self, r, c):
        """Фишку можно двигать и она падает."""
        return self.inside(r, c) and self.tile[r][c] is not None and self.ice[r][c] == 0

    def empty(self, r, c):
        return self.inside(r, c) and self.tile[r][c] is None and self.crate[r][c] == 0

    def fill_initial(self):
        """Стартовое поле без готовых совпадений и хотя бы с одним ходом."""
        for _ in range(300):
            for r in range(self.rows):
                for c in range(self.cols):
                    if not self.inside(r, c) or self.crate[r][c]:
                        self.tile[r][c] = None
                        continue
                    options = [k for k in self.colors if not self.would_match(r, c, k)]
                    self.tile[r][c] = self.rng.choice(options or self.colors)
            if self.has_move():
                return

    def would_match(self, r, c, k):
        """Даст ли цвет k совпадение с уже поставленными слева и сверху (для стартового поля)."""
        if self.color(r, c - 1) == k and self.color(r, c - 2) == k:
            return True
        if self.color(r - 1, c) == k and self.color(r - 2, c) == k:
            return True
        return self.color(r - 1, c) == k and self.color(r, c - 1) == k and self.color(r - 1, c - 1) == k

    def place_specials(self, kinds):
        """Спецфишки на старте (бустеры перед уровнем и серия побед): на случайные свободные клетки."""
        spots = [(r, c) for r in range(self.rows) for c in range(self.cols)
                 if self.movable(r, c) and isinstance(self.tile[r][c], int) and not self.jam[r][c]]
        self.rng.shuffle(spots)
        for kind, pos in zip(kinds, spots):
            if kind in "HV":
                kind = self.rng.choice("HV")
            self.tile[pos[0]][pos[1]] = kind

    # MARK: - Совпадения

    def find_groups(self):
        """Группы совпадений: [(клетки, горизонтальные ряды, вертикальные ряды, квадраты)]."""
        shapes = []
        for r in range(self.rows):
            c = 0
            while c < self.cols:
                k = self.color(r, c)
                e = c
                while k is not None and self.color(r, e + 1) == k:
                    e += 1
                if k is not None and e - c >= 2:
                    shapes.append(("h", [(r, x) for x in range(c, e + 1)]))
                c = e + 1
        for c in range(self.cols):
            r = 0
            while r < self.rows:
                k = self.color(r, c)
                e = r
                while k is not None and self.color(e + 1, c) == k:
                    e += 1
                if k is not None and e - r >= 2:
                    shapes.append(("v", [(y, c) for y in range(r, e + 1)]))
                r = e + 1
        for r in range(self.rows - 1):
            for c in range(self.cols - 1):
                k = self.color(r, c)
                if k is not None and self.color(r, c + 1) == k and self.color(r + 1, c) == k and self.color(r + 1, c + 1) == k:
                    shapes.append(("s", [(r, c), (r, c + 1), (r + 1, c), (r + 1, c + 1)]))
        parent = list(range(len(shapes)))

        def find(i):
            while parent[i] != i:
                parent[i] = parent[parent[i]]
                i = parent[i]
            return i
        owner = {}
        for i, (_, cells) in enumerate(shapes):
            for cell in cells:
                if cell in owner:
                    parent[find(i)] = find(owner[cell])
                else:
                    owner[cell] = i
        groups = {}
        for i in range(len(shapes)):
            groups.setdefault(find(i), []).append(shapes[i])
        out = []
        for key in sorted(groups):
            parts = groups[key]
            cells = sorted({cell for _, cs in parts for cell in cs})
            out.append((cells, [cs for t, cs in parts if t == "h"], [cs for t, cs in parts if t == "v"],
                        [cs for t, cs in parts if t == "s"]))
        return out

    @staticmethod
    def group_special(hs, vs, sq):
        """Что дает группа: R, B, H, V, W или None."""
        longest = max([len(x) for x in hs + vs] or [0])
        if longest >= 5:
            return "R"
        if hs and vs:
            return "B"
        if any(len(x) == 4 for x in hs):
            return "H"
        if any(len(x) == 4 for x in vs):
            return "V"
        if sq:
            return "W"
        return None

    def group_anchor(self, cells, hs, vs, prefer):
        """Где появится спецфишка: клетка хода, если она в группе, иначе пересечение рядов или середина длинного."""
        free = [p for p in cells if self.ice[p[0]][p[1]] == 0]
        if not free:
            return None
        for p in prefer:
            if p in free:
                return p
        both = [p for p in free if any(p in x for x in hs) and any(p in v for v in vs)]
        if both:
            return both[0]
        runs = sorted(hs + vs, key=len, reverse=True)
        if runs:
            mid = [p for p in runs[0] if p in free]
            if mid:
                return mid[(len(mid) - 1) // 2]
        return free[0]

    # MARK: - Ходы

    def has_move(self):
        return bool(self.moves_list(first=True))

    def moves_list(self, first=False):
        """Все засчитываемые ходы: ("tap", a) и ("swap", a, b)."""
        out = []
        for r in range(self.rows):
            for c in range(self.cols):
                if not self.movable(r, c):
                    continue
                if self.special(r, c):
                    out.append(("tap", (r, c)))
                    if first:
                        return out
                for r2, c2 in ((r, c + 1), (r + 1, c)):
                    if not self.movable(r2, c2):
                        continue
                    if self.special(r, c) or self.special(r2, c2) or self.swap_makes_match(r, c, r2, c2):
                        out.append(("swap", (r, c), (r2, c2)))
                        if first:
                            return out
        return out

    def swap_makes_match(self, r, c, r2, c2):
        a, b = self.tile[r][c], self.tile[r2][c2]
        if a == b:
            return False
        self.tile[r][c], self.tile[r2][c2] = b, a
        ok = self.match_at(r, c) or self.match_at(r2, c2)
        self.tile[r][c], self.tile[r2][c2] = a, b
        return ok

    def match_at(self, r, c):
        k = self.color(r, c)
        if k is None:
            return False
        n = 1
        x = c - 1
        while self.color(r, x) == k:
            n, x = n + 1, x - 1
        x = c + 1
        while self.color(r, x) == k:
            n, x = n + 1, x + 1
        if n >= 3:
            return True
        n = 1
        y = r - 1
        while self.color(y, c) == k:
            n, y = n + 1, y - 1
        y = r + 1
        while self.color(y, c) == k:
            n, y = n + 1, y + 1
        if n >= 3:
            return True
        for dr in (-1, 0):
            for dc in (-1, 0):
                if all(self.color(r + dr + i, c + dc + j) == k for i in (0, 1) for j in (0, 1)):
                    return True
        return False

    def play(self, move):
        if move[0] == "tap":
            return self.tap(move[1])
        return self.swap(move[1], move[2])

    def swap(self, a, b):
        """Ход обменом (b - клетка, куда тянули фишку из a). True, если ход засчитан."""
        (r, c), (r2, c2) = a, b
        if abs(r - r2) + abs(c - c2) != 1 or not self.movable(r, c) or not self.movable(r2, c2):
            return False
        sa, sb = self.special(r, c), self.special(r2, c2)
        if sa and sb:
            self.moves += 1
            self.tile[r][c] = None
            self.tile[r2][c2] = None
            self.combo(sa, sb, b)
            self.resolve()
            return True
        if sa or sb:
            self.moves += 1
            self.tile[r][c], self.tile[r2][c2] = self.tile[r2][c2], self.tile[r][c]
            pos, other = (b, a) if sa else (a, b)
            self.fire(pos, sa or sb, color=self.color(*other))
            self.resolve()
            return True
        if not self.swap_makes_match(r, c, r2, c2):
            return False
        self.moves += 1
        self.tile[r][c], self.tile[r2][c2] = self.tile[r2][c2], self.tile[r][c]
        self.resolve(prefer=[b, a])
        return True

    def tap(self, pos):
        r, c = pos
        kind = self.special(r, c)
        if not kind or not self.movable(r, c):
            return False
        self.moves += 1
        self.fire(pos, kind)
        self.resolve()
        return True

    # MARK: - Удары

    def hit(self, pos, queue):
        """Удар по клетке. Задетые спецфишки уходят в очередь срабатывания."""
        r, c = pos
        if not self.inside(r, c):
            return
        if self.crate[r][c]:
            self.crate[r][c] -= 1
            if self.crate[r][c] == 0:
                self.got["crate"] += 1
            return
        if self.jam[r][c]:
            self.jam[r][c] = 0
            self.got["jam"] += 1
        t = self.tile[r][c]
        if t is None:
            return
        if self.ice[r][c]:
            self.ice[r][c] -= 1
            if self.ice[r][c] == 0:
                self.got["ice"] += 1
            return
        self.tile[r][c] = None
        if isinstance(t, str):
            queue.append(((r, c), t, None))
        else:
            self.got_colors[t] += 1

    def clear_groups(self, groups, prefer=()):
        """Убирает группы совпадений, ставит спецфишки, бьет соседние ящики."""
        queue = []
        for cells, hs, vs, sq in groups:
            kind = self.group_special(hs, vs, sq)
            anchor = self.group_anchor(cells, hs, vs, prefer) if kind else None
            crates = set()
            for (r, c) in cells:
                for dr, dc in DIRS:
                    if self.inside(r + dr, c + dc) and self.crate[r + dr][c + dc]:
                        crates.add((r + dr, c + dc))
            for p in cells:
                self.hit(p, queue)
            for p in sorted(crates):
                self.hit(p, queue)
            if anchor and self.tile[anchor[0]][anchor[1]] is None:
                self.tile[anchor[0]][anchor[1]] = kind
        return queue

    def fire(self, pos, kind, color=None):
        """Срабатывание спецфишки и цепочка задетых ею."""
        r, c = pos
        if self.tile[r][c] == kind:
            self.tile[r][c] = None
        self.run_queue([(pos, kind, color)])

    def run_queue(self, queue):
        while queue:
            wave, queue = queue, []
            for pos, kind, color in wave:
                for cell in self.effect(pos, kind, color):
                    self.hit(cell, queue)

    def effect(self, pos, kind, color=None):
        """Клетки, по которым бьет спецфишка."""
        r, c = pos
        if kind == "H":
            return [(r, x) for x in range(self.cols)]
        if kind == "V":
            return [(y, c) for y in range(self.rows)]
        if kind == "B":
            return [(r + dr, c + dc) for dr in range(-2, 3) for dc in range(-2, 3)]
        if kind == "W":
            cells = [(r, c)] + [(r + dr, c + dc) for dr, dc in DIRS]
            target = self.whisk_target(set(cells))
            return cells + ([target] if target else [])
        if kind == "R":
            k = color if color is not None else self.most_common_color()
            return [(y, x) for y in range(self.rows) for x in range(self.cols) if self.color(y, x) == k]
        return []

    def most_common_color(self):
        counts = [0] * len(self.colors)
        for y in range(self.rows):
            for x in range(self.cols):
                k = self.color(y, x)
                if k is not None:
                    counts[k] += 1
        best = max(counts)
        return counts.index(best) if best else None

    def needs(self):
        """Что еще нужно для целей: (цвета, блокеры)."""
        colors, blockers = set(), set()
        for g in self.goal_list:
            if g["type"] == "collect":
                k = self.names.index(g["item"])
                if self.got_colors[k] < g["count"]:
                    colors.add(k)
            elif self.got[g["type"]] < g["count"]:
                blockers.add(g["type"])
        return colors, blockers

    def whisk_target(self, exclude):
        """Цель венчика: нужные ящики, лед или варенье, иначе фишка нужного цвета, иначе любая фишка."""
        colors, blockers = self.needs()
        best, options = 0, []
        for y in range(self.rows):
            for x in range(self.cols):
                if (y, x) in exclude or not self.inside(y, x):
                    continue
                score = 0
                if self.crate[y][x]:
                    score = 3 if "crate" in blockers else 0
                elif self.ice[y][x] and "ice" in blockers:
                    score = 3
                elif self.jam[y][x] and "jam" in blockers:
                    score = 3
                elif self.color(y, x) in colors:
                    score = 2
                elif self.tile[y][x] is not None:
                    score = 1
                if score > best:
                    best, options = score, []
                if score and score == best:
                    options.append((y, x))
        return self.rng.choice(options) if options else None

    def combo(self, a, b, pos):
        """Обменяли две спецфишки: обе сгорают, в клетке pos срабатывает усиленный эффект."""
        r, c = pos
        kinds = {a, b}
        queue, cells = [], []
        if kinds <= {"H", "V"}:
            cells = [(r, x) for x in range(self.cols)] + [(y, c) for y in range(self.rows)]
        elif kinds == {"R"}:
            cells = [(y, x) for y in range(self.rows) for x in range(self.cols)]
        elif "R" in kinds:
            other = (kinds - {"R"}).pop()
            k = self.most_common_color()
            for y in range(self.rows):
                for x in range(self.cols):
                    if k is not None and self.color(y, x) == k and self.ice[y][x] == 0:
                        self.tile[y][x] = None
                        self.got_colors[k] += 1
                        queue.append(((y, x), self.rng.choice("HV") if other in "HV" else other, None))
        elif kinds == {"B"}:
            cells = [(r + dr, c + dc) for dr in range(-3, 4) for dc in range(-3, 4)]
        elif "B" in kinds and kinds & {"H", "V"}:
            cells = [(y, x) for y in range(r - 1, r + 2) for x in range(self.cols)]
            cells += [(y, x) for x in range(c - 1, c + 2) for y in range(self.rows)]
        elif kinds == {"W"}:
            cells = [(r, c)] + [(r + dr, c + dc) for dr, dc in DIRS]
            for _ in range(3):
                t = self.whisk_target(set(cells))
                if t:
                    cells.append(t)
        elif "W" in kinds:
            other = (kinds - {"W"}).pop()
            cells = [(r, c)] + [(r + dr, c + dc) for dr, dc in DIRS]
            t = self.whisk_target(set(cells))
            if t:
                queue.append((t, other, None))
        for cell in cells:
            self.hit(cell, queue)
        self.run_queue(queue)

    # MARK: - Падение

    def gravity(self):
        """Фишки падают вниз сквозь дыры, сверху столбца появляются новые; под ящиком или льдом - по диагонали."""
        while True:
            moved = False
            for c in range(self.cols):
                for r in range(self.rows - 1, -1, -1):
                    if not self.empty(r, c):
                        continue
                    y = r - 1
                    while y >= 0 and (not self.valid[y][c] or self.empty(y, c)):
                        y -= 1
                    if y < 0:
                        self.tile[r][c] = self.rng.choice(self.colors)
                        moved = True
                    elif self.movable(y, c):
                        self.tile[r][c], self.tile[y][c] = self.tile[y][c], None
                        moved = True
            if moved:
                continue
            for r in range(self.rows - 1, 0, -1):
                for c in range(self.cols):
                    if not self.empty(r, c):
                        continue
                    for x in (c - 1, c + 1):
                        if self.movable(r - 1, x):
                            self.tile[r][c], self.tile[r - 1][x] = self.tile[r - 1][x], None
                            moved = True
                            break
                    if moved:
                        break
                if moved:
                    break
            if not moved:
                return

    # MARK: - Разбор хода

    def resolve(self, prefer=()):
        """Падения и каскады до покоя. Если ходов нет - перемешивание."""
        first = True
        while True:
            self.gravity()
            groups = self.find_groups()
            if not groups:
                break
            queue = self.clear_groups(groups, prefer if first else ())
            first = False
            self.run_queue(queue)
        if not self.has_move():
            self.shuffle()

    def shuffle(self):
        cells = [(r, c) for r in range(self.rows) for c in range(self.cols)
                 if self.movable(r, c) and isinstance(self.tile[r][c], int)]
        for _ in range(200):
            values = [self.tile[r][c] for r, c in cells]
            self.rng.shuffle(values)
            for (r, c), v in zip(cells, values):
                self.tile[r][c] = v
            if not self.find_groups() and self.has_move():
                return
        for r, c in cells:
            options = [k for k in self.colors if not self.would_match(r, c, k)]
            self.tile[r][c] = self.rng.choice(options or self.colors)
        if not self.has_move() and cells:
            r, c = cells[len(cells) // 2]
            self.tile[r][c] = "B"

    # MARK: - Цели

    def progress(self, goal):
        if goal["type"] == "collect":
            return self.got_colors[self.names.index(goal["item"])]
        return self.got[goal["type"]]

    def won(self):
        return all(self.progress(g) >= g["count"] for g in self.goal_list)
