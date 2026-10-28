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
            HStack(spacing: 1) {
                ForEach(0..<card.stars, id: \.self) { _ in
                    Image(systemName: "star.fill").font(.system(size: width * 0.09, weight: .bold))
                        .foregroundColor(owned ? Color(red: 1.0, green: 0.78, blue: 0.15) : Theme.brownSoft.opacity(0.4))
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
                .stroke(owned ? CardStyle.colors(card.stars)[1] : Theme.brown.opacity(0.12), lineWidth: 2)
        )
        .overlay(alignment: .topTrailing) {
            if owned && count > 1 {
                Text("+\(count - 1)")
                    .font(Theme.rounded(11, .heavy))
                    .foregroundColor(.white)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(Capsule().fill(Theme.orange))
                    .offset(x: 4, y: -5)
            }
        }
        .overlay(alignment: .topLeading) {
            if isNew {
                Text(lang.t("album.new"))
                    .font(Theme.rounded(10, .heavy))
                    .foregroundColor(.white)
                    .padding(.horizontal, 5)
                    .padding(.vertical, 1)
                    .background(Capsule().fill(Theme.red))
                    .offset(x: -4, y: -5)
            }
        }
    }
}

/// Сундук с подписью содержимого: сколько карточек и какой минимум звезд.
struct ChestContents: View {
    let kind: ChestKind
    @EnvironmentObject private var lang: Lang

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(lang.t("chest.kind." + kind.rawValue)).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brown)
            Text(lang.t("chest.contents", kind.cards, kind.guaranteed))
                .font(Theme.rounded(12, .semibold))
                .foregroundColor(Theme.brownSoft)
                .fixedSize(horizontal: false, vertical: true)
            HStack(spacing: 3) {
                CoinIcon(size: 14)
                Text("+\(kind.coins)").font(Theme.rounded(12, .heavy)).foregroundColor(Theme.brown)
            }
        }
    }
}

// MARK: - Альбом

struct AlbumSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var book: Int?
    @State private var opening: ChestOpening?
    @State private var granted: Granted?

    private let columns = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    SheetHeader(title: lang.t("album.title"),
                                subtitle: lang.t("album.season", Lang.time(progress.albumSecondsLeft))) {
                        presentation.wrappedValue.dismiss()
                    }
                    if let index = book {
                        bookDetail(AlbumCatalog.books[index])
                    } else {
                        summary
                        chests
                        starChest
                        LazyVGrid(columns: columns, spacing: 10) {
                            ForEach(AlbumCatalog.books) { b in bookTile(b) }
                        }
                        grandCard
                    }
                }
                .padding(20)
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
            VStack(alignment: .leading, spacing: 8) {
                Text(lang.t("album.progress", owned, AlbumCatalog.cards.count))
                    .font(Theme.rounded(17, .heavy))
                    .foregroundColor(Theme.brown)
                ProgressBar(value: owned, target: AlbumCatalog.cards.count, color: Theme.gold)
                Text(lang.t("album.text"))
                    .font(Theme.rounded(12, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
    }

    private var chests: some View {
        let kinds = ChestKind.allCases.filter { progress.chestCount($0) > 0 }
        return VStack(alignment: .leading, spacing: 8) {
            Text(lang.t("album.chests")).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
            if kinds.isEmpty {
                Text(lang.t("album.chests.empty"))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
            ForEach(kinds) { kind in
                MetaCard(highlight: true) {
                    HStack(spacing: 12) {
                        ZStack(alignment: .topTrailing) {
                            SpriteImage(name: kind.sprite, size: 64)
                            Text("×\(progress.chestCount(kind))")
                                .font(Theme.rounded(12, .heavy))
                                .foregroundColor(.white)
                                .padding(.horizontal, 5)
                                .background(Capsule().fill(Theme.red))
                        }
                        ChestContents(kind: kind)
                        Spacer(minLength: 0)
                        Button(lang.t("chest.open")) {
                            if let result = progress.openChest(kind) {
                                withAnimation { opening = result }
                            }
                        }
                        .font(Theme.rounded(14, .heavy))
                        .foregroundColor(.white)
                        .padding(.horizontal, 14)
                        .frame(height: 36)
                        .background(Capsule().fill(Theme.green))
                    }
                }
            }
        }
    }

    private var starChest: some View {
        let stars = progress.album.stars
        let ready = stars >= AlbumCatalog.starChestPrice
        return MetaCard(highlight: ready) {
            HStack(spacing: 12) {
                SpriteImage(name: ChestKind.star.sprite, size: 56)
                VStack(alignment: .leading, spacing: 4) {
                    Text(lang.t("album.stars", stars, AlbumCatalog.starChestPrice))
                        .font(Theme.rounded(15, .heavy))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("album.stars.text"))
                        .font(Theme.rounded(12, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                    ProgressBar(value: stars, target: AlbumCatalog.starChestPrice, color: Theme.vip)
                }
                if ready {
                    Button(lang.t("album.stars.get")) {
                        if progress.buyStarChest() { Audio.shared.play(.chest) }
                    }
                    .font(Theme.rounded(13, .heavy))
                    .foregroundColor(.white)
                    .padding(.horizontal, 12)
                    .frame(height: 34)
                    .background(Capsule().fill(Theme.vip))
                }
            }
        }
    }

    private func bookTile(_ b: AlbumBook) -> some View {
        let owned = progress.bookOwned(b)
        let claimable = progress.canClaimBook(b)
        let cover = b.cards.max { $0.stars < $1.stars } ?? b.cards[0]
        return Button { withAnimation(.easeOut(duration: 0.2)) { book = b.id } } label: {
            VStack(spacing: 6) {
                ZStack {
                    RoundedRectangle(cornerRadius: 12, style: .continuous)
                        .fill(LinearGradient(colors: CardStyle.colors(min(5, b.id % 5 + 1)), startPoint: .top, endPoint: .bottom))
                    SpriteImage(name: cover.id, size: 58, silhouette: !progress.hasCard(cover))
                    if progress.bookClaimed(b) {
                        Image(systemName: "checkmark.seal.fill").font(.system(size: 20)).foregroundColor(Theme.green)
                            .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topTrailing)
                            .padding(4)
                    }
                }
                .frame(height: 76)
                Text(lang.t("album.book." + b.key))
                    .font(Theme.rounded(12, .heavy))
                    .foregroundColor(Theme.brown)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                    .multilineTextAlignment(.center)
                    .frame(height: 30)
                ProgressBar(value: owned, target: b.cards.count, color: owned == b.cards.count ? Theme.green : Theme.orange)
                Text("\(owned)/\(b.cards.count)").font(Theme.rounded(11, .bold)).foregroundColor(Theme.brownSoft)
            }
            .padding(8)
            .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(claimable ? Theme.green : Color.clear, lineWidth: 2))
            .overlay(alignment: .topTrailing) {
                if claimable { BadgeDot().offset(x: 3, y: -3) }
            }
        }
        .buttonStyle(.plain)
    }

    private func bookDetail(_ b: AlbumBook) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Button { withAnimation(.easeOut(duration: 0.2)) { book = nil } } label: {
                Label(lang.t("album.back"), systemImage: "chevron.left")
                    .font(Theme.rounded(15, .heavy))
                    .foregroundColor(Theme.orange)
            }
            .buttonStyle(.plain)
            Text(lang.t("album.book." + b.key)).font(Theme.rounded(22, .heavy)).foregroundColor(Theme.brown)
            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(b.cards) { card in
                    AlbumCardView(card: card, owned: progress.hasCard(card), count: progress.cardCount(card), width: 100)
                }
            }
            MetaCard(highlight: progress.canClaimBook(b)) {
                VStack(spacing: 8) {
                    Text(lang.t("album.book.reward")).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brown)
                    RewardChips(reward: b.reward)
                    if progress.canClaimBook(b) {
                        Button(lang.t("common.claim")) { granted = progress.claimBook(b) }
                            .buttonStyle(BigButtonStyle(color: Theme.green))
                    } else if progress.bookClaimed(b) {
                        Label(lang.t("challenge.done"), systemImage: "checkmark.seal.fill")
                            .font(Theme.rounded(15, .heavy))
                            .foregroundColor(Theme.green)
                    }
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    private var grandCard: some View {
        MetaCard(highlight: progress.canClaimAlbumGrand) {
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "trophy.fill").foregroundColor(Theme.gold)
                    Text(lang.t("album.grand")).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                }
                RewardChips(reward: AlbumCatalog.grand)
                if progress.canClaimAlbumGrand {
                    Button(lang.t("common.claim")) { granted = progress.claimAlbumGrand() }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
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
            Color.black.opacity(0.65).ignoresSafeArea()
                .onTapGesture(perform: next)
            VStack(spacing: 18) {
                Text(lang.t("chest.kind." + opening.kind.rawValue))
                    .font(Theme.rounded(24, .heavy))
                    .foregroundColor(.white)
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
                        Text(lang.t("chest.cards.left", opening.drops.count - shown))
                            .font(Theme.rounded(14, .bold))
                            .foregroundColor(.white.opacity(0.8))
                        Text(lang.t("chest.tap"))
                            .font(Theme.rounded(13, .semibold))
                            .foregroundColor(.white.opacity(0.6))
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
                Label("\(opening.drops.filter(\.isNew).count) " + lang.t("album.new"), systemImage: "sparkles")
                    .foregroundColor(Theme.gold)
                HStack(spacing: 3) { CoinIcon(size: 16); Text("+\(opening.coins)") }
                    .foregroundColor(.white)
                if opening.stars > 0 {
                    Label("+\(opening.stars)", systemImage: "star.fill").foregroundColor(Color(red: 0.75, green: 0.6, blue: 1.0))
                }
            }
            .font(Theme.rounded(15, .heavy))
            Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle())
                .frame(maxWidth: 240)
        }
    }
}
