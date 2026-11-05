import SwiftUI

/// Карта: биомы снизу вверх, у каждого путь из 30 уровней, звезды и сундуки.
/// Между биомами ворота: открываются звездами предыдущей кухни или монетами.
struct MapView: View {
    let play: (LevelData, PlayMode) -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var router: Router
    @State private var chest: Int?
    @State private var openedBiome: Int?
    @State private var vipDaily: Granted?
    /// Награда из сундука звезд: готовый сундук открывается одним нажатием, без окна.
    @State private var chestGranted: (title: String, granted: Granted)?
    /// Закрытая мини-игра, про которую игрок спросил тапом.
    @State private var lockedInfo: LockedFeature?
    /// Окно "Открыто!" после прохождения уровня открытия мини-игр.
    @State private var featureOpened = false
    /// Кухня, чьи звезды и сундуки показаны в карточке снизу (nil - текущая).
    @State private var shownBiome: Int?
    /// Куда прокрутить карту: уровень, который стоит переиграть.
    @State private var scrollTarget: Int?

    private let rowHeight: CGFloat = 96

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.12, style: progress.background(forBiome: progress.mapBiome))
            path
            VStack(spacing: 0) {
                topBar
                HStack(alignment: .top) {
                    if progress.marketUnlocked && HappyHour.active(progress.now) {
                        HappyHourChip()
                    }
                    Spacer()
                    sideRail
                }
                .padding(.top, 12)
                Spacer()
                starsCard
                    .padding(.bottom, MainTabBar.height + 10)
            }
            .padding(.horizontal, 12)
            if let index = chest {
                ChestPopup(index: index) { chest = nil }
            }
            if let biome = openedBiome {
                BiomeOpenedPopup(biome: biome) { openedBiome = nil }
            }
            if let granted = vipDaily {
                RewardPopup(title: lang.t("vip.daily"), granted: granted) { vipDaily = nil }
            }
            if let pair = chestGranted {
                RewardPopup(title: pair.title, granted: pair.granted) { chestGranted = nil }
            }
            if let feature = lockedInfo {
                LockedFeaturePopup(feature: feature) { lockedInfo = nil }
            }
            if featureOpened {
                FeatureOpenedPopup(close: { featureOpened = false }) {
                    featureOpened = false
                    router.market = true
                }
            }
        }
        .onAppear {
            Audio.shared.setTrack(Biomes.music(progress.mapBiome))
            progress.applyPassCredit()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) { vipDaily = progress.claimVIPDaily() }
            checkUnlockNews()
        }
        .onChange(of: progress.marketUnlocked) { _ in checkUnlockNews() }
    }

    /// Мини-игры только что открылись: один раз показываем праздничное окно с переходом в "Продуктовый ряд".
    private func checkUnlockNews() {
        guard progress.marketUnlocked, !progress.data.market.unlockSeen else { return }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.9) {
            guard openedBiome == nil, progress.takeMarketUnlockNews() else { return }
            withAnimation(.easeOut(duration: 0.2)) { featureOpened = true }
        }
    }

    // MARK: - Боковые кнопки

    /// Сбоку остается то, что относится к карте: мини-игры (с подписью жанра), фоновые события и задания новичка.
    private var sideRail: some View {
        VStack(spacing: 14) {
            railButton("gen_crate", title: lang.t("rail.pantry"), tag: lang.t("rail.tag.merge"), badge: progress.energy >= MergeBalance.maxEnergy) {
                router.merge = true
            }
            if progress.marketUnlocked {
                railButton("icon_market", title: lang.t("rail.market"), tag: lang.t("rail.tag.match3"), badge: progress.marketClaimable || !progress.data.market.welcomed) {
                    router.market = true
                }
                railButton("icon_garden", title: lang.t("rail.garden"), badge: progress.gardenReady > 0) {
                    router.garden = true
                }
                if progress.jarCanBreak {
                    railButton("icon_jar", title: lang.t("rail.jar"), badge: progress.jarFull) {
                        router.jar = true
                    }
                }
            } else {
                // закрытые мини-игры видно сразу: серые, с замком и уровнем открытия, по тапу - что это и когда откроется
                railButton("icon_market", title: lang.t("rail.market"), tag: lang.t("rail.tag.match3"), badge: false,
                           lockedAt: MarketBalance.unlockLevel) {
                    lockedInfo = .market
                }
                railButton("icon_garden", title: lang.t("rail.garden"), badge: false, lockedAt: MarketBalance.unlockLevel) {
                    lockedInfo = .garden
                }
            }
            if progress.welcomeActive {
                railButton("icon_gift", title: lang.t("rail.quests"), badge: progress.questsClaimable) {
                    router.open(.quests)
                }
            }
        }
    }

    /// Кнопка сбоку карты. У мини-игр снизу плашка с жанром ("3 в ряд", "Слияние"), чтобы было видно, что это отдельная игра.
    private func railButton(_ icon: String, title: String, tag: String? = nil, badge: Bool, lockedAt: Int? = nil,
                            action: @escaping () -> Void) -> some View {
        Button {
            Audio.shared.play(.button, volume: 0.6)
            action()
        } label: {
            VStack(spacing: tag == nil ? -4 : 3) {
                ZStack {
                    RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.woodDark.opacity(0.55)).offset(y: 3)
                    RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card)
                    RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(tag == nil ? Theme.paperBorder : ButtonPalette.orange.dark, lineWidth: 3)
                    SpriteImage(name: icon, size: 46)
                        .saturation(lockedAt == nil ? 1 : 0)
                        .opacity(lockedAt == nil ? 1 : 0.6)
                }
                .frame(width: 58, height: 58)
                .overlay(alignment: .topLeading) {
                    if lockedAt != nil {
                        Image(systemName: "lock.fill")
                            .font(.system(size: 12, weight: .black))
                            .foregroundColor(.white)
                            .frame(width: 24, height: 24)
                            .background(Circle().fill(Theme.woodDark))
                            .overlay(Circle().strokeBorder(Color.white, lineWidth: 2))
                            .offset(x: -6, y: -6)
                    }
                }
                .overlay(alignment: .bottom) {
                    if let tag = tag {
                        Text(tag)
                            .font(Theme.rounded(10, .black))
                            .foregroundColor(.white)
                            .outlined(ButtonPalette.orange.dark, width: 1)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                            .padding(.horizontal, 6)
                            .padding(.vertical, 2)
                            .background(Capsule().fill(LinearGradient(colors: [ButtonPalette.orange.top, ButtonPalette.orange.bottom],
                                                                      startPoint: .top, endPoint: .bottom)))
                            .overlay(Capsule().strokeBorder(ButtonPalette.orange.dark, lineWidth: 1.5))
                            .offset(y: 8)
                    }
                }
                StrokeText(text: title, size: 11, weight: .black, color: .white, stroke: Theme.woodDark, width: 1.2, drop: 1)
                    .lineLimit(2)
                    .multilineTextAlignment(.center)
                    .minimumScaleFactor(0.7)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(width: 70)
                if let level = lockedAt {
                    StrokeText(text: lang.t("lock.level", level), size: 10, weight: .black, color: Theme.gold,
                               stroke: Theme.woodDark, width: 1.2, drop: 1)
                }
            }
            .overlay(alignment: .topTrailing) {
                if badge { BadgeDot().offset(x: -2, y: -4) }
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    private var topBar: some View {
        HStack(spacing: 6) {
            Button { router.lives = true } label: { LivesPill() }.buttonStyle(PressScaleStyle())
                .accessibilityIdentifier("lives.pill")
            Button { router.open(ShopSection.coins) } label: { CoinsPill() }.buttonStyle(PressScaleStyle())
            StreakButton { router.streak = true }
            Spacer(minLength: 0)
            VIPBadge { router.open(ShopSection.offers) }
            CircleIconButton(symbol: "gearshape.fill", size: 42) { withAnimation(.easeInOut(duration: 0.22)) { router.settings = true } }
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
                        Color.clear.frame(height: 150 + MainTabBar.height)
                    }
                }
                .onAppear { scrollToCurrent(proxy) }
                .onChange(of: openedBiome) { _ in scrollToCurrent(proxy) }
                .onChange(of: scrollTarget) { target in
                    guard let target = target else { return }
                    withAnimation(.easeInOut(duration: 0.45)) { proxy.scrollTo(target, anchor: .center) }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { scrollTarget = nil }
                }
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
            // тропинка рисуется в координатах слева направо: при арабском языке не зеркалим, иначе она
            // расходится с кружками уровней
            .environment(\.layoutDirection, .leftToRight)
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
        let palette: ButtonPalette = !unlocked ? .gray : (stars > 0 ? .green : .orange)
        let size: CGFloat = current ? 72 : 60
        return VStack(spacing: 3) {
            Button {
                guard unlocked else { return }
                if progress.isPassed(level.id) || progress.hasLife {
                    play(level, .main)
                } else {
                    router.lives = true
                }
            } label: {
                ZStack {
                    Circle().fill(palette.dark).offset(y: 5)
                    Circle().fill(LinearGradient(colors: [palette.top, palette.bottom], startPoint: .top, endPoint: .bottom))
                    Circle().inset(by: 6).fill(Color.white.opacity(0.18)).frame(height: size * 0.42)
                        .frame(maxHeight: .infinity, alignment: .top).padding(.top, 2)
                    Circle().strokeBorder(level.hard ? Theme.red : palette.dark, lineWidth: level.hard ? 5 : 3.5)
                    if unlocked {
                        StrokeText(text: "\(level.id)", size: current ? 28 : 24, weight: .black, color: .white,
                                   stroke: palette.dark, width: 2, drop: 2)
                    } else {
                        SpriteImage(name: "icon_lock", size: 30)
                    }
                }
                .frame(width: size, height: size)
            }
            .buttonStyle(PressScaleStyle())
            if unlocked && stars > 0 {
                StarsRow(count: stars, size: 13, spacing: 0)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 1)
                    .background(Capsule().fill(Theme.woodDark.opacity(0.75)))
            } else if level.hard {
                Text(lang.t("map.hard"))
                    .font(Theme.rounded(11, .black))
                    .foregroundColor(.white)
                    .outlined(Theme.ribbonDark, width: 1)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.red))
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
                SpriteImage(name: "icon_lock", size: 32)
            }
        }
        .padding(.horizontal, 30)
    }

    private func soonCard(_ biome: Int) -> some View {
        Panel(padding: 12) {
            HStack(spacing: 12) {
                SpriteImage(name: "icon_pause", size: 34)
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

    /// Открытые кухни: в карточке звезд можно листать и пройденные, чтобы добрать звезды и забрать сундуки.
    private var openBiomes: [Int] { (1...Biomes.playable).filter { progress.isBiomeOpen($0) } }

    private var cardBiome: Int {
        if let b = shownBiome, progress.isBiomeOpen(b) { return b }
        return progress.mapBiome
    }

    private func hasReadyChest(_ biome: Int) -> Bool {
        (0..<Biomes.chests(biome).count).contains { progress.chestReady((biome - 1) * 3 + $0) }
    }

    /// Первый уровень кухни, где меньше 3 звезд (его стоит переиграть), иначе первый уровень.
    private func replayTarget(_ biome: Int) -> Int? {
        let levels = LevelStore.shared.levels(biome: biome)
        return (levels.first { progress.isUnlocked($0.id) && progress.stars($0.id) < 3 } ?? levels.first)?.id
    }

    private func showBiome(_ biome: Int) {
        Audio.shared.play(.button, volume: 0.5)
        withAnimation(.easeInOut(duration: 0.2)) { shownBiome = biome }
        scrollTarget = replayTarget(biome)
    }

    private func biomeArrow(_ step: Int) -> some View {
        let list = openBiomes
        let i = list.firstIndex(of: cardBiome) ?? 0
        let target = list.indices.contains(i + step) ? list[i + step] : nil
        return Button {
            if let t = target { showBiome(t) }
        } label: {
            ZStack {
                RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Theme.woodDark.opacity(0.5)).offset(y: 2)
                RoundedRectangle(cornerRadius: 10, style: .continuous).fill(Theme.card)
                RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(Theme.paperBorder, lineWidth: 2)
                Image(systemName: step < 0 ? "chevron.left" : "chevron.right")
                    .font(.system(size: 15, weight: .black))
                    .foregroundColor(Theme.brown)
                    .flipsForRightToLeftLayoutDirection(true)
            }
            .frame(width: 30, height: 30)
            .overlay(alignment: .topTrailing) {
                if let t = target, hasReadyChest(t) { BadgeDot().offset(x: 5, y: -5) }
            }
        }
        .buttonStyle(PressScaleStyle())
        .accessibilityIdentifier(step < 0 ? "biome.prev" : "biome.next")
        .opacity(target == nil ? 0.3 : 1)
        .disabled(target == nil)
    }

    private var starsCard: some View {
        let biome = cardBiome
        let total = progress.totalStars(biome: biome)
        let maxStars = Balance.levelsPerBiome * 3
        let chests = Biomes.chests(biome)
        let several = openBiomes.count > 1
        return Panel(padding: 12) {
            VStack(spacing: 8) {
                HStack(spacing: 6) {
                    if several { biomeArrow(-1) }
                    Button {
                        if let t = replayTarget(biome) {
                            Audio.shared.play(.button, volume: 0.5)
                            scrollTarget = t
                        }
                    } label: {
                        VStack(spacing: 1) {
                            Text(lang.t("biome.\(biome).name"))
                                .font(Theme.rounded(13, .bold))
                                .foregroundColor(Theme.brownSoft)
                                .lineLimit(1)
                                .minimumScaleFactor(0.7)
                            HStack(spacing: 4) {
                                SpriteImage(name: "icon_star", size: 22)
                                Text(lang.t("map.stars", total, maxStars))
                                    .font(Theme.rounded(15, .heavy))
                                    .foregroundColor(Theme.brown)
                                    .lineLimit(1)
                                    .minimumScaleFactor(0.7)
                            }
                        }
                        .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(PressScaleStyle())
                    if several { biomeArrow(1) }
                }
                GeometryReader { geo in
                    ZStack(alignment: .leading) {
                        ProgressBar(value: total, target: maxStars, color: Theme.gold, height: 14)
                        ForEach(chests.indices, id: \.self) { i in
                            chestButton((biome - 1) * 3 + i)
                                .position(x: geo.size.width * CGFloat(chests[i].stars) / CGFloat(maxStars) - 18, y: 6)
                        }
                    }
                }
                .frame(height: 30)
                if biome != progress.mapBiome && total < maxStars {
                    Text(lang.t("map.replay.hint"))
                        .font(Theme.rounded(12, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            .id(biome)
            .transition(.opacity)
        }
    }

    private func chestButton(_ index: Int) -> some View {
        let ready = progress.chestReady(index)
        let claimed = progress.chestClaimed(index)
        let crown = index % 3 == 2
        return Button {
            if ready && !claimed {
                let info = Biomes.chest(index)
                progress.claimChest(index)
                chestGranted = (lang.t(crown ? "chest.gold.title" : "chest.title", info.stars),
                                Granted(reward: ChestPopup.reward(info), card: nil))
            } else {
                chest = index
            }
        } label: {
            SpriteImage(name: claimed ? "icon_check" : (crown ? "chest_gold" : "chest_bronze"), size: crown ? 40 : 34)
                .saturation(ready || claimed ? 1 : 0.5)
                .scaleEffect(ready ? 1.15 : 1)
                .shadow(color: ready ? Theme.gold : .clear, radius: 6)
        }
        .buttonStyle(PressScaleStyle())
    }
}

/// Ворота следующей кухни: звезды предыдущей или монеты.
struct BiomeGate: View {
    let biome: Int
    let opened: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

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
            Toast.error(lang.t("common.nocoins"))
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
            PopupCard(title: lang.t("biome.opened", lang.t("biome.\(biome).name")), close: close) {
                VStack(spacing: 14) {
                    SpriteImage(name: Biomes.icon(biome), size: 120)
                        .scaleEffect(shown ? 1 : 0.4)
                        .rotationEffect(.degrees(shown ? 0 : -15))
                    Text(lang.t("biome.\(biome).intro"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 10) {
                        BackgroundThumb(id: Biomes.style(biome), width: 44)
                        Text(lang.t("biome.opened.bg", lang.t("bg." + Biomes.style(biome))))
                            .font(Theme.rounded(14, .heavy))
                            .foregroundColor(Theme.brown)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    .padding(10)
                    .background(InsetBackground())
                    Button(lang.t("intro.go"), action: close).buttonStyle(GameButtonStyle(palette: .green))
                }
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

    /// Содержимое сундука в виде обычной награды: те же плитки, что везде.
    static func reward(_ chest: Balance.Chest) -> Reward {
        Reward(coins: chest.coins, boosters: chest.boosters, unlimitedMinutes: Int(chest.unlimitedLives / 60),
               chests: chest.album.map { [$0: 1] } ?? [:])
    }

    var body: some View {
        let chest = Biomes.chest(index)
        let crown = index % 3 == 2
        let ready = progress.chestReady(index)
        let claimed = progress.chestClaimed(index)
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t(crown ? "chest.gold.title" : "chest.title", chest.stars), close: close) {
                VStack(spacing: 14) {
                    SpriteImage(name: crown ? (opened ? "chest_gold_open" : "chest_gold") : (opened ? "chest_bronze_open" : "chest_bronze"),
                                size: 120)
                        .rotationEffect(.degrees(opened ? 0 : -6))
                        .scaleEffect(opened ? 1.1 : 1)
                    RewardChips(reward: ChestPopup.reward(chest), perRow: 4, tileWidth: 60)
                    if chest.goldShelves {
                        HStack(spacing: 8) {
                            SpriteImage(name: "shelf_gold", size: 44)
                            Text(lang.t("chest.goldshelves")).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brown)
                        }
                        .padding(8)
                        .frame(maxWidth: .infinity)
                        .background(InsetBackground())
                    }
                    if claimed {
                        DoneLabel(text: lang.t("chest.claimed"))
                        Button(lang.t("common.ok"), action: close).buttonStyle(GameButtonStyle(palette: .orange))
                    } else if ready {
                        Button(lang.t("chest.open")) {
                            withAnimation(.spring(response: 0.3, dampingFraction: 0.5)) { opened = true }
                            progress.claimChest(index)
                            Haptics.success()
                            Audio.shared.play(.chest)
                        }
                        .buttonStyle(GameButtonStyle(palette: .green))
                    } else {
                        Text(lang.t("chest.need", max(0, chest.stars - progress.totalStars(biome: index / 3 + 1))))
                            .font(Theme.rounded(15, .heavy))
                            .foregroundColor(Theme.brownSoft)
                            .multilineTextAlignment(.center)
                        Button(lang.t("common.ok"), action: close).buttonStyle(GameButtonStyle(palette: .orange))
                    }
                }
            }
        }
    }
}

/// Окно жизней: сколько есть, когда следующая, пополнить за монеты, рекламу или безлимит.
struct LivesPopup: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: progress.unlimitedLives ? lang.t("lives.unlimited") : lang.t("lives.count", progress.lives, max(progress.maxLives, progress.lives)),
                      close: close) {
                VStack(spacing: 12) {
                    // с VIP сердец до 8: уменьшаем, чтобы ряд не вылезал за окно. После конца VIP жизней
                    // может остаться больше обычного максимума - показываем все
                    let hearts = max(progress.maxLives, progress.lives)
                    HStack(spacing: 2) {
                        ForEach(0..<hearts, id: \.self) { i in
                            SpriteImage(name: "icon_heart", size: hearts > 5 ? 32 : 40,
                                        silhouette: !progress.unlimitedLives && i >= progress.lives)
                        }
                    }
                    if let left = progress.unlimitedLeft {
                        TimerBadge(text: Lang.time(left))
                    } else if let next = progress.nextLifeIn {
                        Text(lang.t("lives.next", Lang.time(next)))
                            .font(Theme.rounded(16, .heavy))
                            .foregroundColor(Theme.brown)
                            .monospacedDigit()
                    }
                    Text(lang.t("lives.replay"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    if progress.lives < progress.maxLives && !progress.unlimitedLives {
                        Button {
                            if progress.refillLives() { close() } else { Toast.error(lang.t("common.nocoins")) }
                        } label: {
                            HStack(spacing: 6) { Text(lang.t("lives.refill")); CoinIcon(size: 24); Text("\(Balance.livesRefillPrice)") }
                        }
                        .buttonStyle(GameButtonStyle(palette: .orange))
                        Button {
                            Ads.shared.showRewarded(placement: "life") { ok in
                                if ok { progress.addLife() } else { Toast.error(lang.t("ads.limit")) }
                            }
                        } label: {
                            HStack(spacing: 6) { AdIcon(); Text(lang.t("lives.ad")) }
                        }
                        .buttonStyle(GameButtonStyle(palette: .green))
                        AdsLeftLabel()
                    }
                    if !progress.unlimitedLives {
                        Button {
                            Task { @MainActor in
                                switch await Store.shared.buy(.lives) {
                                case .done:
                                    Audio.shared.play(.chest)
                                    close()
                                case .unavailable:
                                    Toast.error(lang.t("shop.unavailable"))
                                case .failed:
                                    Toast.error(lang.t("shop.failed"))
                                default:
                                    break
                                }
                            }
                        } label: {
                            HStack(spacing: 6) { SpriteImage(name: "icon_unlimited", size: 28); Text(lang.t("lives.buy")); Text(Store.shared.price(.lives)) }
                        }
                        .buttonStyle(GameButtonStyle(palette: .purple))
                    }
                }
            }
        }
    }
}

/// Настройки: звук, музыка, вибрация, язык. Полный экран с шапкой.
struct SettingsScreen: View {
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var router: Router

    var body: some View {
        ZStack {
            ScreenScaffold(title: lang.t("settings.title"), back: close, coins: false, tabBar: false) {
                Panel(padding: 14) {
                    VStack(spacing: 12) {
                        toggle(lang.t("settings.music"), "icon_music", \.music)
                        divider
                        toggle(lang.t("settings.sound"), "icon_sound", \.sound)
                        divider
                        toggle(lang.t("settings.haptics"), "icon_haptics", \.haptics)
                    }
                }
                Button {
                    Audio.shared.play(.button, volume: 0.6)
                    withAnimation(.easeInOut(duration: 0.22)) { router.language = true }
                } label: {
                    HStack(spacing: 12) {
                        SpriteImage(name: "icon_globe", size: 40)
                        Text(lang.t("settings.language")).font(Theme.rounded(19, .black)).foregroundColor(Theme.brown)
                        Spacer(minLength: 4)
                        Text(lang.name).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brownSoft)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                        BackArrowShape()
                            .stroke(Theme.brownSoft, style: StrokeStyle(lineWidth: 3.5, lineCap: .round, lineJoin: .round))
                            .frame(width: 10, height: 14)
                            .rotationEffect(.degrees(180))
                            .flipsForRightToLeftLayoutDirection(true)
                    }
                    .padding(14)
                    .background(PaperBackground(radius: 18))
                }
                .buttonStyle(PressScaleStyle())
                Text(lang.t("settings.player", String(progress.playerId.prefix(8))) + " · v\(RemoteConfig.shared.version)")
                    .font(Theme.rounded(13, .heavy))
                    .foregroundColor(Color(red: 1.0, green: 0.93, blue: 0.8))
                    .outlined(Theme.woodDark, width: 1)
                    .padding(.top, 6)
            }
            if router.language {
                LanguageScreen()
                    .transition(.move(edge: .trailing))
                    .zIndex(2)
            }
        }
    }

    private var divider: some View {
        Rectangle().fill(Theme.chipBorder.opacity(0.6)).frame(height: 2)
    }

    private func close() {
        withAnimation(.easeInOut(duration: 0.22)) { router.settings = false }
    }

    private func toggle(_ title: String, _ icon: String, _ key: WritableKeyPath<GameSettings, Bool>) -> some View {
        Toggle(isOn: Binding(
            get: { progress.settings[keyPath: key] },
            set: { value in
                var settings = progress.settings
                settings[keyPath: key] = value
                progress.update(settings: settings)
            })) {
            HStack(spacing: 12) {
                SpriteImage(name: icon, size: 38)
                Text(title).font(Theme.rounded(19, .black)).foregroundColor(Theme.brown)
            }
        }
        .toggleStyle(GameToggleStyle())
    }
}

/// Выбор языка списком в стиле игры: название на своем языке, выбранный отмечен галочкой.
struct LanguageScreen: View {
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var router: Router

    var body: some View {
        ScreenScaffold(title: lang.t("settings.language"), back: close, coins: false, tabBar: false) {
            VStack(spacing: 8) {
                ForEach(Lang.options) { option in
                    let on = option.code == lang.code
                    Button {
                        Audio.shared.play(.button, volume: 0.6)
                        Haptics.light()
                        lang.set(option.code)
                    } label: {
                        HStack(spacing: 10) {
                            Text(option.name)
                                .font(Theme.rounded(18, .black))
                                .foregroundColor(Theme.brown)
                                .lineLimit(1)
                            Spacer(minLength: 4)
                            if on { SpriteImage(name: "icon_check", size: 30) }
                        }
                        .padding(.horizontal, 16)
                        .frame(height: 54)
                        .background(
                            ZStack {
                                RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Theme.woodDark.opacity(0.5)).offset(y: 3)
                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                    .fill(on ? Color(red: 1.0, green: 0.88, blue: 0.55) : Theme.card)
                                RoundedRectangle(cornerRadius: 14, style: .continuous)
                                    .strokeBorder(on ? Theme.orange : Theme.paperBorder, lineWidth: on ? 3 : 2.5)
                            }
                        )
                    }
                    .buttonStyle(PressScaleStyle())
                }
            }
        }
    }

    private func close() {
        withAnimation(.easeInOut(duration: 0.22)) { router.language = false }
    }
}

/// Закрытая мини-игра на карте.
enum LockedFeature {
    case market, garden

    var icon: String { self == .market ? "icon_market" : "icon_garden" }
    var titleKey: String { self == .market ? "rail.market" : "rail.garden" }
    var textKey: String { self == .market ? "lock.market.text" : "lock.garden.text" }
}

/// Тап по закрытой мини-игре: что это, с какого уровня откроется и сколько осталось.
struct LockedFeaturePopup: View {
    let feature: LockedFeature
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        let need = MarketBalance.unlockLevel
        let left = progress.marketLevelsLeft
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t(feature.titleKey), close: close) {
                VStack(spacing: 12) {
                    ZStack(alignment: .bottomTrailing) {
                        SpriteImage(name: feature.icon, size: 96).saturation(0.2)
                        Image(systemName: "lock.fill")
                            .font(.system(size: 20, weight: .black))
                            .foregroundColor(.white)
                            .frame(width: 40, height: 40)
                            .background(Circle().fill(Theme.woodDark))
                            .overlay(Circle().strokeBorder(Color.white, lineWidth: 2.5))
                    }
                    Text(lang.t(feature.textKey))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    VStack(spacing: 6) {
                        Text(lang.t("task.go.locked", need))
                            .font(Theme.rounded(16, .black))
                            .foregroundColor(Theme.brown)
                        ProgressBar(value: need - left, target: need, color: Theme.orange, height: 12)
                        Text(lang.t("lock.left", left))
                            .font(Theme.rounded(13, .heavy))
                            .foregroundColor(Theme.brownSoft)
                    }
                    .padding(10)
                    .background(InsetBackground())
                    Button(lang.t("common.ok"), action: close).buttonStyle(GameButtonStyle(palette: .green))
                }
            }
        }
        .accessibilityIdentifier("locked.popup")
    }
}

/// Мини-игры открылись: праздничное окно один раз, с переходом в "Продуктовый ряд".
struct FeatureOpenedPopup: View {
    let close: () -> Void
    let go: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var shown = false

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("unlock.feature.title"), close: close) {
                VStack(spacing: 14) {
                    HStack(spacing: 18) {
                        SpriteImage(name: "icon_market", size: 96)
                        SpriteImage(name: "icon_garden", size: 72)
                    }
                    .scaleEffect(shown ? 1 : 0.4)
                    .rotationEffect(.degrees(shown ? 0 : -12))
                    Text(lang.t("unlock.feature.text"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button(lang.t("unlock.feature.go"), action: go).buttonStyle(GameButtonStyle(palette: .green))
                    Button(lang.t("chest.later"), action: close).buttonStyle(GameButtonStyle(palette: .orange, height: 44, fontSize: 17))
                }
            }
        }
        .onAppear {
            Audio.shared.play(.chest)
            Haptics.success()
            withAnimation(.spring(response: 0.45, dampingFraction: 0.55)) { shown = true }
        }
    }
}
