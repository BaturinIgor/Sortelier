import UIKit
import UserNotifications

/// Локальные напоминания: жизни восстановились, стрик сгорает, новое испытание, давно не заходил.
enum Notifications {
    static func requestIfNeeded() {
        let progress = PlayerProgress.shared
        guard !progress.notificationsAsked else { return }
        progress.markNotificationsAsked()
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, _ in
            Analytics.log("push_permission", ["granted": granted])
        }
    }

    /// Разрешение просим после третьего уровня, когда игрок уже втянулся.
    static func afterWin(level: Int, mode: PlayMode) {
        guard mode == .main, level >= 3 else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.5) { requestIfNeeded() }
    }

    /// Перепланировать напоминания. Вызывается, когда игра уходит в фон.
    static func reschedule() {
        let center = UNUserNotificationCenter.current()
        center.removeAllPendingNotificationRequests()
        let progress = PlayerProgress.shared
        let lang = Lang.shared
        if let next = progress.nextLifeIn {
            let missing = max(0, progress.maxLives - progress.lives - 1)
            let seconds = next + Double(missing) * Balance.lifeRegen
            add(id: "lives", route: .map, title: lang.t("push.lives.title"), body: lang.t("push.lives.body"), after: seconds)
        }
        if progress.streakAtRisk {
            addAt(hour: 19, dayOffset: 0, id: "streak", route: .streak, title: lang.t("push.streak.title"),
                  body: lang.t("push.streak.body", progress.streakDay))
        }
        addAt(hour: 12, dayOffset: 1, id: "daily", route: .challenges, title: lang.t("push.daily.title"), body: lang.t("push.daily.body"))
        add(id: "comeback", route: .map, title: lang.t("push.comeback.title"), body: lang.t("push.comeback.body"), after: 3 * 86400)
        if progress.marketUnlocked {
            // счастливый час: ближайшие окна сегодня и завтра
            let now = Date()
            var windows = HappyHour.windows(on: now)
            if let tomorrow = Calendar.current.date(byAdding: .day, value: 1, to: now) { windows += HappyHour.windows(on: tomorrow) }
            for (i, w) in windows.filter({ $0.start > now }).prefix(3).enumerated() {
                add(id: "happy\(i)", route: .happyHour, title: lang.t("push.happy.title"), body: lang.t("push.happy.body"), after: w.start.timeIntervalSince(now))
            }
            if progress.gardenReady < Garden.bedCount {
                let soonest = (0..<Garden.bedCount).map { progress.gardenLeft($0) }.filter { $0 > 0 }.min() ?? 0
                add(id: "garden", route: .garden, title: lang.t("push.garden.title"), body: lang.t("push.garden.body"), after: soonest)
            }
        }
    }

    static func clearDelivered() {
        UNUserNotificationCenter.current().removeAllDeliveredNotifications()
    }

    private static func add(id: String, route: PushRoute, title: String, body: String, after seconds: TimeInterval) {
        guard seconds > 60 else { return }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        content.userInfo = [PushRoute.key: route.rawValue]
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: seconds, repeats: false)
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
    }

    private static func addAt(hour: Int, dayOffset: Int, id: String, route: PushRoute, title: String, body: String) {
        let calendar = Calendar.current
        guard let day = calendar.date(byAdding: .day, value: dayOffset, to: Date()),
              let date = calendar.date(bySettingHour: hour, minute: 0, second: 0, of: day),
              date > Date() else { return }
        add(id: id, route: route, title: title, body: body, after: date.timeIntervalSinceNow)
    }
}

/// Куда ведет напоминание: экран, где можно сделать то, о чем оно говорит.
enum PushRoute: String {
    /// Жизни восстановились, давно не заходил: карта уровней.
    case map
    /// Стрик сгорает: карта с окном стрика.
    case streak
    /// Новое испытание дня: раздел испытаний во вкладке ивентов.
    case challenges
    /// Счастливый час: ивенты, там карточка счастливого часа и Большой рецепт.
    case happyHour
    /// Урожай поспел: огород поставщика.
    case garden

    static let key = "route"

    /// Напоминания, запланированные до появления маршрутов, узнаем по идентификатору.
    init(identifier: String) {
        switch identifier {
        case "streak": self = .streak
        case "daily": self = .challenges
        case "garden": self = .garden
        case let id where id.hasPrefix("happy"): self = .happyHour
        default: self = .map
        }
    }

    init(request: UNNotificationRequest) {
        if let raw = request.content.userInfo[PushRoute.key] as? String, let route = PushRoute(rawValue: raw) {
            self = route
        } else {
            self = PushRoute(identifier: request.identifier)
        }
    }
}

/// Нажатие на напоминание: запоминаем, куда вести игрока. Сам переход делает RootView,
/// когда уйдет заставка и если игрок не посреди уровня.
final class NotificationHandler: NSObject, UNUserNotificationCenterDelegate {
    static let shared = NotificationHandler()

    func userNotificationCenter(_ center: UNUserNotificationCenter, didReceive response: UNNotificationResponse,
                                withCompletionHandler completionHandler: @escaping () -> Void) {
        if response.actionIdentifier == UNNotificationDefaultActionIdentifier {
            let request = response.notification.request
            let route = PushRoute(request: request)
            DispatchQueue.main.async {
                Analytics.log("push_open", ["id": request.identifier, "route": route.rawValue])
                Router.shared.pendingPush = route
            }
        }
        completionHandler()
    }

    /// Пока игра открыта, напоминания не показываем: игрок и так в игре.
    func userNotificationCenter(_ center: UNUserNotificationCenter, willPresent notification: UNNotification,
                                withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void) {
        completionHandler([])
    }
}

/// Делегат приложения нужен только затем, чтобы назначить обработчик напоминаний до конца запуска:
/// иначе нажатие на напоминание при холодном старте теряется.
final class AppDelegate: NSObject, UIApplicationDelegate {
    func application(_ application: UIApplication,
                     didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil) -> Bool {
        UNUserNotificationCenter.current().delegate = NotificationHandler.shared
        return true
    }
}
