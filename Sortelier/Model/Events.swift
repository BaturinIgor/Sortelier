import Foundation

/// Ивенты идут по календарю на устройстве, одновременно несколько штук с разной длительностью:
/// большой сезонный (полмесяца), охота за ингредиентом (3 дня из 4), гонка поваров (каждый день,
/// до 3 коротких заездов) и двойные выходные. Позже расписание переедет в удаленный конфиг.
enum EventKind: String, CaseIterable {
    case season, hunt, race, double
}

struct GameEvent: Identifiable, Equatable {
    let kind: EventKind
    /// Тема сезонного ивента или ингредиент охоты.
    let theme: String
    let start: Date
    let end: Date

    var id: String { "\(kind.rawValue)-\(Day.key(start))" }

    func left(_ now: Date) -> TimeInterval { max(0, end.timeIntervalSince(now)) }
}

enum EventCalendar {
    /// Темы сезонного ивента по месяцам: первая и вторая половина.
    static let seasonThemes: [Int: [String]] = [
        1: ["winter", "sweets"], 2: ["sweets", "winter"], 3: ["sweets", "bbq"], 4: ["bbq", "sweets"],
        5: ["bbq", "sweets"], 6: ["bbq", "sweets"], 7: ["bbq", "sweets"], 8: ["bbq", "autumn"],
        9: ["autumn", "sweets"], 10: ["autumn", "sweets"], 11: ["autumn", "winter"], 12: ["winter", "sweets"]
    ]
    static let huntItems = ["egg", "tomato", "honey", "corn"]

    private static var calendar: Calendar { Calendar.current }

    static func active(_ now: Date = Date()) -> [GameEvent] {
        [season(now), hunt(now), race(now), double(now)].compactMap { $0 }
    }

    static func event(_ id: String, _ now: Date = Date()) -> GameEvent? {
        active(now).first { $0.id == id }
    }

    static func season(_ now: Date) -> GameEvent {
        let c = calendar.dateComponents([.year, .month, .day], from: now)
        let month = c.month ?? 1
        let firstHalf = (c.day ?? 1) <= 15
        let monthStart = calendar.date(from: DateComponents(year: c.year, month: month, day: 1)) ?? now
        let mid = calendar.date(byAdding: .day, value: 15, to: monthStart) ?? now
        let next = calendar.date(byAdding: .month, value: 1, to: monthStart) ?? now
        let theme = seasonThemes[month]?[firstHalf ? 0 : 1] ?? "sweets"
        return GameEvent(kind: .season, theme: theme, start: firstHalf ? monthStart : mid, end: firstHalf ? mid : next)
    }

    /// Охота: 3 дня из каждых 4.
    static func hunt(_ now: Date) -> GameEvent? {
        let index = Day.index(now)
        let phase = index % 4
        guard phase < 3 else { return nil }
        let today = calendar.startOfDay(for: now)
        let start = calendar.date(byAdding: .day, value: -phase, to: today) ?? today
        let end = calendar.date(byAdding: .day, value: 3, to: start) ?? today
        let item = huntItems[(index / 4) % huntItems.count]
        return GameEvent(kind: .hunt, theme: item, start: start, end: end)
    }

    /// Гонка поваров: каждый день, заезды обновляются в полночь.
    static func race(_ now: Date) -> GameEvent? {
        let today = calendar.startOfDay(for: now)
        let end = calendar.date(byAdding: .day, value: 1, to: today) ?? today
        return GameEvent(kind: .race, theme: "", start: today, end: end)
    }

    /// Двойные выходные: суббота и воскресенье.
    static func double(_ now: Date) -> GameEvent? {
        let weekday = calendar.component(.weekday, from: now)
        guard weekday == 7 || weekday == 1 else { return nil }
        let today = calendar.startOfDay(for: now)
        let start = calendar.date(byAdding: .day, value: weekday == 7 ? 0 : -1, to: today) ?? today
        let end = calendar.date(byAdding: .day, value: 2, to: start) ?? today
        return GameEvent(kind: .double, theme: "", start: start, end: end)
    }

    /// Следующий ивент этого вида: тема и время начала (для карточек "скоро").
    static func next(_ kind: EventKind, _ now: Date = Date()) -> GameEvent? {
        guard let start = nextStart(kind, now) else { return nil }
        let probe = start.addingTimeInterval(3600)
        switch kind {
        case .season: return season(probe)
        case .hunt: return hunt(probe)
        case .race: return race(probe)
        case .double: return double(probe)
        }
    }

    /// Когда начнется следующий ивент этого вида (для "скоро").
    static func nextStart(_ kind: EventKind, _ now: Date = Date()) -> Date? {
        let today = calendar.startOfDay(for: now)
        for d in 1...8 {
            guard let day = calendar.date(byAdding: .day, value: d, to: today) else { continue }
            let probe = day.addingTimeInterval(3600)
            let e: GameEvent?
            switch kind {
            case .season: e = season(probe)
            case .hunt: e = hunt(probe)
            case .race: e = race(probe)
            case .double: e = double(probe)
            }
            if let e = e, calendar.isDate(e.start, inSameDayAs: day) { return day }
        }
        return nil
    }
}

// MARK: - Прогресс ивента

struct EventState: Codable {
    var points = 0
    var claimed: [Int] = []
    var claimedPass: [Int] = []
    var pass = false
    var levels = 0
    var joined: Date?
    var wins = 0
    var finished: Date?
    var raceClaimed = false
    var bonusDays: [String] = []

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        points = try c.decodeIfPresent(Int.self, forKey: .points) ?? 0
        claimed = try c.decodeIfPresent([Int].self, forKey: .claimed) ?? []
        claimedPass = try c.decodeIfPresent([Int].self, forKey: .claimedPass) ?? []
        pass = try c.decodeIfPresent(Bool.self, forKey: .pass) ?? false
        levels = try c.decodeIfPresent(Int.self, forKey: .levels) ?? 0
        joined = try c.decodeIfPresent(Date.self, forKey: .joined)
        wins = try c.decodeIfPresent(Int.self, forKey: .wins) ?? 0
        finished = try c.decodeIfPresent(Date.self, forKey: .finished)
        raceClaimed = try c.decodeIfPresent(Bool.self, forKey: .raceClaimed) ?? false
        bonusDays = try c.decodeIfPresent([String].self, forKey: .bonusDays) ?? []
    }
}

// MARK: - Награды ивентов

struct EventTier {
    let points: Int
    let free: Reward
    let pass: Reward
}

enum SeasonEvent {
    static let levelsCount = 20

    static func tiers(theme: String) -> [EventTier] {
        [
            EventTier(points: 3, free: Reward(coins: 50), pass: Reward(coins: 150)),
            EventTier(points: 6, free: Reward(boosters: [.hint: 1]), pass: Reward(boosters: [.hint: 1, .undo: 1])),
            EventTier(points: 10, free: Reward(coins: 100), pass: Reward(unlimitedMinutes: 60)),
            EventTier(points: 15, free: Reward(boosters: [.undo: 1]), pass: Reward(coins: 300)),
            EventTier(points: 20, free: Reward(unlimitedMinutes: 30), pass: Reward(chests: [.silver: 1])),
            EventTier(points: 26, free: Reward(coins: 150), pass: Reward(boosters: [.shelf: 2])),
            EventTier(points: 32, free: Reward(boosters: [.shelf: 1]), pass: Reward(coins: 400)),
            EventTier(points: 40, free: Reward(coins: 200, chests: [.bronze: 1]), pass: Reward(chests: [.gold: 1])),
            EventTier(points: 48, free: Reward(boosters: [.hint: 1, .undo: 1]), pass: Reward(unlimitedMinutes: 120)),
            EventTier(points: 56, free: Reward(chests: [.silver: 1]), pass: Reward(boosters: [.hint: 2, .undo: 2, .shelf: 2])),
            EventTier(points: 65, free: Reward(coins: 300), pass: Reward(coins: 600)),
            EventTier(points: 75, free: Reward(background: theme), pass: Reward(coins: 800, chests: [.gold: 1]))
        ]
    }

    /// Печати за победу: новый уровень карты - 2, переигровка - 1, испытание и уровень ивента - 3, за 3 звезды +1.
    static func stamps(mode: PlayMode, isNewLevel: Bool, stars: Int) -> Int {
        let base: Int
        switch mode {
        case .main: base = isNewLevel ? 2 : 1
        case .daily, .weekly, .event: base = 3
        }
        return base + (stars == 3 ? 1 : 0)
    }
}

enum HuntEvent {
    static let tiers: [EventTier] = [
        EventTier(points: 5, free: Reward(coins: 100), pass: Reward()),
        EventTier(points: 12, free: Reward(boosters: [.hint: 1, .undo: 1]), pass: Reward()),
        EventTier(points: 20, free: Reward(chests: [.silver: 1]), pass: Reward()),
        EventTier(points: 30, free: Reward(unlimitedMinutes: 60), pass: Reward()),
        EventTier(points: 42, free: Reward(coins: 500, chests: [.gold: 1]), pass: Reward())
    ]
}

/// Соперник в гонке поваров. Прогресс считается от начала заезда, одинаково при каждом запуске.
struct Rival: Identifiable {
    let id: Int
    let name: String
    let look: Int
    /// Минут на одну победу.
    let pace: Double

    func wins(joined: Date, now: Date) -> Int {
        let minutes = now.timeIntervalSince(joined) / 60
        return min(RaceEvent.goal, Int(minutes / pace))
    }

    func finishTime(joined: Date) -> Date {
        joined.addingTimeInterval(Double(RaceEvent.goal) * pace * 60)
    }
}

/// Заезд гонки поваров: до 3 в день, кто первым выиграет 5 уровней. Места 1-3 получают сундуки.
struct RaceState: Codable {
    var day = ""
    /// Сколько заездов начато в этот день.
    var started = 0
    var joined: Date?
    var wins = 0
    var finished: Date?
    var claimed = false
    var seed: UInt64 = 0

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        day = try c.decodeIfPresent(String.self, forKey: .day) ?? ""
        started = try c.decodeIfPresent(Int.self, forKey: .started) ?? 0
        joined = try c.decodeIfPresent(Date.self, forKey: .joined)
        wins = try c.decodeIfPresent(Int.self, forKey: .wins) ?? 0
        finished = try c.decodeIfPresent(Date.self, forKey: .finished)
        claimed = try c.decodeIfPresent(Bool.self, forKey: .claimed) ?? false
        seed = try c.decodeIfPresent(UInt64.self, forKey: .seed) ?? 0
    }
}

enum RaceEvent {
    static let goal = 5
    /// Заезды без ограничений, но сундуки за места 1-3 дают только в первых трех заездах дня.
    static let chestRaces = 3
    static let names = ["Marco", "Yuki", "Ana", "Leo", "Priya", "Omar", "Sofia", "Chen", "Lena", "Diego"]

    static func rivals(seed: UInt64) -> [Rival] {
        var rng = SeededRandom(seed: seed)
        var used = Set<Int>()
        var list: [Rival] = []
        let paces = [3.2, 4.6, 6.4, 9.0]
        for i in 0..<4 {
            var n = Int(rng.next() % UInt64(names.count))
            while used.contains(n) { n = (n + 1) % names.count }
            used.insert(n)
            let jitter = Double(rng.next() % 100) / 100.0 * 1.5
            list.append(Rival(id: i, name: names[n], look: Int(rng.next() % UInt64(CustomerNode.looks)),
                              pace: paces[i] + jitter))
        }
        return list
    }

    static func reward(place: Int, chests: Bool = true) -> Reward {
        switch place {
        case 1: return Reward(coins: 100, chests: chests ? [.gold: 1] : [:])
        case 2: return Reward(coins: 50, chests: chests ? [.silver: 1] : [:])
        case 3: return Reward(coins: 20, chests: chests ? [.bronze: 1] : [:])
        default: return Reward(coins: 10)
        }
    }
}

enum DoubleEvent {
    static let multiplier = 2
    static let bonusMinutes = 60
}

/// Хеш строки, одинаковый при каждом запуске (hashValue в Swift каждый раз разный).
func stableHash(_ s: String) -> UInt64 {
    var h: UInt64 = 14695981039346656037
    for b in s.utf8 {
        h ^= UInt64(b)
        h = h &* 1099511628211
    }
    return h
}

/// Простой детерминированный генератор: соперники одинаковые при каждом запуске.
struct SeededRandom {
    private var state: UInt64

    init(seed: UInt64) { state = seed &* 6364136223846793005 &+ 1442695040888963407 }

    mutating func next() -> UInt64 {
        state = state &* 6364136223846793005 &+ 1442695040888963407
        var x = state
        x ^= x >> 33
        x = x &* 0xff51afd7ed558ccd
        x ^= x >> 33
        return x
    }
}

final class EventLevelStore {
    static let shared = EventLevelStore()

    private let levels: [String: [LevelData]]

    private init() {
        if let url = Bundle.main.url(forResource: "events", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let decoded = try? JSONDecoder().decode([String: [LevelData]].self, from: data) {
            levels = decoded
        } else {
            levels = [:]
        }
    }

    func levels(theme: String) -> [LevelData] { levels[theme] ?? [] }
}
