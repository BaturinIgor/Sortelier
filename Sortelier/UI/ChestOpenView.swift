import SwiftUI
import UIKit

// MARK: - Показ сундука

/// Открытие сундука живет в отдельном окне: поверх листов, уровня и нижней панели,
/// поэтому карточки никогда не прячутся под панелью или краем всплывающего окна.
/// Сундук открывается только по тапу игрока, до этого его можно отложить.
final class ChestOpener: ObservableObject {
    static let shared = ChestOpener()

    struct Session: Identifiable {
        let id = UUID()
        let kind: ChestKind
        let onOpen: (() -> Void)?
        let onClose: (() -> Void)?
    }

    @Published private(set) var session: Session?

    /// Показывает закрытый сундук из запаса. Карточки выдаются только после тапа по сундуку.
    static func present(_ kind: ChestKind, onOpen: (() -> Void)? = nil, onClose: (() -> Void)? = nil) {
        guard shared.session == nil, PlayerProgress.shared.chestCount(kind) > 0 else { return }
        ChestWindow.install()
        ChestWindow.setVisible(true)
        Haptics.light()
        withAnimation(.easeOut(duration: 0.22)) {
            shared.session = Session(kind: kind, onOpen: onOpen, onClose: onClose)
        }
    }

    static func dismiss() {
        let finished = shared.session
        withAnimation(.easeOut(duration: 0.22)) { shared.session = nil }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
            if shared.session == nil { ChestWindow.setVisible(false) }
        }
        finished?.onClose?()
    }
}

/// Окно сундука: чуть ниже карточки описания награды, чтобы описание открывалось поверх.
enum ChestWindow {
    private static var window: UIWindow?

    static func install() {
        guard window == nil else { return }
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        guard let scene = scenes.first(where: { $0.activationState == .foregroundActive }) ?? scenes.first else { return }
        let w = UIWindow(windowScene: scene)
        let host = NoStatusBarHost(rootView: AnyView(ChestOverlay()))
        host.view.backgroundColor = .clear
        w.rootViewController = host
        w.windowLevel = UIWindow.Level(rawValue: UIWindow.Level.alert.rawValue - 1)
        w.backgroundColor = .clear
        w.isHidden = true
        window = w
    }

    static func setVisible(_ visible: Bool) {
        window?.isHidden = !visible
    }
}

struct ChestOverlay: View {
    @ObservedObject private var opener = ChestOpener.shared
    @ObservedObject private var lang = Lang.shared

    var body: some View {
        ZStack {
            if let session = opener.session {
                ChestOpenView(kind: session.kind, onOpen: session.onOpen, close: { ChestOpener.dismiss() })
                    .id(session.id)
                    .transition(.opacity)
            }
        }
        .environmentObject(lang)
        .environmentObject(PlayerProgress.shared)
    }
}

// MARK: - Открытие

/// Закрытый сундук покачивается и ждет тапа. Тап: сундук трясется, крышка открывается, карточки по одной
/// вылетают рубашкой вверх и переворачиваются. Следующий тап отправляет карточку на ее место в ряду сверху,
/// у каждой карточки свое место, поэтому они не наезжают друг на друга. В конце все карточки видны сразу.
struct ChestOpenView: View {
    let kind: ChestKind
    var onOpen: (() -> Void)?
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    enum Stage { case closed, opening, reveal, collecting, summary }
    enum Spot { case chest, stage, tray }

    @State private var stage: Stage = .closed
    @State private var opening: ChestOpening?
    @State private var spots: [Spot] = []
    @State private var faceUp: [Bool] = []
    @State private var current: Int?
    @State private var busy = false
    @State private var lidOpen = false
    @State private var bob = false
    @State private var shakes: CGFloat = 0
    @State private var spin = false
    @State private var flashes = 0

    /// Карточки рисуются в одном размере и масштабируются: так переход между местами плавный.
    private let base: CGFloat = 160

    private var count: Int { opening?.drops.count ?? kind.cards }

    var body: some View {
        ZStack {
            Dim(opacity: 0.82)
            GeometryReader { geo in
                let layout = ChestLayout(size: geo.size, count: count, summary: stage == .summary)
                ZStack {
                    Color.clear
                        .contentShape(Rectangle())
                        .onTapGesture(perform: tap)
                    rays(layout)
                    if stage != .closed { slots(layout) }
                    chest(layout)
                    ForEach(0..<flashes, id: \.self) { _ in
                        ChestFlash()
                            .frame(width: layout.chestSize * 2, height: layout.chestSize * 2)
                            .position(layout.chestCenter)
                            .allowsHitTesting(false)
                    }
                    cards(layout)
                    if stage == .summary { summary(layout) }
                }
                .environment(\.layoutDirection, .leftToRight)
            }
            VStack(spacing: 0) {
                header
                Spacer(minLength: 0)
                footer
            }
            .padding(.top, 10)
            .padding(.bottom, 18)
            .padding(.horizontal, 20)
        }
        .onAppear {
            // бесконечные анимации со следующего кадра, чтобы не зацепить появление окна
            DispatchQueue.main.async {
                withAnimation(.linear(duration: 18).repeatForever(autoreverses: false)) { spin = true }
                if stage == .closed {
                    withAnimation(.easeInOut(duration: 0.9).repeatForever(autoreverses: true)) { bob = true }
                }
            }
            #if DEBUG
            debugAutoplay()
            #endif
        }
    }

    // MARK: Слои

    private var header: some View {
        VStack(spacing: 8) {
            Ribbon(title: lang.t("chest.kind." + kind.rawValue), size: 22)
            if stage == .reveal || stage == .collecting {
                StrokeText(text: "\(spots.filter { $0 != .chest }.count)/\(count)", size: 16, color: .white,
                           stroke: Theme.woodDark, width: 1.5, drop: 2)
                    .transition(.opacity)
            }
        }
        .allowsHitTesting(false)
    }

    @ViewBuilder
    private var footer: some View {
        switch stage {
        case .closed:
            VStack(spacing: 12) {
                ChestContents(kind: kind)
                    .padding(.horizontal, 14)
                    .padding(.vertical, 7)
                    .background(Capsule().fill(Theme.card))
                    .overlay(Capsule().strokeBorder(Theme.paperBorder, lineWidth: 2))
                StrokeText(text: lang.t("chest.tap.open"), size: 18, color: .white, stroke: Theme.woodDark, width: 1.5, drop: 2)
                    .scaleEffect(bob ? 1.05 : 0.97)
                    .allowsHitTesting(false)
                Button(lang.t("chest.later"), action: close)
                    .buttonStyle(GameButtonStyle(palette: .paper, height: 42, fontSize: 16, fullWidth: false, radius: 13))
            }
            .transition(.opacity)
        case .reveal, .collecting, .opening:
            VStack(spacing: 10) {
                Text(lang.t("chest.tap"))
                    .font(Theme.rounded(14, .bold))
                    .foregroundColor(.white.opacity(0.8))
                    .opacity(stage == .reveal ? 1 : 0)
                    .allowsHitTesting(false)
                Button(lang.t("chest.skip"), action: revealAll)
                    .buttonStyle(GameButtonStyle(palette: .paper, height: 40, fontSize: 15, fullWidth: false, radius: 12))
                    .opacity(stage == .reveal ? 1 : 0)
                    .disabled(stage != .reveal)
            }
            .transition(.opacity)
        case .summary:
            EmptyView()
        }
    }

    private func rays(_ l: ChestLayout) -> some View {
        let rare = current.flatMap { opening?.drops[$0].card.stars }.map { $0 >= 4 } ?? false
        let center = stage == .closed ? l.closedCenter : (current != nil ? l.bigCenter : l.chestCenter)
        return SunRays(count: 14)
            .fill(RadialGradient(colors: [(rare ? Theme.gold : Color(red: 1, green: 0.88, blue: 0.55)).opacity(0.75), .clear],
                                 center: .center, startRadius: 10, endRadius: l.raysSize / 2))
            .frame(width: l.raysSize, height: l.raysSize)
            .rotationEffect(.degrees(spin ? 360 : 0))
            .scaleEffect(rare ? 1.15 : 1)
            .position(center)
            .opacity(stage == .summary ? 0 : (stage == .closed ? 0.55 : 0.9))
            .allowsHitTesting(false)
    }

    private func slots(_ l: ChestLayout) -> some View {
        ForEach(0..<count, id: \.self) { i in
            RoundedRectangle(cornerRadius: l.slotW * 0.12, style: .continuous)
                .fill(Color.white.opacity(0.07))
                .overlay(
                    RoundedRectangle(cornerRadius: l.slotW * 0.12, style: .continuous)
                        .strokeBorder(Color.white.opacity(0.32), style: StrokeStyle(lineWidth: 2, dash: [6, 5]))
                )
                .frame(width: l.slotW, height: l.slotW * ChestLayout.ratio)
                .position(l.slot(i))
                .opacity(stage == .summary ? 0 : 1)
                .allowsHitTesting(false)
        }
    }

    private func chest(_ l: ChestLayout) -> some View {
        let closed = stage == .closed
        let size = closed ? l.closedChestSize : l.chestSize
        return Button(action: tap) {
            SpriteImage(name: lidOpen ? kind.openSprite : kind.sprite, size: size)
                .modifier(ShakeEffect(shakes: shakes))
                .offset(y: closed && bob ? -8 : 0)
                .shadow(color: Theme.gold.opacity(closed ? 0.6 : 0.3), radius: 18)
        }
        .buttonStyle(PressScaleStyle())
        .position(closed ? l.closedCenter : l.chestCenter)
        .opacity(stage == .summary ? 0 : 1)
        .scaleEffect(stage == .summary ? 0.6 : 1)
        .disabled(!(stage == .closed || stage == .reveal))
    }

    private func cards(_ l: ChestLayout) -> some View {
        ForEach(opening?.drops ?? []) { drop in
            let i = drop.id
            let spot = spots.indices.contains(i) ? spots[i] : .chest
            let up = faceUp.indices.contains(i) && faceUp[i]
            let width: CGFloat = spot == .tray ? l.slotW : (spot == .stage ? l.bigW : l.chestSize * 0.3)
            let pos: CGPoint = spot == .tray ? l.slot(i) : (spot == .stage ? l.bigCenter : l.chestCenter)
            FlipCard(angle: up ? 0 : 180,
                     front: AlbumCardView(card: drop.card, owned: true, isNew: drop.isNew && up, width: base),
                     back: CardBack(width: base))
                .scaleEffect(width / base)
                .frame(width: width, height: width * ChestLayout.ratio)
                .position(pos)
                .opacity(spot == .chest ? 0 : 1)
                .zIndex(spot == .stage ? 3 : 2)
                .allowsHitTesting(false)
        }
    }

    private func summary(_ l: ChestLayout) -> some View {
        let opening = self.opening
        return VStack(spacing: 14) {
            HStack(spacing: 14) {
                if let o = opening {
                    let fresh = o.drops.filter(\.isNew).count
                    if fresh > 0 {
                        Text(lang.t("album.new.count", fresh)).foregroundColor(Theme.gold)
                    }
                    HStack(spacing: 3) { CoinIcon(size: 22); Text("+\(o.coins)") }
                        .foregroundColor(.white)
                    if o.stars > 0 {
                        HStack(spacing: 2) { SpriteImage(name: "icon_star", size: 22); Text("+\(o.stars)") }
                            .foregroundColor(Color(red: 0.85, green: 0.75, blue: 1.0))
                    }
                }
            }
            .font(Theme.rounded(17, .black))
            .outlined(Theme.woodDark, width: 1)
            .lineLimit(1)
            .minimumScaleFactor(0.7)
            Button(lang.t("common.ok"), action: close)
                .buttonStyle(GameButtonStyle(palette: .green))
                .frame(maxWidth: 240)
        }
        .frame(width: min(l.size.width - 40, 330))
        .position(x: l.size.width / 2, y: l.summaryCenterY)
        .transition(.opacity.combined(with: .offset(y: 20)))
    }

    // MARK: Действия

    private func tap() {
        switch stage {
        case .closed: openChest()
        case .reveal: advance()
        default: break
        }
    }

    private func openChest() {
        guard stage == .closed else { return }
        guard let result = progress.openChest(kind) else { close(); return }
        onOpen?()
        opening = result
        spots = Array(repeating: .chest, count: result.drops.count)
        faceUp = Array(repeating: false, count: result.drops.count)
        stage = .opening
        Haptics.light()
        Audio.shared.play(.swoosh, volume: 0.6)
        withAnimation(.linear(duration: 0.55)) { shakes += 5 }
        after(0.55) {
            lidOpen = true
            flashes += 1
            Audio.shared.play(.chest)
            Haptics.success()
            withAnimation(.spring(response: 0.5, dampingFraction: 0.75)) {
                bob = false
                stage = .reveal
            }
            after(0.3) { show(0) }
        }
    }

    /// Карточка вылетает из сундука рубашкой вверх и переворачивается.
    private func show(_ i: Int) {
        guard let o = opening, i < o.drops.count, stage == .reveal else { return }
        busy = true
        withAnimation(.spring(response: 0.45, dampingFraction: 0.74)) {
            spots[i] = .stage
            current = i
        }
        after(0.3) {
            guard stage == .reveal else { return }
            withAnimation(.easeInOut(duration: 0.4)) { faceUp[i] = true }
            let drop = o.drops[i]
            Audio.shared.play(drop.isNew ? .unlock : .pick, volume: drop.card.stars >= 4 ? 1 : 0.7)
            if drop.card.stars >= 4 {
                Haptics.success()
                after(0.2) { Audio.shared.play(.sparkle, volume: 0.8) }
            } else {
                Haptics.light()
            }
        }
        after(0.62) { busy = false }
    }

    /// Текущая карточка уходит на свое место, из сундука вылетает следующая.
    private func advance() {
        guard stage == .reveal, !busy, let i = current else { return }
        busy = true
        withAnimation(.spring(response: 0.45, dampingFraction: 0.82)) {
            spots[i] = .tray
            current = nil
        }
        Audio.shared.play(.place, volume: 0.5)
        if i + 1 < count {
            after(0.16) { show(i + 1) }
        } else {
            after(0.45) { finish() }
        }
    }

    /// "Показать все": оставшиеся карточки по очереди переворачиваются и встают на места.
    private func revealAll() {
        guard stage == .reveal else { return }
        stage = .collecting
        let rest = spots.indices.filter { spots[$0] != .tray }
        for (k, i) in rest.enumerated() {
            after(Double(k) * 0.09) {
                withAnimation(.spring(response: 0.45, dampingFraction: 0.82)) {
                    spots[i] = .tray
                    faceUp[i] = true
                    if current == i { current = nil }
                }
                Audio.shared.play(.pick, volume: 0.5)
            }
        }
        after(Double(rest.count) * 0.09 + 0.45) { finish() }
    }

    private func finish() {
        guard stage != .summary else { return }
        current = nil
        withAnimation(.spring(response: 0.55, dampingFraction: 0.85)) {
            stage = .summary
            for i in faceUp.indices { faceUp[i] = true }
        }
        Audio.shared.play(.coin)
        if let o = opening, o.drops.contains(where: \.isNew) { Haptics.success() }
    }

    private func after(_ delay: Double, _ action: @escaping () -> Void) {
        DispatchQueue.main.asyncAfter(deadline: .now() + delay, execute: action)
    }

    #if DEBUG
    /// Снимки в CI: -uiChestTaps 3 (сколько тапов сделать), -uiChestAll (сразу все карточки).
    private func debugAutoplay() {
        let taps = UIDebug.value("uiChestTaps").flatMap(Int.init) ?? 0
        // первый тап открывает сундук, следующие ждут, пока перевернется очередная карточка
        func delay(_ k: Int) -> Double { k == 0 ? 0.7 : 1.6 + Double(k) * 0.9 }
        for k in 0..<taps { after(delay(k)) { tap() } }
        if UIDebug.flag("uiChestAll") { after(delay(max(1, taps))) { revealAll() } }
    }
    #endif
}

// MARK: - Раскладка

/// Места на экране: ряд ячеек под карточки сверху, сцена с большой карточкой, сундук снизу.
struct ChestLayout {
    static let ratio: CGFloat = 1.32

    let size: CGSize
    let count: Int
    let summary: Bool

    private var gap: CGFloat { 10 }
    private var top: CGFloat { 96 }
    private var bottom: CGFloat { 110 }

    var cols: Int { count <= 4 ? max(1, count) : (count + 1) / 2 }
    var rows: Int { (count + cols - 1) / cols }

    var slotW: CGFloat {
        let fit = (size.width - 40 - CGFloat(cols - 1) * gap) / CGFloat(cols)
        // в итоге карточки крупнее, но так, чтобы ряд и кнопка помещались по высоте
        let byHeight = (size.height - top - 200 - CGFloat(rows - 1) * gap) / CGFloat(rows) / Self.ratio
        let limit: CGFloat = summary ? min(112, byHeight) : 74
        return max(36, min(limit, fit))
    }

    private var slotH: CGFloat { slotW * Self.ratio }
    private var trayHeight: CGFloat { CGFloat(rows) * slotH + CGFloat(rows - 1) * gap }

    private var trayTop: CGFloat {
        summary ? max(top - 30, (size.height - trayHeight - 170) / 2) : top - 30 + 34
    }

    func slot(_ i: Int) -> CGPoint {
        let row = i / cols
        let col = i % cols
        let inRow = min(cols, count - row * cols)
        let rowWidth = CGFloat(inRow) * slotW + CGFloat(inRow - 1) * gap
        let x0 = (size.width - rowWidth) / 2 + slotW / 2
        return CGPoint(x: x0 + CGFloat(col) * (slotW + gap), y: trayTop + slotH / 2 + CGFloat(row) * (slotH + gap))
    }

    private var trayBottom: CGFloat { trayTop + trayHeight }
    private var stageTop: CGFloat { trayBottom + 16 }
    private var stageBottom: CGFloat { size.height - bottom }
    private var stageH: CGFloat { max(150, stageBottom - stageTop) }

    var chestSize: CGFloat { min(140, stageH * 0.4) }
    var chestCenter: CGPoint { CGPoint(x: size.width / 2, y: stageTop + stageH - chestSize / 2) }

    var bigW: CGFloat { max(90, min(180, size.width * 0.48, (stageH - chestSize * 0.45) / Self.ratio)) }
    var bigCenter: CGPoint {
        let h = bigW * Self.ratio
        return CGPoint(x: size.width / 2, y: max(stageTop + h / 2, chestCenter.y - chestSize * 0.25 - h / 2))
    }

    var closedChestSize: CGFloat { min(220, size.width * 0.56, size.height * 0.3) }
    var closedCenter: CGPoint { CGPoint(x: size.width / 2, y: size.height * 0.44) }
    var raysSize: CGFloat { min(size.width * 1.1, 460) }

    var summaryCenterY: CGFloat { min(size.height - 70, trayBottom + 80) }
}

// MARK: - Детали

/// Карточка с двумя сторонами: угол 0 - лицо, 180 - рубашка. Угол анимируется, сторона меняется на 90°.
struct FlipCard<Front: View, Back: View>: View, Animatable {
    var angle: Double
    let front: Front
    let back: Back

    var animatableData: Double {
        get { angle }
        set { angle = newValue }
    }

    var body: some View {
        ZStack {
            if angle < 90 {
                front
            } else {
                back.rotation3DEffect(.degrees(180), axis: (x: 0, y: 1, z: 0))
            }
        }
        .rotation3DEffect(.degrees(angle), axis: (x: 0, y: 1, z: 0), perspective: 0.45)
    }
}

/// Рубашка карточки альбома.
struct CardBack: View {
    let width: CGFloat

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: width * 0.12, style: .continuous)
        ZStack {
            shape.fill(LinearGradient(colors: [Color(red: 0.96, green: 0.45, blue: 0.30), Theme.ribbonDark],
                                      startPoint: .top, endPoint: .bottom))
            shape.inset(by: width * 0.07)
                .strokeBorder(Theme.gold.opacity(0.85), style: StrokeStyle(lineWidth: width * 0.025, dash: [width * 0.05, width * 0.035]))
            Circle()
                .fill(RadialGradient(colors: [Color(red: 1, green: 0.9, blue: 0.6), Theme.orange], center: .center,
                                     startRadius: 2, endRadius: width * 0.3))
                .frame(width: width * 0.52, height: width * 0.52)
                .overlay(Circle().strokeBorder(Theme.ribbonDark, lineWidth: width * 0.025))
            SpriteImage(name: "icon_cards", size: width * 0.36)
            shape.strokeBorder(Theme.woodDark, lineWidth: width * 0.025)
        }
        .frame(width: width, height: width * ChestLayout.ratio)
    }
}

/// Лучи за сундуком и карточкой.
struct SunRays: Shape {
    var count: Int

    func path(in rect: CGRect) -> Path {
        let c = CGPoint(x: rect.midX, y: rect.midY)
        let r = min(rect.width, rect.height) / 2
        var p = Path()
        let step = Double.pi * 2 / Double(count)
        for k in 0..<count {
            let a = Double(k) * step
            p.move(to: c)
            p.addLine(to: CGPoint(x: c.x + CGFloat(cos(a - step * 0.22)) * r, y: c.y + CGFloat(sin(a - step * 0.22)) * r))
            p.addLine(to: CGPoint(x: c.x + CGFloat(cos(a + step * 0.22)) * r, y: c.y + CGFloat(sin(a + step * 0.22)) * r))
            p.closeSubpath()
        }
        return p
    }
}

/// Вспышка при открытии крышки.
struct ChestFlash: View {
    @State private var go = false

    var body: some View {
        Circle()
            .fill(RadialGradient(colors: [.white, Theme.gold.opacity(0.7), .clear], center: .center, startRadius: 0, endRadius: 140))
            .scaleEffect(go ? 1.8 : 0.2)
            .opacity(go ? 0 : 1)
            .onAppear { withAnimation(.easeOut(duration: 0.75)) { go = true } }
    }
}

/// Тряска сундука: синус от числа качаний, в конце угол снова ноль.
struct ShakeEffect: GeometryEffect {
    var shakes: CGFloat

    var animatableData: CGFloat {
        get { shakes }
        set { shakes = newValue }
    }

    func effectValue(size: CGSize) -> ProjectionTransform {
        let angle = sin(shakes * .pi * 2) * 0.13
        let pivot = CGPoint(x: size.width / 2, y: size.height * 0.85)
        let t = CGAffineTransform(translationX: pivot.x, y: pivot.y)
            .rotated(by: angle)
            .translatedBy(x: -pivot.x, y: -pivot.y)
        return ProjectionTransform(t)
    }
}
