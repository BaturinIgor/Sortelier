import SwiftUI
import UIKit

/// Карточка с описанием награды: открывается по тапу на любую плитку награды.
/// Живет в отдельном окне, поэтому видна и поверх листов, и поверх уровня.
final class RewardInfo: ObservableObject {
    static let shared = RewardInfo()
    @Published private(set) var item: RewardItem?

    static func show(_ item: RewardItem) {
        InfoWindow.install()
        InfoWindow.setVisible(true)
        Haptics.light()
        withAnimation(.spring(response: 0.32, dampingFraction: 0.8)) { shared.item = item }
    }

    static func hide() {
        withAnimation(.easeOut(duration: 0.18)) { shared.item = nil }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.22) {
            if shared.item == nil { InfoWindow.setVisible(false) }
        }
    }

    // MARK: Тексты

    static func title(_ item: RewardItem, lang: Lang) -> String {
        switch item {
        case .coins: return lang.t("shop.coins")
        case let .booster(b, _): return lang.t("booster." + b.rawValue)
        case .unlimited: return lang.t("lives.unlimited")
        case .lives: return lang.t("info.lives.title")
        case .energy: return lang.t("info.energy.title")
        case let .chest(k, _): return lang.t("chest.kind." + k.rawValue)
        case let .background(bg): return lang.t("bg." + bg)
        }
    }

    static func amount(_ item: RewardItem) -> String {
        switch item {
        case let .coins(n): return "+\(n)"
        case let .booster(_, n): return "×\(n)"
        case let .unlimited(m): return Lang.duration(minutes: m)
        case let .lives(n): return "+\(n)"
        case let .energy(n): return "+\(n)"
        case let .chest(_, n): return "×\(n)"
        case .background: return ""
        }
    }

    static func text(_ item: RewardItem, lang: Lang) -> String {
        switch item {
        case .coins: return lang.t("info.coins")
        case let .booster(b, _): return lang.t("booster." + b.rawValue + ".text")
        case .unlimited: return lang.t("info.unlimited")
        case .lives: return lang.t("info.lives")
        case .energy: return lang.t("info.energy")
        case .chest: return lang.t("info.chest")
        case .background: return lang.t("info.bg")
        }
    }
}

/// Значок предмета награды: один и тот же в плитках, карточке описания и окнах наград.
struct RewardItemIcon: View {
    let item: RewardItem
    var size: CGFloat = 30

    var body: some View {
        switch item {
        case .coins:
            CoinIcon(size: size * 0.85)
        case let .booster(b, _):
            Image(systemName: b.symbol)
                .font(.system(size: size * 0.66, weight: .bold))
                .foregroundColor(b == .pause ? Theme.blue : Theme.orange)
        case .unlimited:
            ZStack {
                Image(systemName: "heart.fill").font(.system(size: size * 0.8)).foregroundColor(Theme.red)
                Image(systemName: "infinity").font(.system(size: size * 0.36, weight: .heavy)).foregroundColor(.white)
            }
        case .lives:
            Image(systemName: "heart.fill").font(.system(size: size * 0.75)).foregroundColor(Theme.red)
        case .energy:
            Image(systemName: "bolt.fill").font(.system(size: size * 0.75)).foregroundColor(Theme.gold)
        case let .chest(k, _):
            SpriteImage(name: k.sprite, size: size * 1.1)
        case let .background(bg):
            Image(uiImage: Art.image(KitchenStyle.image(bg)))
                .resizable()
                .aspectRatio(contentMode: .fill)
                .frame(width: size * 0.7, height: size)
                .clipShape(RoundedRectangle(cornerRadius: size * 0.15))
        }
    }
}

struct RewardInfoOverlay: View {
    @ObservedObject private var info = RewardInfo.shared
    @ObservedObject private var lang = Lang.shared

    var body: some View {
        ZStack {
            if let item = info.item {
                Color.black.opacity(0.35)
                    .ignoresSafeArea()
                    .onTapGesture { RewardInfo.hide() }
                    .transition(.opacity)
                card(item)
                    .padding(.horizontal, 36)
                    .transition(.scale(scale: 0.85).combined(with: .opacity))
                    .onTapGesture { RewardInfo.hide() }
            }
        }
        .environment(\.layoutDirection, lang.direction)
        .environmentObject(lang)
    }

    private func card(_ item: RewardItem) -> some View {
        VStack(spacing: 10) {
            RewardItemIcon(item: item, size: 64)
                .frame(height: 74)
            VStack(spacing: 2) {
                Text(RewardInfo.title(item, lang: lang))
                    .font(Theme.rounded(20, .heavy))
                    .foregroundColor(Theme.brown)
                    .multilineTextAlignment(.center)
                let amount = RewardInfo.amount(item)
                if !amount.isEmpty {
                    Text(amount).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.orange)
                }
            }
            if case let .chest(kind, _) = item {
                chestDetails(kind)
            }
            Text(RewardInfo.text(item, lang: lang))
                .font(Theme.rounded(14, .semibold))
                .foregroundColor(Theme.brownSoft)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            Text(lang.t("info.close"))
                .font(Theme.rounded(11, .bold))
                .foregroundColor(Theme.brownSoft.opacity(0.7))
                .padding(.top, 2)
        }
        .padding(20)
        .frame(maxWidth: 340)
        .background(RoundedRectangle(cornerRadius: 26, style: .continuous).fill(Theme.cream))
        .overlay(RoundedRectangle(cornerRadius: 26, style: .continuous).stroke(Theme.gold.opacity(0.6), lineWidth: 2))
        .shadow(color: .black.opacity(0.25), radius: 16, y: 8)
    }

    /// Что лежит в сундуке: карточки, редкость, монеты.
    private func chestDetails(_ kind: ChestKind) -> some View {
        HStack(spacing: 14) {
            VStack(spacing: 2) {
                Image(systemName: "rectangle.portrait.on.rectangle.portrait.fill")
                    .font(.system(size: 22, weight: .bold)).foregroundColor(Theme.blue)
                Text(lang.t("info.chest.cards", kind.cards)).font(Theme.rounded(12, .heavy)).foregroundColor(Theme.brown)
            }
            VStack(spacing: 2) {
                HStack(spacing: 1) {
                    ForEach(0..<kind.guaranteed, id: \.self) { _ in
                        Image(systemName: "star.fill").font(.system(size: 12, weight: .bold)).foregroundColor(Theme.gold)
                    }
                }
                .frame(height: 22)
                Text(lang.t("info.chest.rarity")).font(Theme.rounded(12, .heavy)).foregroundColor(Theme.brown)
            }
            VStack(spacing: 2) {
                CoinIcon(size: 22)
                Text("+\(kind.coins)").font(Theme.rounded(12, .heavy)).foregroundColor(Theme.brown)
            }
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 14)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card))
    }
}

/// Окно для карточки описания. Пока карточка скрыта, окно не мешает касаниям.
enum InfoWindow {
    private static var window: UIWindow?

    static func install() {
        guard window == nil else { return }
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        guard let scene = scenes.first(where: { $0.activationState == .foregroundActive }) ?? scenes.first else { return }
        let w = UIWindow(windowScene: scene)
        let host = UIHostingController(rootView: RewardInfoOverlay())
        host.view.backgroundColor = .clear
        w.rootViewController = host
        w.windowLevel = .alert
        w.backgroundColor = .clear
        w.isHidden = true
        window = w
    }

    static func setVisible(_ visible: Bool) {
        window?.isHidden = !visible
    }
}
