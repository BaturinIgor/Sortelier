import SpriteKit
import UIKit

/// Текстуры эффектов "Рынка": рисуются один раз при первом обращении.
enum M3Art {
    static let colors: [String: UIColor] = [
        "tomato": UIColor(red: 0.95, green: 0.25, blue: 0.20, alpha: 1),
        "lime": UIColor(red: 0.45, green: 0.85, blue: 0.25, alpha: 1),
        "cheese": UIColor(red: 1.00, green: 0.82, blue: 0.20, alpha: 1),
        "grapes": UIColor(red: 0.62, green: 0.35, blue: 0.85, alpha: 1),
        "milk": UIColor(red: 0.35, green: 0.62, blue: 1.00, alpha: 1),
        "carrot": UIColor(red: 1.00, green: 0.55, blue: 0.15, alpha: 1),
    ]

    static func tint(_ item: String?) -> UIColor {
        item.flatMap { colors[$0] } ?? UIColor(red: 1, green: 0.9, blue: 0.6, alpha: 1)
    }

    /// Мягкое круглое свечение.
    static let glow: SKTexture = radial(size: 96, colors: [UIColor.white, UIColor.white.withAlphaComponent(0)])

    /// Четырехлучевая искра.
    static let sparkle: SKTexture = {
        let s: CGFloat = 48
        let image = UIGraphicsImageRenderer(size: CGSize(width: s, height: s)).image { ctx in
            let cg = ctx.cgContext
            let path = UIBezierPath()
            let c = s / 2
            path.move(to: CGPoint(x: c, y: 0))
            path.addQuadCurve(to: CGPoint(x: s, y: c), controlPoint: CGPoint(x: c + 4, y: c - 4))
            path.addQuadCurve(to: CGPoint(x: c, y: s), controlPoint: CGPoint(x: c + 4, y: c + 4))
            path.addQuadCurve(to: CGPoint(x: 0, y: c), controlPoint: CGPoint(x: c - 4, y: c + 4))
            path.addQuadCurve(to: CGPoint(x: c, y: 0), controlPoint: CGPoint(x: c - 4, y: c - 4))
            cg.setFillColor(UIColor.white.cgColor)
            path.fill()
        }
        return SKTexture(image: image)
    }()

    /// Кольцо взрыва.
    static let ring: SKTexture = {
        let s: CGFloat = 128
        let image = UIGraphicsImageRenderer(size: CGSize(width: s, height: s)).image { ctx in
            let cg = ctx.cgContext
            cg.setStrokeColor(UIColor.white.cgColor)
            cg.setLineWidth(10)
            cg.strokeEllipse(in: CGRect(x: 8, y: 8, width: s - 16, height: s - 16))
        }
        return SKTexture(image: image)
    }()

    /// Полоса света для скалки и лучей пончика: яркая середина, мягкие края.
    static let beam: SKTexture = {
        let size = CGSize(width: 64, height: 32)
        let image = UIGraphicsImageRenderer(size: size).image { ctx in
            let colors = [UIColor.white.withAlphaComponent(0).cgColor, UIColor.white.cgColor, UIColor.white.withAlphaComponent(0).cgColor] as CFArray
            guard let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 0.5, 1]) else { return }
            ctx.cgContext.drawLinearGradient(g, start: CGPoint(x: 0, y: 0), end: CGPoint(x: 0, y: size.height), options: [])
        }
        return SKTexture(image: image)
    }()

    /// Подсветка выбранной фишки.
    static let select: SKTexture = {
        let s: CGFloat = 96
        let image = UIGraphicsImageRenderer(size: CGSize(width: s, height: s)).image { ctx in
            let rect = CGRect(x: 6, y: 6, width: s - 12, height: s - 12)
            let path = UIBezierPath(roundedRect: rect, cornerRadius: 18)
            ctx.cgContext.setFillColor(UIColor(red: 1, green: 0.95, blue: 0.6, alpha: 0.55).cgColor)
            path.fill()
            ctx.cgContext.setStrokeColor(UIColor.white.cgColor)
            path.lineWidth = 5
            path.stroke()
        }
        return SKTexture(image: image)
    }()

    private static var iceCache: [Int: SKTexture] = [:]

    /// Лед поверх фишки: 1 слой - прозрачный, 2 слоя - плотный с инеем.
    static func ice(_ layers: Int) -> SKTexture {
        if let t = iceCache[layers] { return t }
        let s: CGFloat = 128
        let image = UIGraphicsImageRenderer(size: CGSize(width: s, height: s)).image { ctx in
            let cg = ctx.cgContext
            let rect = CGRect(x: 5, y: 5, width: s - 10, height: s - 10)
            let path = UIBezierPath(roundedRect: rect, cornerRadius: 22)
            let alpha: CGFloat = layers >= 2 ? 0.72 : 0.42
            let colors = [UIColor(red: 0.86, green: 0.96, blue: 1, alpha: alpha).cgColor,
                          UIColor(red: 0.55, green: 0.80, blue: 0.98, alpha: alpha).cgColor] as CFArray
            cg.saveGState()
            path.addClip()
            if let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: colors, locations: [0, 1]) {
                cg.drawLinearGradient(g, start: CGPoint(x: 0, y: 0), end: CGPoint(x: s, y: s), options: [])
            }
            if layers >= 2 {
                cg.setStrokeColor(UIColor.white.withAlphaComponent(0.7).cgColor)
                cg.setLineWidth(3)
                for (a, b) in [((20.0, 92.0), (52.0, 70.0)), ((52.0, 70.0), (60.0, 98.0)), ((52.0, 70.0), (88.0, 58.0)), ((88.0, 58.0), (108.0, 74.0))] {
                    cg.move(to: CGPoint(x: a.0, y: a.1))
                    cg.addLine(to: CGPoint(x: b.0, y: b.1))
                }
                cg.strokePath()
            }
            cg.restoreGState()
            cg.setStrokeColor(UIColor.white.withAlphaComponent(0.95).cgColor)
            cg.setLineWidth(4)
            cg.addPath(path.cgPath)
            cg.strokePath()
            cg.setLineCap(.round)
            cg.setLineWidth(7)
            cg.setStrokeColor(UIColor.white.withAlphaComponent(0.85).cgColor)
            cg.move(to: CGPoint(x: 26, y: 40))
            cg.addLine(to: CGPoint(x: 44, y: 22))
            cg.move(to: CGPoint(x: 26, y: 62))
            cg.addLine(to: CGPoint(x: 34, y: 54))
            cg.strokePath()
        }
        let texture = SKTexture(image: image)
        iceCache[layers] = texture
        return texture
    }

    private static func radial(size s: CGFloat, colors: [UIColor]) -> SKTexture {
        let image = UIGraphicsImageRenderer(size: CGSize(width: s, height: s)).image { ctx in
            let cgColors = colors.map(\.cgColor) as CFArray
            guard let g = CGGradient(colorsSpace: CGColorSpaceCreateDeviceRGB(), colors: cgColors, locations: [0, 1]) else { return }
            let c = CGPoint(x: s / 2, y: s / 2)
            ctx.cgContext.drawRadialGradient(g, startCenter: c, startRadius: 0, endCenter: c, endRadius: s / 2, options: [])
        }
        return SKTexture(image: image)
    }
}

/// Игровое поле "Рынка". Ходы считает M3Board, сцена проигрывает их ленту событий по своим часам.
final class Match3Scene: SKScene {
    weak var model: Match3Model?

    /// Сколько места сверху (панель целей) и снизу (бустеры) отдано интерфейсу.
    var hudHeight: CGFloat = 170 { didSet { if built { layoutBoard() } } }
    var bottomReserved: CGFloat = 120 { didSet { if built { layoutBoard() } } }

    private let level: M3Level
    private let boardNode = SKNode()
    private let crop = SKCropNode()
    private let tileLayer = SKNode()
    private let overLayer = SKNode()
    private let fxLayer = SKNode()
    private var backing = SKSpriteNode()
    private var cell: CGFloat = 44
    private var built = false

    private var nodes: [Int: SKSpriteNode] = [:]
    private var idAt: [M3Cell: Int] = [:]
    private var crates: [M3Cell: SKSpriteNode] = [:]
    private var ices: [M3Cell: SKSpriteNode] = [:]
    private var jams: [M3Cell: SKSpriteNode] = [:]

    // Проигрывание ленты
    private var queue: [M3Timed] = []
    private var queueIndex = 0
    private var clock: Double = 0
    private var queueEnd: Double = 0
    private var lastTime: TimeInterval = 0
    private var finished: (() -> Void)?
    private(set) var playing = false
    /// Откуда прилетают спецфишки при превращении: от бустеров снизу или от счетчика ходов в финале.
    var convertSource: CGPoint?

    // Ввод
    private var touchCell: M3Cell?
    private var touchStart = CGPoint.zero
    private var swiped = false
    private var selected: M3Cell?
    private var selectNode: SKSpriteNode?
    private var idle: Double = 0
    private var hintShown = false
    private var soundAt: [Audio.Effect: Double] = [:]

    init(level: M3Level) {
        self.level = level
        super.init(size: CGSize(width: 390, height: 844))
        scaleMode = .resizeFill
        backgroundColor = .clear
        anchorPoint = .zero
        addChild(boardNode)
        crop.zPosition = 2
        crop.addChild(tileLayer)
        boardNode.addChild(crop)
        overLayer.zPosition = 3
        boardNode.addChild(overLayer)
        fxLayer.zPosition = 10
        boardNode.addChild(fxLayer)
        var names = level.colors.map { "m3t_" + $0 }
        names += M3Special.allCases.map(\.sprite) + ["m3_crate_1", "m3_crate_2", "m3_crate_3", "m3_jam"]
        SKTexture.preload(names.map { Art.texture($0) }) {}
        _ = (M3Art.glow, M3Art.sparkle, M3Art.ring, M3Art.beam, M3Art.ice(1), M3Art.ice(2))
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func didChangeSize(_ oldSize: CGSize) {
        guard size.width > 10, size.height > 10, model != nil else { return }
        if !built {
            build()
        } else {
            layoutBoard()
        }
    }

    override func didMove(to view: SKView) {
        view.ignoresSiblingOrder = true
        if !built && size.width > 10 && model != nil { build() }
    }

    // MARK: - Раскладка

    private func point(_ p: M3Cell) -> CGPoint {
        CGPoint(x: (CGFloat(p.c) - CGFloat(level.cols - 1) / 2) * cell,
                y: (CGFloat(level.rows - 1) / 2 - CGFloat(p.r)) * cell)
    }

    private func cellAt(_ p: CGPoint) -> M3Cell? {
        let c = Int((p.x / cell + CGFloat(level.cols - 1) / 2).rounded())
        let r = Int((CGFloat(level.rows - 1) / 2 - p.y / cell).rounded())
        let cellPoint = point(M3Cell(r, c))
        guard abs(cellPoint.x - p.x) <= cell / 2 + 1, abs(cellPoint.y - p.y) <= cell / 2 + 1 else { return nil }
        let result = M3Cell(r, c)
        return model?.board.inside(result) == true ? result : nil
    }

    /// Точка сцены в координатах поля (для полетов к целям).
    private func boardPoint(fromScene p: CGPoint) -> CGPoint { boardNode.convert(p, from: self) }

    private func fitCell() -> CGFloat {
        let w = (size.width - 20) / CGFloat(level.cols)
        let h = (size.height - hudHeight - bottomReserved - 16) / CGFloat(level.rows)
        return max(20, min(w, h, 74))
    }

    private func layoutBoard() {
        let newCell = fitCell()
        let free = size.height - hudHeight - bottomReserved
        boardNode.position = CGPoint(x: size.width / 2, y: bottomReserved + free / 2)
        guard abs(newCell - cell) > 0.5 else { return }
        boardNode.setScale(newCell / cell)
    }

    private func build() {
        guard let board = model?.board else { return }
        built = true
        cell = fitCell()
        layoutBoard()
        backing.removeFromParent()
        backing = SKSpriteNode(texture: SKTexture(image: backingImage(board)))
        backing.size = CGSize(width: CGFloat(level.cols) * cell + 20, height: CGFloat(level.rows) * cell + 20)
        backing.zPosition = 0
        boardNode.addChild(backing)
        let mask = SKSpriteNode(texture: SKTexture(image: maskImage(board)))
        mask.size = CGSize(width: CGFloat(level.cols) * cell, height: CGFloat(level.rows) * cell)
        crop.maskNode = mask
        for p in board.allCells where board.inside(p) {
            if board.hasJam(p) { addJam(p) }
            if let tile = board.tile(p) {
                let node = makeNode(tile)
                let target = point(p)
                node.position = CGPoint(x: target.x, y: target.y + CGFloat(level.rows) * cell + cell)
                tileLayer.addChild(node)
                nodes[tile.id] = node
                idAt[p] = tile.id
                let delay = 0.25 + Double(level.rows - p.r) * 0.035 + Double(p.c) * 0.012
                let fall = SKAction.move(to: target, duration: 0.42)
                fall.timingMode = .easeIn
                node.run(.sequence([.wait(forDuration: delay), fall, squash()]))
            }
            if board.crateLeft(p) > 0 { setCrate(p, left: board.crateLeft(p), animated: false) }
            if board.iceLeft(p) > 0 { setIce(p, left: board.iceLeft(p), animated: false) }
        }
        backing.alpha = 0
        backing.setScale(0.92)
        backing.run(.group([.fadeIn(withDuration: 0.3), .scale(to: 1, duration: 0.35)]))
    }

    /// Подложка поля: темная рамка по форме поля и клетки в шахматку.
    private func backingImage(_ board: M3Board) -> UIImage {
        let pad: CGFloat = 10
        let size = CGSize(width: CGFloat(level.cols) * cell + pad * 2, height: CGFloat(level.rows) * cell + pad * 2)
        return UIGraphicsImageRenderer(size: size).image { ctx in
            let cg = ctx.cgContext
            func rect(_ p: M3Cell, inset: CGFloat) -> CGRect {
                CGRect(x: pad + CGFloat(p.c) * cell + inset, y: pad + CGFloat(p.r) * cell + inset,
                       width: cell - inset * 2, height: cell - inset * 2)
            }
            let cells = board.allCells.filter { board.inside($0) }
            cg.setFillColor(UIColor(red: 0.30, green: 0.18, blue: 0.10, alpha: 0.55).cgColor)
            for p in cells {
                cg.addPath(UIBezierPath(roundedRect: rect(p, inset: -7), cornerRadius: 12).cgPath)
            }
            cg.fillPath()
            cg.setFillColor(UIColor(red: 0.98, green: 0.93, blue: 0.84, alpha: 1).cgColor)
            for p in cells {
                cg.addPath(UIBezierPath(roundedRect: rect(p, inset: -2.5), cornerRadius: 9).cgPath)
            }
            cg.fillPath()
            for p in cells {
                let light = (p.r + p.c) % 2 == 0
                cg.setFillColor((light ? UIColor(red: 1.0, green: 0.97, blue: 0.91, alpha: 1)
                                       : UIColor(red: 0.95, green: 0.88, blue: 0.76, alpha: 1)).cgColor)
                cg.addPath(UIBezierPath(roundedRect: rect(p, inset: 1.5), cornerRadius: 7).cgPath)
                cg.fillPath()
            }
        }
    }

    private func maskImage(_ board: M3Board) -> UIImage {
        let size = CGSize(width: CGFloat(level.cols) * cell, height: CGFloat(level.rows) * cell)
        return UIGraphicsImageRenderer(size: size).image { ctx in
            ctx.cgContext.setFillColor(UIColor.white.cgColor)
            for p in board.allCells where board.inside(p) {
                ctx.cgContext.fill(CGRect(x: CGFloat(p.c) * cell - 0.5, y: CGFloat(p.r) * cell - 0.5, width: cell + 1, height: cell + 1))
            }
        }
    }

    // MARK: - Фишки

    private func makeNode(_ tile: M3Tile) -> SKSpriteNode {
        let node = SKSpriteNode()
        node.zPosition = 1
        style(node, tile.kind)
        return node
    }

    private func style(_ node: SKSpriteNode, _ kind: M3Kind) {
        node.removeAction(forKey: "idle")
        node.zRotation = 0
        switch kind {
        case let .color(k):
            node.texture = Art.texture("m3t_" + level.colors[k])
            node.size = CGSize(width: cell * 0.86, height: cell * 0.86)
        case let .special(s):
            node.texture = Art.texture(s.sprite)
            node.size = CGSize(width: cell * 0.98, height: cell * 0.98)
            switch s {
            case .colPin:
                node.zRotation = .pi / 2
                node.run(.repeatForever(.sequence([.scaleY(to: 1.06, duration: 0.5), .scaleY(to: 1, duration: 0.5)])), withKey: "idle")
            case .rowPin:
                node.run(.repeatForever(.sequence([.scaleX(to: 1.06, duration: 0.5), .scaleX(to: 1, duration: 0.5)])), withKey: "idle")
            case .bomb:
                node.run(.repeatForever(.sequence([.scale(to: 1.07, duration: 0.35), .scale(to: 1, duration: 0.35)])), withKey: "idle")
            case .whisk:
                node.run(.repeatForever(.sequence([.rotate(toAngle: 0.14, duration: 0.3), .rotate(toAngle: -0.14, duration: 0.3)])), withKey: "idle")
            case .rainbow:
                node.run(.repeatForever(.rotate(byAngle: -.pi * 2, duration: 4)), withKey: "idle")
            }
        }
    }

    private func squash() -> SKAction {
        .sequence([.group([.scaleX(to: 1.1, duration: 0.05), .scaleY(to: 0.88, duration: 0.05)]),
                   .group([.scaleX(to: 1, duration: 0.09), .scaleY(to: 1, duration: 0.09)])])
    }

    private func addJam(_ p: M3Cell) {
        let jam = SKSpriteNode(texture: Art.texture("m3_jam"))
        jam.size = CGSize(width: cell * 0.98, height: cell * 0.98)
        jam.position = point(p)
        jam.zPosition = 1
        boardNode.addChild(jam)
        jams[p] = jam
    }

    private func setCrate(_ p: M3Cell, left: Int, animated: Bool) {
        if left <= 0 {
            guard let node = crates.removeValue(forKey: p) else { return }
            debris(at: node.position, color: UIColor(red: 0.72, green: 0.48, blue: 0.25, alpha: 1), count: 9)
            node.run(.sequence([.group([.scale(to: 1.25, duration: 0.14), .fadeOut(withDuration: 0.14)]), .removeFromParent()]))
            return
        }
        let node = crates[p] ?? {
            let n = SKSpriteNode()
            n.position = point(p)
            n.zPosition = 2
            overLayer.addChild(n)
            crates[p] = n
            return n
        }()
        node.texture = Art.texture("m3_crate_\(min(3, left))")
        node.size = CGSize(width: cell * 1.0, height: cell * 1.0)
        if animated {
            debris(at: node.position, color: UIColor(red: 0.72, green: 0.48, blue: 0.25, alpha: 1), count: 5)
            node.run(.sequence([.scale(to: 1.12, duration: 0.06), .scale(to: 1, duration: 0.1)]))
        }
    }

    private func setIce(_ p: M3Cell, left: Int, animated: Bool) {
        if left <= 0 {
            guard let node = ices.removeValue(forKey: p) else { return }
            debris(at: node.position, color: UIColor(red: 0.8, green: 0.94, blue: 1, alpha: 1), count: 10)
            node.run(.sequence([.group([.scale(to: 1.2, duration: 0.15), .fadeOut(withDuration: 0.15)]), .removeFromParent()]))
            return
        }
        let node = ices[p] ?? {
            let n = SKSpriteNode()
            n.position = point(p)
            n.zPosition = 3
            overLayer.addChild(n)
            ices[p] = n
            return n
        }()
        node.texture = M3Art.ice(left)
        node.size = CGSize(width: cell * 0.98, height: cell * 0.98)
        if animated {
            debris(at: node.position, color: UIColor(red: 0.8, green: 0.94, blue: 1, alpha: 1), count: 6)
            node.run(.sequence([.scale(to: 1.1, duration: 0.06), .scale(to: 1, duration: 0.1)]))
        }
    }

    // MARK: - Проигрывание

    func play(_ line: M3Timeline, done: @escaping () -> Void) {
        clearSelection()
        stopHint()
        queue = line.events
        queueIndex = 0
        clock = 0
        queueEnd = line.end
        finished = done
        playing = true
    }

    override func update(_ currentTime: TimeInterval) {
        let dt = lastTime == 0 ? 0 : min(1.0 / 30, currentTime - lastTime)
        lastTime = currentTime
        guard !isPaused else { return }
        if playing {
            clock += dt
            while queueIndex < queue.count && queue[queueIndex].t <= clock {
                apply(queue[queueIndex].event)
                queueIndex += 1
            }
            if queueIndex >= queue.count && clock >= queueEnd {
                playing = false
                let done = finished
                finished = nil
                done?()
            }
        } else if model?.canInteract == true {
            idle += dt
            if idle > 5.5 && !hintShown { showHint() }
        }
    }

    private func apply(_ e: M3Event) {
        switch e {
        case let .swap(a, b, back): animateSwap(a, b, back: back)
        case let .pop(id, p, color, toward): pop(id, p, color: color, toward: toward)
        case let .create(tile, p): create(tile, p)
        case let .fire(id, p, fire): fireEffect(id, p, fire)
        case let .combo(a, b, p, _, _): combo(a, b, p)
        case let .convert(id, p, special, color): convert(id, p, special, color: color)
        case let .crate(p, left):
            setCrate(p, left: left, animated: true)
            sound(.crack, volume: 0.6)
            if left == 0 { flyBlocker("crate", from: point(p), texture: Art.texture("m3_crate_1")) }
        case let .ice(p, left):
            setIce(p, left: left, animated: true)
            sound(.glass, volume: 0.5)
            if left == 0 { flyBlocker("ice", from: point(p), texture: M3Art.ice(1)) }
        case let .jam(p):
            if let jam = jams.removeValue(forKey: p) {
                jam.run(.sequence([.group([.scale(to: 0.3, duration: 0.25), .fadeOut(withDuration: 0.25)]), .removeFromParent()]))
                debris(at: jam.position, color: UIColor(red: 0.85, green: 0.15, blue: 0.3, alpha: 1), count: 5)
                flyBlocker("jam", from: point(p), texture: Art.texture("m3_jam"))
            }
        case let .move(id, path, duration): fall(id, path: path, duration: duration)
        case let .spawn(tile, path, duration):
            let node = makeNode(tile)
            node.position = point(path[0])
            tileLayer.addChild(node)
            nodes[tile.id] = node
            fall(tile.id, path: path, duration: duration)
        case let .shuffle(list): shuffle(list)
        case let .booster(kind, p): boosterEffect(kind, p)
        }
    }

    private func animateSwap(_ a: M3Cell, _ b: M3Cell, back: Bool) {
        guard let ia = idAt[a], let ib = idAt[b], let na = nodes[ia], let nb = nodes[ib] else { return }
        let t = M3Board.swapTime
        let pa = point(a), pb = point(b)
        na.zPosition = 2
        nb.zPosition = 1
        func go(_ node: SKSpriteNode, _ to: CGPoint) -> SKAction {
            let m = SKAction.move(to: to, duration: t)
            m.timingMode = .easeInEaseOut
            return m
        }
        if back {
            na.run(.sequence([go(na, pb), go(na, pa)]))
            nb.run(.sequence([go(nb, pa), go(nb, pb)]))
            sound(.invalid, volume: 0.5)
            Haptics.light()
        } else {
            na.run(go(na, pb))
            nb.run(go(nb, pa))
            idAt[a] = ib
            idAt[b] = ia
            sound(.place, volume: 0.6)
        }
    }

    private func pop(_ id: Int, _ p: M3Cell, color: Int, toward: M3Cell?) {
        guard let node = nodes.removeValue(forKey: id) else { return }
        if idAt[p] == id { idAt[p] = nil }
        node.removeAllActions()
        let item = level.colors[color]
        if let goal = model?.claimFlight(item: item) {
            flyToGoal(node, goal: goal)
        } else if let toward = toward {
            let move = SKAction.move(to: point(toward), duration: 0.14)
            move.timingMode = .easeIn
            node.run(.sequence([.group([move, .scale(to: 0.7, duration: 0.14)]), .fadeOut(withDuration: 0.04), .removeFromParent()]))
        } else {
            node.run(.sequence([.scale(to: 1.18, duration: 0.06),
                                .group([.scale(to: 0.1, duration: 0.12), .fadeOut(withDuration: 0.12)]),
                                .removeFromParent()]))
        }
        burst(at: point(p), tint: M3Art.tint(item), count: 5)
        sound(.pop, volume: 0.55)
    }

    private func create(_ tile: M3Tile, _ p: M3Cell) {
        let node = makeNode(tile)
        node.position = point(p)
        node.setScale(0.2)
        tileLayer.addChild(node)
        nodes[tile.id] = node
        idAt[p] = tile.id
        node.run(.sequence([.scale(to: 1.22, duration: 0.12), .scale(to: 1, duration: 0.1)]))
        flash(at: point(p), scale: 1.6, color: UIColor(red: 1, green: 0.95, blue: 0.7, alpha: 1))
        sound(.dish, volume: 0.5)
        Haptics.light()
    }

    private func convert(_ id: Int, _ p: M3Cell, _ special: M3Special, color: Int?) {
        let target = point(p)
        if let k = color, let node = nodes[id], let goal = model?.claimFlight(item: level.colors[k]) {
            let copy = SKSpriteNode(texture: node.texture, size: node.size)
            copy.position = node.position
            tileLayer.addChild(copy)
            flyToGoal(copy, goal: goal)
        }
        let node: SKSpriteNode
        if let existing = nodes[id] {
            node = existing
        } else {
            node = makeNode(M3Tile(id: id, kind: .special(special)))
            node.position = target
            tileLayer.addChild(node)
            nodes[id] = node
        }
        if let source = convertSource {
            // спецфишка прилетает от бустеров или от счетчика ходов и садится на фишку
            let flyer = SKSpriteNode(texture: Art.texture(special.sprite), size: CGSize(width: cell, height: cell))
            flyer.position = boardPoint(fromScene: source)
            flyer.zPosition = 20
            if special == .colPin { flyer.zRotation = .pi / 2 }
            fxLayer.addChild(flyer)
            let path = arcPath(from: flyer.position, to: target, lift: cell * 2)
            let fly = SKAction.follow(path, asOffset: false, orientToPath: false, duration: 0.4)
            fly.timingMode = .easeInEaseOut
            flyer.run(.sequence([fly, .removeFromParent()]))
            node.run(.sequence([.wait(forDuration: 0.4), .run { [weak self] in
                self?.style(node, .special(special))
                node.setScale(1.3)
                node.run(.scale(to: 1, duration: 0.15))
                self?.flash(at: target, scale: 1.4, color: .white)
            }]))
            sound(.pick, volume: 0.5)
        } else {
            style(node, .special(special))
            node.setScale(1.3)
            node.run(.scale(to: 1, duration: 0.15))
            flash(at: target, scale: 1.3, color: .white)
            sound(.pick, volume: 0.4)
        }
    }

    private func fall(_ id: Int, path: [M3Cell], duration: Double) {
        guard let node = nodes[id], let last = path.last else { return }
        if let first = path.first, idAt[first] == id { idAt[first] = nil }
        for (cellKey, value) in idAt where value == id && cellKey != last { idAt[cellKey] = nil }
        idAt[last] = id
        node.removeAction(forKey: "fall")
        let points = path.map(point)
        let action: SKAction
        if points.count == 2 {
            action = .move(to: points[1], duration: duration)
        } else {
            let cg = CGMutablePath()
            cg.move(to: node.position)
            for p in points.dropFirst() { cg.addLine(to: p) }
            action = .follow(cg, asOffset: false, orientToPath: false, duration: duration)
        }
        // равноускоренное падение: все фишки падают с одним ускорением и не наезжают друг на друга
        action.timingFunction = { t in t * t }
        node.run(.sequence([action, squash()]), withKey: "fall")
        if duration > 0.2 { sound(.coin, volume: 0.06) }
    }

    private func shuffle(_ list: [(id: Int, cell: M3Cell)]) {
        idAt = [:]
        for (i, entry) in list.enumerated() {
            guard let node = nodes[entry.id] else { continue }
            idAt[entry.cell] = entry.id
            let center = CGPoint.zero
            let out = SKAction.move(to: CGPoint(x: (node.position.x + center.x) / 2, y: (node.position.y + center.y) / 2), duration: 0.22)
            out.timingMode = .easeIn
            let back = SKAction.move(to: point(entry.cell), duration: 0.28)
            back.timingMode = .easeOut
            node.run(.sequence([.wait(forDuration: Double(i % 7) * 0.008), .group([out, .rotate(byAngle: .pi, duration: 0.22)]),
                                .group([back, .rotate(byAngle: .pi, duration: 0.28)])]))
        }
        sound(.combo, volume: 0.5)
    }

    // MARK: - Эффекты спецфишек

    private func fireEffect(_ id: Int?, _ p: M3Cell, _ fire: M3Fire) {
        let origin = point(p)
        if let id = id, let node = nodes.removeValue(forKey: id) {
            if idAt[p] == id { idAt[p] = nil }
            node.removeAllActions()
            node.run(.sequence([.scale(to: 1.35, duration: 0.07), .group([.scale(to: 0.2, duration: 0.1), .fadeOut(withDuration: 0.1)]), .removeFromParent()]))
        }
        switch fire.special {
        case .rowPin, .colPin:
            let half = fire.width / 2
            for d in -half...half {
                if fire.cross || fire.special == .rowPin { pinLine(origin: origin, offset: CGFloat(d), horizontal: true, width: fire.width) }
                if fire.cross || fire.special == .colPin { pinLine(origin: origin, offset: CGFloat(d), horizontal: false, width: fire.width) }
            }
            sound(.swoosh, volume: 0.6)
            Haptics.light()
        case .bomb:
            let reach = (CGFloat(fire.radius) * 2 + 1) * cell
            let ring = SKSpriteNode(texture: M3Art.ring, size: CGSize(width: cell, height: cell))
            ring.position = origin
            ring.color = UIColor(red: 1, green: 0.7, blue: 0.3, alpha: 1)
            ring.colorBlendFactor = 1
            fxLayer.addChild(ring)
            ring.run(.sequence([.group([.scale(to: reach / cell * 1.1, duration: 0.3), .fadeOut(withDuration: 0.3)]), .removeFromParent()]))
            flash(at: origin, scale: reach / cell * 0.9, color: UIColor(red: 1, green: 0.85, blue: 0.5, alpha: 1))
            burst(at: origin, tint: UIColor(red: 1, green: 0.6, blue: 0.2, alpha: 1), count: 14, spread: reach * 0.5)
            shake(CGFloat(fire.radius) * 2.5)
            sound(.boom, volume: 0.8)
            Haptics.success()
        case .whisk:
            spin(at: origin, texture: Art.texture("m3_whisk"))
            for target in fire.targets {
                let flyer = SKSpriteNode(texture: Art.texture("m3_whisk"), size: CGSize(width: cell * 0.95, height: cell * 0.95))
                flyer.position = origin
                flyer.zPosition = 20
                if let carry = fire.carry {
                    let rider = SKSpriteNode(texture: Art.texture(carry.sprite), size: CGSize(width: cell * 0.8, height: cell * 0.8))
                    rider.position = CGPoint(x: 0, y: cell * 0.35)
                    rider.zPosition = 1
                    flyer.addChild(rider)
                }
                fxLayer.addChild(flyer)
                let path = arcPath(from: origin, to: point(target), lift: cell * 1.6)
                let fly = SKAction.follow(path, asOffset: false, orientToPath: false, duration: M3Board.whiskFlight)
                fly.timingMode = .easeInEaseOut
                flyer.run(.sequence([.group([fly, .rotate(byAngle: .pi * 4, duration: M3Board.whiskFlight)]),
                                     .group([.scale(to: 1.4, duration: 0.08), .fadeOut(withDuration: 0.08)]), .removeFromParent()]))
            }
            sound(.swoosh, volume: 0.45)
        case .rainbow:
            spin(at: origin, texture: Art.texture("m3_rainbow"))
            if fire.all {
                flash(at: .zero, scale: CGFloat(max(level.rows, level.cols)) * 1.4, color: .white)
                let ring = SKSpriteNode(texture: M3Art.ring, size: CGSize(width: cell, height: cell))
                ring.position = origin
                fxLayer.addChild(ring)
                ring.run(.sequence([.group([.scale(to: CGFloat(level.rows + level.cols), duration: 0.6), .fadeOut(withDuration: 0.6)]), .removeFromParent()]))
                shake(10)
                Haptics.success()
            } else {
                let tint = M3Art.tint(fire.color.map { level.colors[$0] })
                for (i, target) in fire.targets.enumerated() {
                    beam(from: origin, to: point(target), tint: tint, delay: 0.22 + 0.028 * Double(i) - 0.06)
                }
            }
            sound(.sparkle, volume: 0.6)
        }
    }

    private func pinLine(origin: CGPoint, offset: CGFloat, horizontal: Bool, width: Int) {
        let start = horizontal ? CGPoint(x: origin.x, y: origin.y + offset * cell) : CGPoint(x: origin.x + offset * cell, y: origin.y)
        let length = CGFloat(horizontal ? level.cols : level.rows) * cell + cell * 2
        let streak = SKSpriteNode(texture: M3Art.beam, size: CGSize(width: length, height: cell * 0.7))
        streak.position = horizontal ? CGPoint(x: 0, y: start.y) : CGPoint(x: start.x, y: 0)
        if !horizontal { streak.zRotation = .pi / 2 }
        streak.color = UIColor(red: 1, green: 0.9, blue: 0.55, alpha: 1)
        streak.colorBlendFactor = 0.6
        streak.alpha = 0
        streak.blendMode = .add
        fxLayer.addChild(streak)
        streak.run(.sequence([.fadeAlpha(to: 0.9, duration: 0.06), .wait(forDuration: 0.12), .fadeOut(withDuration: 0.25), .removeFromParent()]))
        let cells = CGFloat(horizontal ? level.cols : level.rows)
        let duration = 0.032 * Double(cells)
        for dir in [-1.0, 1.0] as [CGFloat] {
            let pin = SKSpriteNode(texture: Art.texture("m3_pin"), size: CGSize(width: cell * 0.95, height: cell * 0.95))
            pin.position = start
            pin.zPosition = 20
            if !horizontal { pin.zRotation = .pi / 2 }
            fxLayer.addChild(pin)
            let to = horizontal ? CGPoint(x: start.x + dir * cells * cell, y: start.y) : CGPoint(x: start.x, y: start.y + dir * cells * cell)
            pin.run(.sequence([.move(to: to, duration: duration), .fadeOut(withDuration: 0.08), .removeFromParent()]))
            trail(pin, tint: UIColor(red: 1, green: 0.85, blue: 0.5, alpha: 1), duration: duration)
        }
    }

    private func combo(_ a: Int, _ b: Int, _ p: M3Cell) {
        let target = point(p)
        for id in [a, b] {
            guard let node = nodes.removeValue(forKey: id) else { continue }
            for (k, v) in idAt where v == id { idAt[k] = nil }
            node.removeAllActions()
            node.zPosition = 5
            let move = SKAction.move(to: target, duration: 0.12)
            move.timingMode = .easeIn
            node.run(.sequence([.group([move, .scale(to: 1.4, duration: 0.12), .rotate(byAngle: .pi, duration: 0.12)]),
                                .group([.scale(to: 2, duration: 0.1), .fadeOut(withDuration: 0.1)]), .removeFromParent()]))
        }
        flash(at: target, scale: 3, color: UIColor(red: 1, green: 0.95, blue: 0.7, alpha: 1))
        sound(.star2, volume: 0.6)
        Haptics.success()
    }

    private func boosterEffect(_ kind: M3Booster, _ p: M3Cell) {
        let target = point(p)
        let icon = SKSpriteNode(texture: Art.texture(kind.icon), size: CGSize(width: cell * 1.5, height: cell * 1.5))
        icon.zPosition = 30
        fxLayer.addChild(icon)
        switch kind {
        case .mallet:
            icon.position = CGPoint(x: target.x + cell * 0.6, y: target.y + cell * 0.9)
            icon.zRotation = 0.6
            icon.alpha = 0
            icon.run(.sequence([.fadeIn(withDuration: 0.08), .rotate(toAngle: -0.5, duration: 0.2),
                                .run { [weak self] in self?.shake(4); self?.flash(at: target, scale: 1.5, color: .white) },
                                .wait(forDuration: 0.12), .fadeOut(withDuration: 0.15), .removeFromParent()]))
        case .knife:
            let left = point(M3Cell(p.r, 0)), right = point(M3Cell(p.r, level.cols - 1))
            icon.position = CGPoint(x: left.x - cell, y: left.y)
            icon.run(.sequence([.move(to: CGPoint(x: right.x + cell, y: right.y), duration: 0.32 + 0.035 * Double(level.cols)),
                                .fadeOut(withDuration: 0.1), .removeFromParent()]))
            trail(icon, tint: .white, duration: 0.6)
        case .spatula:
            let top = point(M3Cell(0, p.c)), bottom = point(M3Cell(level.rows - 1, p.c))
            icon.position = CGPoint(x: top.x, y: top.y + cell)
            icon.run(.sequence([.move(to: CGPoint(x: bottom.x, y: bottom.y - cell), duration: 0.32 + 0.035 * Double(level.rows)),
                                .fadeOut(withDuration: 0.1), .removeFromParent()]))
            trail(icon, tint: .white, duration: 0.6)
        case .mixer:
            icon.position = .zero
            icon.setScale(0.3)
            icon.run(.sequence([.group([.scale(to: 1.3, duration: 0.25), .rotate(byAngle: .pi * 4, duration: 0.6)]),
                                .group([.fadeOut(withDuration: 0.2), .scale(to: 1.8, duration: 0.2)]), .removeFromParent()]))
        default:
            icon.removeFromParent()
        }
        Haptics.light()
        sound(.pick, volume: 0.6)
    }

    // MARK: - Частицы

    private func flash(at p: CGPoint, scale: CGFloat, color: UIColor) {
        let glow = SKSpriteNode(texture: M3Art.glow, size: CGSize(width: cell, height: cell))
        glow.position = p
        glow.color = color
        glow.colorBlendFactor = 1
        glow.blendMode = .add
        glow.zPosition = 15
        glow.alpha = 0.9
        fxLayer.addChild(glow)
        glow.run(.sequence([.group([.scale(to: scale, duration: 0.18), .fadeOut(withDuration: 0.25)]), .removeFromParent()]))
    }

    private func burst(at p: CGPoint, tint: UIColor, count: Int, spread: CGFloat? = nil) {
        let spread = spread ?? cell * 0.75
        for i in 0..<count {
            let s = SKSpriteNode(texture: i % 2 == 0 ? M3Art.sparkle : M3Art.glow, size: CGSize(width: cell * 0.32, height: cell * 0.32))
            s.position = p
            s.color = tint
            s.colorBlendFactor = i % 2 == 0 ? 0.35 : 1
            s.zPosition = 16
            fxLayer.addChild(s)
            let a = CGFloat(i) / CGFloat(count) * .pi * 2 + CGFloat.random(in: -0.3...0.3)
            let d = spread * CGFloat.random(in: 0.6...1.1)
            let move = SKAction.moveBy(x: cos(a) * d, y: sin(a) * d, duration: 0.32)
            move.timingMode = .easeOut
            s.run(.sequence([.group([move, .scale(to: 0.2, duration: 0.32), .fadeOut(withDuration: 0.32)]), .removeFromParent()]))
        }
    }

    private func debris(at p: CGPoint, color: UIColor, count: Int) {
        for i in 0..<count {
            let s = SKSpriteNode(color: color, size: CGSize(width: cell * 0.14, height: cell * 0.1))
            s.position = p
            s.zPosition = 16
            s.zRotation = CGFloat(i)
            fxLayer.addChild(s)
            let a = CGFloat(i) / CGFloat(count) * .pi * 2
            let d = cell * CGFloat.random(in: 0.5...0.9)
            let up = SKAction.moveBy(x: cos(a) * d, y: sin(a) * d + cell * 0.3, duration: 0.18)
            up.timingMode = .easeOut
            let down = SKAction.moveBy(x: cos(a) * d * 0.3, y: -cell * 0.7, duration: 0.22)
            down.timingMode = .easeIn
            s.run(.sequence([.group([.sequence([up, down]), .rotate(byAngle: 4, duration: 0.4), .sequence([.wait(forDuration: 0.2), .fadeOut(withDuration: 0.2)])]),
                             .removeFromParent()]))
        }
    }

    private func spin(at p: CGPoint, texture: SKTexture) {
        let node = SKSpriteNode(texture: texture, size: CGSize(width: cell, height: cell))
        node.position = p
        node.zPosition = 18
        fxLayer.addChild(node)
        node.run(.sequence([.group([.rotate(byAngle: .pi * 2, duration: 0.3), .scale(to: 1.4, duration: 0.3)]),
                            .group([.fadeOut(withDuration: 0.12), .scale(to: 1.8, duration: 0.12)]), .removeFromParent()]))
    }

    private func beam(from a: CGPoint, to b: CGPoint, tint: UIColor, delay: Double) {
        let dx = b.x - a.x, dy = b.y - a.y
        let length = max(1, hypot(dx, dy))
        let beam = SKSpriteNode(texture: M3Art.beam, size: CGSize(width: length, height: cell * 0.32))
        beam.anchorPoint = CGPoint(x: 0, y: 0.5)
        beam.position = a
        beam.zRotation = atan2(dy, dx)
        beam.color = tint
        beam.colorBlendFactor = 0.7
        beam.blendMode = .add
        beam.zPosition = 17
        beam.xScale = 0
        beam.alpha = 0
        fxLayer.addChild(beam)
        beam.run(.sequence([.wait(forDuration: max(0, delay)), .fadeIn(withDuration: 0.01),
                            .scaleX(to: 1, duration: 0.07), .fadeOut(withDuration: 0.18), .removeFromParent()]))
        let spark = SKSpriteNode(texture: M3Art.sparkle, size: CGSize(width: cell * 0.6, height: cell * 0.6))
        spark.position = b
        spark.zPosition = 18
        spark.alpha = 0
        fxLayer.addChild(spark)
        spark.run(.sequence([.wait(forDuration: max(0, delay) + 0.07), .fadeIn(withDuration: 0.02),
                             .group([.rotate(byAngle: 1.5, duration: 0.25), .scale(to: 1.6, duration: 0.25), .fadeOut(withDuration: 0.25)]),
                             .removeFromParent()]))
    }

    /// След за летящей скалкой: искры через равные промежутки.
    private func trail(_ node: SKNode, tint: UIColor, duration: Double) {
        let step = 0.035
        let count = max(1, Int(duration / step))
        node.run(.repeat(.sequence([.wait(forDuration: step), .run { [weak self, weak node] in
            guard let self = self, let node = node, let parent = node.parent else { return }
            let s = SKSpriteNode(texture: M3Art.glow, size: CGSize(width: self.cell * 0.5, height: self.cell * 0.5))
            s.position = node.position
            s.color = tint
            s.colorBlendFactor = 1
            s.blendMode = .add
            s.zPosition = 14
            parent.addChild(s)
            s.run(.sequence([.group([.scale(to: 0.2, duration: 0.25), .fadeOut(withDuration: 0.25)]), .removeFromParent()]))
        }]), count: count))
    }

    private func shake(_ amount: CGFloat) {
        guard boardNode.action(forKey: "shake") == nil else { return }
        let base = boardNode.position
        var steps: [SKAction] = []
        for i in 0..<6 {
            let k = amount * CGFloat(6 - i) / 6
            steps.append(.move(to: CGPoint(x: base.x + CGFloat.random(in: -k...k), y: base.y + CGFloat.random(in: -k...k)), duration: 0.03))
        }
        steps.append(.move(to: base, duration: 0.03))
        boardNode.run(.sequence(steps), withKey: "shake")
    }

    private func arcPath(from a: CGPoint, to b: CGPoint, lift: CGFloat) -> CGPath {
        let path = CGMutablePath()
        path.move(to: a)
        let mid = CGPoint(x: (a.x + b.x) / 2, y: max(a.y, b.y) + lift)
        path.addQuadCurve(to: b, control: mid)
        return path
    }

    // MARK: - Полет к целям

    private func flyToGoal(_ node: SKSpriteNode, goal: Int) {
        guard let model = model else {
            node.removeFromParent()
            return
        }
        let start = node.convert(CGPoint.zero, to: self)
        node.removeFromParent()
        node.removeAllActions()
        node.position = start
        node.zPosition = 100
        node.setScale(boardNode.xScale)
        addChild(node)
        let end = model.goalPoint(goal)
        let path = CGMutablePath()
        path.move(to: start)
        let control = CGPoint(x: start.x + (end.x - start.x) * 0.2 + CGFloat.random(in: -40...40), y: max(start.y, end.y) + 60)
        path.addQuadCurve(to: end, control: control)
        let distance = hypot(end.x - start.x, end.y - start.y)
        let duration = 0.38 + Double(distance) / 1600
        let fly = SKAction.follow(path, asOffset: false, orientToPath: false, duration: duration)
        fly.timingMode = .easeIn
        node.run(.sequence([.scale(to: boardNode.xScale * 1.2, duration: 0.08),
                            .group([fly, .scale(to: 0.55, duration: duration)]),
                            .run { [weak model] in model?.flightArrived(goal) },
                            .removeFromParent()]))
    }

    private func flyBlocker(_ type: String, from p: CGPoint, texture: SKTexture) {
        guard let goal = model?.claimFlight(type: type) else { return }
        let node = SKSpriteNode(texture: texture, size: CGSize(width: cell * 0.8, height: cell * 0.8))
        node.position = p
        node.zPosition = 30
        fxLayer.addChild(node)
        flyToGoal(node, goal: goal)
    }

    // MARK: - Ввод

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        idle = 0
        stopHint()
        guard let touch = touches.first, !playing, model?.canInteract == true else { return }
        let p = touch.location(in: boardNode)
        touchCell = cellAt(p)
        touchStart = p
        swiped = false
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let touch = touches.first, let from = touchCell, !swiped, !playing, let model = model,
              model.canInteract, model.targeting == nil else { return }
        let p = touch.location(in: boardNode)
        let dx = p.x - touchStart.x, dy = p.y - touchStart.y
        guard max(abs(dx), abs(dy)) > cell * 0.32 else { return }
        swiped = true
        let to = abs(dx) > abs(dy) ? M3Cell(from.r, from.c + (dx > 0 ? 1 : -1)) : M3Cell(from.r + (dy > 0 ? -1 : 1), from.c)
        clearSelection()
        trySwap(from, to)
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        defer { touchCell = nil }
        guard let cellTouched = touchCell, !swiped, !playing, let model = model, model.canInteract else { return }
        if model.targeting != nil {
            if let line = model.useTargeted(at: cellTouched) {
                play(line) { [weak model] in model?.lineFinished(line) }
            }
            return
        }
        if model.board.tile(cellTouched)?.kind.special != nil && selected == nil {
            if let line = model.tap(cellTouched) {
                play(line) { [weak model] in model?.lineFinished(line) }
            }
            return
        }
        if let sel = selected {
            clearSelection()
            if abs(sel.r - cellTouched.r) + abs(sel.c - cellTouched.c) == 1 {
                trySwap(sel, cellTouched)
                return
            }
            if sel == cellTouched { return }
        }
        select(cellTouched)
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        touchCell = nil
    }

    private func trySwap(_ a: M3Cell, _ b: M3Cell) {
        guard let model = model else { return }
        if let line = model.swap(a, b) {
            play(line) { [weak model] in model?.lineFinished(line) }
        } else if let id = idAt[a], let node = nodes[id] {
            node.run(.sequence([.moveBy(x: 4, y: 0, duration: 0.04), .moveBy(x: -8, y: 0, duration: 0.06), .moveBy(x: 4, y: 0, duration: 0.04)]))
            sound(.invalid, volume: 0.4)
        }
    }

    private func select(_ p: M3Cell) {
        guard let id = idAt[p], let node = nodes[id], model?.board.movable(p) == true else { return }
        selected = p
        let ring = SKSpriteNode(texture: M3Art.select, size: CGSize(width: cell, height: cell))
        ring.position = point(p)
        ring.zPosition = 0.5
        ring.run(.repeatForever(.sequence([.fadeAlpha(to: 0.6, duration: 0.4), .fadeAlpha(to: 1, duration: 0.4)])))
        tileLayer.addChild(ring)
        selectNode = ring
        node.run(.scale(to: 1.1, duration: 0.08))
        sound(.pick, volume: 0.4)
    }

    private func clearSelection() {
        if let p = selected, let id = idAt[p], let node = nodes[id] { node.run(.scale(to: 1, duration: 0.08)) }
        selected = nil
        selectNode?.removeFromParent()
        selectNode = nil
    }

    // MARK: - Подсказка

    private var hinted: [SKSpriteNode] = []

    private func showHint() {
        hintShown = true
        guard let h = model?.board.hint(), let ia = idAt[h.0], let ib = idAt[h.1], let na = nodes[ia], let nb = nodes[ib] else { return }
        let (a, b) = h
        let dx = (point(b).x - point(a).x) * 0.12, dy = (point(b).y - point(a).y) * 0.12
        let wiggle = SKAction.repeatForever(.sequence([.moveBy(x: dx, y: dy, duration: 0.18), .moveBy(x: -dx, y: -dy, duration: 0.18),
                                                       .moveBy(x: dx, y: dy, duration: 0.18), .moveBy(x: -dx, y: -dy, duration: 0.18),
                                                       .wait(forDuration: 0.9)]))
        let back = SKAction.repeatForever(.sequence([.moveBy(x: -dx, y: -dy, duration: 0.18), .moveBy(x: dx, y: dy, duration: 0.18),
                                                     .moveBy(x: -dx, y: -dy, duration: 0.18), .moveBy(x: dx, y: dy, duration: 0.18),
                                                     .wait(forDuration: 0.9)]))
        na.run(wiggle, withKey: "hint")
        nb.run(back, withKey: "hint")
        hinted = [na, nb]
    }

    private func stopHint() {
        idle = 0
        hintShown = false
        for node in hinted {
            node.removeAction(forKey: "hint")
            if let id = nodes.first(where: { $0.value === node })?.key, let p = idAt.first(where: { $0.value == id })?.key {
                node.run(.move(to: point(p), duration: 0.08))
            }
        }
        hinted = []
    }

    // MARK: - Звук

    private func sound(_ effect: Audio.Effect, volume: Float) {
        let now = lastTime
        if let last = soundAt[effect], now - last < 0.06 { return }
        soundAt[effect] = now
        Audio.shared.play(effect, volume: volume)
    }
}
