import SwiftUI

/// Карта: биомы снизу вверх, у каждого путь из 30 уровней, звезды и сундуки.
/// Между биомами ворота: открываются звездами предыдущей кухни или монетами.
struct MapView: View {
    let play: (LevelData, PlayMode) -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var showBook = false
    @State private var showLives = false
    @State private var showSettings = false
    @State private var showStreak = false
    @State private var showChallenges = false
    @State private var showQuests = false
    @State private var showAchievements = false
    @State private var showBackgrounds = false
    @State private var showEvents = false
    @State private var showMerge = false
    @State private var pendingLaunch: LevelLaunch?
    @State private var chest: Int?
    @State private var openedBiome: Int?
    @State private var showShop = false
    @State private var vipDaily: Granted?

    private let rowHeight: CGFloat = 96

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.12, style: progress.background(forBiome: progress.mapBiome))
            path
            VStack(spacing: 0) {
                topBar
                HStack {
                    Spacer()
                    sideRail
                }
                .padding(.top, 10)
                Spacer()
                starsCard
            }
            .padding(.horizontal, 14)
            .padding(.bottom, 8)
            if let index = chest {
                ChestPopup(index: index) { chest = nil }
            }
            if let biome = openedBiome {
                BiomeOpenedPopup(biome: biome) { openedBiome = nil }
            }
            if let granted = vipDaily {
                RewardPopup(title: lang.t("vip.daily"), granted: granted) { vipDaily = nil }
            }
        }
        .onAppear {
            Audio.shared.setTrack(Biomes.music(progress.mapBiome))
            progress.applyPassCredit()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { vipDaily = progress.claimVIPDaily() }
        }
        .sheet(isPresented: $showShop) {
            ShopSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showBook) {
            BookView().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showLives) {
            LivesSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showSettings) {
            SettingsSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showStreak) {
            StreakSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showChallenges, onDismiss: launchPending) {
            ChallengesSheet(launch: $pendingLaunch).environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showQuests) {
            QuestsSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showAchievements) {
            AchievementsSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .fullScreenCover(isPresented: $showMerge) {
            MergeView(close: { showMerge = false })
                .environmentObject(PlayerProgress.shared)
                .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showEvents, onDismiss: launchPending) {
            EventsSheet(launch: $pendingLaunch).environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .sheet(isPresented: $showBackgrounds) {
            BackgroundsSheet().environmentObject(PlayerProgress.shared).environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
    }

    private func launchPending() {
        guard let launch = pendingLaunch else { return }
        pendingLaunch = nil
        play(launch.level, launch.mode)
    }

    // MARK: - Боковые кнопки

    private var sideRail: some View {
        VStack(spacing: 12) {
            railButton("cart.fill", badge: !progress.starterBought && progress.isPassed(5)) { showShop = true }
            railButton("book.fill", badge: false) { showBook = true }
            railButton("sparkles", badge: progress.eventsClaimable) { showEvents = true }
            railButton("square.grid.3x3.fill", badge: progress.energy >= MergeBalance.maxEnergy) { showMerge = true }
            railButton("calendar", badge: !progress.dailyDone()) { showChallenges = true }
            if progress.welcomeActive {
                railButton("gift.fill", badge: progress.questsClaimable) { showQuests = true }
            }
            railButton("trophy.fill", badge: progress.achievementsClaimable) { showAchievements = true }
            railButton("paintpalette.fill", badge: false) { showBackgrounds = true }
        }
    }

    private func railButton(_ symbol: String, badge: Bool, action: @escaping () -> Void) -> some View {
        ZStack(alignment: .topTrailing) {
            CircleIconButton(symbol: symbol, size: 48, action: action)
            if badge { BadgeDot().offset(x: 2, y: -2) }
        }
    }

    private var topBar: some View {
        HStack(spacing: 8) {
            Button { showLives = true } label: { LivesPill() }.buttonStyle(.plain)
            Button { showShop = true } label: { CoinsPill() }.buttonStyle(.plain)
            StreakButton { showStreak = true }
            Spacer()
            VIPBadge { showShop = true }
            CircleIconButton(symbol: "gearshape.fill") { showSettings = true }
        }
        .padding(.top, 6)
    }

    // MARK: - Путь уровней

    /// Первый закрытый биом: у него интерактивные ворота, дальше просто замки.
    private var firstLocked: Int? {
        (2...Biomes.playable).first { !progress.isBiomeOpen($0) }
    }

    private var path: some View {
        GeometryReader { geo in
            ScrollViewReader { proxy in
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        VStack(spacing: 10) {
                            ForEach(Biomes.upcoming.reversed(), id: \.self) { biome in soonCard(biome) }
                        }
                        .padding(.top, 80)
                        .padding(.bottom, 24)
                        ForEach((1...Biomes.playable).reversed(), id: \.self) { biome in
                            if progress.isBiomeOpen(biome) {
                                biomeSection(biome, width: geo.size.width)
                            } else if biome == firstLocked {
                                BiomeGate(biome: biome, opened: { openedBiome = biome })
                                    .padding(.horizontal, 30)
                                    .padding(.vertical, 20)
                                    .id("gate\(biome)")
                            } else {
                                lockedCard(biome)
                                    .padding(.vertical, 10)
                            }
                        }
                        Color.clear.frame(height: 150)
                    }
                }
                .onAppear { scrollToCurrent(proxy) }
                .onChange(of: openedBiome) { _ in scrollToCurrent(proxy) }
            }
        }
        .ignoresSafeArea(edges: .bottom)
    }

    private func scrollToCurrent(_ proxy: ScrollViewProxy) {
        let current = progress.currentLevel
        let biome = Biomes.of(level: current)
        if progress.isBiomeOpen(biome) {
            proxy.scrollTo(current, anchor: .center)
        } else {
            proxy.scrollTo("gate\(biome)", anchor: .center)
        }
    }

    private func biomeSection(_ biome: Int, width: CGFloat) -> some View {
        let levels = LevelStore.shared.levels(biome: biome)
        return VStack(spacing: 0) {
            VStack(spacing: 0) {
                ForEach(levels.reversed()) { level in
                    node(level, width: width)
                        .frame(height: rowHeight)
                        .id(level.id)
                }
            }
            .background(trail(levels: levels, width: width))
            title(biome)
                .padding(.top, 10)
                .padding(.bottom, 26)
        }
    }

    private func xOffset(_ id: Int, width: CGFloat) -> CGFloat {
        let amplitude = min(92, width * 0.23)
        return CGFloat(sin(Double(id) * 0.9)) * amplitude
    }

    private func trail(levels: [LevelData], width: CGFloat) -> some View {
        Canvas { context, size in
            var p = Path()
            for (i, level) in levels.reversed().enumerated() {
                let point = CGPoint(x: size.width / 2 + xOffset(level.id, width: width),
                                    y: CGFloat(i) * rowHeight + rowHeight / 2 - 9)
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
                    play(level, .main)
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

    private func title(_ biome: Int) -> some View {
        Panel(padding: 14) {
            HStack(spacing: 12) {
                SpriteImage(name: Biomes.icon(biome), size: 52)
                VStack(alignment: .leading, spacing: 4) {
                    Text(lang.t("biome.\(biome).name"))
                        .font(Theme.rounded(24, .heavy))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("biome.\(biome).subtitle"))
                        .font(Theme.rounded(14, .semibold))
                        .foregroundColor(Theme.brownSoft)
                }
            }
        }
    }

    private func lockedCard(_ biome: Int) -> some View {
        Panel(padding: 14) {
            HStack(spacing: 12) {
                SpriteImage(name: Biomes.icon(biome), size: 46, silhouette: true)
                VStack(alignment: .leading, spacing: 2) {
                    Text(lang.t("biome.\(biome).name"))
                        .font(Theme.rounded(17, .heavy))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("biome.locked", lang.t("biome.\(biome - 1).name")))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Spacer()
                Image(systemName: "lock.fill")
                    .font(.system(size: 20, weight: .bold))
                    .foregroundColor(Theme.brownSoft)
            }
        }
        .padding(.horizontal, 30)
    }

    private func soonCard(_ biome: Int) -> some View {
        Panel(padding: 12) {
            HStack(spacing: 12) {
                Image(systemName: "hourglass")
                    .font(.system(size: 20, weight: .bold))
                    .foregroundColor(Theme.brownSoft)
                    .frame(width: 30)
                VStack(alignment: .leading, spacing: 2) {
                    Text(lang.t("biome.\(biome).name"))
                        .font(Theme.rounded(16, .heavy))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("biome.soon"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                }
                Spacer()
            }
        }
        .opacity(0.85)
        .padding(.horizontal, 44)
    }

    // MARK: - Звезды биома

    private var starsCard: some View {
        let biome = progress.mapBiome
        let total = progress.totalStars(biome: biome)
        let maxStars = Balance.levelsPerBiome * 3
        let chests = Biomes.chests(biome)
        return Panel(padding: 12) {
            VStack(spacing: 8) {
                HStack {
                    Image(systemName: "star.fill").foregroundColor(Theme.gold)
                    Text(lang.t("map.stars", total, maxStars))
                        .font(Theme.rounded(15, .heavy))
                        .foregroundColor(Theme.brown)
                    Spacer()
                    Text(lang.t("biome.\(biome).name"))
                        .font(Theme.rounded(13, .bold))
                        .foregroundColor(Theme.brownSoft)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Theme.brown.opacity(0.12)).frame(height: 12)
                        Capsule().fill(Theme.gold)
                            .frame(width: max(12, geo.size.width * CGFloat(total) / CGFloat(maxStars)), height: 12)
                        ForEach(chests.indices, id: \.self) { i in
                            chestButton((biome - 1) * 3 + i)
                                .position(x: geo.size.width * CGFloat(chests[i].stars) / CGFloat(maxStars) - 18, y: 6)
                        }
                    }
                }
                .frame(height: 30)
            }
        }
    }

    private func chestButton(_ index: Int) -> some View {
        let ready = progress.chestReady(index)
        let claimed = progress.chestClaimed(index)
        let crown = index % 3 == 2
        return Button { chest = index } label: {
            Image(systemName: claimed ? "checkmark.seal.fill" : (crown ? "crown.fill" : "gift.fill"))
                .font(.system(size: crown ? 22 : 18, weight: .bold))
                .foregroundColor(claimed ? Theme.green : (ready ? Theme.orange : Theme.brownSoft))
                .frame(width: 36, height: 36)
                .background(Circle().fill(Theme.card).shadow(color: ready ? Theme.orange.opacity(0.7) : .clear, radius: 6))
                .scaleEffect(ready ? 1.1 : 1)
        }
        .buttonStyle(.plain)
    }
}

/// Ворота следующей кухни: звезды предыдущей или монеты.
struct BiomeGate: View {
    let biome: Int
    let opened: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var message: String?

    var body: some View {
        let reached = progress.biomeGateReached(biome)
        let stars = progress.totalStars(biome: biome - 1)
        let need = Biomes.starsNeeded(biome)
        Panel(padding: 18) {
            VStack(spacing: 12) {
                SpriteImage(name: Biomes.icon(biome), size: 96, silhouette: !reached)
                Text(lang.t("biome.\(biome).name"))
                    .font(Theme.rounded(24, .heavy))
                    .foregroundColor(Theme.brown)
                Text(lang.t("biome.\(biome).subtitle"))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .multilineTextAlignment(.center)
                if !reached {
                    Label(lang.t("biome.locked", lang.t("biome.\(biome - 1).name")), systemImage: "lock.fill")
                        .font(Theme.rounded(14, .bold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                } else {
                    HStack(spacing: 6) {
                        Image(systemName: "star.fill").foregroundColor(Theme.gold)
                        Text(lang.t("biome.gate.stars", min(stars, need), need))
                            .font(Theme.rounded(16, .heavy))
                            .foregroundColor(Theme.brown)
                    }
                    if progress.biomeStarsReady(biome) {
                        Button(lang.t("biome.gate.open")) { open(pay: false) }
                            .buttonStyle(BigButtonStyle(color: Theme.green))
                    } else {
                        Text(lang.t("biome.gate.hint", need - stars))
                            .font(Theme.rounded(13, .semibold))
                            .foregroundColor(Theme.brownSoft)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                        Button { open(pay: true) } label: {
                            HStack { Text(lang.t("biome.gate.buy")); CoinIcon(size: 20); Text("\(Biomes.unlockPrice)") }
                        }
                        .buttonStyle(BigButtonStyle())
                    }
                    if let message = message {
                        Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
                    }
                }
            }
            .frame(maxWidth: .infinity)
        }
    }

    private func open(pay: Bool) {
        if progress.openBiome(biome, pay: pay) {
            Haptics.success()
            Audio.shared.play(.unlock)
            opened()
        } else {
            message = lang.t("common.nocoins")
        }
    }
}

/// Новая кухня открыта: фон в подарок и новая музыка.
struct BiomeOpenedPopup: View {
    let biome: Int
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var shown = false

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    SpriteImage(name: Biomes.icon(biome), size: 120)
                        .scaleEffect(shown ? 1 : 0.4)
                        .rotationEffect(.degrees(shown ? 0 : -15))
                    Text(lang.t("biome.opened", lang.t("biome.\(biome).name")))
                        .font(Theme.rounded(24, .heavy))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                    Text(lang.t("biome.\(biome).intro"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 10) {
                        Image(uiImage: Art.image(KitchenStyle.image(Biomes.style(biome))))
                            .resizable()
                            .aspectRatio(contentMode: .fill)
                            .frame(width: 54, height: 80)
                            .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
                        Text(lang.t("biome.opened.bg", lang.t("bg." + Biomes.style(biome))))
                            .font(Theme.rounded(14, .bold))
                            .foregroundColor(Theme.brown)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Button(lang.t("intro.go"), action: close).buttonStyle(BigButtonStyle())
                }
                .frame(maxWidth: 300)
            }
        }
        .onAppear {
            withAnimation(.spring(response: 0.45, dampingFraction: 0.55)) { shown = true }
            Audio.shared.play(.chest)
            Audio.shared.setTrack(Biomes.music(biome))
        }
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
        let chest = Biomes.chest(index)
        let crown = index % 3 == 2
        let ready = progress.chestReady(index)
        let claimed = progress.chestClaimed(index)
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    Image(systemName: crown ? "crown.fill" : "gift.fill")
                        .font(.system(size: 54, weight: .bold))
                        .foregroundColor(crown ? Theme.gold : Theme.orange)
                        .rotationEffect(.degrees(opened ? 0 : -8))
                        .scaleEffect(opened ? 1.15 : 1)
                    Text(lang.t(crown ? "chest.gold.title" : "chest.title", chest.stars))
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
                            Audio.shared.play(.chest)
                        }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                    } else {
                        Text(lang.t("chest.need", max(0, chest.stars - progress.totalStars(biome: index / 3 + 1))))
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
                Text(progress.unlimitedLives ? lang.t("lives.unlimited") : lang.t("lives.count", progress.lives, progress.maxLives))
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
                if progress.lives < progress.maxLives && !progress.unlimitedLives {
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
                        HStack { AdIcon(); Text(lang.t("lives.ad")) }
                    }
                    .buttonStyle(BigButtonStyle(color: Theme.green))
                    AdsLeftLabel()
                }
                if !progress.unlimitedLives {
                    Button {
                        Task { @MainActor in
                            switch await Store.shared.buy(.lives) {
                            case .done:
                                Audio.shared.play(.chest)
                                presentation.wrappedValue.dismiss()
                            case .unavailable:
                                message = lang.t("shop.unavailable")
                            case .failed:
                                message = lang.t("shop.failed")
                            default:
                                break
                            }
                        }
                    } label: {
                        HStack { Image(systemName: "infinity"); Text(lang.t("lives.buy")); Text(Store.shared.price(.lives)) }
                    }
                    .buttonStyle(BigButtonStyle(color: Theme.vip))
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
            ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                Text(lang.t("settings.title"))
                    .font(Theme.rounded(26, .heavy))
                    .foregroundColor(Theme.brown)
                toggle(lang.t("settings.music"), "music.note", \.music)
                toggle(lang.t("settings.sound"), "speaker.wave.2.fill", \.sound)
                toggle(lang.t("settings.haptics"), "iphone.radiowaves.left.and.right", \.haptics)
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
            }
            .padding(24)
            }
        }
    }

    private func toggle(_ title: String, _ symbol: String, _ key: WritableKeyPath<GameSettings, Bool>) -> some View {
        Toggle(isOn: Binding(
            get: { progress.settings[keyPath: key] },
            set: { value in
                var settings = progress.settings
                settings[keyPath: key] = value
                progress.update(settings: settings)
            })) {
            HStack(spacing: 10) {
                Image(systemName: symbol)
                    .font(.system(size: 17, weight: .bold))
                    .foregroundColor(Theme.orange)
                    .frame(width: 26)
                Text(title).font(Theme.rounded(18, .bold)).foregroundColor(Theme.brown)
            }
        }
        .tint(Theme.orange)
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 14).fill(Theme.card))
    }
}
