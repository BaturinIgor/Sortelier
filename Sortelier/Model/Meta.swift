import Foundation

// MARK: - Награда

/// Награда: монеты, бустеры, безлимитные жизни, жизни, фон, энергия, сундуки альбома.
/// rareCard остался от старых сохранений: такая награда выдается медным сундуком.
/// Один предмет награды.
enum RewardItem: Identifiable, Hashable {
    case coins(Int)
    case booster(Booster, Int)
    case unlimited(Int)
    case lives(Int)
    case energy(Int)
    case chest(ChestKind, Int)
    case background(String)
    /// Гость ивента: покупатель в костюме, который потом заходит на уровни карты.
    case guest(String)

    var id: String {
        switch self {
        case .coins: return "coins"
        case let .booster(b, _): return "booster." + b.rawValue
        case .unlimited: return "unlimited"
        case .lives: return "lives"
        case .energy: return "energy"
        case let .chest(k, _): return "chest." + k.rawValue
        case let .background(bg): return "bg." + bg
        case let .guest(g): return "guest." + g
        }
    }
}

struct Reward: Codable, Hashable {
    var coins = 0
    var boosters: [String: Int] = [:]
    var unlimitedMinutes = 0
    var lives = 0
    var rareCard = false
    var background: String?
    var energy = 0
    var chests: [String: Int] = [:]
    /// Гость ивента (Guests).
    var guest: String?

    init(coins: Int = 0, boosters: [Booster: Int] = [:], unlimitedMinutes: Int = 0, lives: Int = 0,
         rareCard: Bool = false, background: String? = nil, energy: Int = 0, chests: [ChestKind: Int] = [:]) {
        self.coins = coins
        self.boosters = Dictionary(uniqueKeysWithValues: boosters.map { ($0.key.rawValue, $0.value) })
        self.unlimitedMinutes = unlimitedMinutes
        self.lives = lives
        self.rareCard = rareCard
        self.background = background
        self.energy = energy
        self.chests = Dictionary(uniqueKeysWithValues: chests.map { ($0.key.rawValue, $0.value) })
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
        chests = try c.decodeIfPresent([String: Int].self, forKey: .chests) ?? [:]
        guest = try c.decodeIfPresent(String.self, forKey: .guest)
    }

    var chestList: [(ChestKind, Int)] {
        ChestKind.allCases.compactMap { k in
            guard let n = chests[k.rawValue], n > 0 else { return nil }
            return (k, n)
        }
    }

    var boosterList: [(Booster, Int)] {
        Booster.allCases.compactMap { b in
            guard let n = boosters[b.rawValue], n > 0 else { return nil }
            return (b, n)
        }
    }

    /// Награда по отдельным предметам: из них собираются плитки наград и карточки с описанием.
    var items: [RewardItem] {
        var out: [RewardItem] = []
        if coins > 0 { out.append(.coins(coins)) }
        for (b, n) in boosterList { out.append(.booster(b, n)) }
        if unlimitedMinutes > 0 { out.append(.unlimited(unlimitedMinutes)) }
        if lives > 0 { out.append(.lives(lives)) }
        if energy > 0 { out.append(.energy(energy)) }
        var chestsAll = chestList
        if rareCard {
            if let i = chestsAll.firstIndex(where: { $0.0 == .bronze }) {
                chestsAll[i].1 += 1
            } else {
                chestsAll.insert((.bronze, 1), at: 0)
            }
        }
        for (k, n) in chestsAll { out.append(.chest(k, n)) }
        if let bg = background { out.append(.background(bg)) }
        if let g = guest { out.append(.guest(g)) }
        return out
    }

    var isEmpty: Bool {
        coins == 0 && boosterList.isEmpty && unlimitedMinutes == 0 && lives == 0 && !rareCard && background == nil && energy == 0
            && chestList.isEmpty && guest == nil
    }

    static func + (a: Reward, b: Reward) -> Reward {
        var r = a
        r.coins += b.coins
        for (k, v) in b.boosters { r.boosters[k, default: 0] += v }
        r.unlimitedMinutes += b.unlimitedMinutes
        r.lives += b.lives
        r.rareCard = a.rareCard || b.rareCard
        r.background = a.background ?? b.background
        r.guest = a.guest ?? b.guest
        r.energy += b.energy
        for (k, v) in b.chests { r.chests[k, default: 0] += v }
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
    case merges, mergeOrders
    case gourmets, eventRewards, medals, kitchens, coinsEarned, albumCards, booksDone, raceWins
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
    var events: [String: EventState] = [:]
    /// Открытые биомы (первый открыт всегда).
    var biomes: [Int] = []
    /// Обслуженные гурманы с последнего подарка: для гарантии подарка.
    var gourmetSinceGift = 0
    // Покупки: срок VIP, стартовый набор, выданные покупки App Store, неиспользованные пропуска
    var vipUntil: Date?
    var vipDailyDay = ""
    var starterBought = false
    var deliveredTx: [String] = []
    var passCredits = 0
    // Альбом карточек, сундуки в запасе, короткие гонки, шкала звезд ачивок
    var album = AlbumState()
    var chestInventory: [String: Int] = [:]
    var race = RaceState()
    var achievementTrack: [Int] = []
    /// Гости ивентов, которые заходят на уровни карты.
    var guests: [String] = []

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
        events = try c.decodeIfPresent([String: EventState].self, forKey: .events) ?? [:]
        biomes = try c.decodeIfPresent([Int].self, forKey: .biomes) ?? []
        gourmetSinceGift = try c.decodeIfPresent(Int.self, forKey: .gourmetSinceGift) ?? 0
        vipUntil = try c.decodeIfPresent(Date.self, forKey: .vipUntil)
        vipDailyDay = try c.decodeIfPresent(String.self, forKey: .vipDailyDay) ?? ""
        starterBought = try c.decodeIfPresent(Bool.self, forKey: .starterBought) ?? false
        deliveredTx = try c.decodeIfPresent([String].self, forKey: .deliveredTx) ?? []
        passCredits = try c.decodeIfPresent(Int.self, forKey: .passCredits) ?? 0
        album = try c.decodeIfPresent(AlbumState.self, forKey: .album) ?? AlbumState()
        chestInventory = try c.decodeIfPresent([String: Int].self, forKey: .chestInventory) ?? [:]
        race = try c.decodeIfPresent(RaceState.self, forKey: .race) ?? RaceState()
        achievementTrack = try c.decodeIfPresent([Int].self, forKey: .achievementTrack) ?? []
        guests = try c.decodeIfPresent([String].self, forKey: .guests) ?? []
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
    /// Уровень сезонного ивента: id ивента, тема, номер уровня.
    case event(String, String, Int)

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
        Quest(id: "d4a", day: 4, stat: .dailyDone, target: 1, reward: Reward(coins: 100, chests: [.bronze: 1])),
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
        Quest(id: "d7c", day: 7, stat: .threeStars, target: 10, reward: Reward(chests: [.silver: 1]))
    ]

    /// Главный приз за все задания: эксклюзивный фон закусочной.
    static let grand = Reward(coins: 500, unlimitedMinutes: 180, background: "diner")

    static let days = 7
    /// После скольких дней набор исчезает с карты, даже если не закрыт.
    static let lifetimeDays = 14
}

// MARK: - Ачивки

/// Ачивка: у каждой 5 звезд-ступеней. Категории - вкладки на экране ачивок.
struct Achievement: Identifiable {
    enum Category: String, CaseIterable { case kitchen, habits, collection, pantry }

    let id: String
    let category: Category
    let stat: Stat
    let tiers: [Int]
    let symbol: String
}

enum Achievements {
    static let all: [Achievement] = [
        // кухня
        Achievement(id: "chef", category: .kitchen, stat: .levelsWon, tiers: [10, 30, 50, 70, 90], symbol: "flag.checkered"),
        Achievement(id: "host", category: .kitchen, stat: .served, tiers: [50, 250, 1000, 3000, 8000], symbol: "person.3.fill"),
        Achievement(id: "tips", category: .kitchen, stat: .tips, tiers: [100, 500, 2000, 6000, 15000], symbol: "dollarsign.circle.fill"),
        Achievement(id: "cook", category: .kitchen, stat: .dishes, tiers: [10, 50, 200, 600, 1500], symbol: "fork.knife"),
        Achievement(id: "trio", category: .kitchen, stat: .triples, tiers: [20, 100, 400, 1200, 3000], symbol: "square.stack.3d.up.fill"),
        Achievement(id: "stars", category: .kitchen, stat: .threeStars, tiers: [5, 15, 30, 60, 90], symbol: "star.fill"),
        Achievement(id: "combo", category: .kitchen, stat: .maxCombo, tiers: [4, 6, 8, 10, 12], symbol: "bolt.fill"),
        Achievement(id: "gourmet", category: .kitchen, stat: .gourmets, tiers: [1, 5, 15, 40, 100], symbol: "crown.fill"),
        // регулярность
        Achievement(id: "streak", category: .habits, stat: .streakBest, tiers: [3, 7, 14, 30, 60], symbol: "flame.fill"),
        Achievement(id: "daily", category: .habits, stat: .dailyDone, tiers: [3, 10, 30, 100, 200], symbol: "calendar"),
        Achievement(id: "weekly", category: .habits, stat: .weeklyDone, tiers: [1, 4, 12, 26, 52], symbol: "calendar.badge.clock"),
        Achievement(id: "series", category: .habits, stat: .chefBest, tiers: [3, 6, 10, 15, 25], symbol: "medal.fill"),
        Achievement(id: "events", category: .habits, stat: .eventRewards, tiers: [3, 10, 25, 60, 120], symbol: "sparkles"),
        Achievement(id: "racer", category: .habits, stat: .raceWins, tiers: [1, 5, 15, 40, 100], symbol: "flag.2.crossed.fill"),
        // коллекция
        Achievement(id: "cards", category: .collection, stat: .cards, tiers: [10, 30, 50, 70, 86], symbol: "book.fill"),
        Achievement(id: "album", category: .collection, stat: .albumCards, tiers: [10, 25, 45, 65, 84], symbol: "rectangle.stack.fill"),
        Achievement(id: "books", category: .collection, stat: .booksDone, tiers: [1, 3, 5, 7, 9], symbol: "books.vertical.fill"),
        Achievement(id: "chests", category: .collection, stat: .chests, tiers: [5, 20, 60, 150, 400], symbol: "shippingbox.fill"),
        Achievement(id: "kitchens", category: .collection, stat: .kitchens, tiers: [2, 4, 6, 9, 12], symbol: "paintpalette.fill"),
        // кладовая и бустеры
        Achievement(id: "merge", category: .pantry, stat: .mergeOrders, tiers: [5, 20, 60, 150, 400], symbol: "square.grid.3x3.fill"),
        Achievement(id: "merges", category: .pantry, stat: .merges, tiers: [20, 100, 400, 1200, 3000], symbol: "arrow.triangle.merge"),
        Achievement(id: "boosters", category: .pantry, stat: .boostersUsed, tiers: [5, 20, 50, 120, 300], symbol: "wand.and.stars"),
        Achievement(id: "rich", category: .pantry, stat: .coinsEarned, tiers: [1000, 5000, 20000, 60000, 150000], symbol: "bitcoinsign.circle.fill")
    ]

    static var maxStars: Int { all.reduce(0) { $0 + $1.tiers.count } }

    static func reward(tier: Int) -> Reward {
        switch tier {
        case 0: return Reward(coins: 50)
        case 1: return Reward(coins: 120, boosters: [.hint: 1])
        case 2: return Reward(coins: 250, boosters: [.undo: 1, .shuffle: 1])
        case 3: return Reward(coins: 500, chests: [.bronze: 1])
        default: return Reward(coins: 900, unlimitedMinutes: 60, chests: [.silver: 1])
        }
    }
}

/// Шкала наград за общее число звезд ачивок.
enum AchievementTrack {
    struct Milestone: Identifiable {
        let stars: Int
        let reward: Reward
        var id: Int { stars }
    }

    static let milestones: [Milestone] = [
        Milestone(stars: 5, reward: Reward(coins: 200)),
        Milestone(stars: 10, reward: Reward(boosters: [.hint: 1, .undo: 1, .shuffle: 1])),
        Milestone(stars: 15, reward: Reward(coins: 300, chests: [.bronze: 1])),
        Milestone(stars: 22, reward: Reward(unlimitedMinutes: 60, energy: 30)),
        Milestone(stars: 30, reward: Reward(coins: 500, chests: [.silver: 1])),
        Milestone(stars: 40, reward: Reward(boosters: [.hint: 2, .undo: 2, .shelf: 1, .pause: 1])),
        Milestone(stars: 50, reward: Reward(coins: 800, chests: [.silver: 1])),
        Milestone(stars: 62, reward: Reward(unlimitedMinutes: 180, energy: 60)),
        Milestone(stars: 75, reward: Reward(coins: 1200, chests: [.gold: 1])),
        Milestone(stars: 90, reward: Reward(coins: 1500, boosters: [.hint: 3, .undo: 3, .shuffle: 3, .shelf: 2])),
        Milestone(stars: 105, reward: Reward(coins: 2000, chests: [.gold: 2])),
        Milestone(stars: 115, reward: Reward(coins: 5000, unlimitedMinutes: 360, chests: [.star: 1]))
    ]
}

// MARK: - Фоны кухни

struct KitchenStyle: Identifiable {
    enum Source { case free, shop, welcome, event, gourmet, biome }

    let id: String
    let price: Int
    let source: Source

    static let defaultId = "kitchen"

    static let all: [KitchenStyle] = [
        KitchenStyle(id: "kitchen", price: 0, source: .free),
        KitchenStyle(id: "peach", price: 800, source: .shop),
        KitchenStyle(id: "lavender", price: 1200, source: .shop),
        KitchenStyle(id: "night", price: 1800, source: .shop),
        KitchenStyle(id: "diner", price: 0, source: .welcome),
        KitchenStyle(id: "autumn", price: 0, source: .event),
        KitchenStyle(id: "winter", price: 0, source: .event),
        KitchenStyle(id: "sweets", price: 0, source: .event),
        KitchenStyle(id: "bbq", price: 0, source: .event),
        KitchenStyle(id: "japan", price: 0, source: .biome),
        KitchenStyle(id: "italy", price: 0, source: .biome),
        KitchenStyle(id: "mexico", price: 0, source: .biome),
        KitchenStyle(id: "bakery", price: 0, source: .biome),
        KitchenStyle(id: "halloween", price: 0, source: .event),
        KitchenStyle(id: "gourmet", price: 0, source: .gourmet)
    ]

    static func style(_ id: String) -> KitchenStyle? { all.first { $0.id == id } }

    /// Имя картинки фона в Resources/Sprites.
    static func image(_ id: String) -> String { id == defaultId ? "bg_kitchen.jpg" : "bg_\(id).jpg" }
}

// MARK: - Стрик и серия шефа

enum StreakRewards {
    static var coins: [Int] {
        let list = RemoteConfig.shared.ints("balance.streakCoins", [20, 30, 40, 60, 80, 100, 200])
        return list.count == 7 ? list : [20, 30, 40, 60, 80, 100, 200]
    }
    static var freezePrice: Int { RemoteConfig.shared.int("balance.streakFreezePrice", 150) }
    static var maxFreezes: Int { RemoteConfig.shared.int("balance.streakMaxFreezes", 2) }

    static func reward(day: Int) -> Reward {
        let i = max(1, min(7, day)) - 1
        return Reward(coins: coins[i], chests: day == 7 ? [.silver: 1] : (day == 4 ? [.bronze: 1] : [:]))
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
    static let daily = Reward(coins: 50, chests: [.bronze: 1])
    static let weekly = Reward(coins: 300, boosters: [.hint: 1, .undo: 1], chests: [.silver: 1])
    static let medal = Reward(coins: 1500, boosters: [.hint: 2, .undo: 2, .shelf: 1], chests: [.gold: 1])
    static let medalDaily = 20
    static let medalWeekly = 4
}
