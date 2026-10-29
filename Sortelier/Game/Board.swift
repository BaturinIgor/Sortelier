import Foundation

/// Продукт на полке. uid нужен, чтобы анимировать один и тот же спрайт между состояниями.
struct Piece: Hashable {
    let uid: Int
    let item: String
    var hidden: Bool
    /// Лед: продукт нельзя брать, пока не обслужено столько покупателей. 0 - без льда.
    var ice: Int = 0
}

/// Покупатель в очереди: заказ и оставшееся терпение в ходах.
struct Customer: Hashable {
    let uid: Int
    let order: Order
    var patience: Int
    /// Гурман: чаевые в несколько раз больше, иногда дарит фон.
    var gourmet: Bool = false
}

/// Срабатывание полки: тройка или рецепт ушли покупателю.
struct Fire {
    let shelf: Int
    let pieces: [Piece]
    let order: Order
    /// Позиция покупателя в оставшейся очереди в момент срабатывания.
    let queueIndex: Int
    let customer: Customer
    /// Чаевые за оставшееся терпение.
    let tip: Int
}

/// Цепочка: три сырых продукта превратились в один (мука x3 -> тесто).
struct Transform {
    let shelf: Int
    let pieces: [Piece]
    let result: Piece
    let slot: Int
}

/// Что случилось на поле после хода, по порядку.
enum BoardEvent {
    case fire(Fire)
    case transform(Transform)
}

struct MoveOutcome {
    let piece: Piece
    let from: Int
    let fromSlot: Int
    let to: Int
    let toSlot: Int
    let events: [BoardEvent]

    var fires: [Fire] {
        events.compactMap { if case let .fire(f) = $0 { return f } else { return nil } }
    }

    var transforms: [Transform] {
        events.compactMap { if case let .transform(t) = $0 { return t } else { return nil } }
    }
}

/// Цепь между двумя полками: положил продукт на одну - вторая заблокирована, пока первая не сработает.
/// Когда обе полки хоть раз сработали, цепь снимается.
struct ChainLink: Hashable {
    let a: Int
    let b: Int
    /// Полка пары, на которую положили продукт и которая еще не сработала.
    var last: Int?
    var firedA = false
    var firedB = false

    init(a: Int, b: Int) {
        self.a = a
        self.b = b
    }

    var broken: Bool { firedA && firedB }

    func contains(_ s: Int) -> Bool { s == a || s == b }

    func other(_ s: Int) -> Int { s == a ? b : a }

    func blocks(_ s: Int) -> Bool { contains(s) && last == other(s) }

    func hasFired(_ s: Int) -> Bool { s == a ? firedA : firedB }

    mutating func fired(_ s: Int) {
        if last == s { last = nil }
        if s == a { firedA = true }
        if s == b { firedB = true }
        if broken { last = nil }
    }
}

/// Правила поля. Должны совпадать с tools/levels/rules.py, по которому проверены уровни.
struct Board {
    static let slots = 3
    /// Сколько покупателей стоит у прилавка: у них тает терпение.
    static let counter = 3
    /// Во сколько раз больше чаевые у гурмана. Совпадает с GOURMET_MULT в rules.py.
    static let gourmetTip = 5

    /// полка -> ряд (0 - передний) -> слот
    private(set) var shelves: [[[Piece?]]]
    /// Очередь покупателей.
    private(set) var queue: [Customer]
    /// Терпение покупателя в ходах и максимум чаевых. 0 - без терпения и чаевых.
    let patienceMax: Int
    let tipMax: Int
    /// Замки полок: сколько покупателей надо обслужить, чтобы открыть полку.
    private(set) var locks: [Int]
    /// Замки с ключом: полка закрыта, пока не обслужен заказ с этим спрайтом (продукт или "dish_<блюдо>").
    private(set) var keys: [String?]
    /// Цепи между полками. Совпадают с Obstacles в rules.py.
    private(set) var chains: [ChainLink]
    /// Сколько покупателей уже обслужено: по этому числу тает лед и открываются замки.
    private(set) var served = 0
    /// Сколько ходов терпение еще стоит на паузе (бустер).
    private(set) var pauseLeft = 0
    private var nextUid = 0

    /// Оставшиеся заказы в порядке очереди.
    var orders: [Order] { queue.map(\.order) }

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
                        // формат клетки: "?" - загадка, "@2" - лед до 2 обслуженных
                        let hidden = cell.hasPrefix("?")
                        var body = hidden ? String(cell.dropFirst()) : cell
                        var ice = 0
                        if let at = body.firstIndex(of: "@") {
                            ice = Int(body[body.index(after: at)...]) ?? 0
                            body = String(body[..<at])
                        }
                        row.append(Piece(uid: uid, item: body, hidden: hidden, ice: ice))
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
        let patience = level.patience ?? 0
        self.patienceMax = patience
        self.tipMax = level.tipMax ?? 0
        let gourmets = Set(level.gourmet ?? [])
        self.queue = level.orders.enumerated().map {
            Customer(uid: $0.offset + 1, order: $0.element, patience: patience, gourmet: gourmets.contains($0.offset))
        }
        var locks = level.locks ?? []
        while locks.count < built.count { locks.append(0) }
        self.locks = locks
        var keys: [String?] = (level.keys ?? []).map { ($0?.isEmpty ?? true) ? nil : $0 }
        while keys.count < built.count { keys.append(nil) }
        self.keys = keys
        self.chains = (level.chains ?? []).compactMap { pair in
            guard pair.count == 2, pair[0] != pair[1], built.indices.contains(pair[0]), built.indices.contains(pair[1]) else { return nil }
            return ChainLink(a: pair[0], b: pair[1])
        }
        self.nextUid = uid + 1000
        self.catalog = catalog
        for s in shelves.indices { normalize(s) }
        _ = settle(Array(shelves.indices))
    }

    // MARK: - Состояние

    var isWon: Bool { queue.isEmpty }

    /// Чаевые, если обслужить покупателя сейчас. Совпадает с tip_for в rules.py.
    func tip(for customer: Customer) -> Int {
        guard patienceMax > 0, tipMax > 0, customer.patience > 0 else { return 0 }
        let tip = Int((Double(tipMax) * Double(customer.patience) / Double(patienceMax) - 1e-9).rounded(.up))
        return customer.gourmet ? tip * Board.gourmetTip : tip
    }

    var hasFreeSlot: Bool {
        shelves.indices.contains { !isClosed($0) && freeSlot(in: $0) != nil }
    }

    /// Нет ни одного хода: все продукты во льду или нет свободного места на другой полке.
    var isStuck: Bool { !isWon && !hasMove }

    var hasMove: Bool {
        for s in shelves.indices where !isClosed(s) {
            guard shelves[s][0].contains(where: { $0 != nil && !isFrozen($0!) }) else { continue }
            if shelves.indices.contains(where: { $0 != s && !isClosed($0) && freeSlot(in: $0) != nil }) { return true }
        }
        return false
    }

    /// Полка заперта: замок по числу обслуженных или замок с ключом.
    func isLocked(_ shelf: Int) -> Bool {
        (locks.indices.contains(shelf) && locks[shelf] > served) || key(shelf) != nil
    }

    /// Продукт-ключ на замке полки (спрайт), если замок еще висит.
    func key(_ shelf: Int) -> String? { keys.indices.contains(shelf) ? keys[shelf] : nil }

    /// Полка заблокирована цепью: на парную полку положили продукт, и она еще не сработала.
    func isChained(_ shelf: Int) -> Bool {
        chains.contains { !$0.broken && $0.blocks(shelf) }
    }

    /// С полки нельзя брать и на нее нельзя класть.
    func isClosed(_ shelf: Int) -> Bool { isLocked(shelf) || isChained(shelf) }

    /// Сколько еще покупателей до открытия полки.
    func lockLeft(_ shelf: Int) -> Int { locks.indices.contains(shelf) ? max(0, locks[shelf] - served) : 0 }

    func isFrozen(_ piece: Piece) -> Bool { piece.ice > served }

    /// Сколько еще покупателей до того, как растает лед.
    func iceLeft(_ piece: Piece) -> Int { max(0, piece.ice - served) }

    /// Можно ли положить продукт на полку.
    func canPlace(on shelf: Int) -> Bool { !isClosed(shelf) && freeSlot(in: shelf) != nil }

    func front(_ shelf: Int) -> [Piece?] { shelves[shelf][0] }

    func peek(_ shelf: Int) -> [Piece?]? { shelves[shelf].count > 1 ? shelves[shelf][1] : nil }

    func depth(_ shelf: Int) -> Int { shelves[shelf].count }

    func freeSlot(in shelf: Int) -> Int? { shelves[shelf][0].firstIndex { $0 == nil } }

    // MARK: - Ходы

    mutating func move(from src: Int, slot: Int, to dst: Int) -> MoveOutcome? {
        guard src != dst, shelves.indices.contains(src), shelves.indices.contains(dst),
              slot >= 0, slot < Board.slots, !isClosed(src), !isClosed(dst),
              let piece = shelves[src][0][slot], !isFrozen(piece),
              let target = freeSlot(in: dst) else { return nil }
        shelves[src][0][slot] = nil
        shelves[dst][0][target] = piece
        for i in chains.indices where !chains[i].broken && chains[i].contains(dst) { chains[i].last = dst }
        var changed: [Int] = []
        if shelves[src][0].allSatisfy({ $0 == nil }) && shelves[src].count > 1 {
            shelves[src].removeFirst()
            reveal(src)
            changed.append(src)
        }
        changed.append(dst)
        let events = settle(changed)
        // у покупателей за прилавком тает терпение, если оно не на паузе
        if pauseLeft > 0 {
            pauseLeft -= 1
        } else {
            for i in 0..<min(Board.counter, queue.count) {
                queue[i].patience = max(0, queue[i].patience - 1)
            }
        }
        return MoveOutcome(piece: piece, from: src, fromSlot: slot, to: dst, toSlot: target, events: events)
    }

    mutating func addShelf() {
        shelves.append([[nil, nil, nil]])
        locks.append(0)
        keys.append(nil)
    }

    /// Бустер "Пауза терпения".
    mutating func pausePatience(_ moves: Int) {
        pauseLeft += moves
    }

    /// Бустер "Перемешать": продукты передних рядов открытых полок меняются местами.
    /// Лед и замки остаются на месте. Перемешивание не собирает наборы само.
    mutating func shuffleFront() -> Bool {
        var slots: [(Int, Int)] = []
        var pieces: [Piece] = []
        for s in shelves.indices where !isClosed(s) {
            for k in 0..<Board.slots {
                if let piece = shelves[s][0][k], !isFrozen(piece) {
                    slots.append((s, k))
                    pieces.append(piece)
                }
            }
        }
        guard Set(pieces.map(\.item)).count >= 2 else { return false }
        for _ in 0..<40 {
            let order = pieces.shuffled()
            var copy = shelves
            for (i, slot) in slots.enumerated() { copy[slot.0][0][slot.1] = order[i] }
            let ready = copy.contains { layers in
                let names = layers[0].compactMap { $0?.item }
                guard names.count == Board.slots else { return false }
                if catalog.transform(of: names) != nil { return true }
                guard let result = catalog.result(of: names) else { return false }
                return queue.contains { $0.order == result }
            }
            if !ready {
                shelves = copy
                return true
            }
        }
        return false
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

    private mutating func settle(_ changed: [Int]) -> [BoardEvent] {
        var events: [BoardEvent] = []
        var pending = changed
        while let s = pending.popLast() {
            let front = shelves[s][0]
            let names = front.compactMap { $0?.item }
            guard names.count == Board.slots else { continue }
            // цепочка: три сырых превращаются в один продукт в среднем слоте
            if let made = catalog.transform(of: names) {
                nextUid += 1
                let piece = Piece(uid: nextUid, item: made, hidden: false)
                shelves[s][0] = [nil, piece, nil]
                events.append(.transform(Transform(shelf: s, pieces: front.compactMap { $0 }, result: piece, slot: 1)))
                continue
            }
            guard let result = catalog.result(of: names),
                  let index = queue.firstIndex(where: { $0.order == result }) else { continue }
            let customer = queue.remove(at: index)
            served += 1
            // ключ: заказ с этим продуктом обслужен - замки с ним открываются
            let sprite = Art.sprite(for: result)
            for k in keys.indices where keys[k] == sprite { keys[k] = nil }
            for i in chains.indices where !chains[i].broken && chains[i].contains(s) { chains[i].fired(s) }
            events.append(.fire(Fire(shelf: s, pieces: front.compactMap { $0 }, order: result, queueIndex: index,
                                     customer: customer, tip: tip(for: customer))))
            shelves[s][0] = [nil, nil, nil]
            if shelves[s].count > 1 {
                shelves[s].removeFirst()
                reveal(s)
            }
            pending.append(s)
        }
        return events
    }

    // MARK: - Подсказка

    /// Лучший ход на один шаг вперед: срабатывание, потом заготовка тройки или рецепта.
    func hint() -> (from: Int, slot: Int, to: Int)? {
        var best: (score: Double, move: (Int, Int, Int))?
        for s in shelves.indices where !isClosed(s) {
            var seen = Set<String>()
            for k in 0..<Board.slots {
                guard let piece = shelves[s][0][k], !isFrozen(piece), !seen.contains(piece.item) else { continue }
                seen.insert(piece.item)
                for d in shelves.indices where d != s && canPlace(on: d) {
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
