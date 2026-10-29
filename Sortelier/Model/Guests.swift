import Foundation

/// Гости ивентов: покупатели в костюмах темы (ведьмочка, Снегурочка...). Приходят на уровни своего ивента,
/// а когда игрок получил гостя наградой ивента - иногда заходят и на уровни карты.
enum Guests {
    /// Тема ивента -> номер образа покупателя (спрайты customer_<n>_<настроение>, tools/render/customers.py).
    static let looks: [String: Int] = ["halloween": 11, "winter": 12, "sweets": 13, "bbq": 14, "autumn": 15]

    static func sprite(_ id: String, mood: String) -> String { "customer_\(looks[id] ?? 0)_\(mood)" }
}
