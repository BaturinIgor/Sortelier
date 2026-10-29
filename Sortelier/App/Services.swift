import Foundation
import UIKit
import QuartzCore
import SpriteKit

/// Аналитика. Ключ AppMetrica задается в Info.plist (AppMetricaAPIKey).
/// Пока ключа нет, события только пишутся в лог: SDK подключим вместе с ключом.
enum Analytics {
    static var apiKey: String {
        (Bundle.main.object(forInfoDictionaryKey: "AppMetricaAPIKey") as? String) ?? ""
    }

    static func start() {
        log("app_open")
    }

    static func log(_ event: String, _ params: [String: Any] = [:]) {
        #if DEBUG
        print("[analytics]", event, params)
        #endif
    }
}

/// Реклама за награду. В сборке для SideStore награда выдается без показа.
final class Ads {
    static let shared = Ads()

    var canShow: Bool { PlayerProgress.shared.isVIP || PlayerProgress.shared.adsLeftToday > 0 }

    func showRewarded(placement: String, completion: @escaping (Bool) -> Void) {
        // VIP получает награду сразу, без рекламы и без расхода лимита
        if PlayerProgress.shared.isVIP {
            Analytics.log("ad_reward_vip", ["placement": placement])
            completion(true)
            return
        }
        guard canShow else {
            completion(false)
            return
        }
        PlayerProgress.shared.countAdView()
        Analytics.log("ad_reward", ["placement": placement])
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) {
            completion(true)
        }
    }
}

/// Тактильная отдача.
enum Haptics {
    private static var on: Bool { PlayerProgress.shared.settings.haptics }
    // генераторы создаются один раз: новый генератор на каждый удар заметно тормозит при каскадах
    private static let lightGenerator = UIImpactFeedbackGenerator(style: .light)
    private static let notifyGenerator = UINotificationFeedbackGenerator()
    private static var lastAt: CFTimeInterval = 0

    /// Не чаще 20 раз в секунду: вибрация чаще не ощущается, а время занимает.
    private static func allowed() -> Bool {
        let now = CACurrentMediaTime()
        guard on, now - lastAt > 0.05 else { return false }
        lastAt = now
        return true
    }

    static func light() {
        guard allowed() else { return }
        lightGenerator.impactOccurred()
    }

    static func success() {
        guard allowed() else { return }
        notifyGenerator.notificationOccurred(.success)
    }

    static func warning() {
        guard allowed() else { return }
        notifyGenerator.notificationOccurred(.warning)
    }
}

/// Спрайты из Resources/Sprites.
enum Art {
    private static var images: [String: UIImage] = [:]
    private static var textures: [String: SKTexture] = [:]

    static func image(_ name: String) -> UIImage {
        if let cached = images[name] { return cached }
        let image = UIImage(named: name) ?? UIImage()
        images[name] = image
        return image
    }

    static func texture(_ name: String) -> SKTexture {
        if let cached = textures[name] { return cached }
        let texture = SKTexture(image: image(name))
        textures[name] = texture
        return texture
    }

    /// Мягкая тень под продуктом на полке.
    static let shadow: SKTexture = {
        let size = CGSize(width: 128, height: 40)
        let image = UIGraphicsImageRenderer(size: size).image { ctx in
            let colors = [UIColor.black.withAlphaComponent(0.55).cgColor, UIColor.black.withAlphaComponent(0).cgColor] as CFArray
            guard let gradient = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) else { return }
            let cg = ctx.cgContext
            cg.scaleBy(x: 1, y: size.height / size.width)
            let center = CGPoint(x: size.width / 2, y: size.width / 2)
            cg.drawRadialGradient(gradient, startCenter: center, startRadius: 0, endCenter: center,
                                  endRadius: size.width / 2, options: [])
        }
        return SKTexture(image: image)
    }()

    /// Монетка для подписей на игровом поле.
    static let coin: SKTexture = {
        let size = CGSize(width: 48, height: 48)
        let image = UIGraphicsImageRenderer(size: size).image { ctx in
            let cg = ctx.cgContext
            let rect = CGRect(origin: .zero, size: size)
            cg.setFillColor(UIColor(red: 0.85, green: 0.55, blue: 0.08, alpha: 1).cgColor)
            cg.fillEllipse(in: rect)
            let colors = [UIColor(red: 1.0, green: 0.92, blue: 0.45, alpha: 1).cgColor,
                          UIColor(red: 1.0, green: 0.72, blue: 0.12, alpha: 1).cgColor] as CFArray
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                cg.saveGState()
                cg.addEllipse(in: rect.insetBy(dx: 4, dy: 4))
                cg.clip()
                cg.drawLinearGradient(g, start: CGPoint(x: 10, y: 6), end: CGPoint(x: 38, y: 44), options: [])
                cg.restoreGState()
            }
            cg.setStrokeColor(UIColor(red: 0.93, green: 0.62, blue: 0.1, alpha: 1).cgColor)
            cg.setLineWidth(3)
            cg.strokeEllipse(in: rect.insetBy(dx: 12, dy: 12))
        }
        return SKTexture(image: image)
    }()

    static func sprite(for order: Order) -> String {
        order.kind == .dish ? "dish_" + order.target : order.target
    }

    static func spinFrame(_ dish: String, _ frame: Int) -> String {
        String(format: "dish_%@_spin_%02d", dish, frame)
    }
}
