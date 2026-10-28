import SwiftUI

/// Кулинарная книга: блюда и продукты биома, открытые карточки и силуэты.
struct BookView: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var tab = 0
    @State private var selectedDish: String?
    @State private var biome = PlayerProgress.shared.mapBiome

    private var dishes: [CatalogDish] { Catalog.shared.dishes(inBiome: biome) }
    /// Продукты цепочки (тесто) показываем рядом с сырьем, служебных нет.
    private var items: [CatalogItem] { Catalog.shared.items(inBiome: biome) }
    private let columns = [GridItem(.adaptive(minimum: 100), spacing: 12)]

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            VStack(spacing: 14) {
                HStack {
                    VStack(alignment: .leading, spacing: 2) {
                        Text(lang.t("book.title"))
                            .font(Theme.rounded(28, .heavy))
                            .foregroundColor(Theme.brown)
                        Text(lang.t("book.progress", lang.t("biome.\(biome).name"), opened, dishes.count + items.count))
                            .font(Theme.rounded(14, .semibold))
                            .foregroundColor(Theme.brownSoft)
                    }
                    Spacer()
                    CircleIconButton(symbol: "xmark") { presentation.wrappedValue.dismiss() }
                }
                HStack(spacing: 0) {
                    tabButton(0, lang.t("book.dishes"))
                    tabButton(1, lang.t("book.items"))
                    tabButton(2, lang.t("book.medals"))
                }
                .background(Capsule().fill(Theme.card))
                // выбор кухни не исчезает, а гаснет: высота шапки не прыгает при смене вкладки
                biomePicker
                    .opacity(tab == 2 ? 0 : 1)
                    .allowsHitTesting(tab != 2)
                ScrollView(showsIndicators: false) {
                    Group {
                        if tab == 2 {
                            medalsGrid
                        } else {
                            LazyVGrid(columns: columns, spacing: 12) {
                                if tab == 0 {
                                    ForEach(dishes, id: \.id) { dish in dishCard(dish) }
                                } else {
                                    ForEach(items, id: \.id) { item in itemCard(item) }
                                }
                            }
                            .padding(.bottom, 30)
                        }
                    }
                    // вкладка целиком сменяется плавным переходом, карточки не разлетаются по одной
                    .id("\(tab)-\(biome)")
                    .transition(.opacity)
                    .frame(maxWidth: .infinity)
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 22)
        }
    }

    private var biomePicker: some View {
        HStack(spacing: 8) {
            ForEach(1...Biomes.playable, id: \.self) { b in
                let open = progress.isBiomeOpen(b)
                Button { if open { withAnimation(.easeOut(duration: 0.15)) { biome = b } } } label: {
                    HStack(spacing: 4) {
                        SpriteImage(name: Biomes.icon(b), size: 26, silhouette: !open)
                        if !open { Image(systemName: "lock.fill").font(.system(size: 11, weight: .bold)) }
                    }
                    .foregroundColor(Theme.brownSoft)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, 6)
                    .background(Capsule().fill(biome == b ? Theme.gold.opacity(0.45) : Theme.card))
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var opened: Int {
        dishes.filter { progress.isDiscovered("dish_" + $0.id) }.count + items.filter { progress.isDiscovered($0.id) }.count
    }

    private func tabButton(_ index: Int, _ title: String) -> some View {
        Button { withAnimation(.easeOut(duration: 0.15)) { tab = index } } label: {
            Text(title)
                .font(Theme.rounded(16, .heavy))
                .foregroundColor(tab == index ? .white : Theme.brownSoft)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 10)
                .background(Capsule().fill(tab == index ? Theme.orange : Color.clear))
        }
        .buttonStyle(.plain)
    }

    private func dishCard(_ dish: CatalogDish) -> some View {
        let open = progress.isDiscovered("dish_" + dish.id)
        return VStack(spacing: 6) {
            SpriteImage(name: "dish_" + dish.id, size: 84, silhouette: !open)
            Text(open ? lang.dishName(dish.id) : "???")
                .font(Theme.rounded(14, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            HStack(spacing: 2) {
                ForEach(dish.ingredients, id: \.self) { ing in
                    SpriteImage(name: ing, size: 24, silhouette: !open)
                }
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity)
        .background(card(gold: open))
    }

    private func itemCard(_ item: CatalogItem) -> some View {
        let open = progress.isDiscovered(item.id)
        return VStack(spacing: 6) {
            SpriteImage(name: item.id, size: 70, silhouette: !open)
            Text(open ? lang.itemName(item.id) : "???")
                .font(Theme.rounded(13, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(lang.t(kindKey(item)))
                .font(Theme.rounded(11, .semibold))
                .foregroundColor(Theme.brownSoft)
        }
        .padding(10)
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
                .font(Theme.rounded(13, .semibold))
                .foregroundColor(Theme.brownSoft)
                .fixedSize(horizontal: false, vertical: true)
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
                Image(systemName: "rosette")
                    .font(.system(size: 34, weight: .bold))
                    .foregroundColor(earned ? Theme.gold : Theme.brown.opacity(0.14))
                if !earned && !isCurrent {
                    Image(systemName: "lock.fill").font(.system(size: 12, weight: .bold))
                        .foregroundColor(Theme.brown.opacity(future ? 0.25 : 0.4))
                        .offset(y: 16)
                }
            }
            .frame(height: 44)
            Text(name)
                .font(Theme.rounded(12, .heavy))
                .foregroundColor(earned || isCurrent ? Theme.brown : Theme.brownSoft)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            if let p = p, !earned {
                Text("\(min(p.daily, ChallengeRewards.medalDaily))/\(ChallengeRewards.medalDaily) · \(min(p.weekly, ChallengeRewards.medalWeekly))/\(ChallengeRewards.medalWeekly)")
                    .font(Theme.rounded(10, .bold))
                    .foregroundColor(Theme.orange)
                    .monospacedDigit()
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 10)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous)
            .fill(isCurrent ? Theme.gold.opacity(0.18) : Theme.card))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
            .stroke(isCurrent ? Theme.gold : Color.clear, lineWidth: 2))
    }

    private func card(gold: Bool) -> some View {
        RoundedRectangle(cornerRadius: 18, style: .continuous)
            .fill(Theme.card)
            .overlay(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .stroke(gold ? Theme.gold : Theme.brown.opacity(0.1), lineWidth: gold ? 2.5 : 1)
            )
            .shadow(color: Theme.brown.opacity(0.12), radius: 6, y: 3)
    }
}
