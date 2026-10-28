import SwiftUI

/// Кулинарная книга: блюда и продукты биома, открытые карточки и силуэты.
struct BookView: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var tab = 0
    @State private var selectedDish: String?

    private let dishes = Catalog.shared.dishes(inBiome: 1)
    private let items = Catalog.shared.items(inBiome: 1)
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
                        Text(lang.t("book.progress", lang.t("biome.1.name"), opened, dishes.count + items.count))
                            .font(Theme.rounded(14, .semibold))
                            .foregroundColor(Theme.brownSoft)
                    }
                    Spacer()
                    CircleIconButton(symbol: "xmark") { presentation.wrappedValue.dismiss() }
                }
                HStack(spacing: 0) {
                    tabButton(0, lang.t("book.dishes"))
                    tabButton(1, lang.t("book.items"))
                    tabButton(2, lang.t("book.rare"))
                }
                .background(Capsule().fill(Theme.card))
                ScrollView(showsIndicators: false) {
                    if tab == 2 { medalsRow }
                    LazyVGrid(columns: columns, spacing: 12) {
                        if tab == 0 {
                            ForEach(dishes, id: \.id) { dish in dishCard(dish) }
                        } else if tab == 1 {
                            ForEach(items, id: \.id) { item in itemCard(item) }
                        } else {
                            ForEach(RareCards.all, id: \.self) { id in rareCard(id) }
                        }
                    }
                    .padding(.bottom, 30)
                }
            }
            .padding(.horizontal, 18)
            .padding(.top, 22)
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
            Text(lang.t(item.kind == "snack" ? "book.kind.snack" : "book.kind.ingredient"))
                .font(Theme.rounded(11, .semibold))
                .foregroundColor(Theme.brownSoft)
        }
        .padding(10)
        .frame(maxWidth: .infinity)
        .background(card(gold: false))
    }

    private func rareCard(_ id: String) -> some View {
        let open = progress.hasRare(id)
        let name = Catalog.shared.dish(id) != nil ? lang.dishName(id) : lang.itemName(id)
        return VStack(spacing: 6) {
            if open {
                GoldSprite(name: RareCards.sprite(id), size: 80)
            } else {
                SpriteImage(name: RareCards.sprite(id), size: 80, silhouette: true)
            }
            Text(open ? lang.t("book.rare.name", name) : "???")
                .font(Theme.rounded(13, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        }
        .padding(10)
        .frame(maxWidth: .infinity)
        .background(card(gold: open))
    }

    @ViewBuilder
    private var medalsRow: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(lang.t("book.rare.hint"))
                .font(Theme.rounded(13, .semibold))
                .foregroundColor(Theme.brownSoft)
                .fixedSize(horizontal: false, vertical: true)
            if !progress.medals.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 10) {
                        ForEach(progress.medals, id: \.self) { month in
                            VStack(spacing: 2) {
                                Image(systemName: "rosette").font(.system(size: 30)).foregroundColor(Theme.gold)
                                Text(month).font(Theme.rounded(11, .bold)).foregroundColor(Theme.brownSoft)
                            }
                            .padding(8)
                            .background(RoundedRectangle(cornerRadius: 12).fill(Theme.card))
                        }
                    }
                }
            }
        }
        .padding(.bottom, 10)
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
