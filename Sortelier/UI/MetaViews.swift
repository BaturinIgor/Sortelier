import SwiftUI

// MARK: - Награды

/// Спрайт в золоте: редкие карточки.
struct GoldSprite: View {
    let name: String
    var size: CGFloat = 60

    var body: some View {
        let image = Image(uiImage: Art.image(name)).resizable().aspectRatio(contentMode: .fit)
        return image
            .saturation(0)
            .brightness(0.06)
            .colorMultiply(Color(red: 1.0, green: 0.80, blue: 0.30))
            .overlay(
                LinearGradient(colors: [Color.white.opacity(0), Color.white.opacity(0.6), Color.white.opacity(0)],
                               startPoint: .topLeading, endPoint: .bottomTrailing)
                    .mask(image)
            )
            .frame(width: size, height: size)
    }
}

/// Строка в окне победы: значок, подпись и полученная награда.
struct RewardLine: View {
    let symbol: String
    let color: Color
    let title: String
    let granted: Granted?

    var body: some View {
        VStack(spacing: 6) {
            HStack(spacing: 6) {
                if symbol == "coin_icon" {
                    CoinIcon(size: 22)
                } else if symbol.hasPrefix("icon_") {
                    SpriteImage(name: symbol, size: 24)
                } else if let sprite = GameIcon.sprite(for: symbol) {
                    SpriteImage(name: sprite, size: 24)
                } else {
                    Image(systemName: symbol).font(.system(size: 15, weight: .bold)).foregroundColor(color)
                }
                Text(title).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brown)
            }
            if let granted = granted, !granted.reward.isEmpty {
                RewardChips(reward: granted.reward, card: granted.card, perRow: 4, tileWidth: 56)
            }
        }
    }
}

/// Плашка "Получено" сразу после нажатия "Забрать": выезжает сверху, сама прячется через пару секунд
/// и не мешает нажимать дальше. Тап или свайп вверх убирает ее сразу. Если в награде сундуки,
/// на плашке есть кнопка открыть их, и тогда она держится чуть дольше.
struct RewardPopup: View {
    let title: String
    let granted: Granted
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress
    @State private var shown = false
    @State private var closing = false

    static let duration: TimeInterval = 2.6
    static let chestDuration: TimeInterval = 4.5

    private var chests: [ChestKind] {
        granted.reward.chestList.flatMap { Array(repeating: $0.0, count: $0.1) }
    }

    var body: some View {
        let items = granted.reward.items
        let shownItems = Array(items.prefix(items.count > 5 ? 4 : 5))
        let rest = items.count - shownItems.count
        let openable = chests.filter { progress.chestCount($0) > 0 }
        VStack(spacing: 8) {
            HStack(spacing: 8) {
                SpriteImage(name: chests.first?.sprite ?? "icon_gift", size: 34)
                Text(title)
                    .font(Theme.rounded(16, .black))
                    .foregroundColor(Theme.brown)
                    .lineLimit(2)
                    .minimumScaleFactor(0.7)
                Spacer(minLength: 0)
            }
            if !shownItems.isEmpty {
                HStack(spacing: 6) {
                    ForEach(shownItems) { item in RewardTile(item: item, size: 46) }
                    if rest > 0 {
                        Text("+\(rest)").font(Theme.rounded(15, .black)).foregroundColor(Theme.brownSoft)
                    }
                }
                .frame(maxWidth: .infinity)
            }
            if !openable.isEmpty {
                Button(lang.t("chest.open.now")) {
                    let queue = openable
                    dismiss()
                    // сундуки открываются по очереди: следующий после закрытия предыдущего
                    DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { RewardPopup.open(queue) }
                }
                .buttonStyle(GameButtonStyle(palette: .orange, height: 40, fontSize: 16))
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .frame(maxWidth: 360)
        .background(PaperBackground(radius: 18, highlight: true))
        .contentShape(Rectangle())
        .onTapGesture(perform: dismiss)
        .gesture(DragGesture(minimumDistance: 10).onEnded { if $0.translation.height < -10 { dismiss() } })
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("reward.banner")
        .padding(.horizontal, 16)
        .padding(.top, 6)
        .offset(y: shown ? 0 : -220)
        .opacity(shown ? 1 : 0)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .top)
        // ожидание заново на каждую новую награду: две подряд не закроют друг друга раньше времени
        .task(id: granted) {
            closing = false
            Audio.shared.play(.chest)
            Haptics.success()
            withAnimation(.spring(response: 0.38, dampingFraction: 0.72)) { shown = true }
            let wait = chests.isEmpty ? RewardPopup.duration : RewardPopup.chestDuration
            try? await Task.sleep(nanoseconds: UInt64(wait * 1_000_000_000))
            if !Task.isCancelled { dismiss() }
        }
    }

    private func dismiss() {
        guard !closing else { return }
        closing = true
        withAnimation(.easeIn(duration: 0.22)) { shown = false }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.24) { close() }
    }

    static func open(_ queue: [ChestKind]) {
        guard let first = queue.first else { return }
        ChestOpener.present(first, onClose: {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.35) { open(Array(queue.dropFirst())) }
        })
    }
}

/// Красная точка "есть что забрать".
struct BadgeDot: View {
    var body: some View {
        Circle()
            .fill(LinearGradient(colors: [ButtonPalette.red.top, ButtonPalette.red.bottom], startPoint: .top, endPoint: .bottom))
            .frame(width: 16, height: 16)
            .overlay(Circle().strokeBorder(Color.white, lineWidth: 2.5))
            .shadow(color: Theme.ribbonDark.opacity(0.6), radius: 0, y: 1.5)
    }
}

/// Заголовок с подзаголовком внутри экрана.
struct SheetHeader: View {
    let title: String
    var subtitle: String?
    let close: () -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(title).font(Theme.rounded(24, .black)).foregroundColor(Theme.brown)
            if let subtitle = subtitle {
                Text(subtitle).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.brownSoft)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

/// Полоса прогресса: утопленная темная дорожка и глянцевая заливка.
struct ProgressBar: View {
    let value: Int
    let target: Int
    var color: Color = Theme.orange
    var height: CGFloat = 14

    var body: some View {
        GeometryReader { geo in
            let share = CGFloat(min(1, Double(value) / Double(max(1, target))))
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.woodDark.opacity(0.75))
                Capsule().fill(Color.black.opacity(0.25)).padding(.top, height * 0.45)
                if share > 0 {
                    Capsule()
                        .fill(LinearGradient(colors: [color.opacity(0.75), color], startPoint: .top, endPoint: .bottom))
                        .overlay(Capsule().fill(Color.white.opacity(0.3)).frame(height: height * 0.28).padding(.horizontal, 4)
                            .frame(maxHeight: .infinity, alignment: .top).padding(.top, 2))
                        .frame(width: max(height, (geo.size.width - 4) * share))
                        .padding(2)
                }
            }
        }
        .frame(height: height)
    }
}

/// Карточка на бумаге в списках меты.
struct MetaCard<Content: View>: View {
    var highlight = false
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(PaperBackground(radius: 18, highlight: highlight))
    }
}

/// Заголовок карточки: иконка, название и таймер справа.
struct CardTitle: View {
    let icon: String
    let title: String
    var timer: String?

    var body: some View {
        HStack(spacing: 8) {
            SpriteImage(name: icon, size: 34)
            Text(title)
                .font(Theme.rounded(19, .black))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Spacer(minLength: 4)
            if let timer = timer { TimerBadge(text: timer) }
        }
    }
}

/// Отметка "выполнено": зеленая галочка и текст.
struct DoneLabel: View {
    let text: String

    var body: some View {
        HStack(spacing: 6) {
            SpriteImage(name: "icon_check", size: 26)
            Text(text).font(Theme.rounded(16, .black)).foregroundColor(Theme.green)
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 4)
    }
}

// MARK: - Стрик

struct StreakButton: View {
    let action: () -> Void
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        Button(action: action) {
            Pill(text: "\(progress.streakDay)") {
                SpriteImage(name: "icon_flame", size: 30)
                    .saturation(progress.playedToday ? 1 : 0.2)
            }
            .overlay(alignment: .topTrailing) {
                if progress.streakAtRisk { BadgeDot().offset(x: 4, y: -4) }
            }
        }
        .buttonStyle(PressScaleStyle())
    }
}

/// Окно стрика: день серии, 7 дней с наградами и заморозки.
struct StreakPopup: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("streak.title"), close: close, maxWidth: 360) {
                VStack(spacing: 14) {
                    HStack(spacing: 12) {
                        SpriteImage(name: "icon_flame", size: 64)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(lang.t("streak.day", progress.streakDay))
                                .font(Theme.rounded(22, .black))
                                .foregroundColor(Theme.brown)
                            Text(status)
                                .font(Theme.rounded(14, .semibold))
                                .foregroundColor(progress.streakAtRisk ? Theme.red : Theme.brownSoft)
                                .fixedSize(horizontal: false, vertical: true)
                        }
                        Spacer(minLength: 0)
                    }
                    days
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 8) {
                            SpriteImage(name: "icon_snowflake", size: 30)
                            Text(lang.t("streak.freezes", progress.streakFreezes, StreakRewards.maxFreezes))
                                .font(Theme.rounded(16, .black))
                                .foregroundColor(Theme.brown)
                        }
                        Text(lang.t("streak.freeze.text"))
                            .font(Theme.rounded(13, .semibold))
                            .foregroundColor(Theme.brownSoft)
                            .fixedSize(horizontal: false, vertical: true)
                        if progress.streakFreezes < StreakRewards.maxFreezes {
                            Button {
                                if progress.buyFreeze() { Audio.shared.play(.coin) } else { Toast.error(lang.t("common.nocoins")) }
                            } label: {
                                HStack(spacing: 6) { Text(lang.t("streak.freeze.buy")); CoinIcon(size: 24); Text("\(StreakRewards.freezePrice)") }
                            }
                            .buttonStyle(GameButtonStyle(palette: .blue, height: 46, fontSize: 18))
                        }
                    }
                    .padding(12)
                    .background(InsetBackground())
                }
            }
        }
    }

    private var status: String {
        if progress.playedToday { return lang.t("streak.done") }
        if progress.streakDay > 0 { return lang.t("streak.risk") }
        return lang.t("streak.start")
    }

    private var days: some View {
        let current = progress.streakDay
        let next = progress.playedToday ? current : current % 7 + 1
        // неделя закрыта, а сегодня еще не играли: начинается новый круг, старые галочки не показываем
        let filled = !progress.playedToday && current == 7 ? 0 : current
        return HStack(spacing: 4) {
            ForEach(1...7, id: \.self) { d in
                let done = d <= filled
                let isNext = d == next && !progress.playedToday
                VStack(spacing: 3) {
                    Text(lang.t("streak.short", d))
                        .font(Theme.rounded(11, .black))
                        .foregroundColor(Theme.brownSoft)
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                    ZStack {
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .fill(done ? Color(red: 1.0, green: 0.78, blue: 0.4) : Theme.cream)
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .strokeBorder(isNext ? Theme.orange : Theme.chipBorder, lineWidth: isNext ? 3 : 2)
                        if done {
                            SpriteImage(name: "icon_check", size: 24)
                        } else if d == 7 {
                            SpriteImage(name: "chest_silver", size: 32)
                        } else {
                            CoinIcon(size: 22)
                        }
                    }
                    .frame(height: 42)
                    Text("\(StreakRewards.coins[d - 1])")
                        .font(Theme.rounded(11, .black))
                        .foregroundColor(Theme.brown)
                }
                .frame(maxWidth: .infinity)
            }
        }
    }
}

/// Подсказка при первом заходе в раздел: что здесь и зачем. Закрывается кнопкой и больше не показывается.
struct ScreenTip: View {
    /// Ключ раздела: текст берется из tip.<id>, отметка о показе - в seenIntros как tip.<id>.
    let id: String
    let icon: String
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        if !progress.seenIntro("tip." + id) {
            HStack(alignment: .center, spacing: 12) {
                SpriteImage(name: icon, size: 40)
                Text(lang.t("tip." + id))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brown)
                    .fixedSize(horizontal: false, vertical: true)
                    .frame(maxWidth: .infinity, alignment: .leading)
                Button(lang.t("tip.ok")) {
                    withAnimation(.easeOut(duration: 0.2)) { progress.markIntro("tip." + id) }
                }
                .buttonStyle(GameButtonStyle(palette: .green, height: 36, fontSize: 15, fullWidth: false, radius: 12))
                .fixedSize()
            }
            .padding(12)
            .background(InsetBackground(radius: 16, color: Color(red: 1.0, green: 0.93, blue: 0.7)))
            .transition(.opacity.combined(with: .move(edge: .top)))
            .accessibilityIdentifier("tip." + id)
        }
    }
}
