import SwiftUI

/// Стиль "уютная кухня": дерево, бумага, ленты-заголовки, объемные кнопки.
/// Цвета заданы как на экране (sRGB).
enum Theme {
    // бумага и текст
    static let cream = Color(red: 0.988, green: 0.906, blue: 0.769)      // вставки и плитки
    static let peach = Color(red: 0.99, green: 0.82, blue: 0.62)
    static let card = Color(red: 1.0, green: 0.965, blue: 0.894)          // бумага панелей
    static let paperInner = Color(red: 1.0, green: 0.89, blue: 0.722)
    static let paperBorder = Color(red: 0.478, green: 0.29, blue: 0.165)
    static let chipBorder = Color(red: 0.788, green: 0.604, blue: 0.42)
    static let brown = Color(red: 0.357, green: 0.204, blue: 0.086)        // основной текст
    static let brownSoft = Color(red: 0.55, green: 0.36, blue: 0.21)
    // дерево
    static let woodDark = Color(red: 0.29, green: 0.157, blue: 0.063)
    static let woodEdge = Color(red: 0.353, green: 0.196, blue: 0.078)
    static let woodMid = Color(red: 0.494, green: 0.29, blue: 0.149)
    static let woodLight = Color(red: 0.659, green: 0.404, blue: 0.227)
    // акценты
    static let orange = Color(red: 0.94, green: 0.54, blue: 0.14)
    static let red = Color(red: 0.886, green: 0.337, blue: 0.227)
    static let ribbonDark = Color(red: 0.478, green: 0.118, blue: 0.055)
    static let green = Color(red: 0.30, green: 0.69, blue: 0.24)
    static let gold = Color(red: 1.0, green: 0.76, blue: 0.18)
    static let blue = Color(red: 0.23, green: 0.56, blue: 0.90)
    static let vip = Color(red: 0.54, green: 0.36, blue: 0.90)

    /// Фон экранов без картинки кухни.
    static var background: LinearGradient {
        LinearGradient(colors: [Color(red: 0.99, green: 0.90, blue: 0.74), Color(red: 0.93, green: 0.74, blue: 0.52)],
                       startPoint: .top, endPoint: .bottom)
    }

    /// Шрифт игры: Nunito трех насыщенностей (кириллица, латиница, вьетнамский).
    /// Для тайского, хинди, арабского и иероглифов система сама подставит свой шрифт.
    static func rounded(_ size: CGFloat, _ weight: Font.Weight = .bold) -> Font {
        let name: String
        switch weight {
        case .black, .heavy: name = "Nunito-Black"
        case .bold, .semibold: name = "Nunito-ExtraBold"
        default: name = "Nunito-Bold"
        }
        return .custom(name, fixedSize: size)
    }
}

// MARK: - Текст с обводкой

/// Белый (или цветной) текст с темной обводкой и тенью снизу: заголовки, кнопки, ленты.
struct StrokeText: View {
    let text: String
    var size: CGFloat = 22
    var weight: Font.Weight = .heavy
    var color: Color = .white
    var stroke: Color = Theme.woodDark
    var width: CGFloat = 2
    var drop: CGFloat = 3
    var alignment: TextAlignment = .center

    private var offsets: [CGSize] {
        let w = width
        return [CGSize(width: -w, height: 0), CGSize(width: w, height: 0), CGSize(width: 0, height: -w),
                CGSize(width: 0, height: w), CGSize(width: -w * 0.7, height: -w * 0.7), CGSize(width: w * 0.7, height: -w * 0.7),
                CGSize(width: -w * 0.7, height: w * 0.7), CGSize(width: w * 0.7, height: w * 0.7)]
    }

    var body: some View {
        let base = Text(text).font(Theme.rounded(size, weight)).multilineTextAlignment(alignment)
        ZStack {
            if drop > 0 {
                base.foregroundColor(stroke).offset(y: drop + width * 0.5)
            }
            ForEach(offsets.indices, id: \.self) { i in
                base.foregroundColor(stroke).offset(offsets[i])
            }
            base.foregroundColor(color)
        }
    }
}

/// Обводка для любых подписей (кнопки): несколько жестких теней вокруг.
struct Outline: ViewModifier {
    var color: Color
    var width: CGFloat = 1.2

    func body(content: Content) -> some View {
        content
            .shadow(color: color, radius: 0, x: width, y: 0)
            .shadow(color: color, radius: 0, x: -width, y: 0)
            .shadow(color: color, radius: 0, x: 0, y: width)
            .shadow(color: color, radius: 0, x: 0, y: -width)
            .shadow(color: color, radius: 0, x: 0, y: width + 1.2)
    }
}

extension View {
    func outlined(_ color: Color, width: CGFloat = 1.2) -> some View { modifier(Outline(color: color, width: width)) }
}

// MARK: - Фоны

/// Фон кухни биома: рендер из tools/render/environment.py.
struct KitchenBackground: View {
    /// Светлая вуаль поверх, чтобы спокойнее читался интерфейс.
    var veil: Double = 0
    /// Фон темы вместо выбранного игроком: уровни ивента.
    var style: String?
    /// Размытие и затемнение: фон экранов меню.
    var blurred = false
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        GeometryReader { geo in
            Image(uiImage: Art.image(KitchenStyle.image(style ?? progress.background)))
                .resizable()
                .scaledToFill()
                .frame(width: geo.size.width, height: geo.size.height)
                .clipped()
                .blur(radius: blurred ? 5 : 0)
                .overlay(Color.white.opacity(veil))
                .overlay(blurred ? Color(red: 0.25, green: 0.13, blue: 0.05).opacity(0.28) : Color.clear)
        }
        .ignoresSafeArea()
    }
}

/// Дерево: шапка экрана и нижняя панель. Градиент и тонкие волокна.
struct WoodBackground: View {
    var body: some View {
        ZStack {
            LinearGradient(colors: [Theme.woodLight, Theme.woodMid], startPoint: .top, endPoint: .bottom)
            Canvas { context, size in
                var y: CGFloat = 3
                var k = 0
                while y < size.height {
                    var p = Path()
                    p.move(to: CGPoint(x: 0, y: y))
                    var x: CGFloat = 0
                    while x < size.width {
                        x += 24
                        p.addLine(to: CGPoint(x: x, y: y + CGFloat(sin(Double(x) / 37 + Double(k))) * 1.2))
                    }
                    context.stroke(p, with: .color(Color.black.opacity(0.07)), lineWidth: 1.4)
                    y += 7
                    k += 1
                }
            }
        }
    }
}

// MARK: - Панели

/// Бумажная панель с коричневой рамкой, светлой внутренней каймой и тенью-гранью снизу.
struct PaperBackground: View {
    var radius: CGFloat = 20
    var highlight = false

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        ZStack {
            shape.fill(Theme.woodDark.opacity(0.5)).offset(y: 5)
            shape.fill(Theme.card)
            shape.inset(by: 4).strokeBorder(Theme.paperInner, lineWidth: 3)
            shape.strokeBorder(highlight ? Theme.orange : Theme.paperBorder, lineWidth: 3)
            if highlight {
                shape.stroke(Theme.gold.opacity(0.55), lineWidth: 6).blur(radius: 4)
            }
        }
    }
}

/// Карточка с бумажной подложкой.
struct Panel<Content: View>: View {
    var padding: CGFloat = 16
    var highlight = false
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(padding)
            .background(PaperBackground(highlight: highlight))
    }
}

/// Вставка внутри панели: плитки наград, поля.
struct InsetBackground: View {
    var radius: CGFloat = 14
    var color: Color = Theme.cream

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        ZStack {
            shape.fill(color)
            shape.strokeBorder(Theme.chipBorder, lineWidth: 2)
        }
    }
}

/// Лента-заголовок с вырезами на концах.
struct RibbonShape: Shape {
    func path(in rect: CGRect) -> Path {
        let notch = min(14, rect.height * 0.42)
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.maxX - notch, y: rect.midY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        p.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        p.addLine(to: CGPoint(x: rect.minX + notch, y: rect.midY))
        p.closeSubpath()
        return p
    }
}

struct Ribbon: View {
    let title: String
    var color: Color = Theme.red
    var dark: Color = Theme.ribbonDark
    var size: CGFloat = 18

    var body: some View {
        StrokeText(text: title, size: size, color: .white, stroke: dark, width: 1.5, drop: 2)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
            .padding(.horizontal, 34)
            .padding(.vertical, 7)
            .background(
                ZStack {
                    RibbonShape().fill(dark).offset(y: 4)
                    RibbonShape().fill(LinearGradient(colors: [color.opacity(0.92), color], startPoint: .top, endPoint: .bottom))
                    RibbonShape().stroke(dark, lineWidth: 3)
                }
            )
    }
}

// MARK: - Кнопки

/// Палитра кнопок: верх, низ, темная грань и обводка текста.
enum ButtonPalette {
    case green, orange, red, blue, purple, gold, gray, paper

    var top: Color {
        switch self {
        case .green: return Color(red: 0.48, green: 0.84, blue: 0.42)
        case .orange: return Color(red: 1.0, green: 0.71, blue: 0.29)
        case .red: return Color(red: 0.95, green: 0.45, blue: 0.35)
        case .blue: return Color(red: 0.43, green: 0.76, blue: 1.0)
        case .purple: return Color(red: 0.71, green: 0.55, blue: 1.0)
        case .gold: return Color(red: 1.0, green: 0.86, blue: 0.40)
        case .gray: return Color(red: 0.85, green: 0.80, blue: 0.72)
        case .paper: return Color(red: 1.0, green: 0.97, blue: 0.90)
        }
    }

    var bottom: Color {
        switch self {
        case .green: return Color(red: 0.30, green: 0.69, blue: 0.24)
        case .orange: return Color(red: 0.94, green: 0.54, blue: 0.14)
        case .red: return Color(red: 0.85, green: 0.27, blue: 0.18)
        case .blue: return Color(red: 0.23, green: 0.56, blue: 0.90)
        case .purple: return Color(red: 0.54, green: 0.36, blue: 0.90)
        case .gold: return Color(red: 0.95, green: 0.64, blue: 0.23)
        case .gray: return Color(red: 0.73, green: 0.67, blue: 0.57)
        case .paper: return Color(red: 0.99, green: 0.89, blue: 0.72)
        }
    }

    var dark: Color {
        switch self {
        case .green: return Color(red: 0.14, green: 0.38, blue: 0.10)
        case .orange: return Color(red: 0.54, green: 0.26, blue: 0.03)
        case .red: return Theme.ribbonDark
        case .blue: return Color(red: 0.09, green: 0.31, blue: 0.55)
        case .purple: return Color(red: 0.27, green: 0.14, blue: 0.48)
        case .gold: return Color(red: 0.55, green: 0.31, blue: 0.03)
        case .gray: return Color(red: 0.49, green: 0.42, blue: 0.32)
        case .paper: return Theme.paperBorder
        }
    }

    var text: Color { self == .paper ? Theme.brown : .white }

    static func from(_ color: Color) -> ButtonPalette {
        switch color {
        case Theme.green: return .green
        case Theme.red: return .red
        case Theme.blue: return .blue
        case Theme.vip: return .purple
        case Theme.gold: return .gold
        case Theme.brownSoft, Theme.cream: return .gray
        default: return .orange
        }
    }
}

/// Объемная игровая кнопка: градиент, блик, темная рамка и грань снизу, при нажатии "проваливается".
struct GameButtonStyle: ButtonStyle {
    var palette: ButtonPalette = .green
    var height: CGFloat = 52
    var fontSize: CGFloat = 20
    var fullWidth = true
    var radius: CGFloat = 16

    func makeBody(configuration: Configuration) -> some View {
        let pressed = configuration.isPressed
        let shape = RoundedRectangle(cornerRadius: radius, style: .continuous)
        return configuration.label
            .font(Theme.rounded(fontSize, .heavy))
            .foregroundColor(palette.text)
            .lineLimit(1)
            .minimumScaleFactor(0.6)
            .modifier(Outline(color: palette == .paper ? .clear : palette.dark, width: 1.2))
            .padding(.horizontal, 16)
            .frame(maxWidth: fullWidth ? .infinity : nil)
            .frame(height: height)
            .background(
                ZStack {
                    shape.fill(palette.dark).offset(y: pressed ? 1 : 5)
                    shape.fill(LinearGradient(colors: [palette.top, palette.bottom], startPoint: .top, endPoint: .bottom))
                    shape.inset(by: 5)
                        .fill(Color.white.opacity(palette == .paper ? 0 : 0.22))
                        .frame(height: height * 0.36)
                        .frame(maxHeight: .infinity, alignment: .top)
                        .padding(.top, 1)
                    shape.strokeBorder(palette.dark, lineWidth: 3)
                }
            )
            .offset(y: pressed ? 4 : 0)
            .padding(.bottom, 5)
            .animation(.easeOut(duration: 0.08), value: pressed)
            .onChange(of: pressed) { p in
                if p { Audio.shared.play(.button, volume: 0.6) }
            }
    }
}

/// Прежнее имя кнопки: цвет переводится в палитру нового стиля.
struct BigButtonStyle: ButtonStyle {
    var color: Color = Theme.orange

    func makeBody(configuration: Configuration) -> some View {
        GameButtonStyle(palette: ButtonPalette.from(color)).makeBody(configuration: configuration)
    }
}

/// Маленькая кнопка в строку: "Забрать", цена бустера.
struct SmallButtonStyle: ButtonStyle {
    var palette: ButtonPalette = .green

    func makeBody(configuration: Configuration) -> some View {
        GameButtonStyle(palette: palette, height: 34, fontSize: 15, fullWidth: false, radius: 12)
            .makeBody(configuration: configuration)
    }
}

/// Иконки нового стиля вместо системных значков.
enum GameIcon {
    static func sprite(for symbol: String) -> String? {
        switch symbol {
        case "gearshape.fill": return "icon_gear"
        case "book.fill": return "icon_book"
        case "trophy.fill": return "icon_trophy"
        case "gift.fill": return "icon_gift"
        case "calendar": return "icon_calendar"
        case "paintpalette.fill": return "icon_palette"
        case "sparkles": return "icon_ticket"
        case "cart.fill": return "coins_bag"
        case "rectangle.stack.fill": return "icon_cards"
        case "square.grid.3x3.fill": return "gen_crate"
        case "heart.fill": return "icon_heart"
        case "bolt.fill": return "icon_energy"
        case "star.fill": return "icon_star"
        case "lock.fill": return "icon_lock"
        case "flag.checkered": return "icon_flag"
        case "play.rectangle.fill": return "icon_ad"
        case "checkmark.circle.fill", "checkmark.seal.fill": return "icon_check"
        case "rosette": return "icon_medal"
        default: return nil
        }
    }
}

/// Круглая кнопка: закрыть (красная с крестиком) или иконка на бумажной подложке.
struct CircleIconButton: View {
    let symbol: String
    var size: CGFloat = 44
    let action: () -> Void

    var body: some View {
        Button {
            Audio.shared.play(.button, volume: 0.6)
            action()
        } label: {
            label
        }
        .buttonStyle(PressScaleStyle())
    }

    @ViewBuilder
    private var label: some View {
        if symbol == "xmark" {
            CloseGlyph(size: size)
        } else if let sprite = GameIcon.sprite(for: symbol) {
            ZStack {
                RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).fill(Theme.woodDark.opacity(0.5)).offset(y: 3)
                RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).fill(Theme.card)
                RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).strokeBorder(Theme.paperBorder, lineWidth: 2.5)
                SpriteImage(name: sprite, size: size * 0.78)
            }
            .frame(width: size, height: size)
        } else {
            ZStack {
                RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).fill(Theme.woodDark.opacity(0.5)).offset(y: 3)
                RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).fill(Theme.card)
                RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).strokeBorder(Theme.paperBorder, lineWidth: 2.5)
                Image(systemName: symbol)
                    .font(.system(size: size * 0.4, weight: .heavy))
                    .foregroundColor(Theme.brown)
            }
            .frame(width: size, height: size)
        }
    }
}

/// Красная круглая кнопка с белым крестиком.
struct CloseGlyph: View {
    var size: CGFloat = 40

    var body: some View {
        ZStack {
            Circle().fill(Theme.ribbonDark).offset(y: 3)
            Circle().fill(LinearGradient(colors: [ButtonPalette.red.top, ButtonPalette.red.bottom], startPoint: .top, endPoint: .bottom))
            Circle().strokeBorder(Theme.ribbonDark, lineWidth: 2.5)
            CrossShape()
                .stroke(Color.white, style: StrokeStyle(lineWidth: size * 0.11, lineCap: .round))
                .frame(width: size * 0.34, height: size * 0.34)
        }
        .frame(width: size, height: size)
    }
}

struct CrossShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.minX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY))
        p.move(to: CGPoint(x: rect.maxX, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.minX, y: rect.maxY))
        return p
    }
}

/// Стрелка "назад" для шапки.
struct BackArrowShape: Shape {
    func path(in rect: CGRect) -> Path {
        var p = Path()
        p.move(to: CGPoint(x: rect.maxX * 0.68, y: rect.minY))
        p.addLine(to: CGPoint(x: rect.minX + rect.width * 0.18, y: rect.midY))
        p.addLine(to: CGPoint(x: rect.maxX * 0.68, y: rect.maxY))
        return p
    }
}

/// Нажатие слегка уменьшает кнопку.
struct PressScaleStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.92 : 1)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }
}

// MARK: - Переключатель

/// Переключатель в стиле игры: деревянная дорожка, зеленая при включении, бумажный кружок.
struct GameToggleStyle: ToggleStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack {
            configuration.label
            Spacer(minLength: 8)
            Button {
                withAnimation(.spring(response: 0.25, dampingFraction: 0.75)) { configuration.isOn.toggle() }
                Haptics.light()
            } label: {
                ZStack(alignment: configuration.isOn ? .trailing : .leading) {
                    Capsule()
                        .fill(configuration.isOn
                              ? LinearGradient(colors: [ButtonPalette.green.top, ButtonPalette.green.bottom], startPoint: .top, endPoint: .bottom)
                              : LinearGradient(colors: [Theme.woodMid, Theme.woodLight], startPoint: .top, endPoint: .bottom))
                    Capsule().strokeBorder(configuration.isOn ? ButtonPalette.green.dark : Theme.woodDark, lineWidth: 2.5)
                    Circle()
                        .fill(Theme.card)
                        .overlay(Circle().strokeBorder(Theme.paperBorder, lineWidth: 2.5))
                        .frame(width: 26, height: 26)
                        .padding(3)
                }
                .frame(width: 60, height: 34)
            }
            .buttonStyle(.plain)
        }
    }
}

// MARK: - Монеты, жизни, пилюли

struct CoinIcon: View {
    var size: CGFloat = 22

    /// Объемная монета из рендера, такая же, как в паках магазина. Без картинки - плоская монета.
    private static let hasSprite = UIImage(named: "coin_icon") != nil

    var body: some View {
        Group {
            if CoinIcon.hasSprite {
                Image(uiImage: Art.image("coin_icon"))
                    .resizable()
                    .aspectRatio(contentMode: .fit)
                    .scaleEffect(1.12)
            } else {
                ZStack {
                    Circle().fill(Theme.gold)
                    Circle().stroke(Color(red: 0.85, green: 0.55, blue: 0.05), lineWidth: size * 0.1)
                    Text("S")
                        .font(.system(size: size * 0.55, weight: .heavy, design: .rounded))
                        .foregroundColor(Color(red: 0.75, green: 0.45, blue: 0.0))
                }
            }
        }
        .frame(width: size, height: size)
    }
}

/// Счетчик на темном дереве: монеты, жизни, энергия.
struct Pill<Leading: View>: View {
    let text: String
    var plus = false
    @ViewBuilder var leading: Leading

    var body: some View {
        HStack(spacing: 5) {
            leading
            Text(text)
                .font(Theme.rounded(16, .heavy))
                .monospacedDigit()
                .foregroundColor(Color(red: 1.0, green: 0.91, blue: 0.68))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            if plus { PlusBadge(size: 22) }
        }
        .padding(.leading, 4)
        .padding(.trailing, plus ? 5 : 12)
        .frame(height: 36)
        .background(
            ZStack {
                Capsule().fill(Theme.woodDark)
                Capsule().strokeBorder(Color.black.opacity(0.35), lineWidth: 2)
            }
        )
    }
}

/// Зеленый квадратик с плюсом: пополнить.
struct PlusBadge: View {
    var size: CGFloat = 22

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: size * 0.3, style: .continuous)
                .fill(LinearGradient(colors: [ButtonPalette.green.top, ButtonPalette.green.bottom], startPoint: .top, endPoint: .bottom))
            RoundedRectangle(cornerRadius: size * 0.3, style: .continuous).strokeBorder(ButtonPalette.green.dark, lineWidth: 2)
            Image(systemName: "plus").font(.system(size: size * 0.55, weight: .black)).foregroundColor(.white)
        }
        .frame(width: size, height: size)
    }
}

/// Значок кнопки "за рекламу": у VIP вместо рекламы корона, награда сразу.
struct AdIcon: View {
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        if progress.isVIP {
            Image(systemName: "crown.fill")
        } else {
            SpriteImage(name: "icon_ad", size: 24)
        }
    }
}

struct CoinsPill: View {
    var plus = true
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        Pill(text: "\(progress.coins)", plus: plus) { CoinIcon(size: 28) }
    }
}

struct LivesPill: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        Pill(text: label) {
            ZStack {
                SpriteImage(name: progress.unlimitedLives ? "icon_unlimited" : "icon_heart", size: 30)
                if !progress.unlimitedLives {
                    Text("\(progress.lives)")
                        .font(Theme.rounded(13, .black))
                        .foregroundColor(.white)
                        .outlined(Theme.ribbonDark, width: 1)
                        .offset(y: -1)
                }
            }
        }
    }

    private var label: String {
        if let left = progress.unlimitedLeft { return Lang.time(left) }
        if let next = progress.nextLifeIn { return Lang.time(next) }
        return lang.t("lives.full")
    }
}

struct StarsRow: View {
    let count: Int
    var size: CGFloat = 16
    var spacing: CGFloat = 2
    var total = 3

    var body: some View {
        HStack(spacing: spacing) {
            ForEach(0..<total, id: \.self) { i in
                SpriteImage(name: "icon_star", size: size * 1.3, silhouette: i >= count)
            }
        }
    }
}

struct SpriteImage: View {
    let name: String
    var size: CGFloat = 60
    var silhouette = false

    var body: some View {
        Group {
            if silhouette {
                Image(uiImage: Art.image(name))
                    .renderingMode(.template)
                    .resizable()
                    .foregroundColor(Theme.brown.opacity(0.18))
            } else {
                Image(uiImage: Art.image(name))
                    .resizable()
            }
        }
        .aspectRatio(contentMode: .fit)
        .frame(width: size, height: size)
    }
}

/// Затемнение под всплывающими окнами. Пока оно на экране, нижняя панель тоже затемнена и не нажимается.
struct Dim: View {
    var opacity: Double = 0.5

    var body: some View {
        Color.black.opacity(opacity).ignoresSafeArea().registersModal()
    }
}

/// Окно поверх экрана: считаем открытые окна, чтобы затемнить нижнюю панель.
struct ModalRegistration: ViewModifier {
    func body(content: Content) -> some View {
        content
            .onAppear { DispatchQueue.main.async { Router.shared.modalCount += 1 } }
            .onDisappear { DispatchQueue.main.async { Router.shared.modalCount = max(0, Router.shared.modalCount - 1) } }
    }
}

extension View {
    func registersModal() -> some View { modifier(ModalRegistration()) }
}

// MARK: - Всплывающее окно

/// Окно поверх экрана: бумажная панель, лента с заголовком сверху, красный крестик в углу.
struct PopupCard<Content: View>: View {
    var title: String?
    var close: (() -> Void)?
    var maxWidth: CGFloat = 330
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 0) {
            content
                .padding(.horizontal, 18)
                .padding(.top, title == nil ? 20 : 34)
                .padding(.bottom, 18)
                .frame(maxWidth: maxWidth)
                .background(PaperBackground(radius: 24))
                .overlay(alignment: .top) {
                    if let title = title {
                        Ribbon(title: title, size: 19).offset(y: -20)
                            .padding(.horizontal, 6)
                    }
                }
                .overlay(alignment: .topTrailing) {
                    if let close = close {
                        Button {
                            Audio.shared.play(.button, volume: 0.6)
                            close()
                        } label: { CloseGlyph(size: 38) }
                        .buttonStyle(PressScaleStyle())
                        .offset(x: 12, y: -14)
                    }
                }
        }
        .padding(.horizontal, 22)
    }
}
