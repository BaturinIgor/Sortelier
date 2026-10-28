import Foundation

/// Кладовая: мини-игра со слиянием. Энергия тратится на генераторы, два одинаковых предмета
/// сливаются в следующий, готовое отдается в заказы за безлимитные жизни, бустеры и монеты.
enum MergeChain: String, CaseIterable, Codable {
    case desserts, grill, garden

    var items: [String] {
        switch self {
        case .desserts: return ["cookie", "muffin", "cupcake", "donut", "waffle", "pie", "dish_pancakes"]
        case .grill: return ["sausage", "corndog", "patty", "dish_hotdog", "dish_burger", "dish_cheeseburger"]
        case .garden: return ["tomato", "lettuce", "corn", "fries", "dish_sandwich", "dish_sub"]
        }
    }

    var generator: String {
        switch self {
        case .desserts: return "gen_oven"
        case .grill: return "gen_grill"
        case .garden: return "gen_crate"
        }
    }
}

struct MergeItem: Codable, Hashable {
    let chain: MergeChain
    let tier: Int

    var sprite: String { chain.items[min(tier, chain.items.count - 1)] }
    var isMax: Bool { tier >= chain.items.count - 1 }
    var next: MergeItem? { isMax ? nil : MergeItem(chain: chain, tier: tier + 1) }
    /// Ценность для заказа: каждая ступень вдвое дороже.
    var value: Int { 1 << (tier + 1) }
    /// Цена продажи с доски: 1, 2, 5, 10, 20, 40, 80.
    var sellPrice: Int { tier == 0 ? 1 : (tier == 1 ? 2 : 5 << (tier - 2)) }
}

struct MergeOrder: Codable, Identifiable, Equatable {
    let id: Int
    let needs: [MergeItem]
    let reward: Reward
}

struct MergeData: Codable {
    var cells: [MergeItem?] = []
    var energy = MergeBalance.maxEnergy
    var energyUpdatedAt = Date()
    var orders: [MergeOrder] = []
    var nextOrderId = 1
    var completed = 0
    var bestTier = 1

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        cells = try c.decodeIfPresent([MergeItem?].self, forKey: .cells) ?? []
        energy = try c.decodeIfPresent(Int.self, forKey: .energy) ?? MergeBalance.maxEnergy
        energyUpdatedAt = try c.decodeIfPresent(Date.self, forKey: .energyUpdatedAt) ?? Date()
        orders = try c.decodeIfPresent([MergeOrder].self, forKey: .orders) ?? []
        nextOrderId = try c.decodeIfPresent(Int.self, forKey: .nextOrderId) ?? 1
        completed = try c.decodeIfPresent(Int.self, forKey: .completed) ?? 0
        bestTier = try c.decodeIfPresent(Int.self, forKey: .bestTier) ?? 1
    }
}

enum MergeBalance {
    static let cols = 7
    static let rows = 8
    static let maxEnergy = 30
    static let energyRegen: TimeInterval = 3 * 60
    static let adEnergy = 10
    static let buyEnergy = 10
    static let buyEnergyPrice = 60
    static let orderSlots = 3
    /// Ящик с припасами за рекламу: столько предметов первых ступеней.
    static let supplyItems = 3

    /// Генераторы стоят в нижнем ряду.
    static let generators: [Int: MergeChain] = [
        (rows - 1) * cols + 1: .desserts,
        (rows - 1) * cols + 3: .grill,
        (rows - 1) * cols + 5: .garden
    ]

    static func reward(value: Int, rng: inout SystemRandomNumberGenerator) -> Reward {
        let boosters: [Booster] = [.hint, .undo, .shelf]
        let booster = boosters[Int.random(in: 0..<boosters.count, using: &rng)]
        switch value {
        case ..<5: return Reward(coins: 20 * value)
        case ..<9: return Reward(coins: 30, boosters: [booster: 1])
        case ..<17: return Reward(coins: 40, unlimitedMinutes: 15)
        case ..<33: return Reward(unlimitedMinutes: 30, chests: [.bronze: 1])
        default: return Reward(unlimitedMinutes: 60, chests: [.silver: 1])
        }
    }
}

/// Состояние доски. Хранится в сохранении игрока и сохраняется после каждого действия.
final class MergeGame: ObservableObject {
    @Published private(set) var data: MergeData
    /// Сцена перерисовывает доску после изменений.
    var onChange: (() -> Void)?

    static let cellCount = MergeBalance.cols * MergeBalance.rows

    init() {
        var d = PlayerProgress.shared.data.merge
        if d.cells.count != Self.cellCount {
            d.cells = Array(repeating: nil, count: Self.cellCount)
            let start: [(Int, MergeItem)] = [
                (8, MergeItem(chain: .desserts, tier: 0)), (10, MergeItem(chain: .desserts, tier: 0)),
                (16, MergeItem(chain: .grill, tier: 0)), (18, MergeItem(chain: .grill, tier: 0)),
                (24, MergeItem(chain: .garden, tier: 0)), (26, MergeItem(chain: .garden, tier: 0))
            ]
            for (i, item) in start { d.cells[i] = item }
        }
        data = d
        refillOrders()
        PlayerProgress.shared.refreshEnergy()
    }

    func item(at index: Int) -> MergeItem? {
        data.cells.indices.contains(index) ? data.cells[index] : nil
    }

    func generator(at index: Int) -> MergeChain? { MergeBalance.generators[index] }

    /// notify = false, когда сцена сама анимирует изменение (перетаскивание).
    private func commit(notify: Bool = true) {
        PlayerProgress.shared.data.merge.cells = data.cells
        PlayerProgress.shared.data.merge.orders = data.orders
        PlayerProgress.shared.data.merge.nextOrderId = data.nextOrderId
        PlayerProgress.shared.data.merge.completed = data.completed
        PlayerProgress.shared.data.merge.bestTier = data.bestTier
        PlayerProgress.shared.save()
        if notify { onChange?() }
    }

    // MARK: - Генераторы

    /// Тап по генератору: тратит энергию и кладет новый предмет в ближайшую свободную клетку.
    /// Возвращает клетку или причину отказа.
    enum SpawnResult { case spawned(Int), noEnergy, boardFull }

    func spawn(from generatorIndex: Int) -> SpawnResult {
        guard let chain = generator(at: generatorIndex) else { return .boardFull }
        guard let cell = nearestEmpty(to: generatorIndex) else { return .boardFull }
        guard PlayerProgress.shared.spendEnergy(1) else { return .noEnergy }
        let tier = Int.random(in: 0..<10) == 0 ? 1 : 0
        data.cells[cell] = MergeItem(chain: chain, tier: tier)
        commit()
        return .spawned(cell)
    }

    private func nearestEmpty(to index: Int) -> Int? {
        let (r0, c0) = (index / MergeBalance.cols, index % MergeBalance.cols)
        var best: (Int, Int)?
        for i in data.cells.indices where data.cells[i] == nil && generator(at: i) == nil {
            let (r, c) = (i / MergeBalance.cols, i % MergeBalance.cols)
            let d = (r - r0) * (r - r0) + (c - c0) * (c - c0)
            if best == nil || d < best!.1 { best = (i, d) }
        }
        return best?.0
    }

    // MARK: - Перемещение и слияние

    enum MoveResult { case moved, merged(MergeItem), swapped, invalid }

    func move(from: Int, to: Int) -> MoveResult {
        guard from != to, data.cells.indices.contains(from), data.cells.indices.contains(to),
              generator(at: to) == nil, let a = data.cells[from] else { return .invalid }
        if let b = data.cells[to] {
            if a == b, let next = a.next {
                data.cells[to] = next
                data.cells[from] = nil
                data.bestTier = max(data.bestTier, next.tier)
                PlayerProgress.shared.bump(.merges, save: false)
                refillOrders()
                commit(notify: false)
                return .merged(next)
            }
            data.cells[to] = a
            data.cells[from] = b
            commit(notify: false)
            return .swapped
        }
        data.cells[to] = a
        data.cells[from] = nil
        commit(notify: false)
        return .moved
    }

    // MARK: - Продажа и припасы

    /// Продает предмет с доски. Возвращает полученные монеты.
    func sell(at index: Int) -> Int {
        guard let item = item(at: index) else { return 0 }
        data.cells[index] = nil
        commit()
        PlayerProgress.shared.addCoins(item.sellPrice)
        Analytics.log("merge_sell", ["tier": item.tier, "chain": item.chain.rawValue])
        return item.sellPrice
    }

    /// Ящик с припасами: несколько случайных предметов первых ступеней в свободные клетки.
    /// Возвращает, сколько предметов поместилось.
    func addSupply() -> Int {
        var added = 0
        for _ in 0..<MergeBalance.supplyItems {
            guard let cell = data.cells.indices.filter({ data.cells[$0] == nil && generator(at: $0) == nil }).randomElement()
            else { break }
            let chain = MergeChain.allCases.randomElement() ?? .desserts
            data.cells[cell] = MergeItem(chain: chain, tier: Int.random(in: 0..<3) == 0 ? 1 : 0)
            added += 1
        }
        if added > 0 {
            commit()
            Analytics.log("merge_supply", ["items": added])
        }
        return added
    }

    // MARK: - Заказы

    func canDeliver(_ order: MergeOrder) -> Bool {
        var pool = data.cells.compactMap { $0 }
        for need in order.needs {
            guard let i = pool.firstIndex(of: need) else { return false }
            pool.remove(at: i)
        }
        return true
    }

    func has(_ item: MergeItem) -> Bool { data.cells.contains(item) }

    func deliver(_ order: MergeOrder) -> Granted? {
        guard canDeliver(order), let index = data.orders.firstIndex(of: order) else { return nil }
        for need in order.needs {
            if let i = data.cells.firstIndex(of: need) { data.cells[i] = nil }
        }
        data.orders.remove(at: index)
        data.completed += 1
        refillOrders()
        commit()
        PlayerProgress.shared.bump(.mergeOrders)
        Analytics.log("merge_order", ["value": order.needs.reduce(0) { $0 + $1.value }])
        return PlayerProgress.shared.grant(order.reward, source: "merge")
    }

    private func refillOrders() {
        var rng = SystemRandomNumberGenerator()
        while data.orders.count < MergeBalance.orderSlots {
            let chains = MergeChain.allCases.shuffled()
            let top = min(5, max(2, data.bestTier + 1))
            var needs = [MergeItem(chain: chains[0], tier: Int.random(in: 1...top))]
            if Int.random(in: 0..<10) < 4 {
                needs.append(MergeItem(chain: chains[1], tier: Int.random(in: 1...max(1, top - 1))))
            }
            let value = needs.reduce(0) { $0 + $1.value }
            data.orders.append(MergeOrder(id: data.nextOrderId, needs: needs,
                                          reward: MergeBalance.reward(value: value, rng: &rng)))
            data.nextOrderId += 1
        }
    }
}

// MARK: - Энергия

extension PlayerProgress {
    var energy: Int { data.merge.energy }

    var nextEnergyIn: TimeInterval? {
        guard data.merge.energy < MergeBalance.maxEnergy else { return nil }
        return max(0, data.merge.energyUpdatedAt.addingTimeInterval(MergeBalance.energyRegen).timeIntervalSince(now))
    }

    func refreshEnergy() {
        guard data.merge.energy < MergeBalance.maxEnergy else { return }
        let gained = Int(Date().timeIntervalSince(data.merge.energyUpdatedAt) / MergeBalance.energyRegen)
        guard gained > 0 else { return }
        data.merge.energy = min(MergeBalance.maxEnergy, data.merge.energy + gained)
        data.merge.energyUpdatedAt = data.merge.energy >= MergeBalance.maxEnergy
            ? Date()
            : data.merge.energyUpdatedAt.addingTimeInterval(Double(gained) * MergeBalance.energyRegen)
        save()
    }

    func spendEnergy(_ amount: Int) -> Bool {
        refreshEnergy()
        guard data.merge.energy >= amount else { return false }
        if data.merge.energy >= MergeBalance.maxEnergy { data.merge.energyUpdatedAt = Date() }
        data.merge.energy -= amount
        save()
        return true
    }

    /// Энергия из наград может превышать максимум.
    func addMergeEnergy(_ amount: Int) {
        data.merge.energy += amount
        save()
    }

    func buyEnergy() -> Bool {
        guard spend(MergeBalance.buyEnergyPrice) else { return false }
        addMergeEnergy(MergeBalance.buyEnergy)
        return true
    }
}
