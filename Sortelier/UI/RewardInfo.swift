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
        case let .guest(g): return lang.t("guest." + g)
        case let .market(b, _): return lang.t("m3.booster." + b.rawValue)
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
        case let .market(_, n): return "×\(n)"
        case .background, .guest: return ""
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
        case .guest: return lang.t("info.guest")
        case let .market(b, _): return lang.t("m3.booster." + b.rawValue + ".text")
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
            CoinIcon(size: size * 0.9)
        case let .booster(b, _):
            SpriteImage(name: b.icon, size: size)
        case .unlimited:
            SpriteImage(name: "icon_unlimited", size: size)
        case .lives:
            SpriteImage(name: "icon_heart", size: size)
        case .energy:
            SpriteImage(name: "icon_energy", size: size)
        case let .chest(k, _):
            SpriteImage(name: k.sprite, size: size * 1.15)
        case let .background(bg):
            Image(uiImage: Art.image(KitchenStyle.image(bg)))
                .resizable()
                .aspectRatio(contentMode: .fill)
                .frame(width: size * 0.72, height: size)
                .clipShape(RoundedRectangle(cornerRadius: size * 0.15))
                .overlay(RoundedRectangle(cornerRadius: size * 0.15).strokeBorder(Theme.paperBorder, lineWidth: 1.5))
        case let .guest(g):
            SpriteImage(name: Guests.sprite(g, mood: "joy"), size: size * 1.1)
        case let .market(b, _):
            SpriteImage(name: b.icon, size: size)
        }
    }
}

struct RewardInfoOverlay: View {
    @ObservedObject private var info = RewardInfo.shared
    @ObservedObject private var lang = Lang.shared

    var body: some View {
        ZStack {
            if let item = info.item {
                Color.black.opacity(0.4)
                    .ignoresSafeArea()
                    .onTapGesture { RewardInfo.hide() }
                    .transition(.opacity)
                PopupCard(title: RewardInfo.title(item, lang: lang), close: { RewardInfo.hide() }, maxWidth: 320) {
                    card(item)
                }
                .transition(.scale(scale: 0.85).combined(with: .opacity))
                .onTapGesture { RewardInfo.hide() }
            }
        }
        .environment(\.layoutDirection, lang.direction)
        .environmentObject(lang)
    }

    private func card(_ item: RewardItem) -> some View {
        VStack(spacing: 12) {
            RewardItemIcon(item: item, size: 84)
                .frame(height: 92)
            let amount = RewardInfo.amount(item)
            if !amount.isEmpty {
                StrokeText(text: amount, size: 24, color: .white, stroke: Theme.woodDark, width: 1.8, drop: 2)
            }
            if case let .chest(kind, _) = item {
                chestDetails(kind)
            }
            Text(RewardInfo.text(item, lang: lang))
                .font(Theme.rounded(15, .semibold))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
            Text(lang.t("info.close"))
                .font(Theme.rounded(12, .bold))
                .foregroundColor(Theme.brownSoft.opacity(0.8))
        }
        .frame(maxWidth: .infinity)
    }

    /// Что лежит в сундуке: карточки, редкость, монеты.
    private func chestDetails(_ kind: ChestKind) -> some View {
        HStack(spacing: 8) {
            detail {
                SpriteImage(name: "icon_cards", size: 34)
            } text: {
                lang.t("info.chest.cards", kind.cards)
            }
            detail {
                HStack(spacing: 0) {
                    ForEach(0..<kind.guaranteed, id: \.self) { _ in SpriteImage(name: "icon_star", size: 16) }
                }
                .frame(height: 34)
            } text: {
                lang.t("info.chest.rarity")
            }
            detail {
                CoinIcon(size: 30).frame(height: 34)
            } text: {
                "+\(kind.coins)"
            }
        }
    }

    private func detail<Icon: View>(@ViewBuilder icon: () -> Icon, text: () -> String) -> some View {
        VStack(spacing: 2) {
            icon()
            Text(text()).font(Theme.rounded(12, .heavy)).foregroundColor(Theme.brown).lineLimit(1).minimumScaleFactor(0.7)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 8)
        .background(InsetBackground(radius: 12))
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
        let host = NoStatusBarHost(rootView: AnyView(RewardInfoOverlay()))
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

/// Окна поверх игры не должны показывать системную строку состояния.
final class NoStatusBarHost: UIHostingController<AnyView> {
    override var prefersStatusBarHidden: Bool { true }
}

