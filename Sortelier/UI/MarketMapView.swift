import SwiftUI

/// Карта "Рынка": две главы по 30 уровней снизу вверх, сундуки за звезды, серия побед, вход в "Большой рецепт".
struct MarketMapView: View {
    let close: () -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var popup: Int?
    @State private var launch: MarketLaunch?
    @State private var granted: (String, Granted)?
    @State private var recipe = false
    @State private var welcome: Granted?

    struct MarketLaunch: Identifiable {
        let id = UUID()
        let level: M3Level
        let pre: [M3Booster]
    }

    private let rowHeight: CGFloat = 92

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.08, style: MarketCatalog.style(chapter: chapterOf(progress.marketCurrent)))
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
                Spacer()
                Button {
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
        }
        .onAppear {
            Audio.shared.setTrack("music_italy")
            #if DEBUG
            if let id = UIDebug.value("uiMarketLevel").flatMap(Int.init), let level = MarketCatalog.shared.level(id) {
                launch = MarketLaunch(level: level, pre: [])
                return
            }
            if let id = UIDebug.value("uiMarketPopup").flatMap(Int.init) { popup = id }
            #endif
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { welcome = progress.marketWelcome() }
        }
        .fullScreenCover(item: $launch) { item in
            MarketLevelHost(level: item.level, pre: item.pre) { next in
                launch = nil
                Audio.shared.setTrack("music_italy")
                if let next = next, MarketCatalog.shared.level(next) != nil {
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

    private func chapterOf(_ level: Int) -> Int { MarketCatalog.shared.level(level)?.chapter ?? 1 }

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
                .layoutPriority(1)
            Spacer(minLength: 4)
            Button { Router.shared.lives = true } label: { LivesPill() }.buttonStyle(PressScaleStyle())
            CoinsPill(plus: false)
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
                        Color.clear.frame(height: 120)
                        ForEach((1...MarketCatalog.shared.chapters).reversed(), id: \.self) { ch in
                            chapterSection(ch, width: geo.size.width)
                        }
                        Color.clear.frame(height: 110)
                    }
                }
                .onAppear {
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) {
                        proxy.scrollTo("m\(progress.marketCurrent)", anchor: .center)
                    }
                }
            }
        }
        .ignoresSafeArea(edges: .bottom)
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
        return Button {
            if open { popup = level.id } else { Toast.error(lang.t("m3.map.locked")) }
        } label: {
            VStack(spacing: 0) {
                ZStack {
                    Circle().fill(Theme.woodDark).offset(y: 4)
                    Circle().fill(LinearGradient(colors: nodeColors(passed: passed, current: current, open: open, hard: hard),
                                                 startPoint: .top, endPoint: .bottom))
                    Circle().strokeBorder(hard ? Theme.red : Theme.woodDark, lineWidth: hard ? 4 : 3)
                    if open {
                        StrokeText(text: "\(level.id)", size: current ? 24 : 20, weight: .black, color: .white,
                                   stroke: Theme.woodDark, width: 1.5, drop: 2)
                    } else {
                        SpriteImage(name: "icon_lock", size: 28)
                    }
                }
                .frame(width: current ? 66 : 54, height: current ? 66 : 54)
                .modifier(Pulse(active: current))
                if passed {
                    StarsRow(count: progress.marketStars(level.id), size: 13)
                        .padding(.top, 2)
                } else if hard && open {
                    Text(lang.t("map.hard")).font(Theme.rounded(11, .black)).foregroundColor(.white)
                        .padding(.horizontal, 6).padding(.vertical, 1)
                        .background(Capsule().fill(Theme.red))
                }
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    private func nodeColors(passed: Bool, current: Bool, open: Bool, hard: Bool) -> [Color] {
        if current { return [Color(red: 1, green: 0.78, blue: 0.35), Theme.orange] }
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
                    Text(lang.t("m3.chapter.\(chapter)"))
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
