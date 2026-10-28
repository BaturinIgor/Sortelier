import SpriteKit
import UIKit

/// Покупатель за прилавком: аватар, заказ в облачке, монеты за заказ и шкала терпения.
/// Начало координат - центр места у прилавка на уровне столешницы.
final class CustomerNode: SKNode {
    static let looks = 10
    /// Отдельный образ гурмана: цилиндр, монокль, бабочка.
    static let gourmetLook = 10

    let uid: Int
    let order: Order
    private let look: Int
    private let avatar: SKSpriteNode
    private let bubble = SKNode()
    private let coinPill = SKNode()
    private let coinLabel = SKLabelNode()
    private let pillBack: SKShapeNode
    private let barFill: SKSpriteNode
    private let barWidth: CGFloat
    private(set) var mood = ""
    var leaving = false

    /// Центр облачка с заказом в координатах узла: туда летит готовое.
    let bubbleCenter: CGPoint

    init(customer: Customer, look: Int, slotWidth: CGFloat, plankHeight: CGFloat) {
        uid = customer.uid
        order = customer.order
        self.look = look
        let a = min(78, slotWidth * 0.68)
        avatar = SKSpriteNode(texture: Art.texture("customer_\(look)_happy"))
        avatar.size = CGSize(width: a, height: a)
        avatar.position = CGPoint(x: -slotWidth * 0.17, y: a * 0.40)
        avatar.zPosition = 0

        let isDish = order.kind == .dish
        let bw: CGFloat = min(54, slotWidth * 0.48)
        let bh: CGFloat = isDish ? bw * 1.18 : bw
        bubbleCenter = CGPoint(x: slotWidth * 0.24, y: a * 0.58 + (isDish ? 4 : 0))

        barWidth = slotWidth * 0.72
        barFill = SKSpriteNode(color: .green, size: CGSize(width: barWidth, height: 7))
        pillBack = SKShapeNode(rectOf: CGSize(width: 36, height: 20), cornerRadius: 10)
        super.init()

        addChild(avatar)

        // облачко с заказом
        let back = SKShapeNode(rectOf: CGSize(width: bw, height: bh), cornerRadius: 14)
        back.fillColor = customer.gourmet
            ? UIColor(red: 1, green: 0.96, blue: 0.82, alpha: 0.98)
            : UIColor(red: 1, green: 0.985, blue: 0.95, alpha: 0.98)
        back.strokeColor = customer.gourmet
            ? UIColor(red: 0.95, green: 0.68, blue: 0.10, alpha: 1)
            : UIColor(red: 0.90, green: 0.78, blue: 0.62, alpha: 1)
        back.lineWidth = customer.gourmet ? 2.5 : 1.5
        bubble.addChild(back)
        let tail = SKShapeNode(circleOfRadius: 4)
        tail.fillColor = back.fillColor
        tail.strokeColor = back.strokeColor
        tail.lineWidth = 1.5
        tail.position = CGPoint(x: -bw / 2 - 2, y: -bh * 0.22)
        bubble.addChild(tail)
        let icon = SKSpriteNode(texture: Art.texture(Art.sprite(for: order)))
        let iconSize = bw * (isDish ? 0.74 : 0.8)
        icon.size = CGSize(width: iconSize, height: iconSize)
        icon.position = CGPoint(x: 0, y: isDish ? bh * 0.14 : 0)
        bubble.addChild(icon)
        if order.kind == .triple {
            let times = SKShapeNode(rectOf: CGSize(width: 24, height: 16), cornerRadius: 8)
            times.fillColor = UIColor(red: 0.55, green: 0.33, blue: 0.18, alpha: 1)
            times.strokeColor = .clear
            times.position = CGPoint(x: bw * 0.36, y: -bh * 0.38)
            let label = SKLabelNode(text: "×3")
            label.fontName = "AvenirNext-Heavy"
            label.fontSize = 11
            label.fontColor = .white
            label.verticalAlignmentMode = .center
            times.addChild(label)
            bubble.addChild(times)
        } else if let dish = Catalog.shared.dish(order.target) {
            let mini = bw * 0.27
            for (i, ing) in dish.ingredients.enumerated() {
                let s = SKSpriteNode(texture: Art.texture(ing))
                s.size = CGSize(width: mini, height: mini)
                s.position = CGPoint(x: CGFloat(i - 1) * (mini + 1), y: -bh * 0.32)
                bubble.addChild(s)
            }
        }
        bubble.position = bubbleCenter
        bubble.zPosition = 6
        addChild(bubble)
        if customer.gourmet {
            // звезда гурмана над аватаром
            let config = UIImage.SymbolConfiguration(pointSize: 40, weight: .heavy)
            let image = UIImage(systemName: "crown.fill", withConfiguration: config)?
                .withTintColor(UIColor(red: 1.0, green: 0.74, blue: 0.10, alpha: 1), renderingMode: .alwaysOriginal)
            let star = SKSpriteNode(texture: image.map { SKTexture(image: $0) })
            star.size = CGSize(width: 22, height: 18)
            star.position = CGPoint(x: avatar.position.x - a * 0.38, y: avatar.position.y + a * 0.42)
            star.zPosition = 7
            star.run(.repeatForever(.sequence([.scale(to: 1.2, duration: 0.6), .scale(to: 1, duration: 0.6)])))
            addChild(star)
        }

        // монеты за заказ с учетом чаевых
        pillBack.strokeColor = UIColor(red: 0.85, green: 0.6, blue: 0.1, alpha: 1)
        pillBack.lineWidth = 1.2
        coinPill.addChild(pillBack)
        let coin = SKSpriteNode(texture: Art.coin)
        coin.size = CGSize(width: 14, height: 14)
        coin.position = CGPoint(x: -9, y: 0)
        coinPill.addChild(coin)
        coinLabel.fontName = "AvenirNext-Heavy"
        coinLabel.fontSize = 12
        coinLabel.verticalAlignmentMode = .center
        coinLabel.horizontalAlignmentMode = .left
        coinLabel.position = CGPoint(x: -1, y: 0)
        coinPill.addChild(coinLabel)
        coinPill.position = CGPoint(x: bubbleCenter.x + bw * 0.42, y: bubbleCenter.y + bh / 2)
        coinPill.zPosition = 7
        addChild(coinPill)

        // шкала терпения на столешнице
        let track = SKShapeNode(rectOf: CGSize(width: barWidth + 4, height: 11), cornerRadius: 5.5)
        track.fillColor = UIColor(red: 0.20, green: 0.11, blue: 0.06, alpha: 0.75)
        track.strokeColor = .clear
        track.position = CGPoint(x: 0, y: -plankHeight * 0.5)
        track.zPosition = 5
        addChild(track)
        barFill.anchorPoint = CGPoint(x: 0, y: 0.5)
        barFill.position = CGPoint(x: -barWidth / 2, y: -plankHeight * 0.5)
        barFill.zPosition = 6
        addChild(barFill)
    }

    required init?(coder aDecoder: NSCoder) { fatalError("init(coder:) has not been implemented") }

    /// Обновить шкалу терпения, настроение и монеты.
    func update(patience: Int, max: Int, coins: Int, tip: Int, paused: Bool = false, animated: Bool) {
        let fraction: CGFloat = max > 0 ? CGFloat(patience) / CGFloat(max) : 1
        let color: UIColor
        if paused && max > 0 {
            // терпение на паузе: шкала голубая
            color = UIColor(red: 0.35, green: 0.68, blue: 0.98, alpha: 1)
        } else if max == 0 || fraction > 0.5 {
            color = UIColor(red: 0.36, green: 0.76, blue: 0.36, alpha: 1)
        } else if fraction > 0.25 {
            color = UIColor(red: 1.0, green: 0.74, blue: 0.18, alpha: 1)
        } else {
            color = UIColor(red: 0.93, green: 0.34, blue: 0.28, alpha: 1)
        }
        barFill.color = color
        let scale = Swift.max(0.001, fraction)
        if animated {
            barFill.run(.scaleX(to: scale, duration: 0.2))
        } else {
            barFill.xScale = scale
        }
        coinLabel.text = "\(coins)"
        pillBack.fillColor = tip > 0
            ? UIColor(red: 1.0, green: 0.88, blue: 0.45, alpha: 1)
            : UIColor(red: 0.90, green: 0.86, blue: 0.80, alpha: 1)
        coinLabel.fontColor = UIColor(red: 0.45, green: 0.28, blue: 0.10, alpha: 1)
        let newMood = (max == 0 || fraction > 0.5) ? "happy" : (fraction > 0 ? "wait" : "upset")
        setMood(newMood)
    }

    func setMood(_ value: String) {
        guard value != mood else { return }
        mood = value
        avatar.texture = Art.texture("customer_\(look)_\(value)")
    }

    /// Заказ получен: радость, монеты над облачком и уход.
    func celebrate(coins: Int, done: @escaping () -> Void) {
        leaving = true
        setMood("joy")
        bubble.run(.sequence([.scale(to: 1.15, duration: 0.08), .scale(to: 0, duration: 0.15)]))
        coinPill.run(.fadeOut(withDuration: 0.1))
        avatar.run(.sequence([.moveBy(x: 0, y: 10, duration: 0.12), .moveBy(x: 0, y: -10, duration: 0.12)]))
        let label = SKLabelNode(text: "+\(coins)")
        label.fontName = "AvenirNext-Heavy"
        label.fontSize = 20
        label.fontColor = UIColor(red: 1, green: 0.78, blue: 0.15, alpha: 1)
        label.position = CGPoint(x: bubbleCenter.x, y: bubbleCenter.y)
        label.zPosition = 20
        addChild(label)
        label.run(.group([.moveBy(x: 0, y: 34, duration: 0.6), .sequence([.wait(forDuration: 0.3), .fadeOut(withDuration: 0.3)])]))
        run(.sequence([.wait(forDuration: 0.45),
                       .group([.moveBy(x: 0, y: 20, duration: 0.3), .fadeOut(withDuration: 0.3)]),
                       .run(done),
                       .removeFromParent()]))
    }

    /// Уход без анимации радости (отмена хода, перестройка поля).
    func leave() {
        leaving = true
        run(.sequence([.fadeOut(withDuration: 0.2), .removeFromParent()]))
    }
}
