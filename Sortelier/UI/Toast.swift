import SwiftUI
import UIKit

/// Всплывающее уведомление снизу экрана: плавно появляется и само скрывается.
/// Живет в отдельном окне поверх всего, поэтому видно и над листами, и над уровнем.
final class Toast: ObservableObject {
    static let shared = Toast()

    enum Style { case info, error, success }

    struct Item: Identifiable, Equatable {
        let id = UUID()
        let text: String
        let icon: String?
        let style: Style
    }

    @Published private(set) var current: Item?
    private var hideWork: DispatchWorkItem?

    func show(_ text: String, icon: String? = nil, style: Style = .info, duration: TimeInterval = 2.2) {
        ToastWindow.install()
        hideWork?.cancel()
        withAnimation(.spring(response: 0.35, dampingFraction: 0.8)) {
            current = Item(text: text, icon: icon, style: style)
        }
        let work = DispatchWorkItem { [weak self] in
            withAnimation(.easeInOut(duration: 0.3)) { self?.current = nil }
        }
        hideWork = work
        DispatchQueue.main.asyncAfter(deadline: .now() + duration, execute: work)
    }

    /// Ошибка: не хватает монет, реклама закончилась и т.п.
    static func error(_ text: String) {
        Haptics.warning()
        shared.show(text, icon: "exclamationmark.circle.fill", style: .error)
    }

    static func info(_ text: String, icon: String? = nil) {
        shared.show(text, icon: icon, style: .info)
    }

    static func success(_ text: String, icon: String = "checkmark.circle.fill") {
        shared.show(text, icon: icon, style: .success)
    }
}

struct ToastOverlay: View {
    @ObservedObject private var toast = Toast.shared
    @ObservedObject private var lang = Lang.shared

    var body: some View {
        VStack {
            Spacer()
            if let item = toast.current {
                HStack(spacing: 8) {
                    if item.style == .success {
                        SpriteImage(name: "icon_check", size: 26)
                    } else if let icon = item.icon {
                        if let sprite = GameIcon.sprite(for: icon) {
                            SpriteImage(name: sprite, size: 26)
                        } else {
                            Image(systemName: icon)
                                .font(.system(size: 18, weight: .heavy))
                                .foregroundColor(color(item.style))
                        }
                    }
                    Text(item.text)
                        .font(Theme.rounded(15, .black))
                        .foregroundColor(Color(red: 1.0, green: 0.95, blue: 0.84))
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                .background(
                    ZStack {
                        Capsule().fill(Color.black.opacity(0.35)).offset(y: 4)
                        Capsule().fill(Theme.woodDark.opacity(0.96))
                        Capsule().strokeBorder(item.style == .error ? Theme.red : Theme.woodLight, lineWidth: 2.5)
                    }
                )
                .padding(.horizontal, 24)
                .padding(.bottom, 110)
                .transition(.move(edge: .bottom).combined(with: .opacity))
                .id(item.id)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .environment(\.layoutDirection, lang.direction)
        .allowsHitTesting(false)
    }

    private func color(_ style: Toast.Style) -> Color {
        switch style {
        case .info: return Theme.gold
        case .error: return Color(red: 1.0, green: 0.55, blue: 0.45)
        case .success: return Color(red: 0.55, green: 0.90, blue: 0.55)
        }
    }
}

/// Отдельное прозрачное окно для уведомлений. Касания проходят сквозь него.
enum ToastWindow {
    private static var window: UIWindow?

    static func install() {
        guard window == nil else { return }
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        guard let scene = scenes.first(where: { $0.activationState == .foregroundActive }) ?? scenes.first else { return }
        let w = UIWindow(windowScene: scene)
        let host = NoStatusBarHost(rootView: AnyView(ToastOverlay()))
        host.view.backgroundColor = .clear
        w.rootViewController = host
        w.windowLevel = .alert + 1
        w.backgroundColor = .clear
        w.isUserInteractionEnabled = false
        w.isHidden = false
        window = w
    }
}
