import SwiftUI
import SpriteKit

/// Держит уровень и позволяет перейти к следующему без возврата на карту.
struct LevelHost: View {
    @State private var level: LevelData
    @State private var mode: PlayMode
    @State private var token = UUID()
    let close: () -> Void

    init(level: LevelData, mode: PlayMode = .main, close: @escaping () -> Void) {
        _level = State(initialValue: level)
        _mode = State(initialValue: mode)
        self.close = close
    }

    var body: some View {
        LevelScreen(level: level, mode: mode, next: { next, nextMode in
            level = next
            mode = nextMode
            token = UUID()
        }, close: close)
        .id(token)
    }
}

final class LevelModel: ObservableObject {
    let session: GameSession
    let scene: GameScene

    init(level: LevelData, mode: PlayMode) {
        session = GameSession(level: level, mode: mode)
        scene = GameScene(session: session)
    }
}

struct LevelScreen: View {
    @StateObject private var model: LevelModel
    let next: (LevelData, PlayMode) -> Void
    let close: () -> Void

    init(level: LevelData, mode: PlayMode, next: @escaping (LevelData, PlayMode) -> Void, close: @escaping () -> Void) {
        _model = StateObject(wrappedValue: LevelModel(level: level, mode: mode))
        self.next = next
        self.close = close
    }

    var body: some View {
        LevelContent(session: model.session, scene: model.scene, next: next, close: close)
    }
}

struct LevelContent: View {
    @ObservedObject var session: GameSession
    let scene: GameScene
    let next: (LevelData, PlayMode) -> Void
    let close: () -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var paused = false
    @State private var showIntro = false
    @State private var buyBooster: Booster?
    @State private var ruleIntro: String?

    private var overlayVisible: Bool {
        paused || showIntro || ruleIntro != nil || session.newDish != nil || session.phase != .playing || buyBooster != nil
    }

    var body: some View {
        GeometryReader { geo in
            ZStack {
                KitchenBackground(style: eventStyle ?? progress.background(forBiome: session.level.biome))
                SpriteView(scene: scene, options: [.allowsTransparency])
                    .ignoresSafeArea()
                VStack(spacing: 4) {
                    topBar
                    StarProgress(coins: session.orderCoins, thresholds: session.level.stars)
                    Spacer()
                    if session.boostersAllowed {
                        boosterBar
                    } else {
                        Text(lang.t("rule.noboosters.bar"))
                            .font(Theme.rounded(15, .heavy))
                            .foregroundColor(Theme.brownSoft)
                            .padding(.horizontal, 20)
                            .frame(height: 58)
                            .background(Capsule().fill(Theme.card.opacity(0.92)))
                    }
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 6)
                overlays
            }
            .onAppear {
                Audio.shared.setTrack(eventStyle == nil ? Biomes.music(session.level.biome) : Biomes.music(1))
                scene.hudHeight = geo.safeAreaInsets.top + 96
                scene.bottomReserved = geo.safeAreaInsets.bottom + 96
                if let intro = session.level.intro, !progress.seenIntro(intro) {
                    showIntro = true
                }
                if let rule = session.level.rule, case let .weekly(_, index) = session.mode, index == 0 {
                    ruleIntro = rule
                }
            }
        }
        .onChange(of: overlayVisible) { visible in
            scene.isPaused = visible
        }
    }

    // MARK: - Панели

    private var topBar: some View {
        HStack(spacing: 10) {
            CircleIconButton(symbol: "pause.fill", size: 42) { paused = true }
            VStack(alignment: .leading, spacing: 0) {
                Text(title)
                    .font(Theme.rounded(19, .heavy))
                    .foregroundColor(Theme.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                if session.level.hard && session.mode == .main {
                    Text(lang.t("map.hard"))
                        .font(Theme.rounded(12, .heavy))
                        .foregroundColor(Theme.red)
                }
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 42)
            .background(Capsule().fill(Theme.card).shadow(color: Theme.brown.opacity(0.18), radius: 4, y: 2))
            Spacer()
        }
        .padding(.top, 6)
        .frame(height: 52)
    }

    /// Уровни ивента идут на фоне темы ивента.
    private var eventStyle: String? {
        if case let .event(_, theme, _) = session.mode { return theme }
        return nil
    }

    private var title: String {
        switch session.mode {
        case .main: return lang.t("level.title", session.level.id)
        case .daily: return lang.t("challenge.daily.title")
        case let .weekly(_, index): return lang.t("challenge.weekly.level", index + 1)
        case let .event(_, theme, index): return lang.t("event.level", lang.t("event.season." + theme), index + 1)
        }
    }

    private var boosterBar: some View {
        let pause = session.pauseAvailable
        return HStack(spacing: pause ? 10 : 14) {
            boosterButton(.undo) { session.undo() }
            boosterButton(.hint) { session.hint() }
            boosterButton(.shuffle) { session.shuffle() }
            boosterButton(.shelf) { session.useExtraShelf() }
            if pause {
                boosterButton(.pause) { session.pausePatience() }
            }
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 16)
        .background(Capsule().fill(Theme.card.opacity(0.92)).shadow(color: Theme.brown.opacity(0.2), radius: 8, y: 3))
    }

    private func boosterButton(_ booster: Booster, use: @escaping () -> Bool) -> some View {
        let count = progress.count(booster)
        return Button {
            guard session.phase == .playing else { return }
            if count > 0 {
                if !use() { Toast.error(lang.t("booster.cant")) }
            } else {
                buyBooster = booster
            }
        } label: {
            ZStack(alignment: .topTrailing) {
                Image(systemName: booster.symbol)
                    .font(.system(size: 22, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 52, height: 52)
                    .background(Circle().fill(booster == .pause ? Theme.blue : Theme.orange)
                        .shadow(color: (booster == .pause ? Theme.blue : Theme.orange).opacity(0.5), radius: 0, y: 4))
                Text(count > 0 ? "\(count)" : "+")
                    .font(Theme.rounded(13, .heavy))
                    .foregroundColor(.white)
                    .frame(minWidth: 22, minHeight: 22)
                    .background(Circle().fill(count > 0 ? Theme.green : Theme.brownSoft))
                    .offset(x: 4, y: -4)
            }
        }
        .buttonStyle(.plain)
    }


    // MARK: - Окна

    @ViewBuilder
    private var overlays: some View {
        if let dish = session.newDish {
            DishUnlockView(dish: dish) { session.newDish = nil }
                .transition(.opacity)
        } else if session.phase == .won {
            WinView(session: session, next: goNext, close: close)
        } else if session.phase == .stuck {
            StuckView(session: session, giveUp: {
                session.abandon()
                close()
            })
        } else if showIntro, let intro = session.level.intro {
            IntroView(kind: intro) {
                progress.markIntro(intro)
                showIntro = false
            }
        } else if let rule = ruleIntro {
            IntroView(kind: "rule." + rule) { ruleIntro = nil }
        } else if paused {
            PauseView(session: session, resume: { paused = false }, restart: restart, exit: {
                session.abandon()
                close()
            })
        } else if let booster = buyBooster {
            BuyBoosterView(booster: booster, close: { buyBooster = nil })
        }
    }

    private func restart() {
        session.abandon()
        if !session.costsLife || progress.hasLife {
            next(session.level, session.mode)
        } else {
            close()
        }
    }

    private func goNext() {
        guard let target = session.nextLevel else {
            close()
            return
        }
        if target.mode != .main || progress.isPassed(target.level.id) || progress.hasLife {
            next(target.level, target.mode)
        } else {
            close()
        }
    }
}

// MARK: - Окна поверх уровня

struct PauseView: View {
    @ObservedObject var session: GameSession
    let resume: () -> Void
    let restart: () -> Void
    let exit: () -> Void
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim()
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    Text(lang.t("pause.title"))
                        .font(Theme.rounded(26, .heavy))
                        .foregroundColor(Theme.brown)
                    if session.costsLife && session.hasMoves {
                        Text(lang.t("pause.lifewarning"))
                            .font(Theme.rounded(14, .semibold))
                            .foregroundColor(Theme.red)
                            .multilineTextAlignment(.center)
                    }
                    Button(lang.t("pause.resume"), action: resume).buttonStyle(BigButtonStyle(color: Theme.green))
                    Button(lang.t("pause.restart"), action: restart).buttonStyle(BigButtonStyle())
                    Button(lang.t("pause.exit"), action: exit).buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                }
                .frame(maxWidth: 290)
            }
        }
    }
}

struct StuckView: View {
    @ObservedObject var session: GameSession
    let giveUp: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        ZStack {
            Dim()
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    SpriteImage(name: progress.goldShelves ? "shelf_gold" : "shelf", size: 110)
                    Text(lang.t("stuck.title"))
                        .font(Theme.rounded(24, .heavy))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("stuck.text"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                    Button {
                        if !session.continueWithCoins() { Toast.error(lang.t("common.nocoins")) }
                    } label: {
                        HStack { Text(lang.t("stuck.shelf")); CoinIcon(size: 20); Text("\(session.continuePrice)") }
                    }
                    .buttonStyle(BigButtonStyle())
                    if !session.adContinueUsed {
                        Button {
                            session.continueWithAd { ok in if !ok { Toast.error(lang.t("ads.limit")) } }
                        } label: {
                            HStack { AdIcon(); Text(lang.t("stuck.ad")) }
                        }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                        AdsLeftLabel()
                    }
                    Button(lang.t(session.costsLife ? "stuck.giveup" : "stuck.giveup.replay"), action: giveUp)
                        .buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                }
                .frame(maxWidth: 300)
            }
        }
    }
}

struct WinView: View {
    @ObservedObject var session: GameSession
    let next: () -> Void
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var shown = 0

    var body: some View {
        ZStack {
            Dim()
            if let result = session.result {
                Panel(padding: 22) {
                    VStack(spacing: 14) {
                        Text(lang.t("win.title"))
                            .font(Theme.rounded(28, .heavy))
                            .foregroundColor(Theme.brown)
                        HStack(spacing: 6) {
                            ForEach(0..<3, id: \.self) { i in
                                Image(systemName: "star.fill")
                                    .font(.system(size: i == 1 ? 58 : 46))
                                    .foregroundColor(i < shown ? Theme.gold : Theme.brown.opacity(0.15))
                                    .scaleEffect(i < shown ? 1 : 0.6)
                                    .offset(y: i == 1 ? -8 : 0)
                                    .shadow(color: i < shown ? Theme.orange.opacity(0.5) : .clear, radius: 0, y: 3)
                            }
                        }
                        VStack(spacing: 6) {
                            row(lang.t("win.orders"), result.served * Balance.coinsPerOrder)
                            if result.tips > 0 { row(lang.t("win.tips"), result.tips) }
                            if result.comboCoins > 0 { row(lang.t("win.combo"), result.comboCoins) }
                            row(lang.t("win.efficiency"), result.efficiency)
                            Divider()
                            row(lang.t("win.total"), result.total, bold: true)
                        }
                        .padding(.horizontal, 6)
                        rewardText(result)
                        extras(result)
                        if result.reward.coinsAdded > 0 && !session.doubled {
                            Button {
                                session.doubleCoins { ok in if !ok { Toast.error(lang.t("ads.limit")) } }
                            } label: {
                                HStack { AdIcon(); Text(lang.t("win.double")) }
                            }
                            .buttonStyle(BigButtonStyle(color: Theme.green))
                            AdsLeftLabel()
                        }
                        HStack(spacing: 10) {
                            Button(lang.t("win.map"), action: close).buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                            if session.nextLevel != nil {
                                Button(lang.t("win.next"), action: next).buttonStyle(BigButtonStyle())
                            }
                        }
                    }
                    .frame(maxWidth: 310)
                }
                .onAppear {
                    Audio.shared.play(.win, volume: 0.8)
                    for i in 1...result.stars {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.35 + 0.3 * Double(i)) {
                            withAnimation(.spring(response: 0.35, dampingFraction: 0.45)) { shown = i }
                            Audio.shared.play(i == 1 ? .star1 : (i == 2 ? .star2 : .star3))
                            Haptics.light()
                        }
                    }
                }
            }
        }
    }

    private func row(_ title: String, _ value: Int, bold: Bool = false) -> some View {
        HStack {
            Text(title).font(Theme.rounded(16, bold ? .heavy : .semibold)).foregroundColor(Theme.brownSoft)
            Spacer()
            CoinIcon(size: 18)
            Text("\(value)").font(Theme.rounded(17, bold ? .heavy : .bold)).foregroundColor(Theme.brown).monospacedDigit()
        }
    }

    /// Стрик, серия шефа и награда испытания.
    @ViewBuilder
    private func extras(_ result: GameSession.Result) -> some View {
        VStack(spacing: 6) {
            if let day = result.streakDay, let granted = result.streak {
                RewardLine(symbol: "flame.fill", color: Theme.orange, title: lang.t("win.streak", day), granted: granted)
            }
            if session.mode == .main && !session.isReplay && result.chefSeries > 1 {
                RewardLine(symbol: "crown.fill", color: Theme.gold, title: lang.t("win.chef", result.chefSeries),
                           granted: result.chef)
            }
            if let granted = result.challenge {
                RewardLine(symbol: "calendar", color: Theme.green, title: lang.t(challengeTitle), granted: granted)
            }
            ForEach(result.events) { gain in
                RewardLine(symbol: EventUI.symbol(gain.kind), color: EventUI.color(gain.kind),
                           title: EventUI.gainText(gain, lang: lang), granted: nil)
            }
            if result.doubleBonus > 0 {
                RewardLine(symbol: "2.circle.fill", color: Theme.green, title: lang.t("event.double.bonus", result.doubleBonus),
                           granted: nil)
            }
            if result.vipBonus > 0 {
                RewardLine(symbol: "crown.fill", color: Theme.gold, title: lang.t("win.vip", result.vipBonus), granted: nil)
            }
            if let gift = result.gourmetGift {
                RewardLine(symbol: "crown.fill", color: Theme.gold,
                           title: lang.t(gift.reward.background != nil ? "win.gourmet.bg" : "win.gourmet"), granted: gift)
            }
        }
    }

    private var challengeTitle: String {
        switch session.mode {
        case .daily: return "win.daily"
        case .weekly: return "win.weekly"
        case .main, .event: return ""
        }
    }

    @ViewBuilder
    private func rewardText(_ result: GameSession.Result) -> some View {
        VStack(spacing: 4) {
            if session.isReplay {
                Text(result.reward.coinsAdded > 0 ? lang.t("win.record", result.reward.coinsAdded) : lang.t("win.norecord"))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .multilineTextAlignment(.center)
            }
            if result.reward.lifeReturned {
                Text(lang.t("win.life"))
                    .font(Theme.rounded(14, .bold))
                    .foregroundColor(Theme.red)
            }
        }
    }
}

struct IntroView: View {
    let kind: String
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        ZStack {
            Dim()
            Panel(padding: 22) {
                VStack(spacing: 16) {
                    illustration
                    Text(lang.t("intro.\(kind).title"))
                        .font(Theme.rounded(24, .heavy))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                    Text(lang.t("intro.\(kind).text"))
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

    @ViewBuilder
    private var illustration: some View {
        switch kind {
        case "recipes":
            HStack(spacing: 4) {
                SpriteImage(name: "bun", size: 50)
                Text("+").font(Theme.rounded(22, .heavy)).foregroundColor(Theme.brownSoft)
                SpriteImage(name: "patty", size: 50)
                Text("+").font(Theme.rounded(22, .heavy)).foregroundColor(Theme.brownSoft)
                SpriteImage(name: "lettuce", size: 50)
                Text("=").font(Theme.rounded(22, .heavy)).foregroundColor(Theme.brownSoft)
                SpriteImage(name: "dish_burger", size: 64)
            }
        case "patience":
            HStack(spacing: 10) {
                SpriteImage(name: "customer_1_happy", size: 70)
                VStack(alignment: .leading, spacing: 6) {
                    patienceBar(0.9, Theme.green)
                    patienceBar(0.45, Theme.gold)
                    patienceBar(0.15, Theme.red)
                }
                SpriteImage(name: "customer_1_upset", size: 70)
            }
        case "hidden":
            ZStack {
                Circle().fill(Color(red: 0.45, green: 0.30, blue: 0.20)).frame(width: 64, height: 64)
                Text("?").font(Theme.rounded(36, .heavy)).foregroundColor(.white)
            }
        case "onigiri":
            HStack(spacing: 4) {
                SpriteImage(name: "rice", size: 46)
                SpriteImage(name: "rice", size: 46)
                SpriteImage(name: "rice", size: 46)
                Text("=").font(Theme.rounded(22, .heavy)).foregroundColor(Theme.brownSoft)
                SpriteImage(name: "dish_onigiri", size: 64)
            }
        case "juice":
            HStack(spacing: 4) {
                SpriteImage(name: "grapes", size: 46)
                SpriteImage(name: "grapes", size: 46)
                SpriteImage(name: "grapes", size: 46)
                Text("=").font(Theme.rounded(22, .heavy)).foregroundColor(Theme.brownSoft)
                SpriteImage(name: "dish_juice", size: 64)
            }
        case "dough":
            VStack(spacing: 6) {
                HStack(spacing: 4) {
                    SpriteImage(name: "flour", size: 40)
                    SpriteImage(name: "flour", size: 40)
                    SpriteImage(name: "flour", size: 40)
                    Image(systemName: "arrow.right").font(.system(size: 18, weight: .heavy)).foregroundColor(Theme.orange)
                    SpriteImage(name: "dough", size: 50)
                }
                HStack(spacing: 4) {
                    SpriteImage(name: "dough", size: 40)
                    Text("+").font(Theme.rounded(18, .heavy)).foregroundColor(Theme.brownSoft)
                    SpriteImage(name: "tomato", size: 40)
                    Text("+").font(Theme.rounded(18, .heavy)).foregroundColor(Theme.brownSoft)
                    SpriteImage(name: "mozzarella", size: 40)
                    Text("=").font(Theme.rounded(18, .heavy)).foregroundColor(Theme.brownSoft)
                    SpriteImage(name: "dish_pizza", size: 56)
                }
            }
        case "ice":
            ZStack(alignment: .topTrailing) {
                SpriteImage(name: "fish", size: 70)
                RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .fill(Color(red: 0.72, green: 0.90, blue: 1.0).opacity(0.5))
                    .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).stroke(Color.white, lineWidth: 2))
                    .frame(width: 72, height: 74)
                Text("2")
                    .font(Theme.rounded(15, .heavy))
                    .foregroundColor(.white)
                    .frame(width: 26, height: 26)
                    .background(Circle().fill(Color(red: 0.20, green: 0.55, blue: 0.90)))
                    .offset(x: 8, y: -8)
            }
        case "gourmet":
            ZStack(alignment: .topLeading) {
                SpriteImage(name: "customer_10_happy", size: 90)
                Image(systemName: "crown.fill").font(.system(size: 22)).foregroundColor(Theme.gold).offset(x: 4, y: 0)
            }
        case "lock":
            ZStack {
                SpriteImage(name: progress.goldShelves ? "shelf_gold" : "shelf", size: 120)
                    .overlay(Color.black.opacity(0.25).clipShape(RoundedRectangle(cornerRadius: 10)))
                Image(systemName: "lock.fill").font(.system(size: 34, weight: .bold)).foregroundColor(Theme.gold)
            }
        case "conflict":
            HStack(spacing: 6) {
                SpriteImage(name: "baguette", size: 56)
                Image(systemName: "arrow.left.arrow.right").font(.system(size: 22, weight: .bold)).foregroundColor(Theme.orange)
                SpriteImage(name: "dish_sub", size: 64)
            }
        case "rule.noboosters":
            ZStack {
                HStack(spacing: 8) {
                    ForEach(Booster.allCases) { b in
                        Image(systemName: b.symbol)
                            .font(.system(size: 22, weight: .bold))
                            .foregroundColor(.white)
                            .frame(width: 48, height: 48)
                            .background(Circle().fill(Theme.brownSoft))
                    }
                }
                Rectangle().fill(Theme.red).frame(width: 190, height: 5).rotationEffect(.degrees(-12))
            }
        case "rule.hidden":
            HStack(spacing: 8) {
                ForEach(0..<3, id: \.self) { _ in
                    ZStack {
                        Circle().fill(Color(red: 0.45, green: 0.30, blue: 0.20)).frame(width: 52, height: 52)
                        Text("?").font(Theme.rounded(30, .heavy)).foregroundColor(.white)
                    }
                }
            }
        case "rule.recipes":
            HStack(spacing: 4) {
                SpriteImage(name: "dish_burger", size: 60)
                SpriteImage(name: "dish_hotdog", size: 60)
                SpriteImage(name: "dish_pancakes", size: 60)
            }
        default:
            HStack(spacing: 2) {
                SpriteImage(name: "donut", size: 54)
                SpriteImage(name: "donut", size: 54)
                SpriteImage(name: "donut", size: 54)
            }
        }
    }
}

private func patienceBar(_ fraction: CGFloat, _ color: Color) -> some View {
    ZStack(alignment: .leading) {
        Capsule().fill(Theme.brown.opacity(0.7)).frame(width: 64, height: 10)
        Capsule().fill(color).frame(width: 64 * fraction, height: 8).padding(.leading, 1)
    }
}

/// Монеты уровня и пороги звезд: 1 звезда за прохождение, 2 и 3 - по монетам.
struct StarProgress: View {
    let coins: Int
    let thresholds: [Int]

    var body: some View {
        let s2 = thresholds.first ?? 1
        let s3 = thresholds.count > 1 ? thresholds[1] : s2
        let top = max(1, Double(s3) * 1.12)
        HStack(spacing: 8) {
            CoinIcon(size: 20)
            Text("\(coins)")
                .font(Theme.rounded(17, .heavy))
                .foregroundColor(Theme.brown)
                .monospacedDigit()
                .frame(minWidth: 30, alignment: .leading)
            GeometryReader { geo in
                let w = geo.size.width
                ZStack(alignment: .leading) {
                    Capsule().fill(Theme.brown.opacity(0.14)).frame(height: 10)
                    Capsule().fill(LinearGradient(colors: [Theme.gold, Theme.orange], startPoint: .leading, endPoint: .trailing))
                        .frame(width: max(10, w * CGFloat(min(1, Double(coins) / top))), height: 10)
                        .animation(.easeOut(duration: 0.3), value: coins)
                    marker(stars: 2, value: s2, x: w * CGFloat(Double(s2) / top), reached: coins >= s2)
                    marker(stars: 3, value: s3, x: w * CGFloat(Double(s3) / top), reached: coins >= s3)
                }
                .frame(height: geo.size.height)
            }
            .frame(height: 34)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 3)
        .background(Capsule().fill(Theme.card.opacity(0.95)).shadow(color: Theme.brown.opacity(0.15), radius: 4, y: 2))
    }

    private func marker(stars: Int, value: Int, x: CGFloat, reached: Bool) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 0) {
                ForEach(0..<stars, id: \.self) { _ in
                    Image(systemName: "star.fill").font(.system(size: 8, weight: .bold))
                }
            }
            .foregroundColor(reached ? Theme.gold : Theme.brownSoft.opacity(0.7))
            Rectangle().fill(Theme.brown.opacity(0.35)).frame(width: 2, height: 12)
            Text("\(value)")
                .font(Theme.rounded(9, .heavy))
                .foregroundColor(reached ? Theme.orange : Theme.brownSoft)
        }
        .fixedSize()
        .position(x: x, y: 17)
    }
}

/// Сколько рекламы осталось на сегодня.
struct AdsLeftLabel: View {
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        if progress.isVIP {
            Label(lang.t("vip.noads"), systemImage: "crown.fill")
                .font(Theme.rounded(12, .bold))
                .foregroundColor(Theme.gold)
        } else {
            Text(lang.t("ads.left", progress.adsLeftToday, Balance.adDailyLimit))
                .font(Theme.rounded(12, .semibold))
                .foregroundColor(Theme.brownSoft)
        }
    }
}

struct BuyBoosterView: View {
    let booster: Booster
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    Image(systemName: booster.symbol)
                        .font(.system(size: 40, weight: .bold))
                        .foregroundColor(.white)
                        .frame(width: 84, height: 84)
                        .background(Circle().fill(Theme.orange))
                    Text(lang.t("booster." + booster.rawValue))
                        .font(Theme.rounded(22, .heavy))
                        .foregroundColor(Theme.brown)
                    Text(lang.t("booster." + booster.rawValue + ".text"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                    Button {
                        if progress.buy(booster) { close() } else { Toast.error(lang.t("common.nocoins")) }
                    } label: {
                        HStack { Text(lang.t("booster.buy")); CoinIcon(size: 20); Text("\(booster.price)") }
                    }
                    .buttonStyle(BigButtonStyle())
                    Button(lang.t("common.cancel"), action: close).buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                }
                .frame(maxWidth: 290)
            }
        }
    }
}
