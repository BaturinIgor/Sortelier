import SpriteKit
import UIKit

/// Спрайт продукта на полке.
final class PieceNode: SKNode {
    let uid: Int
    let item: String
    private let sprite: SKSpriteNode
    private let shadow: SKSpriteNode
    private let mystery: SKNode
    private var iceNode: SKNode?
    private var size: CGFloat
    private(set) var isMystery = false
    private(set) var isDim = false
    /// Сколько покупателей осталось до того, как растает лед.
    private(set) var iceLeft = 0

    init(piece: Piece, size: CGFloat) {
        uid = piece.uid
        item = piece.item
        self.size = size
        sprite = SKSpriteNode(texture: Art.texture(piece.item))
        sprite.size = CGSize(width: size, height: size)
        shadow = SKSpriteNode(texture: Art.shadow)
        shadow.size = CGSize(width: size * 0.78, height: size * 0.24)
        shadow.position = CGPoint(x: 0, y: -size * 0.42)
        shadow.zPosition = -1
        shadow.alpha = 0.55
        let bubble = SKShapeNode(circleOfRadius: size * 0.3)
        bubble.fillColor = UIColor(red: 0.45, green: 0.30, blue: 0.20, alpha: 1)
        bubble.strokeColor = UIColor(red: 0.95, green: 0.85, blue: 0.70, alpha: 1)
        bubble.lineWidth = 2
        let mark = SKLabelNode(text: "?")
        mark.fontName = "AvenirNext-Heavy"
        mark.fontSize = size * 0.38
        mark.fontColor = .white
        mark.verticalAlignmentMode = .center
        bubble.addChild(mark)
        mystery = bubble
        super.init()
        addChild(shadow)
        addChild(sprite)
        addChild(mystery)
        setMystery(piece.hidden)
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    func resize(_ size: CGFloat) {
        let changed = abs(size - self.size) > 0.5
        self.size = size
        sprite.size = CGSize(width: size, height: size)
        shadow.size = CGSize(width: size * 0.78, height: size * 0.24)
        shadow.position = CGPoint(x: 0, y: -size * 0.42)
        if changed && iceLeft > 0 { drawIce() }
    }

    /// Лед поверх продукта с числом покупателей до оттаивания. 0 - растаял.
    func setIce(_ left: Int, animated: Bool) {
        guard left != iceLeft else { return }
        let was = iceLeft
        iceLeft = left
        if left > 0 {
            drawIce()
            if animated && was > left { iceNode?.run(.sequence([.scale(to: 1.12, duration: 0.08), .scale(to: 1, duration: 0.1)])) }
            return
        }
        guard let ice = iceNode else { return }
        iceNode = nil
        if animated {
            // лед трескается: осколки разлетаются
            for i in 0..<8 {
                let shard = SKShapeNode(rectOf: CGSize(width: size * 0.12, height: size * 0.07), cornerRadius: 2)
                shard.fillColor = UIColor(red: 0.80, green: 0.94, blue: 1.0, alpha: 0.9)
                shard.strokeColor = .white
                shard.lineWidth = 1
                shard.zPosition = 5
                shard.zRotation = CGFloat(i) * 0.8
                addChild(shard)
                let a = CGFloat(i) / 8 * 2 * .pi
                shard.run(.sequence([.group([.moveBy(x: cos(a) * size * 0.6, y: sin(a) * size * 0.6, duration: 0.35),
                                             .rotate(byAngle: 2, duration: 0.35), .fadeOut(withDuration: 0.35)]),
                                     .removeFromParent()]))
            }
            ice.run(.sequence([.group([.scale(to: 1.25, duration: 0.18), .fadeOut(withDuration: 0.18)]), .removeFromParent()]))
            Audio.shared.play(.invalid, volume: 0.25)
        } else {
            ice.removeFromParent()
        }
    }

    private func drawIce() {
        iceNode?.removeFromParent()
        let node = SKNode()
        node.zPosition = 4
        let w = size * 0.94
        let block = SKShapeNode(rectOf: CGSize(width: w, height: w * 1.02), cornerRadius: size * 0.16)
        block.fillColor = UIColor(red: 0.72, green: 0.90, blue: 1.0, alpha: 0.5)
        block.strokeColor = UIColor(white: 1, alpha: 0.9)
        block.lineWidth = 2
        node.addChild(block)
        // блики на льду
        for (x, y, l) in [(-0.22, 0.2, 0.32), (-0.06, 0.3, 0.16), (0.24, -0.22, 0.2)] as [(CGFloat, CGFloat, CGFloat)] {
            let path = CGMutablePath()
            path.move(to: CGPoint(x: (x - l / 2) * w, y: (y - l / 2) * w))
            path.addLine(to: CGPoint(x: (x + l / 2) * w, y: (y + l / 2) * w))
            let line = SKShapeNode(path: path)
            line.strokeColor = UIColor(white: 1, alpha: 0.85)
            line.lineWidth = 2.5
            line.lineCap = .round
            node.addChild(line)
        }
        let badge = SKShapeNode(circleOfRadius: max(8, size * 0.17))
        badge.fillColor = UIColor(red: 0.20, green: 0.55, blue: 0.90, alpha: 1)
        badge.strokeColor = .white
        badge.lineWidth = 1.5
        badge.position = CGPoint(x: w * 0.4, y: w * 0.42)
        let label = SKLabelNode(text: "\(iceLeft)")
        label.fontName = "AvenirNext-Heavy"
        label.fontSize = max(10, size * 0.22)
        label.fontColor = .white
        label.verticalAlignmentMode = .center
        badge.addChild(label)
        node.addChild(badge)
        addChild(node)
        iceNode = node
    }

    func setMystery(_ hidden: Bool) {
        isMystery = hidden
        sprite.isHidden = hidden
        mystery.isHidden = !hidden
    }

    func setDim(_ dim: Bool, animated: Bool) {
        isDim = dim
        shadow.isHidden = dim
        // задний ряд заметно темнее и холоднее переднего, чтобы его не путали
        let factor: CGFloat = dim ? 0.58 : 0
        sprite.color = UIColor(red: 0.10, green: 0.07, blue: 0.08, alpha: 1)
        if animated {
            sprite.run(.colorize(with: .black, colorBlendFactor: factor, duration: 0.2))
        } else {
            sprite.colorBlendFactor = factor
        }
    }

    func swapToDish(_ dish: String, size: CGFloat) {
        sprite.texture = Art.texture("dish_" + dish)
        sprite.size = CGSize(width: size, height: size)
        sprite.colorBlendFactor = 0
        shadow.isHidden = true
        setMystery(false)
    }
}

/// Игровое поле: полки, продукты, покупатели за прилавком.
final class GameScene: SKScene {
    let session: GameSession

    /// Сверху под интерфейс SwiftUI (включая безопасную зону).
    var hudHeight: CGFloat = 100 { didSet { if oldValue != hudHeight { rebuild() } } }
    /// Снизу под панель бустеров.
    var bottomReserved: CGFloat = 110 { didSet { if oldValue != bottomReserved { rebuild() } } }

    /// Прилавок с покупателями над полками.
    private let counterHeight: CGFloat = 126
    private let plankHeight: CGFloat = 28
    // Разметка спрайта полки из tools/render/environment.py (доли размера картинки)
    private let shelfAspect: CGFloat = 720.0 / 368.0
    private let shelfInner: CGFloat = 0.897
    private let shelfFloor: CGFloat = 0.126

    private var shelfFrames: [CGRect] = []
    private var shelfNodes: [SKSpriteNode] = []
    private var depthBadges: [SKNode] = []
    private var pieceNodes: [Int: PieceNode] = [:]
    private let board = SKNode()
    private let customersLayer = SKNode()
    private var customerNodes: [Int: CustomerNode] = [:]
    private var plank: SKNode?
    private var queueBadge: SKNode?
    private var lockNodes: [Int: SKNode] = [:]
    private var pauseBadge: SKNode?
    private var itemSize: CGFloat = 40
    private var shelfWidth: CGFloat = 120

    private struct Drag {
        let uid: Int
        let shelf: Int
        let slot: Int
        let start: CGPoint
        var moved: Bool
    }

    private var drag: Drag?
    private var selected: (shelf: Int, slot: Int)?
    private var selectionRing: SKShapeNode?

    init(session: GameSession) {
        self.session = session
        super.init(size: CGSize(width: 390, height: 844))
        scaleMode = .resizeFill
        backgroundColor = .clear
        addChild(board)
        addChild(customersLayer)
        session.onReset = { [weak self] in
            self?.clearSelection()
            self?.rebuild()
        }
        session.onHint = { [weak self] from, slot, to in
            self?.showHint(from: from, slot: slot, to: to)
        }
        session.onPause = { [weak self] in
            Audio.shared.play(.unlock, volume: 0.5)
            self?.refreshCustomers()
        }
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    override func didMove(to view: SKView) {
        view.isMultipleTouchEnabled = false
        rebuild()
    }

    override func didChangeSize(_ oldSize: CGSize) {
        super.didChangeSize(oldSize)
        if oldSize != size { rebuild() }
    }

    // MARK: - Раскладка

    private var shelfArea: CGRect {
        let top = size.height - hudHeight - counterHeight - 10
        return CGRect(x: 10, y: bottomReserved, width: size.width - 20, height: max(100, top - bottomReserved))
    }

    private func computeLayout() {
        let n = max(1, session.board.shelves.count)
        let area = shelfArea
        let gapX: CGFloat = 10
        let gapY: CGFloat = 16
        var best: (w: CGFloat, cols: Int) = (0, 1)
        for cols in 1...3 where cols <= n {
            let rows = Int((Double(n) / Double(cols)).rounded(.up))
            let byWidth = (area.width - gapX * CGFloat(cols - 1)) / CGFloat(cols)
            let byHeight = (area.height - gapY * CGFloat(rows - 1)) / CGFloat(rows) * shelfAspect
            let w = min(byWidth, byHeight, 250)
            if w > best.w + 1 { best = (w, cols) }
        }
        shelfWidth = best.w
        let h = shelfWidth / shelfAspect
        let cols = best.cols
        let rows = Int((Double(n) / Double(cols)).rounded(.up))
        let totalH = CGFloat(rows) * h + CGFloat(rows - 1) * gapY
        let top = area.midY + totalH / 2
        shelfFrames = (0..<n).map { i in
            let row = i / cols
            let inRow = min(cols, n - row * cols)
            let rowW = CGFloat(inRow) * shelfWidth + CGFloat(inRow - 1) * gapX
            let col = i % cols
            let x = area.midX - rowW / 2 + CGFloat(col) * (shelfWidth + gapX)
            let y = top - CGFloat(row + 1) * h - CGFloat(row) * gapY
            return CGRect(x: x, y: y, width: shelfWidth, height: h)
        }
        itemSize = shelfWidth * shelfInner / 3
    }

    private func slotPosition(_ shelf: Int, _ slot: Int) -> CGPoint {
        let f = shelfFrames[shelf]
        let step = f.width * shelfInner / 3
        return CGPoint(x: f.midX + CGFloat(slot - 1) * step, y: f.minY + f.height * shelfFloor + itemSize * 0.45)
    }

    private func peekPosition(_ shelf: Int, _ slot: Int) -> CGPoint {
        let p = slotPosition(shelf, slot)
        return CGPoint(x: p.x, y: p.y + itemSize * 0.27)
    }

    // MARK: - Построение

    func rebuild() {
        guard size.width > 0, size.height > 0 else { return }
        computeLayout()
        board.removeAllChildren()
        shelfNodes = []
        depthBadges = []
        pieceNodes = [:]
        let texture = Art.texture(PlayerProgress.shared.goldShelves ? "shelf_gold" : "shelf")
        for frame in shelfFrames {
            let node = SKSpriteNode(texture: texture)
            node.size = frame.size
            node.position = CGPoint(x: frame.midX, y: frame.midY)
            node.zPosition = 0
            board.addChild(node)
            shelfNodes.append(node)
        }
        lockNodes = [:]
        sync(animated: false)
        updateLocks(animated: false)
        buildCounter()
        layoutCustomers(animated: false)
    }

    private struct Target {
        let position: CGPoint
        let scale: CGFloat
        let dim: Bool
        let mystery: Bool
        let z: CGFloat
        var ice = 0
    }

    private func targets() -> [Int: (Piece, Target)] {
        var result: [Int: (Piece, Target)] = [:]
        let b = session.board
        for s in b.shelves.indices where s < shelfFrames.count {
            for (k, piece) in b.front(s).enumerated() {
                guard let piece = piece else { continue }
                result[piece.uid] = (piece, Target(position: slotPosition(s, k), scale: 1, dim: false, mystery: false, z: 20,
                                                   ice: b.iceLeft(piece)))
            }
            if let peek = b.peek(s) {
                for (k, piece) in peek.enumerated() {
                    guard let piece = piece else { continue }
                    result[piece.uid] = (piece, Target(position: peekPosition(s, k), scale: 0.72, dim: true,
                                                       mystery: piece.hidden, z: 10, ice: piece.hidden ? 0 : b.iceLeft(piece)))
                }
            }
        }
        return result
    }

    private func sync(animated: Bool, delay: TimeInterval = 0) {
        let all = targets()
        for (uid, node) in pieceNodes where all[uid] == nil {
            pieceNodes[uid] = nil
            if animated {
                node.run(.sequence([.fadeOut(withDuration: 0.15), .removeFromParent()]))
            } else {
                node.removeFromParent()
            }
        }
        for (uid, entry) in all {
            let (piece, target) = entry
            if let node = pieceNodes[uid] {
                node.zPosition = target.z
                node.resize(itemSize)
                if node.isMystery != target.mystery { node.setMystery(target.mystery) }
                if node.isDim != target.dim { node.setDim(target.dim, animated: animated) }
                node.setIce(target.ice, animated: animated)
                if animated {
                    let move = SKAction.move(to: target.position, duration: 0.18)
                    move.timingMode = .easeOut
                    let group = SKAction.group([move, .scale(to: target.scale, duration: 0.18)])
                    if node.position != target.position || node.xScale != target.scale {
                        node.run(delay > 0 ? .sequence([.wait(forDuration: delay), group]) : group, withKey: "sync")
                    }
                } else {
                    node.position = target.position
                    node.setScale(target.scale)
                }
            } else {
                let node = PieceNode(piece: piece, size: itemSize)
                node.position = target.position
                node.setScale(target.scale)
                node.zPosition = target.z
                node.setDim(target.dim, animated: false)
                node.setIce(target.ice, animated: false)
                board.addChild(node)
                pieceNodes[uid] = node
                if animated {
                    node.alpha = 0
                    node.run(.sequence([.wait(forDuration: delay), .fadeIn(withDuration: 0.2)]))
                }
            }
        }
        updateDepthBadges()
    }

    private func updateDepthBadges() {
        depthBadges.forEach { $0.removeFromParent() }
        depthBadges = []
        let b = session.board
        for s in b.shelves.indices where s < shelfFrames.count {
            let hiddenRows = b.depth(s) - 2
            guard hiddenRows > 0 else { continue }
            let f = shelfFrames[s]
            let badge = SKShapeNode(rectOf: CGSize(width: 30, height: 18), cornerRadius: 9)
            badge.fillColor = UIColor(red: 0.35, green: 0.22, blue: 0.14, alpha: 0.9)
            badge.strokeColor = .clear
            badge.position = CGPoint(x: f.maxX - 20, y: f.maxY - 8)
            badge.zPosition = 30
            let label = SKLabelNode(text: "+\(hiddenRows)")
            label.fontName = "AvenirNext-Bold"
            label.fontSize = 12
            label.fontColor = .white
            label.verticalAlignmentMode = .center
            badge.addChild(label)
            board.addChild(badge)
            depthBadges.append(badge)
        }
    }

    // MARK: - Замки полок

    /// Замок поверх закрытой полки: число покупателей до открытия.
    private func updateLocks(animated: Bool) {
        let b = session.board
        for s in b.shelves.indices where s < shelfFrames.count {
            let left = b.lockLeft(s)
            if left > 0 {
                if let node = lockNodes[s], node.userData?["left"] as? Int == left { continue }
                let pulse = lockNodes[s] != nil && animated
                lockNodes[s]?.removeFromParent()
                let node = makeLock(frame: shelfFrames[s], left: left)
                board.addChild(node)
                lockNodes[s] = node
                if pulse { node.childNode(withName: "padlock")?.run(.sequence([.rotate(toAngle: -0.2, duration: 0.06),
                                                                                .rotate(toAngle: 0.2, duration: 0.1),
                                                                                .rotate(toAngle: 0, duration: 0.06)])) }
            } else if let node = lockNodes[s] {
                lockNodes[s] = nil
                if animated {
                    let padlock = node.childNode(withName: "padlock")
                    padlock?.run(.sequence([.rotate(toAngle: -0.25, duration: 0.07), .rotate(toAngle: 0.25, duration: 0.1),
                                            .rotate(toAngle: 0, duration: 0.07),
                                            .group([.moveBy(x: 0, y: 30, duration: 0.3), .scale(to: 1.3, duration: 0.3)])]))
                    node.run(.sequence([.wait(forDuration: 0.25), .fadeOut(withDuration: 0.25), .removeFromParent()]))
                    Audio.shared.play(.unlock, volume: 0.6)
                } else {
                    node.removeFromParent()
                }
            }
        }
    }

    private func makeLock(frame f: CGRect, left: Int) -> SKNode {
        let node = SKNode()
        node.userData = ["left": left]
        node.position = CGPoint(x: f.midX, y: f.midY)
        node.zPosition = 60
        let veil = SKShapeNode(rectOf: CGSize(width: f.width - 6, height: f.height - 4), cornerRadius: 10)
        veil.fillColor = UIColor(red: 0.22, green: 0.13, blue: 0.08, alpha: 0.42)
        veil.strokeColor = UIColor(red: 0.85, green: 0.62, blue: 0.20, alpha: 0.9)
        veil.lineWidth = 2
        node.addChild(veil)
        // цепь поперек полки
        let chain = SKShapeNode(rectOf: CGSize(width: f.width - 14, height: 5), cornerRadius: 2.5)
        chain.fillColor = UIColor(red: 0.70, green: 0.70, blue: 0.74, alpha: 1)
        chain.strokeColor = UIColor(red: 0.45, green: 0.45, blue: 0.50, alpha: 1)
        chain.lineWidth = 1
        node.addChild(chain)
        let padlock = SKNode()
        padlock.name = "padlock"
        let r = min(f.height * 0.2, 20)
        let shackle = SKShapeNode()
        let path = CGMutablePath()
        path.addArc(center: CGPoint(x: 0, y: r * 0.55), radius: r * 0.62, startAngle: 0, endAngle: .pi, clockwise: false)
        shackle.path = path
        shackle.strokeColor = UIColor(red: 0.62, green: 0.62, blue: 0.66, alpha: 1)
        shackle.lineWidth = r * 0.28
        padlock.addChild(shackle)
        let body = SKShapeNode(rectOf: CGSize(width: r * 2, height: r * 1.6), cornerRadius: r * 0.35)
        body.fillColor = UIColor(red: 1.0, green: 0.76, blue: 0.20, alpha: 1)
        body.strokeColor = UIColor(red: 0.70, green: 0.45, blue: 0.08, alpha: 1)
        body.lineWidth = 2
        body.position = CGPoint(x: 0, y: -r * 0.3)
        padlock.addChild(body)
        let label = SKLabelNode(text: "\(left)")
        label.fontName = "AvenirNext-Heavy"
        label.fontSize = r * 1.05
        label.fontColor = UIColor(red: 0.42, green: 0.25, blue: 0.08, alpha: 1)
        label.verticalAlignmentMode = .center
        label.position = CGPoint(x: 0, y: -r * 0.32)
        padlock.addChild(label)
        node.addChild(padlock)
        return node
    }

    private var lastObstacleTip = Date.distantPast

    /// Подсказка над полкой: почему нельзя (лед, замок).
    private func obstacleFeedback(_ key: String, shelf: Int, uid: Int? = nil) {
        Haptics.warning()
        Audio.shared.play(.invalid, volume: 0.7)
        if let uid = uid, let node = pieceNodes[uid] {
            node.run(.sequence([.moveBy(x: -4, y: 0, duration: 0.04), .moveBy(x: 8, y: 0, duration: 0.06),
                                .moveBy(x: -8, y: 0, duration: 0.06), .moveBy(x: 4, y: 0, duration: 0.04)]))
        } else if let lock = lockNodes[shelf]?.childNode(withName: "padlock") {
            lock.run(.sequence([.rotate(toAngle: -0.2, duration: 0.05), .rotate(toAngle: 0.2, duration: 0.08),
                                .rotate(toAngle: 0, duration: 0.05)]))
        }
        guard Date().timeIntervalSince(lastObstacleTip) > 1.5, shelf < shelfFrames.count else { return }
        lastObstacleTip = Date()
        toast(Lang.shared.t(key), above: shelfFrames[shelf])
    }

    private func toast(_ text: String, above f: CGRect) {
        let label = SKLabelNode(text: text)
        label.fontName = "AvenirNext-Bold"
        label.fontSize = 13
        label.fontColor = .white
        label.verticalAlignmentMode = .center
        let back = SKShapeNode(rectOf: CGSize(width: label.frame.width + 22, height: 28), cornerRadius: 14)
        back.fillColor = UIColor(red: 0.36, green: 0.22, blue: 0.13, alpha: 0.95)
        back.strokeColor = .clear
        back.addChild(label)
        let x = min(max(f.midX, back.frame.width / 2 + 8), size.width - back.frame.width / 2 - 8)
        back.position = CGPoint(x: x, y: f.maxY + 18)
        back.zPosition = 150
        back.alpha = 0
        board.addChild(back)
        back.run(.sequence([.fadeIn(withDuration: 0.12), .wait(forDuration: 1.4), .fadeOut(withDuration: 0.25),
                            .removeFromParent()]))
    }

    // MARK: - Покупатели

    private var counterRect: CGRect {
        CGRect(x: 0, y: size.height - hudHeight - counterHeight, width: size.width, height: counterHeight)
    }

    private var slotWidth: CGFloat { (size.width - 16 - 40) / CGFloat(Board.counter) }

    private func customerSlot(_ i: Int) -> CGPoint {
        CGPoint(x: 8 + slotWidth * (CGFloat(i) + 0.5), y: counterRect.minY + plankHeight)
    }

    private func look(of customer: Customer) -> Int {
        customer.gourmet ? CustomerNode.gourmetLook : (customer.uid * 7 + session.level.id * 3) % CustomerNode.looks
    }

    private func buildCounter() {
        plank?.removeFromParent()
        let rect = counterRect
        let node: SKSpriteNode
        if let image = UIImage(named: "counter") {
            node = SKSpriteNode(texture: SKTexture(image: image))
        } else {
            node = SKSpriteNode(color: UIColor(red: 0.55, green: 0.32, blue: 0.16, alpha: 1), size: .zero)
        }
        node.size = CGSize(width: size.width + 4, height: plankHeight + 6)
        node.position = CGPoint(x: size.width / 2, y: rect.minY + plankHeight / 2 - 2)
        node.zPosition = 4
        customersLayer.addChild(node)
        plank = node
    }

    private func layoutCustomers(animated: Bool) {
        let b = session.board
        let visible = Array(b.queue.prefix(Board.counter))
        let ids = Set(visible.map(\.uid))
        for (uid, node) in customerNodes where !ids.contains(uid) {
            customerNodes[uid] = nil
            if animated {
                if !node.leaving { node.leave() }
            } else {
                node.removeFromParent()
            }
        }
        for (i, c) in visible.enumerated() {
            let pos = customerSlot(i)
            let node: CustomerNode
            if let existing = customerNodes[c.uid] {
                node = existing
                if animated {
                    let move = SKAction.move(to: pos, duration: 0.3)
                    move.timingMode = .easeInEaseOut
                    node.run(move, withKey: "move")
                } else {
                    node.removeAction(forKey: "move")
                    node.position = pos
                }
            } else {
                node = CustomerNode(customer: c, look: look(of: c), slotWidth: slotWidth, plankHeight: plankHeight)
                node.zPosition = 3
                customersLayer.addChild(node)
                customerNodes[c.uid] = node
                if animated {
                    node.position = CGPoint(x: pos.x + 70, y: pos.y)
                    node.alpha = 0
                    let move = SKAction.move(to: pos, duration: 0.35)
                    move.timingMode = .easeOut
                    node.run(.group([move, .fadeIn(withDuration: 0.25)]), withKey: "move")
                } else {
                    node.position = pos
                }
            }
            node.update(patience: c.patience, max: b.patienceMax, coins: Balance.coinsPerOrder + b.tip(for: c),
                        tip: b.tip(for: c), paused: b.pauseLeft > 0, animated: animated)
        }
        updateQueueBadge(waiting: b.queue.count - visible.count)
        updatePauseBadge()
    }

    /// После хода: тает терпение у тех, кто у прилавка.
    private func refreshCustomers() {
        let b = session.board
        for c in b.queue.prefix(Board.counter) {
            guard let node = customerNodes[c.uid], !node.leaving else { continue }
            node.update(patience: c.patience, max: b.patienceMax, coins: Balance.coinsPerOrder + b.tip(for: c),
                        tip: b.tip(for: c), paused: b.pauseLeft > 0, animated: true)
        }
        updatePauseBadge()
    }

    /// Плашка над прилавком, пока терпение на паузе.
    private func updatePauseBadge() {
        let left = session.board.pauseLeft
        if left == 0 {
            if let badge = pauseBadge {
                pauseBadge = nil
                badge.run(.sequence([.fadeOut(withDuration: 0.2), .removeFromParent()]))
            }
            return
        }
        pauseBadge?.removeFromParent()
        let label = SKLabelNode(text: Lang.shared.t("game.pause", left))
        label.fontName = "AvenirNext-Heavy"
        label.fontSize = 13
        label.fontColor = .white
        label.verticalAlignmentMode = .center
        let back = SKShapeNode(rectOf: CGSize(width: label.frame.width + 24, height: 24), cornerRadius: 12)
        back.fillColor = UIColor(red: 0.25, green: 0.55, blue: 0.90, alpha: 0.95)
        back.strokeColor = .white
        back.lineWidth = 1.5
        back.addChild(label)
        back.position = CGPoint(x: size.width / 2, y: counterRect.minY - 2)
        back.zPosition = 20
        customersLayer.addChild(back)
        pauseBadge = back
    }

    private func updateQueueBadge(waiting: Int) {
        queueBadge?.removeFromParent()
        queueBadge = nil
        guard waiting > 0 else { return }
        let badge = SKShapeNode(rectOf: CGSize(width: 36, height: 44), cornerRadius: 12)
        badge.fillColor = UIColor(red: 0.98, green: 0.93, blue: 0.84, alpha: 0.95)
        badge.strokeColor = UIColor(red: 0.85, green: 0.70, blue: 0.50, alpha: 1)
        badge.lineWidth = 1.5
        badge.position = CGPoint(x: size.width - 8 - 18, y: counterRect.minY + plankHeight + 34)
        badge.zPosition = 5
        // силуэт человека: голова и плечи
        let ink = UIColor(red: 0.55, green: 0.38, blue: 0.25, alpha: 1)
        let head = SKShapeNode(circleOfRadius: 4)
        head.fillColor = ink
        head.strokeColor = .clear
        head.position = CGPoint(x: 0, y: 14)
        badge.addChild(head)
        let body = SKShapeNode(rectOf: CGSize(width: 14, height: 7), cornerRadius: 3.5)
        body.fillColor = ink
        body.strokeColor = .clear
        body.position = CGPoint(x: 0, y: 5)
        badge.addChild(body)
        let label = SKLabelNode(text: "+\(waiting)")
        label.fontName = "AvenirNext-Heavy"
        label.fontSize = 14
        label.fontColor = UIColor(red: 0.45, green: 0.30, blue: 0.20, alpha: 1)
        label.verticalAlignmentMode = .center
        label.position = CGPoint(x: 0, y: -9)
        badge.addChild(label)
        customersLayer.addChild(badge)
        queueBadge = badge
    }

    // MARK: - Касания

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard session.phase == .playing, let touch = touches.first else { return }
        let p = touch.location(in: self)
        if let hit = frontPiece(at: p) {
            let b = session.board
            if b.isLocked(hit.shelf) {
                // тап по закрытой полке может быть целью для выбранного продукта
                if let sel = selected, sel.shelf != hit.shelf { clearSelection() }
                obstacleFeedback("game.lock", shelf: hit.shelf)
                return
            }
            if let piece = b.front(hit.shelf)[hit.slot], b.isFrozen(piece) {
                if let sel = selected, sel.shelf != hit.shelf, b.canPlace(on: hit.shelf) {
                    attemptMove(from: sel.shelf, slot: sel.slot, to: hit.shelf)
                    clearSelection()
                } else {
                    clearSelection()
                    obstacleFeedback("game.ice", shelf: hit.shelf, uid: hit.uid)
                }
                return
            }
            drag = Drag(uid: hit.uid, shelf: hit.shelf, slot: hit.slot, start: p, moved: false)
            if let node = pieceNodes[hit.uid] {
                node.removeAllActions()
                node.zPosition = 100
                node.run(.scale(to: 1.15, duration: 0.08))
            }
            Audio.shared.play(.pick, volume: 0.7)
            return
        }
        if let sel = selected, let target = shelf(at: p), target != sel.shelf {
            attemptMove(from: sel.shelf, slot: sel.slot, to: target)
            clearSelection()
        } else if let back = peekPiece(at: p) {
            clearSelection()
            backRowFeedback(uid: back.uid, shelf: back.shelf)
        } else {
            clearSelection()
        }
    }

    private func peekPiece(at p: CGPoint) -> (uid: Int, shelf: Int)? {
        let b = session.board
        for s in b.shelves.indices where s < shelfFrames.count {
            guard let peek = b.peek(s) else { continue }
            for (k, piece) in peek.enumerated() {
                guard let piece = piece else { continue }
                let c = peekPosition(s, k)
                let r = CGRect(x: c.x - itemSize * 0.4, y: c.y - itemSize * 0.4, width: itemSize * 0.8, height: itemSize * 0.8)
                if r.contains(p) { return (piece.uid, s) }
            }
        }
        return nil
    }

    private var lastBackRowTip = Date.distantPast

    /// Тап по продукту из заднего ряда: он не берется, объясняем почему.
    private func backRowFeedback(uid: Int, shelf: Int) {
        Haptics.warning()
        Audio.shared.play(.invalid, volume: 0.7)
        if let node = pieceNodes[uid] {
            node.run(.sequence([.moveBy(x: -4, y: 0, duration: 0.04), .moveBy(x: 8, y: 0, duration: 0.06),
                                .moveBy(x: -8, y: 0, duration: 0.06), .moveBy(x: 4, y: 0, duration: 0.04)]))
        }
        guard Date().timeIntervalSince(lastBackRowTip) > 1.5, shelf < shelfFrames.count else { return }
        lastBackRowTip = Date()
        toast(Lang.shared.t("game.backrow"), above: shelfFrames[shelf])
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard var d = drag, let touch = touches.first, let node = pieceNodes[d.uid] else { return }
        let p = touch.location(in: self)
        if hypot(p.x - d.start.x, p.y - d.start.y) > 8 { d.moved = true }
        drag = d
        if d.moved {
            node.position = CGPoint(x: p.x, y: p.y + itemSize * 0.35)
        }
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let d = drag, let touch = touches.first else { return }
        drag = nil
        let p = touch.location(in: self)
        if !d.moved {
            returnToPlace(d.uid)
            if let sel = selected, sel.shelf == d.shelf, sel.slot == d.slot {
                clearSelection()
            } else if let sel = selected, sel.shelf != d.shelf, session.board.canPlace(on: d.shelf) {
                // тап по продукту на другой полке со свободным местом тоже переносит выбранный
                clearSelection()
                attemptMove(from: sel.shelf, slot: sel.slot, to: d.shelf)
            } else {
                select(shelf: d.shelf, slot: d.slot, uid: d.uid)
            }
            return
        }
        clearSelection()
        if let target = shelf(at: p), target != d.shelf {
            attemptMove(from: d.shelf, slot: d.slot, to: target)
        } else {
            returnToPlace(d.uid)
        }
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        if let d = drag { returnToPlace(d.uid) }
        drag = nil
    }

    private func frontPiece(at p: CGPoint) -> (uid: Int, shelf: Int, slot: Int)? {
        let b = session.board
        for s in b.shelves.indices where s < shelfFrames.count {
            for (k, piece) in b.front(s).enumerated() {
                guard let piece = piece else { continue }
                let c = slotPosition(s, k)
                let r = CGRect(x: c.x - itemSize * 0.55, y: c.y - itemSize * 0.6, width: itemSize * 1.1, height: itemSize * 1.2)
                if r.contains(p) { return (piece.uid, s, k) }
            }
        }
        return nil
    }

    private func shelf(at p: CGPoint) -> Int? {
        if let i = shelfFrames.firstIndex(where: { $0.insetBy(dx: -6, dy: -10).contains(p) }) { return i }
        // если палец чуть мимо, берем ближайшую полку
        var best: (Int, CGFloat)?
        for (i, f) in shelfFrames.enumerated() {
            let d = hypot(p.x - f.midX, p.y - f.midY)
            if d < f.width * 0.7, best == nil || d < best!.1 { best = (i, d) }
        }
        return best?.0
    }

    private func returnToPlace(_ uid: Int) {
        guard let node = pieceNodes[uid], let entry = targets()[uid] else { return }
        node.zPosition = entry.1.z
        let move = SKAction.move(to: entry.1.position, duration: 0.15)
        move.timingMode = .easeOut
        node.run(.group([move, .scale(to: entry.1.scale, duration: 0.15)]))
    }

    private func select(shelf: Int, slot: Int, uid: Int) {
        clearSelection()
        selected = (shelf, slot)
        guard let node = pieceNodes[uid] else { return }
        let ring = SKShapeNode(circleOfRadius: itemSize * 0.52)
        ring.strokeColor = UIColor(red: 1, green: 0.75, blue: 0.2, alpha: 1)
        ring.lineWidth = 3
        ring.fillColor = UIColor(red: 1, green: 0.85, blue: 0.4, alpha: 0.25)
        ring.position = node.position
        ring.zPosition = 15
        ring.run(.repeatForever(.sequence([.scale(to: 1.08, duration: 0.4), .scale(to: 1, duration: 0.4)])))
        board.addChild(ring)
        selectionRing = ring
        Haptics.light()
    }

    private func clearSelection() {
        selected = nil
        selectionRing?.removeFromParent()
        selectionRing = nil
    }

    // MARK: - Ход и анимации

    private func attemptMove(from src: Int, slot: Int, to dst: Int) {
        let pieceUid = session.board.front(src)[slot]?.uid
        guard let outcome = session.move(from: src, slot: slot, to: dst) else {
            if let uid = pieceUid { returnToPlace(uid) }
            if session.board.isLocked(dst) {
                obstacleFeedback("game.lock", shelf: dst)
                return
            }
            Audio.shared.play(.invalid, volume: 0.7)
            if session.board.freeSlot(in: dst) == nil, dst < shelfNodes.count {
                shelfNodes[dst].run(.sequence([.moveBy(x: -5, y: 0, duration: 0.05), .moveBy(x: 10, y: 0, duration: 0.08),
                                               .moveBy(x: -5, y: 0, duration: 0.05)]))
            }
            return
        }
        Haptics.light()
        Audio.shared.play(.place, volume: 0.8)
        if let node = pieceNodes[outcome.piece.uid] {
            node.removeAllActions()
            node.zPosition = 20
            let move = SKAction.move(to: slotPosition(outcome.to, outcome.toSlot), duration: 0.1)
            move.timingMode = .easeOut
            // мягкий отскок при приземлении на полку
            let squash = SKAction.scaleX(to: 1.08, y: 0.9, duration: 0.05)
            let settle = SKAction.scale(to: 1, duration: 0.09)
            settle.timingMode = .easeOut
            node.run(.sequence([.group([move, .scale(to: 1, duration: 0.1)]), squash, settle]))
        }
        // Поле не блокируется: следующий ход можно делать сразу, анимации идут параллельно.
        var delay: TimeInterval = 0.1
        var combo = session.combo - outcome.fires.count
        for event in outcome.events {
            switch event {
            case let .fire(fire):
                combo += 1
                animateFire(fire, coins: session.coins(for: fire, combo: combo), delay: delay)
                delay += 0.1
            case let .transform(t):
                animateTransform(t, delay: delay)
                delay += 0.2
            }
        }
        sync(animated: true, delay: outcome.fires.isEmpty ? 0 : 0.12)
        if !outcome.fires.isEmpty {
            run(.sequence([.wait(forDuration: delay + 0.2), .run { [weak self] in self?.updateLocks(animated: true) }]))
        }
        refreshCustomers()
        if !outcome.fires.isEmpty {
            removeAction(forKey: "orders")
            run(.sequence([.wait(forDuration: delay + 0.75),
                           .run { [weak self] in self?.layoutCustomers(animated: true) }]), withKey: "orders")
        }
        removeAction(forKey: "end")
        run(.sequence([.wait(forDuration: outcome.fires.isEmpty ? 0.12 : delay + 0.45),
                       .run { [weak self] in
                           self?.session.presentPendingDish()
                           self?.session.checkEnd()
                       }]), withKey: "end")
    }

    private func animateFire(_ fire: Fire, coins: Int, delay: TimeInterval) {
        let nodes = fire.pieces.compactMap { pieceNodes[$0.uid] }
        let f = shelfFrames[fire.shelf]
        let center = CGPoint(x: f.midX, y: slotPosition(fire.shelf, 1).y + itemSize * 0.2)
        let customer = customerNodes[fire.customer.uid]
        if let customer = customer {
            customer.leaving = true
            customerNodes[fire.customer.uid] = nil
        }
        let target: CGPoint
        if let customer = customer {
            target = CGPoint(x: customer.position.x + customer.bubbleCenter.x, y: customer.position.y + customer.bubbleCenter.y)
        } else if let badge = queueBadge {
            target = badge.position
        } else {
            target = CGPoint(x: counterRect.midX, y: counterRect.midY)
        }
        let combo = session.combo
        let size = itemSize
        for (i, node) in nodes.enumerated() {
            node.zPosition = 120
            node.setIce(0, animated: false)
            let gather = SKAction.move(to: center, duration: 0.14)
            gather.timingMode = .easeIn
            var steps: [SKAction] = [.wait(forDuration: delay), .group([gather, .scale(to: 1.1, duration: 0.14)])]
            if i == 0 {
                if fire.order.kind == .dish {
                    steps.append(.run { node.swapToDish(fire.order.target, size: size * 1.3) })
                }
                steps.append(.scale(to: 1.35, duration: 0.07))
                let fly = SKAction.move(to: target, duration: 0.28)
                fly.timingMode = .easeInEaseOut
                steps.append(.group([fly, .scale(to: 0.6, duration: 0.28)]))
                steps.append(.run {
                    customer?.celebrate(coins: coins) {}
                    Audio.shared.play(.coin, volume: 0.7)
                })
                steps.append(.removeFromParent())
            } else {
                steps.append(.group([.fadeOut(withDuration: 0.08), .scale(to: 0.3, duration: 0.08)]))
                steps.append(.removeFromParent())
            }
            node.run(.sequence(steps))
        }
        run(.sequence([.wait(forDuration: delay + 0.14), .run { [weak self] in
            guard let self = self else { return }
            Haptics.success()
            Audio.shared.play(fire.order.kind == .dish ? .dish : .triple)
            self.burst(at: center, dish: fire.order.kind == .dish)
            self.comboPopup(combo: combo)
            if customer == nil { self.coinPopup(at: center, coins: coins) }
        }]))
        for piece in fire.pieces {
            pieceNodes[piece.uid] = nil
        }
    }

    /// Цепочка: три продукта слетаются в средний слот и становятся одним.
    private func animateTransform(_ t: Transform, delay: TimeInterval) {
        guard t.shelf < shelfFrames.count else { return }
        let center = slotPosition(t.shelf, t.slot)
        for piece in t.pieces {
            guard let node = pieceNodes[piece.uid] else { continue }
            pieceNodes[piece.uid] = nil
            node.removeAllActions()
            node.setDim(false, animated: false)
            node.setMystery(false)
            node.setIce(0, animated: false)
            node.zPosition = 110
            let gather = SKAction.move(to: center, duration: 0.16)
            gather.timingMode = .easeIn
            node.run(.sequence([.wait(forDuration: delay), .group([gather, .scale(to: 1, duration: 0.16)]),
                                .group([.fadeOut(withDuration: 0.08), .scale(to: 0.4, duration: 0.08)]),
                                .removeFromParent()]))
        }
        let made = PieceNode(piece: t.result, size: itemSize)
        made.position = center
        made.zPosition = 20
        made.alpha = 0
        made.setScale(1)
        board.addChild(made)
        pieceNodes[t.result.uid] = made
        made.run(.sequence([.wait(forDuration: delay + 0.18), .fadeIn(withDuration: 0.01),
                            .scale(to: 1.35, duration: 0.1), .scale(to: 1, duration: 0.12)]), withKey: "made")
        run(.sequence([.wait(forDuration: delay + 0.18), .run { [weak self] in
            Haptics.light()
            Audio.shared.play(.triple, volume: 0.6)
            self?.burst(at: center, dish: false)
        }]))
    }

    private func burst(at point: CGPoint, dish: Bool) {
        let colors: [UIColor] = dish
            ? [.systemYellow, .systemOrange, .systemPink, .white]
            : [.systemYellow, .white, .systemOrange]
        for i in 0..<(dish ? 16 : 10) {
            let dot = SKShapeNode(circleOfRadius: CGFloat.random(in: 2.5...5))
            dot.fillColor = colors[i % colors.count]
            dot.strokeColor = .clear
            dot.position = point
            dot.zPosition = 110
            board.addChild(dot)
            let angle = CGFloat.random(in: 0...(2 * .pi))
            let dist = CGFloat.random(in: 30...(dish ? 90 : 60))
            let move = SKAction.moveBy(x: cos(angle) * dist, y: sin(angle) * dist, duration: 0.45)
            move.timingMode = .easeOut
            dot.run(.sequence([.group([move, .fadeOut(withDuration: 0.45)]), .removeFromParent()]))
        }
    }

    private func coinPopup(at point: CGPoint, coins: Int) {
        let label = SKLabelNode(text: "+\(coins)")
        label.fontName = "AvenirNext-Heavy"
        label.fontSize = 20
        label.fontColor = UIColor(red: 1, green: 0.78, blue: 0.15, alpha: 1)
        label.position = CGPoint(x: point.x, y: point.y + itemSize * 0.6)
        label.zPosition = 130
        board.addChild(label)
        label.run(.sequence([.group([.moveBy(x: 0, y: 40, duration: 0.7), .fadeOut(withDuration: 0.7)]), .removeFromParent()]))
    }

    private func comboPopup(combo: Int) {
        if combo >= Balance.comboFrom {
            Audio.shared.play(.combo, volume: 0.7)
            let text = SKLabelNode(text: Lang.shared.t("game.combo", combo))
            text.fontName = "AvenirNext-Heavy"
            text.fontSize = 24
            text.fontColor = UIColor(red: 0.95, green: 0.40, blue: 0.20, alpha: 1)
            text.position = CGPoint(x: size.width / 2, y: shelfArea.maxY - 4)
            text.zPosition = 140
            text.setScale(0.5)
            board.addChild(text)
            text.run(.sequence([.scale(to: 1.1, duration: 0.15), .scale(to: 1, duration: 0.1),
                                .wait(forDuration: 0.5), .fadeOut(withDuration: 0.3), .removeFromParent()]))
        }
    }

    // MARK: - Подсказка

    private func showHint(from: Int, slot: Int, to: Int) {
        clearSelection()
        guard let uid = session.board.front(from)[slot]?.uid, let node = pieceNodes[uid],
              to < shelfNodes.count else { return }
        let pulse = SKAction.repeat(.sequence([.scale(to: 1.2, duration: 0.25), .scale(to: 1, duration: 0.25)]), count: 4)
        node.run(pulse)
        let f = shelfFrames[to]
        let glow = SKShapeNode(rectOf: CGSize(width: f.width + 8, height: f.height + 8), cornerRadius: 12)
        glow.strokeColor = UIColor(red: 1, green: 0.8, blue: 0.2, alpha: 1)
        glow.lineWidth = 4
        glow.position = CGPoint(x: f.midX, y: f.midY)
        glow.zPosition = 25
        board.addChild(glow)
        glow.run(.sequence([.repeat(.sequence([.fadeAlpha(to: 0.3, duration: 0.25), .fadeAlpha(to: 1, duration: 0.25)]), count: 4),
                            .removeFromParent()]))
    }
}
