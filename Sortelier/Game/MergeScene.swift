import SpriteKit
import UIKit

/// Доска кладовой: клетки, предметы и генераторы. Перетаскивание сливает одинаковые предметы.
final class MergeScene: SKScene {
    private let game: MergeGame
    /// Тап по предмету: экран показывает цепочку.
    var onSelect: ((MergeItem?) -> Void)?
    /// Тап по генератору без энергии или на полной доске.
    var onSpawnFail: ((MergeGame.SpawnResult) -> Void)?

    private let gridLayer = SKNode()
    private let itemLayer = SKNode()
    private var itemNodes: [Int: SKSpriteNode] = [:]
    private var cell: CGFloat = 48
    private var origin = CGPoint.zero
    private var drag: (index: Int, node: SKSpriteNode, start: CGPoint, moved: Bool)?
    private var selection: SKShapeNode?

    init(game: MergeGame) {
        self.game = game
        super.init(size: CGSize(width: 390, height: 500))
        scaleMode = .resizeFill
        backgroundColor = .clear
        addChild(gridLayer)
        addChild(itemLayer)
        game.onChange = { [weak self] in self?.syncItems(animated: true) }
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

    private func rebuild() {
        guard size.width > 0, size.height > 0 else { return }
        let cols = CGFloat(MergeBalance.cols)
        let rows = CGFloat(MergeBalance.rows)
        cell = min((size.width - 16) / cols, (size.height - 8) / rows)
        let w = cell * cols
        let h = cell * rows
        origin = CGPoint(x: (size.width - w) / 2, y: (size.height - h) / 2)
        gridLayer.removeAllChildren()
        let board = SKShapeNode(rectOf: CGSize(width: w + 10, height: h + 10), cornerRadius: 18)
        board.fillColor = UIColor(red: 0.98, green: 0.93, blue: 0.84, alpha: 0.88)
        board.strokeColor = UIColor(red: 0.85, green: 0.70, blue: 0.50, alpha: 1)
        board.lineWidth = 2
        board.position = CGPoint(x: size.width / 2, y: size.height / 2)
        gridLayer.addChild(board)
        for i in 0..<MergeGame.cellCount {
            let tile = SKShapeNode(rectOf: CGSize(width: cell - 4, height: cell - 4), cornerRadius: 10)
            let light = (i / MergeBalance.cols + i % MergeBalance.cols) % 2 == 0
            tile.fillColor = light ? UIColor(red: 1, green: 0.97, blue: 0.91, alpha: 1) : UIColor(red: 0.96, green: 0.90, blue: 0.80, alpha: 1)
            tile.strokeColor = .clear
            tile.position = center(of: i)
            gridLayer.addChild(tile)
        }
        for (index, chain) in MergeBalance.generators {
            let gen = SKSpriteNode(texture: Art.texture(chain.generator))
            gen.size = CGSize(width: cell * 1.05, height: cell * 1.05)
            gen.position = center(of: index)
            gen.zPosition = 2
            gen.name = "gen"
            gridLayer.addChild(gen)
            let badge = SKShapeNode(circleOfRadius: 9)
            badge.fillColor = UIColor(red: 1.0, green: 0.78, blue: 0.15, alpha: 1)
            badge.strokeColor = .white
            badge.lineWidth = 1.5
            badge.position = CGPoint(x: center(of: index).x + cell * 0.34, y: center(of: index).y + cell * 0.34)
            badge.zPosition = 3
            let bolt = SKLabelNode(text: "1")
            bolt.fontName = "AvenirNext-Heavy"
            bolt.fontSize = 11
            bolt.fontColor = UIColor(red: 0.45, green: 0.28, blue: 0.1, alpha: 1)
            bolt.verticalAlignmentMode = .center
            badge.addChild(bolt)
            gridLayer.addChild(badge)
        }
        itemLayer.removeAllChildren()
        itemNodes = [:]
        syncItems(animated: false)
    }

    private func center(of index: Int) -> CGPoint {
        let r = index / MergeBalance.cols
        let c = index % MergeBalance.cols
        return CGPoint(x: origin.x + (CGFloat(c) + 0.5) * cell,
                       y: origin.y + (CGFloat(MergeBalance.rows - 1 - r) + 0.5) * cell)
    }

    private func index(at p: CGPoint) -> Int? {
        let c = Int(floor((p.x - origin.x) / cell))
        let rFromBottom = Int(floor((p.y - origin.y) / cell))
        let r = MergeBalance.rows - 1 - rFromBottom
        guard c >= 0, c < MergeBalance.cols, r >= 0, r < MergeBalance.rows else { return nil }
        return r * MergeBalance.cols + c
    }

    // MARK: - Предметы

    private func syncItems(animated: Bool) {
        for i in 0..<MergeGame.cellCount {
            let item = game.item(at: i)
            if let item = item {
                if let node = itemNodes[i], node.name == item.sprite {
                    if drag?.index != i {
                        node.position = center(of: i)
                        node.setScale(1)
                    }
                } else {
                    itemNodes[i]?.removeFromParent()
                    let node = SKSpriteNode(texture: Art.texture(item.sprite))
                    node.name = item.sprite
                    node.size = CGSize(width: cell * 0.9, height: cell * 0.9)
                    node.position = center(of: i)
                    node.zPosition = 5
                    itemLayer.addChild(node)
                    itemNodes[i] = node
                    if animated {
                        node.setScale(0.2)
                        node.run(.sequence([.scale(to: 1.15, duration: 0.12), .scale(to: 1, duration: 0.08)]))
                    }
                }
            } else if let node = itemNodes[i] {
                itemNodes[i] = nil
                node.removeFromParent()
            }
        }
    }

    // MARK: - Касания

    override func touchesBegan(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let p = touches.first?.location(in: self), let i = index(at: p) else { return }
        if game.generator(at: i) != nil {
            tapGenerator(i)
            return
        }
        guard let node = itemNodes[i] else {
            clearSelection()
            onSelect?(nil)
            return
        }
        node.zPosition = 50
        node.run(.scale(to: 1.15, duration: 0.08))
        drag = (i, node, p, false)
        Audio.shared.play(.pick, volume: 0.6)
    }

    override func touchesMoved(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard var d = drag, let p = touches.first?.location(in: self) else { return }
        if hypot(p.x - d.start.x, p.y - d.start.y) > 6 { d.moved = true }
        drag = d
        if d.moved { d.node.position = CGPoint(x: p.x, y: p.y + cell * 0.25) }
    }

    override func touchesEnded(_ touches: Set<UITouch>, with event: UIEvent?) {
        guard let d = drag, let p = touches.first?.location(in: self) else { return }
        drag = nil
        d.node.zPosition = 5
        if !d.moved {
            d.node.run(.scale(to: 1, duration: 0.08))
            select(d.index)
            return
        }
        clearSelection()
        guard let target = index(at: p), target != d.index else {
            returnToCell(d.node, d.index)
            return
        }
        let result = game.move(from: d.index, to: target)
        switch result {
        case .invalid:
            returnToCell(d.node, d.index)
            Audio.shared.play(.invalid, volume: 0.6)
        case let .merged(item):
            // слившийся предмет пересоздается в целевой клетке
            itemNodes[d.index]?.removeFromParent()
            itemNodes[d.index] = nil
            itemNodes[target]?.removeFromParent()
            itemNodes[target] = nil
            syncItems(animated: true)
            sparkle(at: center(of: target))
            Audio.shared.play(item.isMax ? .dish : .triple, volume: 0.8)
            Haptics.success()
            onSelect?(item)
        case .moved:
            itemNodes[target] = d.node
            itemNodes[d.index] = nil
            d.node.run(.group([.move(to: center(of: target), duration: 0.1), .scale(to: 1, duration: 0.1)]))
            Audio.shared.play(.place, volume: 0.7)
        case .swapped:
            let other = itemNodes[target]
            itemNodes[target] = d.node
            itemNodes[d.index] = other
            d.node.run(.group([.move(to: center(of: target), duration: 0.1), .scale(to: 1, duration: 0.1)]))
            other?.run(.move(to: center(of: d.index), duration: 0.12))
            Audio.shared.play(.place, volume: 0.7)
        }
    }

    override func touchesCancelled(_ touches: Set<UITouch>, with event: UIEvent?) {
        if let d = drag { returnToCell(d.node, d.index) }
        drag = nil
    }

    private func returnToCell(_ node: SKSpriteNode, _ index: Int) {
        node.run(.group([.move(to: center(of: index), duration: 0.15), .scale(to: 1, duration: 0.15)]))
    }

    private func tapGenerator(_ index: Int) {
        switch game.spawn(from: index) {
        case let .spawned(cellIndex):
            if let node = itemNodes[cellIndex] {
                node.position = center(of: index)
                node.run(.move(to: center(of: cellIndex), duration: 0.18))
            }
            Audio.shared.play(.pick, volume: 0.7)
            Haptics.light()
        case .noEnergy:
            Audio.shared.play(.invalid, volume: 0.6)
            onSpawnFail?(.noEnergy)
        case .boardFull:
            Audio.shared.play(.invalid, volume: 0.6)
            onSpawnFail?(.boardFull)
        }
    }

    private func select(_ index: Int) {
        clearSelection()
        guard let item = game.item(at: index) else { return }
        let ring = SKShapeNode(rectOf: CGSize(width: cell - 2, height: cell - 2), cornerRadius: 11)
        ring.strokeColor = UIColor(red: 1, green: 0.7, blue: 0.15, alpha: 1)
        ring.lineWidth = 3
        ring.position = center(of: index)
        ring.zPosition = 4
        gridLayer.addChild(ring)
        selection = ring
        onSelect?(item)
    }

    private func clearSelection() {
        selection?.removeFromParent()
        selection = nil
    }

    private func sparkle(at point: CGPoint) {
        for i in 0..<12 {
            let dot = SKShapeNode(circleOfRadius: CGFloat.random(in: 2...4))
            dot.fillColor = [UIColor.systemYellow, .white, .systemOrange][i % 3]
            dot.strokeColor = .clear
            dot.position = point
            dot.zPosition = 60
            itemLayer.addChild(dot)
            let a = CGFloat.random(in: 0...(2 * .pi))
            let r = CGFloat.random(in: 20...46)
            dot.run(.sequence([.group([.moveBy(x: cos(a) * r, y: sin(a) * r, duration: 0.35), .fadeOut(withDuration: 0.35)]),
                               .removeFromParent()]))
        }
    }
}
