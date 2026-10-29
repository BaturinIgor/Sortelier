import SwiftUI

// MARK: - Огород

/// Огород поставщика: три грядки растут в реальном времени, победы их поливают.
struct GardenView: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var granted: Granted?
    @State private var flying: (Int, String)?

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.1, style: "autumn")
            VStack(spacing: 12) {
                HStack(spacing: 8) {
                    CircleIconButton(symbol: "xmark", size: 42, action: close)
                    StrokeText(text: lang.t("garden.title"), size: 22, weight: .black, color: Color(red: 1.0, green: 0.95, blue: 0.84),
                               stroke: Theme.woodDark, width: 1.5, drop: 2)
                    Spacer()
                    if HappyHour.active(progress.now) { HappyHourChip() }
                }
                .padding(.top, 8)
                Text(lang.t("garden.text", Int(Garden.waterSeconds / 60)))
                    .font(Theme.rounded(14, .bold))
                    .foregroundColor(.white)
                    .outlined(Theme.woodDark, width: 1.2)
                    .multilineTextAlignment(.center)
                    .fixedSize(horizontal: false, vertical: true)
                ForEach(0..<Garden.bedCount, id: \.self) { i in bed(i) }
                Spacer()
            }
            .padding(.horizontal, 14)
            if let g = granted {
                RewardPopup(title: lang.t("garden.harvested"), granted: g) { granted = nil }
            }
        }
    }

    private func bed(_ i: Int) -> some View {
        let item = progress.gardenBeds[i].item
        let left = progress.gardenLeft(i)
        let fraction = progress.gardenFraction(i)
        let ready = left <= 0
        return HStack(spacing: 12) {
            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Color(red: 0.42, green: 0.26, blue: 0.14))
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .fill(LinearGradient(colors: [Color(red: 0.36, green: 0.22, blue: 0.12), Color(red: 0.25, green: 0.15, blue: 0.08)],
                                         startPoint: .top, endPoint: .bottom))
                    .padding(6)
                    .frame(height: 44)
                HStack(spacing: 6) {
                    ForEach(0..<3, id: \.self) { k in
                        SpriteImage(name: item, size: 30 + 22 * CGFloat(fraction))
                            .saturation(0.35 + 0.65 * fraction)
                            .offset(y: CGFloat(k % 2) * -4)
                            .modifier(Pulse(active: ready))
                    }
                }
                .padding(.bottom, 18)
                if flying?.0 == i {
                    SpriteImage(name: item, size: 50)
                        .transition(.asymmetric(insertion: .identity, removal: .offset(y: -200).combined(with: .opacity)))
                }
            }
            .frame(width: 170, height: 110)
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Theme.woodDark, lineWidth: 3))
            VStack(spacing: 8) {
                Text(lang.t("garden.crop." + item)).font(Theme.rounded(16, .black)).foregroundColor(Theme.brown)
                if ready {
                    Button(lang.t("garden.harvest")) {
                        guard let harvested = progress.harvest(i) else { return }
                        let g = harvested.0
                        Audio.shared.play(.chest)
                        Haptics.success()
                        withAnimation(.easeOut(duration: 0.5)) { flying = (i, item) }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.1) { withAnimation(.easeIn(duration: 0.5)) { flying = nil } }
                        DispatchQueue.main.asyncAfter(deadline: .now() + 0.55) { granted = g }
                    }
                    .buttonStyle(GameButtonStyle(palette: .green, height: 42, fontSize: 17))
                } else {
                    Text(Lang.time(left)).font(Theme.rounded(18, .black)).foregroundColor(Theme.brown).monospacedDigit()
                    GeometryReader { g in
                        ZStack(alignment: .leading) {
                            Capsule().fill(Theme.cream)
                            Capsule().fill(Theme.green).frame(width: max(10, g.size.width * CGFloat(fraction)))
                            Capsule().strokeBorder(Theme.chipBorder, lineWidth: 2)
                        }
                    }
                    .frame(height: 12)
                }
                Text(lang.t("garden.yield", Garden.yield)).font(Theme.rounded(12, .bold)).foregroundColor(Theme.brownSoft)
            }
            .frame(maxWidth: .infinity)
        }
        .padding(10)
        .background(PaperBackground(radius: 20))
    }
}

// MARK: - Банка чаевых

struct JarPopup: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @ObservedObject private var store = Store.shared
    @State private var granted: Granted?

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("jar.title"), close: close, maxWidth: 330) {
                VStack(spacing: 12) {
                    JarGlyph(fill: Double(progress.jarCoins) / Double(TipJar.capacity))
                        .frame(width: 130, height: 150)
                    HStack(spacing: 6) {
                        CoinIcon(size: 28)
                        Text("\(progress.jarCoins)").font(Theme.rounded(26, .black)).foregroundColor(Theme.brown).monospacedDigit()
                        Text("/ \(TipJar.capacity)").font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brownSoft)
                    }
                    Text(lang.t(progress.jarFull ? "jar.full" : "jar.text"))
                        .font(Theme.rounded(14, .semibold))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button {
                        Task {
                            let outcome = await store.buy(.jar)
                            if case let .done(g) = outcome, let g = g { granted = g }
                            if case .unavailable = outcome { Toast.error(lang.t("shop.unavailable")) }
                        }
                    } label: {
                        Text(lang.t("jar.break", store.price(.jar)))
                    }
                    .buttonStyle(GameButtonStyle(palette: .gold))
                    .disabled(!progress.jarCanBreak)
                    .opacity(progress.jarCanBreak ? 1 : 0.6)
                    if !progress.jarCanBreak {
                        Text(lang.t("jar.min", TipJar.minimum)).font(Theme.rounded(12, .bold)).foregroundColor(Theme.brownSoft)
                    }
                }
            }
            if let g = granted {
                RewardPopup(title: lang.t("jar.broken"), granted: g) { granted = nil; close() }
            }
        }
    }
}

/// Стеклянная банка с монетами: уровень монет по заполнению.
struct JarGlyph: View {
    let fill: Double

    var body: some View {
        GeometryReader { g in
            let w = g.size.width, h = g.size.height
            ZStack(alignment: .bottom) {
                RoundedRectangle(cornerRadius: w * 0.22, style: .continuous)
                    .fill(Color(red: 0.85, green: 0.95, blue: 1).opacity(0.45))
                VStack(spacing: -h * 0.06) {
                    ForEach(0..<max(1, Int(fill * 9)), id: \.self) { row in
                        HStack(spacing: -w * 0.08) {
                            ForEach(0..<4, id: \.self) { _ in CoinIcon(size: w * 0.3) }
                        }
                        .offset(x: row % 2 == 0 ? -w * 0.04 : w * 0.04)
                    }
                }
                .frame(height: h * 0.82 * CGFloat(max(0.08, min(1, fill))), alignment: .bottom)
                .clipped()
                .padding(.bottom, h * 0.06)
                RoundedRectangle(cornerRadius: w * 0.22, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.95), lineWidth: 4)
                Capsule().fill(Color.white.opacity(0.7)).frame(width: w * 0.08, height: h * 0.45)
                    .offset(x: -w * 0.3, y: -h * 0.3)
                RoundedRectangle(cornerRadius: 6).fill(Color(red: 0.75, green: 0.5, blue: 0.25))
                    .frame(width: w * 0.7, height: h * 0.1)
                    .offset(y: -h * 0.95)
            }
            .frame(width: w, height: h)
        }
    }
}

// MARK: - Тайный критик

/// Критик пришел на уровень: показывается на старте.
struct CriticArrivalView: View {
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Color.black.opacity(0.35).ignoresSafeArea()
            VStack(spacing: 10) {
                SpriteImage(name: Critic.sprite, size: 140)
                Ribbon(title: lang.t("critic.arrived"), color: Theme.vip, dark: ButtonPalette.purple.dark)
                Text(lang.t("critic.arrived.text"))
                    .font(Theme.rounded(16, .heavy))
                    .foregroundColor(.white)
                    .outlined(Theme.woodDark, width: 1.4)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 30)
            }
        }
    }
}

/// Рецензия критика в окне победы.
struct CriticReviewCard: View {
    let review: CriticReview
    @EnvironmentObject private var lang: Lang

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            SpriteImage(name: Critic.sprite, size: 64)
            VStack(alignment: .leading, spacing: 4) {
                StarsRow(count: review.stars, size: 16)
                Text("\"" + lang.t("critic.review.\(review.stars).\(review.text)") + "\"")
                    .font(Theme.rounded(14, .semibold))
                    .italic()
                    .foregroundColor(Theme.brown)
                    .fixedSize(horizontal: false, vertical: true)
                Text(lang.t("critic.points", review.points))
                    .font(Theme.rounded(13, .black))
                    .foregroundColor(Theme.vip)
            }
        }
        .padding(10)
        .background(InsetBackground(radius: 14, color: Color(red: 0.96, green: 0.92, blue: 1)))
    }
}

/// Рейтинг ресторана за месяц: 5 звезд критика и награды за каждую.
struct CriticPanel: View {
    let granted: (Granted) -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        let s = progress.critic
        Panel {
            VStack(spacing: 10) {
                HStack(spacing: 10) {
                    SpriteImage(name: Critic.sprite, size: 66)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(lang.t("critic.title")).font(Theme.rounded(18, .black)).foregroundColor(Theme.brown)
                        Text(lang.t(s.pending ? "critic.next.pending" : "critic.next"))
                            .font(Theme.rounded(13, .semibold)).foregroundColor(Theme.brownSoft)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    Spacer(minLength: 0)
                }
                HStack(spacing: 6) {
                    ForEach(Critic.thresholds.indices, id: \.self) { i in
                        let reached = s.points >= Critic.thresholds[i]
                        let claimable = progress.criticClaimable(i)
                        Button {
                            if claimable, let g = progress.claimCritic(i) {
                                Audio.shared.play(.chest)
                                granted(g)
                            } else {
                                RewardInfo.show(Critic.reward(i).items.first ?? .coins(0))
                            }
                        } label: {
                            VStack(spacing: 2) {
                                HStack(spacing: -4) {
                                    ForEach(0...i, id: \.self) { _ in SpriteImage(name: "icon_star", size: 14, silhouette: !reached) }
                                }
                                .frame(height: 16)
                                Text("\(Critic.thresholds[i])").font(Theme.rounded(12, .black)).foregroundColor(Theme.brownSoft)
                                if s.claimed.contains(i) {
                                    SpriteImage(name: "icon_check", size: 20)
                                } else {
                                    SpriteImage(name: i == 4 ? "chest_gold" : (i >= 2 ? "chest_silver" : "chest_bronze"), size: 26)
                                        .modifier(Pulse(active: claimable))
                                }
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 5)
                            .background(InsetBackground(radius: 10, color: claimable ? Color(red: 1, green: 0.93, blue: 0.6) : Theme.cream))
                        }
                        .buttonStyle(PressScaleStyle())
                    }
                }
                Text(lang.t("critic.points.total", s.points))
                    .font(Theme.rounded(13, .heavy))
                    .foregroundColor(Theme.vip)
            }
        }
    }
}
