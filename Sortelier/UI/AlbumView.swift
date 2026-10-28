import SwiftUI

/// Цвет рамки карточки по звездам.
enum CardStyle {
    static func colors(_ stars: Int) -> [Color] {
        switch stars {
        case 1: return [Color(red: 0.99, green: 0.93, blue: 0.80), Color(red: 0.90, green: 0.76, blue: 0.56)]
        case 2: return [Color(red: 0.86, green: 0.96, blue: 0.80), Color(red: 0.52, green: 0.78, blue: 0.48)]
        case 3: return [Color(red: 0.82, green: 0.92, blue: 1.0), Color(red: 0.42, green: 0.64, blue: 0.94)]
        case 4: return [Color(red: 0.92, green: 0.84, blue: 1.0), Color(red: 0.62, green: 0.42, blue: 0.90)]
        default: return [Color(red: 1.0, green: 0.95, blue: 0.70), Color(red: 1.0, green: 0.70, blue: 0.15)]
        }
    }
}

/// Карточка альбома: рамка по звездам, картинка, название. Без карточки - силуэт.
struct AlbumCardView: View {
    let card: AlbumCard
    var owned = true
    var count = 1
    var isNew = false
    var width: CGFloat = 100
    @EnvironmentObject private var lang: Lang

    var body: some View {
        VStack(spacing: 3) {
            HStack(spacing: 0) {
                ForEach(0..<card.stars, id: \.self) { _ in
                    SpriteImage(name: "icon_star", size: width * 0.13, silhouette: !owned)
                }
            }
            SpriteImage(name: card.id, size: width * 0.66, silhouette: !owned)
            Text(owned ? AlbumCatalog.name(card, lang: lang) : "???")
                .font(Theme.rounded(width * 0.11, .heavy))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.6)
                .frame(height: width * 0.26)
        }
        .padding(.vertical, width * 0.06)
        .padding(.horizontal, width * 0.05)
        .frame(width: width, height: width * 1.32)
        .background(
            RoundedRectangle(cornerRadius: width * 0.12, style: .continuous)
                .fill(owned ? LinearGradient(colors: CardStyle.colors(card.stars), startPoint: .top, endPoint: .bottom)
                            : LinearGradient(colors: [Theme.cream, Theme.cream], startPoint: .top, endPoint: .bottom))
        )
        .overlay(
            RoundedRectangle(cornerRadius: width * 0.12, style: .continuous)
                .strokeBorder(owned ? Theme.paperBorder : Theme.chipBorder, lineWidth: width > 90 ? 3 : 2)
        )
        .overlay(alignment: .topTrailing) {
            if owned && count > 1 {
                CountBadge(count: count - 1).scaleEffect(0.85).offset(x: 6, y: -6)
            }
        }
        .overlay(alignment: .topLeading) {
            if isNew {
                Text(lang.t("album.new"))
                    .font(Theme.rounded(10, .black))
                    .foregroundColor(.white)
                    .outlined(Theme.ribbonDark, width: 1)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.red))
                    .overlay(Capsule().strokeBorder(Theme.ribbonDark, lineWidth: 1.5))
                    .offset(x: -6, y: -6)
            }
        }
    }
}

/// Что лежит в сундуке: карточки, минимальная редкость, монеты. Тап на сундук открывает подробности.
struct ChestContents: View {
    let kind: ChestKind
    @EnvironmentObject private var lang: Lang

    var body: some View {
        HStack(spacing: 5) {
            HStack(spacing: 1) {
                SpriteImage(name: "icon_cards", size: 20)
                Text("×\(kind.cards)").font(Theme.rounded(12, .black)).foregroundColor(Theme.brown)
            }
            HStack(spacing: -1) {
                ForEach(0..<kind.guaranteed, id: \.self) { _ in SpriteImage(name: "icon_star", size: 12) }
            }
            HStack(spacing: 1) {
                CoinIcon(size: 16)
                Text("+\(kind.coins)").font(Theme.rounded(12, .black)).foregroundColor(Theme.brown)
            }
        }
        .lineLimit(1)
        .minimumScaleFactor(0.7)
    }
}

// MARK: - Альбом

struct AlbumScreen: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var router: Router
    @State private var book: Int?
    @State private var opening: ChestOpening?
    @State private var granted: Granted?

    private let columns = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        ZStack {
            ScreenScaffold(title: book.map { lang.t("album.book." + AlbumCatalog.books[$0].key) } ?? lang.t("album.title"),
                           back: {
                               if book != nil { withAnimation(.easeOut(duration: 0.2)) { book = nil } } else { router.open(.map) }
                           }) {
                Group {
                    if let index = book {
                        bookDetail(AlbumCatalog.books[index])
                    } else {
                        VStack(spacing: 14) {
                            summary
                            SectionTitle(title: lang.t("album.chests"), color: Theme.orange)
                            chests
                            starChest
                            SectionTitle(title: lang.t("album.books"))
                            LazyVGrid(columns: columns, spacing: 12) {
                                ForEach(AlbumCatalog.books) { b in bookTile(b) }
                            }
                            grandCard
                        }
                    }
                }
                .id(book ?? -1)
                .transition(.opacity)
            }
            if let granted = granted {
                RewardPopup(title: lang.t("common.received"), granted: granted) { self.granted = nil }
            }
            if let opening = opening {
                ChestOpenView(opening: opening) { self.opening = nil }
                    .transition(.opacity)
            }
        }
    }

    private var summary: some View {
        let owned = progress.albumCardsOwned
        return MetaCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    SpriteImage(name: "icon_cards", size: 40)
                    Text(lang.t("album.progress", owned, AlbumCatalog.cards.count))
                        .font(Theme.rounded(17, .black))
                        .foregroundColor(Theme.brown)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                ProgressBar(value: owned, target: AlbumCatalog.cards.count, color: Theme.gold)
                TimerBadge(text: lang.t("album.season", Lang.time(progress.albumSecondsLeft)))
                Text(lang.t("album.text"))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    @ViewBuilder
    private var chests: some View {
        let kinds = ChestKind.allCases.filter { progress.chestCount($0) > 0 }
        if kinds.isEmpty {
            Text(lang.t("album.chests.empty"))
                .font(Theme.rounded(14, .semibold))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(12)
                .frame(maxWidth: .infinity)
                .background(InsetBackground())
        } else {
            LazyVGrid(columns: [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)], spacing: 14) {
                ForEach(kinds) { kind in chestTile(kind) }
            }
        }
    }

    private func chestTile(_ kind: ChestKind) -> some View {
        VStack(spacing: 6) {
            Button { RewardInfo.show(.chest(kind, progress.chestCount(kind))) } label: {
                SpriteImage(name: kind.sprite, size: 84)
                    .overlay(alignment: .topTrailing) { CountBadge(count: progress.chestCount(kind)).offset(x: 6, y: 2) }
            }
            .buttonStyle(PressScaleStyle())
            Text(lang.t("chest.kind." + kind.rawValue))
                .font(Theme.rounded(14, .black))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            ChestContents(kind: kind)
            Button(lang.t("chest.open")) {
                if let result = progress.openChest(kind) {
                    withAnimation { opening = result }
                }
            }
            .buttonStyle(GameButtonStyle(palette: .green, height: 40, fontSize: 17, radius: 13))
        }
        .padding(.horizontal, 10)
        .padding(.top, 8)
        .padding(.bottom, 6)
        .frame(maxWidth: .infinity)
        .background(PaperBackground(highlight: true))
    }

    private var starChest: some View {
        let stars = progress.album.stars
        let ready = stars >= AlbumCatalog.starChestPrice
        return MetaCard(highlight: ready) {
            HStack(spacing: 12) {
                Button { RewardInfo.show(.chest(.star, 1)) } label: { SpriteImage(name: ChestKind.star.sprite, size: 64) }
                    .buttonStyle(PressScaleStyle())
                VStack(alignment: .leading, spacing: 6) {
                    Text(lang.t("album.stars", stars, AlbumCatalog.starChestPrice))
                        .font(Theme.rounded(15, .black))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("album.stars.text"))
                        .font(Theme.rounded(12, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                    ProgressBar(value: stars, target: AlbumCatalog.starChestPrice, color: Theme.vip, height: 12)
                    if ready {
                        Button(lang.t("album.stars.get")) {
                            if progress.buyStarChest() { Audio.shared.play(.chest) }
                        }
                        .buttonStyle(GameButtonStyle(palette: .purple, height: 38, fontSize: 16, radius: 12))
                    }
                }
            }
        }
    }

    private func bookTile(_ b: AlbumBook) -> some View {
        let owned = progress.bookOwned(b)
        let claimable = progress.canClaimBook(b)
        let cover = b.cards.max { $0.stars < $1.stars } ?? b.cards[0]
        return Button {
            Audio.shared.play(.button, volume: 0.5)
            withAnimation(.easeOut(duration: 0.2)) { book = b.id }
        } label: {
            VStack(spacing: 6) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(LinearGradient(colors: CardStyle.colors(min(5, b.id % 5 + 1)), startPoint: .top, endPoint: .bottom))
                    RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Theme.paperBorder, lineWidth: 2)
                    SpriteImage(name: cover.id, size: 60, silhouette: !progress.hasCard(cover))
                }
                .frame(height: 78)
                .overlay(alignment: .topTrailing) {
                    if progress.bookClaimed(b) { SpriteImage(name: "icon_check", size: 26).offset(x: 6, y: -6) }
                }
                Text(lang.t("album.book." + b.key))
                    .font(Theme.rounded(12, .black))
                    .foregroundColor(Theme.brown)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                    .multilineTextAlignment(.center)
                    .frame(height: 32)
                ProgressBar(value: owned, target: b.cards.count, color: owned == b.cards.count ? Theme.green : Theme.orange, height: 11)
                Text("\(owned)/\(b.cards.count)").font(Theme.rounded(12, .black)).foregroundColor(Theme.brownSoft)
            }
            .padding(8)
            .background(PaperBackground(radius: 16, highlight: claimable))
            .overlay(alignment: .topTrailing) {
                if claimable { BadgeDot().offset(x: 4, y: -4) }
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    private func bookDetail(_ b: AlbumBook) -> some View {
        VStack(spacing: 14) {
            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(b.cards) { card in
                    AlbumCardView(card: card, owned: progress.hasCard(card), count: progress.cardCount(card), width: 104)
                }
            }
            MetaCard(highlight: progress.canClaimBook(b)) {
                VStack(spacing: 10) {
                    Text(lang.t("album.book.reward")).font(Theme.rounded(16, .black)).foregroundColor(Theme.brown)
                    RewardChips(reward: b.reward)
                    if progress.canClaimBook(b) {
                        Button(lang.t("common.claim")) { granted = progress.claimBook(b) }
                            .buttonStyle(GameButtonStyle(palette: .green))
                    } else if progress.bookClaimed(b) {
                        DoneLabel(text: lang.t("challenge.done"))
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    private var grandCard: some View {
        MetaCard(highlight: progress.canClaimAlbumGrand) {
            VStack(spacing: 10) {
                HStack(spacing: 8) {
                    SpriteImage(name: "icon_trophy", size: 38)
                    Text(lang.t("album.grand")).font(Theme.rounded(16, .black)).foregroundColor(Theme.brown)
                        .fixedSize(horizontal: false, vertical: true)
                }
                RewardChips(reward: AlbumCatalog.grand, perRow: 4, tileWidth: 60)
                if progress.canClaimAlbumGrand {
                    Button(lang.t("common.claim")) { granted = progress.claimAlbumGrand() }
                        .buttonStyle(GameButtonStyle(palette: .green))
                }
            }
            .frame(maxWidth: .infinity)
        }
    }
}

// MARK: - Открытие сундука

/// Сундук трясется, открывается, карточки вылетают по одной. Тап показывает следующую.
struct ChestOpenView: View {
    let opening: ChestOpening
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var opened = false
    @State private var shake = false
    @State private var shown = 0

    private var done: Bool { shown >= opening.drops.count }

    var body: some View {
        ZStack {
            Dim(opacity: 0.7)
                .onTapGesture(perform: next)
            VStack(spacing: 18) {
                Ribbon(title: lang.t("chest.kind." + opening.kind.rawValue), size: 22)
                if !done {
                    ZStack {
                        SpriteImage(name: opened ? opening.kind.openSprite : opening.kind.sprite, size: 170)
                            .rotationEffect(.degrees(shake ? 6 : -6))
                            .scaleEffect(opened ? 1.05 : 1)
                        if opened && shown > 0 {
                            let drop = opening.drops[shown - 1]
                            AlbumCardView(card: drop.card, owned: true, isNew: drop.isNew, width: 150)
                                .transition(.asymmetric(insertion: .scale(scale: 0.2).combined(with: .offset(y: 60)), removal: .opacity))
                                .id(drop.id)
                                .offset(y: -40)
                        }
                    }
                    .frame(height: 260)
                    if opened {
                        StrokeText(text: lang.t("chest.cards.left", opening.drops.count - shown), size: 16, color: .white,
                                   stroke: Theme.woodDark, width: 1.5, drop: 2)
                        Text(lang.t("chest.tap"))
                            .font(Theme.rounded(13, .bold))
                            .foregroundColor(.white.opacity(0.75))
                    }
                } else {
                    summary
                }
            }
            .padding(24)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.08).repeatCount(7, autoreverses: true)) { shake = true }
            Haptics.light()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.65) {
                withAnimation(.spring(response: 0.35, dampingFraction: 0.5)) {
                    shake = false
                    opened = true
                }
                Audio.shared.play(.chest)
                Haptics.success()
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { next() }
            }
        }
    }

    private func next() {
        guard opened else { return }
        if done { return }
        withAnimation(.spring(response: 0.4, dampingFraction: 0.65)) { shown += 1 }
        let drop = opening.drops[shown - 1]
        Audio.shared.play(drop.isNew ? .unlock : .pick, volume: drop.card.stars >= 4 ? 1 : 0.7)
        if drop.card.stars >= 4 { Haptics.success() } else { Haptics.light() }
    }

    private var summary: some View {
        VStack(spacing: 14) {
            LazyVGrid(columns: [GridItem(.adaptive(minimum: 72), spacing: 8)], spacing: 8) {
                ForEach(opening.drops) { d in
                    AlbumCardView(card: d.card, owned: true, isNew: d.isNew, width: 72)
                }
            }
            HStack(spacing: 14) {
                Text(lang.t("album.new.count", opening.drops.filter(\.isNew).count))
                    .foregroundColor(Theme.gold)
                HStack(spacing: 3) { CoinIcon(size: 22); Text("+\(opening.coins)") }
                    .foregroundColor(.white)
                if opening.stars > 0 {
                    HStack(spacing: 2) { SpriteImage(name: "icon_star", size: 22); Text("+\(opening.stars)") }
                        .foregroundColor(Color(red: 0.85, green: 0.75, blue: 1.0))
                }
            }
            .font(Theme.rounded(16, .black))
            .outlined(Theme.woodDark, width: 1)
            Button(lang.t("common.ok"), action: close).buttonStyle(GameButtonStyle(palette: .green))
                .frame(maxWidth: 240)
        }
    }
}
