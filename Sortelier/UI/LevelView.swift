import SwiftUI
import SpriteKit

/// Держит уровень и позволяет перейти к следующему без возврата на карту.
struct LevelHost: View {
    @State private var level: LevelData
    @State private var token = UUID()
    let close: () -> Void

    init(level: LevelData, close: @escaping () -> Void) {
        _level = State(initialValue: level)
        self.close = close
    }

    var body: some View {
        LevelScreen(level: level, next: { next in
            level = next
            token = UUID()
        }, close: close)
        .id(token)
    }
}

final class LevelModel: ObservableObject {
    let session: GameSession
    let scene: GameScene

    init(level: LevelData) {
        session = GameSession(level: level)
        scene = GameScene(session: session)
    }
}

struct LevelScreen: View {
    @StateObject private var model: LevelModel
    let next: (LevelData) -> Void
    let close: () -> Void

    init(level: LevelData, next: @escaping (LevelData) -> Void, close: @escaping () -> Void) {
        _model = StateObject(wrappedValue: LevelModel(level: level))
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
    let next: (LevelData) -> Void
    let close: () -> Void

    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var paused = false
    @State private var showIntro = false
    @State private var buyBooster: Booster?
    @State private var toast: String?

    private var overlayVisible: Bool {
        paused || showIntro || session.newDish != nil || session.phase != .playing || buyBooster != nil
    }

    var body: some View {
        GeometryReader { geo in
            ZStack {
                KitchenBackground()
                SpriteView(scene: scene, options: [.allowsTransparency])
                    .ignoresSafeArea()
                VStack(spacing: 0) {
                    topBar
                    Spacer()
                    boosterBar
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 6)
                if let text = toast {
                    Text(text)
                        .font(Theme.rounded(15, .bold))
                        .foregroundColor(.white)
                        .padding(.horizontal, 16)
                        .padding(.vertical, 10)
                        .background(Capsule().fill(Theme.brown.opacity(0.9)))
                        .transition(.opacity)
                        .frame(maxHeight: .infinity, alignment: .bottom)
                        .padding(.bottom, 110)
                }
                overlays
            }
            .onAppear {
                scene.hudHeight = geo.safeAreaInsets.top + 62
                scene.bottomReserved = geo.safeAreaInsets.bottom + 96
                if let intro = session.level.intro, !progress.seenIntro(intro) {
                    showIntro = true
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
                Text(lang.t("level.title", session.level.id))
                    .font(Theme.rounded(19, .heavy))
                    .foregroundColor(Theme.brown)
                if session.level.hard {
                    Text(lang.t("map.hard"))
                        .font(Theme.rounded(12, .heavy))
                        .foregroundColor(Theme.red)
                }
            }
            .padding(.horizontal, 14)
            .frame(minHeight: 42)
            .background(Capsule().fill(Theme.card).shadow(color: Theme.brown.opacity(0.18), radius: 4, y: 2))
            Spacer()
            Pill(text: "\(session.orderCoins)") { CoinIcon(size: 22) }
            starMeter
        }
        .padding(.top, 6)
        .frame(height: 56)
    }

    /// Сколько монет уже набрано относительно порогов звезд.
    private var starMeter: some View {
        let s2 = session.level.stars[0]
        let s3 = session.level.stars[1]
        let earned = session.orderCoins
        let count = earned >= s3 ? 3 : (earned >= s2 ? 2 : 1)
        return StarsRow(count: count, size: 14, spacing: 1)
            .padding(.horizontal, 8)
            .frame(height: 36)
            .background(Capsule().fill(Theme.card).shadow(color: Theme.brown.opacity(0.18), radius: 4, y: 2))
    }

    private var boosterBar: some View {
        HStack(spacing: 18) {
            boosterButton(.undo) { session.undo() }
            boosterButton(.hint) { session.hint() }
            boosterButton(.shelf) { session.useExtraShelf() }
        }
        .padding(.vertical, 10)
        .padding(.horizontal, 20)
        .background(Capsule().fill(Theme.card.opacity(0.92)).shadow(color: Theme.brown.opacity(0.2), radius: 8, y: 3))
    }

    private func boosterButton(_ booster: Booster, use: @escaping () -> Bool) -> some View {
        let count = progress.count(booster)
        return Button {
            guard session.phase == .playing else { return }
            if count > 0 {
                if !use() { flash(lang.t("booster.cant")) }
            } else {
                buyBooster = booster
            }
        } label: {
            ZStack(alignment: .topTrailing) {
                Image(systemName: booster.symbol)
                    .font(.system(size: 24, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 58, height: 58)
                    .background(Circle().fill(Theme.orange).shadow(color: Theme.orange.opacity(0.5), radius: 0, y: 4))
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

    private func flash(_ text: String) {
        withAnimation { toast = text }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) {
            withAnimation { toast = nil }
        }
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
        if session.isReplay || progress.hasLife {
            next(session.level)
        } else {
            close()
        }
    }

    private func goNext() {
        let nextId = session.level.id + 1
        guard let level = LevelStore.shared.level(nextId) else {
            close()
            return
        }
        if progress.isPassed(nextId) || progress.hasLife {
            next(level)
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
                    if !session.isReplay && session.hasMoves {
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
    @State private var message: String?

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
                        if !session.continueWithCoins() { message = lang.t("common.nocoins") }
                    } label: {
                        HStack { Text(lang.t("stuck.shelf")); CoinIcon(size: 20); Text("\(session.continuePrice)") }
                    }
                    .buttonStyle(BigButtonStyle())
                    if !session.adContinueUsed {
                        Button {
                            session.continueWithAd { ok in if !ok { message = lang.t("ads.limit") } }
                        } label: {
                            HStack { Image(systemName: "play.rectangle.fill"); Text(lang.t("stuck.ad")) }
                        }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                    }
                    Button(lang.t(session.isReplay ? "stuck.giveup.replay" : "stuck.giveup"), action: giveUp)
                        .buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                    if let message = message {
                        Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
                    }
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
    @State private var message: String?

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
                            row(lang.t("win.orders"), result.orderCoins)
                            row(lang.t("win.efficiency"), result.efficiency)
                            Divider()
                            row(lang.t("win.total"), result.total, bold: true)
                        }
                        .padding(.horizontal, 6)
                        rewardText(result)
                        if result.reward.coinsAdded > 0 && !session.doubled {
                            Button {
                                session.doubleCoins { ok in if !ok { message = lang.t("ads.limit") } }
                            } label: {
                                HStack { Image(systemName: "play.rectangle.fill"); Text(lang.t("win.double")) }
                            }
                            .buttonStyle(BigButtonStyle(color: Theme.green))
                        }
                        if let message = message {
                            Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
                        }
                        HStack(spacing: 10) {
                            Button(lang.t("win.map"), action: close).buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                            if LevelStore.shared.level(session.level.id + 1) != nil {
                                Button(lang.t("win.next"), action: next).buttonStyle(BigButtonStyle())
                            }
                        }
                    }
                    .frame(maxWidth: 310)
                }
                .onAppear {
                    for i in 1...result.stars {
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25 * Double(i)) {
                            withAnimation(.spring(response: 0.35, dampingFraction: 0.45)) { shown = i }
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
        case "hidden":
            ZStack {
                Circle().fill(Color(red: 0.45, green: 0.30, blue: 0.20)).frame(width: 64, height: 64)
                Text("?").font(Theme.rounded(36, .heavy)).foregroundColor(.white)
            }
        case "conflict":
            HStack(spacing: 6) {
                SpriteImage(name: "baguette", size: 56)
                Image(systemName: "arrow.left.arrow.right").font(.system(size: 22, weight: .bold)).foregroundColor(Theme.orange)
                SpriteImage(name: "dish_sub", size: 64)
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

struct BuyBoosterView: View {
    let booster: Booster
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress
    @State private var message: String?

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
                        if progress.buy(booster) { close() } else { message = lang.t("common.nocoins") }
                    } label: {
                        HStack { Text(lang.t("booster.buy")); CoinIcon(size: 20); Text("\(booster.price)") }
                    }
                    .buttonStyle(BigButtonStyle())
                    Button(lang.t("common.cancel"), action: close).buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                    if let message = message {
                        Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
                    }
                }
                .frame(maxWidth: 290)
            }
        }
    }
}
