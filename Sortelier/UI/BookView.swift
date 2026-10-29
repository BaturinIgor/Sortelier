import SwiftUI

/// Вкладка "Кухня": кулинарная книга, достижения и фоны.
struct KitchenHub: View {
    @EnvironmentObject private var router: Router
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var granted: Granted?
    @State private var frozen: [String]?

    private var sections: [SegmentPicker<KitchenSection>.Item] {
        [.init(id: .book, title: lang.t("kitchen.section.book"), icon: "icon_book"),
         .init(id: .achievements, title: lang.t("kitchen.section.achievements"), icon: "icon_trophy", badge: progress.achievementsClaimable),
         .init(id: .backgrounds, title: lang.t("kitchen.section.backgrounds"), icon: "icon_palette")]
    }

    var body: some View {
        ZStack {
            ScreenScaffold(title: lang.t("tab.kitchen"), back: { router.open(.map) }) {
                SegmentPicker(items: sections, selection: $router.kitchenSection)
                Group {
                    switch router.kitchenSection {
                    case .book: BookContent()
                    case .achievements: AchievementsContent(granted: $granted, frozen: $frozen)
                    case .backgrounds: BackgroundsContent()
                    }
                }
                .id(router.kitchenSection)
                .transition(.opacity)
            }
            if let granted = granted {
                RewardPopup(title: lang.t("common.received"), granted: granted) {
                    self.granted = nil
                    withAnimation(.spring(response: 0.55, dampingFraction: 0.85)) { frozen = nil }
                }
            }
        }
    }
}

/// Кулинарная книга: блюда и продукты биома, открытые карточки и силуэты, медали месяцев.
struct BookContent: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var tab = 0
    @State private var biome = PlayerProgress.shared.mapBiome

    private var dishes: [CatalogDish] { Catalog.shared.dishes(inBiome: biome) }
    /// Продукты цепочки (тесто) показываем рядом с сырьем, служебных нет.
    private var items: [CatalogItem] { Catalog.shared.items(inBiome: biome) }
    private let columns = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        VStack(spacing: 12) {
            SegmentPicker(items: [.init(id: 0, title: lang.t("book.dishes")), .init(id: 1, title: lang.t("book.items")),
                                  .init(id: 2, title: lang.t("book.medals"))],
                          selection: $tab)
            // выбор кухни не исчезает, а гаснет: высота не прыгает при смене вкладки
            biomePicker
                .opacity(tab == 2 ? 0 : 1)
                .allowsHitTesting(tab != 2)
            if tab != 2 {
                Text(lang.t("book.progress", lang.t("biome.\(biome).name"), opened, dishes.count + items.count))
                    .font(Theme.rounded(14, .heavy))
                    .foregroundColor(Color(red: 1.0, green: 0.94, blue: 0.82))
                    .outlined(Theme.woodDark, width: 1)
            }
            Group {
                if tab == 2 {
                    medalsGrid
                } else {
                    LazyVGrid(columns: columns, spacing: 10) {
                        if tab == 0 {
                            ForEach(dishes, id: \.id) { dish in dishCard(dish) }
                        } else {
                            ForEach(items, id: \.id) { item in itemCard(item) }
                        }
                    }
                }
            }
            // вкладка целиком сменяется плавным переходом, карточки не разлетаются по одной
            .id("\(tab)-\(biome)")
            .transition(.opacity)
        }
    }

    private var biomePicker: some View {
        HStack(spacing: 8) {
            // последняя страница - продукты сезонных ивентов (биом 0), она открыта всегда
            ForEach(Array(1...Biomes.playable) + [0], id: \.self) { b in
                let open = b == 0 || progress.isBiomeOpen(b)
                let on = biome == b
                Button {
                    guard open else { return }
                    Audio.shared.play(.button, volume: 0.5)
                    withAnimation(.easeOut(duration: 0.15)) { biome = b }
                } label: {
                    ZStack {
                        SpriteImage(name: Biomes.icon(b), size: b == 0 ? 38 : 46, silhouette: !open)
                        if !open { SpriteImage(name: "icon_lock", size: 22).offset(x: 18, y: 12) }
                    }
                    .frame(maxWidth: .infinity)
                    .frame(height: 54)
                    .background(
                        ZStack {
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .fill(on ? Color(red: 1.0, green: 0.85, blue: 0.5) : Theme.card)
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .strokeBorder(on ? Theme.orange : Theme.chipBorder, lineWidth: on ? 3 : 2)
                        }
                    )
                }
                .buttonStyle(PressScaleStyle())
            }
        }
    }

    private var opened: Int {
        dishes.filter { progress.isDiscovered("dish_" + $0.id) }.count + items.filter { progress.isDiscovered($0.id) }.count
    }

    private func dishCard(_ dish: CatalogDish) -> some View {
        let open = progress.isDiscovered("dish_" + dish.id)
        return VStack(spacing: 6) {
            SpriteImage(name: "dish_" + dish.id, size: 78, silhouette: !open)
            Text(open ? lang.dishName(dish.id) : "???")
                .font(Theme.rounded(14, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(2)
                .multilineTextAlignment(.center)
                .minimumScaleFactor(0.8)
                .frame(minHeight: 36)
            HStack(spacing: 1) {
                ForEach(dish.ingredients, id: \.self) { ing in
                    SpriteImage(name: ing, size: 22, silhouette: !open)
                }
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(card(gold: open))
    }

    private func itemCard(_ item: CatalogItem) -> some View {
        let open = progress.isDiscovered(item.id)
        return VStack(spacing: 6) {
            SpriteImage(name: item.id, size: 64, silhouette: !open)
            Text(open ? lang.itemName(item.id) : "???")
                .font(Theme.rounded(13, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(item.event.map { lang.t("event.season." + $0) } ?? lang.t(kindKey(item)))
                .font(Theme.rounded(11, .semibold))
                .foregroundColor(Theme.brownSoft)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(card(gold: false))
    }

    private func kindKey(_ item: CatalogItem) -> String {
        switch item.kind {
        case "snack": return "book.kind.snack"
        case "raw": return "book.kind.raw"
        case "chain": return "book.kind.chain"
        default: return "book.kind.ingredient"
        }
    }

    /// Медали за месяцы текущего года: полученные золотые, остальные силуэтом, у текущего месяца прогресс.
    private var medalsGrid: some View {
        let year = String(Day.monthKey().prefix(4))
        let current = Day.monthKey()
        let names = monthNames
        return VStack(alignment: .leading, spacing: 12) {
            Text(lang.t("book.medals.hint", ChallengeRewards.medalDaily, ChallengeRewards.medalWeekly))
                .font(Theme.rounded(14, .semibold))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(12)
                .frame(maxWidth: .infinity)
                .background(InsetBackground())
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10),
                                GridItem(.flexible(), spacing: 10)], spacing: 10) {
                ForEach(1...12, id: \.self) { m in
                    let key = year + "-" + String(format: "%02d", m)
                    medalCell(name: names[m - 1], earned: progress.medalClaimed(key), isCurrent: key == current,
                              future: key > current, progress: key == current ? progress.medalProgress(key) : nil)
                }
            }
        }
        .padding(.bottom, 30)
    }

    private var monthNames: [String] {
        let f = DateFormatter()
        f.locale = Locale(identifier: lang.code)
        return f.standaloneMonthSymbols.map { $0.prefix(1).uppercased() + $0.dropFirst() }
    }

    private func medalCell(name: String, earned: Bool, isCurrent: Bool, future: Bool,
                           progress p: (daily: Int, weekly: Int)?) -> some View {
        VStack(spacing: 4) {
            ZStack {
                SpriteImage(name: "icon_medal", size: 52, silhouette: !earned)
                if !earned && !isCurrent {
                    SpriteImage(name: "icon_lock", size: 22).opacity(future ? 0.5 : 0.85).offset(x: 14, y: 14)
                }
            }
            .frame(height: 54)
            Text(name)
                .font(Theme.rounded(13, .black))
                .foregroundColor(earned || isCurrent ? Theme.brown : Theme.brownSoft)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            if let p = p, !earned {
                Text("\(min(p.daily, ChallengeRewards.medalDaily))/\(ChallengeRewards.medalDaily) · \(min(p.weekly, ChallengeRewards.medalWeekly))/\(ChallengeRewards.medalWeekly)")
                    .font(Theme.rounded(11, .black))
                    .foregroundColor(Theme.orange)
                    .monospacedDigit()
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(PaperBackground(radius: 16, highlight: isCurrent))
    }

    private func card(gold: Bool) -> some View {
        PaperBackground(radius: 16, highlight: gold)
    }
}
