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
                    if let icon = item.icon {
                        Image(systemName: icon)
                            .font(.system(size: 17, weight: .bold))
                            .foregroundColor(color(item.style))
                    }
                    Text(item.text)
                        .font(Theme.rounded(15, .bold))
                        .foregroundColor(.white)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.horizontal, 18)
                .padding(.vertical, 12)
                .background(Capsule().fill(Theme.brown.opacity(0.94)).shadow(color: .black.opacity(0.25), radius: 10, y: 4))
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
        let host = UIHostingController(rootView: ToastOverlay())
        host.view.backgroundColor = .clear
        w.rootViewController = host
        w.windowLevel = .alert + 1
        w.backgroundColor = .clear
        w.isUserInteractionEnabled = false
        w.isHidden = false
        window = w
    }
}
