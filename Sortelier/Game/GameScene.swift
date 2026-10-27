import SpriteKit
import UIKit

/// Спрайт продукта на полке.
final class PieceNode: SKNode {
    let uid: Int
    let item: String
    private let sprite: SKSpriteNode
    private let shadow: SKSpriteNode
    private let mystery: SKNode
    private(set) var isMystery = false
    private(set) var isDim = false

    init(piece: Piece, size: CGFloat) {
        uid = piece.uid
        item = piece.item
        sprite = SKSpriteNode(texture: Art.texture(piece.item))
        sprite.size = CGSize(width: size, height: size)
        shadow = SKSpriteNode(texture: Art.shadow)
        shadow.size = CGSize(width: size * 0.78, height: size * 0.24)
        shadow.position = CGPoint(x: 0, y: -size * 0.36)
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
        sprite.size = CGSize(width: size, height: size)
        shadow.size = CGSize(width: size * 0.78, height: size * 0.24)
        shadow.position = CGPoint(x: 0, y: -size * 0.36)
    }

    func setMystery(_ hidden: Bool) {
        isMystery = hidden
        sprite.isHidden = hidden
        mystery.isHidden = !hidden
    }

    func setDim(_ dim: Bool, animated: Bool) {
        isDim = dim
        shadow.isHidden = dim
        let factor: CGFloat = dim ? 0.45 : 0
        sprite.color = .black
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

/// Игровое поле: полки, продукты, очередь заказов.
final class GameScene: SKScene {
    let session: GameSession

    /// Сверху под интерфейс SwiftUI (включая безопасную зону).
    var hudHeight: CGFloat = 100 { didSet { if oldValue != hudHeight { rebuild() } } }
    /// Снизу под панель бустеров.
    var bottomReserved: CGFloat = 110 { didSet { if oldValue != bottomReserved { rebuild() } } }

    private let ordersHeight: CGFloat = 104
    private let shelfAspect: CGFloat = 600.0 / 275.0

    private var shelfFrames: [CGRect] = []
    private var shelfNodes: [SKSpriteNode] = []
    private var depthBadges: [SKNode] = []
    private var pieceNodes: [Int: PieceNode] = [:]
    private let board = SKNode()
    private let ordersLayer = SKNode()
    private var cards: [(order: Order, node: SKNode)] = []
    private var queueBadge: SKNode?
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
        addChild(ordersLayer)
        session.onReset = { [weak self] in
            self?.clearSelection()
            self?.rebuild()
        }
        session.onHint = { [weak self] from, slot, to in
            self?.showHint(from: from, slot: slot, to: to)
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
        let top = size.height - hudHeight - ordersHeight - 10
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
        itemSize = shelfWidth * 0.927 / 3 * 0.98
    }

    private func slotPosition(_ shelf: Int, _ slot: Int) -> CGPoint {
        let f = shelfFrames[shelf]
        let step = f.width * 0.927 / 3
        return CGPoint(x: f.midX + CGFloat(slot - 1) * step, y: f.minY + f.height * 0.10 + itemSize * 0.46)
    }

    private func peekPosition(_ shelf: Int, _ slot: Int) -> CGPoint {
        let p = slotPosition(shelf, slot)
        return CGPoint(x: p.x, y: p.y + itemSize * 0.36)
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
        sync(animated: false)
        layoutOrders(animated: false)
    }

    private struct Target {
        let position: CGPoint
        let scale: CGFloat
        let dim: Bool
        let mystery: Bool
        let z: CGFloat
    }

    private func targets() -> [Int: (Piece, Target)] {
        var result: [Int: (Piece, Target)] = [:]
        let b = session.board
        for s in b.shelves.indices where s < shelfFrames.count {
            for (k, piece) in b.front(s).enumerated() {
                guard let piece = piece else { continue }
                result[piece.uid] = (piece, Target(position: slotPosition(s, k), scale: 1, dim: false, mystery: false, z: 20))
            }
            if let peek = b.peek(s) {
                for (k, piece) in peek.enumerated() {
                    guard let piece = piece else { continue }
                    result[piece.uid] = (piece, Target(position: peekPosition(s, k), scale: 0.8, dim: true,
                                                       mystery: piece.hidden, z: 10))
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

    // MARK: - Заказы

    private var ordersRect: CGRect {
        CGRect(x: 10, y: size.height - hudHeight - ordersHeight, width: size.width - 20, height: ordersHeight)
    }

    private func layoutOrders(animated: Bool) {
        cards.forEach { card in
            if animated {
                card.node.run(.sequence([.fadeOut(withDuration: 0.12), .removeFromParent()]))
            } else {
                card.node.removeFromParent()
            }
        }
        cards = []
        queueBadge?.removeFromParent()
        queueBadge = nil
        let orders = session.board.orders
        let visible = Array(orders.prefix(3))
        let rect = ordersRect
        let badgeW: CGFloat = orders.count > 3 ? 44 : 0
        let gap: CGFloat = 8
        let cardW = min(118, (rect.width - badgeW - gap * 3) / 3)
        let totalW = CGFloat(visible.count) * cardW + CGFloat(max(0, visible.count - 1)) * gap + (badgeW > 0 ? gap + badgeW : 0)
        var x = rect.midX - totalW / 2
        for order in visible {
            let card = makeCard(order, width: cardW, height: rect.height - 8)
            card.position = CGPoint(x: x + cardW / 2, y: rect.midY)
            ordersLayer.addChild(card)
            cards.append((order, card))
            if animated {
                card.alpha = 0
                card.setScale(0.9)
                card.run(.group([.fadeIn(withDuration: 0.2), .scale(to: 1, duration: 0.2)]))
            }
            x += cardW + gap
        }
        if badgeW > 0 {
            let badge = SKShapeNode(circleOfRadius: 20)
            badge.fillColor = UIColor(red: 0.98, green: 0.93, blue: 0.84, alpha: 0.95)
            badge.strokeColor = UIColor(red: 0.85, green: 0.70, blue: 0.50, alpha: 1)
            badge.lineWidth = 1.5
            badge.position = CGPoint(x: x + badgeW / 2, y: rect.midY)
            let label = SKLabelNode(text: "+\(orders.count - 3)")
            label.fontName = "AvenirNext-Bold"
            label.fontSize = 15
            label.fontColor = UIColor(red: 0.45, green: 0.30, blue: 0.20, alpha: 1)
            label.verticalAlignmentMode = .center
            badge.addChild(label)
            ordersLayer.addChild(badge)
            queueBadge = badge
        }
    }

    private func makeCard(_ order: Order, width: CGFloat, height: CGFloat) -> SKNode {
        let card = SKNode()
        let bg = SKShapeNode(rectOf: CGSize(width: width, height: height), cornerRadius: 16)
        bg.fillColor = UIColor(red: 1, green: 0.98, blue: 0.94, alpha: 0.97)
        bg.strokeColor = UIColor(red: 0.90, green: 0.78, blue: 0.62, alpha: 1)
        bg.lineWidth = 1.5
        card.addChild(bg)
        let main = SKSpriteNode(texture: Art.texture(Art.sprite(for: order)))
        let mainSize = min(height * 0.62, width * 0.62)
        main.size = CGSize(width: mainSize, height: mainSize)
        main.position = CGPoint(x: 0, y: height * 0.13)
        card.addChild(main)
        if order.kind == .triple {
            let label = SKLabelNode(text: "×3")
            label.fontName = "AvenirNext-Heavy"
            label.fontSize = 16
            label.fontColor = UIColor(red: 0.55, green: 0.33, blue: 0.18, alpha: 1)
            label.position = CGPoint(x: 0, y: -height * 0.40)
            card.addChild(label)
        } else if let dish = Catalog.shared.dish(order.target) {
            let mini = min(22, width / 4.2)
            for (i, ing) in dish.ingredients.enumerated() {
                let s = SKSpriteNode(texture: Art.texture(ing))
                s.size = CGSize(width: mini, height: mini)
                s.position = CGPoint(x: CGFloat(i - 1) * (mini + 3), y: -height * 0.30)
                card.addChild(s)
            }
        }
        card.zPosition = 5
        return card
    }

    // MARK: - Касания

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard session.phase == .playing, let touch = touches.first else { return }
        let p = touch.location(in: self)
        if let hit = frontPiece(at: p) {
            drag = Drag(uid: hit.uid, shelf: hit.shelf, slot: hit.slot, start: p, moved: false)
            if let node = pieceNodes[hit.uid] {
                node.removeAllActions()
                node.zPosition = 100
                node.run(.scale(to: 1.15, duration: 0.08))
            }
            return
        }
        if let sel = selected, let target = shelf(at: p), target != sel.shelf {
            attemptMove(from: sel.shelf, slot: sel.slot, to: target)
            clearSelection()
        } else {
            clearSelection()
        }
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
            } else if let sel = selected, sel.shelf != d.shelf, session.board.freeSlot(in: d.shelf) != nil {
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
            if session.board.freeSlot(in: dst) == nil, dst < shelfNodes.count {
                shelfNodes[dst].run(.sequence([.moveBy(x: -5, y: 0, duration: 0.05), .moveBy(x: 10, y: 0, duration: 0.08),
                                               .moveBy(x: -5, y: 0, duration: 0.05)]))
            }
            return
        }
        Haptics.light()
        if let node = pieceNodes[outcome.piece.uid] {
            node.removeAllActions()
            node.zPosition = 20
            let move = SKAction.move(to: slotPosition(outcome.to, outcome.toSlot), duration: 0.1)
            move.timingMode = .easeOut
            node.run(.group([move, .scale(to: 1, duration: 0.1)]))
        }
        // Поле не блокируется: следующий ход можно делать сразу, анимации идут параллельно.
        var delay: TimeInterval = 0.1
        for fire in outcome.fires {
            let card = cards.first { $0.node.name != "served" && $0.order == fire.order }?.node
            card?.name = "served"
            animateFire(fire, card: card, delay: delay)
            delay += 0.1
        }
        sync(animated: true, delay: outcome.fires.isEmpty ? 0 : 0.12)
        if !outcome.fires.isEmpty {
            removeAction(forKey: "orders")
            run(.sequence([.wait(forDuration: delay + 0.42),
                           .run { [weak self] in self?.layoutOrders(animated: true) }]), withKey: "orders")
        }
        removeAction(forKey: "end")
        run(.sequence([.wait(forDuration: outcome.fires.isEmpty ? 0.12 : delay + 0.45),
                       .run { [weak self] in
                           self?.session.presentPendingDish()
                           self?.session.checkEnd()
                       }]), withKey: "end")
    }

    private func animateFire(_ fire: Fire, card: SKNode?, delay: TimeInterval) {
        let nodes = fire.pieces.compactMap { pieceNodes[$0.uid] }
        let f = shelfFrames[fire.shelf]
        let center = CGPoint(x: f.midX, y: slotPosition(fire.shelf, 1).y + itemSize * 0.2)
        let target: CGPoint
        if let card = card {
            target = card.position
        } else if let badge = queueBadge {
            target = badge.position
        } else {
            target = CGPoint(x: ordersRect.midX, y: ordersRect.midY)
        }
        let combo = session.combo
        let size = itemSize
        for (i, node) in nodes.enumerated() {
            node.zPosition = 120
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
                steps.append(.run { [weak self, weak card] in self?.cardServed(card) })
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
            self.burst(at: center, dish: fire.order.kind == .dish)
            self.coinPopup(at: center, combo: combo)
        }]))
        for piece in fire.pieces {
            pieceNodes[piece.uid] = nil
        }
    }

    private func cardServed(_ card: SKNode?) {
        guard let card = card, card.parent != nil else { return }
        let check = SKLabelNode(text: "✓")
        check.fontName = "AvenirNext-Heavy"
        check.fontSize = 34
        check.fontColor = UIColor(red: 0.25, green: 0.65, blue: 0.35, alpha: 1)
        check.verticalAlignmentMode = .center
        check.zPosition = 10
        card.addChild(check)
        card.run(.sequence([.scale(to: 1.1, duration: 0.1), .scale(to: 1, duration: 0.1)]))
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

    private func coinPopup(at point: CGPoint, combo: Int) {
        let coins = Balance.coinsPerOrder + (combo >= Balance.comboFrom ? Balance.comboBonus : 0)
        let label = SKLabelNode(text: "+\(coins)")
        label.fontName = "AvenirNext-Heavy"
        label.fontSize = 20
        label.fontColor = UIColor(red: 1, green: 0.78, blue: 0.15, alpha: 1)
        label.position = CGPoint(x: point.x, y: point.y + itemSize * 0.6)
        label.zPosition = 130
        board.addChild(label)
        label.run(.sequence([.group([.moveBy(x: 0, y: 40, duration: 0.7), .fadeOut(withDuration: 0.7)]), .removeFromParent()]))
        if combo >= Balance.comboFrom {
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
