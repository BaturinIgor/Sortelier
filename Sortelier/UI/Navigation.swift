import SwiftUI

/// Вкладки нижней панели.
enum AppTab: String, CaseIterable, Identifiable {
    case shop, events, map, album, kitchen

    var id: String { rawValue }

    var icon: String {
        switch self {
        case .shop: return "coins_bag"
        case .events: return "icon_ticket"
        case .map: return "icon_map"
        case .album: return "icon_cards"
        case .kitchen: return "icon_book"
        }
    }
}

/// Разделы вкладки "Ивенты".
enum EventsSection: String, CaseIterable, Identifiable {
    case events, challenges, quests
    var id: String { rawValue }
}

/// Разделы вкладки "Кухня".
enum KitchenSection: String, CaseIterable, Identifiable {
    case book, achievements, backgrounds
    var id: String { rawValue }
}

/// Куда смотрит игрок: вкладка, раздел внутри нее и открытые поверх экраны.
final class Router: ObservableObject {
    static let shared = Router()

    @Published var tab: AppTab = .map
    @Published var eventsSection: EventsSection = .events
    @Published var kitchenSection: KitchenSection = .book
    @Published var settings = false
    @Published var lives = false
    @Published var streak = false
    @Published var merge = false
    @Published var language = false
    /// Сколько окон открыто поверх экрана: нижняя панель затемняется.
    @Published var modalCount = 0

    func open(_ tab: AppTab) {
        guard tab != self.tab else { return }
        Audio.shared.play(.button, volume: 0.5)
        withAnimation(.easeInOut(duration: 0.18)) { self.tab = tab }
    }

    func open(_ section: EventsSection) {
        eventsSection = section
        open(AppTab.events)
    }

    func open(_ section: KitchenSection) {
        kitchenSection = section
        open(AppTab.kitchen)
    }
}

// MARK: - Нижняя панель

struct MainTabBar: View {
    @EnvironmentObject private var router: Router
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    static let height: CGFloat = 70

    var body: some View {
        HStack(spacing: 2) {
            ForEach(AppTab.allCases) { tab in item(tab) }
        }
        .padding(.horizontal, 6)
        .frame(height: Self.height)
        .background(
            WoodBackground()
                .overlay(Rectangle().fill(Theme.woodDark).frame(height: 4), alignment: .top)
                .ignoresSafeArea(edges: .bottom)
                .shadow(color: .black.opacity(0.3), radius: 6, y: -2)
        )
        .overlay(
            Color.black.opacity(router.modalCount > 0 ? 0.5 : 0)
                .ignoresSafeArea(edges: .bottom)
                .allowsHitTesting(router.modalCount > 0)
                .animation(.easeInOut(duration: 0.2), value: router.modalCount > 0)
        )
    }

    private func item(_ tab: AppTab) -> some View {
        let active = router.tab == tab
        return Button { router.open(tab) } label: {
            VStack(spacing: 1) {
                SpriteImage(name: tab.icon, size: active ? 52 : 40)
                    .offset(y: active ? -14 : 0)
                    .padding(.bottom, active ? -14 : 0)
                StrokeText(text: lang.t("tab." + tab.rawValue), size: 11, weight: .heavy, color: active ? .white : Color(red: 1.0, green: 0.91, blue: 0.76),
                           stroke: Theme.woodDark, width: 1.2, drop: 1)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
            .frame(maxWidth: .infinity)
            .frame(height: Self.height - 6)
            .background(
                Group {
                    if active {
                        ZStack {
                            RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.woodDark).offset(y: 3)
                            RoundedRectangle(cornerRadius: 16, style: .continuous)
                                .fill(RadialGradient(colors: [Color(red: 1.0, green: 0.85, blue: 0.45), Color(red: 0.95, green: 0.64, blue: 0.23)],
                                                     center: .init(x: 0.5, y: 0.35), startRadius: 2, endRadius: 50))
                            RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Theme.woodEdge, lineWidth: 3)
                        }
                        .padding(.top, -8)
                    }
                }
            )
            .overlay(alignment: .topTrailing) {
                badge(tab).offset(x: -6, y: active ? -10 : 2)
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    @ViewBuilder
    private func badge(_ tab: AppTab) -> some View {
        switch tab {
        case .shop:
            if !progress.starterBought && progress.isPassed(5) { BadgeDot() }
        case .events:
            if progress.eventsClaimable || (progress.welcomeActive && progress.questsClaimable) || !progress.dailyDone() {
                BadgeDot()
            }
        case .map:
            EmptyView()
        case .album:
            if progress.chestsWaiting > 0 {
                CountBadge(count: progress.chestsWaiting)
            } else if progress.albumClaimable {
                BadgeDot()
            }
        case .kitchen:
            if progress.achievementsClaimable { BadgeDot() }
        }
    }
}

/// Кружок с числом: сундуки к открытию.
struct CountBadge: View {
    let count: Int

    var body: some View {
        Text("\(count)")
            .font(Theme.rounded(12, .black))
            .foregroundColor(.white)
            .padding(.horizontal, 6)
            .frame(minWidth: 22, minHeight: 22)
            .background(Capsule().fill(Theme.red))
            .overlay(Capsule().strokeBorder(Color.white, lineWidth: 2))
    }
}

// MARK: - Экран с шапкой

/// Деревянная шапка: назад, заголовок, монеты. Закреплена и не уезжает при прокрутке.
struct ScreenHeader: View {
    let title: String
    var back: (() -> Void)?
    var coins = true
    @EnvironmentObject private var router: Router

    var body: some View {
        HStack(spacing: 10) {
            if let back = back {
                Button {
                    Audio.shared.play(.button, volume: 0.6)
                    back()
                } label: {
                    ZStack {
                        RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Theme.woodDark).offset(y: 3)
                        RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Color(red: 1.0, green: 0.91, blue: 0.76))
                        RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Theme.woodEdge, lineWidth: 3)
                        BackArrowShape()
                            .stroke(Theme.woodEdge, style: StrokeStyle(lineWidth: 4, lineCap: .round, lineJoin: .round))
                            .frame(width: 14, height: 18)
                            .flipsForRightToLeftLayoutDirection(true)
                    }
                    .frame(width: 42, height: 42)
                }
                .buttonStyle(PressScaleStyle())
            }
            StrokeText(text: title, size: 25, weight: .black, color: Color(red: 1.0, green: 0.96, blue: 0.86),
                       stroke: Theme.woodDark, width: 2, drop: 3, alignment: .leading)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .frame(maxWidth: .infinity, alignment: .leading)
            if coins {
                Button { router.open(.shop) } label: { CoinsPill() }
                    .buttonStyle(PressScaleStyle())
            }
        }
        .padding(.horizontal, 14)
        .padding(.top, 6)
        .padding(.bottom, 12)
        .background(
            WoodBackground()
                .overlay(Rectangle().fill(Theme.woodDark).frame(height: 4), alignment: .bottom)
                .shadow(color: .black.opacity(0.35), radius: 6, y: 3)
                .ignoresSafeArea(edges: .top)
        )
    }
}

/// Экран меню: размытый фон кухни, закрепленная шапка, прокрутка, отступ под нижнюю панель.
struct ScreenScaffold<Content: View>: View {
    let title: String
    var back: (() -> Void)?
    var coins = true
    var tabBar = true
    @ViewBuilder var content: Content

    var body: some View {
        ZStack {
            KitchenBackground(blurred: true)
            ScrollView(showsIndicators: false) {
                VStack(spacing: 14) { content }
                    .padding(.horizontal, 14)
                    .padding(.top, 14)
                    .padding(.bottom, tabBar ? MainTabBar.height + 40 : 30)
            }
            .safeAreaInset(edge: .top, spacing: 0) {
                ScreenHeader(title: title, back: back, coins: coins)
            }
        }
    }
}

// MARK: - Переключатель разделов

/// Разделы внутри вкладки: бумажные кнопки на деревянной полке, выбранная оранжевая.
struct SegmentPicker<ID: Hashable>: View {
    struct Item {
        let id: ID
        let title: String
        var icon: String?
        var badge = false
    }

    let items: [Item]
    @Binding var selection: ID

    var body: some View {
        HStack(spacing: 6) {
            ForEach(items.indices, id: \.self) { i in
                let item = items[i]
                let on = item.id == selection
                Button {
                    Audio.shared.play(.button, volume: 0.5)
                    withAnimation(.easeInOut(duration: 0.18)) { selection = item.id }
                } label: {
                    HStack(spacing: 4) {
                        if let icon = item.icon { SpriteImage(name: icon, size: 26) }
                        Text(item.title)
                            .font(Theme.rounded(14, .black))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                    }
                    .foregroundColor(on ? .white : Theme.brown)
                    .modifier(Outline(color: on ? ButtonPalette.orange.dark : .clear, width: 1))
                    .padding(.horizontal, 6)
                    .frame(maxWidth: .infinity)
                    .frame(height: 40)
                    .background(
                        ZStack {
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .fill(on ? LinearGradient(colors: [ButtonPalette.orange.top, ButtonPalette.orange.bottom], startPoint: .top, endPoint: .bottom)
                                         : LinearGradient(colors: [Theme.card, Theme.cream], startPoint: .top, endPoint: .bottom))
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .strokeBorder(on ? ButtonPalette.orange.dark : Theme.chipBorder, lineWidth: 2.5)
                        }
                    )
                    .overlay(alignment: .topTrailing) {
                        if item.badge { BadgeDot().offset(x: 4, y: -4) }
                    }
                }
                .buttonStyle(PressScaleStyle())
            }
        }
        .padding(6)
        .background(
            ZStack {
                RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.woodDark).offset(y: 3)
                RoundedRectangle(cornerRadius: 16, style: .continuous).fill(LinearGradient(colors: [Theme.woodLight, Theme.woodMid],
                                                                                          startPoint: .top, endPoint: .bottom))
                RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Theme.woodDark, lineWidth: 2.5)
            }
        )
    }
}

// MARK: - Горизонтальная лента ступеней

/// Лента наград по ступеням: карточки одной ширины, следующая видна наполовину,
/// при открытии лента сама прокручивается к текущей ступени.
struct StepTrack<Cell: View>: View {
    let count: Int
    let current: Int
    var cellWidth: CGFloat = 104
    @ViewBuilder let cell: (Int) -> Cell

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                HStack(alignment: .top, spacing: 10) {
                    ForEach(0..<count, id: \.self) { i in
                        cell(i).frame(width: cellWidth).id(i)
                    }
                }
                .padding(.horizontal, 4)
                .padding(.vertical, 8)
            }
            .onAppear {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.15) {
                    withAnimation(.easeOut(duration: 0.35)) { proxy.scrollTo(min(max(0, current), max(0, count - 1)), anchor: .center) }
                }
            }
        }
    }
}
