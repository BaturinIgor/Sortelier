import Foundation

/// Удаленный конфиг: баланс и расписание ивентов без новой сборки.
///
/// Файл лежит в репозитории (config/config.json) и раздается как обычный файл с GitHub.
/// Игра читает сохраненную копию сразу при запуске, а свежую скачивает в фоне: при запуске и при возврате
/// в игру, не чаще раза в час. Без сети работает на последней скачанной копии, при самом первом запуске
/// без сети - на копии внутри приложения (Resources/Data/config.json). Любого ключа может не быть:
/// тогда берется значение из кода.
final class RemoteConfig: ObservableObject {
    static let shared = RemoteConfig()

    static let url = URL(string: "https://raw.githubusercontent.com/BaturinIgor/Sortelier/main/config/config.json")!

    @Published private(set) var version = 0
    private var root: [String: Any] = [:]
    private var lastFetch = Date.distantPast
    private var fetching = false

    private static var cacheURL: URL {
        let dir = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask)[0]
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("config.json")
    }

    private init() {
        let bundled = Bundle.main.url(forResource: "config", withExtension: "json").flatMap { Self.parse(try? Data(contentsOf: $0)) }
        let cached = Self.parse(try? Data(contentsOf: Self.cacheURL))
        // сохраненная копия старше встроенной (игру обновили) - берем встроенную
        if let cached = cached, Self.version(of: cached) >= Self.version(of: bundled ?? [:]) {
            apply(cached)
        } else if let bundled = bundled {
            apply(bundled)
        }
    }

    // MARK: - Загрузка

    /// Скачивает свежий конфиг, если давно не проверяли.
    func refresh(force: Bool = false) {
        guard !fetching, force || Date().timeIntervalSince(lastFetch) > 3600 else { return }
        fetching = true
        var request = URLRequest(url: Self.url, cachePolicy: .reloadIgnoringLocalCacheData, timeoutInterval: 12)
        request.setValue("no-cache", forHTTPHeaderField: "Cache-Control")
        URLSession.shared.dataTask(with: request) { [weak self] data, response, _ in
            let ok = (response as? HTTPURLResponse)?.statusCode == 200
            let parsed = ok ? Self.parse(data) : nil
            DispatchQueue.main.async {
                guard let self = self else { return }
                self.fetching = false
                self.lastFetch = Date()
                guard let parsed = parsed, let data = data, Self.version(of: parsed) >= self.version else { return }
                try? data.write(to: Self.cacheURL, options: .atomic)
                if Self.version(of: parsed) != self.version || !NSDictionary(dictionary: parsed).isEqual(to: self.root) {
                    self.apply(parsed)
                    Analytics.log("config_update", ["version": self.version])
                }
            }
        }.resume()
    }

    private func apply(_ dict: [String: Any]) {
        root = dict
        version = Self.version(of: dict)
    }

    private static func parse(_ data: Data?) -> [String: Any]? {
        guard let data = data, let object = try? JSONSerialization.jsonObject(with: data),
              let dict = object as? [String: Any], dict["version"] is NSNumber else { return nil }
        return dict
    }

    private static func version(of dict: [String: Any]) -> Int { (dict["version"] as? NSNumber)?.intValue ?? 0 }

    // MARK: - Значения

    /// Значение по пути через точку: "balance.maxLives".
    func value(_ path: String) -> Any? {
        var node: Any? = root
        for key in path.split(separator: ".") {
            node = (node as? [String: Any])?[String(key)]
        }
        return node
    }

    func int(_ path: String, _ fallback: Int) -> Int { (value(path) as? NSNumber)?.intValue ?? fallback }

    func double(_ path: String, _ fallback: Double) -> Double { (value(path) as? NSNumber)?.doubleValue ?? fallback }

    func bool(_ path: String, _ fallback: Bool) -> Bool { (value(path) as? NSNumber)?.boolValue ?? fallback }

    func ints(_ path: String, _ fallback: [Int]) -> [Int] {
        guard let list = value(path) as? [NSNumber], !list.isEmpty else { return fallback }
        return list.map(\.intValue)
    }

    func strings(_ path: String, _ fallback: [String]) -> [String] {
        guard let list = value(path) as? [String], !list.isEmpty else { return fallback }
        return list
    }

    func list(_ path: String) -> [[String: Any]] { value(path) as? [[String: Any]] ?? [] }

    func dict(_ path: String) -> [String: Any]? { value(path) as? [String: Any] }

    // MARK: - Разбор

    /// Дата из конфига: "2026-10-24" (полночь по времени устройства) или "2026-10-24T18:00".
    static func date(_ any: Any?) -> Date? {
        guard let text = any as? String else { return nil }
        let f = DateFormatter()
        f.locale = Locale(identifier: "en_US_POSIX")
        f.calendar = Calendar(identifier: .gregorian)
        f.timeZone = .current
        for format in ["yyyy-MM-dd'T'HH:mm", "yyyy-MM-dd"] {
            f.dateFormat = format
            if let date = f.date(from: text) { return date }
        }
        return nil
    }

    /// Награда из конфига: {"coins": 100, "boosters": {"hint": 1}, "chests": {"silver": 1}, "unlimitedMinutes": 60,
    /// "background": "winter", "guest": "witch"}.
    static func reward(_ any: Any?) -> Reward? {
        guard let d = any as? [String: Any] else { return nil }
        var boosters: [Booster: Int] = [:]
        for (key, n) in d["boosters"] as? [String: NSNumber] ?? [:] {
            if let b = Booster(rawValue: key) { boosters[b] = n.intValue }
        }
        var chests: [ChestKind: Int] = [:]
        for (key, n) in d["chests"] as? [String: NSNumber] ?? [:] {
            if let k = ChestKind(rawValue: key) { chests[k] = n.intValue }
        }
        var reward = Reward(coins: (d["coins"] as? NSNumber)?.intValue ?? 0, boosters: boosters,
                            unlimitedMinutes: (d["unlimitedMinutes"] as? NSNumber)?.intValue ?? 0,
                            lives: (d["lives"] as? NSNumber)?.intValue ?? 0,
                            background: d["background"] as? String, energy: (d["energy"] as? NSNumber)?.intValue ?? 0,
                            chests: chests)
        reward.guest = d["guest"] as? String
        return reward
    }
}
