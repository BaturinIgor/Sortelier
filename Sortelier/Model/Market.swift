import Foundation

// MARK: - Уровни "Рынка"

/// 60 уровней мини-игры "Рынок" (3 в ряд), две главы по 30. Генерирует tools/match3/generate.py.
final class MarketCatalog {
    static let shared = MarketCatalog()

    let levels: [M3Level]
    static let perChapter = 30

    private struct File: Decodable { let levels: [M3Level] }

    private init() {
        if let url = Bundle.main.url(forResource: "match3", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let file = try? JSONDecoder().decode(File.self, from: data) {
            levels = file.levels
        } else {
            levels = []
        }
    }

    func level(_ id: Int) -> M3Level? { levels.first { $0.id == id } }

    var chapters: Int { max(1, (levels.count + Self.perChapter - 1) / Self.perChapter) }

    func levels(chapter: Int) -> [M3Level] { levels.filter { $0.chapter == chapter } }

    /// Фон главы: кухни из основной игры.
    static func style(chapter: Int) -> String { chapter == 1 ? "peach" : "lavender" }
}

// MARK: - Баланс

enum MarketBalance {
    private static var config: RemoteConfig { .shared }

    /// "Рынок" открывается после этого уровня основной карты.
    static var unlockLevel: Int { config.int("market.unlockLevel", 8) }
    static var winCoins: Int { config.int("market.winCoins", 30) }
    static var coinsPerMove: Int { config.int("market.coinsPerMove", 3) }
    static var extraMoves: Int { config.int("market.extraMoves", 5) }
    static var extraPrices: [Int] { config.ints("market.extraPrices", [150, 300, 600]) }
    /// Энергия кладовой за каждую победу на "Рынке".
    static var winEnergy: Int { config.int("market.winEnergy", 3) }
    /// Каждая N-я победа на "Рынке" дает бустер основной игры.
    static var boosterEvery: Int { config.int("market.boosterEvery", 3) }

    static func price(_ b: M3Booster) -> Int {
        let fallback: Int
        switch b {
        case .pin: fallback = 90
        case .bomb: fallback = 130
        case .rainbow: fallback = 200
        case .mallet: fallback = 90
        case .knife, .spatula: fallback = 120
        case .mixer: fallback = 70
        }
        return config.int("market.prices." + b.rawValue, fallback)
    }

    /// Подарок при открытии "Рынка".
    static let welcome: [M3Booster: Int] = [.pin: 2, .bomb: 1, .rainbow: 1, .mallet: 2, .knife: 1, .spatula: 1, .mixer: 1]

    /// Серия побед подряд: что стоит на поле со старта на каждой ступени.
    static let streak: [[M3Special]] = [
        [.whisk],
        [.whisk, .rowPin],
        [.whisk, .rowPin, .rowPin],
        [.whisk, .rowPin, .bomb],
        [.whisk, .rowPin, .bomb, .rowPin],
    ]

    static var streakMax: Int { streak.count }

    /// Сундуки за звезды главы.
    struct StarChest {
        let stars: Int
        let reward: Reward
    }

    static func chests(chapter: Int) -> [StarChest] {
        let k = chapter
        return [
            StarChest(stars: 30, reward: Reward(coins: 150 * k, market: [.mallet: 1, .pin: 1], chests: [.bronze: 1])),
            StarChest(stars: 60, reward: Reward(coins: 300 * k, boosters: [.hint: 1, .undo: 1], market: [.bomb: 1, .knife: 1],
                                                chests: [.silver: 1])),
            StarChest(stars: 90, reward: Reward(coins: 800 * k, boosters: [.shelf: 1], unlimitedMinutes: 60, market: [.rainbow: 1, .mixer: 1],
                                                chests: [.gold: 1])),
        ]
    }
}

// MARK: - Сохранение

struct MarketData: Codable {
    var stars: [String: Int] = [:]
    var boosters: [String: Int] = [:]
    /// Побед подряд (ступень серии - min(streak, 5)).
    var streak = 0
    var wins = 0
    var chests: [String] = []
    var welcomed = false
    var bestStreak = 0

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        stars = try c.decodeIfPresent([String: Int].self, forKey: .stars) ?? [:]
        boosters = try c.decodeIfPresent([String: Int].self, forKey: .boosters) ?? [:]
        streak = try c.decodeIfPresent(Int.self, forKey: .streak) ?? 0
        wins = try c.decodeIfPresent(Int.self, forKey: .wins) ?? 0
        chests = try c.decodeIfPresent([String].self, forKey: .chests) ?? []
        welcomed = try c.decodeIfPresent(Bool.self, forKey: .welcomed) ?? false
        bestStreak = try c.decodeIfPresent(Int.self, forKey: .bestStreak) ?? 0
    }
}

/// Итог победы на "Рынке" для окна победы.
struct MarketResult {
    let level: Int
    let stars: Int
    let coins: Int
    let movesLeft: Int
    let firstWin: Bool
    let streak: Int
    let bonus: Reward
    let events: [PlayerProgress.EventGain]
    let recipeSteps: Int
    let critic: CriticReview?
    let jar: Int
    let happyHour: Bool
}

// MARK: - Прогресс

extension PlayerProgress {
    var marketUnlocked: Bool {
        #if DEBUG
        if UIDebug.flag("uiMarket") { return true }
        #endif
        return isPassed(MarketBalance.unlockLevel)
    }

    func marketStars(_ level: Int) -> Int { data.market.stars[String(level)] ?? 0 }

    func marketPassed(_ level: Int) -> Bool { marketStars(level) > 0 }

    func marketStars(chapter: Int) -> Int {
        MarketCatalog.shared.levels(chapter: chapter).reduce(0) { $0 + marketStars($1.id) }
    }

    /// Первый непройденный уровень (или последний, если пройдены все).
    var marketCurrent: Int {
        let levels = MarketCatalog.shared.levels
        return levels.first { !marketPassed($0.id) }?.id ?? (levels.last?.id ?? 1)
    }

    var marketAllDone: Bool { MarketCatalog.shared.levels.allSatisfy { marketPassed($0.id) } }

    func isMarketOpen(_ level: Int) -> Bool { level <= marketCurrent }

    // MARK: Бустеры

    func count(_ b: M3Booster) -> Int { data.market.boosters[b.rawValue] ?? 0 }

    func add(_ b: M3Booster, _ n: Int = 1) {
        data.market.boosters[b.rawValue, default: 0] += n
        save()
    }

    func use(_ b: M3Booster) -> Bool {
        guard count(b) > 0 else { return false }
        data.market.boosters[b.rawValue, default: 0] -= 1
        data.meta.stats[Stat.boostersUsed.rawValue, default: 0] += 1
        save()
        Analytics.log("market_booster", ["booster": b.rawValue])
        return true
    }

    func buy(_ b: M3Booster) -> Bool {
        guard spend(MarketBalance.price(b)) else { return false }
        add(b)
        return true
    }

    /// Подарок при первом входе на "Рынок".
    func marketWelcome() -> Granted? {
        guard !data.market.welcomed else { return nil }
        data.market.welcomed = true
        save()
        return grant(Reward(market: MarketBalance.welcome), source: "market_welcome")
    }

    // MARK: Серия побед

    var marketStreak: Int { min(data.market.streak, MarketBalance.streakMax) }

    var streakSpecials: [M3Special] {
        let stage = marketStreak
        return stage > 0 ? MarketBalance.streak[stage - 1] : []
    }

    // MARK: Конец уровня

    /// Победа. stars - по оставшимся ходам, collected - собранные продукты (для "Большого рецепта").
    func marketWin(_ level: M3Level, movesLeft: Int, collected: [String: Int]) -> MarketResult {
        let stars = movesLeft >= level.stars[1] ? 3 : (movesLeft >= level.stars[0] ? 2 : 1)
        let key = String(level.id)
        let old = data.market.stars[key] ?? 0
        let first = old == 0
        data.market.stars[key] = max(old, stars)
        data.market.wins += 1
        data.market.streak += 1
        data.market.bestStreak = max(data.market.bestStreak, data.market.streak)
        data.meta.stats[Stat.marketWins.rawValue, default: 0] += 1
        let happy = HappyHour.active()
        var coins = MarketBalance.winCoins + movesLeft * MarketBalance.coinsPerMove
        if !first { coins = coins / 2 }
        var bonus = Reward(energy: MarketBalance.winEnergy)
        if data.market.wins % MarketBalance.boosterEvery == 0 {
            let list: [Booster] = [.hint, .undo, .shuffle]
            bonus.boosters[list[(data.market.wins / MarketBalance.boosterEvery) % list.count].rawValue, default: 0] += 1
        }
        save()
        _ = grant(Reward(coins: coins) + bonus, source: "market_win")
        let events = eventsAfterWin(mode: .main, isNewLevel: first, stars: stars, coinsAdded: coins).gains
        _ = registerPlayDay()
        let steps = recipeAdd(collected)
        gardenWater()
        let critic = criticFinish(won: true, stars: stars)
        let jar = jarAdd(win: true, coins: coins)
        Analytics.log("market_win", ["level": level.id, "moves_left": movesLeft, "stars": stars, "streak": data.market.streak])
        return MarketResult(level: level.id, stars: stars, coins: coins, movesLeft: movesLeft, firstWin: first,
                            streak: marketStreak, bonus: bonus, events: events, recipeSteps: steps, critic: critic, jar: jar,
                            happyHour: happy)
    }

    /// Проигрыш или выход после ходов: жизнь, серия обрывается. Собранное идет в "Большой рецепт".
    func marketLose(_ level: M3Level, collected: [String: Int]) {
        loseLife()
        let had = data.market.streak
        data.market.streak = 0
        save()
        _ = recipeAdd(collected)
        _ = criticFinish(won: false, stars: 0)
        Analytics.log("market_fail", ["level": level.id, "streak": had])
    }

    // MARK: Сундуки глав

    func marketChestReady(chapter: Int, index: Int) -> Bool {
        let chest = MarketBalance.chests(chapter: chapter)[index]
        return marketStars(chapter: chapter) >= chest.stars && !data.market.chests.contains("\(chapter)-\(index)")
    }

    func marketChestClaimed(chapter: Int, index: Int) -> Bool { data.market.chests.contains("\(chapter)-\(index)") }

    func claimMarketChest(chapter: Int, index: Int) -> Granted? {
        guard marketChestReady(chapter: chapter, index: index) else { return nil }
        data.market.chests.append("\(chapter)-\(index)")
        save()
        return grant(MarketBalance.chests(chapter: chapter)[index].reward, source: "market_chest")
    }

    var marketClaimable: Bool {
        (1...MarketCatalog.shared.chapters).contains { ch in (0..<3).contains { marketChestReady(chapter: ch, index: $0) } }
    }
}
