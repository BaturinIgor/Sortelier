import SwiftUI

/// "Большой рецепт": 25 шагов за неделю, на каждом выбор из двух ингредиентов.
/// Закрытый шаг кладет ингредиент на гигантское блюдо, к концу недели у каждого свое блюдо.
struct BigRecipeView: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var visible = 0
    @State private var landing: Int?

    var body: some View {
        let state = progress.recipe
        ZStack {
            KitchenBackground(blurred: true)
            ScrollView(showsIndicators: false) {
                VStack(spacing: 14) {
                    header
                    GiantPlate(theme: BigRecipe.theme(state.week), items: state.plate, visible: visible, landing: landing)
                        .frame(width: 300, height: 300)
                        .padding(.top, 4)
                    if !state.plate.isEmpty {
                        Text(dishName)
                            .font(Theme.rounded(18, .black))
                            .foregroundColor(.white)
                            .outlined(Theme.woodDark, width: 1.4)
                            .multilineTextAlignment(.center)
                    }
                    stepsTrack(state)
                    if progress.recipeDone {
                        Panel {
                            VStack(spacing: 8) {
                                SpriteImage(name: "icon_trophy", size: 70)
                                Text(lang.t("recipe.done")).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
                                    .multilineTextAlignment(.center)
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
                        .padding(.horizontal, 10)
                }
                .padding(.horizontal, 14)
                .padding(.bottom, 30)
            }
        }
        .onAppear {
            let s = progress.recipe
            let fresh = min(s.unseen, s.plate.count)
            visible = s.plate.count - fresh
            for i in 0..<fresh {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.5 + Double(i) * 0.55) {
                    landing = visible
                    withAnimation(.spring(response: 0.45, dampingFraction: 0.55)) { visible += 1 }
                    Audio.shared.play(.dish, volume: 0.7)
                    Haptics.light()
                }
            }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.6 + Double(fresh) * 0.55) {
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
                                    SpriteImage(name: state.plate[i], size: 20)
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
                        SpriteImage(name: o.item, size: 64)
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
                    SpriteImage(name: o.item, size: 60)
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

/// Гигантское блюдо: основа по теме недели и ингредиенты по спирали от центра.
struct GiantPlate: View {
    let theme: String
    let items: [String]
    let visible: Int
    let landing: Int?

    var body: some View {
        GeometryReader { geo in
            let size = min(geo.size.width, geo.size.height)
            ZStack {
                Circle().fill(Color.black.opacity(0.25)).offset(y: 8).blur(radius: 6)
                Circle().fill(LinearGradient(colors: [Color.white, Color(red: 0.88, green: 0.88, blue: 0.9)], startPoint: .top, endPoint: .bottom))
                Circle().strokeBorder(Color(red: 0.75, green: 0.75, blue: 0.8), lineWidth: 3)
                base.frame(width: size * 0.82, height: size * 0.82)
                ForEach(0..<min(visible, items.count), id: \.self) { i in
                    SpriteImage(name: items[i], size: size * 0.15)
                        .rotationEffect(.degrees(Double(i * 47 % 60) - 30))
                        .offset(spot(i, radius: size * 0.36))
                        .transition(.asymmetric(insertion: .offset(y: -size * 0.6).combined(with: .scale(scale: 1.6)).combined(with: .opacity),
                                                removal: .opacity))
                        .zIndex(Double(i))
                }
            }
            .frame(width: size, height: size)
        }
    }

    private func spot(_ i: Int, radius: CGFloat) -> CGSize {
        let a = Double(i) * 137.508 * .pi / 180
        let r = radius * CGFloat(sqrt((Double(i) + 0.6) / Double(BigRecipe.steps)))
        return CGSize(width: cos(a) * r, height: sin(a) * r)
    }

    @ViewBuilder
    private var base: some View {
        switch theme {
        case "pizza":
            ZStack {
                Circle().fill(RadialGradient(colors: [Color(red: 0.95, green: 0.75, blue: 0.45), Color(red: 0.80, green: 0.52, blue: 0.25)],
                                             center: .center, startRadius: 60, endRadius: 130))
                Circle().fill(RadialGradient(colors: [Color(red: 0.92, green: 0.30, blue: 0.18), Color(red: 0.80, green: 0.20, blue: 0.12)],
                                             center: .center, startRadius: 10, endRadius: 120)).padding(16)
                Circle().fill(Color(red: 1, green: 0.93, blue: 0.7).opacity(0.55)).padding(30).blur(radius: 6)
            }
        case "cake":
            ZStack {
                Circle().fill(Color(red: 0.98, green: 0.80, blue: 0.85))
                Circle().strokeBorder(Color.white, style: StrokeStyle(lineWidth: 10, dash: [14, 8])).padding(6)
                Circle().fill(Color(red: 1, green: 0.95, blue: 0.9)).padding(22)
            }
        case "salad":
            ZStack {
                Circle().fill(Color(red: 0.55, green: 0.80, blue: 0.95))
                Circle().fill(RadialGradient(colors: [Color(red: 0.70, green: 0.92, blue: 0.45), Color(red: 0.35, green: 0.70, blue: 0.25)],
                                             center: .center, startRadius: 10, endRadius: 120)).padding(12)
            }
        default:
            ZStack {
                Circle().fill(Color(red: 0.18, green: 0.18, blue: 0.2))
                Circle().fill(RadialGradient(colors: [Color(red: 1, green: 0.85, blue: 0.35), Color(red: 0.92, green: 0.62, blue: 0.15)],
                                             center: .center, startRadius: 10, endRadius: 120)).padding(10)
            }
        }
    }
}
