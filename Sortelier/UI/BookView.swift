import SwiftUI

/// Вкладка "Кухня": кулинарная книга, достижения и фоны.
struct KitchenHub: View {
    @EnvironmentObject private var router: Router
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var granted: Granted?
    @State private var frozen: [String]?

    private var sections: [SegmentPicker<KitchenSection>.Item] {
        [.init(id: .book, title: lang.t("kitchen.section.book"), icon: "icon_book", badge: progress.bookClaimable),
         .init(id: .achievements, title: lang.t("kitchen.section.achievements"), icon: "icon_trophy", badge: progress.achievementsClaimable),
         .init(id: .backgrounds, title: lang.t("kitchen.section.backgrounds"), icon: "icon_palette")]
    }

    private var tipIcon: String {
        switch router.kitchenSection {
        case .book: return "icon_book"
        case .achievements: return "icon_trophy"
        case .backgrounds: return "icon_palette"
        }
    }

    var body: some View {
        ZStack {
            ScreenScaffold(title: lang.t("tab.kitchen"), back: { router.open(.map) }) {
                SegmentPicker(items: sections, selection: $router.kitchenSection)
                ScreenTip(id: "kitchen." + router.kitchenSection.rawValue, icon: tipIcon).id(router.kitchenSection)
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
    /// Карточки, с которых только что взлетели монеты.
    @State private var popped: [String: Int] = [:]

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
                collectAll
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
                    .overlay(alignment: .topTrailing) {
                        if open && !unpaid(biome: b).isEmpty { BadgeDot().offset(x: 4, y: -4) }
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

    /// Открытые карточки страницы, за которые еще не забраны монеты.
    private func unpaid(biome b: Int) -> [String] {
        let ids = Catalog.shared.dishes(inBiome: b).map { "dish_" + $0.id } + Catalog.shared.items(inBiome: b).map(\.id)
        return ids.filter { progress.bookUnpaid($0) }
    }

    /// Кнопка "забрать все" над сеткой: монеты за все новые карточки этой кухни.
    @ViewBuilder
    private var collectAll: some View {
        let ids = unpaid(biome: biome)
        if !ids.isEmpty {
            let total = ids.reduce(0) { $0 + PlayerProgress.bookCoins($1) }
            Button {
                collect(ids)
            } label: {
                HStack(spacing: 6) {
                    Text(lang.t("book.collect"))
                    CoinIcon(size: 22)
                    Text("+\(total)")
                }
            }
            .buttonStyle(GameButtonStyle(palette: .green, height: 44, fontSize: 17))
            .transition(.opacity.combined(with: .scale(scale: 0.9)))
        } else {
            Text(lang.t("book.coins.hint", PlayerProgress.bookCoins("tomato"), PlayerProgress.bookCoins("dish_x")))
                .font(Theme.rounded(12, .bold))
                .foregroundColor(Color(red: 1.0, green: 0.94, blue: 0.82))
                .outlined(Theme.woodDark, width: 1)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func collect(_ ids: [String]) {
        let shown = ids.filter { progress.bookUnpaid($0) }
        let coins = progress.claimBook(shown)
        guard coins > 0 else { return }
        Audio.shared.play(.coin)
        Haptics.success()
        withAnimation(.easeOut(duration: 0.25)) {
            for id in shown { popped[id] = PlayerProgress.bookCoins(id) }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.0) {
            withAnimation(.easeIn(duration: 0.3)) { for id in shown { popped[id] = nil } }
        }
    }

    /// Монетка на новой карточке и взлетающие "+5" после сбора. Тап по карточке забирает ее монеты.
    private func coinBadge(_ id: String) -> some View {
        ZStack(alignment: .topTrailing) {
            if progress.bookUnpaid(id) {
                Button { collect([id]) } label: {
                    HStack(spacing: 2) {
                        CoinIcon(size: 18)
                        Text("+\(PlayerProgress.bookCoins(id))")
                            .font(Theme.rounded(12, .black))
                            .foregroundColor(.white)
                            .outlined(ButtonPalette.green.dark, width: 1)
                    }
                    .padding(.horizontal, 6)
                    .padding(.vertical, 3)
                    .background(Capsule().fill(Theme.green))
                    .overlay(Capsule().strokeBorder(Color.white, lineWidth: 2))
                }
                .buttonStyle(PressScaleStyle())
                .offset(x: 6, y: -8)
                .transition(.scale.combined(with: .opacity))
            }
            if let n = popped[id] {
                HStack(spacing: 2) {
                    CoinIcon(size: 20)
                    StrokeText(text: "+\(n)", size: 18, color: Theme.gold, stroke: Theme.woodDark, width: 1.5, drop: 2)
                }
                .offset(x: -20, y: -34)
                .transition(.asymmetric(insertion: .move(edge: .bottom).combined(with: .opacity), removal: .opacity))
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
                // у онигири, сока, лимонада и трюфелей три одинаковых ингредиента: id по позиции
                ForEach(Array(dish.ingredients.enumerated()), id: \.offset) { _, ing in
                    SpriteImage(name: ing, size: 22, silhouette: !open)
                }
            }
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(card(gold: open))
        .overlay(alignment: .topTrailing) { coinBadge("dish_" + dish.id) }
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
        .overlay(alignment: .topTrailing) { coinBadge(item.id) }
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
