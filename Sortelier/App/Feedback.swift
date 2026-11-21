import UIKit
import StoreKit

/// Обратная связь: почта поддержки и письмо с данными об устройстве.
enum Support {
    /// Почта для вопросов и ошибок (та же в SUPPORT.md, PRIVACY.md и в App Store).
    static let email = "dawnwell.app+sortelier@gmail.com"

    /// Версия и сборка приложения: "1.2 (45)".
    static var appVersion: String {
        let info = Bundle.main.infoDictionary
        let version = info?["CFBundleShortVersionString"] as? String ?? "?"
        let build = info?["CFBundleVersion"] as? String ?? "?"
        return "\(version) (\(build))"
    }

    /// Модель устройства вида iPhone15,2 (на симуляторе - модель, которую он изображает).
    static var deviceModel: String {
        if let sim = ProcessInfo.processInfo.environment["SIMULATOR_MODEL_IDENTIFIER"] { return sim }
        var info = utsname()
        uname(&info)
        return withUnsafeBytes(of: &info.machine) { raw in
            String(decoding: raw.prefix { $0 != 0 }, as: UTF8.self)
        }
    }

    /// Техническая часть письма: по ней проще найти ошибку. Личных данных здесь нет, ID игрока случайный.
    static var deviceInfo: String {
        [
            "Sortelier \(appVersion)",
            "\(deviceModel), iOS \(UIDevice.current.systemVersion)",
            "Lang: \(Lang.shared.code)",
            "Player ID: \(PlayerProgress.shared.playerId)",
        ].joined(separator: "\n")
    }

    /// Открывает письмо в почтовом приложении. Если почты нет, копирует адрес и говорит об этом.
    static func writeEmail() {
        let lang = Lang.shared
        let body = "\n\n\n---\n" + deviceInfo
        var parts = URLComponents()
        parts.scheme = "mailto"
        parts.path = email
        parts.queryItems = [
            URLQueryItem(name: "subject", value: lang.t("feedback.subject")),
            URLQueryItem(name: "body", value: body),
        ]
        Analytics.log("feedback_open")
        guard let url = parts.url else { return copyFallback() }
        UIApplication.shared.open(url, options: [:]) { opened in
            if !opened { copyFallback() }
        }
    }

    private static func copyFallback() {
        UIPasteboard.general.string = email
        Toast.info(Lang.shared.t("feedback.noMail", email), icon: "doc.on.doc.fill")
    }
}

/// Запрос оценки в App Store в удачный момент: после победы на 3 звезды или в серии побед "3 в ряд",
/// когда игрок уже наигрался (не раньше 12 побед), не после проигрыша и не чаще раза в 120 дней и раза за версию.
/// Сколько раз окно реально покажется, решает iOS (не больше 3 раз в год).
enum ReviewPrompt {
    private static let defaults = UserDefaults.standard

    private enum Key {
        static let wins = "review.wins"
        static let lastAsk = "review.lastAsk"
        static let lastVersion = "review.lastVersion"
        static let pending = "review.pending"
    }

    static let minWins = 12
    static let minDaysBetween = 120.0

    /// Победа: great - 3 звезды или серия побед от 3. Сам запрос - после закрытия окна победы (askIfPending).
    static func noteWin(great: Bool) {
        let wins = defaults.integer(forKey: Key.wins) + 1
        defaults.set(wins, forKey: Key.wins)
        guard great, canAsk(wins: wins) else { return }
        defaults.set(true, forKey: Key.pending)
    }

    private static func canAsk(wins: Int) -> Bool {
        #if DEBUG
        if UIDebug.demo { return false }
        #endif
        guard wins >= minWins else { return false }
        let version = Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? ""
        if defaults.string(forKey: Key.lastVersion) == version { return false }
        if let last = defaults.object(forKey: Key.lastAsk) as? Date,
           Date().timeIntervalSince(last) < minDaysBetween * 86400 { return false }
        return true
    }

    /// Окно победы закрыто (на карту, дальше или заново): показать запрос, если он ждет.
    static func askIfPending() {
        guard defaults.bool(forKey: Key.pending) else { return }
        defaults.set(false, forKey: Key.pending)
        defaults.set(Date(), forKey: Key.lastAsk)
        defaults.set(Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "", forKey: Key.lastVersion)
        // даем экрану смениться: окно оценки поверх анимации перехода выглядит как сбой
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.2) {
            guard let scene = UIApplication.shared.connectedScenes
                .compactMap({ $0 as? UIWindowScene })
                .first(where: { $0.activationState == .foregroundActive }) else { return }
            Analytics.log("review_prompt", ["wins": defaults.integer(forKey: Key.wins)])
            SKStoreReviewController.requestReview(in: scene)
        }
    }
}
