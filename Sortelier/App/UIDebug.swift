#if DEBUG
import SwiftUI

/// Снимки экранов в CI (только отладочная сборка для симулятора).
/// Параметры запуска: -uiScreen shop, -uiLang de, -uiDemo (тестовый прогресс), -uiInfo gold (карточка сундука).
enum UIDebug {
    static var args: [String] { ProcessInfo.processInfo.arguments }

    static func value(_ key: String) -> String? {
        guard let i = args.firstIndex(of: "-" + key), i + 1 < args.count else { return nil }
        return args[i + 1]
    }

    static var demo: Bool { args.contains("-uiDemo") }

    /// До первого кадра: язык и тестовый прогресс.
    static func prepare() {
        if let code = value("uiLang") { Lang.shared.set(code) }
        if demo { PlayerProgress.shared.debugFillDemo() }
    }

    /// Уровень сразу после запуска: -uiLevel 96 (карта) или -uiEvent halloween:4 (уровень ивента).
    static func levelLaunch() -> LevelLaunch? {
        if let id = value("uiLevel").flatMap(Int.init), let level = LevelStore.shared.level(id) {
            return LevelLaunch(level: level, mode: .main)
        }
        if let spec = value("uiEvent") {
            let parts = spec.split(separator: ":").map(String.init)
            let theme = parts[0]
            let index = parts.count > 1 ? Int(parts[1]) ?? 0 : 0
            let levels = EventLevelStore.shared.levels(theme: theme)
            guard levels.indices.contains(index) else { return nil }
            let id = EventCalendar.active().first { $0.kind == .season }?.id ?? "season-debug"
            return LevelLaunch(level: levels[index], mode: .event(id, theme, index))
        }
        return nil
    }

    /// Сколько ходов подсказки сделать сразу: снимок уровня в середине игры (-uiAutoplay 6).
    static var autoplay: Int { value("uiAutoplay").flatMap(Int.init) ?? 0 }

    static func apply(_ router: Router) {
        guard let screen = value("uiScreen") else { return }
        switch screen {
        case "shop": router.tab = .shop
        case "events": router.tab = .events; router.eventsSection = .events
        case "challenges": router.tab = .events; router.eventsSection = .challenges
        case "quests": router.tab = .events; router.eventsSection = .quests
        case "album": router.tab = .album
        case "book": router.tab = .kitchen; router.kitchenSection = .book
        case "achievements": router.tab = .kitchen; router.kitchenSection = .achievements
        case "backgrounds": router.tab = .kitchen; router.kitchenSection = .backgrounds
        case "settings": router.settings = true
        case "language": router.settings = true; router.language = true
        case "lives": router.lives = true
        case "streak": router.streak = true
        case "merge": router.merge = true
        case "eventmap": router.tab = .events; router.eventsSection = .events
        default: router.tab = .map
        }
        if let kind = value("uiInfo") {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
                RewardInfo.show(.chest(ChestKind(rawValue: kind) ?? .gold, 1))
            }
        }
    }
}

extension PlayerProgress {
    /// Прогресс "в середине игры": пройдена часть уровней, есть сундуки, карточки, идущая гонка.
    func debugFillDemo() {
        var d = SaveData()
        d.coins = 12450
        d.lives = 3
        d.livesUpdatedAt = Date()
        for id in 1...34 { d.stars["\(id)"] = [3, 2, 3, 3, 1][id % 5] }
        d.meta.biomes = [1, 2]
        // все интро уровней уже показаны: снимки сразу с полем
        if UIDebug.args.contains("-uiNoIntro") {
            d.seenIntros = ["basics", "patience", "recipes", "hidden", "conflict", "onigiri", "ice", "gourmet", "juice", "dough",
                            "lock", "masa", "limeade", "key", "bakery", "truffles", "chain"]
            d.meta.biomes = [1, 2, 3, 4, 5]
        }
        let stats: [Stat: Int] = [.levelsWon: 34, .served: 260, .tips: 120, .dishes: 40, .triples: 150, .threeStars: 20,
                                  .maxCombo: 6, .boostersUsed: 12, .chests: 3, .merges: 40, .albumCards: 20,
                                  .coinsEarned: 9000, .dailyDone: 4, .streakBest: 3, .gourmets: 3]
        d.meta.stats = Dictionary(uniqueKeysWithValues: stats.map { ($0.key.rawValue, $0.value) })
        d.meta.streak.day = 3
        d.meta.streak.lastDay = Day.key(Date().addingTimeInterval(-86400))
        d.meta.welcomeStart = Day.key(Date().addingTimeInterval(-2 * 86400))
        d.meta.chestInventory = ["bronze": 2, "silver": 1, "gold": 1]
        d.meta.album.season = Day.monthKey()
        for (i, card) in AlbumCatalog.cards.prefix(24).enumerated() { d.meta.album.cards[card.id] = i % 5 == 0 ? 2 : 1 }
        d.meta.album.stars = 18
        d.meta.achievementTiers = ["chef": 1]
        // снимки для App Store: игрок в мексиканской кухне, открыто много блюд, идет ивент
        if UIDebug.args.contains("-uiStore") {
            for id in 1...100 { d.stars["\(id)"] = id % 7 == 0 ? 2 : 3 }
            d.meta.biomes = [1, 2, 3, 4]
            let catalog = Catalog.shared
            d.discovered = catalog.items.filter { (1...4).contains($0.biome) }.map(\.id)
                + catalog.dishes.filter { (1...4).contains($0.biome) }.map { "dish_" + $0.id }
            d.meta.guests = ["autumn"]
        }
        for event in EventCalendar.active(Date()) {
            var st = EventState()
            st.points = UIDebug.args.contains("-uiStore") ? 34 : 10
            st.levels = UIDebug.args.contains("-uiStore") ? 7 : 3
            st.claimed = UIDebug.args.contains("-uiStore") ? [0, 1, 2, 3, 4] : [0]
            d.meta.events[event.id] = st
        }
        d.meta.race.day = Day.key()
        d.meta.race.started = 1
        d.meta.race.joined = Date().addingTimeInterval(-15 * 60)
        d.meta.race.wins = 2
        d.meta.race.seed = 42
        data = d
    }
}
#endif
