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
        /// День стрика, если засчитан этой победой, и его награда.
        let streakDay: Int?
        let streak: Granted?
        let chef: Granted?
        let chefSeries: Int
        let challenge: Granted?
        let events: [PlayerProgress.EventGain]
        let doubleBonus: Int
        /// Подарок довольного гурмана: фон кухни или монеты.
        let gourmetGift: Granted?
        /// Монеты VIP сверх награды (x1.5).
        let vipBonus: Int
    }

    let level: LevelData
    let mode: PlayMode
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
    /// Сцена показывает паузу терпения.
    var onPause: (() -> Void)?

    private var since = 99
    private var history: [Snapshot] = []
    // итоги для статистики
    private var servedCount = 0
    private var dishCount = 0
    private var tripleCount = 0
    private var bestCombo = 0
    /// Гурманы, обслуженные с чаевыми.
    private var happyGourmets = 0

    private struct Snapshot {
        let board: Board
        let orderCoins: Int
        let tips: Int
        let comboCoins: Int
        let moves: Int
        let combo: Int
        let since: Int
        let happyGourmets: Int
    }

    init(level: LevelData, mode: PlayMode = .main) {
        self.level = level
        self.mode = mode
        self.isReplay = mode == .main && PlayerProgress.shared.isPassed(level.id)
        self.board = Board(level: level)
        Analytics.log("level_start", ["level": level.id, "replay": isReplay, "mode": mode.analyticsName])
        #if DEBUG
        // снимки экрана в середине уровня: несколько ходов подсказки
        for _ in 0..<UIDebug.autoplay {
            guard let m = board.hint(), move(from: m.from, slot: m.slot, to: m.to) != nil, !board.isWon else { break }
        }
        pendingDish = nil
        #endif
    }

    var hasMoves: Bool { moves > 0 }

    /// Поражение на этом уровне сжигает жизнь: только новый уровень основной карты.
    var costsLife: Bool { mode == .main && !isReplay }

    /// Бустеры запрещены правилом недельного испытания.
    var boostersAllowed: Bool { level.rule != "noboosters" }

    /// Что открыть кнопкой "Дальше".
    var nextLevel: (level: LevelData, mode: PlayMode)? {
        switch mode {
        case .main:
            // следующий биом сначала открывают на карте
            guard let next = LevelStore.shared.level(level.id + 1),
                  PlayerProgress.shared.isBiomeOpen(next.biome) else { return nil }
            return (level: next, mode: PlayMode.main)
        case .daily:
            return nil
        case let .weekly(week, index):
            guard index < 2, week == Day.weekKey(), let set = ChallengeStore.shared.weeklySet(),
                  set.levels.count > index + 1 else { return nil }
            return (level: set.levels[index + 1], mode: PlayMode.weekly(week, index + 1))
        case let .event(id, theme, index):
            let levels = EventLevelStore.shared.levels(theme: theme)
            guard EventCalendar.event(id) != nil, levels.count > index + 1 else { return nil }
            return (level: levels[index + 1], mode: PlayMode.event(id, theme, index + 1))
        }
    }

    var canUndo: Bool { !history.isEmpty && phase == .playing }

    // MARK: - Ходы

    func move(from: Int, slot: Int, to: Int) -> MoveOutcome? {
        guard phase == .playing else { return nil }
        var copy = board
        guard let outcome = copy.move(from: from, slot: slot, to: to) else { return nil }
        history.append(Snapshot(board: board, orderCoins: orderCoins, tips: tips, comboCoins: comboCoins, moves: moves,
                                combo: combo, since: since, happyGourmets: happyGourmets))
        if history.count > 40 { history.removeFirst() }
        board = copy
        moves += 1
        since += 1
        for fire in outcome.fires {
            combo = (combo > 0 && since <= Balance.comboWindow) ? combo + 1 : 1
            since = 0
            servedCount += 1
            if fire.order.kind == .dish { dishCount += 1 } else { tripleCount += 1 }
            bestCombo = max(bestCombo, combo)
            orderCoins += Balance.coinsPerOrder + fire.tip
            tips += fire.tip
            if fire.customer.gourmet && fire.tip > 0 { happyGourmets += 1 }
            if combo >= Balance.comboFrom {
                orderCoins += Balance.comboBonus
                comboCoins += Balance.comboBonus
            }
            discover(fire.order)
        }
        for t in outcome.transforms {
            PlayerProgress.shared.discover(t.result.item)
            if let raw = t.pieces.first?.item { PlayerProgress.shared.discover(raw) }
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
                for ingredient in dish.ingredients {
                    progress.discover(ingredient)
                    if let raw = Catalog.shared.chainSource(of: ingredient) { progress.discover(raw) }
                }
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
        let progress = PlayerProgress.shared
        var reward: PlayerProgress.LevelReward
        var chef: Granted?
        var challenge: Granted?
        switch mode {
        case .main:
            reward = progress.completeLevel(level.id, coins: total, stars: stars)
            if !isReplay {
                progress.bump(.levelsWon)
                chef = progress.chefWin(level: level.id)
            }
            if reward.firstThreeStars { progress.bump(.threeStars) }
        case let .daily(day):
            let first = !progress.dailyDone(day)
            if first { progress.addCoins(total) }
            challenge = progress.completeDaily(day)
            reward = PlayerProgress.LevelReward(coinsAdded: first ? total : 0, newRecord: false,
                                                firstThreeStars: false, lifeReturned: false)
        case let .weekly(week, index):
            let first = progress.weeklyDone(week) == index
            if first { progress.addCoins(total) }
            challenge = progress.completeWeekly(week, index: index)
            reward = PlayerProgress.LevelReward(coinsAdded: first ? total : 0, newRecord: false,
                                                firstThreeStars: false, lifeReturned: false)
        case let .event(id, _, index):
            let first = progress.completeEventLevel(id, index: index)
            if first { progress.addCoins(total) }
            reward = PlayerProgress.LevelReward(coinsAdded: first ? total : 0, newRecord: false,
                                                firstThreeStars: false, lifeReturned: false)
        }
        let events = progress.eventsAfterWin(mode: mode, isNewLevel: mode == .main && !isReplay, stars: stars,
                                             coinsAdded: reward.coinsAdded)
        progress.addLevelStats(served: servedCount, tips: tips, dishes: dishCount, triples: tripleCount,
                               maxCombo: bestCombo)
        let streak = progress.registerPlayDay()
        if happyGourmets > 0 { progress.bump(.gourmets, by: happyGourmets) }
        let gourmetGift = progress.gourmetServed(count: happyGourmets)
        let vipBonus = progress.vipBonus(for: reward.coinsAdded)
        result = Result(orderCoins: orderCoins, served: level.orders.count, tips: tips, comboCoins: comboCoins,
                        efficiency: efficiency, total: total, stars: stars, reward: reward,
                        streakDay: streak?.day, streak: streak?.granted, chef: chef,
                        chefSeries: progress.chefSeries, challenge: challenge,
                        events: events.gains, doubleBonus: events.bonus, gourmetGift: gourmetGift,
                        vipBonus: vipBonus)
        Notifications.afterWin(level: level.id, mode: mode)
        phase = .won
        Haptics.success()
        Analytics.log("level_win", ["level": level.id, "moves": moves, "coins": total, "stars": stars,
                                    "tips": tips, "par": level.par, "replay": isReplay])
    }

    // MARK: - Бустеры

    func undo() -> Bool {
        guard boostersAllowed, canUndo, PlayerProgress.shared.use(.undo), let snapshot = history.popLast() else { return false }
        board = snapshot.board
        orderCoins = snapshot.orderCoins
        tips = snapshot.tips
        comboCoins = snapshot.comboCoins
        moves = snapshot.moves
        combo = snapshot.combo
        since = snapshot.since
        happyGourmets = snapshot.happyGourmets
        onReset?()
        return true
    }

    func hint() -> Bool {
        guard boostersAllowed, phase == .playing, let move = board.hint(), PlayerProgress.shared.use(.hint) else { return false }
        onHint?(move.from, move.slot, move.to)
        return true
    }

    func shuffle() -> Bool {
        guard boostersAllowed, phase == .playing, PlayerProgress.shared.count(.shuffle) > 0 else { return false }
        var copy = board
        guard copy.shuffleFront(), PlayerProgress.shared.use(.shuffle) else { return false }
        board = copy
        onReset?()
        return true
    }

    /// Пауза терпения доступна, когда у покупателей есть терпение.
    var pauseAvailable: Bool { board.patienceMax > 0 && level.biome >= 2 }

    func pausePatience() -> Bool {
        guard boostersAllowed, phase == .playing, pauseAvailable, PlayerProgress.shared.use(.pause) else { return false }
        board.pausePatience(Balance.pauseMoves)
        onPause?()
        return true
    }

    func useExtraShelf() -> Bool {
        guard boostersAllowed, phase == .playing, PlayerProgress.shared.use(.shelf) else { return false }
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
        if costsLife && hasMoves {
            PlayerProgress.shared.loseLife()
            PlayerProgress.shared.chefFail(level: level.id)
        }
        if hasMoves {
            PlayerProgress.shared.addLevelStats(served: servedCount, tips: tips, dishes: dishCount,
                                                triples: tripleCount, maxCombo: bestCombo)
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

extension PlayMode {
    var analyticsName: String {
        switch self {
        case .main: return "main"
        case .daily: return "daily"
        case .weekly: return "weekly"
        case .event: return "event"
        }
    }
}
