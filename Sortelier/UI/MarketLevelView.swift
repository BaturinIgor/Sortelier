import SwiftUI
import SpriteKit

/// Уровень "Рынка" поверх всего. close(next) - вернуться на карту рынка; next - открыть окно следующего уровня.
struct MarketLevelHost: View {
    let level: M3Level
    let pre: [M3Booster]
    let close: (_ next: Int?) -> Void
    @StateObject private var model: Match3Model

    init(level: M3Level, pre: [M3Booster], close: @escaping (_ next: Int?) -> Void) {
        self.level = level
        self.pre = pre
        self.close = close
        _model = StateObject(wrappedValue: Match3Model(level: level, pre: pre))
    }

    var body: some View {
        MarketLevelContent(model: model, close: close)
    }
}

struct MarketLevelContent: View {
    @ObservedObject var model: Match3Model
    let close: (_ next: Int?) -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var paused = false
    @State private var intro: String?
    @State private var buying: M3Booster?
    @State private var criticBanner = false

    private var overlayVisible: Bool { paused || intro != nil || buying != nil || criticBanner }

    var body: some View {
        GeometryReader { geo in
            ZStack {
                KitchenBackground(veil: 0.05, style: MarketCatalog.style(chapter: model.level.chapter))
                VStack(spacing: 6) {
                    Color.clear.frame(height: 52)
                    GoalsPanel(model: model)
                    Spacer()
                }
                .padding(.horizontal, 12)
                SpriteView(scene: model.scene, options: [.allowsTransparency])
                    .ignoresSafeArea()
                VStack(spacing: 6) {
                    topBar
                    Spacer()
                    if model.targeting != nil { targetingHint }
                    boosterBar
                        .background(GeometryReader { g in
                            Color.clear.onAppear { model.boosterFrame = g.frame(in: .global) }
                        })
                }
                .padding(.horizontal, 12)
                .padding(.bottom, 6)
                overlays
            }
            .onAppear {
                model.scene.hudHeight = geo.safeAreaInsets.top + 58 + 96
                model.scene.bottomReserved = geo.safeAreaInsets.bottom + 92
                Audio.shared.setTrack(model.level.chapter == 1 ? "music_italy" : "music_bakery")
                if let kind = model.level.intro, !progress.seenIntro("m3." + kind) {
                    intro = kind
                } else if model.critic {
                    showCritic()
                } else {
                    model.start()
                }
            }
        }
        .onChange(of: overlayVisible) { visible in
            model.overlay = visible
            model.scene.isPaused = visible && !criticBanner
        }
    }

    private func showCritic() {
        criticBanner = true
        Audio.shared.play(.customer, volume: 0.7)
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.4) {
            withAnimation(.easeOut(duration: 0.25)) { criticBanner = false }
            model.start()
        }
    }

    // MARK: - Панели

    private var topBar: some View {
        HStack(spacing: 10) {
            CircleIconButton(symbol: "pause.fill", size: 42) {
                guard model.phase == .playing || model.phase == .starting else { return }
                paused = true
            }
            StrokeText(text: lang.t("m3.level", model.level.id), size: 19, weight: .black, color: Color(red: 1.0, green: 0.95, blue: 0.84),
                       stroke: Theme.woodDark, width: 1.5, drop: 2)
                .lineLimit(1)
                .padding(.horizontal, 16)
                .frame(minHeight: 44)
                .background(WoodTray(radius: 18))
            if model.level.hard == true {
                Text(lang.t("map.hard"))
                    .font(Theme.rounded(13, .black))
                    .foregroundColor(.white)
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                    .background(Capsule().fill(Theme.red))
                    .overlay(Capsule().strokeBorder(Color.white, lineWidth: 2))
            }
            Spacer()
            if model.streakAtStart > 0 {
                StreakChip(stage: model.streakAtStart)
            }
        }
        .padding(.top, 6)
        .frame(height: 52)
    }

    private var targetingHint: some View {
        HStack(spacing: 8) {
            if let b = model.targeting { SpriteImage(name: b.icon, size: 30) }
            Text(lang.t("m3.target." + (model.targeting?.rawValue ?? "mallet")))
                .font(Theme.rounded(15, .heavy))
                .foregroundColor(.white)
                .outlined(Theme.woodDark, width: 1)
            Button { model.targeting = nil } label: { CloseGlyph(size: 26) }.buttonStyle(PressScaleStyle())
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 8)
        .background(Capsule().fill(Theme.woodDark.opacity(0.85)))
        .transition(.scale.combined(with: .opacity))
    }

    private var boosterBar: some View {
        HStack(spacing: 12) {
            ForEach(M3Booster.inLevel) { b in boosterButton(b) }
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 16)
        .background(WoodTray(radius: 22))
    }

    private func boosterButton(_ b: M3Booster) -> some View {
        let count = progress.count(b)
        let active = model.targeting == b
        return Button {
            guard model.phase == .playing else { return }
            withAnimation(.spring(response: 0.25, dampingFraction: 0.7)) {
                if !model.pick(b) { buying = b }
            }
        } label: {
            ZStack(alignment: .topTrailing) {
                ZStack {
                    RoundedRectangle(cornerRadius: 15, style: .continuous).fill(Theme.woodDark).offset(y: 3)
                    RoundedRectangle(cornerRadius: 15, style: .continuous).fill(active ? Theme.gold : Theme.card)
                    RoundedRectangle(cornerRadius: 15, style: .continuous).strokeBorder(active ? Color.white : Theme.paperBorder, lineWidth: active ? 3 : 2.5)
                    SpriteImage(name: b.icon, size: 46)
                }
                .frame(width: 56, height: 56)
                .scaleEffect(active ? 1.1 : 1)
                Text(count > 0 ? "\(count)" : "+")
                    .font(Theme.rounded(14, .black))
                    .foregroundColor(.white)
                    .outlined(count > 0 ? ButtonPalette.green.dark : ButtonPalette.orange.dark, width: 1)
                    .frame(minWidth: 24, minHeight: 24)
                    .background(ZStack {
                        Circle().fill(count > 0 ? Theme.green : Theme.orange)
                        Circle().strokeBorder(Color.white, lineWidth: 2)
                    })
                    .offset(x: 6, y: -6)
            }
        }
        .buttonStyle(PressScaleStyle())
    }

    // MARK: - Окна

    @ViewBuilder
    private var overlays: some View {
        if criticBanner {
            CriticArrivalView().transition(.scale(scale: 0.8).combined(with: .opacity))
        } else if let kind = intro {
            MarketIntroView(kind: kind) {
                progress.markIntro("m3." + kind)
                intro = nil
                if model.critic { showCritic() } else { model.start() }
            }
        } else if model.phase == .won, let result = model.result {
            MarketWinView(model: model, result: result, next: { close(result.level + 1) }, map: { close(nil) })
        } else if model.phase == .outOfMoves {
            OutOfMovesView(model: model)
        } else if model.phase == .lost {
            MarketLoseView(model: model, retry: { close(model.level.id) }, map: { close(nil) })
        } else if paused {
            MarketPauseView(moved: model.moved, streak: model.streakAtStart, resume: { paused = false }, exit: {
                paused = false
                model.abandon()
                close(nil)
            })
        } else if let b = buying {
            BuyMarketBoosterView(booster: b) { buying = nil }
        }
    }
}

/// Деревянная подложка панелей уровня.
struct WoodTray: View {
    var radius: CGFloat = 22

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: radius, style: .continuous).fill(Theme.woodDark).offset(y: 4)
            WoodBackground().clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
            RoundedRectangle(cornerRadius: radius, style: .continuous).strokeBorder(Theme.woodDark, lineWidth: 3)
        }
    }
}

// MARK: - Панель целей

struct GoalsPanel: View {
    @ObservedObject var model: Match3Model
    @EnvironmentObject private var lang: Lang

    var body: some View {
        HStack(spacing: 10) {
            VStack(spacing: -2) {
                Text(lang.t("m3.moves"))
                    .font(Theme.rounded(12, .black))
                    .foregroundColor(Color(red: 1.0, green: 0.9, blue: 0.7))
                    .outlined(Theme.woodDark, width: 1)
                StrokeText(text: "\(model.movesLeft)", size: 34, weight: .black,
                           color: model.movesLeft <= 3 && model.phase == .playing ? Color(red: 1, green: 0.55, blue: 0.45) : .white,
                           stroke: Theme.woodDark, width: 2, drop: 2)
                    .monospacedDigit()
                    .animation(.spring(response: 0.25, dampingFraction: 0.5), value: model.movesLeft)
            }
            .frame(width: 74, height: 74)
            .background(
                ZStack {
                    Circle().fill(Theme.woodDark).offset(y: 3)
                    Circle().fill(RadialGradient(colors: [Color(red: 0.98, green: 0.62, blue: 0.25), Color(red: 0.80, green: 0.36, blue: 0.10)],
                                                 center: .init(x: 0.5, y: 0.3), startRadius: 2, endRadius: 46))
                    Circle().strokeBorder(Theme.woodDark, lineWidth: 3)
                }
            )
            .background(GeometryReader { g in
                Color.clear
                    .onAppear { model.movesFrame = g.frame(in: .global) }
                    .onChange(of: g.frame(in: .global)) { model.movesFrame = $0 }
            })
            HStack(spacing: 6) {
                ForEach(model.level.goals.indices, id: \.self) { i in
                    GoalCell(goal: model.level.goals[i], left: model.shown[i], pulse: model.goalPulse[i])
                        .background(GeometryReader { g in
                            Color.clear
                                .onAppear { model.goalFrames[i] = g.frame(in: .global) }
                                .onChange(of: g.frame(in: .global)) { model.goalFrames[i] = $0 }
                        })
                }
            }
            .frame(maxWidth: .infinity)
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 8)
        .background(WoodTray(radius: 24))
        .frame(height: 92)
    }
}

struct GoalCell: View {
    let goal: M3Goal
    let left: Int
    let pulse: Int
    @State private var scale: CGFloat = 1

    var body: some View {
        VStack(spacing: 0) {
            GoalIcon(goal: goal, size: 44)
                .scaleEffect(scale)
            ZStack {
                if left == 0 {
                    SpriteImage(name: "icon_check", size: 24)
                        .transition(.scale.combined(with: .opacity))
                } else {
                    Text("\(left)")
                        .font(Theme.rounded(18, .black))
                        .foregroundColor(.white)
                        .outlined(Theme.woodDark, width: 1.4)
                        .monospacedDigit()
                }
            }
            .frame(height: 24)
            .animation(.spring(response: 0.3, dampingFraction: 0.55), value: left == 0)
        }
        .frame(width: 58)
        .padding(.vertical, 4)
        .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Color.black.opacity(0.18)))
        .onChange(of: pulse) { _ in
            scale = 1.28
            withAnimation(.spring(response: 0.28, dampingFraction: 0.45)) { scale = 1 }
        }
    }
}

/// Иконка цели: продукт, ящик, лед, варенье.
struct GoalIcon: View {
    let goal: M3Goal
    var size: CGFloat = 44

    var body: some View {
        switch goal.type {
        case "collect": SpriteImage(name: goal.item ?? "tomato", size: size)
        case "crate": SpriteImage(name: "m3_crate_1", size: size)
        case "jam": SpriteImage(name: "m3_jam", size: size)
        default: IceGlyph(size: size)
        }
    }
}

struct IceGlyph: View {
    var size: CGFloat = 44

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.2, style: .continuous)
                .fill(LinearGradient(colors: [Color(red: 0.88, green: 0.97, blue: 1), Color(red: 0.55, green: 0.80, blue: 0.98)],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
            RoundedRectangle(cornerRadius: size * 0.2, style: .continuous).strokeBorder(Color.white, lineWidth: 2.5)
            Capsule().fill(Color.white.opacity(0.9)).frame(width: size * 0.08, height: size * 0.32).rotationEffect(.degrees(40))
                .offset(x: -size * 0.18, y: -size * 0.12)
        }
        .frame(width: size * 0.82, height: size * 0.82)
        .frame(width: size, height: size)
    }
}

/// Ступень серии побед: 5 делений.
struct StreakChip: View {
    let stage: Int
    @EnvironmentObject private var lang: Lang

    var body: some View {
        HStack(spacing: 4) {
            SpriteImage(name: "icon_flame", size: 26)
            HStack(spacing: 2) {
                ForEach(0..<MarketBalance.streakMax, id: \.self) { i in
                    Capsule().fill(i < stage ? Theme.orange : Color.black.opacity(0.3)).frame(width: 9, height: 14)
                }
            }
        }
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(Capsule().fill(Theme.woodDark.opacity(0.75)))
        .overlay(Capsule().strokeBorder(Theme.orange.opacity(0.8), lineWidth: 1.5))
    }
}

// MARK: - Окна уровня

struct MarketPauseView: View {
    let moved: Bool
    let streak: Int
    let resume: () -> Void
    let exit: () -> Void
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim()
            PopupCard(title: lang.t("pause.title"), close: resume, maxWidth: 300) {
                VStack(spacing: 12) {
                    if moved {
                        Text(lang.t(streak > 0 ? "m3.pause.streak" : "pause.lifewarning"))
                            .font(Theme.rounded(14, .semibold))
                            .foregroundColor(Theme.red)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Button(lang.t("pause.resume"), action: resume).buttonStyle(GameButtonStyle(palette: .green))
                    Button(lang.t("pause.exit"), action: exit).buttonStyle(GameButtonStyle(palette: .paper))
                }
            }
        }
    }
}

struct OutOfMovesView: View {
    @ObservedObject var model: Match3Model
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress
    @State private var confirm = false

    var body: some View {
        ZStack {
            Dim()
            PopupCard(title: lang.t("m3.out.title"), maxWidth: 330) {
                VStack(spacing: 12) {
                    HStack(spacing: 8) {
                        ForEach(model.level.goals.indices.filter { model.board.remaining($0) > 0 }, id: \.self) { i in
                            VStack(spacing: 0) {
                                GoalIcon(goal: model.level.goals[i], size: 46)
                                Text("\(model.board.remaining(i))").font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                            }
                            .frame(width: 64)
                            .padding(.vertical, 6)
                            .background(InsetBackground(radius: 12))
                        }
                    }
                    Text(lang.t("m3.out.text", MarketBalance.extraMoves))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button {
                        if !model.buyMoves() { Toast.error(lang.t("common.nocoins")) }
                    } label: {
                        HStack(spacing: 6) { Text(lang.t("m3.out.buy", MarketBalance.extraMoves)); CoinIcon(size: 24); Text("\(model.extraPrice)") }
                    }
                    .buttonStyle(GameButtonStyle(palette: .orange))
                    if !model.adUsed {
                        Button {
                            model.adMoves { ok in if !ok { Toast.error(lang.t("ads.limit")) } }
                        } label: {
                            HStack { AdIcon(); Text(lang.t("m3.out.ad", MarketBalance.extraMoves)) }
                        }
                        .buttonStyle(GameButtonStyle(palette: .green))
                        AdsLeftLabel()
                    }
                    if confirm {
                        Text(lang.t(model.streakAtStart > 0 ? "m3.out.lose.streak" : "m3.out.lose"))
                            .font(Theme.rounded(14, .bold))
                            .foregroundColor(Theme.red)
                            .multilineTextAlignment(.center)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Button(lang.t(confirm ? "m3.out.confirm" : "m3.out.giveup")) {
                        if confirm { model.giveUp() } else { withAnimation { confirm = true } }
                    }
                    .buttonStyle(GameButtonStyle(palette: .paper))
                }
            }
        }
    }
}

struct MarketWinView: View {
    @ObservedObject var model: Match3Model
    let result: MarketResult
    let next: () -> Void
    let map: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var shown = 0
    @State private var coins = 0

    var body: some View {
        ZStack {
            Dim()
            PopupCard(title: lang.t("win.title"), maxWidth: 340) {
                VStack(spacing: 12) {
                    HStack(spacing: 4) {
                        ForEach(0..<3, id: \.self) { i in
                            SpriteImage(name: "icon_star", size: i == 1 ? 78 : 62, silhouette: i >= shown)
                                .scaleEffect(i < shown ? 1 : 0.7)
                                .offset(y: i == 1 ? -8 : 0)
                        }
                    }
                    HStack(spacing: 8) {
                        CoinIcon(size: 30)
                        Text("+\(coins)").font(Theme.rounded(26, .black)).foregroundColor(Theme.brown).monospacedDigit()
                    }
                    .padding(.horizontal, 18)
                    .padding(.vertical, 6)
                    .background(InsetBackground())
                    VStack(spacing: 8) {
                        streakLine
                        if !result.bonus.isEmpty {
                            RewardLine(symbol: "icon_gift", color: Theme.green, title: lang.t("m3.win.bonus"),
                                       granted: Granted(reward: result.bonus, card: nil))
                        }
                        ForEach(result.events) { gain in
                            RewardLine(symbol: EventUI.icon(gain.kind), color: EventUI.color(gain.kind),
                                       title: EventUI.gainText(gain, lang: lang), granted: nil)
                        }
                        if result.recipeSteps > 0 {
                            RewardLine(symbol: "icon_recipe", color: Theme.orange, title: lang.t("recipe.win"), granted: nil)
                        }
                        if result.jar > 0 {
                            RewardLine(symbol: "icon_jar", color: Theme.gold, title: lang.t("jar.win", result.jar), granted: nil)
                        }
                        if result.happyHour {
                            RewardLine(symbol: "icon_happy", color: Theme.gold, title: lang.t("happy.win"), granted: nil)
                        }
                    }
                    if let review = result.critic {
                        CriticReviewCard(review: review)
                    }
                    HStack(spacing: 10) {
                        Button(lang.t("win.map"), action: map).buttonStyle(GameButtonStyle(palette: .paper))
                        if MarketCatalog.shared.level(result.level + 1) != nil {
                            Button(lang.t("win.next"), action: next).buttonStyle(GameButtonStyle(palette: .orange))
                        }
                    }
                }
            }
        }
        .onAppear {
            Audio.shared.play(.win, volume: 0.8)
            for i in 1...max(1, result.stars) {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.35 + 0.3 * Double(i)) {
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.45)) { shown = i }
                    Audio.shared.play(i == 1 ? .star1 : (i == 2 ? .star2 : .star3))
                    Haptics.light()
                }
            }
            let steps = 20
            for k in 1...steps {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3 + Double(k) * 0.035) {
                    coins = result.coins * k / steps
                }
            }
        }
    }

    private var streakLine: some View {
        VStack(spacing: 4) {
            HStack(spacing: 6) {
                SpriteImage(name: "icon_flame", size: 24)
                Text(lang.t("m3.streak.title", min(result.streak, MarketBalance.streakMax)))
                    .font(Theme.rounded(15, .heavy))
                    .foregroundColor(Theme.brown)
            }
            StreakStages(stage: result.streak, animateFrom: model.streakAtStart)
        }
    }
}

/// Пять ступеней серии побед с иконками того, что ставится на поле.
struct StreakStages: View {
    let stage: Int
    var animateFrom: Int?
    var broken = false
    @State private var lit = 0

    var body: some View {
        HStack(spacing: 4) {
            ForEach(0..<MarketBalance.streakMax, id: \.self) { i in
                let on = i < lit
                VStack(spacing: 1) {
                    ZStack {
                        Circle().fill(on ? Theme.orange : Theme.cream)
                        Circle().strokeBorder(on ? ButtonPalette.orange.dark : Theme.chipBorder, lineWidth: 2)
                        Text("\(i + 1)").font(Theme.rounded(13, .black)).foregroundColor(on ? .white : Theme.brownSoft)
                    }
                    .frame(width: 26, height: 26)
                    .scaleEffect(on && i == lit - 1 ? 1.15 : 1)
                    HStack(spacing: -6) {
                        ForEach(Array(MarketBalance.streak[i].suffix(2).enumerated()), id: \.offset) { _, s in
                            SpriteImage(name: s.sprite, size: 22)
                        }
                    }
                    .opacity(on ? 1 : 0.45)
                }
                .frame(maxWidth: .infinity)
                .rotationEffect(.degrees(broken && i < (animateFrom ?? 0) ? Double((i % 2 == 0 ? -1 : 1) * 12) : 0))
                .offset(y: broken && i < (animateFrom ?? 0) ? 6 : 0)
            }
        }
        .onAppear {
            let from = animateFrom ?? stage
            lit = broken ? from : min(from, stage)
            if broken {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.6) {
                    withAnimation(.spring(response: 0.4, dampingFraction: 0.5)) { lit = 0 }
                    Haptics.warning()
                }
            } else if stage > from {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) {
                    withAnimation(.spring(response: 0.35, dampingFraction: 0.45)) { lit = min(stage, MarketBalance.streakMax) }
                    Audio.shared.play(.combo, volume: 0.5)
                }
            }
        }
    }
}

struct MarketLoseView: View {
    @ObservedObject var model: Match3Model
    let retry: () -> Void
    let map: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        ZStack {
            Dim()
            PopupCard(title: lang.t("m3.lose.title"), maxWidth: 330) {
                VStack(spacing: 12) {
                    SpriteImage(name: "icon_heart", size: 70)
                        .overlay(Text("-1").font(Theme.rounded(20, .black)).foregroundColor(.white).outlined(Theme.ribbonDark, width: 1.4))
                        .opacity(model.moved ? 1 : 0.4)
                    if model.streakAtStart > 0 {
                        Text(lang.t("m3.lose.streak"))
                            .font(Theme.rounded(15, .heavy))
                            .foregroundColor(Theme.red)
                        StreakStages(stage: 0, animateFrom: model.streakAtStart, broken: true)
                    }
                    HStack(spacing: 10) {
                        Button(lang.t("win.map"), action: map).buttonStyle(GameButtonStyle(palette: .paper))
                        Button(lang.t("m3.retry")) {
                            if progress.hasLife { retry() } else { map(); Router.shared.lives = true }
                        }
                        .buttonStyle(GameButtonStyle(palette: .orange))
                    }
                }
            }
        }
    }
}

struct BuyMarketBoosterView: View {
    let booster: M3Booster
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("m3.booster." + booster.rawValue), close: close, maxWidth: 310) {
                VStack(spacing: 14) {
                    SpriteImage(name: booster.icon, size: 96)
                    Text(lang.t("m3.booster." + booster.rawValue + ".text"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button {
                        if progress.buy(booster) { close() } else { Toast.error(lang.t("common.nocoins")) }
                    } label: {
                        HStack(spacing: 6) { Text(lang.t("booster.buy")); CoinIcon(size: 24); Text("\(MarketBalance.price(booster))") }
                    }
                    .buttonStyle(GameButtonStyle(palette: .green))
                }
            }
        }
    }
}

// MARK: - Обучение

struct MarketIntroView: View {
    let kind: String
    let close: () -> Void
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim()
            Panel(padding: 22) {
                VStack(spacing: 16) {
                    illustration
                    Text(lang.t("m3.intro.\(kind).title"))
                        .font(Theme.rounded(24, .heavy))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                    Text(lang.t("m3.intro.\(kind).text"))
                        .font(Theme.rounded(16, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button(lang.t("intro.go"), action: close).buttonStyle(BigButtonStyle())
                }
                .frame(maxWidth: 310)
            }
        }
    }

    private func row(_ items: [String], size: CGFloat = 44) -> some View {
        HStack(spacing: 2) { ForEach(Array(items.enumerated()), id: \.offset) { _, n in SpriteImage(name: n, size: size) } }
    }

    private var arrow: some View {
        Image(systemName: "arrow.right").font(.system(size: 22, weight: .black)).foregroundColor(Theme.brownSoft)
    }

    @ViewBuilder
    private var illustration: some View {
        switch kind {
        case "basic":
            row(["tomato", "tomato", "tomato"], size: 58)
        case "pin":
            HStack(spacing: 8) { row(["cheese", "cheese", "cheese", "cheese"], size: 40); arrow; SpriteImage(name: "m3_pin", size: 60) }
        case "whisk":
            HStack(spacing: 8) {
                VStack(spacing: 2) { row(["lime", "lime"], size: 40); row(["lime", "lime"], size: 40) }
                arrow
                SpriteImage(name: "m3_whisk", size: 64)
            }
        case "bomb":
            HStack(spacing: 8) {
                VStack(alignment: .leading, spacing: 2) { row(["grapes", "grapes", "grapes"], size: 34); SpriteImage(name: "grapes", size: 34); SpriteImage(name: "grapes", size: 34) }
                arrow
                SpriteImage(name: "m3_bomb", size: 64)
            }
        case "rainbow":
            HStack(spacing: 6) { row(["milk", "milk", "milk", "milk", "milk"], size: 34); arrow; SpriteImage(name: "m3_rainbow", size: 60) }
        case "combo":
            HStack(spacing: 6) {
                SpriteImage(name: "m3_pin", size: 56)
                Text("+").font(Theme.rounded(26, .black)).foregroundColor(Theme.brownSoft)
                SpriteImage(name: "m3_bomb", size: 56)
                Text("=").font(Theme.rounded(26, .black)).foregroundColor(Theme.brownSoft)
                SpriteImage(name: "icon_flame", size: 56)
            }
        case "crate", "crate2", "crate3":
            HStack(spacing: 6) {
                SpriteImage(name: "m3_crate_1", size: 60)
                if kind != "crate" { SpriteImage(name: "m3_crate_2", size: 60) }
                if kind == "crate3" { SpriteImage(name: "m3_crate_3", size: 60) }
            }
        case "ice", "ice2":
            ZStack {
                SpriteImage(name: "cheese", size: 64)
                IceGlyph(size: 72).opacity(kind == "ice2" ? 0.85 : 0.6)
            }
        case "jam":
            ZStack {
                SpriteImage(name: "m3_jam", size: 76)
                SpriteImage(name: "tomato", size: 52)
            }
        case "carrot":
            row(["tomato", "lime", "cheese", "grapes", "milk", "carrot"], size: 40)
        default:
            SpriteImage(name: "icon_market", size: 80)
        }
    }
}
