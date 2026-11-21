import Foundation
import StoreKit
import FirebaseAnalytics
import FirebaseCore
import UserMessagingPlatform

/// Анонимная статистика через Google Analytics for Firebase (как в Habits).
///
/// - Все события игры идут через `Analytics.log(имя, параметры)`: имена и ключи приводятся к правилам Firebase
///   (буквы, цифры и _, до 40 символов, до 25 параметров, строки до 100 символов).
/// - Экономика монет - стандартные события Firebase `earn_virtual_currency` / `spend_virtual_currency`
///   с источником или покупкой, покупки за деньги - `purchase` с ценой и валютой.
/// - Без GoogleService-Info.plist (сборка для SideStore, локальная и отладочная сборка) ничего не отправляется.
///   В отладке сбор включается аргументом запуска -AnalyticsDebug (с -FIRDebugEnabled события видны в DebugView).
///
/// Личных данных нет: только номера уровней, звезды, монеты и т. п. IDFA Firebase не собирает (FirebaseAnalyticsCore,
/// без AdSupport), IDFV и рекламные сигналы выключены в Info.plist. Согласие: в Европе, пока игрок не дал согласие
/// в форме Google (UMP, цель 1 TCF - хранение на устройстве), Firebase работает без идентификатора
/// (analytics_storage = denied), рекламные виды согласия всегда denied.
enum Analytics {
    private static var configured = false

    /// Firebase настроен (есть GoogleService-Info.plist) и это не отладочная сборка.
    static var isAvailable: Bool {
        guard Bundle.main.path(forResource: "GoogleService-Info", ofType: "plist") != nil else { return false }
        #if DEBUG
        return ProcessInfo.processInfo.arguments.contains("-AnalyticsDebug")
        #else
        return true
        #endif
    }

    /// Вызывается при запуске (до рекламы: согласие UMP обновит consent).
    static func start() {
        if !configured, isAvailable,
           let path = Bundle.main.path(forResource: "GoogleService-Info", ofType: "plist"),
           // испорченный plist уронил бы приложение в configure(), а так просто нет статистики
           let options = FirebaseOptions(contentsOfFile: path) {
            FirebaseApp.configure(options: options)
            configured = true
            updateConsent()
            // в Info.plist сбор выключен (FIREBASE_ANALYTICS_COLLECTION_ENABLED = false), включаем после consent
            FirebaseAnalytics.Analytics.setAnalyticsCollectionEnabled(true)
            refreshUser()
        }
        log("app_open")
    }

    // MARK: Согласие

    /// Согласие из формы Google (UMP). Вызывается при запуске и после каждого ответа в форме.
    static func updateConsent() {
        guard configured else { return }
        FirebaseAnalytics.Analytics.setConsent([
            .analyticsStorage: storageAllowed ? .granted : .denied,
            .adStorage: .denied,
            .adUserData: .denied,
            .adPersonalization: .denied,
        ])
    }

    /// Можно ли хранить идентификатор статистики. Вне Европы - да, в Европе - если в форме дано согласие на цель 1.
    /// Пока UMP не ответил (первый запуск, нет сети), - нет: события уходят без идентификатора.
    static var storageAllowed: Bool {
        switch ConsentInformation.shared.consentStatus {
        case .notRequired:
            return true
        case .obtained:
            let defaults = UserDefaults.standard
            guard defaults.integer(forKey: "IABTCF_gdprApplies") == 1 else { return true }
            return (defaults.string(forKey: "IABTCF_PurposeConsents") ?? "").first == "1"
        default:
            return false
        }
    }

    // MARK: События

    static func log(_ event: String, _ params: [String: Any] = [:]) {
        #if DEBUG
        print("[analytics]", event, params)
        #endif
        guard configured else { return }
        FirebaseAnalytics.Analytics.logEvent(firebaseName(event), parameters: firebaseParameters(params))
    }

    /// Получены монеты. source - откуда: level_win, market_win, double_coins, chest, purchase...
    static func earned(_ coins: Int, source: String) {
        guard coins > 0 else { return }
        log(AnalyticsEventEarnVirtualCurrency, [AnalyticsParameterVirtualCurrencyName: "coins",
                                                AnalyticsParameterValue: coins, "source": source])
    }

    /// Потрачены монеты. item - на что: booster_hint, continue, m3_moves, kitchen_unlock...
    static func spent(_ coins: Int, item: String) {
        guard coins > 0 else { return }
        log(AnalyticsEventSpendVirtualCurrency, [AnalyticsParameterVirtualCurrencyName: "coins",
                                                 AnalyticsParameterValue: coins, AnalyticsParameterItemName: item])
    }

    /// Покупка за деньги: стандартное событие purchase с ценой и валютой (для дохода в Firebase).
    static func purchase(_ product: Product, item: String) {
        log(AnalyticsEventPurchase, [
            AnalyticsParameterValue: NSDecimalNumber(decimal: product.price).doubleValue,
            AnalyticsParameterCurrency: product.priceFormatStyle.currencyCode,
            AnalyticsParameterItemID: product.id,
            AnalyticsParameterItemName: item,
        ])
    }

    /// Свойства игрока для разрезов: до какого уровня дошел, VIP, открыт ли "3 в ряд".
    static func setUser(level: Int, vip: Bool, marketOpen: Bool) {
        guard configured else { return }
        FirebaseAnalytics.Analytics.setUserProperty(String(level), forName: "max_level")
        FirebaseAnalytics.Analytics.setUserProperty(vip ? "1" : "0", forName: "is_vip")
        FirebaseAnalytics.Analytics.setUserProperty(marketOpen ? "1" : "0", forName: "market_open")
    }

    /// Свойства игрока по текущему прогрессу: при запуске и после побед.
    static func refreshUser() {
        guard configured else { return }
        let p = PlayerProgress.shared
        setUser(level: p.currentLevel, vip: p.isVIP, marketOpen: p.marketUnlocked)
    }

    // MARK: Правила Firebase

    /// "levelWin" и "level.win" -> "level_win": Firebase разрешает только буквы, цифры и _, до 40 символов.
    static func firebaseName(_ name: String) -> String {
        var result = ""
        var previous: Character = "_"
        for char in name {
            defer { previous = char }
            if char == "." || char == "-" || char == " " {
                if !result.hasSuffix("_") { result.append("_") }
            } else if char.isUppercase {
                if !result.isEmpty && !result.hasSuffix("_") && (previous.isLowercase || previous.isNumber) { result.append("_") }
                result.append(contentsOf: char.lowercased())
            } else if char.isLetter || char.isNumber || char == "_" {
                result.append(char)
            }
        }
        // имя должно начинаться с буквы
        while let first = result.first, !first.isLetter { result.removeFirst() }
        return String(result.prefix(40))
    }

    /// Параметры для Firebase: не больше 25, строки до 100 символов, флаги как 0/1.
    static func firebaseParameters(_ payload: [String: Any]) -> [String: Any] {
        var result: [String: Any] = [:]
        for (key, value) in payload.sorted(by: { $0.key < $1.key }).prefix(25) {
            let name = firebaseName(key)
            switch value {
            case let flag as Bool: result[name] = flag ? 1 : 0
            case let number as Int: result[name] = number
            case let number as Double: result[name] = number
            case let text as String: result[name] = String(text.prefix(100))
            // другие типы не отправляем: их текстовое описание могло бы унести лишнее
            default: continue
            }
        }
        return result
    }
}
