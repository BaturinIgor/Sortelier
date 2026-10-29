import Foundation

// Фоновые события, которые идут сами, пока игрок проходит уровни любой из двух игр:
// "Большой рецепт", огород поставщика, банка чаевых, тайный критик, счастливый час.

struct ExtrasData: Codable {
    var recipe = RecipeState()
    var garden = GardenState()
    var jar = JarState()
    var critic = CriticState()

    init() {}

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        recipe = try c.decodeIfPresent(RecipeState.self, forKey: .recipe) ?? RecipeState()
        garden = try c.decodeIfPresent(GardenState.self, forKey: .garden) ?? GardenState()
        jar = try c.decodeIfPresent(JarState.self, forKey: .jar) ?? JarState()
        critic = try c.decodeIfPresent(CriticState.self, forKey: .critic) ?? CriticState()
    }
}

// MARK: - Большой рецепт

struct RecipeState: Codable {
    var week = ""
    var step = 0
    var choice: Int?
    var progress = 0
    /// Ингредиенты, которые легли на блюдо (по шагам).
    var plate: [String] = []
    /// Шаги, закрытые вне экрана рецепта: их ингредиенты прилетят на блюдо при открытии.
    var unseen = 0
}

enum BigRecipe {
    static let steps = 25
    static let items = ["tomato", "lime", "cheese", "grapes", "milk", "carrot"]
    static let themes = ["pizza", "cake", "salad", "paella"]

    static var scale: Double { RemoteConfig.shared.double("recipe.scale", 1.0) }

    struct Option: Equatable {
        let item: String
        let count: Int
        let reward: Reward
    }

    static func theme(_ week: String = Day.weekKey()) -> String {
        themes[Int(stableHash("theme" + week) % UInt64(themes.count))]
    }

    static func isMilestone(_ step: Int) -> Bool { (step + 1) % 5 == 0 }

    /// Два варианта шага: обычный и сложный (больше продуктов, награда лучше).
    static func options(week: String, step: Int) -> [Option] {
        var rng = M3RNG(seed: stableHash("recipe" + week + "-\(step)"))
        var pool = items
        rng.shuffle(&pool)
        let base = Double(12 + step * 3 / 2) * scale
        let easy = max(5, Int((base / 5).rounded()) * 5)
        let hard = max(10, Int((base * 1.6 / 5).rounded()) * 5)
        return [Option(item: pool[0], count: easy, reward: reward(step: step, hard: false, rng: &rng)),
                Option(item: pool[1], count: hard, reward: reward(step: step, hard: true, rng: &rng))]
    }

    private static func reward(step: Int, hard: Bool, rng: inout M3RNG) -> Reward {
        if step == steps - 1 {
            return Reward(coins: 1500, boosters: [.hint: 2, .undo: 2, .shelf: 1], unlimitedMinutes: hard ? 120 : 60,
                          market: [.rainbow: 1, .bomb: 2], chests: [.gold: 1])
        }
        if isMilestone(step) {
            let chest: ChestKind = step >= 14 ? .silver : .bronze
            return hard ? Reward(coins: 200 + step * 10, market: [.bomb: 1], chests: [step >= 14 ? .gold : .silver: 1])
                        : Reward(coins: 120 + step * 8, chests: [chest: 1])
        }
        let coins = 30 + step * 4
        if !hard { return Reward(coins: coins) }
        switch rng.int(4) {
        case 0: return Reward(coins: coins, market: [.pin: 1])
        case 1: return Reward(coins: coins, market: [.mallet: 1])
        case 2: return Reward(coins: coins, boosters: [.hint: 1])
        default: return Reward(coins: coins, energy: 10)
        }
    }
}

extension PlayerProgress {
    var recipe: RecipeState {
        let week = Day.weekKey()
        var s = data.extras.recipe
        if s.week != week { s = RecipeState(week: week) }
        return s
    }

    var recipeOptions: [BigRecipe.Option] {
        let s = recipe
        guard s.step < BigRecipe.steps else { return [] }
        return BigRecipe.options(week: s.week, step: s.step)
    }

    var recipeCurrent: BigRecipe.Option? {
        let s = recipe
        guard let choice = s.choice, recipeOptions.indices.contains(choice) else { return nil }
        return recipeOptions[choice]
    }

    var recipeDone: Bool { recipe.step >= BigRecipe.steps }

    func chooseRecipe(_ index: Int) {
        var s = recipe
        guard s.choice == nil, s.step < BigRecipe.steps, (0..<2).contains(index) else { return }
        s.choice = index
        s.progress = 0
        data.extras.recipe = s
        save()
        Analytics.log("recipe_choice", ["step": s.step, "hard": index == 1])
    }

    /// Собранные продукты (в любой игре и на огороде). Возвращает, сколько шагов закрылось.
    @discardableResult
    func recipeAdd(_ collected: [String: Int]) -> Int {
        var s = recipe
        guard s.step < BigRecipe.steps, !collected.isEmpty else { return 0 }
        let options = BigRecipe.options(week: s.week, step: s.step)
        if s.choice == nil {
            // шаг без выбора: продукт засчитывается в вариант, где он нужен
            let matches = options.indices.filter { (collected[options[$0].item] ?? 0) > 0 }
            guard let first = matches.first else {
                data.extras.recipe = s
                return 0
            }
            s.choice = first
        }
        guard let choice = s.choice else { return 0 }
        let option = options[choice]
        let gain = (collected[option.item] ?? 0) * (HappyHour.active() ? 2 : 1)
        guard gain > 0 else { return 0 }
        s.progress += gain
        var closed = 0
        if s.progress >= option.count {
            s.plate.append(option.item)
            s.step += 1
            s.choice = nil
            s.progress = 0
            s.unseen += 1
            closed = 1
            data.extras.recipe = s
            data.meta.stats[Stat.recipeSteps.rawValue, default: 0] += 1
            _ = grant(option.reward, source: "recipe")
            Analytics.log("recipe_step", ["step": s.step])
        }
        data.extras.recipe = s
        save()
        return closed
    }

    func recipeSeen() {
        var s = recipe
        s.unseen = 0
        data.extras.recipe = s
        save()
    }

    /// Название блюда по двум главным ингредиентам.
    func recipeTop(_ count: Int = 2) -> [String] {
        let plate = recipe.plate
        var counts: [String: Int] = [:]
        for item in plate { counts[item, default: 0] += 1 }
        return counts.sorted { $0.value != $1.value ? $0.value > $1.value : $0.key < $1.key }.prefix(count).map(\.key)
    }
}

// MARK: - Огород поставщика

struct GardenBed: Codable, Equatable {
    var item: String
    var planted: Date
    /// Сколько секунд срезали поливом (победы).
    var boost: Double = 0
}

struct GardenState: Codable {
    var beds: [GardenBed] = []
    var harvests = 0
}

enum Garden {
    static var bedCount: Int { 3 }
    static var growSeconds: Double { Double(RemoteConfig.shared.int("garden.growMinutes", 180)) * 60 }
    /// Каждая победа поливает грядки: минус столько секунд.
    static var waterSeconds: Double { Double(RemoteConfig.shared.int("garden.waterMinutes", 12)) * 60 }
    static var yield: Int { RemoteConfig.shared.int("garden.yield", 12) }
    /// Что растет на грядке по очереди.
    static let crops: [[String]] = [["tomato", "carrot"], ["lime", "grapes"], ["cheese", "milk"]]

    static func reward(bed: Int, harvest: Int) -> Reward {
        switch (bed + harvest) % 4 {
        case 0: return Reward(coins: 40)
        case 1: return Reward(coins: 25, energy: 6)
        case 2: return Reward(coins: 25, market: [[.mallet, .pin, .mixer][harvest % 3]: 1])
        default: return Reward(coins: 30, boosters: [[Booster.hint, .undo, .shuffle][harvest % 3]: 1])
        }
    }
}

extension PlayerProgress {
    var gardenUnlocked: Bool { marketUnlocked }

    var gardenBeds: [GardenBed] {
        var beds = data.extras.garden.beds
        while beds.count < Garden.bedCount {
            let i = beds.count
            beds.append(GardenBed(item: Garden.crops[i][0], planted: Date().addingTimeInterval(-Garden.growSeconds * 0.75)))
        }
        return beds
    }

    func gardenLeft(_ i: Int) -> TimeInterval {
        let bed = gardenBeds[i]
        let ready = bed.planted.addingTimeInterval(Garden.growSeconds - bed.boost)
        return max(0, ready.timeIntervalSince(now))
    }

    func gardenFraction(_ i: Int) -> Double { 1 - gardenLeft(i) / Garden.growSeconds }

    var gardenReady: Int { (0..<Garden.bedCount).filter { gardenLeft($0) <= 0 }.count }

    /// Победа поливает огород.
    func gardenWater() {
        guard gardenUnlocked else { return }
        var beds = gardenBeds
        let water = Garden.waterSeconds * (HappyHour.active() ? 2 : 1)
        for i in beds.indices { beds[i].boost += water }
        data.extras.garden.beds = beds
        save()
    }

    /// Сбор урожая: награда, продукты в "Большой рецепт", грядка засевается следующим.
    func harvest(_ i: Int) -> (Granted, String, Int)? {
        guard gardenLeft(i) <= 0 else { return nil }
        var beds = gardenBeds
        let item = beds[i].item
        let n = data.extras.garden.harvests
        let crops = Garden.crops[i % Garden.crops.count]
        let next = crops[(crops.firstIndex(of: item).map { $0 + 1 } ?? 0) % crops.count]
        beds[i] = GardenBed(item: next, planted: Date())
        data.extras.garden.beds = beds
        data.extras.garden.harvests += 1
        data.meta.stats[Stat.harvests.rawValue, default: 0] += 1
        save()
        let granted = grant(Garden.reward(bed: i, harvest: n), source: "garden")
        recipeAdd([item: Garden.yield])
        Analytics.log("garden_harvest", ["item": item])
        return (granted, item, Garden.yield)
    }
}

// MARK: - Банка чаевых

struct JarState: Codable {
    var coins = 0
    var broken = 0
}

enum TipJar {
    static var capacity: Int { RemoteConfig.shared.int("jar.capacity", 3000) }
    /// Разбить можно, когда набралось столько.
    static var minimum: Int { RemoteConfig.shared.int("jar.minimum", 1200) }
    static var perWin: Int { RemoteConfig.shared.int("jar.perWin", 25) }
}

extension PlayerProgress {
    var jarCoins: Int { data.extras.jar.coins }
    var jarFull: Bool { jarCoins >= TipJar.capacity }
    var jarCanBreak: Bool { jarCoins >= TipJar.minimum }

    /// Часть монет каждой победы падает в банку (в счастливый час вдвое больше). Возвращает, сколько упало.
    @discardableResult
    func jarAdd(win: Bool, coins: Int) -> Int {
        guard win, marketUnlocked else { return 0 }
        let add = (TipJar.perWin + coins / 3) * (HappyHour.active() ? 2 : 1)
        let before = data.extras.jar.coins
        data.extras.jar.coins = min(TipJar.capacity, before + add)
        save()
        return data.extras.jar.coins - before
    }

    /// Покупка "Разбить банку": все монеты из банки игроку.
    func breakJar() -> Granted? {
        let coins = data.extras.jar.coins
        guard coins > 0 else { return nil }
        data.extras.jar.coins = 0
        data.extras.jar.broken += 1
        save()
        Analytics.log("jar_break", ["coins": coins])
        return grant(Reward(coins: coins), source: "jar")
    }
}

// MARK: - Тайный критик

struct CriticState: Codable {
    /// Сколько побед до следующего визита.
    var countdown = 3
    /// Критик сидит на следующем уровне.
    var pending = false
    var month = ""
    var points = 0
    var claimed: [Int] = []
    var reviews = 0
}

struct CriticReview: Equatable {
    let stars: Int
    let text: Int
    let points: Int
}

enum Critic {
    /// Очки рейтинга на 1-5 звезд ресторана за месяц.
    static let thresholds = [3, 8, 14, 21, 30]

    static func reward(_ index: Int) -> Reward {
        switch index {
        case 0: return Reward(coins: 150, market: [.pin: 1])
        case 1: return Reward(coins: 250, boosters: [.hint: 1, .undo: 1], chests: [.bronze: 1])
        case 2: return Reward(coins: 400, market: [.bomb: 1, .knife: 1], chests: [.silver: 1])
        case 3: return Reward(coins: 600, boosters: [.shelf: 1], unlimitedMinutes: 60, chests: [.silver: 1])
        default: return Reward(coins: 1200, market: [.rainbow: 1], chests: [.gold: 1])
        }
    }

    static let textVariants = 4
    /// Образ критика: отдельный портрет (tools/render/customers.py).
    static let sprite = "critic"
}

extension PlayerProgress {
    var critic: CriticState {
        var s = data.extras.critic
        let month = Day.monthKey()
        if s.month != month {
            s.month = month
            s.points = 0
            s.claimed = []
        }
        return s
    }

    /// Критик ждет на этом уровне (показывается при старте).
    var criticHere: Bool { marketUnlocked && critic.pending }

    var criticStars: Int { Critic.thresholds.filter { critic.points >= $0 }.count }

    /// Конец уровня любой игры. Победа с критиком - рецензия и очки рейтинга.
    func criticFinish(won: Bool, stars: Int) -> CriticReview? {
        guard marketUnlocked else { return nil }
        var s = critic
        var review: CriticReview?
        if s.pending {
            s.pending = false
            s.countdown = Int.random(in: 3...6)
            if won {
                let points = stars + (stars == 3 ? 1 : 0)
                s.points += points
                s.reviews += 1
                data.meta.stats[Stat.reviews.rawValue, default: 0] += 1
                review = CriticReview(stars: stars, text: Int.random(in: 0..<Critic.textVariants), points: points)
                Analytics.log("critic_review", ["stars": stars])
            }
        } else if won {
            s.countdown -= 1
            if s.countdown <= 0 { s.pending = true }
        }
        data.extras.critic = s
        save()
        return review
    }

    func criticClaimable(_ i: Int) -> Bool {
        let s = critic
        return s.points >= Critic.thresholds[i] && !s.claimed.contains(i)
    }

    var criticAnyClaimable: Bool { Critic.thresholds.indices.contains { criticClaimable($0) } }

    func claimCritic(_ i: Int) -> Granted? {
        guard criticClaimable(i) else { return nil }
        var s = critic
        s.claimed.append(i)
        data.extras.critic = s
        save()
        return grant(Critic.reward(i), source: "critic")
    }
}

// MARK: - Счастливый час

/// Два окна по 30 минут в день в случайное (но одинаковое для всех) время с 11 до 22.
/// В счастливый час "Большой рецепт", банка чаевых и полив огорода идут вдвое быстрее.
enum HappyHour {
    static var minutes: Int { RemoteConfig.shared.int("happy.minutes", 30) }
    static var perDay: Int { RemoteConfig.shared.int("happy.perDay", 2) }

    static func windows(on date: Date) -> [DateInterval] {
        let calendar = Calendar.current
        let day = calendar.startOfDay(for: date)
        var rng = M3RNG(seed: stableHash("happy" + Day.key(date)))
        var starts: [Int] = []
        // слоты по полчаса с 11:00 до 21:30, не подряд
        let slots = Array(22..<43)
        var tries = 0
        while starts.count < perDay && tries < 50 {
            tries += 1
            let s = slots[rng.int(slots.count)]
            if starts.allSatisfy({ abs($0 - s) > 2 }) { starts.append(s) }
        }
        return starts.sorted().map { slot in
            DateInterval(start: day.addingTimeInterval(Double(slot) * 1800), duration: Double(minutes) * 60)
        }
    }

    static func current(_ date: Date = Date()) -> DateInterval? {
        #if DEBUG
        if UIDebug.flag("uiHappy") { return DateInterval(start: date.addingTimeInterval(-300), duration: 1800) }
        #endif
        return windows(on: date).first { $0.contains(date) }
    }

    static func active(_ date: Date = Date()) -> Bool { current(date) != nil }

    /// Ближайшее окно сегодня или завтра.
    static func next(_ date: Date = Date()) -> DateInterval? {
        let today = windows(on: date).filter { $0.start > date }
        if let first = today.first { return first }
        guard let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: date) else { return nil }
        return windows(on: tomorrow).first
    }
}
