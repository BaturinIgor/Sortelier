import SwiftUI

/// Карта "Рынка": одна глава на экране (30 уровней снизу вверх и сундуки за звезды), переключатель глав и список
/// всех глав, серия побед, вход в "Большой рецепт". 600 уровней одной лентой были бы длинным и тяжелым скроллом,
/// поэтому лента показывает только выбранную главу.
struct MarketMapView: View {
    let close: () -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var popup: Int?
    @State private var launch: MarketLaunch?
    @State private var granted: (String, Granted)?
    @State private var recipe = false
    @State private var welcome: Granted?
    /// Выбранная глава (0 - еще не выбрана, при входе берется глава текущего уровня).
    @State private var chapter = 0
    @State private var chapterList = false
    /// Окно жизней показываем здесь: окно из RootView осталось бы под экраном рынка и всплыло бы только после выхода.
    @ObservedObject private var router = Router.shared

    struct MarketLaunch: Identifiable {
        let id = UUID()
        let level: M3Level
        let pre: [M3Booster]
    }

    private let rowHeight: CGFloat = 92

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.08, style: MarketCatalog.style(chapter: shownChapter))
                .id(shownChapter)
                .transition(.opacity)
            path
            VStack {
                LinearGradient(colors: [Theme.woodDark.opacity(0.55), Theme.woodDark.opacity(0)], startPoint: .top, endPoint: .bottom)
                    .frame(height: 150)
                    .ignoresSafeArea(edges: .top)
                Spacer()
            }
            .allowsHitTesting(false)
            VStack(spacing: 8) {
                header
                HStack(spacing: 8) {
                    if progress.marketStreak > 0 { StreakChip(stage: progress.marketStreak) }
                    if HappyHour.active() { HappyHourChip() }
                    Spacer()
                    recipeButton
                }
                chapterBar
                Spacer()
                Button {
                    if chapterOf(progress.marketCurrent) != shownChapter { select(chapterOf(progress.marketCurrent)) }
                    popup = progress.marketCurrent
                } label: {
                    Text(progress.marketAllDone ? lang.t("m3.map.done") : lang.t("m3.level", progress.marketCurrent))
                }
                .buttonStyle(GameButtonStyle(palette: .orange, height: 58, fontSize: 24))
                .frame(maxWidth: 280)
                .disabled(progress.marketAllDone)
                .opacity(progress.marketAllDone ? 0.7 : 1)
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 10)
            if let id = popup, let level = MarketCatalog.shared.level(id) {
                MarketLevelPopup(level: level, close: { popup = nil }, play: { pre in
                    popup = nil
                    launch = MarketLaunch(level: level, pre: pre)
                })
            }
            if let pair = granted {
                RewardPopup(title: pair.0, granted: pair.1) { granted = nil }
            }
            if let g = welcome {
                RewardPopup(title: lang.t("m3.welcome"), granted: g) { welcome = nil }
            }
            if chapterList {
                MarketChapterList(selected: shownChapter, close: { chapterList = false }) { ch in
                    chapterList = false
                    select(ch)
                }
            }
            if router.lives {
                LivesPopup { router.lives = false }
            }
        }
        .onAppear {
            if chapter == 0 { chapter = chapterOf(progress.marketCurrent) }
            Audio.shared.setTrack(MarketCatalog.track(chapter: shownChapter))
            #if DEBUG
            if let id = UIDebug.value("uiMarketLevel").flatMap(Int.init), let level = MarketCatalog.shared.level(id) {
                launch = MarketLaunch(level: level, pre: [])
                return
            }
            if let id = UIDebug.value("uiMarketPopup").flatMap(Int.init) { popup = id }
            if let ch = UIDebug.value("uiMarketChapter").flatMap(Int.init) { chapter = ch }
            if UIDebug.flag("uiMarketChapters") { chapterList = true }
            #endif
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { welcome = progress.marketWelcome() }
        }
        .fullScreenCover(item: $launch) { item in
            MarketLevelHost(level: item.level, pre: item.pre) { next in
                launch = nil
                if let next = next, MarketCatalog.shared.level(next) != nil {
                    if chapterOf(next) != shownChapter { select(chapterOf(next)) }
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.5) { popup = next }
                }
            }
            .statusBarHidden()
            .environmentObject(PlayerProgress.shared)
            .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
        .fullScreenCover(isPresented: $recipe) {
            BigRecipeView(close: { recipe = false })
                .statusBarHidden()
                .environmentObject(PlayerProgress.shared)
                .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
        }
    }

    private func chapterOf(_ level: Int) -> Int { MarketCatalog.shared.chapter(of: level) }

    private var shownChapter: Int { chapter == 0 ? chapterOf(progress.marketCurrent) : chapter }

    private func select(_ ch: Int) {
        let ch = max(1, min(MarketCatalog.shared.chapters, ch))
        guard ch != shownChapter else { return }
        Audio.shared.play(.swoosh, volume: 0.5)
        withAnimation(.easeInOut(duration: 0.3)) { chapter = ch }
        Audio.shared.setTrack(MarketCatalog.track(chapter: ch))
    }

    /// Переключатель глав: стрелки и название, тап по названию открывает список всех глав.
    private var chapterBar: some View {
        let ch = shownChapter
        let total = MarketCatalog.shared.chapters
        let stars = progress.marketStars(chapter: ch)
        let cap = MarketCatalog.shared.levels(chapter: ch).count * 3
        return HStack(spacing: 8) {
            arrowButton("chevron.left", enabled: ch > 1) { select(ch - 1) }
            Button { chapterList = true } label: {
                VStack(spacing: 1) {
                    Text(MarketCatalog.chapterTitle(ch, lang))
                        .font(Theme.rounded(15, .black)).foregroundColor(.white).outlined(Theme.woodDark, width: 1)
                        .lineLimit(1).minimumScaleFactor(0.6)
                    HStack(spacing: 4) {
                        Text(lang.t("m3.chapter.of", ch, total))
                        SpriteImage(name: "icon_star", size: 13)
                        Text("\(stars)/\(cap)").monospacedDigit()
                        Image(systemName: "chevron.down").font(.system(size: 10, weight: .black))
                    }
                    .font(Theme.rounded(12, .heavy)).foregroundColor(Color(red: 1, green: 0.9, blue: 0.7))
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 5)
                .frame(maxWidth: .infinity)
                .background(Capsule().fill(Theme.woodDark.opacity(0.8)))
                .overlay(Capsule().strokeBorder(Theme.gold.opacity(0.8), lineWidth: 1.5))
                .overlay(alignment: .topTrailing) {
                    if (1...total).contains(where: { $0 != ch && progress.marketChapterClaimable($0) }) { BadgeDot().offset(x: 2, y: -3) }
                }
            }
            .buttonStyle(PressScaleStyle())
            arrowButton("chevron.right", enabled: ch < total && progress.isMarketChapterOpen(ch + 1)) { select(ch + 1) }
        }
    }

    private func arrowButton(_ symbol: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: symbol)
                .font(.system(size: 17, weight: .black))
                .foregroundColor(.white)
                .frame(width: 40, height: 40)
                .background(Circle().fill(Theme.woodDark.opacity(0.8)))
                .overlay(Circle().strokeBorder(Theme.gold.opacity(0.8), lineWidth: 1.5))
        }
        .buttonStyle(PressScaleStyle())
        .disabled(!enabled)
        .opacity(enabled ? 1 : 0.35)
    }

    private var header: some View {
        HStack(spacing: 8) {
            CircleIconButton(symbol: "xmark", size: 42, action: close)
            StrokeText(text: lang.t("m3.title"), size: 21, weight: .black, color: Color(red: 1.0, green: 0.95, blue: 0.84),
                       stroke: Theme.woodDark, width: 1.5, drop: 2)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .padding(.horizontal, 14)
                .frame(height: 42)
                .background(ZStack {
                    Capsule().fill(Theme.woodDark).offset(y: 3)
                    WoodBackground().clipShape(Capsule())
                    Capsule().strokeBorder(Theme.woodDark, lineWidth: 2.5)
                })
            Spacer(minLength: 4)
            // счетчики не сжимаем: длинное название ("Продуктовый ряд", "Мастерская шефа") уменьшается само
            Button { Router.shared.lives = true } label: { LivesPill() }.buttonStyle(PressScaleStyle())
                .fixedSize()
                .accessibilityIdentifier("market.lives")
            CoinsPill(plus: false).fixedSize()
        }
        .padding(.top, 6)
    }

    private var recipeButton: some View {
        Button { recipe = true } label: {
            HStack(spacing: 6) {
                SpriteImage(name: "icon_recipe", size: 34)
                VStack(alignment: .leading, spacing: 0) {
                    Text(lang.t("recipe.title")).font(Theme.rounded(13, .black)).foregroundColor(.white).outlined(Theme.woodDark, width: 1)
                    Text("\(min(progress.recipe.step, BigRecipe.steps))/\(BigRecipe.steps)")
                        .font(Theme.rounded(12, .heavy)).foregroundColor(Color(red: 1, green: 0.9, blue: 0.7))
                }
            }
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(Capsule().fill(Theme.woodDark.opacity(0.8)))
            .overlay(Capsule().strokeBorder(Theme.gold.opacity(0.8), lineWidth: 1.5))
            .overlay(alignment: .topTrailing) {
                if progress.recipe.unseen > 0 { BadgeDot().offset(x: 2, y: -4) }
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    // MARK: - Путь уровней

    private var path: some View {
        GeometryReader { geo in
            ScrollViewReader { proxy in
                ScrollView(showsIndicators: false) {
                    VStack(spacing: 0) {
                        Color.clear.frame(height: 170)
                        if shownChapter < MarketCatalog.shared.chapters {
                            nextChapterCard(shownChapter + 1)
                                .padding(.horizontal, 18)
                                .padding(.bottom, 10)
                        }
                        chapterSection(shownChapter, width: geo.size.width)
                        if shownChapter > 1 {
                            Button { select(shownChapter - 1) } label: {
                                Label(lang.t("m3.chapter.prev"), systemImage: "chevron.down")
                            }
                            .buttonStyle(GameButtonStyle(palette: .blue, height: 44, fontSize: 16))
                            .frame(maxWidth: 240)
                            .padding(.bottom, 6)
                        }
                        Color.clear.frame(height: 110)
                    }
                    .id(shownChapter)
                }
                .onAppear { scrollToFocus(proxy, animated: false) }
                .onChange(of: chapter) { _ in scrollToFocus(proxy, animated: false) }
            }
        }
        .ignoresSafeArea(edges: .bottom)
    }

    /// Текущий уровень, если он в показанной главе, иначе начало главы (низ ленты).
    private func scrollToFocus(_ proxy: ScrollViewProxy, animated: Bool) {
        let levels = MarketCatalog.shared.levels(chapter: shownChapter)
        let current = progress.marketCurrent
        let target = levels.contains(where: { $0.id == current }) ? current : (levels.first?.id ?? current)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
            proxy.scrollTo("m\(target)", anchor: .center)
        }
    }

    /// Карточка следующей главы над лентой: открыта - переход, закрыта - что нужно для открытия.
    private func nextChapterCard(_ next: Int) -> some View {
        let open = progress.isMarketChapterOpen(next)
        let first = MarketCatalog.shared.levels(chapter: next).first?.id ?? 0
        return Button {
            if open { select(next) } else { Toast.info(lang.t("m3.chapter.locked", first - 1)) }
        } label: {
            HStack(spacing: 10) {
                SpriteImage(name: open ? "icon_market" : "icon_lock", size: 34)
                VStack(alignment: .leading, spacing: 1) {
                    Text(MarketCatalog.chapterTitle(next, lang))
                        .font(Theme.rounded(15, .black)).foregroundColor(Theme.brown)
                        .lineLimit(1).minimumScaleFactor(0.7)
                    Text(open ? lang.t("m3.chapter.go") : lang.t("m3.chapter.locked", first - 1))
                        .font(Theme.rounded(12, .heavy)).foregroundColor(Theme.brownSoft)
                        .lineLimit(2)
                }
                Spacer(minLength: 4)
                if open { Image(systemName: "chevron.up").font(.system(size: 16, weight: .black)).foregroundColor(Theme.brown) }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
            .background(PaperBackground(radius: 16))
            .opacity(open ? 1 : 0.85)
        }
        .buttonStyle(PressScaleStyle())
    }

    private func chapterSection(_ chapter: Int, width: CGFloat) -> some View {
        let levels = MarketCatalog.shared.levels(chapter: chapter)
        return VStack(spacing: 0) {
            ZStack(alignment: .topLeading) {
                trail(levels, width: width)
                VStack(spacing: 0) {
                    ForEach(levels.reversed()) { level in
                        node(level)
                            .frame(height: rowHeight)
                            .offset(x: offset(level.id, width: width))
                            .id("m\(level.id)")
                    }
                }
                .frame(width: width)
            }
            .environment(\.layoutDirection, .leftToRight)
            chapterCard(chapter)
                .padding(.horizontal, 18)
                .padding(.vertical, 18)
        }
    }

    private func offset(_ id: Int, width: CGFloat) -> CGFloat {
        sin(Double(id) * 0.9) * Double(width) * 0.24
    }

    private func trail(_ levels: [M3Level], width: CGFloat) -> some View {
        Canvas { ctx, size in
            var p = Path()
            for (i, level) in levels.reversed().enumerated() {
                let pt = CGPoint(x: width / 2 + offset(level.id, width: width), y: CGFloat(i) * rowHeight + rowHeight / 2)
                if i == 0 { p.move(to: pt) } else { p.addLine(to: pt) }
            }
            ctx.stroke(p, with: .color(Theme.woodDark.opacity(0.35)), style: StrokeStyle(lineWidth: 16, lineCap: .round, lineJoin: .round))
            ctx.stroke(p, with: .color(Color(red: 1, green: 0.95, blue: 0.85).opacity(0.9)),
                       style: StrokeStyle(lineWidth: 6, lineCap: .round, lineJoin: .round, dash: [2, 12]))
        }
        .frame(width: width, height: CGFloat(levels.count) * rowHeight)
    }

    private func node(_ level: M3Level) -> some View {
        let current = level.id == progress.marketCurrent && !progress.marketAllDone
        let passed = progress.marketPassed(level.id)
        let open = progress.isMarketOpen(level.id)
        let hard = level.hard == true
        let fever = level.isFever
        return Button {
            if open { popup = level.id } else { Toast.error(lang.t("m3.map.locked")) }
        } label: {
            VStack(spacing: 0) {
                ZStack {
                    Circle().fill(Theme.woodDark).offset(y: 4)
                    Circle().fill(LinearGradient(colors: nodeColors(passed: passed, current: current, open: open, hard: hard, fever: fever),
                                                 startPoint: .top, endPoint: .bottom))
                    Circle().strokeBorder(hard ? Theme.red : (fever ? Theme.gold : Theme.woodDark), lineWidth: hard || fever ? 4 : 3)
                    if open {
                        StrokeText(text: "\(level.id)", size: current ? 24 : 20, weight: .black, color: .white,
                                   stroke: Theme.woodDark, width: 1.5, drop: 2)
                    } else {
                        SpriteImage(name: "icon_lock", size: 28)
                    }
                }
                .frame(width: current ? 66 : 54, height: current ? 66 : 54)
                .overlay(alignment: .topTrailing) {
                    if fever { SpriteImage(name: "m3_rainbow", size: 26).offset(x: 8, y: -6) }
                }
                .modifier(Pulse(active: current))
                if passed {
                    StarsRow(count: progress.marketStars(level.id), size: 13)
                        .padding(.top, 2)
                } else if hard && open {
                    Text(lang.t("map.hard")).font(Theme.rounded(11, .black)).foregroundColor(.white)
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(Capsule().fill(Theme.red))
                } else if fever {
                    Text(lang.t("m3.fever")).font(Theme.rounded(11, .black)).foregroundColor(.white)
                        .lineLimit(1).fixedSize()
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(Capsule().fill(MarketFever.gradient))
                }
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    private func nodeColors(passed: Bool, current: Bool, open: Bool, hard: Bool, fever: Bool) -> [Color] {
        if current { return [Color(red: 1, green: 0.78, blue: 0.35), Theme.orange] }
        if fever && open { return [Color(red: 1, green: 0.62, blue: 0.85), Color(red: 0.78, green: 0.3, blue: 0.75)] }
        if passed { return hard ? [Color(red: 0.95, green: 0.5, blue: 0.45), Theme.red] : [Color(red: 0.55, green: 0.85, blue: 0.45), Theme.green] }
        if open { return [Color(red: 0.6, green: 0.8, blue: 1), Theme.blue] }
        return [Color(red: 0.75, green: 0.70, blue: 0.62), Color(red: 0.55, green: 0.50, blue: 0.44)]
    }

    private func chapterCard(_ chapter: Int) -> some View {
        let stars = progress.marketStars(chapter: chapter)
        let chests = MarketBalance.chests(chapter: chapter)
        let total = MarketCatalog.shared.levels(chapter: chapter).count * 3
        return Panel(padding: 12) {
            VStack(spacing: 8) {
                HStack {
                    Text(MarketCatalog.chapterTitle(chapter, lang))
                        .font(Theme.rounded(17, .black))
                        .foregroundColor(Theme.brown)
                    Spacer()
                    SpriteImage(name: "icon_star", size: 22)
                    Text("\(stars)/\(total)").font(Theme.rounded(15, .black)).foregroundColor(Theme.brown).monospacedDigit()
                }
                GeometryReader { g in
                    ZStack(alignment: .leading) {
                        Capsule().fill(Theme.cream)
                        Capsule().fill(LinearGradient(colors: [Theme.gold, Theme.orange], startPoint: .leading, endPoint: .trailing))
                            .frame(width: max(14, g.size.width * CGFloat(min(1, Double(stars) / Double(max(1, chests.last?.stars ?? 90))))))
                        Capsule().strokeBorder(Theme.chipBorder, lineWidth: 2)
                    }
                }
                .frame(height: 14)
                HStack(spacing: 10) {
                    ForEach(chests.indices, id: \.self) { i in chestButton(chapter: chapter, index: i, chest: chests[i]) }
                }
            }
        }
    }

    private func chestButton(chapter: Int, index: Int, chest: MarketBalance.StarChest) -> some View {
        let ready = progress.marketChestReady(chapter: chapter, index: index)
        let claimed = progress.marketChestClaimed(chapter: chapter, index: index)
        let kinds: [ChestKind] = [.bronze, .silver, .gold]
        return Button {
            if ready, let g = progress.claimMarketChest(chapter: chapter, index: index) {
                Audio.shared.play(.chest)
                granted = (lang.t("m3.chest.title"), g)
            } else {
                RewardInfo.show(.chest(kinds[index], 1))
            }
        } label: {
            VStack(spacing: 0) {
                SpriteImage(name: kinds[index].sprite + (claimed ? "_open" : ""), size: 46)
                    .modifier(Pulse(active: ready))
                HStack(spacing: 2) {
                    SpriteImage(name: "icon_star", size: 14)
                    Text("\(chest.stars)").font(Theme.rounded(12, .black)).foregroundColor(Theme.brown)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 4)
            .background(InsetBackground(radius: 12, color: ready ? Color(red: 1, green: 0.93, blue: 0.6) : Theme.cream))
            .overlay(alignment: .topTrailing) { if ready { BadgeDot().offset(x: 3, y: -3) } }
        }
        .buttonStyle(PressScaleStyle())
    }
}

/// Пульс для текущего уровня и готовых наград.
struct Pulse: ViewModifier {
    let active: Bool
    @State private var on = false

    func body(content: Content) -> some View {
        content
            .scaleEffect(active && on ? 1.07 : 1)
            .onAppear {
                guard active else { return }
                withAnimation(.easeInOut(duration: 0.7).repeatForever(autoreverses: true)) { on = true }
            }
    }
}

struct HappyHourChip: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        HStack(spacing: 4) {
            SpriteImage(name: "icon_happy", size: 28)
            VStack(alignment: .leading, spacing: -1) {
                Text(lang.t("happy.title")).font(Theme.rounded(12, .black)).foregroundColor(.white).outlined(Theme.ribbonDark, width: 1)
                    .lineLimit(1)
                    .fixedSize()
                if let window = HappyHour.current(progress.now) {
                    Text("x2 · " + Lang.time(window.end.timeIntervalSince(progress.now)))
                        .font(Theme.rounded(11, .heavy)).foregroundColor(Color(red: 1, green: 0.95, blue: 0.6)).monospacedDigit()
                        .lineLimit(1)
                        .fixedSize()
                }
            }
        }
        .fixedSize()
        .padding(.horizontal, 9)
        .padding(.vertical, 4)
        .background(Capsule().fill(LinearGradient(colors: [Color(red: 0.95, green: 0.45, blue: 0.6), Color(red: 0.75, green: 0.25, blue: 0.55)],
                                                   startPoint: .top, endPoint: .bottom)))
        .overlay(Capsule().strokeBorder(Color.white.opacity(0.8), lineWidth: 1.5))
    }
}

// MARK: - Окно уровня

struct MarketLevelPopup: View {
    let level: M3Level
    let close: () -> Void
    let play: ([M3Booster]) -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var picked: Set<M3Booster> = []
    @State private var buying: M3Booster?

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("m3.level", level.id), close: close, maxWidth: 340) {
                VStack(spacing: 12) {
                    if level.hard == true {
                        Text(lang.t("m3.hard.text"))
                            .font(Theme.rounded(13, .black))
                            .foregroundColor(.white)
                            .padding(.horizontal, 10)
                            .padding(.vertical, 4)
                            .background(Capsule().fill(Theme.red))
                    } else if level.isFever {
                        Text(lang.t("m3.fever.text"))
                            .font(Theme.rounded(13, .black))
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                            .padding(.horizontal, 12)
                            .padding(.vertical, 5)
                            .background(Capsule().fill(MarketFever.gradient))
                    }
                    Text(lang.t("m3.goals")).font(Theme.rounded(14, .heavy)).foregroundColor(Theme.brownSoft)
                    HStack(spacing: 8) {
                        ForEach(level.goals.indices, id: \.self) { i in
                            VStack(spacing: 0) {
                                GoalIcon(goal: level.goals[i], size: 48)
                                Text("\(level.goals[i].count)").font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                            }
                            .frame(width: 66)
                            .padding(.vertical, 6)
                            .background(InsetBackground(radius: 12))
                        }
                    }
                    VStack(spacing: 4) {
                        Text(lang.t("m3.streak.popup"))
                            .font(Theme.rounded(13, .heavy))
                            .foregroundColor(Theme.brownSoft)
                            .multilineTextAlignment(.center)
                        StreakStages(stage: progress.marketStreak)
                    }
                    .padding(8)
                    .background(InsetBackground(radius: 12))
                    Text(lang.t("m3.pre")).font(Theme.rounded(14, .heavy)).foregroundColor(Theme.brownSoft)
                    HStack(spacing: 12) {
                        ForEach(M3Booster.preLevel) { b in preButton(b) }
                    }
                    Button(lang.t("m3.play")) {
                        guard progress.hasLife else {
                            close()
                            Router.shared.lives = true
                            return
                        }
                        play(M3Booster.preLevel.filter { picked.contains($0) })
                    }
                    .buttonStyle(GameButtonStyle(palette: .green, height: 56, fontSize: 22))
                }
            }
            if let b = buying {
                BuyMarketBoosterView(booster: b) { buying = nil }
            }
        }
    }

    private func preButton(_ b: M3Booster) -> some View {
        let count = progress.count(b)
        let on = picked.contains(b)
        return Button {
            if on {
                picked.remove(b)
            } else if count > 0 {
                picked.insert(b)
                Haptics.light()
            } else {
                buying = b
            }
        } label: {
            ZStack(alignment: .topTrailing) {
                ZStack {
                    RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.woodDark).offset(y: 3)
                    RoundedRectangle(cornerRadius: 16, style: .continuous).fill(on ? Color(red: 0.75, green: 0.95, blue: 0.6) : Theme.card)
                    RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(on ? Theme.green : Theme.paperBorder, lineWidth: on ? 3.5 : 2.5)
                    SpriteImage(name: b.icon, size: 50)
                }
                .frame(width: 64, height: 64)
                Group {
                    if on {
                        SpriteImage(name: "icon_check", size: 26)
                    } else {
                        Text(count > 0 ? "\(count)" : "+")
                            .font(Theme.rounded(14, .black))
                            .foregroundColor(.white)
                            .frame(minWidth: 24, minHeight: 24)
                            .background(ZStack {
                                Circle().fill(count > 0 ? Theme.blue : Theme.orange)
                                Circle().strokeBorder(Color.white, lineWidth: 2)
                            })
                    }
                }
                .offset(x: 6, y: -6)
            }
        }
        .buttonStyle(PressScaleStyle())
    }
}

// MARK: - Праздничные уровни

enum MarketFever {
    static let gradient = LinearGradient(colors: [Color(red: 0.98, green: 0.45, blue: 0.7), Color(red: 0.62, green: 0.32, blue: 0.9)],
                                         startPoint: .leading, endPoint: .trailing)
}

// MARK: - Список глав

/// Все главы сеткой: звезды, замок, готовый сундук. Тап по открытой главе показывает ее на карте.
struct MarketChapterList: View {
    let selected: Int
    let close: () -> Void
    let pick: (Int) -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("m3.chapters"), close: close, maxWidth: 360) {
                ScrollView(showsIndicators: false) {
                    LazyVGrid(columns: Array(repeating: GridItem(.flexible(), spacing: 8), count: 3), spacing: 8) {
                        ForEach(1...MarketCatalog.shared.chapters, id: \.self) { ch in tile(ch) }
                    }
                    .padding(.vertical, 4)
                }
                .frame(maxHeight: 460)
            }
            .padding(.horizontal, 12)
        }
    }

    private static let tints: [[Color]] = [
        [Color(red: 1, green: 0.78, blue: 0.55), Color(red: 0.93, green: 0.55, blue: 0.35)],
        [Color(red: 0.8, green: 0.7, blue: 1), Color(red: 0.55, green: 0.42, blue: 0.85)],
        [Color(red: 0.6, green: 0.88, blue: 0.5), Color(red: 0.3, green: 0.65, blue: 0.3)],
        [Color(red: 1, green: 0.65, blue: 0.7), Color(red: 0.85, green: 0.35, blue: 0.45)],
        [Color(red: 0.55, green: 0.85, blue: 1), Color(red: 0.25, green: 0.55, blue: 0.85)],
        [Color(red: 1, green: 0.88, blue: 0.45), Color(red: 0.9, green: 0.62, blue: 0.2)],
    ]

    static func tint(_ ch: Int) -> [Color] { tints[(max(1, ch) - 1) % tints.count] }

    private func tile(_ ch: Int) -> some View {
        let open = progress.isMarketChapterOpen(ch)
        let levels = MarketCatalog.shared.levels(chapter: ch)
        let stars = progress.marketStars(chapter: ch)
        let current = levels.contains { $0.id == progress.marketCurrent } && !progress.marketAllDone
        let done = !levels.isEmpty && levels.allSatisfy { progress.marketPassed($0.id) }
        return Button {
            if open { pick(ch) } else { Toast.info(lang.t("m3.chapter.locked", (levels.first?.id ?? 1) - 1)) }
        } label: {
            VStack(spacing: 3) {
                ZStack {
                    // цветная плашка вместо фона главы: 20 больших картинок в одном окне - лишняя память
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .fill(LinearGradient(colors: open ? Self.tint(ch) : [Color(red: 0.75, green: 0.70, blue: 0.62), Color(red: 0.55, green: 0.50, blue: 0.44)],
                                             startPoint: .top, endPoint: .bottom))
                    RoundedRectangle(cornerRadius: 10, style: .continuous).strokeBorder(Theme.woodDark.opacity(0.6), lineWidth: 2)
                    if open {
                        StrokeText(text: "\(ch)", size: 24, weight: .black, color: .white, stroke: Theme.woodDark, width: 1.5, drop: 2)
                    } else {
                        SpriteImage(name: "icon_lock", size: 28)
                    }
                }
                .frame(height: 50)
                Text(MarketCatalog.chapterTitle(ch, lang))
                    .font(Theme.rounded(11, .black)).foregroundColor(Theme.brown)
                    .lineLimit(2).multilineTextAlignment(.center).minimumScaleFactor(0.7)
                    .frame(height: 28)
                HStack(spacing: 2) {
                    SpriteImage(name: done ? "icon_check" : "icon_star", size: 13)
                    Text("\(stars)/\(levels.count * 3)").font(Theme.rounded(11, .black)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
            }
            .padding(6)
            .background(InsetBackground(radius: 14, color: ch == selected ? Color(red: 1, green: 0.93, blue: 0.6) : Theme.cream))
            .overlay(
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .strokeBorder(current ? Theme.orange : Color.clear, lineWidth: 3)
            )
            .overlay(alignment: .topTrailing) {
                if progress.marketChapterClaimable(ch) { BadgeDot().offset(x: 3, y: -3) }
            }
        }
        .buttonStyle(PressScaleStyle())
    }
}
