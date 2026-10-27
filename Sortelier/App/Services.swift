import Foundation
import UIKit
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

    var canShow: Bool { PlayerProgress.shared.adsLeftToday > 0 }

    func showRewarded(placement: String, completion: @escaping (Bool) -> Void) {
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
    static func light() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }

    static func success() {
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }

    static func warning() {
        UINotificationFeedbackGenerator().notificationOccurred(.warning)
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

    static func sprite(for order: Order) -> String {
        order.kind == .dish ? "dish_" + order.target : order.target
    }

    static func spinFrame(_ dish: String, _ frame: Int) -> String {
        String(format: "dish_%@_spin_%02d", dish, frame)
    }
}
