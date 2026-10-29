import SwiftUI
import SpriteKit

/// Уровень "Рынка": движок, сцена, ходы, цели на панели, бустеры, конец уровня.
final class Match3Model: ObservableObject {
    enum Phase: Equatable {
        case starting, playing, finale, outOfMoves, won, lost
    }

    let level: M3Level
    let scene: Match3Scene
    private(set) var board: M3Board

    @Published private(set) var phase: Phase = .starting
    @Published private(set) var movesLeft: Int
    /// Сколько осталось по каждой цели на панели (уменьшается, когда фишка долетает).
    @Published private(set) var shown: [Int]
    @Published var targeting: M3Booster?
    /// Окна поверх уровня (пауза, покупка): поле не принимает касания.
    @Published var overlay = false
    @Published private(set) var result: MarketResult?
    @Published private(set) var finaleCoins = 0
    @Published private(set) var extraBought = 0
    @Published private(set) var adUsed = false
    @Published private(set) var critic: Bool
    /// Пульс иконки цели при попадании.
    @Published private(set) var goalPulse: [Int] = []

    private var inFlight: [Int]
    private(set) var moved = false
    private let preBoosters: [M3Booster]
    let streakAtStart: Int

    /// Рамки целей и счетчика ходов на экране (глобальные координаты SwiftUI).
    var goalFrames: [Int: CGRect] = [:]
    var movesFrame: CGRect = .zero
    var boosterFrame: CGRect = .zero

    init(level: M3Level, pre: [M3Booster]) {
        self.level = level
        let seed = UInt64(level.id) &* 7919 &+ UInt64.random(in: 1...1_000_000)
        board = M3Board(level: level, seed: seed)
        movesLeft = level.moves
        shown = level.goals.map(\.count)
        inFlight = Array(repeating: 0, count: level.goals.count)
        goalPulse = Array(repeating: 0, count: level.goals.count)
        preBoosters = pre
        streakAtStart = PlayerProgress.shared.marketStreak
        critic = PlayerProgress.shared.criticHere
        scene = Match3Scene(level: level)
        #if DEBUG
        // снимки в CI: несколько ходов подсказки сразу, без анимации
        for _ in 0..<UIDebug.autoplay {
            guard let h = board.hint(), let line = board.swap(h.0, h.1), line.counted else { break }
            movesLeft -= 1
        }
        shown = level.goals.indices.map { board.remaining($0) }
        #endif
        scene.model = self
    }

    var canInteract: Bool { phase == .playing && !overlay && !scene.playing }

    /// После появления поля: спецфишки серии и бустеров перед уровнем прилетают на поле.
    func start() {
        guard phase == .starting else { return }
        var specials = PlayerProgress.shared.streakSpecials
        for b in preBoosters {
            if let s = b.special, PlayerProgress.shared.use(b) { specials.append(s) }
        }
        let delay = 0.5 + Double(level.rows) * 0.035 + 0.45
        DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in
            guard let self = self else { return }
            #if DEBUG
            if UIDebug.flag("uiM3Out") {
                self.movesLeft = 0
                self.moved = true
                self.phase = .outOfMoves
                return
            }
            if UIDebug.flag("uiM3Win") {
                self.movesLeft = 4
                self.phase = .playing
                self.beginFinale()
                return
            }
            #endif
            guard !specials.isEmpty else {
                self.phase = .playing
                return
            }
            let line = self.board.placeStart(specials)
            self.scene.convertSource = CGPoint(x: self.scene.size.width / 2, y: 40)
            self.scene.play(line) { [weak self] in
                self?.scene.convertSource = nil
                self?.phase = .playing
            }
        }
    }

    // MARK: - Ходы

    func swap(_ a: M3Cell, _ b: M3Cell) -> M3Timeline? {
        guard canInteract else { return nil }
        var copy = board
        guard let line = copy.swap(a, b) else { return nil }
        board = copy
        if line.counted {
            movesLeft -= 1
            moved = true
        }
        return line
    }

    func tap(_ p: M3Cell) -> M3Timeline? {
        guard canInteract else { return nil }
        var copy = board
        guard let line = copy.tap(p) else { return nil }
        board = copy
        movesLeft -= 1
        moved = true
        return line
    }

    // MARK: - Бустеры

    /// Нажали бустер на панели: молоток, нож, лопатка ждут клетку, миксер срабатывает сразу.
    /// Возвращает false, если бустеров нет (панель предложит купить).
    func pick(_ b: M3Booster) -> Bool {
        guard phase == .playing, !scene.playing else { return true }
        if targeting == b {
            targeting = nil
            return true
        }
        guard PlayerProgress.shared.count(b) > 0 else { return false }
        if b.needsTarget {
            targeting = b
            Haptics.light()
            return true
        }
        var copy = board
        guard let line = copy.use(b, at: M3Cell(0, 0)), PlayerProgress.shared.use(b) else { return true }
        board = copy
        scene.play(line) { [weak self] in self?.lineFinished(line) }
        return true
    }

    func useTargeted(at p: M3Cell) -> M3Timeline? {
        guard let b = targeting else { return nil }
        var copy = board
        guard let line = copy.use(b, at: p), PlayerProgress.shared.use(b) else { return nil }
        board = copy
        targeting = nil
        return line
    }

    // MARK: - Цели

    func claimFlight(item: String) -> Int? {
        guard let i = level.goals.indices.first(where: { level.goals[$0].type == "collect" && level.goals[$0].item == item }),
              shown[i] - inFlight[i] > 0 else { return nil }
        inFlight[i] += 1
        return i
    }

    func claimFlight(type: String) -> Int? {
        guard let i = level.goals.indices.first(where: { level.goals[$0].type == type }), shown[i] - inFlight[i] > 0 else { return nil }
        inFlight[i] += 1
        return i
    }

    func flightArrived(_ i: Int) {
        inFlight[i] = max(0, inFlight[i] - 1)
        shown[i] = max(0, shown[i] - 1)
        goalPulse[i] += 1
        Audio.shared.play(.coin, volume: 0.25)
    }

    /// Точка цели в координатах сцены.
    func goalPoint(_ i: Int) -> CGPoint {
        let frame = goalFrames[i] ?? CGRect(x: scene.size.width / 2, y: 60, width: 1, height: 1)
        return CGPoint(x: frame.midX, y: scene.size.height - frame.midY)
    }

    var movesPoint: CGPoint {
        CGPoint(x: movesFrame.midX, y: scene.size.height - movesFrame.midY)
    }

    // MARK: - Конец хода

    func lineFinished(_ line: M3Timeline) {
        for i in shown.indices {
            shown[i] = min(shown[i], board.remaining(i) + inFlight[i])
        }
        switch phase {
        case .playing:
            if board.won {
                beginFinale()
            } else if movesLeft <= 0 {
                phase = .outOfMoves
                Haptics.warning()
            }
        default:
            break
        }
    }

    private func beginFinale() {
        phase = .finale
        Haptics.success()
        Audio.shared.play(.win, volume: 0.7)
        let left = movesLeft
        let line = board.finale(moves: left)
        scene.convertSource = movesPoint
        // счетчик ходов тикает вниз вместе с прилетающими скалками
        for i in 0..<left {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2 + Double(i) * 0.09) { [weak self] in
                guard let self = self else { return }
                self.movesLeft = max(0, self.movesLeft - 1)
                self.finaleCoins += MarketBalance.coinsPerMove
            }
        }
        scene.play(line) { [weak self] in
            guard let self = self else { return }
            self.scene.convertSource = nil
            self.result = PlayerProgress.shared.marketWin(self.level, movesLeft: left, collected: self.collected)
            self.phase = .won
        }
    }

    /// Собранные продукты по названиям (для "Большого рецепта").
    var collected: [String: Int] {
        var out: [String: Int] = [:]
        for (k, name) in level.colors.enumerated() where board.gotColors[k] > 0 { out[name] = board.gotColors[k] }
        return out
    }

    // MARK: - Ходы кончились

    var extraPrice: Int {
        let prices = MarketBalance.extraPrices
        return prices[min(extraBought, prices.count - 1)]
    }

    func buyMoves() -> Bool {
        guard phase == .outOfMoves, PlayerProgress.shared.spend(extraPrice) else { return false }
        extraBought += 1
        addMoves()
        Analytics.log("market_moves", ["level": level.id, "n": extraBought])
        return true
    }

    func adMoves(_ done: @escaping (Bool) -> Void) {
        guard phase == .outOfMoves, !adUsed else { return done(false) }
        Ads.shared.showRewarded(placement: "market_moves") { [weak self] ok in
            guard let self = self, ok else { return done(false) }
            self.adUsed = true
            self.addMoves()
            done(true)
        }
    }

    private func addMoves() {
        movesLeft += MarketBalance.extraMoves
        phase = .playing
    }

    /// Сдаться, когда ходы кончились.
    func giveUp() {
        guard phase == .outOfMoves else { return }
        PlayerProgress.shared.marketLose(level, collected: collected)
        phase = .lost
    }

    /// Выход из уровня: если ходы были, это проигрыш (жизнь и серия).
    func abandon() {
        guard phase != .won && phase != .lost else { return }
        if moved {
            PlayerProgress.shared.marketLose(level, collected: collected)
        }
        phase = .lost
    }
}
