import SwiftUI

/// Мини-карта сезонного ивента: 20 уровней тропинкой на фоне кухни темы, по краям сладости ивента.
/// Пройденные уровни зеленые, текущий оранжевый и крупнее, остальные закрыты.
struct EventMapScreen: View {
    let event: GameEvent
    let play: (LevelData, PlayMode) -> Void
    let back: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var pulse = false

    private let rowHeight: CGFloat = 92

    private var levels: [LevelData] { EventLevelStore.shared.levels(theme: event.theme) }

    private var done: Int { progress.eventState(event.id).levels }

    /// Сладости и блюдо ивента для украшения тропинки и карточки темы.
    private var treats: [String] {
        Catalog.shared.items.filter { $0.event == event.theme && $0.kind == "snack" }.map(\.id)
    }

    private var special: CatalogDish? { Catalog.shared.dishes.first { $0.event == event.theme } }

    var body: some View {
        ZStack {
            KitchenBackground(style: event.theme, blurred: true)
            GeometryReader { geo in
                ScrollViewReader { proxy in
                    ScrollView(showsIndicators: false) {
                        VStack(spacing: 0) {
                            VStack(spacing: 0) {
                                ForEach(Array(levels.enumerated()).reversed(), id: \.offset) { i, level in
                                    row(i, level: level, width: geo.size.width)
                                        .frame(height: rowHeight)
                                        .id(i)
                                }
                            }
                            .background(trail(width: geo.size.width))
                            .padding(.top, 20)
                            themeCard
                                .padding(.horizontal, 14)
                                .padding(.top, 12)
                                .padding(.bottom, MainTabBar.height + 40)
                        }
                    }
                    .onAppear {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                            proxy.scrollTo(min(done, levels.count - 1), anchor: .center)
                        }
                        withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { pulse = true }
                    }
                }
            }
            .safeAreaInset(edge: .top, spacing: 0) {
                ScreenHeader(title: EventUI.title(event, lang: lang), back: back)
            }
        }
    }

    private func xOffset(_ i: Int, width: CGFloat) -> CGFloat {
        CGFloat(sin(Double(i) * 0.95 + 0.4)) * min(96, width * 0.24)
    }

    private func trail(width: CGFloat) -> some View {
        Canvas { context, size in
            var p = Path()
            for (k, i) in (0..<levels.count).reversed().enumerated() {
                let point = CGPoint(x: size.width / 2 + xOffset(i, width: width), y: CGFloat(k) * rowHeight + rowHeight / 2 - 6)
                if k == 0 { p.move(to: point) } else { p.addLine(to: point) }
            }
            context.stroke(p, with: .color(Color.white.opacity(0.85)),
                           style: StrokeStyle(lineWidth: 10, lineCap: .round, lineJoin: .round, dash: [2, 16]))
        }
    }

    private func row(_ i: Int, level: LevelData, width: CGFloat) -> some View {
        let x = xOffset(i, width: width)
        return ZStack {
            // сладость ивента на свободной стороне тропинки, через два уровня
            if i % 3 == 1, !treats.isEmpty {
                SpriteImage(name: treats[(i / 3) % treats.count], size: 58)
                    .rotationEffect(.degrees(i % 2 == 0 ? -8 : 8))
                    .shadow(color: .black.opacity(0.25), radius: 3, y: 2)
                    .offset(x: x > 0 ? -width * 0.3 : width * 0.3)
            }
            node(i, level: level)
                .offset(x: x)
        }
        .frame(maxWidth: .infinity)
    }

    private func node(_ i: Int, level: LevelData) -> some View {
        let passed = i < done
        let current = i == done
        let palette: ButtonPalette = passed ? .green : (current ? .orange : .gray)
        let size: CGFloat = current ? 74 : 60
        return VStack(spacing: 3) {
            Button {
                guard current else { return }
                play(level, .event(event.id, event.theme, i))
            } label: {
                ZStack {
                    Circle().fill(palette.dark).offset(y: 5)
                    Circle().fill(LinearGradient(colors: [palette.top, palette.bottom], startPoint: .top, endPoint: .bottom))
                    Circle().inset(by: 6).fill(Color.white.opacity(0.18)).frame(height: size * 0.42)
                        .frame(maxHeight: .infinity, alignment: .top).padding(.top, 2)
                    Circle().strokeBorder(level.hard ? Theme.red : palette.dark, lineWidth: level.hard ? 5 : 3.5)
                    if passed {
                        SpriteImage(name: "icon_check", size: 34)
                    } else if current {
                        StrokeText(text: "\(i + 1)", size: 28, weight: .black, color: .white, stroke: palette.dark, width: 2, drop: 2)
                    } else {
                        SpriteImage(name: "icon_lock", size: 28)
                    }
                }
                .frame(width: size, height: size)
                .scaleEffect(current && pulse ? 1.06 : 1)
            }
            .buttonStyle(PressScaleStyle())
            if current {
                Text(lang.t("event.map.play"))
                    .font(Theme.rounded(12, .black))
                    .foregroundColor(.white)
                    .outlined(ButtonPalette.orange.dark, width: 1)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.orange))
            } else if level.hard && !passed {
                Text(lang.t("map.hard"))
                    .font(Theme.rounded(11, .black))
                    .foregroundColor(.white)
                    .outlined(Theme.ribbonDark, width: 1)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.red))
            }
        }
    }

    /// Карточка темы под тропинкой: блюдо ивента, гость и время до конца.
    private var themeCard: some View {
        Panel(padding: 14) {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 8) {
                    Text(lang.t("event.levels", min(done, levels.count), levels.count))
                        .font(Theme.rounded(17, .black))
                        .foregroundColor(Theme.brown)
                    Spacer(minLength: 4)
                    TimerBadge(text: Lang.time(event.left(progress.now)))
                }
                Text(lang.t("event.map.text", SeasonEvent.stamps(mode: .event(event.id, event.theme, 0), isNewLevel: false, stars: 1)))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 10) {
                    if let dish = special {
                        feature(sprite: "dish_" + dish.id, title: lang.dishName(dish.id), caption: lang.t("event.map.dish"))
                    }
                    if Guests.looks[event.theme] != nil {
                        feature(sprite: Guests.sprite(event.theme, mood: "joy"), title: lang.t("guest." + event.theme),
                                caption: lang.t("event.map.guest"))
                    }
                }
            }
        }
    }

    private func feature(sprite: String, title: String, caption: String) -> some View {
        VStack(spacing: 4) {
            SpriteImage(name: sprite, size: 62)
            Text(title)
                .font(Theme.rounded(13, .black))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(caption)
                .font(Theme.rounded(11, .semibold))
                .foregroundColor(Theme.brownSoft)
                .lineLimit(2)
                .multilineTextAlignment(.center)
                .minimumScaleFactor(0.8)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(InsetBackground(radius: 14))
    }
}
