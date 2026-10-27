import Foundation
import Combine

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
        Option(code: "ru", name: "Русский")
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

    static func detect() -> String {
        for preferred in Locale.preferredLanguages {
            let base = String(preferred.lowercased().prefix { $0 != "-" && $0 != "_" })
            if options.contains(where: { $0.code == base }) { return base }
        }
        return "en"
    }

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

    static func time(_ seconds: TimeInterval) -> String {
        let s = Int(seconds.rounded(.up))
        if s >= 3600 {
            return String(format: "%d:%02d:%02d", s / 3600, (s % 3600) / 60, s % 60)
        }
        return String(format: "%d:%02d", s / 60, s % 60)
    }
}

func L(_ key: String) -> String { Lang.shared.t(key) }
