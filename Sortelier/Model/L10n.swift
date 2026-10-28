import Foundation
import Combine
import SwiftUI

/// Язык игры. Тексты лежат в Resources/Strings/<код>.json, английский служит запасным.
final class Lang: ObservableObject {
    static let shared = Lang()

    struct Option: Identifiable, Hashable {
        let code: String
        let name: String
        var id: String { code }
    }

    static let options: [Option] = [
        Option(code: "en", name: "English"),
        Option(code: "ru", name: "Русский"),
        Option(code: "es", name: "Español"),
        Option(code: "pt-BR", name: "Português (Brasil)"),
        Option(code: "de", name: "Deutsch"),
        Option(code: "fr", name: "Français"),
        Option(code: "it", name: "Italiano"),
        Option(code: "tr", name: "Türkçe"),
        Option(code: "pl", name: "Polski"),
        Option(code: "id", name: "Bahasa Indonesia"),
        Option(code: "vi", name: "Tiếng Việt"),
        Option(code: "th", name: "ไทย"),
        Option(code: "hi", name: "हिन्दी"),
        Option(code: "ar", name: "العربية"),
        Option(code: "ja", name: "日本語"),
        Option(code: "ko", name: "한국어"),
        Option(code: "zh-Hans", name: "简体中文"),
        Option(code: "zh-Hant", name: "繁體中文")
    ]

    @Published private(set) var code: String
    private var table: [String: String]
    private let fallback: [String: String]

    private init() {
        fallback = Self.load("en")
        let saved = PlayerProgress.shared.language
        let initial = saved.flatMap { code in Self.options.contains { $0.code == code } ? code : nil } ?? Self.detect()
        code = initial
        table = Self.load(initial)
    }

    var name: String { Self.options.first { $0.code == code }?.name ?? code }

    func set(_ newCode: String) {
        guard newCode != code, Self.options.contains(where: { $0.code == newCode }) else { return }
        table = Self.load(newCode)
        code = newCode
        PlayerProgress.shared.language = newCode
    }

    /// Язык системы: китайский делим на упрощенный и традиционный, португальский - бразильский.
    static func detect() -> String {
        for preferred in Locale.preferredLanguages {
            let lower = preferred.lowercased().replacingOccurrences(of: "_", with: "-")
            let base = String(lower.prefix { $0 != "-" })
            switch base {
            case "zh":
                let traditional = lower.contains("hant") || lower.hasSuffix("-tw") || lower.hasSuffix("-hk") || lower.hasSuffix("-mo")
                return traditional ? "zh-Hant" : "zh-Hans"
            case "pt":
                return "pt-BR"
            default:
                if options.contains(where: { $0.code == base }) { return base }
            }
        }
        return "en"
    }

    /// Арабский пишется справа налево: интерфейс зеркалится.
    var isRTL: Bool { code == "ar" }

    var direction: LayoutDirection { isRTL ? .rightToLeft : .leftToRight }

    private static func load(_ code: String) -> [String: String] {
        guard let url = Bundle.main.url(forResource: code, withExtension: "json"),
              let data = try? Data(contentsOf: url),
              let dict = try? JSONDecoder().decode([String: String].self, from: data) else { return [:] }
        return dict
    }

    func t(_ key: String) -> String {
        table[key] ?? fallback[key] ?? key
    }

    /// Подстановка {0}, {1}... по порядку.
    func t(_ key: String, _ args: CustomStringConvertible...) -> String {
        var text = t(key)
        for (i, arg) in args.enumerated() {
            text = text.replacingOccurrences(of: "{\(i)}", with: arg.description)
        }
        return text
    }

    func itemName(_ id: String) -> String { t("item." + id) }

    func dishName(_ id: String) -> String { t("dish." + id) }

    func orderName(_ order: Order) -> String {
        order.kind == .dish ? dishName(order.target) : itemName(order.target)
    }

    /// "30 мин", "2 ч", "1 ч 30 мин".
    static func duration(minutes: Int) -> String {
        if minutes >= 60 && minutes % 60 == 0 { return shared.t("time.hours", minutes / 60) }
        if minutes >= 60 { return shared.t("time.hm", minutes / 60, minutes % 60) }
        return shared.t("time.minutes", minutes)
    }

    /// Коротко для узких плашек: "30м", "2ч".
    static func durationShort(minutes: Int) -> String {
        minutes >= 60 && minutes % 60 == 0 ? shared.t("time.h.short", minutes / 60) : shared.t("time.m.short", minutes)
    }

    /// Таймер: "4:05", "1:02:03", больше суток - "2 д 05:12:33".
    static func time(_ seconds: TimeInterval) -> String {
        let s = Int(seconds.rounded(.up))
        if s >= 86400 {
            let rest = s % 86400
            return shared.t("time.days.short", s / 86400) + " " + String(format: "%02d:%02d:%02d", rest / 3600, (rest % 3600) / 60, rest % 60)
        }
        if s >= 3600 {
            return String(format: "%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60)
        }
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

func L(_ key: String) -> String { Lang.shared.t(key) }
