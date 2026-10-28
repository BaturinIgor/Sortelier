import Foundation

/// Биомы карты: по 30 уровней, открываются звездами предыдущего биома или монетами.
enum Biomes {
    /// Сколько биомов уже есть в игре.
    static let playable = 3
    /// Анонсы следующих кухонь на карте ("скоро").
    static let upcoming = [4, 5, 6]
    static let unlockPrice = 3000

    static func first(_ biome: Int) -> Int { (biome - 1) * Balance.levelsPerBiome + 1 }
    static func last(_ biome: Int) -> Int { biome * Balance.levelsPerBiome }
    static func of(level: Int) -> Int { max(1, (level - 1) / Balance.levelsPerBiome + 1) }

    /// Звезды предыдущего биома, нужные для открытия (из 90).
    static func starsNeeded(_ biome: Int) -> Int { biome == 2 ? 54 : 63 }

    /// Фон уровней биома, если игрок не выбрал свой.
    static func style(_ biome: Int) -> String {
        switch biome {
        case 2: return "japan"
        case 3: return "italy"
        default: return KitchenStyle.defaultId
        }
    }

    /// Музыка биома.
    static func music(_ biome: Int) -> String {
        switch biome {
        case 2: return "music_japan"
        case 3: return "music_italy"
        default: return "music_kitchen"
        }
    }

    /// Знаковое блюдо для карточки биома на карте.
    static func icon(_ biome: Int) -> String {
        switch biome {
        case 1: return "dish_burger"
        case 2: return "dish_sushi"
        case 3: return "dish_pizza"
        default: return ""
        }
    }

    /// Сундуки звезд: по три на биом. Индекс сундука = (биом - 1) * 3 + номер.
    static func chests(_ biome: Int) -> [Balance.Chest] {
        switch biome {
        case 1: return Balance.chests
        case 2:
            return [
                Balance.Chest(stars: 30, coins: 300, boosters: [.hint: 1, .undo: 1], unlimitedLives: 0, goldShelves: false),
                Balance.Chest(stars: 60, coins: 700, boosters: [.hint: 1, .undo: 1, .shelf: 1], unlimitedLives: 3600,
                              goldShelves: false, album: .silver),
                Balance.Chest(stars: 90, coins: 2000, boosters: [.hint: 2, .undo: 2, .shelf: 2],
                              unlimitedLives: 4 * 3600, goldShelves: false, album: .gold)
            ]
        default:
            return [
                Balance.Chest(stars: 30, coins: 400, boosters: [.hint: 1, .undo: 1], unlimitedLives: 0, goldShelves: false),
                Balance.Chest(stars: 60, coins: 900, boosters: [.hint: 1, .undo: 1, .shelf: 1], unlimitedLives: 2 * 3600,
                              goldShelves: false, album: .silver),
                Balance.Chest(stars: 90, coins: 2500, boosters: [.hint: 3, .undo: 3, .shelf: 2],
                              unlimitedLives: 6 * 3600, goldShelves: false, album: .star)
            ]
        }
    }

    static func chest(_ index: Int) -> Balance.Chest {
        let list = chests(index / 3 + 1)
        return list[min(index % 3, list.count - 1)]
    }
}

// MARK: - Открытие биомов

extension PlayerProgress {
    func isBiomeOpen(_ biome: Int) -> Bool {
        biome == 1 || (biome <= Biomes.playable && data.meta.biomes.contains(biome))
    }

    /// Весь предыдущий биом пройден: можно открывать следующий.
    func biomeGateReached(_ biome: Int) -> Bool {
        biome >= 2 && biome <= Biomes.playable && isPassed(Biomes.last(biome - 1))
    }

    func biomeStarsReady(_ biome: Int) -> Bool {
        totalStars(biome: biome - 1) >= Biomes.starsNeeded(biome)
    }

    /// Открывает биом за звезды (pay = false) или за монеты.
    @discardableResult
    func openBiome(_ biome: Int, pay: Bool) -> Bool {
        guard !isBiomeOpen(biome), biomeGateReached(biome) else { return false }
        if pay {
            guard spend(Biomes.unlockPrice) else { return false }
        } else {
            guard biomeStarsReady(biome) else { return false }
        }
        data.meta.biomes.append(biome)
        let style = Biomes.style(biome)
        if !data.meta.backgrounds.contains(style) { data.meta.backgrounds.append(style) }
        save()
        Analytics.log("biome_open", ["biome": biome, "paid": pay])
        return true
    }

    /// Биом, в котором сейчас игрок: последний открытый с непройденными уровнями.
    var currentBiome: Int {
        Biomes.of(level: min(currentLevel, LevelStore.shared.levels.last?.id ?? 1))
    }

    /// Биом, который показываем на карте: последний открытый, где сейчас игрок.
    var mapBiome: Int {
        let biome = currentBiome
        return isBiomeOpen(biome) ? biome : max(1, biome - 1)
    }

    /// Фон уровня биома: выбранный игроком или фирменный фон кухни.
    func background(forBiome biome: Int) -> String {
        if data.meta.background != KitchenStyle.defaultId { return data.meta.background }
        return isBiomeOpen(biome) ? Biomes.style(biome) : KitchenStyle.defaultId
    }

    // MARK: - Гурманы

    /// Гурман доволен: иногда дарит фон кухни, а когда фон уже есть - монеты.
    /// Гарантия: не позже шестого довольного гурмана.
    func gourmetServed(count: Int) -> Granted? {
        guard count > 0 else { return nil }
        data.meta.gourmetSinceGift += count
        let owned = data.meta.backgrounds.contains("gourmet")
        let lucky = Double.random(in: 0..<1) < 0.2 * Double(count)
        if !owned && (lucky || data.meta.gourmetSinceGift >= 6) {
            data.meta.gourmetSinceGift = 0
            save()
            Analytics.log("gourmet_gift")
            return grant(Reward(background: "gourmet"), source: "gourmet")
        }
        if owned && lucky {
            save()
            return grant(Reward(coins: 50 * count), source: "gourmet")
        }
        save()
        return nil
    }
}
