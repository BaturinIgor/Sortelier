import Foundation
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
            add(id: "lives", title: lang.t("push.lives.title"), body: lang.t("push.lives.body"), after: seconds)
        }
        if progress.streakAtRisk {
            addAt(hour: 19, dayOffset: 0, id: "streak", title: lang.t("push.streak.title"),
                  body: lang.t("push.streak.body", progress.streakDay))
        }
        addAt(hour: 12, dayOffset: 1, id: "daily", title: lang.t("push.daily.title"), body: lang.t("push.daily.body"))
        add(id: "comeback", title: lang.t("push.comeback.title"), body: lang.t("push.comeback.body"), after: 3 * 86400)
    }

    static func clearDelivered() {
        UNUserNotificationCenter.current().removeAllDeliveredNotifications()
    }

    private static func add(id: String, title: String, body: String, after seconds: TimeInterval) {
        guard seconds > 60 else { return }
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body
        content.sound = .default
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: seconds, repeats: false)
        UNUserNotificationCenter.current().add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
    }

    private static func addAt(hour: Int, dayOffset: Int, id: String, title: String, body: String) {
        let calendar = Calendar.current
        guard let day = calendar.date(byAdding: .day, value: dayOffset, to: Date()),
              let date = calendar.date(bySettingHour: hour, minute: 0, second: 0, of: day),
              date > Date() else { return }
        add(id: id, title: title, body: body, after: date.timeIntervalSinceNow)
    }
}
