import SwiftUI

/// Карта биома 1: путь из 30 уровней, звезды и сундуки.
struct MapView: View {
    let play: (LevelData) -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var showBook = false
    @State private var showLives = false
    @State private var showSettings = false
    @State private var chest: Int?

    private let levels = LevelStore.shared.levels
    private let rowHeight: CGFloat = 96

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.12)
            path
            VStack(spacing: 0) {
                topBar
                Spacer()
                starsCard
            }
            .padding(.horizontal, 14)
            .padding(.bottom, 8)
            if let index = chest {
                ChestPopup(index: index) { chest = nil }
            }
        }
        .sheet(isPresented: $showBook) {
            BookView().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared)
        }
        .sheet(isPresented: $showLives) {
            LivesSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared)
        }
        .sheet(isPresented: $showSettings) {
            SettingsSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared)
        }
    }

    private var topBar: some View {
        HStack(spacing: 8) {
            Button { showLives = true } label: { LivesPill() }.buttonStyle(.plain)
            CoinsPill()
            Spacer()
            CircleIconButton(symbol: "book.fill") { showBook = true }
            CircleIconButton(symbol: "gearshape.fill") { showSettings = true }
        }
        .padding(.top, 6)
    }

    // MARK: - Путь уровней

    private var path: some View {
        GeometryReader { geo in
            ScrollViewReader { proxy in
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        nextBiome
                            .padding(.top, 80)
                            .padding(.bottom, 24)
                        VStack(spacing: 0) {
                            ForEach(levels.reversed()) { level in
                                node(level, width: geo.size.width)
                                    .frame(height: rowHeight)
                                    .id(level.id)
                            }
                        }
                        .background(trail(width: geo.size.width))
                        title
                            .padding(.top, 10)
                            .padding(.bottom, 150)
                    }
                }
                .onAppear {
                    proxy.scrollTo(progress.currentLevel, anchor: .center)
                }
            }
        }
        .ignoresSafeArea(edges: .bottom)
    }

    private func xOffset(_ id: Int, width: CGFloat) -> CGFloat {
        let amplitude = min(110, width * 0.27)
        return CGFloat(sin(Double(id) * 0.9)) * amplitude
    }

    private func trail(width: CGFloat) -> some View {
        Canvas { context, size in
            let top: CGFloat = 0
            var p = Path()
            for (i, level) in levels.reversed().enumerated() {
                let point = CGPoint(x: size.width / 2 + xOffset(level.id, width: width),
                                    y: top + CGFloat(i) * rowHeight + rowHeight / 2 - 9)
                if i == 0 { p.move(to: point) } else { p.addLine(to: point) }
            }
            context.stroke(p, with: .color(Color.white.opacity(0.85)),
                           style: StrokeStyle(lineWidth: 10, lineCap: .round, lineJoin: .round, dash: [2, 16]))
        }
    }

    private func node(_ level: LevelData, width: CGFloat) -> some View {
        let unlocked = progress.isUnlocked(level.id)
        let stars = progress.stars(level.id)
        let current = level.id == progress.currentLevel && stars == 0
        let fill: Color = !unlocked ? Color.gray.opacity(0.45) : (stars > 0 ? Theme.green : Theme.orange)
        return VStack(spacing: 3) {
            Button {
                guard unlocked else { return }
                if progress.isPassed(level.id) || progress.hasLife {
                    play(level)
                } else {
                    showLives = true
                }
            } label: {
                ZStack {
                    Circle()
                        .fill(fill)
                        .frame(width: current ? 70 : 60, height: current ? 70 : 60)
                        .shadow(color: fill.opacity(0.6), radius: 0, x: 0, y: 5)
                    Circle()
                        .stroke(level.hard ? Theme.red : Color.white.opacity(0.9), lineWidth: level.hard ? 5 : 3)
                        .frame(width: current ? 70 : 60, height: current ? 70 : 60)
                    if unlocked {
                        Text("\(level.id)")
                            .font(Theme.rounded(current ? 28 : 24, .heavy))
                            .foregroundColor(.white)
                    } else {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 20, weight: .bold))
                            .foregroundColor(.white.opacity(0.9))
                    }
                }
            }
            .buttonStyle(.plain)
            if unlocked && stars > 0 {
                StarsRow(count: stars, size: 14)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.card.opacity(0.9)))
            } else if level.hard {
                Text(lang.t("map.hard"))
                    .font(Theme.rounded(11, .heavy))
                    .foregroundColor(Theme.red)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.card.opacity(0.9)))
            }
        }
        .offset(x: xOffset(level.id, width: width))
        .frame(maxWidth: .infinity)
    }

    private var title: some View {
        Panel(padding: 14) {
            VStack(spacing: 4) {
                Text(lang.t("biome.1.name"))
                    .font(Theme.rounded(26, .heavy))
                    .foregroundColor(Theme.brown)
                Text(lang.t("biome.1.subtitle"))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
            }
        }
    }

    private var nextBiome: some View {
        Panel(padding: 14) {
            HStack(spacing: 12) {
                Image(systemName: "lock.fill")
                    .font(.system(size: 22, weight: .bold))
                    .foregroundColor(Theme.brownSoft)
                VStack(alignment: .leading, spacing: 2) {
                    Text(lang.t("biome.2.name"))
                        .font(Theme.rounded(17, .heavy))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("biome.2.soon"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                }
                Spacer()
            }
        }
        .padding(.horizontal, 30)
    }

    // MARK: - Звезды биома

    private var starsCard: some View {
        let total = progress.totalStars()
        let maxStars = Balance.levelsPerBiome * 3
        return Panel(padding: 12) {
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "star.fill").foregroundColor(Theme.gold)
                    Text(lang.t("map.stars", total, maxStars))
                        .font(Theme.rounded(15, .heavy))
                        .foregroundColor(Theme.brown)
                    Spacer()
                }
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Theme.brown.opacity(0.12)).frame(height: 12)
                        Capsule().fill(Theme.gold)
                            .frame(width: max(12, geo.size.width * CGFloat(total) / CGFloat(maxStars)), height: 12)
                        ForEach(Balance.chests.indices, id: \.self) { i in
                            chestButton(i)
                                .position(x: geo.size.width * CGFloat(Balance.chests[i].stars) / CGFloat(maxStars) - 18,
                                          y: 6)
                        }
                    }
                }
                .frame(height: 30)
            }
        }
    }

    private func chestButton(_ i: Int) -> some View {
        let ready = progress.chestReady(i)
        let claimed = progress.chestClaimed(i)
        return Button { if ready { chest = i } else if !claimed { chest = i } } label: {
            Image(systemName: claimed ? "checkmark.seal.fill" : (i == 2 ? "crown.fill" : "gift.fill"))
                .font(.system(size: i == 2 ? 22 : 18, weight: .bold))
                .foregroundColor(claimed ? Theme.green : (ready ? Theme.orange : Theme.brownSoft))
                .frame(width: 36, height: 36)
                .background(Circle().fill(Theme.card).shadow(color: ready ? Theme.orange.opacity(0.7) : .clear, radius: 6))
                .scaleEffect(ready ? 1.1 : 1)
        }
        .buttonStyle(.plain)
    }
}

/// Окно сундука звезд биома.
struct ChestPopup: View {
    let index: Int
    let close: () -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var opened = false

    var body: some View {
        let chest = Balance.chests[index]
        let ready = progress.chestReady(index)
        let claimed = progress.chestClaimed(index)
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    Image(systemName: index == 2 ? "crown.fill" : "gift.fill")
                        .font(.system(size: 54, weight: .bold))
                        .foregroundColor(index == 2 ? Theme.gold : Theme.orange)
                        .rotationEffect(.degrees(opened ? 0 : -8))
                        .scaleEffect(opened ? 1.15 : 1)
                    Text(lang.t(index == 2 ? "chest.gold.title" : "chest.title", chest.stars))
                        .font(Theme.rounded(22, .heavy))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                    VStack(alignment: .leading, spacing: 8) {
                        rewardRow(AnyView(CoinIcon(size: 22)), "\(chest.coins)")
                        ForEach(Booster.allCases) { booster in
                            if let n = chest.boosters[booster], n > 0 {
                                rewardRow(AnyView(Image(systemName: booster.symbol).foregroundColor(Theme.orange)),
                                          lang.t("booster." + booster.rawValue) + " ×\(n)")
                            }
                        }
                        if chest.unlimitedLives > 0 {
                            rewardRow(AnyView(Image(systemName: "heart.fill").foregroundColor(Theme.red)),
                                      lang.t("chest.unlimited", Int(chest.unlimitedLives / 3600)))
                        }
                        if chest.goldShelves {
                            rewardRow(AnyView(SpriteImage(name: "shelf_gold", size: 34)), lang.t("chest.goldshelves"))
                        }
                    }
                    if claimed {
                        Text(lang.t("chest.claimed"))
                            .font(Theme.rounded(16, .heavy))
                            .foregroundColor(Theme.green)
                        Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle())
                    } else if ready {
                        Button(lang.t("chest.open")) {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) { opened = true }
                            progress.claimChest(index)
                            Haptics.success()
                        }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                    } else {
                        Text(lang.t("chest.need", max(0, chest.stars - progress.totalStars())))
                            .font(Theme.rounded(15, .semibold))
                            .foregroundColor(Theme.brownSoft)
                            .multilineTextAlignment(.center)
                        Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle())
                    }
                }
                .frame(maxWidth: 300)
            }
        }
    }

    private func rewardRow(_ icon: AnyView, _ text: String) -> some View {
        HStack(spacing: 10) {
            icon.frame(width: 34)
            Text(text)
                .font(Theme.rounded(17, .bold))
                .foregroundColor(Theme.brown)
        }
    }
}

struct LivesSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var message: String?

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            VStack(spacing: 18) {
                Image(systemName: "heart.fill")
                    .font(.system(size: 64))
                    .foregroundColor(Theme.red)
                Text(progress.unlimitedLives ? lang.t("lives.unlimited") : lang.t("lives.count", progress.lives, Balance.maxLives))
                    .font(Theme.rounded(24, .heavy))
                    .foregroundColor(Theme.brown)
                if let next = progress.nextLifeIn {
                    Text(lang.t("lives.next", Lang.time(next)))
                        .font(Theme.rounded(16, .semibold))
                        .foregroundColor(Theme.brownSoft)
                }
                Text(lang.t("lives.replay"))
                    .font(Theme.rounded(14, .medium))
                    .foregroundColor(Theme.brownSoft)
                    .multilineTextAlignment(.center)
                if progress.lives < Balance.maxLives && !progress.unlimitedLives {
                    Button {
                        if progress.refillLives() {
                            presentation.wrappedValue.dismiss()
                        } else {
                            message = lang.t("common.nocoins")
                        }
                    } label: {
                        HStack { Text(lang.t("lives.refill")); CoinIcon(size: 20); Text("\(Balance.livesRefillPrice)") }
                    }
                    .buttonStyle(BigButtonStyle())
                    Button {
                        Ads.shared.showRewarded(placement: "life") { ok in
                            if ok { progress.addLife() } else { message = lang.t("ads.limit") }
                        }
                    } label: {
                        HStack { Image(systemName: "play.rectangle.fill"); Text(lang.t("lives.ad")) }
                    }
                    .buttonStyle(BigButtonStyle(color: Theme.green))
                    AdsLeftLabel()
                }
                if let message = message {
                    Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
                }
                Spacer()
            }
            .padding(24)
            .padding(.top, 20)
        }
    }
}

struct SettingsSheet: View {
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            VStack(alignment: .leading, spacing: 16) {
                Text(lang.t("settings.title"))
                    .font(Theme.rounded(26, .heavy))
                    .foregroundColor(Theme.brown)
                Text(lang.t("settings.language"))
                    .font(Theme.rounded(16, .bold))
                    .foregroundColor(Theme.brownSoft)
                ForEach(Lang.options) { option in
                    Button { lang.set(option.code) } label: {
                        HStack {
                            Text(option.name).font(Theme.rounded(18, .bold)).foregroundColor(Theme.brown)
                            Spacer()
                            if option.code == lang.code {
                                Image(systemName: "checkmark.circle.fill").foregroundColor(Theme.green)
                            }
                        }
                        .padding(14)
                        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.card))
                    }
                    .buttonStyle(.plain)
                }
                Text(lang.t("settings.player", String(progress.playerId.prefix(8))))
                    .font(Theme.rounded(13, .medium))
                    .foregroundColor(Theme.brownSoft)
                    .padding(.top, 10)
                Spacer()
            }
            .padding(24)
        }
    }
}
