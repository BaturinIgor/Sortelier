import Foundation

// MARK: - Сундуки

/// Сундук с карточками альбома. Содержимое известно заранее и видно до открытия.
enum ChestKind: String, CaseIterable, Codable, Identifiable {
    case bronze, silver, gold, star

    var id: String { rawValue }

    /// Сколько карточек внутри.
    var cards: Int {
        switch self {
        case .bronze: return 2
        case .silver: return 4
        case .gold: return 6
        case .star: return 8
        }
    }

    /// Одна карточка в сундуке гарантированно не ниже этих звезд.
    var guaranteed: Int {
        switch self {
        case .bronze: return 2
        case .silver: return 3
        case .gold: return 4
        case .star: return 5
        }
    }

    var coins: Int {
        switch self {
        case .bronze: return 30
        case .silver: return 80
        case .gold: return 200
        case .star: return 300
        }
    }

    var sprite: String { "chest_" + rawValue }
    var openSprite: String { "chest_" + rawValue + "_open" }
}

// MARK: - Карточки и книги

struct AlbumCard: Identifiable, Hashable {
    /// Имя спрайта: продукт, блюдо, покупатель или предмет кухни.
    let id: String
    let stars: Int
    let book: Int
}

struct AlbumBook: Identifiable {
    let id: Int
    let key: String
    let cards: [AlbumCard]
    let reward: Reward
}

/// Альбом: 9 книг по 9-12 карточек, всего 84. Сезон длится календарный месяц.
enum AlbumCatalog {
    private static let raw: [(key: String, cards: [(String, Int)])] = [
        ("burger", [("bun", 1), ("lettuce", 1), ("tomato", 1), ("ketchup", 1), ("cheese", 2), ("patty", 2), ("fries", 2),
                    ("dish_burger", 3), ("dish_cheeseburger", 4)]),
        ("hotdog", [("sausage", 1), ("hotdog_bun", 1), ("bread", 1), ("ham", 2), ("baguette", 2), ("corndog", 3),
                    ("dish_hotdog", 3), ("dish_sandwich", 4), ("dish_sub", 5)]),
        ("breakfast", [("egg", 1), ("milk", 1), ("honey", 1), ("corn", 2), ("soda", 2), ("waffle", 2), ("muffin", 3),
                       ("cookie", 3), ("dish_pancakes", 4)]),
        ("desserts", [("donut", 1), ("cupcake", 1), ("icecream", 2), ("pie", 2), ("mochi", 3), ("taiyaki", 3),
                      ("gelato", 3), ("cannoli", 4), ("tiramisu", 5)]),
        ("market", [("rice", 1), ("fish", 1), ("soy", 1), ("avocado", 1), ("carrot", 2), ("leek", 2), ("mushroom", 2),
                    ("edamame", 3), ("gen_crate", 4)]),
        ("japan", [("dango", 1), ("matcha", 2), ("gyoza", 2), ("tempura", 2), ("dish_onigiri", 3), ("dish_maki", 3),
                   ("dish_sushi", 4), ("dish_tamago", 4), ("dish_ramen", 5)]),
        ("deli", [("flour", 1), ("dough", 1), ("mozzarella", 1), ("basil", 1), ("pasta", 2), ("olive_oil", 2),
                  ("grapes", 2), ("olives", 3), ("grissini", 3)]),
        ("italy", [("focaccia", 1), ("espresso", 2), ("panna_cotta", 2), ("dish_juice", 2), ("dish_pasta", 3),
                   ("dish_bruschetta", 3), ("dish_caprese", 4), ("dish_pizza", 5), ("gen_oven", 4)]),
        ("guests", [("customer_0_happy", 1), ("customer_1_happy", 1), ("customer_2_happy", 1), ("customer_3_happy", 2),
                    ("customer_4_happy", 2), ("customer_5_happy", 2), ("customer_6_happy", 3), ("customer_7_happy", 3),
                    ("customer_8_happy", 3), ("customer_9_happy", 4), ("shelf_gold", 4), ("customer_10_happy", 5)])
    ]

    static let books: [AlbumBook] = raw.enumerated().map { i, b in
        AlbumBook(id: i, key: b.key, cards: b.cards.map { AlbumCard(id: $0.0, stars: $0.1, book: i) },
                  reward: bookReward(i))
    }

    static let cards: [AlbumCard] = books.flatMap(\.cards)
    static let byId: [String: AlbumCard] = Dictionary(uniqueKeysWithValues: cards.map { ($0.id, $0) })

    static func bookReward(_ i: Int) -> Reward {
        switch i {
        case 0: return Reward(coins: 300, boosters: [.hint: 1, .undo: 1])
        case 1: return Reward(coins: 400, unlimitedMinutes: 30)
        case 2: return Reward(coins: 400, boosters: [.shuffle: 1, .shelf: 1])
        case 3: return Reward(coins: 500, energy: 40)
        case 4: return Reward(coins: 500, boosters: [.hint: 2, .pause: 1])
        case 5: return Reward(coins: 600, unlimitedMinutes: 60)
        case 6: return Reward(coins: 600, boosters: [.undo: 2, .shuffle: 2])
        case 7: return Reward(coins: 800, unlimitedMinutes: 120, energy: 60)
        default: return Reward(coins: 1000, boosters: [.hint: 2, .undo: 2, .shuffle: 2, .shelf: 2, .pause: 2])
        }
    }

    /// Главный приз за весь альбом.
    static let grand = Reward(coins: 3000, boosters: [.hint: 3, .undo: 3, .shuffle: 3, .shelf: 3, .pause: 3],
                              unlimitedMinutes: 360)

    /// Цена звездного сундука в звездах альбома (их дают повторки).
    static let starChestPrice = 40

    /// Шанс карточки по звездам, проценты.
    static let weights = [1: 40, 2: 30, 3: 18, 4: 9, 5: 3]

    /// Название карточки: продукт, блюдо, гость или предмет кухни.
    static func name(_ card: AlbumCard, lang: Lang) -> String {
        if card.id.hasPrefix("dish_") { return lang.dishName(String(card.id.dropFirst(5))) }
        if card.id.hasPrefix("customer_") {
            let look = Int(card.id.split(separator: "_")[1]) ?? 0
            return look == CustomerNode.gourmetLook ? lang.t("album.gourmet") : lang.t("album.guest", guestNames[look % guestNames.count])
        }
        if card.id.hasPrefix("gen_") || card.id == "shelf_gold" { return lang.t("album." + card.id) }
        return lang.itemName(card.id)
    }

    static let guestNames = ["Mia", "Leo", "Zoe", "Max", "Ana", "Omar", "Lily", "Hugo", "Nina", "Sam"]
}

// MARK: - Сохранение альбома и гонки

struct AlbumState: Codable {
    /// Месяц сезона: при смене месяца альбом начинается заново.
    var season = ""
    /// Карточка -> сколько штук (повторки тоже считаются).
    var cards: [String: Int] = [:]
    var booksClaimed: [Int] = []
    var grandClaimed = false
    /// Звезды за повторки: копятся на звездный сундук.
    var stars = 0

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        season = try c.decodeIfPresent(String.self, forKey: .season) ?? ""
        cards = try c.decodeIfPresent([String: Int].self, forKey: .cards) ?? [:]
        booksClaimed = try c.decodeIfPresent([Int].self, forKey: .booksClaimed) ?? []
        grandClaimed = try c.decodeIfPresent(Bool.self, forKey: .grandClaimed) ?? false
        stars = try c.decodeIfPresent(Int.self, forKey: .stars) ?? 0
    }
}

/// Результат открытия сундука: карточки по порядку и что из них новое.
struct ChestOpening: Identifiable {
    struct Drop: Identifiable {
        let id: Int
        let card: AlbumCard
        let isNew: Bool
    }

    let id = UUID()
    let kind: ChestKind
    let drops: [Drop]
    let coins: Int
    /// Звезды альбома за повторки.
    let stars: Int
}

extension PlayerProgress {
    /// Альбом текущего месяца. Новый месяц - новый сезон: карточки и награды книг обнуляются.
    var album: AlbumState {
        let month = Day.monthKey()
        guard data.meta.album.season == month else {
            var fresh = AlbumState()
            fresh.season = month
            return fresh
        }
        return data.meta.album
    }

    private func ensureSeason() {
        let month = Day.monthKey()
        guard data.meta.album.season != month else { return }
        if !data.meta.album.season.isEmpty { Analytics.log("album_season_end", ["cards": data.meta.album.cards.count]) }
        data.meta.album = AlbumState()
        data.meta.album.season = month
    }

    func hasCard(_ card: AlbumCard) -> Bool { (album.cards[card.id] ?? 0) > 0 }

    func cardCount(_ card: AlbumCard) -> Int { album.cards[card.id] ?? 0 }

    var albumCardsOwned: Int { AlbumCatalog.cards.filter { hasCard($0) }.count }

    func bookOwned(_ book: AlbumBook) -> Int { book.cards.filter { hasCard($0) }.count }

    func bookComplete(_ book: AlbumBook) -> Bool { bookOwned(book) == book.cards.count }

    func canClaimBook(_ book: AlbumBook) -> Bool { bookComplete(book) && !album.booksClaimed.contains(book.id) }

    func bookClaimed(_ book: AlbumBook) -> Bool { album.booksClaimed.contains(book.id) }

    var albumComplete: Bool { AlbumCatalog.books.allSatisfy { bookComplete($0) } }

    var canClaimAlbumGrand: Bool { albumComplete && !album.grandClaimed }

    /// Секунды до конца сезона альбома.
    var albumSecondsLeft: TimeInterval {
        let cal = Calendar.current
        let c = cal.dateComponents([.year, .month], from: now)
        guard let start = cal.date(from: c), let next = cal.date(byAdding: .month, value: 1, to: start) else { return 0 }
        return next.timeIntervalSince(now)
    }

    // MARK: Сундуки

    func chestCount(_ kind: ChestKind) -> Int { data.meta.chestInventory[kind.rawValue] ?? 0 }

    var chestsWaiting: Int { ChestKind.allCases.reduce(0) { $0 + chestCount($1) } }

    func addChests(_ chests: [String: Int]) {
        for (k, n) in chests where n > 0 { data.meta.chestInventory[k, default: 0] += n }
    }

    /// Открывает сундук из запаса: карточки, монеты, звезды за повторки.
    func openChest(_ kind: ChestKind) -> ChestOpening? {
        guard chestCount(kind) > 0 else { return nil }
        ensureSeason()
        data.meta.chestInventory[kind.rawValue, default: 0] -= 1
        var drops: [ChestOpening.Drop] = []
        var stars = 0
        for i in 0..<kind.cards {
            let card = drawCard(minStars: i == 0 ? kind.guaranteed : 1)
            let had = data.meta.album.cards[card.id] ?? 0
            data.meta.album.cards[card.id] = had + 1
            if had > 0 { stars += card.stars }
            drops.append(ChestOpening.Drop(id: i, card: card, isNew: had == 0))
        }
        data.meta.album.stars += stars
        data.coins += kind.coins
        data.meta.stats[Stat.coinsEarned.rawValue, default: 0] += kind.coins
        data.meta.stats[Stat.chests.rawValue, default: 0] += 1
        let owned = AlbumCatalog.cards.filter { (data.meta.album.cards[$0.id] ?? 0) > 0 }.count
        if owned > stat(.albumCards) { data.meta.stats[Stat.albumCards.rawValue] = owned }
        save()
        Analytics.log("chest_open", ["kind": kind.rawValue, "new": drops.filter(\.isNew).count])
        // самые редкие карточки показываем последними
        let sorted = drops.sorted { $0.card.stars < $1.card.stars }
        return ChestOpening(kind: kind, drops: sorted.enumerated().map { ChestOpening.Drop(id: $0.offset, card: $0.element.card,
                                                                                         isNew: $0.element.isNew) },
                            coins: kind.coins, stars: stars)
    }

    /// Случайная карточка: сначала звезды по весам, потом чаще та, которой еще нет.
    private func drawCard(minStars: Int) -> AlbumCard {
        let options = AlbumCatalog.weights.filter { $0.key >= minStars }
        let total = options.values.reduce(0, +)
        var roll = Int.random(in: 0..<max(1, total))
        var stars = minStars
        for key in options.keys.sorted() {
            roll -= options[key] ?? 0
            if roll < 0 { stars = key; break }
        }
        let pool = AlbumCatalog.cards.filter { $0.stars == stars }
        let missing = pool.filter { (data.meta.album.cards[$0.id] ?? 0) == 0 }
        if !missing.isEmpty && Double.random(in: 0..<1) < 0.6 {
            return missing.randomElement() ?? pool[0]
        }
        return pool.randomElement() ?? AlbumCatalog.cards[0]
    }

    /// Звездный сундук за звезды альбома.
    func buyStarChest() -> Bool {
        ensureSeason()
        guard data.meta.album.stars >= AlbumCatalog.starChestPrice else { return false }
        data.meta.album.stars -= AlbumCatalog.starChestPrice
        data.meta.chestInventory[ChestKind.star.rawValue, default: 0] += 1
        save()
        return true
    }

    func claimBook(_ book: AlbumBook) -> Granted? {
        guard canClaimBook(book) else { return nil }
        data.meta.album.booksClaimed.append(book.id)
        data.meta.stats[Stat.booksDone.rawValue, default: 0] += 1
        save()
        return grant(book.reward, source: "album_book")
    }

    func claimAlbumGrand() -> Granted? {
        guard canClaimAlbumGrand else { return nil }
        data.meta.album.grandClaimed = true
        save()
        return grant(AlbumCatalog.grand, source: "album_grand")
    }

    var albumClaimable: Bool {
        chestsWaiting > 0 || AlbumCatalog.books.contains { canClaimBook($0) } || canClaimAlbumGrand
            || album.stars >= AlbumCatalog.starChestPrice
    }
}
