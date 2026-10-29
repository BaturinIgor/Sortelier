import Foundation

/// Стартовый баланс из документа требований. Числа можно поменять удаленным конфигом (раздел "balance"),
/// значения здесь - запасные, если в конфиге ключа нет.
enum Balance {
    private static var config: RemoteConfig { .shared }

    static var coinsPerOrder: Int { config.int("balance.coinsPerOrder", 5) }
    static var comboBonus: Int { config.int("balance.comboBonus", 2) }
    static var comboFrom: Int { config.int("balance.comboFrom", 3) }
    static var comboWindow: Int { config.int("balance.comboWindow", 3) }
    static var efficiencyShare: Double { config.double("balance.efficiencyShare", 0.3) }

    static var maxLives: Int { config.int("balance.maxLives", 5) }
    static var lifeRegen: TimeInterval { TimeInterval(config.int("balance.lifeRegenMinutes", 30) * 60) }
    static var livesRefillPrice: Int { config.int("balance.livesRefillPrice", 200) }

    static var startCoins: Int { config.int("balance.startCoins", 300) }
    static let startBoosters: [Booster: Int] = [.hint: 3, .undo: 3, .shuffle: 1, .shelf: 1]
    /// Сколько ходов терпение стоит на паузе после бустера.
    static var pauseMoves: Int { config.int("balance.pauseMoves", 5) }

    static var continuePrices: [Int] { config.ints("balance.continuePrices", [150, 300, 600]) }
    static var adDailyLimit: Int { config.int("balance.adDailyLimit", 10) }

    static let levelsPerBiome = 30

    struct Chest {
        let stars: Int
        let coins: Int
        let boosters: [Booster: Int]
        let unlimitedLives: TimeInterval
        let goldShelves: Bool
        /// Сундук альбома в придачу.
        var album: ChestKind? = nil
    }

    static let chests: [Chest] = [
        Chest(stars: 30, coins: 200, boosters: [.hint: 1, .undo: 1], unlimitedLives: 0, goldShelves: false),
        Chest(stars: 60, coins: 500, boosters: [.hint: 1, .undo: 1, .shelf: 1], unlimitedLives: 3600, goldShelves: false,
              album: .silver),
        Chest(stars: 90, coins: 1500, boosters: [.hint: 2, .undo: 2, .shelf: 2], unlimitedLives: 3 * 3600, goldShelves: true,
              album: .gold)
    ]
}

enum Booster: String, Codable, CaseIterable, Identifiable {
    case hint, undo, shuffle, shelf, pause

    var id: String { rawValue }

    var price: Int {
        let fallback: Int
        switch self {
        case .undo: fallback = 60
        case .hint: fallback = 80
        case .shuffle: fallback = 100
        case .pause: fallback = 120
        case .shelf: fallback = 150
        }
        return RemoteConfig.shared.int("balance.boosterPrices." + rawValue, fallback)
    }

    /// Объемная иконка бустера (tools/render/icons.py).
    var icon: String { "icon_" + rawValue }

    var symbol: String {
        switch self {
        case .hint: return "lightbulb.fill"
        case .undo: return "arrow.uturn.backward"
        case .shuffle: return "shuffle"
        case .shelf: return "plus.rectangle.on.rectangle"
        case .pause: return "hourglass"
        }
    }
}
