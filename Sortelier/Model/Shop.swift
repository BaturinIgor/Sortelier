import Foundation
import StoreKit

/// Товары магазина. Цены и содержимое - из раздела "Экономика" документа требований.
/// В версии из App Store цена приходит из StoreKit, здесь только запасная подпись.
enum ShopItem: String, CaseIterable, Identifiable {
    case starter, coinsS, coinsM, coinsL, coinsXL, coinsXXL, boosters, lives, vipWeek, vipMonth, eventPass, jar, market

    var id: String { rawValue }

    var productId: String { "com.personal.sortelier." + rawValue.lowercased() }

    static func from(productId: String) -> ShopItem? { allCases.first { $0.productId == productId } }

    var fallbackPrice: String {
        switch self {
        case .starter, .coinsS, .lives: return "$0.99"
        case .coinsM, .eventPass, .jar: return "$2.99"
        case .coinsL, .vipMonth: return "$4.99"
        case .coinsXL: return "$9.99"
        case .coinsXXL: return "$19.99"
        case .boosters, .vipWeek, .market: return "$1.99"
        }
    }

    var isVIP: Bool { self == .vipWeek || self == .vipMonth }

    static let coinPacks: [ShopItem] = [.coinsS, .coinsM, .coinsL, .coinsXL, .coinsXXL]

    /// Содержимое покупки. Всегда заранее известное: случайных платных наград нет.
    var reward: Reward {
        switch self {
        case .starter:
            return Reward(coins: 1000, boosters: [.hint: 2, .undo: 2, .shuffle: 2, .shelf: 2, .pause: 2], unlimitedMinutes: 60,
                          chests: [.silver: 1])
        case .coinsS: return Reward(coins: 500, chests: [.bronze: 1])
        case .coinsM: return Reward(coins: 1800, chests: [.silver: 1])
        case .coinsL: return Reward(coins: 3500, chests: [.gold: 1])
        case .coinsXL: return Reward(coins: 8000, chests: [.gold: 2])
        case .coinsXXL: return Reward(coins: 18000, chests: [.gold: 2, .star: 1])
        case .boosters: return Reward(boosters: [.hint: 3, .undo: 3, .shuffle: 3, .shelf: 3], chests: [.bronze: 1])
        case .lives: return Reward(unlimitedMinutes: 120)
        case .market: return Reward(market: [.pin: 3, .bomb: 2, .rainbow: 1, .mallet: 2, .knife: 1, .spatula: 1, .mixer: 1])
        case .vipWeek, .vipMonth, .eventPass, .jar: return Reward()
        }
    }

    /// Выгода пака монет относительно самого маленького.
    var bonusPercent: Int? {
        switch self {
        case .coinsM: return 20
        case .coinsL: return 40
        case .coinsXL: return 60
        case .coinsXXL: return 80
        default: return nil
        }
    }

    /// Картинка пака монет: стопка, горка, мешок, сундук, гора сокровищ.
    var coinSprite: String {
        switch self {
        case .coinsS: return "coins_stack"
        case .coinsM: return "coins_pile"
        case .coinsL: return "coins_bag"
        case .coinsXL: return "coins_chest"
        default: return "coins_mountain"
        }
    }

    /// Срок VIP в тестовом режиме (в App Store срок задает подписка).
    var testDays: Int { self == .vipMonth ? 30 : 7 }
}

/// VIP: все награды за рекламу сразу, монеты x1.5 за уровни, 8 жизней, набор бустеров каждый день.
enum VIP {
    static var coinMultiplier: Double { RemoteConfig.shared.double("balance.vipCoinMultiplier", 1.5) }
    static var maxLives: Int { RemoteConfig.shared.int("balance.vipMaxLives", 8) }
    static let daily = Reward(boosters: [.hint: 1, .undo: 1, .shuffle: 1])
}

/// Покупки через StoreKit 2. В сборке для SideStore App Store недоступен: товары не загружаются,
/// и при тестовом флаге TEST_PURCHASES покупка выдается без оплаты, чтобы можно было проверить магазин и VIP.
/// Все изменения состояния и выдача наград идут на главном потоке.
final class Store: ObservableObject {
    static let shared = Store()

    @Published private(set) var products: [String: Product] = [:]
    @Published private(set) var busy: ShopItem?
    private var listener: Task<Void, Never>?

    static var testMode: Bool {
        #if TEST_PURCHASES
        return true
        #else
        return false
        #endif
    }

    /// Покупки работают: товары пришли из App Store или включен тестовый режим.
    var canPurchase: Bool { !products.isEmpty || Store.testMode }

    func start() {
        guard listener == nil else { return }
        listener = Task.detached { [weak self] in
            for await result in Transaction.updates {
                await self?.handle(result)
            }
        }
        Task {
            await load()
            await refreshEntitlements()
        }
    }

    func price(_ item: ShopItem) -> String {
        products[item.productId]?.displayPrice ?? item.fallbackPrice
    }

    func load() async {
        guard let list = try? await Product.products(for: Set(ShopItem.allCases.map(\.productId))) else { return }
        var map: [String: Product] = [:]
        for product in list { map[product.id] = product }
        await MainActor.run { self.products = map }
    }

    enum Outcome {
        case done(Granted?)
        case cancelled, pending, unavailable, failed
    }

    func buy(_ item: ShopItem) async -> Outcome {
        Analytics.log("purchase_start", ["item": item.rawValue])
        guard let product = products[item.productId] else {
            guard Store.testMode else { return .unavailable }
            let granted = await MainActor.run { PlayerProgress.shared.deliver(item, transaction: nil, vipUntil: nil) }
            Analytics.log("purchase_done", ["item": item.rawValue, "test": true])
            return .done(granted)
        }
        await MainActor.run { self.busy = item }
        defer { Task { await MainActor.run { self.busy = nil } } }
        do {
            switch try await product.purchase() {
            case let .success(verification):
                guard case let .verified(transaction) = verification else {
                    Analytics.log("purchase_failed", ["item": item.rawValue, "reason": "unverified"])
                    return .failed
                }
                let granted = await deliver(transaction)
                await transaction.finish()
                Analytics.log("purchase_done", ["item": item.rawValue])
                return .done(granted)
            case .userCancelled:
                Analytics.log("purchase_cancel", ["item": item.rawValue])
                return .cancelled
            case .pending:
                return .pending
            @unknown default:
                return .failed
            }
        } catch {
            Analytics.log("purchase_failed", ["item": item.rawValue, "reason": error.localizedDescription])
            return .failed
        }
    }

    /// Покупки, завершенные вне приложения или после одобрения родителем.
    private func handle(_ result: VerificationResult<Transaction>) async {
        guard case let .verified(transaction) = result else { return }
        _ = await deliver(transaction)
        await transaction.finish()
        await refreshEntitlements()
    }

    private func deliver(_ transaction: Transaction) async -> Granted? {
        guard let item = ShopItem.from(productId: transaction.productID), transaction.revocationDate == nil else { return nil }
        let id = String(transaction.id)
        let expiration = transaction.expirationDate
        return await MainActor.run { PlayerProgress.shared.deliver(item, transaction: id, vipUntil: expiration) }
    }

    /// Действующая подписка VIP и купленный стартовый набор.
    func refreshEntitlements() async {
        if products.isEmpty && Store.testMode { return }
        var vipUntil: Date?
        var starter = false
        for await result in Transaction.currentEntitlements {
            guard case let .verified(transaction) = result, transaction.revocationDate == nil,
                  let item = ShopItem.from(productId: transaction.productID) else { continue }
            if item.isVIP, let expiration = transaction.expirationDate {
                vipUntil = max(vipUntil ?? expiration, expiration)
            }
            if item == .starter { starter = true }
        }
        let until = vipUntil
        let bought = starter
        await MainActor.run { PlayerProgress.shared.updateEntitlements(vipUntil: until, starter: bought) }
    }

    func restore() async -> Bool {
        Analytics.log("purchase_restore")
        if products.isEmpty && Store.testMode { return true }
        do {
            try await AppStore.sync()
        } catch {
            return false
        }
        await refreshEntitlements()
        return true
    }
}

// MARK: - Выдача покупок

extension PlayerProgress {
    var isVIP: Bool {
        guard let until = data.meta.vipUntil else { return false }
        return until > now
    }

    var vipLeft: TimeInterval? {
        guard let until = data.meta.vipUntil, until > now else { return nil }
        return until.timeIntervalSince(now)
    }

    var starterBought: Bool { data.meta.starterBought }

    /// Выдает купленное. transaction - номер покупки App Store: одна покупка выдается один раз.
    @discardableResult
    func deliver(_ item: ShopItem, transaction: String?, vipUntil: Date?) -> Granted? {
        if let id = transaction {
            guard !data.meta.deliveredTx.contains(id) else { return nil }
            data.meta.deliveredTx.append(id)
            if data.meta.deliveredTx.count > 300 { data.meta.deliveredTx.removeFirst(100) }
        }
        switch item {
        case .vipWeek, .vipMonth:
            let until = vipUntil ?? Date().addingTimeInterval(TimeInterval(item.testDays * 86400))
            data.meta.vipUntil = max(data.meta.vipUntil ?? until, until)
            save()
            Analytics.log("vip_start", ["item": item.rawValue])
            return nil
        case .eventPass:
            data.meta.passCredits += 1
            save()
            applyPassCredit()
            return nil
        case .starter:
            data.meta.starterBought = true
        case .jar:
            return breakJar()
        default:
            break
        }
        save()
        return grant(item.reward, source: "shop_" + item.rawValue)
    }

    func updateEntitlements(vipUntil: Date?, starter: Bool) {
        var changed = false
        if data.meta.vipUntil != vipUntil, vipUntil != nil || data.meta.vipUntil.map({ $0 > Date() }) == true {
            if vipUntil == nil { Analytics.log("vip_end") }
            data.meta.vipUntil = vipUntil
            changed = true
        }
        if starter && !data.meta.starterBought {
            data.meta.starterBought = true
            changed = true
        }
        if changed { save() }
    }

    /// Купленный пропуск открывает платную ветку текущего сезонного ивента
    /// (если ивента сейчас нет - следующего).
    func applyPassCredit() {
        guard data.meta.passCredits > 0,
              let season = activeEvents.first(where: { $0.kind == .season }) else { return }
        var s = eventState(season.id)
        guard !s.pass else { return }
        s.pass = true
        data.meta.events[season.id] = s
        data.meta.passCredits -= 1
        save()
        Analytics.log("event_pass", ["event": season.id])
    }

    /// Ежедневный набор бустеров VIP. Возвращает выданное, если сегодня еще не получали.
    func claimVIPDaily() -> Granted? {
        guard isVIP, data.meta.vipDailyDay != Day.key() else { return nil }
        data.meta.vipDailyDay = Day.key()
        save()
        return grant(VIP.daily, source: "vip_daily")
    }

    /// Монеты VIP сверх награды за уровень: x1.5. На звезды не влияет.
    func vipBonus(for coins: Int) -> Int {
        guard isVIP, coins > 0 else { return 0 }
        let bonus = Int((Double(coins) * (VIP.coinMultiplier - 1)).rounded())
        addCoins(bonus)
        return bonus
    }
}
