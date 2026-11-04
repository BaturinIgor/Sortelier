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

/// Цвет обложки книги альбома.
enum BookStyle {
    private static let palette: [(Double, Double, Double)] = [
        (0.93, 0.42, 0.30), (0.95, 0.60, 0.22), (0.96, 0.74, 0.26), (0.92, 0.50, 0.66),
        (0.42, 0.70, 0.42), (0.86, 0.32, 0.36), (0.55, 0.68, 0.33), (0.30, 0.62, 0.50),
        (0.42, 0.58, 0.90), (0.28, 0.66, 0.62), (0.68, 0.50, 0.86)
    ]

    static func colors(_ i: Int) -> [Color] {
        let c = palette[i % palette.count]
        return [Color(red: min(1, c.0 + 0.12), green: min(1, c.1 + 0.12), blue: min(1, c.2 + 0.12)),
                Color(red: c.0 * 0.8, green: c.1 * 0.8, blue: c.2 * 0.8)]
    }
}

/// Карточка альбома: рамка по звездам, окно с картинкой, звезды на плашке, название. Без карточки - силуэт.
struct AlbumCardView: View {
    let card: AlbumCard
    var owned = true
    var count = 1
    var isNew = false
    var width: CGFloat = 100
    @EnvironmentObject private var lang: Lang

    var body: some View {
        let colors = CardStyle.colors(card.stars)
        let shape = RoundedRectangle(cornerRadius: width * 0.12, style: .continuous)
        let window = RoundedRectangle(cornerRadius: width * 0.09, style: .continuous)
        VStack(spacing: width * 0.05) {
            ZStack {
                window.fill(owned
                            ? RadialGradient(colors: [Color.white.opacity(0.95), colors[0]], center: .center,
                                             startRadius: 2, endRadius: width * 0.5)
                            : RadialGradient(colors: [Theme.cream, Theme.cream], center: .center, startRadius: 0, endRadius: 1))
                window.strokeBorder(owned ? colors[1].opacity(0.9) : Theme.chipBorder.opacity(0.7), lineWidth: max(1.5, width * 0.02))
                SpriteImage(name: card.id, size: width * 0.6, silhouette: !owned)
                    .offset(y: width * 0.03)
            }
            .frame(height: width * 0.8)
            .overlay(alignment: .top) {
                HStack(spacing: 0) {
                    ForEach(0..<card.stars, id: \.self) { _ in
                        SpriteImage(name: "icon_star", size: width * 0.12, silhouette: !owned)
                    }
                }
                .padding(.horizontal, width * 0.04)
                .padding(.vertical, width * 0.012)
                .background(Capsule().fill(Theme.woodDark.opacity(owned ? 0.72 : 0.2)))
                .offset(y: -width * 0.05)
            }
            Text(owned ? AlbumCatalog.name(card, lang: lang) : "???")
                .font(Theme.rounded(width * 0.11, .heavy))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.6)
                .frame(height: width * 0.24)
        }
        .padding(width * 0.07)
        .frame(width: width, height: width * 1.32)
        .background(
            shape.fill(LinearGradient(colors: owned ? colors : [Theme.card, Theme.cream], startPoint: .top, endPoint: .bottom))
        )
        .overlay(
            Group {
                if owned && card.stars >= 4 {
                    // редкие карточки с бликом
                    LinearGradient(colors: [.clear, Color.white.opacity(0.4), .clear], startPoint: .topLeading, endPoint: .bottomTrailing)
                        .clipShape(shape)
                        .allowsHitTesting(false)
                }
            }
        )
        .overlay(shape.strokeBorder(owned ? Theme.paperBorder : Theme.chipBorder, lineWidth: width > 90 ? 3 : 2))
        .overlay(alignment: .topTrailing) {
            if owned && count > 1 {
                CountBadge(count: count - 1).scaleEffect(0.85).offset(x: 6, y: -6)
            }
        }
        .overlay(alignment: .topLeading) {
            if isNew {
                Text(lang.t("album.new"))
                    .font(Theme.rounded(max(10, width * 0.08), .black))
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
                            chestShelf
                            SectionTitle(title: lang.t("album.books"))
                            LazyVGrid(columns: columns, spacing: 14) {
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
        }
    }

    // MARK: Сезон

    private var summary: some View {
        let owned = progress.albumCardsOwned
        let total = AlbumCatalog.cards.count
        return MetaCard {
            HStack(spacing: 14) {
                AlbumRing(value: owned, target: total) {
                    VStack(spacing: 0) {
                        SpriteImage(name: "icon_cards", size: 30)
                        Text("\(owned)")
                            .font(Theme.rounded(15, .black))
                            .foregroundColor(Theme.brown)
                    }
                }
                VStack(alignment: .leading, spacing: 7) {
                    Text(lang.t("album.progress", owned, total))
                        .font(Theme.rounded(16, .black))
                        .foregroundColor(Theme.brown)
                        .fixedSize(horizontal: false, vertical: true)
                    TimerBadge(text: lang.t("album.season", Lang.time(progress.albumSecondsLeft)))
                    Text(lang.t("album.text"))
                        .font(Theme.rounded(12, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer(minLength: 0)
            }
        }
    }

    // MARK: Сундуки

    /// Все четыре сундука на деревянной полке: есть в запасе - яркий со счетчиком, нет - бледный.
    private var chestShelf: some View {
        MetaCard(highlight: progress.chestsWaiting > 0) {
            VStack(spacing: 12) {
                VStack(spacing: 0) {
                    HStack(alignment: .bottom, spacing: 4) {
                        ForEach(ChestKind.allCases) { kind in chestImage(kind).frame(maxWidth: .infinity) }
                    }
                    plank
                        .padding(.top, -12)
                        .zIndex(-1)
                    HStack(alignment: .top, spacing: 6) {
                        ForEach(ChestKind.allCases) { kind in chestLabel(kind).frame(maxWidth: .infinity) }
                    }
                    .padding(.top, 8)
                }
                if progress.chestsWaiting == 0 {
                    Text(lang.t("album.chests.empty"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                        .frame(maxWidth: .infinity)
                }
                Rectangle()
                    .fill(Theme.chipBorder.opacity(0.45))
                    .frame(height: 2)
                starChestRow
            }
        }
    }

    private var plank: some View {
        let shape = RoundedRectangle(cornerRadius: 5, style: .continuous)
        return WoodBackground()
            .frame(height: 14)
            .clipShape(shape)
            .overlay(shape.strokeBorder(Theme.woodDark, lineWidth: 2))
            .shadow(color: Theme.woodDark.opacity(0.4), radius: 0, y: 3)
    }

    private func chestImage(_ kind: ChestKind) -> some View {
        let n = progress.chestCount(kind)
        return Button {
            if n > 0 { ChestOpener.present(kind) } else { RewardInfo.show(.chest(kind, 1)) }
        } label: {
            ZStack {
                if n > 0 {
                    Circle()
                        .fill(RadialGradient(colors: [Theme.gold.opacity(0.6), .clear], center: .center, startRadius: 4, endRadius: 40))
                        .frame(width: 80, height: 80)
                }
                SpriteImage(name: kind.sprite, size: 66)
                    .saturation(n > 0 ? 1 : 0)
                    .opacity(n > 0 ? 1 : 0.45)
            }
            .frame(height: 76)
            .overlay(alignment: .topTrailing) {
                if n > 0 { CountBadge(count: n).offset(x: 2, y: 2) }
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    private func chestLabel(_ kind: ChestKind) -> some View {
        let n = progress.chestCount(kind)
        return VStack(spacing: 5) {
            Text(lang.t("chest.kind." + kind.rawValue))
                .font(Theme.rounded(11, .black))
                .foregroundColor(n > 0 ? Theme.brown : Theme.brownSoft)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
                .frame(height: 28)
            if n > 0 {
                Button(lang.t("chest.open")) { ChestOpener.present(kind) }
                    .buttonStyle(GameButtonStyle(palette: .green, height: 30, fontSize: 13, radius: 10))
            } else {
                HStack(spacing: 1) {
                    SpriteImage(name: "icon_cards", size: 16)
                    Text("×\(kind.cards)").font(Theme.rounded(11, .black)).foregroundColor(Theme.brownSoft)
                }
                .frame(height: 30)
            }
        }
    }

    private var starChestRow: some View {
        let stars = progress.album.stars
        let price = AlbumCatalog.starChestPrice
        let ready = stars >= price
        return HStack(spacing: 10) {
            Button { RewardInfo.show(.chest(.star, 1)) } label: { SpriteImage(name: ChestKind.star.sprite, size: 50) }
                .buttonStyle(PressScaleStyle())
            VStack(alignment: .leading, spacing: 5) {
                Text(lang.t("album.stars", stars, price))
                    .font(Theme.rounded(14, .black))
                    .foregroundColor(Theme.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                ProgressBar(value: stars, target: price, color: Theme.vip, height: 12)
                Text(lang.t("album.stars.text"))
                    .font(Theme.rounded(11, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if ready {
                Button(lang.t("album.stars.get")) {
                    if progress.buyStarChest() {
                        Audio.shared.play(.chest)
                        ChestOpener.present(.star)
                    }
                }
                .buttonStyle(GameButtonStyle(palette: .purple, height: 38, fontSize: 15, fullWidth: false, radius: 12))
            }
        }
    }

    // MARK: Книги

    private func cover(_ b: AlbumBook, height: CGFloat) -> some View {
        let shape = RoundedRectangle(cornerRadius: 10, style: .continuous)
        let card = b.cards.max { $0.stars < $1.stars } ?? b.cards[0]
        let claimable = progress.canClaimBook(b)
        let claimed = progress.bookClaimed(b)
        return ZStack {
            shape.fill(LinearGradient(colors: BookStyle.colors(b.id), startPoint: .top, endPoint: .bottom))
            // корешок
            HStack(spacing: 0) {
                Rectangle().fill(Color.black.opacity(0.2)).frame(width: height * 0.1)
                Rectangle().fill(Color.white.opacity(0.3)).frame(width: 2)
                Spacer(minLength: 0)
            }
            .clipShape(shape)
            Circle()
                .fill(RadialGradient(colors: progress.hasCard(card) ? [Color.white, Theme.cream] : [Theme.card, Theme.peach],
                                     center: .center, startRadius: 2, endRadius: height * 0.36))
                .frame(width: height * 0.68, height: height * 0.68)
                .overlay(Circle().strokeBorder(Theme.paperBorder.opacity(0.55), lineWidth: 2))
                .offset(x: height * 0.04)
            SpriteImage(name: card.id, size: height * 0.54, silhouette: !progress.hasCard(card))
                .offset(x: height * 0.04)
            shape.strokeBorder(claimable ? Theme.orange : (claimed ? Theme.gold : Theme.paperBorder),
                               lineWidth: claimable || claimed ? 3 : 2)
        }
        .frame(height: height)
        .shadow(color: Theme.woodDark.opacity(0.45), radius: 0, y: 3)
    }

    private func bookTile(_ b: AlbumBook) -> some View {
        let owned = progress.bookOwned(b)
        let claimable = progress.canClaimBook(b)
        return Button {
            Audio.shared.play(.button, volume: 0.5)
            withAnimation(.easeOut(duration: 0.2)) { book = b.id }
        } label: {
            VStack(spacing: 6) {
                cover(b, height: 92)
                    .overlay(alignment: .topTrailing) {
                        if progress.bookClaimed(b) { SpriteImage(name: "icon_check", size: 26).offset(x: 6, y: -6) }
                    }
                    .overlay(alignment: .bottom) {
                        if claimable {
                            Text(lang.t("common.claim"))
                                .font(Theme.rounded(11, .black))
                                .foregroundColor(.white)
                                .outlined(ButtonPalette.green.dark, width: 1)
                                .lineLimit(1)
                                .padding(.horizontal, 8)
                                .padding(.vertical, 3)
                                .background(Capsule().fill(ButtonPalette.green.bottom))
                                .overlay(Capsule().strokeBorder(ButtonPalette.green.dark, lineWidth: 1.5))
                                .offset(y: 8)
                        }
                    }
                Text(lang.t("album.book." + b.key))
                    .font(Theme.rounded(12, .black))
                    .foregroundColor(Theme.brown)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                    .multilineTextAlignment(.center)
                    .frame(height: 32)
                HStack(spacing: 5) {
                    ProgressBar(value: owned, target: b.cards.count, color: owned == b.cards.count ? Theme.green : Theme.orange, height: 10)
                    Text("\(owned)/\(b.cards.count)")
                        .font(Theme.rounded(11, .black))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize()
                }
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
        let owned = progress.bookOwned(b)
        return VStack(spacing: 14) {
            MetaCard(highlight: progress.canClaimBook(b)) {
                VStack(spacing: 12) {
                    HStack(spacing: 12) {
                        cover(b, height: 72).frame(width: 64)
                        VStack(alignment: .leading, spacing: 7) {
                            Text(lang.t("album.progress", owned, b.cards.count))
                                .font(Theme.rounded(15, .black))
                                .foregroundColor(Theme.brown)
                                .fixedSize(horizontal: false, vertical: true)
                            ProgressBar(value: owned, target: b.cards.count,
                                        color: owned == b.cards.count ? Theme.green : Theme.orange, height: 12)
                        }
                    }
                    Text(lang.t("album.book.reward")).font(Theme.rounded(15, .black)).foregroundColor(Theme.brown)
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
            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(b.cards) { card in
                    AlbumCardView(card: card, owned: progress.hasCard(card), count: progress.cardCount(card), width: 104)
                }
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

/// Кольцо прогресса альбома.
struct AlbumRing<Content: View>: View {
    let value: Int
    let target: Int
    var size: CGFloat = 78
    @ViewBuilder var content: Content

    var body: some View {
        let share = CGFloat(min(1, Double(value) / Double(max(1, target))))
        ZStack {
            Circle().fill(Theme.cream)
            Circle().stroke(Theme.woodDark.opacity(0.25), lineWidth: 8)
            Circle()
                .trim(from: 0, to: share)
                .stroke(LinearGradient(colors: [Theme.gold, Theme.orange], startPoint: .top, endPoint: .bottom),
                        style: StrokeStyle(lineWidth: 8, lineCap: .round))
                .rotationEffect(.degrees(-90))
            content
        }
        .frame(width: size, height: size)
        .padding(4)
    }
}
