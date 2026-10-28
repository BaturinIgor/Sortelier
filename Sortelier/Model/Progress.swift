import Foundation
import Combine

/// Настройки звука и вибрации.
struct GameSettings: Codable, Equatable {
    var music = true
    var sound = true
    var haptics = true

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        music = try c.decodeIfPresent(Bool.self, forKey: .music) ?? true
        sound = try c.decodeIfPresent(Bool.self, forKey: .sound) ?? true
        haptics = try c.decodeIfPresent(Bool.self, forKey: .haptics) ?? true
    }
}

/// Прогресс игрока. Хранится JSON-файлом в Application Support.
struct SaveData: Codable {
    var coins = Balance.startCoins
    var lives = Balance.maxLives
    var livesUpdatedAt = Date()
    var unlimitedLivesUntil: Date?
    var boosters: [String: Int] = Dictionary(uniqueKeysWithValues: Balance.startBoosters.map { ($0.key.rawValue, $0.value) })
    var stars: [String: Int] = [:]
    var best: [String: Int] = [:]
    var chests: [Int] = []
    var discovered: [String] = []
    var goldShelves = false
    var language: String?
    var adDay = ""
    var adViews = 0
    var seenIntros: [String] = []
    var playerId = UUID().uuidString
    var settings = GameSettings()
    var meta = MetaData()
    var merge = MergeData()

    init() {}

    // Новые поля в обновлениях не должны сбрасывать прогресс: читаем все, что есть.
    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        let d = SaveData()
        coins = try c.decodeIfPresent(Int.self, forKey: .coins) ?? d.coins
        lives = try c.decodeIfPresent(Int.self, forKey: .lives) ?? d.lives
        livesUpdatedAt = try c.decodeIfPresent(Date.self, forKey: .livesUpdatedAt) ?? d.livesUpdatedAt
        unlimitedLivesUntil = try c.decodeIfPresent(Date.self, forKey: .unlimitedLivesUntil)
        boosters = try c.decodeIfPresent([String: Int].self, forKey: .boosters) ?? d.boosters
        stars = try c.decodeIfPresent([String: Int].self, forKey: .stars) ?? [:]
        best = try c.decodeIfPresent([String: Int].self, forKey: .best) ?? [:]
        chests = try c.decodeIfPresent([Int].self, forKey: .chests) ?? []
        discovered = try c.decodeIfPresent([String].self, forKey: .discovered) ?? []
        goldShelves = try c.decodeIfPresent(Bool.self, forKey: .goldShelves) ?? false
        language = try c.decodeIfPresent(String.self, forKey: .language)
        adDay = try c.decodeIfPresent(String.self, forKey: .adDay) ?? ""
        adViews = try c.decodeIfPresent(Int.self, forKey: .adViews) ?? 0
        seenIntros = try c.decodeIfPresent([String].self, forKey: .seenIntros) ?? []
        playerId = try c.decodeIfPresent(String.self, forKey: .playerId) ?? d.playerId
        settings = try c.decodeIfPresent(GameSettings.self, forKey: .settings) ?? GameSettings()
        meta = try c.decodeIfPresent(MetaData.self, forKey: .meta) ?? MetaData()
        merge = try c.decodeIfPresent(MergeData.self, forKey: .merge) ?? MergeData()
    }
}

final class PlayerProgress: ObservableObject {
    static let shared = PlayerProgress()

    @Published var data: SaveData
    @Published private(set) var now = Date()

    private var timer: AnyCancellable?

    private static var fileURL: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("save.json")
    }

    private init() {
        if let raw = try? Data(contentsOf: Self.fileURL),
           let decoded = try? JSONDecoder().decode(SaveData.self, from: raw) {
            data = decoded
        } else {
            data = SaveData()
        }
        refreshLives()
        timer = Timer.publish(every: 1, on: .main, in: .common).autoconnect().sink { [weak self] date in
            self?.now = date
            self?.refreshLives()
            self?.refreshEnergy()
        }
    }

    func save() {
        if let raw = try? JSONEncoder().encode(data) {
            try? raw.write(to: Self.fileURL, options: .atomic)
        }
    }

    // MARK: - Настройки

    var settings: GameSettings { data.settings }

    func update(settings: GameSettings) {
        data.settings = settings
        save()
        Audio.shared.updateMusic()
    }

    // MARK: - Монеты и бустеры

    var coins: Int { data.coins }

    func addCoins(_ amount: Int) {
        guard amount != 0 else { return }
        data.coins = max(0, data.coins + amount)
        save()
    }

    func spend(_ amount: Int) -> Bool {
        guard data.coins >= amount else { return false }
        data.coins -= amount
        save()
        return true
    }

    func count(_ booster: Booster) -> Int { data.boosters[booster.rawValue] ?? 0 }

    func add(_ booster: Booster, _ amount: Int = 1) {
        data.boosters[booster.rawValue, default: 0] += amount
        save()
    }

    func use(_ booster: Booster) -> Bool {
        guard count(booster) > 0 else { return false }
        data.boosters[booster.rawValue, default: 0] -= 1
        data.meta.stats[Stat.boostersUsed.rawValue, default: 0] += 1
        save()
        Analytics.log("booster_use", ["booster": booster.rawValue])
        return true
    }

    func buy(_ booster: Booster) -> Bool {
        guard spend(booster.price) else { return false }
        add(booster)
        return true
    }

    // MARK: - Жизни

    /// С VIP запас жизней больше.
    var maxLives: Int { isVIP ? VIP.maxLives : Balance.maxLives }

    var unlimitedLives: Bool {
        if let until = data.unlimitedLivesUntil { return until > now }
        return false
    }

    var lives: Int { unlimitedLives ? maxLives : data.lives }

    var hasLife: Bool { unlimitedLives || data.lives > 0 }

    /// Секунды до следующей жизни, nil если жизни полные.
    var nextLifeIn: TimeInterval? {
        guard !unlimitedLives, data.lives < maxLives else { return nil }
        return max(0, data.livesUpdatedAt.addingTimeInterval(Balance.lifeRegen).timeIntervalSince(now))
    }

    var unlimitedLeft: TimeInterval? {
        guard let until = data.unlimitedLivesUntil, until > now else { return nil }
        return until.timeIntervalSince(now)
    }

    private func refreshLives() {
        guard data.lives < maxLives else {
            return
        }
        let elapsed = Date().timeIntervalSince(data.livesUpdatedAt)
        let gained = Int(elapsed / Balance.lifeRegen)
        guard gained > 0 else { return }
        data.lives = min(maxLives, data.lives + gained)
        data.livesUpdatedAt = data.lives >= maxLives
            ? Date()
            : data.livesUpdatedAt.addingTimeInterval(Double(gained) * Balance.lifeRegen)
        save()
    }

    func loseLife() {
        guard !unlimitedLives else { return }
        if data.lives >= maxLives { data.livesUpdatedAt = Date() }
        data.lives = max(0, data.lives - 1)
        save()
        if data.lives == 0 { Analytics.log("lives_out") }
    }

    func addLife(_ amount: Int = 1) {
        data.lives = min(maxLives, data.lives + amount)
        if data.lives >= maxLives { data.livesUpdatedAt = Date() }
        save()
    }

    func refillLives() -> Bool {
        guard spend(Balance.livesRefillPrice) else { return false }
        addLife(maxLives)
        return true
    }

    func addUnlimitedLives(_ seconds: TimeInterval) {
        guard seconds > 0 else { return }
        let start = max(data.unlimitedLivesUntil ?? Date(), Date())
        data.unlimitedLivesUntil = start.addingTimeInterval(seconds)
        save()
    }

    // MARK: - Уровни и звезды

    func stars(_ level: Int) -> Int { data.stars[String(level)] ?? 0 }

    func best(_ level: Int) -> Int { data.best[String(level)] ?? 0 }

    func isPassed(_ level: Int) -> Bool { stars(level) > 0 }

    /// Первый непройденный уровень.
    var currentLevel: Int {
        let count = LevelStore.shared.levels.count
        for id in 1...max(1, count) where !isPassed(id) { return id }
        return count
    }

    func isUnlocked(_ level: Int) -> Bool { level <= currentLevel && isBiomeOpen(Biomes.of(level: level)) }

    func totalStars(biome: Int = 1) -> Int {
        LevelStore.shared.levels.filter { $0.biome == biome }.reduce(0) { $0 + stars($1.id) }
    }

    struct LevelReward {
        let coinsAdded: Int
        let newRecord: Bool
        let firstThreeStars: Bool
        let lifeReturned: Bool
    }

    /// Засчитывает победу. Монеты при переигровке только за улучшение рекорда.
    func completeLevel(_ level: Int, coins: Int, stars newStars: Int) -> LevelReward {
        let previousBest = best(level)
        let previousStars = stars(level)
        let added = max(0, coins - previousBest)
        data.best[String(level)] = max(previousBest, coins)
        data.stars[String(level)] = max(previousStars, newStars)
        data.coins += added
        let firstThree = newStars == 3 && previousStars < 3
        var lifeReturned = false
        if firstThree && !unlimitedLives && data.lives < maxLives {
            data.lives += 1
            if data.lives >= maxLives { data.livesUpdatedAt = Date() }
            lifeReturned = true
        }
        save()
        return LevelReward(coinsAdded: added, newRecord: coins > previousBest && previousBest > 0,
                           firstThreeStars: firstThree, lifeReturned: lifeReturned)
    }

    // MARK: - Сундуки

    /// Сундук index: биом index / 3 + 1, номер index % 3.
    func chestReady(_ index: Int) -> Bool {
        !data.chests.contains(index) && totalStars(biome: index / 3 + 1) >= Biomes.chest(index).stars
    }

    func chestClaimed(_ index: Int) -> Bool { data.chests.contains(index) }

    func claimChest(_ index: Int) {
        guard chestReady(index) else { return }
        let chest = Biomes.chest(index)
        data.chests.append(index)
        data.meta.stats[Stat.chests.rawValue, default: 0] += 1
        data.coins += chest.coins
        for (booster, n) in chest.boosters { data.boosters[booster.rawValue, default: 0] += n }
        if chest.goldShelves { data.goldShelves = true }
        save()
        addUnlimitedLives(chest.unlimitedLives)
        Analytics.log("chest_open", ["stars": chest.stars])
    }

    // MARK: - Кулинарная книга

    func isDiscovered(_ id: String) -> Bool { data.discovered.contains(id) }

    /// Возвращает true, если открыт впервые.
    @discardableResult
    func discover(_ id: String) -> Bool {
        guard !data.discovered.contains(id) else { return false }
        data.discovered.append(id)
        data.meta.stats[Stat.cards.rawValue] = data.discovered.count
        save()
        return true
    }

    // MARK: - Реклама и прочее

    var adsLeftToday: Int {
        let today = Self.dayKey(Date())
        return data.adDay == today ? max(0, Balance.adDailyLimit - data.adViews) : Balance.adDailyLimit
    }

    func countAdView() {
        let today = Self.dayKey(Date())
        if data.adDay != today {
            data.adDay = today
            data.adViews = 0
        }
        data.adViews += 1
        save()
    }

    private static func dayKey(_ date: Date) -> String {
        let c = Calendar.current.dateComponents([.year, .month, .day], from: date)
        return "\(c.year ?? 0)-\(c.month ?? 0)-\(c.day ?? 0)"
    }

    func seenIntro(_ key: String) -> Bool { data.seenIntros.contains(key) }

    func markIntro(_ key: String) {
        guard !data.seenIntros.contains(key) else { return }
        data.seenIntros.append(key)
        save()
    }

    var language: String? {
        get { data.language }
        set { data.language = newValue; save() }
    }

    var playerId: String { data.playerId }

    var goldShelves: Bool { data.goldShelves }
}
