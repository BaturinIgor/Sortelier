import Foundation
import Combine

/// Состояние одного прохождения уровня: поле, ходы, монеты, звезды.
final class GameSession: ObservableObject {
    enum Phase { case playing, won, stuck }

    struct Result {
        let orderCoins: Int
        let served: Int
        let tips: Int
        let comboCoins: Int
        let efficiency: Int
        let total: Int
        let stars: Int
        let reward: PlayerProgress.LevelReward
    }

    let level: LevelData
    let isReplay: Bool

    @Published private(set) var board: Board
    @Published private(set) var phase: Phase = .playing
    /// Все монеты уровня до бонуса за экономию: заказы, чаевые, серии.
    @Published private(set) var orderCoins = 0
    @Published private(set) var tips = 0
    @Published private(set) var comboCoins = 0
    @Published private(set) var moves = 0
    @Published private(set) var combo = 0
    @Published private(set) var result: Result?
    @Published private(set) var continues = 0
    @Published private(set) var adContinueUsed = false
    @Published private(set) var doubled = false
    /// Блюдо, приготовленное впервые: показываем анимацию открытия.
    @Published var newDish: String?
    private var pendingDish: String?

    /// Сцена перерисовывает поле целиком после отмены или новой полки.
    var onReset: (() -> Void)?
    /// Сцена подсвечивает подсказку.
    var onHint: ((Int, Int, Int) -> Void)?

    private var since = 99
    private var history: [Snapshot] = []

    private struct Snapshot {
        let board: Board
        let orderCoins: Int
        let tips: Int
        let comboCoins: Int
        let moves: Int
        let combo: Int
        let since: Int
    }

    init(level: LevelData) {
        self.level = level
        self.isReplay = PlayerProgress.shared.isPassed(level.id)
        self.board = Board(level: level)
        Analytics.log("level_start", ["level": level.id, "replay": isReplay])
    }

    var hasMoves: Bool { moves > 0 }

    var canUndo: Bool { !history.isEmpty && phase == .playing }

    // MARK: - Ходы

    func move(from: Int, slot: Int, to: Int) -> MoveOutcome? {
        guard phase == .playing else { return nil }
        var copy = board
        guard let outcome = copy.move(from: from, slot: slot, to: to) else { return nil }
        history.append(Snapshot(board: board, orderCoins: orderCoins, tips: tips, comboCoins: comboCoins, moves: moves,
                                combo: combo, since: since))
        if history.count > 40 { history.removeFirst() }
        board = copy
        moves += 1
        since += 1
        for fire in outcome.fires {
            combo = (combo > 0 && since <= Balance.comboWindow) ? combo + 1 : 1
            since = 0
            orderCoins += Balance.coinsPerOrder + fire.tip
            tips += fire.tip
            if combo >= Balance.comboFrom {
                orderCoins += Balance.comboBonus
                comboCoins += Balance.comboBonus
            }
            discover(fire.order)
        }
        return outcome
    }

    /// Монеты за срабатывание с учетом чаевых и серии: для всплывающей подписи.
    func coins(for fire: Fire, combo: Int) -> Int {
        Balance.coinsPerOrder + fire.tip + (combo >= Balance.comboFrom ? Balance.comboBonus : 0)
    }

    private func discover(_ order: Order) {
        let progress = PlayerProgress.shared
        switch order.kind {
        case .triple:
            progress.discover(order.target)
        case .dish:
            if let dish = Catalog.shared.dish(order.target) {
                for ingredient in dish.ingredients { progress.discover(ingredient) }
            }
            if progress.discover("dish_" + order.target) {
                pendingDish = order.target
                Analytics.log("dish_unlock", ["dish": order.target])
            }
        }
    }

    /// Сцена вызывает, когда блюдо собралось на полке.
    func presentPendingDish() {
        guard let dish = pendingDish else { return }
        pendingDish = nil
        newDish = dish
    }

    /// Сцена вызывает после анимаций хода.
    func checkEnd() {
        guard phase == .playing else { return }
        if board.isWon {
            finish()
        } else if board.isStuck {
            phase = .stuck
            Haptics.warning()
            Analytics.log("level_stuck", ["level": level.id, "moves": moves])
        }
    }

    private func finish() {
        let n = Double(level.orders.count)
        let par = Double(max(1, level.par))
        let eff = min(1, max(0, (2 * par - Double(moves)) / par))
        let efficiency = Int((Balance.efficiencyShare * Double(Balance.coinsPerOrder) * n * eff).rounded())
        let total = orderCoins + efficiency
        let stars = total >= level.stars[1] ? 3 : (total >= level.stars[0] ? 2 : 1)
        let reward = PlayerProgress.shared.completeLevel(level.id, coins: total, stars: stars)
        result = Result(orderCoins: orderCoins, served: level.orders.count, tips: tips, comboCoins: comboCoins,
                        efficiency: efficiency, total: total, stars: stars, reward: reward)
        phase = .won
        Haptics.success()
        Analytics.log("level_win", ["level": level.id, "moves": moves, "coins": total, "stars": stars,
                                    "tips": tips, "par": level.par, "replay": isReplay])
    }

    // MARK: - Бустеры

    func undo() -> Bool {
        guard canUndo, PlayerProgress.shared.use(.undo), let snapshot = history.popLast() else { return false }
        board = snapshot.board
        orderCoins = snapshot.orderCoins
        tips = snapshot.tips
        comboCoins = snapshot.comboCoins
        moves = snapshot.moves
        combo = snapshot.combo
        since = snapshot.since
        onReset?()
        return true
    }

    func hint() -> Bool {
        guard phase == .playing, let move = board.hint(), PlayerProgress.shared.use(.hint) else { return false }
        onHint?(move.from, move.slot, move.to)
        return true
    }

    func useExtraShelf() -> Bool {
        guard phase == .playing, PlayerProgress.shared.use(.shelf) else { return false }
        addShelf()
        return true
    }

    private func addShelf() {
        board.addShelf()
        if phase == .stuck { phase = .playing }
        onReset?()
    }

    // MARK: - Поражение

    var continuePrice: Int {
        Balance.continuePrices[min(continues, Balance.continuePrices.count - 1)]
    }

    func continueWithCoins() -> Bool {
        guard phase == .stuck, PlayerProgress.shared.spend(continuePrice) else { return false }
        continues += 1
        Analytics.log("continue", ["level": level.id, "way": "coins"])
        addShelf()
        return true
    }

    func continueWithAd(_ done: @escaping (Bool) -> Void) {
        guard phase == .stuck, !adContinueUsed else { return done(false) }
        Ads.shared.showRewarded(placement: "continue") { [weak self] ok in
            guard let self = self, ok else { return done(false) }
            self.adContinueUsed = true
            self.addShelf()
            done(true)
        }
    }

    /// Выход без победы. Жизнь списывается только за новый уровень, где уже были ходы.
    func abandon() {
        guard phase != .won else { return }
        if !isReplay && hasMoves {
            PlayerProgress.shared.loseLife()
        }
        Analytics.log("level_fail", ["level": level.id, "moves": moves, "replay": isReplay])
    }

    // MARK: - Победа

    func doubleCoins(_ done: @escaping (Bool) -> Void) {
        guard let reward = result?.reward, reward.coinsAdded > 0, !doubled else { return done(false) }
        Ads.shared.showRewarded(placement: "double_coins") { [weak self] ok in
            guard let self = self, ok else { return done(false) }
            PlayerProgress.shared.addCoins(reward.coinsAdded)
            self.doubled = true
            done(true)
        }
    }
}
