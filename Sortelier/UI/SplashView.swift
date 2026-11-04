import SwiftUI

/// Заставка при запуске: яркий фон в цветах иконки, вращающиеся лучи, крутящийся бургер,
/// парящие вокруг продукты, логотип и полоса загрузки с советами.
/// Пока она на экране, заранее читаются данные и картинки первого экрана, чтобы карта открылась без рывков.
struct SplashView: View {
    /// Не уходить сама: снимок заставки в CI.
    var hold = false
    let finished: () -> Void

    @EnvironmentObject private var lang: Lang
    @State private var loaded: Double = 0
    @State private var appeared = false
    @State private var leaving = false
    @State private var tip = Int.random(in: 0..<SplashView.tipCount)

    static let tipCount = 5
    /// Меньше не показываем, даже если все загрузилось мгновенно: иначе заставка мелькнет.
    private static let minDuration: TimeInterval = 2.2

    private static let floaters: [(name: String, x: CGFloat, y: CGFloat, size: CGFloat, phase: Double)] = [
        ("tomato", 0.15, 0.12, 62, 0.0), ("cheese", 0.85, 0.11, 58, 1.3), ("egg", 0.5, 0.05, 40, 3.3),
        ("donut", 0.1, 0.33, 54, 0.7), ("lime", 0.9, 0.3, 50, 2.1),
        ("strawberry", 0.11, 0.52, 46, 2.8), ("fries", 0.89, 0.5, 54, 1.8)
    ]

    var body: some View {
        GeometryReader { geo in
            ZStack {
                background
                rays(geo.size)
                TimelineView(.animation) { context in
                    let t = context.date.timeIntervalSinceReferenceDate
                    ZStack {
                        floaters(geo.size, t)
                        sparkles(geo.size, t)
                        hero(geo.size, t)
                    }
                }
                logo
                    .position(x: geo.size.width / 2, y: geo.size.height * 0.4 + Self.heroSide(geo.size) * 0.5 + 64)
                VStack(spacing: 0) {
                    Spacer(minLength: 0)
                    loader
                        .padding(.horizontal, 36)
                        .padding(.bottom, 40)
                }
                .frame(width: geo.size.width, height: geo.size.height)
            }
            .frame(width: geo.size.width, height: geo.size.height)
        }
        .ignoresSafeArea()
        .scaleEffect(leaving ? 1.15 : 1)
        .opacity(leaving ? 0 : 1)
        .onAppear {
            withAnimation(.spring(response: 0.55, dampingFraction: 0.6)) { appeared = true }
            load()
        }
    }

    // MARK: - Фон

    private var background: some View {
        RadialGradient(colors: [Color(red: 1.0, green: 0.88, blue: 0.5), Color(red: 0.98, green: 0.62, blue: 0.2),
                                Color(red: 0.86, green: 0.36, blue: 0.1)],
                       center: .init(x: 0.5, y: 0.4), startRadius: 10, endRadius: 520)
    }

    /// Солнечные лучи от бургера: медленно вращаются.
    private func rays(_ size: CGSize) -> some View {
        TimelineView(.animation) { context in
            let angle = context.date.timeIntervalSinceReferenceDate.truncatingRemainder(dividingBy: 60) * 6
            SunRays(count: 18)
                .fill(Color.white.opacity(0.16))
                .frame(width: size.height * 1.4, height: size.height * 1.4)
                .rotationEffect(.degrees(angle))
                .position(x: size.width / 2, y: size.height * 0.4)
        }
        .mask(RadialGradient(colors: [.white, .white.opacity(0)], center: .init(x: 0.5, y: 0.4), startRadius: 60, endRadius: size.height * 0.6))
    }

    // MARK: - Бургер и продукты

    private func hero(_ size: CGSize, _ t: TimeInterval) -> some View {
        let frame = Int(t * 12) % 24
        let bob = CGFloat(sin(t * 2.4) * 8)
        let side = Self.heroSide(size)
        return ZStack {
            Ellipse()
                .fill(Color(red: 0.55, green: 0.2, blue: 0.05).opacity(0.28))
                .frame(width: side * (0.62 - bob / 400), height: side * 0.12)
                .blur(radius: 6)
                .offset(y: side * 0.46)
            Image(uiImage: Art.image(Art.spinFrame("burger", frame)))
                .resizable()
                .aspectRatio(contentMode: .fit)
                .frame(width: side, height: side)
                .offset(y: bob)
        }
        .scaleEffect(appeared ? (leaving ? 1.3 : 1) : 0.2)
        .position(x: size.width / 2, y: size.height * 0.4)
    }

    private static func heroSide(_ size: CGSize) -> CGFloat {
        min(size.width * 0.62, size.height * 0.3, 250)
    }

    private func floaters(_ size: CGSize, _ t: TimeInterval) -> some View {
        ForEach(Self.floaters.indices, id: \.self) { i in
            let f = Self.floaters[i]
            let dx = CGFloat(sin(t * 0.9 + f.phase) * 10)
            let dy = CGFloat(cos(t * 1.3 + f.phase) * 14)
            SpriteImage(name: f.name, size: f.size)
                .shadow(color: Color(red: 0.5, green: 0.18, blue: 0.04).opacity(0.3), radius: 4, y: 4)
                .rotationEffect(.degrees(sin(t * 1.1 + f.phase) * 14))
                .scaleEffect(appeared ? 1 : 0)
                .animation(.spring(response: 0.5, dampingFraction: 0.55).delay(0.15 + Double(i) * 0.05), value: appeared)
                .position(x: size.width * f.x + dx, y: size.height * f.y + dy)
        }
    }

    /// Искорки: мерцают на месте, каждая в своем ритме.
    private func sparkles(_ size: CGSize, _ t: TimeInterval) -> some View {
        ForEach(0..<12, id: \.self) { i in
            let seed = Double(i) * 1.618
            let x = CGFloat((seed * 0.37).truncatingRemainder(dividingBy: 1))
            let y = CGFloat((seed * 0.53 + 0.1).truncatingRemainder(dividingBy: 0.75))
            let pulse = (sin(t * 3 + seed * 4) + 1) / 2
            Image(systemName: "sparkle")
                .font(.system(size: 10 + CGFloat(i % 3) * 6, weight: .bold))
                .foregroundColor(.white)
                .opacity(0.25 + pulse * 0.7)
                .scaleEffect(CGFloat(0.6 + pulse * 0.6))
                .position(x: size.width * (0.06 + x * 0.88), y: size.height * (0.05 + y))
        }
    }

    // MARK: - Логотип и загрузка

    private var logo: some View {
        VStack(spacing: 10) {
            StrokeText(text: "Sortelier", size: 56, weight: .black, color: .white,
                       stroke: Color(red: 0.55, green: 0.18, blue: 0.04), width: 3, drop: 5)
                .shadow(color: Color(red: 0.5, green: 0.15, blue: 0.0).opacity(0.35), radius: 8, y: 4)
            Ribbon(title: lang.t("splash.subtitle"), size: 17)
        }
        .scaleEffect(appeared ? 1 : 0.4)
        .opacity(appeared ? 1 : 0)
        .animation(.spring(response: 0.6, dampingFraction: 0.55).delay(0.1), value: appeared)
    }

    private var loader: some View {
        VStack(spacing: 12) {
            StrokeText(text: lang.t("splash.loading"), size: 17, weight: .heavy, color: .white,
                       stroke: Color(red: 0.55, green: 0.18, blue: 0.04), width: 1.5, drop: 2)
            LoadingBar(value: loaded)
                .frame(height: 26)
            Text(lang.t("splash.tip.\(tip)"))
                .font(Theme.rounded(14, .semibold))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(.horizontal, 16)
                .padding(.vertical, 10)
                .frame(maxWidth: .infinity)
                .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card.opacity(0.88)))
                .id(tip)
                .transition(.opacity)
        }
        .opacity(appeared ? 1 : 0)
        .animation(.easeOut(duration: 0.4).delay(0.3), value: appeared)
    }

    // MARK: - Загрузка

    /// Что прогреваем, по шагу за кадр: каталоги и уровни, затем картинки первого экрана.
    private var steps: [() -> Void] {
        let progress = PlayerProgress.shared
        return [
            { _ = Catalog.shared },
            { _ = LevelStore.shared },
            { _ = EventLevelStore.shared },
            { _ = MarketCatalog.shared },
            { _ = Art.image(KitchenStyle.image(progress.background(forBiome: progress.mapBiome))) },
            { AppTab.allCases.forEach { _ = Art.image($0.icon) } },
            {
                ["icon_star", "icon_heart", "coin_icon", "icon_lock", "gen_crate", "icon_market", "icon_garden", "icon_gift",
                 "chest_bronze", "chest_silver", "chest_gold"].forEach { _ = Art.image($0) }
            },
            { Catalog.shared.items(inBiome: progress.mapBiome).forEach { _ = Art.image($0.id) } },
            { (0..<24).forEach { _ = Art.image(Art.spinFrame("burger", $0)) } }
        ]
    }

    private func load() {
        let work = steps
        let start = Date()
        func run(_ i: Int) {
            guard i < work.count else { return finish(start) }
            work[i]()
            withAnimation(.easeOut(duration: 0.3)) { loaded = Double(i + 1) / Double(work.count) * 0.9 }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.12) { run(i + 1) }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { run(0) }
    }

    private func finish(_ start: Date) {
        if hold { return }
        let wait = max(0, Self.minDuration - Date().timeIntervalSince(start))
        DispatchQueue.main.asyncAfter(deadline: .now() + wait * 0.5) {
            withAnimation(.easeOut(duration: 0.3)) { tip = (tip + 1) % Self.tipCount }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + wait) {
            withAnimation(.easeOut(duration: 0.3)) { loaded = 1 }
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) {
                withAnimation(.easeIn(duration: 0.35)) { leaving = true }
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.36) { finished() }
            }
        }
    }
}

/// Полоса загрузки: деревянная рамка, кремовая подложка, оранжевая заливка с бегущим бликом.
private struct LoadingBar: View {
    let value: Double

    var body: some View {
        GeometryReader { geo in
            let inner = geo.size.width - 8
            let fill = CGFloat(value)
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.woodDark)
                Capsule().fill(Theme.cream).padding(4)
                TimelineView(.animation) { context in
                    let t = context.date.timeIntervalSinceReferenceDate
                    let shine = CGFloat((t * 0.8).truncatingRemainder(dividingBy: 1))
                    Capsule()
                        .fill(LinearGradient(colors: [Theme.gold, Theme.orange], startPoint: .top, endPoint: .bottom))
                        .overlay(
                            LinearGradient(colors: [.white.opacity(0), .white.opacity(0.55), .white.opacity(0)],
                                           startPoint: .leading, endPoint: .trailing)
                                .frame(width: 40)
                                .offset(x: -40 + shine * (inner * max(fill, 0.05) + 40)),
                            alignment: .leading
                        )
                        .overlay(Capsule().fill(Color.white.opacity(0.35)).frame(height: 5).padding(.horizontal, 8).offset(y: -4))
                        .clipShape(Capsule())
                        .frame(width: max(geo.size.height - 8, inner * fill))
                }
                .padding(4)
            }
        }
    }
}

/// Лучи-клинья от центра.
private struct SunRays: Shape {
    let count: Int

    func path(in rect: CGRect) -> Path {
        var p = Path()
        let center = CGPoint(x: rect.midX, y: rect.midY)
        let radius = max(rect.width, rect.height) / 2
        let step = 2 * Double.pi / Double(count)
        for i in 0..<count {
            let a = Double(i) * step
            p.move(to: center)
            p.addLine(to: CGPoint(x: center.x + radius * CGFloat(cos(a - step * 0.22)), y: center.y + radius * CGFloat(sin(a - step * 0.22))))
            p.addLine(to: CGPoint(x: center.x + radius * CGFloat(cos(a + step * 0.22)), y: center.y + radius * CGFloat(sin(a + step * 0.22))))
            p.closeSubpath()
        }
        return p
    }
}
