import Foundation

/// Продукт на полке. uid нужен, чтобы анимировать один и тот же спрайт между состояниями.
struct Piece: Hashable {
    let uid: Int
    let item: String
    var hidden: Bool
}

/// Срабатывание полки: тройка или рецепт ушли покупателю.
struct Fire {
    let shelf: Int
    let pieces: [Piece]
    let order: Order
    /// Позиция покупателя в оставшейся очереди в момент срабатывания.
    let queueIndex: Int
}

struct MoveOutcome {
    let piece: Piece
    let from: Int
    let fromSlot: Int
    let to: Int
    let toSlot: Int
    let fires: [Fire]
}

/// Правила поля. Должны совпадать с tools/levels/rules.py, по которому проверены уровни.
struct Board {
    static let slots = 3

    /// полка -> ряд (0 - передний) -> слот
    private(set) var shelves: [[[Piece?]]]
    /// Оставшиеся заказы в порядке очереди.
    private(set) var orders: [Order]

    private let catalog: Catalog

    init(level: LevelData, catalog: Catalog = .shared) {
        var uid = 0
        var built: [[[Piece?]]] = []
        for layers in level.shelves {
            var shelf: [[Piece?]] = []
            for layer in layers {
                var row: [Piece?] = []
                for cell in layer {
                    if let cell = cell {
                        uid += 1
                        let hidden = cell.hasPrefix("?")
                        let item = hidden ? String(cell.dropFirst()) : cell
                        row.append(Piece(uid: uid, item: item, hidden: hidden))
                    } else {
                        row.append(nil)
                    }
                }
                while row.count < Board.slots { row.append(nil) }
                shelf.append(row)
            }
            if shelf.isEmpty { shelf = [[nil, nil, nil]] }
            built.append(shelf)
        }
        self.shelves = built
        self.orders = level.orders
        self.catalog = catalog
        for s in shelves.indices { normalize(s) }
        _ = settle(Array(shelves.indices))
    }

    // MARK: - Состояние

    var isWon: Bool { orders.isEmpty }

    var hasFreeSlot: Bool {
        shelves.contains { $0[0].contains { $0 == nil } }
    }

    var isStuck: Bool { !isWon && !hasFreeSlot }

    func front(_ shelf: Int) -> [Piece?] { shelves[shelf][0] }

    func peek(_ shelf: Int) -> [Piece?]? { shelves[shelf].count > 1 ? shelves[shelf][1] : nil }

    func depth(_ shelf: Int) -> Int { shelves[shelf].count }

    func freeSlot(in shelf: Int) -> Int? { shelves[shelf][0].firstIndex { $0 == nil } }

    // MARK: - Ходы

    mutating func move(from src: Int, slot: Int, to dst: Int) -> MoveOutcome? {
        guard src != dst, shelves.indices.contains(src), shelves.indices.contains(dst),
              slot >= 0, slot < Board.slots,
              let piece = shelves[src][0][slot],
              let target = freeSlot(in: dst) else { return nil }
        shelves[src][0][slot] = nil
        shelves[dst][0][target] = piece
        var changed: [Int] = []
        if shelves[src][0].allSatisfy({ $0 == nil }) && shelves[src].count > 1 {
            shelves[src].removeFirst()
            reveal(src)
            changed.append(src)
        }
        changed.append(dst)
        let fires = settle(changed)
        return MoveOutcome(piece: piece, from: src, fromSlot: slot, to: dst, toSlot: target, fires: fires)
    }

    mutating func addShelf() {
        shelves.append([[nil, nil, nil]])
    }

    private mutating func normalize(_ s: Int) {
        while shelves[s].count > 1 && shelves[s][0].allSatisfy({ $0 == nil }) {
            shelves[s].removeFirst()
        }
        reveal(s)
    }

    private mutating func reveal(_ s: Int) {
        for k in 0..<Board.slots {
            if var piece = shelves[s][0][k], piece.hidden {
                piece.hidden = false
                shelves[s][0][k] = piece
            }
        }
    }

    private mutating func settle(_ changed: [Int]) -> [Fire] {
        var fires: [Fire] = []
        var queue = changed
        while let s = queue.popLast() {
            let front = shelves[s][0]
            let names = front.compactMap { $0?.item }
            guard names.count == Board.slots,
                  let result = catalog.result(of: names),
                  let index = orders.firstIndex(of: result) else { continue }
            orders.remove(at: index)
            fires.append(Fire(shelf: s, pieces: front.compactMap { $0 }, order: result, queueIndex: index))
            shelves[s][0] = [nil, nil, nil]
            if shelves[s].count > 1 {
                shelves[s].removeFirst()
                reveal(s)
            }
            queue.append(s)
        }
        return fires
    }

    // MARK: - Подсказка

    /// Лучший ход на один шаг вперед: срабатывание, потом заготовка тройки или рецепта.
    func hint() -> (from: Int, slot: Int, to: Int)? {
        var best: (score: Double, move: (Int, Int, Int))?
        for s in shelves.indices {
            var seen = Set<String>()
            for k in 0..<Board.slots {
                guard let piece = shelves[s][0][k], !seen.contains(piece.item) else { continue }
                seen.insert(piece.item)
                for d in shelves.indices where d != s && freeSlot(in: d) != nil {
                    var copy = self
                    guard let outcome = copy.move(from: s, slot: k, to: d) else { continue }
                    var score = Double(outcome.fires.count) * 100
                    score -= copy.heuristic()
                    if best == nil || score > best!.score {
                        best = (score, (s, k, d))
                    }
                }
            }
        }
        guard let move = best?.move else { return nil }
        return (move.0, move.1, move.2)
    }

    /// Та же оценка, что в решателе: меньше - ближе к решению.
    func heuristic() -> Double {
        var score = Double(orders.count) * 10
        var buried = 0.0
        for layers in shelves {
            let front = layers[0].compactMap { $0?.item }
            var counts: [String: Int] = [:]
            for item in front { counts[item, default: 0] += 1 }
            for (_, n) in counts where n >= 2 { score -= 1.5 }
            if front.count == 2 && front[0] != front[1] {
                if catalog.dishes.contains(where: { d in front.allSatisfy { d.ingredients.contains($0) } }) {
                    score -= 1
                }
            }
            for (depth, layer) in layers.enumerated() where depth > 0 {
                buried += Double(depth * layer.compactMap { $0 }.count)
            }
        }
        let free = shelves.reduce(0) { $0 + $1[0].filter { $0 == nil }.count }
        if free == 0 { score += 50 }
        return score + buried * 0.08 - Double(free) * 0.2
    }
}
