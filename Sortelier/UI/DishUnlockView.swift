import SwiftUI

/// Открытие нового блюда: лучи, вращающееся блюдо и конфетти.
struct DishUnlockView: View {
    let dish: String
    let close: () -> Void

    @EnvironmentObject private var lang: Lang
    @State private var appear = false
    @State private var start = Date()

    var body: some View {
        ZStack {
            Color.black.opacity(0.6).ignoresSafeArea()
            TimelineView(.animation) { timeline in
                let t = timeline.date.timeIntervalSince(start)
                ZStack {
                    rays(t)
                    confetti(t)
                    VStack(spacing: 18) {
                        Text(lang.t("unlock.title"))
                            .font(Theme.rounded(30, .heavy))
                            .foregroundColor(Theme.gold)
                            .shadow(color: .black.opacity(0.35), radius: 0, y: 3)
                        Image(uiImage: Art.image(Art.spinFrame(dish, Int(t * 14) % 24)))
                            .resizable()
                            .aspectRatio(contentMode: .fit)
                            .frame(width: 230, height: 230)
                            .scaleEffect(appear ? 1 : 0.2)
                        Text(lang.dishName(dish))
                            .font(Theme.rounded(26, .heavy))
                            .foregroundColor(.white)
                        if let recipe = Catalog.shared.dish(dish) {
                            HStack(spacing: 6) {
                                ForEach(Array(recipe.ingredients.enumerated()), id: \.offset) { i, ing in
                                    if i > 0 {
                                        Text("+").font(Theme.rounded(20, .heavy)).foregroundColor(.white.opacity(0.7))
                                    }
                                    VStack(spacing: 2) {
                                        SpriteImage(name: ing, size: 46)
                                        Text(lang.itemName(ing))
                                            .font(Theme.rounded(11, .bold))
                                            .foregroundColor(.white.opacity(0.85))
                                    }
                                }
                            }
                        }
                        Text(lang.t("unlock.book"))
                            .font(Theme.rounded(14, .semibold))
                            .foregroundColor(.white.opacity(0.75))
                        Button(lang.t("unlock.ok"), action: close)
                            .buttonStyle(BigButtonStyle())
                            .frame(maxWidth: 240)
                            .opacity(appear ? 1 : 0)
                    }
                    .padding(24)
                }
            }
        }
        .onAppear {
            Haptics.success()
            Audio.shared.play(.unlock)
            withAnimation(.spring(response: 0.5, dampingFraction: 0.55)) { appear = true }
        }
    }

    private func rays(_ t: TimeInterval) -> some View {
        ZStack {
            ForEach(0..<12, id: \.self) { i in
                Rectangle()
                    .fill(LinearGradient(colors: [Theme.gold.opacity(0.55), Theme.gold.opacity(0)],
                                         startPoint: .bottom, endPoint: .top))
                    .frame(width: 34, height: 260)
                    .offset(y: -130)
                    .rotationEffect(.degrees(Double(i) * 30 + t * 18))
            }
            Circle()
                .fill(RadialGradient(colors: [Theme.gold.opacity(0.7), .clear], center: .center, startRadius: 10, endRadius: 170))
                .frame(width: 340, height: 340)
        }
        .offset(y: -40)
        .opacity(appear ? 1 : 0)
    }

    private func confetti(_ t: TimeInterval) -> some View {
        Canvas { context, size in
            let colors: [Color] = [Theme.gold, Theme.orange, .pink, .white, Theme.green]
            for i in 0..<60 {
                let seed = Double(i) * 12.9898
                let rx = (sin(seed) * 43758.5453).truncatingRemainder(dividingBy: 1)
                let ry = (sin(seed * 1.7) * 23421.631).truncatingRemainder(dividingBy: 1)
                let speed = 70 + abs(ry) * 120
                let x = size.width * abs(rx) + CGFloat(sin(t * 2 + seed)) * 18
                let y = (CGFloat(t * speed) + size.height * abs(ry)).truncatingRemainder(dividingBy: size.height + 40) - 20
                var piece = Path(roundedRect: CGRect(x: -4, y: -2, width: 8, height: 4), cornerRadius: 1)
                piece = piece.applying(CGAffineTransform(rotationAngle: CGFloat(t * 3 + seed)))
                context.translateBy(x: x, y: y)
                context.fill(piece, with: .color(colors[i % colors.count]))
                context.translateBy(x: -x, y: -y)
            }
        }
        .allowsHitTesting(false)
        .ignoresSafeArea()
    }
}
