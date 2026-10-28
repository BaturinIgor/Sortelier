import SwiftUI

enum Theme {
    static let cream = Color(red: 1.0, green: 0.95, blue: 0.86)
    static let peach = Color(red: 0.99, green: 0.82, blue: 0.62)
    static let brown = Color(red: 0.36, green: 0.22, blue: 0.13)
    static let brownSoft = Color(red: 0.55, green: 0.38, blue: 0.25)
    static let orange = Color(red: 0.95, green: 0.50, blue: 0.18)
    static let red = Color(red: 0.88, green: 0.30, blue: 0.25)
    static let green = Color(red: 0.30, green: 0.66, blue: 0.38)
    static let gold = Color(red: 1.0, green: 0.76, blue: 0.18)
    static let card = Color(red: 1.0, green: 0.985, blue: 0.95)

    static var background: LinearGradient {
        LinearGradient(colors: [Color(red: 1.0, green: 0.95, blue: 0.86), Color(red: 0.98, green: 0.80, blue: 0.60)],
                       startPoint: .top, endPoint: .bottom)
    }

    static func rounded(_ size: CGFloat, _ weight: Font.Weight = .bold) -> Font {
        .system(size: size, weight: weight, design: .rounded)
    }
}

/// Фон кухни биома: рендер из tools/render/environment.py.
struct KitchenBackground: View {
    /// Светлая вуаль поверх, чтобы спокойнее читался интерфейс.
    var veil: Double = 0
    /// Фон темы вместо выбранного игроком: уровни ивента.
    var style: String?
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        GeometryReader { geo in
            Image(uiImage: Art.image(KitchenStyle.image(style ?? progress.background)))
                .resizable()
                .scaledToFill()
                .frame(width: geo.size.width, height: geo.size.height)
                .clipped()
                .overlay(Color.white.opacity(veil))
        }
        .ignoresSafeArea()
    }
}

/// Карточка с мягкой тенью.
struct Panel<Content: View>: View {
    var padding: CGFloat = 16
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(padding)
            .background(
                RoundedRectangle(cornerRadius: 24, style: .continuous)
                    .fill(Theme.card)
                    .shadow(color: Theme.brown.opacity(0.18), radius: 14, x: 0, y: 6)
            )
    }
}

struct BigButtonStyle: ButtonStyle {
    var color: Color = Theme.orange

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(Theme.rounded(19))
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(color)
                    .shadow(color: color.opacity(0.45), radius: 0, x: 0, y: configuration.isPressed ? 1 : 4)
            )
            .offset(y: configuration.isPressed ? 3 : 0)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
            .onChange(of: configuration.isPressed) { pressed in
                if pressed { Audio.shared.play(.button, volume: 0.6) }
            }
    }
}

struct CircleIconButton: View {
    let symbol: String
    var size: CGFloat = 44
    let action: () -> Void

    var body: some View {
        Button {
            Audio.shared.play(.button, volume: 0.6)
            action()
        } label: {
            Image(systemName: symbol)
                .font(.system(size: size * 0.42, weight: .bold))
                .foregroundColor(Theme.brown)
                .frame(width: size, height: size)
                .background(Circle().fill(Theme.card).shadow(color: Theme.brown.opacity(0.2), radius: 4, y: 2))
        }
        .buttonStyle(.plain)
    }
}

struct CoinIcon: View {
    var size: CGFloat = 22

    var body: some View {
        ZStack {
            Circle().fill(Theme.gold)
            Circle().stroke(Color(red: 0.85, green: 0.55, blue: 0.05), lineWidth: size * 0.1)
            Text("S")
                .font(.system(size: size * 0.55, weight: .heavy, design: .rounded))
                .foregroundColor(Color(red: 0.75, green: 0.45, blue: 0.0))
        }
        .frame(width: size, height: size)
    }
}

struct Pill<Leading: View>: View {
    let text: String
    @ViewBuilder var leading: Leading

    var body: some View {
        HStack(spacing: 6) {
            leading
            Text(text)
                .font(Theme.rounded(16))
                .monospacedDigit()
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .padding(.leading, 6)
        .padding(.trailing, 12)
        .frame(height: 36)
        .background(Capsule().fill(Theme.card).shadow(color: Theme.brown.opacity(0.18), radius: 4, y: 2))
    }
}

struct CoinsPill: View {
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        Pill(text: "\(progress.coins)") { CoinIcon(size: 24) }
    }
}

struct LivesPill: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        Pill(text: label) {
            ZStack {
                Image(systemName: "heart.fill")
                    .font(.system(size: 22))
                    .foregroundColor(Theme.red)
                if !progress.unlimitedLives {
                    Text("\(progress.lives)")
                        .font(.system(size: 11, weight: .heavy, design: .rounded))
                        .foregroundColor(.white)
                }
            }
        }
    }

    private var label: String {
        if let left = progress.unlimitedLeft { return "∞ " + Lang.time(left) }
        if let next = progress.nextLifeIn { return Lang.time(next) }
        return lang.t("lives.full")
    }
}

struct StarsRow: View {
    let count: Int
    var size: CGFloat = 16
    var spacing: CGFloat = 2

    var body: some View {
        HStack(spacing: spacing) {
            ForEach(0..<3, id: \.self) { i in
                Image(systemName: "star.fill")
                    .font(.system(size: size))
                    .foregroundColor(i < count ? Theme.gold : Theme.brown.opacity(0.18))
                    .shadow(color: i < count ? Theme.orange.opacity(0.4) : .clear, radius: 1, y: 1)
            }
        }
    }
}

struct SpriteImage: View {
    let name: String
    var size: CGFloat = 60
    var silhouette = false

    var body: some View {
        Group {
            if silhouette {
                Image(uiImage: Art.image(name))
                    .renderingMode(.template)
                    .resizable()
                    .foregroundColor(Theme.brown.opacity(0.18))
            } else {
                Image(uiImage: Art.image(name))
                    .resizable()
            }
        }
        .aspectRatio(contentMode: .fit)
        .frame(width: size, height: size)
    }
}

/// Затемнение под всплывающими окнами.
struct Dim: View {
    var body: some View {
        Color.black.opacity(0.45).ignoresSafeArea()
    }
}
