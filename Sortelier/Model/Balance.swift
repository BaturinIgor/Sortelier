import Foundation

/// Стартовый баланс из документа требований. Позже переедет в удаленный конфиг.
enum Balance {
    static let coinsPerOrder = 5
    static let comboBonus = 2
    static let comboFrom = 3
    static let comboWindow = 3
    static let efficiencyShare = 0.3

    static let maxLives = 5
    static let lifeRegen: TimeInterval = 30 * 60
    static let livesRefillPrice = 200

    static let startCoins = 300
    static let startBoosters: [Booster: Int] = [.hint: 3, .undo: 3, .shuffle: 1, .shelf: 1]
    /// Сколько ходов терпение стоит на паузе после бустера.
    static let pauseMoves = 5

    static let continuePrices = [150, 300, 600]
    static let adDailyLimit = 10

    static let levelsPerBiome = 30

    struct Chest {
        let stars: Int
        let coins: Int
        let boosters: [Booster: Int]
        let unlimitedLives: TimeInterval
        let goldShelves: Bool
    }

    static let chests: [Chest] = [
        Chest(stars: 30, coins: 200, boosters: [.hint: 1, .undo: 1], unlimitedLives: 0, goldShelves: false),
        Chest(stars: 60, coins: 500, boosters: [.hint: 1, .undo: 1, .shelf: 1], unlimitedLives: 3600, goldShelves: false),
        Chest(stars: 90, coins: 1500, boosters: [.hint: 2, .undo: 2, .shelf: 2], unlimitedLives: 3 * 3600, goldShelves: true)
    ]
}

enum Booster: String, Codable, CaseIterable, Identifiable {
    case hint, undo, shuffle, shelf, pause

    var id: String { rawValue }

    var price: Int {
        switch self {
        case .undo: return 60
        case .hint: return 80
        case .shuffle: return 100
        case .pause: return 120
        case .shelf: return 150
        }
    }

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
