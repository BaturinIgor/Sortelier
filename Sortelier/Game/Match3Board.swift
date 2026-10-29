import Foundation

// Правила мини-игры "Рынок" (3 в ряд). Эталон с описанием всех правил - tools/match3/rules.py.
// Каждый ход возвращает ленту событий со временем: сцена просто проигрывает ее, поэтому цепочки взрывов,
// падение и каскады идут ровно в том порядке и темпе, в каком их посчитал движок.

struct M3Cell: Hashable {
    let r: Int
    let c: Int
    init(_ r: Int, _ c: Int) {
        self.r = r
        self.c = c
    }
}

/// Спецфишки: скалка по ряду и по столбцу, бомба, венчик, радужный пончик.
enum M3Special: String, Codable, CaseIterable {
    case rowPin = "H", colPin = "V", bomb = "B", whisk = "W", rainbow = "R"

    var isPin: Bool { self == .rowPin || self == .colPin }

    var sprite: String {
        switch self {
        case .rowPin, .colPin: return "m3_pin"
        case .bomb: return "m3_bomb"
        case .whisk: return "m3_whisk"
        case .rainbow: return "m3_rainbow"
        }
    }
}

enum M3Kind: Equatable {
    case color(Int)
    case special(M3Special)

    var color: Int? {
        if case let .color(k) = self { return k }
        return nil
    }

    var special: M3Special? {
        if case let .special(s) = self { return s }
        return nil
    }
}

struct M3Tile: Equatable {
    let id: Int
    var kind: M3Kind
}

/// Как сработала спецфишка: для картинки эффекта.
struct M3Fire {
    var special: M3Special
    /// Ширина полосы скалки (3 в комбо с бомбой), крест в комбо двух скалок.
    var width = 1
    var cross = false
    var radius = 2
    /// Куда летит венчик (и что он несет), куда бьют лучи пончика.
    var targets: [M3Cell] = []
    var carry: M3Special?
    var color: Int?
    /// Пончик + пончик: все поле.
    var all = false
}

enum M3Booster: String, Codable, CaseIterable, Identifiable {
    /// Перед уровнем: спецфишки на поле со старта.
    case pin, bomb, rainbow
    /// Во время уровня: молоток (одна клетка), нож (ряд), лопатка (столбец), миксер (перемешать).
    case mallet, knife, spatula, mixer

    var id: String { rawValue }
    var icon: String {
        switch self {
        case .pin: return "m3_pin"
        case .bomb: return "m3_bomb"
        case .rainbow: return "m3_rainbow"
        default: return "icon_m3_" + rawValue
        }
    }
    var isPreLevel: Bool { self == .pin || self == .bomb || self == .rainbow }
    var needsTarget: Bool { self == .mallet || self == .knife || self == .spatula }

    var special: M3Special? {
        switch self {
        case .pin: return .rowPin
        case .bomb: return .bomb
        case .rainbow: return .rainbow
        default: return nil
        }
    }

    static let preLevel: [M3Booster] = [.pin, .bomb, .rainbow]
    static let inLevel: [M3Booster] = [.mallet, .knife, .spatula, .mixer]
}

enum M3Event {
    /// Обмен двух фишек; back - обмен без совпадения, фишки возвращаются.
    case swap(M3Cell, M3Cell, back: Bool)
    /// Фишка убрана. toward - клетка, где из группы появляется спецфишка (фишки съезжаются к ней).
    case pop(id: Int, cell: M3Cell, color: Int, toward: M3Cell?)
    case create(M3Tile, M3Cell)
    case fire(id: Int?, cell: M3Cell, M3Fire)
    case combo(a: Int, b: Int, cell: M3Cell, M3Special, M3Special)
    /// Фишка стала спецфишкой (комбо с пончиком, бустеры перед уровнем, финал). color - собранный цвет.
    case convert(id: Int, cell: M3Cell, M3Special, color: Int?)
    case crate(M3Cell, left: Int)
    case ice(M3Cell, left: Int)
    case jam(M3Cell)
    /// Падение по клеткам пути (строки выше поля - отрицательные) и новая фишка сверху.
    case move(id: Int, path: [M3Cell], duration: Double)
    case spawn(M3Tile, path: [M3Cell], duration: Double)
    case shuffle([(id: Int, cell: M3Cell)])
    case booster(M3Booster, M3Cell)
}

struct M3Timed {
    let t: Double
    let event: M3Event
}

struct M3Timeline {
    var events: [M3Timed] = []
    var end: Double = 0
    /// Ход засчитан (обмен с совпадением, спецфишка).
    var counted = false
    /// Сколько спецфишек сработало в финале.
    var finaleFires = 0
}

/// Детерминированный генератор: одинаковый сид - одинаковое поле.
struct M3RNG {
    private var state: UInt64

    init(seed: UInt64) { state = seed &+ 0x9E3779B97F4A7C15 }

    mutating func next() -> UInt64 {
        state = state &+ 0x9E3779B97F4A7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58476D1CE4E5B9
        z = (z ^ (z >> 27)) &* 0x94D049BB133111EB
        return z ^ (z >> 31)
    }

    mutating func int(_ n: Int) -> Int { n <= 1 ? 0 : Int(next() % UInt64(n)) }
    mutating func double() -> Double { Double(next() >> 11) / Double(1 << 53) }
    mutating func pick<T>(_ list: [T]) -> T { list[int(list.count)] }

    mutating func shuffle<T>(_ list: inout [T]) {
        guard list.count > 1 else { return }
        for i in stride(from: list.count - 1, to: 0, by: -1) {
            list.swapAt(i, int(i + 1))
        }
    }
}

struct M3Goal: Codable, Hashable {
    /// collect (собрать фишки item), crate, ice, jam.
    let type: String
    var item: String?
    let count: Int
}

struct M3Level: Codable, Identifiable {
    let id: Int
    let chapter: Int
    let cells: [String]
    let colors: [String]
    let moves: Int
    /// Сколько ходов должно остаться на 2 и 3 звезды.
    let stars: [Int]
    let goals: [M3Goal]
    var intro: String?
    var hard: Bool?

    var rows: Int { cells.count }
    var cols: Int { cells.first?.count ?? 0 }
}

struct M3Board {
    let rows: Int
    let cols: Int
    let colorCount: Int
    let goals: [M3Goal]
    private let goalColors: [Int?]
    private(set) var valid: [Bool]
    private(set) var tiles: [M3Tile?]
    private(set) var crate: [Int]
    private(set) var ice: [Int]
    private(set) var jam: [Int]
    private(set) var gotColors: [Int]
    private(set) var gotCrate = 0
    private(set) var gotIce = 0
    private(set) var gotJam = 0
    private var rng: M3RNG
    private var nextId = 1

    private struct Pending {
        let t: Double
        let id: Int?
        let cell: M3Cell
        let fire: M3Fire
    }

    private var out: [M3Timed] = []
    private var fires: [Pending] = []
    private var lastHit: Double = 0

    // Тайминги (секунды).
    static let swapTime = 0.17
    static let popTime = 0.16
    static let whiskFlight = 0.42
    /// Ускорение падения: клеток в секунду в квадрате.
    static let gravity = 120.0

    init(level: M3Level, seed: UInt64) {
        rows = level.rows
        cols = level.cols
        colorCount = level.colors.count
        goals = level.goals
        goalColors = level.goals.map { g in g.type == "collect" ? g.item.flatMap { level.colors.firstIndex(of: $0) } : nil }
        rng = M3RNG(seed: seed)
        let chars = level.cells.flatMap { Array($0) }
        valid = chars.map { $0 != "-" }
        crate = chars.map { Int(String($0)).map { min(3, max(0, $0)) } ?? 0 }
        ice = chars.map { $0 == "i" || $0 == "k" ? 1 : ($0 == "I" ? 2 : 0) }
        jam = chars.map { $0 == "j" || $0 == "k" ? 1 : 0 }
        tiles = Array(repeating: nil, count: rows * cols)
        gotColors = Array(repeating: 0, count: level.colors.count)
        fillInitial()
    }

    // MARK: - Клетки

    @inline(__always) func index(_ p: M3Cell) -> Int { p.r * cols + p.c }
    @inline(__always) func inBounds(_ p: M3Cell) -> Bool { p.r >= 0 && p.r < rows && p.c >= 0 && p.c < cols }
    func inside(_ p: M3Cell) -> Bool { inBounds(p) && valid[index(p)] }
    func tile(_ p: M3Cell) -> M3Tile? { inBounds(p) ? tiles[index(p)] : nil }
    func color(_ p: M3Cell) -> Int? { tile(p)?.kind.color }
    func movable(_ p: M3Cell) -> Bool { inside(p) && tiles[index(p)] != nil && ice[index(p)] == 0 }
    func isEmpty(_ p: M3Cell) -> Bool { inside(p) && tiles[index(p)] == nil && crate[index(p)] == 0 }
    func crateLeft(_ p: M3Cell) -> Int { inBounds(p) ? crate[index(p)] : 0 }
    func iceLeft(_ p: M3Cell) -> Int { inBounds(p) ? ice[index(p)] : 0 }
    func hasJam(_ p: M3Cell) -> Bool { inBounds(p) && jam[index(p)] > 0 }

    var allCells: [M3Cell] {
        var list: [M3Cell] = []
        list.reserveCapacity(rows * cols)
        for r in 0..<rows { for c in 0..<cols { list.append(M3Cell(r, c)) } }
        return list
    }

    /// Верхняя клетка столбца: над ней появляются новые фишки.
    func topRow(_ c: Int) -> Int {
        for r in 0..<rows where valid[r * cols + c] { return r }
        return 0
    }

    private mutating func newTile(_ kind: M3Kind) -> M3Tile {
        nextId += 1
        return M3Tile(id: nextId, kind: kind)
    }

    // MARK: - Стартовое поле

    private mutating func fillInitial() {
        for _ in 0..<300 {
            for p in allCells {
                let i = index(p)
                guard valid[i], crate[i] == 0 else {
                    tiles[i] = nil
                    continue
                }
                let options = (0..<colorCount).filter { !wouldMatch(p, $0) }
                tiles[i] = newTile(.color(options.isEmpty ? rng.int(colorCount) : rng.pick(options)))
            }
            if hasMove() { return }
        }
    }

    private func wouldMatch(_ p: M3Cell, _ k: Int) -> Bool {
        let (r, c) = (p.r, p.c)
        if color(M3Cell(r, c - 1)) == k && color(M3Cell(r, c - 2)) == k { return true }
        if color(M3Cell(r - 1, c)) == k && color(M3Cell(r - 2, c)) == k { return true }
        return color(M3Cell(r - 1, c)) == k && color(M3Cell(r, c - 1)) == k && color(M3Cell(r - 1, c - 1)) == k
    }

    /// Спецфишки на старте (бустеры перед уровнем, серия побед): обычные фишки превращаются в них.
    mutating func placeStart(_ specials: [M3Special]) -> M3Timeline {
        begin()
        var spots = allCells.filter { movable($0) && color($0) != nil && !hasJam($0) }
        rng.shuffle(&spots)
        for (i, special) in specials.enumerated() where i < spots.count {
            let p = spots[i]
            guard var t = tiles[index(p)] else { continue }
            let kind: M3Special = special.isPin ? (rng.int(2) == 0 ? .rowPin : .colPin) : special
            t.kind = .special(kind)
            tiles[index(p)] = t
            emit(0.35 + Double(i) * 0.22, .convert(id: t.id, cell: p, kind, color: nil))
        }
        return finish(end: 0.35 + Double(specials.count) * 0.22 + 0.35, counted: false)
    }

    // MARK: - Совпадения

    struct Group {
        var cells: [M3Cell]
        var rowsRuns: [[M3Cell]]
        var colRuns: [[M3Cell]]
        var squares: Int
    }

    func findGroups() -> [Group] {
        var shapes: [(kind: Int, cells: [M3Cell])] = []
        for r in 0..<rows {
            var c = 0
            while c < cols {
                let k = color(M3Cell(r, c))
                var e = c
                if let k = k {
                    while color(M3Cell(r, e + 1)) == k { e += 1 }
                    if e - c >= 2 { shapes.append((0, (c...e).map { M3Cell(r, $0) })) }
                }
                c = e + 1
            }
        }
        for c in 0..<cols {
            var r = 0
            while r < rows {
                let k = color(M3Cell(r, c))
                var e = r
                if let k = k {
                    while color(M3Cell(e + 1, c)) == k { e += 1 }
                    if e - r >= 2 { shapes.append((1, (r...e).map { M3Cell($0, c) })) }
                }
                r = e + 1
            }
        }
        if rows > 1 && cols > 1 {
            for r in 0..<(rows - 1) {
                for c in 0..<(cols - 1) {
                    guard let k = color(M3Cell(r, c)) else { continue }
                    if color(M3Cell(r, c + 1)) == k && color(M3Cell(r + 1, c)) == k && color(M3Cell(r + 1, c + 1)) == k {
                        shapes.append((2, [M3Cell(r, c), M3Cell(r, c + 1), M3Cell(r + 1, c), M3Cell(r + 1, c + 1)]))
                    }
                }
            }
        }
        guard !shapes.isEmpty else { return [] }
        var parent = Array(0..<shapes.count)
        func find(_ i: Int) -> Int {
            var i = i
            while parent[i] != i {
                parent[i] = parent[parent[i]]
                i = parent[i]
            }
            return i
        }
        var owner: [M3Cell: Int] = [:]
        for (i, shape) in shapes.enumerated() {
            for cell in shape.cells {
                if let o = owner[cell] {
                    parent[find(i)] = find(o)
                } else {
                    owner[cell] = i
                }
            }
        }
        var order: [Int] = []
        var byRoot: [Int: Group] = [:]
        for (i, shape) in shapes.enumerated() {
            let root = find(i)
            var g = byRoot[root] ?? Group(cells: [], rowsRuns: [], colRuns: [], squares: 0)
            if byRoot[root] == nil { order.append(root) }
            for cell in shape.cells where !g.cells.contains(cell) { g.cells.append(cell) }
            switch shape.kind {
            case 0: g.rowsRuns.append(shape.cells)
            case 1: g.colRuns.append(shape.cells)
            default: g.squares += 1
            }
            byRoot[root] = g
        }
        return order.compactMap { byRoot[$0] }.map { g in
            var g = g
            g.cells.sort { ($0.r, $0.c) < ($1.r, $1.c) }
            return g
        }
    }

    static func special(of g: Group) -> M3Special? {
        let longest = (g.rowsRuns + g.colRuns).map(\.count).max() ?? 0
        if longest >= 5 { return .rainbow }
        if !g.rowsRuns.isEmpty && !g.colRuns.isEmpty { return .bomb }
        if g.rowsRuns.contains(where: { $0.count == 4 }) { return .rowPin }
        if g.colRuns.contains(where: { $0.count == 4 }) { return .colPin }
        if g.squares > 0 { return .whisk }
        return nil
    }

    private func anchor(of g: Group, prefer: [M3Cell]) -> M3Cell? {
        let free = g.cells.filter { ice[index($0)] == 0 }
        guard !free.isEmpty else { return nil }
        if let p = prefer.first(where: { free.contains($0) }) { return p }
        if let both = free.first(where: { p in g.rowsRuns.contains { $0.contains(p) } && g.colRuns.contains { $0.contains(p) } }) {
            return both
        }
        if let longest = (g.rowsRuns + g.colRuns).max(by: { $0.count < $1.count }) {
            let mid = longest.filter { free.contains($0) }
            if !mid.isEmpty { return mid[(mid.count - 1) / 2] }
        }
        return free[0]
    }

    // MARK: - Ходы

    func hasMove() -> Bool { !moves(first: true).isEmpty }

    /// Засчитываемые ходы: (a, nil) - тап по спецфишке, (a, b) - обмен.
    func moves(first: Bool = false) -> [(M3Cell, M3Cell?)] {
        var list: [(M3Cell, M3Cell?)] = []
        var copy = self
        for p in allCells where movable(p) {
            if tile(p)?.kind.special != nil {
                list.append((p, nil))
                if first { return list }
            }
            for q in [M3Cell(p.r, p.c + 1), M3Cell(p.r + 1, p.c)] where movable(q) {
                if tile(p)?.kind.special != nil || tile(q)?.kind.special != nil || copy.swapMakesMatch(p, q) {
                    list.append((p, q))
                    if first { return list }
                }
            }
        }
        return list
    }

    private mutating func swapMakesMatch(_ a: M3Cell, _ b: M3Cell) -> Bool {
        let ia = index(a), ib = index(b)
        guard let ta = tiles[ia], let tb = tiles[ib], ta.kind != tb.kind else { return false }
        tiles.swapAt(ia, ib)
        let ok = matchAt(a) || matchAt(b)
        tiles.swapAt(ia, ib)
        return ok
    }

    private func matchAt(_ p: M3Cell) -> Bool {
        guard let k = color(p) else { return false }
        var n = 1
        var x = p.c - 1
        while color(M3Cell(p.r, x)) == k { n += 1; x -= 1 }
        x = p.c + 1
        while color(M3Cell(p.r, x)) == k { n += 1; x += 1 }
        if n >= 3 { return true }
        n = 1
        var y = p.r - 1
        while color(M3Cell(y, p.c)) == k { n += 1; y -= 1 }
        y = p.r + 1
        while color(M3Cell(y, p.c)) == k { n += 1; y += 1 }
        if n >= 3 { return true }
        for dr in [-1, 0] {
            for dc in [-1, 0] {
                let r0 = p.r + dr, c0 = p.c + dc
                if color(M3Cell(r0, c0)) == k && color(M3Cell(r0, c0 + 1)) == k
                    && color(M3Cell(r0 + 1, c0)) == k && color(M3Cell(r0 + 1, c0 + 1)) == k {
                    return true
                }
            }
        }
        return false
    }

    /// Подсказка: ход, который дает самую сильную спецфишку, иначе любой обычный.
    func hint() -> (M3Cell, M3Cell)? {
        var best: (M3Cell, M3Cell)?
        var bestRank = -1
        let rank: [M3Special: Int] = [.whisk: 1, .rowPin: 2, .colPin: 2, .bomb: 3, .rainbow: 4]
        for (a, b) in moves() {
            guard let b = b else { continue }
            var copy = self
            copy.tiles.swapAt(index(a), index(b))
            var r = 0
            if tile(a)?.kind.special != nil && tile(b)?.kind.special != nil {
                r = 6
            } else if tile(a)?.kind.special != nil || tile(b)?.kind.special != nil {
                r = 5
            } else {
                for g in copy.findGroups() where g.cells.contains(a) || g.cells.contains(b) {
                    r = max(r, Self.special(of: g).flatMap { rank[$0] } ?? 0)
                }
            }
            if r > bestRank {
                bestRank = r
                best = (a, b)
            }
        }
        return best
    }

    // MARK: - Ход игрока

    /// Обмен: b - клетка, куда потянули фишку из a. nil - обмен невозможен (лед, ящик, не соседи).
    mutating func swap(_ a: M3Cell, _ b: M3Cell) -> M3Timeline? {
        guard abs(a.r - b.r) + abs(a.c - b.c) == 1, movable(a), movable(b),
              let ta = tiles[index(a)], let tb = tiles[index(b)] else { return nil }
        begin()
        let sa = ta.kind.special, sb = tb.kind.special
        if let sa = sa, let sb = sb {
            emit(0, .swap(a, b, back: false))
            tiles[index(a)] = nil
            tiles[index(b)] = nil
            combo(ta, tb, sa, sb, at: b, t: Self.swapTime * 0.6)
            let end = settle(from: Self.swapTime, prefer: [])
            return finish(end: end, counted: true)
        }
        if sa != nil || sb != nil {
            emit(0, .swap(a, b, back: false))
            tiles.swapAt(index(a), index(b))
            let (pos, special, other) = sa != nil ? (b, ta, tb) : (a, tb, ta)
            tiles[index(pos)] = nil
            var fire = M3Fire(special: special.kind.special ?? .bomb)
            fire.color = other.kind.color
            schedule(Self.swapTime, id: special.id, cell: pos, fire)
            let end = settle(from: Self.swapTime, prefer: [])
            return finish(end: end, counted: true)
        }
        guard swapMakesMatch(a, b) else {
            emit(0, .swap(a, b, back: true))
            return finish(end: Self.swapTime * 2, counted: false)
        }
        emit(0, .swap(a, b, back: false))
        tiles.swapAt(index(a), index(b))
        let end = settle(from: Self.swapTime, prefer: [b, a])
        return finish(end: end, counted: true)
    }

    /// Тап по спецфишке: срабатывает на месте.
    mutating func tap(_ p: M3Cell) -> M3Timeline? {
        guard movable(p), let t = tiles[index(p)], let special = t.kind.special else { return nil }
        begin()
        tiles[index(p)] = nil
        schedule(0.02, id: t.id, cell: p, M3Fire(special: special))
        let end = settle(from: 0.02, prefer: [])
        return finish(end: end, counted: true)
    }

    /// Бустер во время уровня. Ход не тратится.
    mutating func use(_ booster: M3Booster, at p: M3Cell) -> M3Timeline? {
        begin()
        let t0 = 0.32
        switch booster {
        case .mallet:
            guard inside(p), tiles[index(p)] != nil || crate[index(p)] > 0 else { return nil }
            emit(0, .booster(.mallet, p))
            hit(p, t: t0)
        case .knife:
            guard inside(p) else { return nil }
            emit(0, .booster(.knife, p))
            for c in 0..<cols { hit(M3Cell(p.r, c), t: t0 + 0.035 * Double(c)) }
        case .spatula:
            guard inside(p) else { return nil }
            emit(0, .booster(.spatula, p))
            for r in 0..<rows { hit(M3Cell(r, p.c), t: t0 + 0.035 * Double(r)) }
        case .mixer:
            emit(0, .booster(.mixer, p))
            let end = shuffle(at: 0.3)
            return finish(end: end, counted: false)
        default:
            return nil
        }
        runFires()
        let end = settle(from: t0, prefer: [])
        return finish(end: end, counted: false)
    }

    /// Финал после победы: оставшиеся ходы превращаются в скалки, потом срабатывают все спецфишки поля.
    mutating func finale(moves left: Int) -> M3Timeline {
        begin()
        var t = 0.2
        var spots = allCells.filter { movable($0) && color($0) != nil }
        rng.shuffle(&spots)
        for (i, p) in spots.prefix(left).enumerated() {
            guard var tile = tiles[index(p)] else { continue }
            let kind: M3Special = rng.int(2) == 0 ? .rowPin : .colPin
            tile.kind = .special(kind)
            tiles[index(p)] = tile
            emit(t + Double(i) * 0.09, .convert(id: tile.id, cell: p, kind, color: nil))
        }
        t += Double(min(left, spots.count)) * 0.09 + 0.35
        var fired = 0
        for _ in 0..<6 {
            let specials = allCells.filter { movable($0) && tile($0)?.kind.special != nil }
            guard !specials.isEmpty else { break }
            for (i, p) in specials.enumerated() {
                guard let tile = tiles[index(p)], let s = tile.kind.special else { continue }
                tiles[index(p)] = nil
                schedule(t + Double(i) * 0.14, id: tile.id, cell: p, M3Fire(special: s))
                fired += 1
            }
            t = settle(from: t, prefer: []) + 0.1
        }
        var line = finish(end: t, counted: false)
        line.finaleFires = fired
        return line
    }

    // MARK: - Лента событий

    private mutating func begin() {
        out = []
        fires = []
        lastHit = 0
    }

    private mutating func emit(_ t: Double, _ e: M3Event) {
        out.append(M3Timed(t: t, event: e))
    }

    private mutating func finish(end: Double, counted: Bool) -> M3Timeline {
        let events = out.enumerated().sorted { ($0.element.t, $0.offset) < ($1.element.t, $1.offset) }.map(\.element)
        out = []
        return M3Timeline(events: events, end: max(end, (events.last?.t ?? 0) + 0.2), counted: counted)
    }

    private mutating func schedule(_ t: Double, id: Int?, cell: M3Cell, _ fire: M3Fire) {
        fires.append(Pending(t: t, id: id, cell: cell, fire: fire))
    }

    // MARK: - Удары

    /// Удар по клетке: ящик, варенье, лед, фишка. Задетая спецфишка срабатывает чуть позже.
    private mutating func hit(_ p: M3Cell, t: Double, toward: M3Cell? = nil) {
        guard inside(p) else { return }
        let i = index(p)
        lastHit = max(lastHit, t)
        if crate[i] > 0 {
            crate[i] -= 1
            if crate[i] == 0 { gotCrate += 1 }
            emit(t, .crate(p, left: crate[i]))
            return
        }
        if jam[i] > 0 {
            jam[i] = 0
            gotJam += 1
            emit(t, .jam(p))
        }
        guard let tile = tiles[i] else { return }
        if ice[i] > 0 {
            ice[i] -= 1
            if ice[i] == 0 { gotIce += 1 }
            emit(t, .ice(p, left: ice[i]))
            return
        }
        tiles[i] = nil
        switch tile.kind {
        case let .color(k):
            gotColors[k] += 1
            emit(t, .pop(id: tile.id, cell: p, color: k, toward: toward))
        case let .special(s):
            schedule(t + 0.07, id: tile.id, cell: p, M3Fire(special: s))
        }
    }

    private mutating func clear(_ groups: [Group], at t: Double, prefer: [M3Cell]) {
        for g in groups {
            let kind = Self.special(of: g)
            let target = kind == nil ? nil : anchor(of: g, prefer: prefer)
            var crates: [M3Cell] = []
            for p in g.cells {
                for q in [M3Cell(p.r - 1, p.c), M3Cell(p.r + 1, p.c), M3Cell(p.r, p.c - 1), M3Cell(p.r, p.c + 1)]
                where inside(q) && crate[index(q)] > 0 && !crates.contains(q) {
                    crates.append(q)
                }
            }
            for p in g.cells { hit(p, t: t, toward: p == target ? nil : target) }
            for q in crates { hit(q, t: t + 0.05) }
            if let kind = kind, let a = target, tiles[index(a)] == nil {
                let tile = newTile(.special(kind))
                tiles[index(a)] = tile
                emit(t + Self.popTime, .create(tile, a))
            }
        }
    }

    private mutating func runFires() {
        while !fires.isEmpty {
            var best = 0
            for i in fires.indices where fires[i].t < fires[best].t { best = i }
            let f = fires.remove(at: best)
            perform(f)
        }
    }

    private mutating func perform(_ f: Pending) {
        var fire = f.fire
        let (r, c) = (f.cell.r, f.cell.c)
        var hits: [(M3Cell, Double)] = []
        func line(row: Int) { for x in 0..<cols { hits.append((M3Cell(row, x), 0.032 * Double(abs(x - c)))) } }
        func line(col: Int) { for y in 0..<rows { hits.append((M3Cell(y, col), 0.032 * Double(abs(y - r)))) } }
        switch fire.special {
        case .rowPin, .colPin:
            let half = fire.width / 2
            for d in -half...half {
                if fire.cross || fire.special == .rowPin { line(row: r + d) }
                if fire.cross || fire.special == .colPin { line(col: c + d) }
            }
        case .bomb:
            let rr = fire.radius
            for dr in -rr...rr {
                for dc in -rr...rr {
                    hits.append((M3Cell(r + dr, c + dc), 0.045 * Double(max(abs(dr), abs(dc)))))
                }
            }
        case .whisk:
            let near = [f.cell, M3Cell(r - 1, c), M3Cell(r + 1, c), M3Cell(r, c - 1), M3Cell(r, c + 1)]
            for p in near { hits.append((p, 0.02)) }
            if fire.targets.isEmpty {
                var exclude = Set(near)
                let count = fire.carry == nil && fire.width > 1 ? 3 : 1
                for _ in 0..<count {
                    if let target = whiskTarget(excluding: exclude) {
                        fire.targets.append(target)
                        exclude.insert(target)
                    }
                }
            }
            for target in fire.targets {
                if let carry = fire.carry {
                    var carried = M3Fire(special: carry)
                    if carry.isPin { carried.special = rng.int(2) == 0 ? .rowPin : .colPin }
                    schedule(f.t + Self.whiskFlight, id: nil, cell: target, carried)
                    lastHit = max(lastHit, f.t + Self.whiskFlight)
                } else {
                    hits.append((target, Self.whiskFlight))
                }
            }
        case .rainbow:
            if fire.all {
                for p in allCells { hits.append((p, 0.25 + 0.03 * Double(abs(p.r - r) + abs(p.c - c)))) }
            } else {
                let k = fire.color ?? mostCommonColor()
                fire.color = k
                let targets = allCells.filter { k != nil && color($0) == k }
                    .sorted { abs($0.r - r) + abs($0.c - c) < abs($1.r - r) + abs($1.c - c) }
                fire.targets = targets
                for (i, p) in targets.enumerated() { hits.append((p, 0.22 + 0.028 * Double(i))) }
            }
        }
        emit(f.t, .fire(id: f.id, cell: f.cell, fire))
        lastHit = max(lastHit, f.t + 0.1)
        for (p, d) in hits.sorted(by: { $0.1 < $1.1 }) { hit(p, t: f.t + d) }
    }

    private mutating func combo(_ ta: M3Tile, _ tb: M3Tile, _ a: M3Special, _ b: M3Special, at p: M3Cell, t: Double) {
        emit(t - 0.05, .combo(a: ta.id, b: tb.id, cell: p, a, b))
        let t = t + 0.18
        let kinds: Set<M3Special> = [a, b]
        if a.isPin && b.isPin {
            var f = M3Fire(special: .rowPin)
            f.cross = true
            schedule(t, id: nil, cell: p, f)
        } else if a == .rainbow && b == .rainbow {
            var f = M3Fire(special: .rainbow)
            f.all = true
            schedule(t, id: nil, cell: p, f)
        } else if kinds.contains(.rainbow) {
            let other = a == .rainbow ? b : a
            let k = mostCommonColor()
            var targets = allCells.filter { k != nil && color($0) == k && ice[index($0)] == 0 }
            targets.sort { abs($0.r - p.r) + abs($0.c - p.c) < abs($1.r - p.r) + abs($1.c - p.c) }
            var beam = M3Fire(special: .rainbow)
            beam.color = k
            beam.targets = targets
            emit(t, .fire(id: nil, cell: p, beam))
            for (i, q) in targets.enumerated() {
                guard let tile = tiles[index(q)], let kk = tile.kind.color else { continue }
                let kind: M3Special = other.isPin ? (rng.int(2) == 0 ? .rowPin : .colPin) : other
                gotColors[kk] += 1
                tiles[index(q)] = nil
                emit(t + 0.2 + 0.04 * Double(i), .convert(id: tile.id, cell: q, kind, color: kk))
                schedule(t + 0.45 + 0.04 * Double(targets.count) + 0.09 * Double(i), id: tile.id, cell: q, M3Fire(special: kind))
            }
            lastHit = max(lastHit, t + 0.5)
        } else if a == .bomb && b == .bomb {
            var f = M3Fire(special: .bomb)
            f.radius = 3
            schedule(t, id: nil, cell: p, f)
        } else if kinds.contains(.bomb) && (a.isPin || b.isPin) {
            var f = M3Fire(special: .rowPin)
            f.cross = true
            f.width = 3
            schedule(t, id: nil, cell: p, f)
        } else if a == .whisk && b == .whisk {
            var f = M3Fire(special: .whisk)
            f.width = 3
            schedule(t, id: nil, cell: p, f)
        } else {
            var f = M3Fire(special: .whisk)
            f.carry = a == .whisk ? b : a
            schedule(t, id: nil, cell: p, f)
        }
        runFires()
    }

    func mostCommonColor() -> Int? {
        var counts = Array(repeating: 0, count: colorCount)
        for t in tiles { if let k = t?.kind.color { counts[k] += 1 } }
        guard let best = counts.max(), best > 0 else { return nil }
        return counts.firstIndex(of: best)
    }

    /// Что еще нужно собрать.
    func remaining(_ goal: Int) -> Int {
        let g = goals[goal]
        return max(0, g.count - progress(goal))
    }

    func progress(_ goal: Int) -> Int {
        switch goals[goal].type {
        case "collect": return goalColors[goal].map { gotColors[$0] } ?? 0
        case "crate": return gotCrate
        case "ice": return gotIce
        case "jam": return gotJam
        default: return 0
        }
    }

    var won: Bool { goals.indices.allSatisfy { remaining($0) == 0 } }

    /// Цель венчика: нужные ящики, лед, варенье, потом фишки нужного цвета, потом любая фишка.
    private mutating func whiskTarget(excluding exclude: Set<M3Cell>) -> M3Cell? {
        var wantColors = Set<Int>()
        var wantCrate = false, wantIce = false, wantJam = false
        for i in goals.indices where remaining(i) > 0 {
            switch goals[i].type {
            case "collect": if let k = goalColors[i] { wantColors.insert(k) }
            case "crate": wantCrate = true
            case "ice": wantIce = true
            case "jam": wantJam = true
            default: break
            }
        }
        var best = 0
        var options: [M3Cell] = []
        for p in allCells where inside(p) && !exclude.contains(p) {
            let i = index(p)
            var score = 0
            if crate[i] > 0 {
                score = wantCrate ? 3 : 0
            } else if ice[i] > 0 && wantIce {
                score = 3
            } else if jam[i] > 0 && wantJam {
                score = 3
            } else if let k = tiles[i]?.kind.color, wantColors.contains(k) {
                score = 2
            } else if tiles[i] != nil {
                score = 1
            }
            if score > best {
                best = score
                options = []
            }
            if score > 0 && score == best { options.append(p) }
        }
        return options.isEmpty ? nil : rng.pick(options)
    }

    // MARK: - Падение

    /// Падение и новые фишки. Возвращает время, когда все приземлились.
    private mutating func gravity(at t0: Double) -> Double {
        var paths: [Int: [M3Cell]] = [:]
        var spawned: [Int: M3Tile] = [:]
        var spawnCount = Array(repeating: 0, count: cols)
        while true {
            var moved = false
            for c in 0..<cols {
                for r in stride(from: rows - 1, through: 0, by: -1) {
                    let p = M3Cell(r, c)
                    guard isEmpty(p) else { continue }
                    var y = r - 1
                    while y >= 0 && (!valid[y * cols + c] || isEmpty(M3Cell(y, c))) { y -= 1 }
                    if y < 0 {
                        let tile = newTile(.color(rng.int(colorCount)))
                        tiles[index(p)] = tile
                        spawned[tile.id] = tile
                        let start = M3Cell(topRow(c) - 1 - spawnCount[c], c)
                        spawnCount[c] += 1
                        paths[tile.id] = [start, p]
                        moved = true
                    } else if movable(M3Cell(y, c)), let tile = tiles[y * cols + c] {
                        tiles[index(p)] = tile
                        tiles[y * cols + c] = nil
                        paths[tile.id, default: [M3Cell(y, c)]].append(p)
                        moved = true
                    }
                }
            }
            if moved { continue }
            outer: for r in stride(from: rows - 1, to: 0, by: -1) {
                for c in 0..<cols where isEmpty(M3Cell(r, c)) {
                    for x in [c - 1, c + 1] {
                        let q = M3Cell(r - 1, x)
                        if movable(q), let tile = tiles[index(q)] {
                            tiles[index(M3Cell(r, c))] = tile
                            tiles[index(q)] = nil
                            paths[tile.id, default: [q]].append(M3Cell(r, c))
                            moved = true
                            break outer
                        }
                    }
                }
            }
            if !moved { break }
        }
        var end = t0
        for (id, path) in paths {
            var length = 0.0
            for i in 1..<path.count {
                let a = path[i - 1], b = path[i]
                length += hypot(Double(b.r - a.r), Double(b.c - a.c))
            }
            let duration = max(0.08, (2 * length / Self.gravity).squareRoot())
            end = max(end, t0 + duration)
            if let tile = spawned[id] {
                emit(t0, .spawn(tile, path: path, duration: duration))
            } else {
                emit(t0, .move(id: id, path: path, duration: duration))
            }
        }
        return paths.isEmpty ? t0 : end + 0.04
    }

    // MARK: - Разбор хода

    /// Совпадения, взрывы и падения до покоя. Возвращает время конца.
    private mutating func settle(from t: Double, prefer: [M3Cell]) -> Double {
        var t = t
        var prefer = prefer
        for _ in 0..<60 {
            let groups = findGroups()
            if !groups.isEmpty {
                clear(groups, at: t, prefer: prefer)
                prefer = []
            }
            runFires()
            let start = max(t, lastHit + (groups.isEmpty && lastHit <= t ? 0 : 0.1))
            let landed = gravity(at: start)
            if landed == start && groups.isEmpty && fires.isEmpty { break }
            t = landed
        }
        if !hasMove() { t = shuffle(at: t + 0.15) }
        return t
    }

    private mutating func shuffle(at t: Double) -> Double {
        let cells = allCells.filter { movable($0) && color($0) != nil }
        guard cells.count > 1 else { return t }
        var originals = cells.compactMap { tiles[index($0)] }
        for attempt in 0..<200 {
            var order = originals
            rng.shuffle(&order)
            if attempt == 199 {
                order = order.map { M3Tile(id: $0.id, kind: .color(rng.int(colorCount))) }
            }
            for (p, tile) in zip(cells, order) { tiles[index(p)] = tile }
            if findGroups().isEmpty && hasMove() { break }
            if attempt == 199 && !hasMove(), let p = cells.first, let tile = tiles[index(p)] {
                tiles[index(p)] = M3Tile(id: tile.id, kind: .special(.bomb))
            }
            originals = order
        }
        emit(t, .shuffle(cells.compactMap { p in tiles[index(p)].map { (id: $0.id, cell: p) } }))
        return t + 0.6
    }
}
