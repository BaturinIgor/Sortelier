import Foundation

/// Заказ покупателя: тройка одинаковых продуктов или блюдо по рецепту.
struct Order: Codable, Hashable {
    enum Kind: String, Codable { case triple, dish }
    let kind: Kind
    let target: String
}

struct CatalogItem: Decodable, Hashable {
    let id: String
    let kind: String
    let biome: Int
}

struct CatalogDish: Decodable, Hashable {
    let id: String
    let ingredients: [String]
    let biome: Int
}

/// Продукты и рецепты. Лежат в Resources/Data/catalog.json, генерирует tools/levels/generate.py.
final class Catalog {
    static let shared = Catalog()

    let items: [CatalogItem]
    let dishes: [CatalogDish]
    private let recipeIndex: [String: String]
    private let dishById: [String: CatalogDish]

    private init() {
        struct File: Decodable {
            let items: [CatalogItem]
            let dishes: [CatalogDish]
        }
        var file = File(items: [], dishes: [])
        if let url = Bundle.main.url(forResource: "catalog", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let decoded = try? JSONDecoder().decode(File.self, from: data) {
            file = decoded
        }
        items = file.items
        dishes = file.dishes
        var index: [String: String] = [:]
        for dish in file.dishes {
            index[dish.ingredients.sorted().joined(separator: "|")] = dish.id
        }
        recipeIndex = index
        var byId: [String: CatalogDish] = [:]
        for dish in file.dishes { byId[dish.id] = dish }
        dishById = byId
    }

    func dish(_ id: String) -> CatalogDish? { dishById[id] }

    /// Что дает полный ряд из трех продуктов.
    func result(of three: [String]) -> Order? {
        guard three.count == 3 else { return nil }
        if three[0] == three[1] && three[1] == three[2] {
            return Order(kind: .triple, target: three[0])
        }
        if let dish = recipeIndex[three.sorted().joined(separator: "|")] {
            return Order(kind: .dish, target: dish)
        }
        return nil
    }

    func items(inBiome biome: Int) -> [CatalogItem] {
        items.filter { $0.biome == biome }
    }

    func dishes(inBiome biome: Int) -> [CatalogDish] {
        dishes.filter { $0.biome == biome }
    }
}

struct LevelData: Decodable, Identifiable {
    let id: Int
    let biome: Int
    let shelves: [[[String?]]]
    let orders: [Order]
    let par: Int
    /// Терпение покупателя в ходах и максимум чаевых (нет в старых уровнях).
    let patience: Int?
    let tipMax: Int?
    let stars: [Int]
    let best: Int
    let hard: Bool
    let intro: String?
    /// Особое правило недельного испытания: noboosters, hidden, recipes.
    let rule: String?
}

final class LevelStore {
    static let shared = LevelStore()

    let levels: [LevelData]

    private init() {
        if let url = Bundle.main.url(forResource: "levels_1", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let decoded = try? JSONDecoder().decode([LevelData].self, from: data) {
            levels = decoded.sorted { $0.id < $1.id }
        } else {
            levels = []
        }
    }

    func level(_ id: Int) -> LevelData? {
        levels.first { $0.id == id }
    }
}
