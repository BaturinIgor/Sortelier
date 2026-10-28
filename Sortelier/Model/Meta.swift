import Foundation

// MARK: - Награда

/// Награда: монеты, бустеры, безлимитные жизни, жизни, редкая карточка, фон, энергия.
struct Reward: Codable, Hashable {
    var coins = 0
    var boosters: [String: Int] = [:]
    var unlimitedMinutes = 0
    var lives = 0
    var rareCard = false
    var background: String?
    var energy = 0

    init(coins: Int = 0, boosters: [Booster: Int] = [:], unlimitedMinutes: Int = 0, lives: Int = 0,
         rareCard: Bool = false, background: String? = nil, energy: Int = 0) {
        self.coins = coins
        self.boosters = Dictionary(uniqueKeysWithValues: boosters.map { ($0.key.rawValue, $0.value) })
        self.unlimitedMinutes = unlimitedMinutes
        self.lives = lives
        self.rareCard = rareCard
        self.background = background
        self.energy = energy
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        coins = try c.decodeIfPresent(Int.self, forKey: .coins) ?? 0
        boosters = try c.decodeIfPresent([String: Int].self, forKey: .boosters) ?? [:]
        unlimitedMinutes = try c.decodeIfPresent(Int.self, forKey: .unlimitedMinutes) ?? 0
        lives = try c.decodeIfPresent(Int.self, forKey: .lives) ?? 0
        rareCard = try c.decodeIfPresent(Bool.self, forKey: .rareCard) ?? false
        background = try c.decodeIfPresent(String.self, forKey: .background)
        energy = try c.decodeIfPresent(Int.self, forKey: .energy) ?? 0
    }

    var boosterList: [(Booster, Int)] {
        Booster.allCases.compactMap { b in
            guard let n = boosters[b.rawValue], n > 0 else { return nil }
            return (b, n)
        }
    }

    var isEmpty: Bool {
        coins == 0 && boosterList.isEmpty && unlimitedMinutes == 0 && lives == 0 && !rareCard && background == nil && energy == 0
    }

    static func + (a: Reward, b: Reward) -> Reward {
        var r = a
        r.coins += b.coins
        for (k, v) in b.boosters { r.boosters[k, default: 0] += v }
        r.unlimitedMinutes += b.unlimitedMinutes
        r.lives += b.lives
        r.rareCard = a.rareCard || b.rareCard
        r.background = a.background ?? b.background
        r.energy += b.energy
        return r
    }
}

/// Что игрок получил на самом деле: редкая карточка выбирается при выдаче.
struct Granted: Equatable {
    let reward: Reward
    let card: String?
}

// MARK: - Статистика

/// Счетчики для заданий и ачивок. levelsWon - новые пройденные уровни основной карты.
enum Stat: String, CaseIterable {
    case levelsWon, served, tips, dishes, triples, threeStars, maxCombo, boostersUsed
    case dailyDone, weeklyDone, weeklyLevels, streakBest, rareCards, cards, chests, chefBest
}

// MARK: - Сохранение меты

struct StreakData: Codable, Equatable {
    /// День в цикле из 7, засчитанный последним (0 - еще не начат).
    var day = 0
    var lastDay: String?
    var freezes = 0

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        day = try c.decodeIfPresent(Int.self, forKey: .day) ?? 0
        lastDay = try c.decodeIfPresent(String.self, forKey: .lastDay)
        freezes = try c.decodeIfPresent(Int.self, forKey: .freezes) ?? 0
    }
}

struct MetaData: Codable {
    var stats: [String: Int] = [:]
    var streak = StreakData()
    var chefSeries = 0
    /// Неудачные попытки на новых уровнях: для серии шефа.
    var failed: [String] = []
    var dailyDone: [String] = []
    var weeklyProgress: [String: Int] = [:]
    /// Дни, когда закрыто недельное испытание: по ним считается медаль месяца.
    var weeklyDoneDays: [String] = []
    var medals: [String] = []
    var rareCards: [String] = []
    var welcomeStart: String?
    var questsClaimed: [String] = []
    var welcomeGrand = false
    var achievementTiers: [String: Int] = [:]
    var backgrounds: [String] = [KitchenStyle.defaultId]
    var background = KitchenStyle.defaultId
    var notificationsAsked = false

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        stats = try c.decodeIfPresent([String: Int].self, forKey: .stats) ?? [:]
        streak = try c.decodeIfPresent(StreakData.self, forKey: .streak) ?? StreakData()
        chefSeries = try c.decodeIfPresent(Int.self, forKey: .chefSeries) ?? 0
        failed = try c.decodeIfPresent([String].self, forKey: .failed) ?? []
        dailyDone = try c.decodeIfPresent([String].self, forKey: .dailyDone) ?? []
        weeklyProgress = try c.decodeIfPresent([String: Int].self, forKey: .weeklyProgress) ?? [:]
        weeklyDoneDays = try c.decodeIfPresent([String].self, forKey: .weeklyDoneDays) ?? []
        medals = try c.decodeIfPresent([String].self, forKey: .medals) ?? []
        rareCards = try c.decodeIfPresent([String].self, forKey: .rareCards) ?? []
        welcomeStart = try c.decodeIfPresent(String.self, forKey: .welcomeStart)
        questsClaimed = try c.decodeIfPresent([String].self, forKey: .questsClaimed) ?? []
        welcomeGrand = try c.decodeIfPresent(Bool.self, forKey: .welcomeGrand) ?? false
        achievementTiers = try c.decodeIfPresent([String: Int].self, forKey: .achievementTiers) ?? [:]
        backgrounds = try c.decodeIfPresent([String].self, forKey: .backgrounds) ?? [KitchenStyle.defaultId]
        background = try c.decodeIfPresent(String.self, forKey: .background) ?? KitchenStyle.defaultId
        notificationsAsked = try c.decodeIfPresent(Bool.self, forKey: .notificationsAsked) ?? false
    }
}

// MARK: - Дни, недели, месяцы

enum Day {
    private static var calendar: Calendar { Calendar.current }

    static func key(_ date: Date = Date()) -> String {
        let c = calendar.dateComponents([.year, .month, .day], from: date)
        return String(format: "%04d-%02d-%02d", c.year ?? 0, c.month ?? 0, c.day ?? 0)
    }

    static func date(_ key: String) -> Date? {
        let parts = key.split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return calendar.date(from: DateComponents(year: parts[0], month: parts[1], day: parts[2]))
    }

    /// Сколько дней от a до b (по календарю).
    static func between(_ a: String, _ b: String) -> Int {
        guard let da = date(a), let db = date(b) else { return 0 }
        return calendar.dateComponents([.day], from: da, to: db).day ?? 0
    }

    static func monthKey(_ date: Date = Date()) -> String {
        let c = calendar.dateComponents([.year, .month], from: date)
        return String(format: "%04d-%02d", c.year ?? 0, c.month ?? 0)
    }

    static func weekKey(_ date: Date = Date()) -> String {
        var iso = Calendar(identifier: .iso8601)
        iso.timeZone = TimeZone.current
        let c = iso.dateComponents([.yearForWeekOfYear, .weekOfYear], from: date)
        return String(format: "%04d-W%02d", c.yearForWeekOfYear ?? 0, c.weekOfYear ?? 0)
    }

    /// Номер дня от 1 января 2026: по нему выбирается ежедневный уровень.
    static func index(_ date: Date = Date()) -> Int {
        let start = calendar.date(from: DateComponents(year: 2026, month: 1, day: 1)) ?? date
        return max(0, calendar.dateComponents([.day], from: start, to: date).day ?? 0)
    }

    static func weekIndex(_ date: Date = Date()) -> Int {
        var iso = Calendar(identifier: .iso8601)
        iso.timeZone = TimeZone.current
        let c = iso.dateComponents([.yearForWeekOfYear, .weekOfYear], from: date)
        return max(0, ((c.yearForWeekOfYear ?? 2026) - 2026) * 53 + (c.weekOfYear ?? 1))
    }

    /// Секунды до следующей полуночи.
    static func secondsToMidnight(_ now: Date = Date()) -> TimeInterval {
        let start = calendar.startOfDay(for: now)
        let next = calendar.date(byAdding: .day, value: 1, to: start) ?? now
        return next.timeIntervalSince(now)
    }

    /// Секунды до конца ISO-недели (до полуночи понедельника).
    static func secondsToWeekEnd(_ now: Date = Date()) -> TimeInterval {
        var iso = Calendar(identifier: .iso8601)
        iso.timeZone = TimeZone.current
        guard let interval = iso.dateInterval(of: .weekOfYear, for: now) else { return 0 }
        return interval.end.timeIntervalSince(now)
    }
}

// MARK: - Испытания

/// Режим уровня: основная карта или испытания.
enum PlayMode: Equatable {
    case main
    case daily(String)
    /// Ключ недели и номер уровня в наборе (0...2).
    case weekly(String, Int)

    var isChallenge: Bool { self != .main }
}

struct WeeklySet: Decodable {
    let week: Int
    let rule: String
    let levels: [LevelData]
}

final class ChallengeStore {
    static let shared = ChallengeStore()

    let daily: [LevelData]
    let weekly: [WeeklySet]

    private init() {
        func load<T: Decodable>(_ name: String, _ type: T.Type) -> T? {
            guard let url = Bundle.main.url(forResource: name, withExtension: "json"),
                  let data = try? Data(contentsOf: url) else { return nil }
            return try? JSONDecoder().decode(type, from: data)
        }
        daily = load("daily", [LevelData].self) ?? []
        weekly = load("weekly", [WeeklySet].self) ?? []
    }

    func dailyLevel(_ date: Date = Date()) -> LevelData? {
        guard !daily.isEmpty else { return nil }
        return daily[Day.index(date) % daily.count]
    }

    func weeklySet(_ date: Date = Date()) -> WeeklySet? {
        guard !weekly.isEmpty else { return nil }
        return weekly[Day.weekIndex(date) % weekly.count]
    }
}

// MARK: - Редкие карточки

enum RareCards {
    /// Золотые версии блюд и сладостей биома 1.
    static let all = ["burger", "cheeseburger", "hotdog", "sandwich", "sub", "pancakes",
                      "donut", "cupcake", "icecream", "pie", "waffle", "muffin"]

    static func sprite(_ id: String) -> String {
        Catalog.shared.dish(id) != nil ? "dish_" + id : id
    }
}

// MARK: - Приветственные задания на 7 дней

struct Quest: Identifiable {
    let id: String
    let day: Int
    let stat: Stat
    let target: Int
    let reward: Reward
}

enum WelcomeQuests {
    static let all: [Quest] = [
        Quest(id: "d1a", day: 1, stat: .levelsWon, target: 2, reward: Reward(coins: 40)),
        Quest(id: "d1b", day: 1, stat: .served, target: 6, reward: Reward(coins: 40)),
        Quest(id: "d1c", day: 1, stat: .triples, target: 4, reward: Reward(boosters: [.hint: 1])),
        Quest(id: "d2a", day: 2, stat: .levelsWon, target: 5, reward: Reward(coins: 60)),
        Quest(id: "d2b", day: 2, stat: .dishes, target: 2, reward: Reward(boosters: [.undo: 1])),
        Quest(id: "d2c", day: 2, stat: .threeStars, target: 1, reward: Reward(coins: 60)),
        Quest(id: "d3a", day: 3, stat: .levelsWon, target: 8, reward: Reward(coins: 80)),
        Quest(id: "d3b", day: 3, stat: .tips, target: 40, reward: Reward(coins: 60)),
        Quest(id: "d3c", day: 3, stat: .boostersUsed, target: 1, reward: Reward(boosters: [.shelf: 1])),
        Quest(id: "d4a", day: 4, stat: .dailyDone, target: 1, reward: Reward(coins: 100)),
        Quest(id: "d4b", day: 4, stat: .levelsWon, target: 11, reward: Reward(coins: 80)),
        Quest(id: "d4c", day: 4, stat: .dishes, target: 8, reward: Reward(boosters: [.hint: 1, .undo: 1])),
        Quest(id: "d5a", day: 5, stat: .levelsWon, target: 14, reward: Reward(coins: 100)),
        Quest(id: "d5b", day: 5, stat: .served, target: 80, reward: Reward(coins: 100)),
        Quest(id: "d5c", day: 5, stat: .threeStars, target: 5, reward: Reward(unlimitedMinutes: 30)),
        Quest(id: "d6a", day: 6, stat: .weeklyLevels, target: 1, reward: Reward(coins: 150)),
        Quest(id: "d6b", day: 6, stat: .levelsWon, target: 17, reward: Reward(coins: 120)),
        Quest(id: "d6c", day: 6, stat: .tips, target: 200, reward: Reward(boosters: [.shelf: 1])),
        Quest(id: "d7a", day: 7, stat: .levelsWon, target: 20, reward: Reward(coins: 150)),
        Quest(id: "d7b", day: 7, stat: .dishes, target: 25, reward: Reward(coins: 150)),
        Quest(id: "d7c", day: 7, stat: .threeStars, target: 10, reward: Reward(rareCard: true))
    ]

    /// Главный приз за все задания: эксклюзивный фон закусочной.
    static let grand = Reward(coins: 500, unlimitedMinutes: 180, background: "diner")

    static let days = 7
    /// После скольких дней набор исчезает с карты, даже если не закрыт.
    static let lifetimeDays = 14
}

// MARK: - Ачивки

struct Achievement: Identifiable {
    let id: String
    let stat: Stat
    let tiers: [Int]
    let symbol: String
}

enum Achievements {
    static let all: [Achievement] = [
        Achievement(id: "chef", stat: .levelsWon, tiers: [10, 30, 60, 90], symbol: "flag.checkered"),
        Achievement(id: "host", stat: .served, tiers: [50, 250, 1000, 3000], symbol: "person.3.fill"),
        Achievement(id: "tips", stat: .tips, tiers: [100, 500, 2000, 6000], symbol: "dollarsign.circle.fill"),
        Achievement(id: "cook", stat: .dishes, tiers: [10, 50, 200, 600], symbol: "fork.knife"),
        Achievement(id: "stars", stat: .threeStars, tiers: [5, 15, 30, 60], symbol: "star.fill"),
        Achievement(id: "combo", stat: .maxCombo, tiers: [4, 6, 8, 10], symbol: "bolt.fill"),
        Achievement(id: "streak", stat: .streakBest, tiers: [3, 7, 14, 30], symbol: "flame.fill"),
        Achievement(id: "daily", stat: .dailyDone, tiers: [3, 10, 30, 100], symbol: "calendar"),
        Achievement(id: "weekly", stat: .weeklyDone, tiers: [1, 4, 12, 26], symbol: "calendar.badge.clock"),
        Achievement(id: "cards", stat: .cards, tiers: [10, 20, 31, 45], symbol: "book.fill"),
        Achievement(id: "rare", stat: .rareCards, tiers: [1, 4, 8, 12], symbol: "sparkles"),
        Achievement(id: "series", stat: .chefBest, tiers: [3, 6, 10, 15], symbol: "crown.fill"),
        Achievement(id: "boosters", stat: .boostersUsed, tiers: [5, 20, 50, 120], symbol: "wand.and.stars"),
        Achievement(id: "chests", stat: .chests, tiers: [1, 2, 3, 6], symbol: "gift.fill")
    ]

    static func reward(tier: Int) -> Reward {
        switch tier {
        case 0: return Reward(coins: 50)
        case 1: return Reward(coins: 150, boosters: [.hint: 1])
        case 2: return Reward(coins: 400, boosters: [.hint: 1, .undo: 1, .shelf: 1])
        default: return Reward(coins: 800, unlimitedMinutes: 60, rareCard: true)
        }
    }
}

// MARK: - Фоны кухни

struct KitchenStyle: Identifiable {
    enum Source { case free, shop, welcome, event, gourmet }

    let id: String
    let price: Int
    let source: Source

    static let defaultId = "kitchen"

    static let all: [KitchenStyle] = [
        KitchenStyle(id: "kitchen", price: 0, source: .free),
        KitchenStyle(id: "peach", price: 800, source: .shop),
        KitchenStyle(id: "lavender", price: 1200, source: .shop),
        KitchenStyle(id: "night", price: 1800, source: .shop),
        KitchenStyle(id: "diner", price: 0, source: .welcome)
    ]

    static func style(_ id: String) -> KitchenStyle? { all.first { $0.id == id } }

    /// Имя картинки фона в Resources/Sprites.
    static func image(_ id: String) -> String { id == defaultId ? "bg_kitchen.jpg" : "bg_\(id).jpg" }
}

// MARK: - Стрик и серия шефа

enum StreakRewards {
    static let coins = [20, 30, 40, 60, 80, 100, 200]
    static let freezePrice = 150
    static let maxFreezes = 2

    static func reward(day: Int) -> Reward {
        let i = max(1, min(7, day)) - 1
        return Reward(coins: coins[i], rareCard: day == 7)
    }
}

enum ChefSeries {
    /// Каждые 3 победы подряд с первой попытки - бустер по кругу.
    static func reward(series: Int) -> Reward? {
        guard series > 0, series % 3 == 0 else { return nil }
        let order: [Booster] = [.hint, .undo, .shelf]
        return Reward(boosters: [order[(series / 3 - 1) % order.count]: 1])
    }
}

enum ChallengeRewards {
    static let daily = Reward(coins: 50)
    static let dailyRareChance = 0.1
    static let weekly = Reward(coins: 300, boosters: [.hint: 1, .undo: 1], rareCard: true)
    static let medal = Reward(coins: 1500, boosters: [.hint: 2, .undo: 2, .shelf: 1], rareCard: true)
    static let medalDaily = 20
    static let medalWeekly = 4
}
