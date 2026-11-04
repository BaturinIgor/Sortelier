import SwiftUI

/// "Большой рецепт": 25 шагов за неделю, на каждом выбор из двух ингредиентов.
/// Закрытый шаг кладет начинку на гигантское блюдо недели (пицца, торт, салат, паэлья): помидор ложится кружком,
/// лайм - долькой, молоко - шапкой сливок. К концу недели у каждого свое блюдо со своим названием.
struct BigRecipeView: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var visible = 0
    @State private var landing: Int?
    @State private var glow = false

    var body: some View {
        let state = progress.recipe
        ZStack {
            KitchenBackground(blurred: true)
            ScrollView(showsIndicators: false) {
                VStack(spacing: 14) {
                    header
                    dishStage(state)
                    if !state.plate.isEmpty { composition(state) }
                    stepsTrack(state)
                    if progress.recipeDone {
                        Panel(highlight: true) {
                            VStack(spacing: 8) {
                                SpriteImage(name: "icon_trophy", size: 70)
                                Text(lang.t("recipe.done")).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
                                    .multilineTextAlignment(.center)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            .frame(maxWidth: .infinity)
                        }
                    } else if let current = progress.recipeCurrent {
                        currentCard(current, state: state)
                    } else {
                        choiceCards(state)
                    }
                    Text(lang.t("recipe.hint"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(.white.opacity(0.95))
                        .outlined(Theme.woodDark.opacity(0.6), width: 1)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.horizontal, 10)
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 30)
            }
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 2.4).repeatForever(autoreverses: true)) { glow = true }
            let s = progress.recipe
            let fresh = min(s.unseen, s.plate.count)
            visible = s.plate.count - fresh
            for i in 0..<fresh {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.6 + Double(i) * 0.6) {
                    landing = visible
                    withAnimation(.spring(response: 0.42, dampingFraction: 0.58)) { visible += 1 }
                    Audio.shared.play(.dish, volume: 0.7)
                    Haptics.light()
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.9 + Double(fresh) * 0.6) {
                landing = nil
                progress.recipeSeen()
            }
        }
    }

    private var dishName: String {
        let top = progress.recipeTop()
        let dish = lang.t("recipe.dish." + BigRecipe.theme(progress.recipe.week))
        let parts = top.map { lang.t("recipe.with." + $0) }
        if parts.count >= 2 { return lang.t("recipe.name2", dish, parts[0], parts[1]) }
        if let one = parts.first { return lang.t("recipe.name1", dish, one) }
        return dish
    }

    private var header: some View {
        HStack(spacing: 8) {
            CircleIconButton(symbol: "xmark", size: 42, action: close)
            VStack(alignment: .leading, spacing: 0) {
                StrokeText(text: lang.t("recipe.title"), size: 22, weight: .black, color: Color(red: 1.0, green: 0.95, blue: 0.84),
                           stroke: Theme.woodDark, width: 1.5, drop: 2, alignment: .leading)
                Text(lang.t("recipe.left", Lang.time(Day.secondsToWeekEnd(progress.now))))
                    .font(Theme.rounded(13, .heavy))
                    .foregroundColor(Color(red: 1, green: 0.9, blue: 0.7))
                    .outlined(Theme.woodDark, width: 1)
            }
            Spacer()
            if HappyHour.active(progress.now) { HappyHourChip() }
        }
        .padding(.top, 8)
    }

    // MARK: - Блюдо

    /// Блюдо на подсвеченной сцене: теплое пятно света, пар, лента с названием.
    private func dishStage(_ state: RecipeState) -> some View {
        let done = progress.recipeDone
        return VStack(spacing: -18) {
            ZStack {
                Circle()
                    .fill(RadialGradient(colors: [Color(red: 1.0, green: 0.93, blue: 0.70).opacity(done ? 0.95 : 0.75),
                                                  Color(red: 1.0, green: 0.80, blue: 0.45).opacity(0.35), .clear],
                                         center: .center, startRadius: 10, endRadius: 170))
                    .frame(width: 340, height: 340)
                    .scaleEffect(glow ? 1.04 : 0.96)
                if done { SunRays().frame(width: 340, height: 340).opacity(0.5) }
                GiantPlate(theme: BigRecipe.theme(state.week), items: state.plate, visible: visible, landing: landing)
                    .frame(width: 320, height: 320)
                if !state.plate.isEmpty { Steam().frame(width: 200, height: 120).offset(y: -130) }
            }
            .frame(height: 330)
            Ribbon(title: state.plate.isEmpty ? lang.t("recipe.dish." + BigRecipe.theme(state.week)) : dishName,
                   color: done ? Theme.gold : Theme.red, dark: done ? ButtonPalette.gold.dark : Theme.ribbonDark, size: 17)
                .padding(.horizontal, 6)
        }
        .padding(.top, 4)
    }

    /// Состав: какие начинки уже лежат на блюде и сколько.
    private func composition(_ state: RecipeState) -> some View {
        let placed = state.plate.prefix(visible)
        let counts: [(String, Int)] = BigRecipe.items.map { item in (item, placed.filter { $0 == item }.count) }.filter { $0.1 > 0 }
        return VStack(spacing: 6) {
            Text(lang.t("recipe.composition"))
                .font(Theme.rounded(13, .black))
                .foregroundColor(Color(red: 1, green: 0.9, blue: 0.7))
                .outlined(Theme.woodDark, width: 1)
            HStack(spacing: 6) {
                ForEach(counts.indices, id: \.self) { k in
                    HStack(spacing: 2) {
                        SpriteImage(name: GiantPlate.topping(counts[k].0), size: 30)
                        Text("×\(counts[k].1)").font(Theme.rounded(14, .black)).foregroundColor(Theme.brown).monospacedDigit()
                    }
                    .padding(.horizontal, 6)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.card))
                    .overlay(Capsule().strokeBorder(Theme.chipBorder, lineWidth: 2))
                }
            }
        }
    }

    private func stepsTrack(_ state: RecipeState) -> some View {
        VStack(spacing: 6) {
            Text(lang.t("recipe.step", min(state.step + 1, BigRecipe.steps), BigRecipe.steps))
                .font(Theme.rounded(15, .black))
                .foregroundColor(.white)
                .outlined(Theme.woodDark, width: 1.2)
            ScrollViewReader { proxy in
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 5) {
                        ForEach(0..<BigRecipe.steps, id: \.self) { i in
                            let done = i < state.step
                            let milestone = BigRecipe.isMilestone(i)
                            ZStack {
                                Circle().fill(done ? Theme.green : (i == state.step ? Theme.gold : Theme.cream))
                                Circle().strokeBorder(Theme.woodDark.opacity(0.7), lineWidth: 2)
                                if milestone {
                                    SpriteImage(name: i == BigRecipe.steps - 1 ? "chest_gold" : (i >= 14 ? "chest_silver" : "chest_bronze"),
                                                size: 26)
                                } else if done, state.plate.indices.contains(i) {
                                    SpriteImage(name: GiantPlate.topping(state.plate[i]), size: 22)
                                } else {
                                    Text("\(i + 1)").font(Theme.rounded(11, .black)).foregroundColor(Theme.brownSoft)
                                }
                            }
                            .frame(width: milestone ? 36 : 28, height: milestone ? 36 : 28)
                            .id(i)
                        }
                    }
                    .padding(.horizontal, 6)
                    .padding(.vertical, 4)
                }
                .onAppear { proxy.scrollTo(min(state.step, BigRecipe.steps - 1), anchor: .center) }
            }
            .background(Capsule().fill(Theme.woodDark.opacity(0.55)))
        }
    }

    /// Что собрать и во что это превратится на блюде: продукт -> начинка.
    private func ingredientPair(_ item: String, size: CGFloat) -> some View {
        HStack(spacing: 2) {
            SpriteImage(name: item, size: size)
            Image(systemName: "arrow.right")
                .font(.system(size: size * 0.26, weight: .black))
                .foregroundColor(Theme.brownSoft)
                .flipsForRightToLeftLayoutDirection(true)
            SpriteImage(name: GiantPlate.topping(item), size: size * 0.82)
        }
    }

    private func choiceCards(_ state: RecipeState) -> some View {
        let options = progress.recipeOptions
        return VStack(spacing: 8) {
            Text(lang.t("recipe.choose")).font(Theme.rounded(16, .black)).foregroundColor(.white).outlined(Theme.woodDark, width: 1.2)
            HStack(spacing: 10) {
                ForEach(options.indices, id: \.self) { i in
                    let o = options[i]
                    VStack(spacing: 6) {
                        Text(lang.t(i == 0 ? "recipe.easy" : "recipe.hard"))
                            .font(Theme.rounded(12, .black))
                            .foregroundColor(.white)
                            .padding(.horizontal, 8).padding(.vertical, 2)
                            .background(Capsule().fill(i == 0 ? Theme.green : Theme.red))
                        ingredientPair(o.item, size: 54)
                        Text(lang.t("recipe.collect", o.count)).font(Theme.rounded(15, .black)).foregroundColor(Theme.brown)
                        RewardChips(reward: o.reward, card: nil, perRow: 3, tileWidth: 46)
                        Button(lang.t("recipe.pick")) {
                            withAnimation(.spring(response: 0.35, dampingFraction: 0.7)) { progress.chooseRecipe(i) }
                            Haptics.light()
                        }
                        .buttonStyle(GameButtonStyle(palette: i == 0 ? .green : .orange, height: 40, fontSize: 16))
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity)
                    .background(PaperBackground(radius: 18))
                }
            }
        }
    }

    private func currentCard(_ o: BigRecipe.Option, state: RecipeState) -> some View {
        Panel {
            VStack(spacing: 8) {
                HStack(spacing: 10) {
                    ingredientPair(o.item, size: 52)
                    VStack(alignment: .leading, spacing: 4) {
                        Text(lang.t("recipe.collect", o.count)).font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                        GeometryReader { g in
                            ZStack(alignment: .leading) {
                                Capsule().fill(Theme.cream)
                                Capsule().fill(LinearGradient(colors: [Theme.gold, Theme.orange], startPoint: .leading, endPoint: .trailing))
                                    .frame(width: max(16, g.size.width * CGFloat(min(1, Double(state.progress) / Double(max(1, o.count))))))
                                Capsule().strokeBorder(Theme.chipBorder, lineWidth: 2)
                                Text("\(state.progress)/\(o.count)")
                                    .font(Theme.rounded(13, .black)).foregroundColor(Theme.brown)
                                    .frame(maxWidth: .infinity)
                            }
                        }
                        .frame(height: 22)
                    }
                }
                RewardChips(reward: o.reward, card: nil, perRow: 4, tileWidth: 52)
            }
        }
    }
}

/// Гигантское блюдо: 3D-основа недели (recipe_<тема>) и начинки (top_<продукт>), разложенные по верху блюда.
/// Верх блюда на картинке - эллипс (камера смотрит сверху под 62 градуса), его центр и радиусы в долях картинки
/// посчитаны при рендере (tools/render/models_recipe.py).
struct GiantPlate: View {
    let theme: String
    let items: [String]
    let visible: Int
    let landing: Int?

    private struct Surface {
        let cx, cy, rx, ry: CGFloat
    }

    private static let surfaces: [String: Surface] = [
        "pizza": Surface(cx: 0.430, cy: 0.472, rx: 0.262, ry: 0.231),
        "cake": Surface(cx: 0.500, cy: 0.383, rx: 0.306, ry: 0.270),
        "salad": Surface(cx: 0.481, cy: 0.490, rx: 0.317, ry: 0.280),
        "paella": Surface(cx: 0.500, cy: 0.491, rx: 0.307, ry: 0.271)
    ]

    static func topping(_ item: String) -> String { "top_" + item }

    var body: some View {
        GeometryReader { geo in
            let size = min(geo.size.width, geo.size.height)
            let surface = Self.surfaces[theme] ?? Self.surfaces["paella"]!
            let shown = Array(0..<min(visible, items.count))
            ZStack(alignment: .topLeading) {
                Ellipse()
                    .fill(Color.black.opacity(0.28))
                    .frame(width: size * 0.78, height: size * 0.2)
                    .blur(radius: size * 0.03)
                    .position(x: size * 0.5, y: size * 0.8)
                SpriteImage(name: "recipe_" + theme, size: size)
                    .position(x: size / 2, y: size / 2)
                ForEach(shown, id: \.self) { i in
                    let p = spot(i, surface)
                    SpriteImage(name: Self.topping(items[i]), size: size * 0.17)
                        .rotationEffect(.degrees(Double(i * 47 % 70) - 35))
                        .shadow(color: .black.opacity(0.25), radius: size * 0.008, y: size * 0.006)
                        .position(x: p.x * size, y: p.y * size)
                        .transition(.asymmetric(insertion: .offset(y: -size * 0.55).combined(with: .scale(scale: 1.7)).combined(with: .opacity),
                                                removal: .opacity))
                        .zIndex(Double(p.y))
                }
                if let landing = landing, landing < items.count {
                    let p = spot(landing, surface)
                    SplashBurst(color: Self.splash(items[landing]))
                        .frame(width: size * 0.3, height: size * 0.3)
                        .position(x: p.x * size, y: p.y * size)
                        .id("splash\(landing)")
                        .zIndex(10)
                        .allowsHitTesting(false)
                }
            }
            .frame(width: size, height: size)
        }
    }

    /// Место начинки: золотая спираль от центра к краю, сжатая в эллипс верха блюда, с небольшим разбросом.
    private func spot(_ i: Int, _ s: Surface) -> CGPoint {
        let a = Double(i) * 137.508 * .pi / 180
        let r = 0.82 * sqrt((Double(i) + 0.5) / Double(BigRecipe.steps))
        let jitter = 0.05 * sin(Double(i) * 12.9898)
        return CGPoint(x: s.cx + CGFloat(cos(a) * (r + jitter)) * s.rx,
                       y: s.cy + CGFloat(sin(a) * (r + jitter)) * s.ry)
    }

    private static func splash(_ item: String) -> Color {
        switch item {
        case "tomato": return Color(red: 0.95, green: 0.25, blue: 0.15)
        case "lime": return Color(red: 0.55, green: 0.85, blue: 0.25)
        case "cheese": return Color(red: 1.0, green: 0.80, blue: 0.25)
        case "grapes": return Color(red: 0.62, green: 0.32, blue: 0.75)
        case "carrot": return Color(red: 1.0, green: 0.55, blue: 0.15)
        default: return .white
        }
    }
}

/// Брызги в месте, куда легла начинка: кружки разлетаются и гаснут.
private struct SplashBurst: View {
    let color: Color
    @State private var go = false

    var body: some View {
        GeometryReader { geo in
            let r = min(geo.size.width, geo.size.height) / 2
            ZStack {
                Circle()
                    .strokeBorder(Color.white.opacity(0.9), lineWidth: 3)
                    .scaleEffect(go ? 1.0 : 0.2)
                    .opacity(go ? 0 : 0.9)
                ForEach(0..<8, id: \.self) { k in
                    let a = Double(k) / 8 * 2 * .pi + 0.3
                    Circle()
                        .fill(k % 2 == 0 ? color : Color.white)
                        .frame(width: r * 0.22, height: r * 0.22)
                        .offset(x: go ? CGFloat(cos(a)) * r : 0, y: go ? CGFloat(sin(a)) * r * 0.8 : 0)
                        .scaleEffect(go ? 0.3 : 1)
                        .opacity(go ? 0 : 1)
                }
            }
            .frame(width: geo.size.width, height: geo.size.height)
        }
        .onAppear { withAnimation(.easeOut(duration: 0.55)) { go = true } }
    }
}

/// Пар над горячим блюдом: три мягкие струйки поднимаются и тают.
private struct Steam: View {
    @State private var rise = false

    var body: some View {
        HStack(spacing: 26) {
            ForEach(0..<3, id: \.self) { k in
                Capsule()
                    .fill(Color.white.opacity(0.45))
                    .frame(width: 14, height: 46)
                    .blur(radius: 7)
                    .offset(y: rise ? -26 : 14)
                    .opacity(rise ? 0 : 0.85)
                    .animation(.easeOut(duration: 2.2).repeatForever(autoreverses: false).delay(Double(k) * 0.6), value: rise)
            }
        }
        .allowsHitTesting(false)
        .onAppear { rise = true }
    }
}

/// Лучи за готовым блюдом, медленно вращаются.
private struct SunRays: View {
    @State private var spin = false

    var body: some View {
        ZStack {
            ForEach(0..<12, id: \.self) { k in
                RayShape()
                    .fill(Color(red: 1.0, green: 0.92, blue: 0.55).opacity(0.55))
                    .rotationEffect(.degrees(Double(k) * 30))
            }
        }
        .rotationEffect(.degrees(spin ? 360 : 0))
        .animation(.linear(duration: 30).repeatForever(autoreverses: false), value: spin)
        .allowsHitTesting(false)
        .onAppear { spin = true }
    }

    private struct RayShape: Shape {
        func path(in rect: CGRect) -> Path {
            var p = Path()
            let c = CGPoint(x: rect.midX, y: rect.midY)
            p.move(to: c)
            p.addLine(to: CGPoint(x: rect.midX - rect.width * 0.07, y: rect.minY))
            p.addLine(to: CGPoint(x: rect.midX + rect.width * 0.07, y: rect.minY))
            p.closeSubpath()
            return p
        }
    }
}
