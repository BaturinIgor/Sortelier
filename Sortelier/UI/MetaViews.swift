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

/// Содержимое награды плитками: значок сверху, подпись снизу (до двух строк, не обрезается).
/// Плитки идут рядами по perRow и стоят по центру доступной ширины.
struct RewardChips: View {
    let reward: Reward
    var card: String?
    var perRow = 3
    var tileWidth: CGFloat = 78
    /// Компактно: только значок и число (узкие карточки заказов кладовой).
    var compact = false
    @EnvironmentObject private var lang: Lang

    private struct Tile: Identifiable {
        let id: Int
        let view: AnyView
    }

    var body: some View {
        let tiles = makeTiles()
        let rows = stride(from: 0, to: tiles.count, by: max(1, perRow)).map { Array(tiles[$0..<min($0 + max(1, perRow), tiles.count)]) }
        return VStack(spacing: 6) {
            ForEach(rows.indices, id: \.self) { r in
                HStack(spacing: 6) {
                    ForEach(rows[r]) { tile in tile.view }
                }
            }
        }
        .frame(maxWidth: .infinity)
    }

    private func tile(_ id: Int, _ item: RewardItem, _ text: String) -> Tile {
        Tile(id: id, view: AnyView(
            Button { RewardInfo.show(item) } label: {
                VStack(spacing: 2) {
                    RewardItemIcon(item: item, size: compact ? 20 : 28).frame(height: compact ? 20 : 26)
                    if !text.isEmpty {
                        Text(text)
                            .font(Theme.rounded(compact ? 11 : 12, .heavy))
                            .foregroundColor(Theme.brown)
                            .multilineTextAlignment(.center)
                            .lineLimit(2)
                            .minimumScaleFactor(0.6)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .padding(.vertical, compact ? 3 : 6)
                .padding(.horizontal, 4)
                .frame(width: tileWidth)
                .frame(minHeight: compact ? 42 : 60)
                .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(Theme.cream))
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        ))
    }

    private func makeTiles() -> [Tile] {
        reward.items.enumerated().map { i, item in
            let text: String
            switch item {
            case let .coins(n): text = "\(n)"
            case let .booster(b, n): text = compact ? "×\(n)" : lang.t("booster." + b.rawValue) + " ×\(n)"
            case let .unlimited(m): text = compact ? Lang.durationShort(minutes: m) : Lang.duration(minutes: m)
            case let .lives(n): text = "+\(n)"
            case let .energy(n): text = "+\(n)"
            case let .chest(k, n): text = compact ? "×\(n)" : lang.t("chest.kind." + k.rawValue) + (n > 1 ? " ×\(n)" : "")
            case let .background(bg): text = compact ? "" : lang.t("bg." + bg)
            }
            return tile(i, item, text)
        }
    }
}

/// Строка в окне победы: значок, подпись и полученная награда.
struct RewardLine: View {
    let symbol: String
    let color: Color
    let title: String
    let granted: Granted?

    var body: some View {
        VStack(spacing: 4) {
            HStack(spacing: 6) {
                Image(systemName: symbol).font(.system(size: 15, weight: .bold)).foregroundColor(color)
                Text(title).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brown)
            }
            if let granted = granted, !granted.reward.isEmpty {
                RewardChips(reward: granted.reward, card: granted.card)
            }
        }
    }
}

/// Окно "Получено" после нажатия "Забрать". Если в награде сундуки, их можно открыть сразу.
struct RewardPopup: View {
    let title: String
    let granted: Granted
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var progress: PlayerProgress
    @State private var appear = false
    @State private var opening: ChestOpening?
    @State private var openedCount = 0

    private var chests: [ChestKind] {
        granted.reward.chestList.flatMap { Array(repeating: $0.0, count: $0.1) }
    }

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    if let chest = chests.first {
                        SpriteImage(name: chest.sprite, size: 110)
                            .scaleEffect(appear ? 1 : 0.4)
                    } else {
                        Image(systemName: "gift.fill")
                            .font(.system(size: 50, weight: .bold))
                            .foregroundColor(Theme.orange)
                            .scaleEffect(appear ? 1 : 0.4)
                    }
                    Text(title)
                        .font(Theme.rounded(22, .heavy))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                    RewardChips(reward: granted.reward)
                    if openedCount < chests.count && progress.chestCount(chests[openedCount]) > 0 {
                        Button(lang.t(openedCount == 0 ? "chest.open.now" : "chest.open.next")) {
                            if let result = progress.openChest(chests[openedCount]) {
                                openedCount += 1
                                withAnimation { opening = result }
                            }
                        }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                    }
                    Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle())
                }
                .frame(maxWidth: 300)
            }
            if let opening = opening {
                ChestOpenView(opening: opening) { withAnimation { self.opening = nil } }
                    .transition(.opacity)
            }
        }
        .onAppear {
            Audio.shared.play(.chest)
            Haptics.success()
            withAnimation(.spring(response: 0.4, dampingFraction: 0.5)) { appear = true }
        }
    }
}

/// Красная точка "есть что забрать".
struct BadgeDot: View {
    var body: some View {
        Circle()
            .fill(Theme.red)
            .frame(width: 12, height: 12)
            .overlay(Circle().stroke(Color.white, lineWidth: 2))
    }
}

/// Заголовок листа с кнопкой закрытия.
struct SheetHeader: View {
    let title: String
    var subtitle: String?
    let close: () -> Void

    var body: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(Theme.rounded(26, .heavy))
                    .foregroundColor(Theme.brown)
                if let subtitle = subtitle {
                    Text(subtitle)
                        .font(Theme.rounded(14, .semibold))
                        .foregroundColor(Theme.brownSoft)
                }
            }
            Spacer()
            CircleIconButton(symbol: "xmark", action: close)
        }
    }
}

/// Полоса прогресса задания.
struct ProgressBar: View {
    let value: Int
    let target: Int
    var color: Color = Theme.orange

    var body: some View {
        GeometryReader { geo in
            ZStack(alignment: .leading) {
                Capsule().fill(Theme.brown.opacity(0.12))
                Capsule().fill(color)
                    .frame(width: max(8, geo.size.width * CGFloat(min(1, Double(value) / Double(max(1, target))))))
            }
        }
        .frame(height: 10)
    }
}

/// Карточка-подложка в листах меты.
struct MetaCard<Content: View>: View {
    var highlight = false
    @ViewBuilder var content: Content

    var body: some View {
        content
            .padding(14)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: 18, style: .continuous)
                    .fill(Theme.card)
                    .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous)
                        .stroke(highlight ? Theme.orange : Theme.brown.opacity(0.08), lineWidth: highlight ? 2 : 1))
                    .shadow(color: Theme.brown.opacity(0.1), radius: 5, y: 2)
            )
    }
}

// MARK: - Стрик

struct StreakButton: View {
    let action: () -> Void
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        Button(action: action) {
            ZStack(alignment: .topTrailing) {
                Pill(text: "\(progress.streakDay)") {
                    Image(systemName: "flame.fill")
                        .font(.system(size: 20))
                        .foregroundColor(progress.playedToday ? Theme.orange : Theme.brownSoft)
                }
                if progress.streakAtRisk { BadgeDot().offset(x: 4, y: -4) }
            }
        }
        .buttonStyle(.plain)
    }
}

struct StreakSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    SheetHeader(title: lang.t("streak.title"), subtitle: lang.t("streak.subtitle")) {
                        presentation.wrappedValue.dismiss()
                    }
                    MetaCard(highlight: progress.streakAtRisk) {
                        HStack(spacing: 14) {
                            Image(systemName: "flame.fill")
                                .font(.system(size: 44))
                                .foregroundColor(Theme.orange)
                            VStack(alignment: .leading, spacing: 4) {
                                Text(lang.t("streak.day", progress.streakDay))
                                    .font(Theme.rounded(22, .heavy))
                                    .foregroundColor(Theme.brown)
                                Text(status)
                                    .font(Theme.rounded(14, .semibold))
                                    .foregroundColor(progress.streakAtRisk ? Theme.red : Theme.brownSoft)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                        }
                    }
                    days
                    MetaCard {
                        VStack(alignment: .leading, spacing: 10) {
                            HStack {
                                Image(systemName: "snowflake").foregroundColor(Color(red: 0.3, green: 0.6, blue: 0.95))
                                Text(lang.t("streak.freezes", progress.streakFreezes, StreakRewards.maxFreezes))
                                    .font(Theme.rounded(16, .heavy))
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
                                    HStack { Text(lang.t("streak.freeze.buy")); CoinIcon(size: 20); Text("\(StreakRewards.freezePrice)") }
                                }
                                .buttonStyle(BigButtonStyle(color: Color(red: 0.3, green: 0.6, blue: 0.95)))
                            }
                        }
                    }
                }
                .padding(20)
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
        return HStack(spacing: 6) {
            ForEach(1...7, id: \.self) { d in
                VStack(spacing: 4) {
                    Text(lang.t("streak.short", d))
                        .font(Theme.rounded(11, .heavy))
                        .foregroundColor(Theme.brownSoft)
                    ZStack {
                        Circle()
                            .fill(dayDone(d, current) ? Theme.orange : Theme.card)
                            .frame(width: 40, height: 40)
                            .overlay(Circle().stroke(d == next && !progress.playedToday ? Theme.orange : Theme.brown.opacity(0.12),
                                                     lineWidth: 2))
                        if d == 7 {
                            Image(systemName: "sparkles")
                                .font(.system(size: 16, weight: .bold))
                                .foregroundColor(dayDone(d, current) ? .white : Theme.gold)
                        } else if dayDone(d, current) {
                            Image(systemName: "checkmark").font(.system(size: 15, weight: .heavy)).foregroundColor(.white)
                        }
                    }
                    Text("\(StreakRewards.coins[d - 1])")
                        .font(Theme.rounded(11, .heavy))
                        .foregroundColor(Theme.brown)
                }
                .frame(maxWidth: .infinity)
            }
        }
    }

    private func dayDone(_ d: Int, _ current: Int) -> Bool { d <= current && current > 0 }
}

// MARK: - Испытания

struct ChallengesSheet: View {
    /// Выбранный уровень: карта запустит его после закрытия листа.
    @Binding var launch: LevelLaunch?
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var granted: Granted?

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    SheetHeader(title: lang.t("challenge.title"), subtitle: lang.t("challenge.subtitle")) {
                        presentation.wrappedValue.dismiss()
                    }
                    dailyCard
                    weeklyCard
                    medalCard
                }
                .padding(20)
            }
            if let granted = granted {
                RewardPopup(title: lang.t("medal.title"), granted: granted) { self.granted = nil }
            }
        }
    }

    private var dailyCard: some View {
        let done = progress.dailyDone()
        return MetaCard(highlight: !done) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: "calendar").foregroundColor(Theme.orange)
                    Text(lang.t("challenge.daily.title")).font(Theme.rounded(19, .heavy)).foregroundColor(Theme.brown)
                    Spacer()
                    Text(Lang.time(Day.secondsToMidnight(progress.now)))
                        .font(Theme.rounded(13, .bold)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
                Text(lang.t("challenge.daily.text"))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                RewardChips(reward: ChallengeRewards.daily)
                if done {
                    Label(lang.t("challenge.done"), systemImage: "checkmark.seal.fill")
                        .font(Theme.rounded(16, .heavy))
                        .foregroundColor(Theme.green)
                } else if let level = ChallengeStore.shared.dailyLevel() {
                    Button(lang.t("challenge.play")) {
                        launch = LevelLaunch(level: level, mode: .daily(Day.key()))
                        presentation.wrappedValue.dismiss()
                    }
                    .buttonStyle(BigButtonStyle())
                }
            }
        }
    }

    private var weeklyCard: some View {
        let week = Day.weekKey()
        let done = progress.weeklyDone(week)
        let set = ChallengeStore.shared.weeklySet()
        return MetaCard(highlight: done < 3) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: "calendar.badge.clock").foregroundColor(Theme.orange)
                    Text(lang.t("challenge.weekly.title")).font(Theme.rounded(19, .heavy)).foregroundColor(Theme.brown)
                    Spacer()
                    Text(Lang.time(Day.secondsToWeekEnd(progress.now)))
                        .font(Theme.rounded(13, .bold)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
                if let set = set {
                    Text(lang.t("rule." + set.rule + ".title"))
                        .font(Theme.rounded(15, .heavy))
                        .foregroundColor(Theme.orange)
                    Text(lang.t("rule." + set.rule + ".text"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack(spacing: 8) {
                    ForEach(0..<3, id: \.self) { i in
                        Capsule()
                            .fill(i < done ? Theme.green : Theme.brown.opacity(0.12))
                            .frame(height: 10)
                    }
                }
                RewardChips(reward: ChallengeRewards.weekly)
                if done >= 3 {
                    Label(lang.t("challenge.done"), systemImage: "checkmark.seal.fill")
                        .font(Theme.rounded(16, .heavy))
                        .foregroundColor(Theme.green)
                } else if let set = set, set.levels.count > done {
                    Button(lang.t("challenge.weekly.play", done + 1)) {
                        launch = LevelLaunch(level: set.levels[done], mode: .weekly(week, done))
                        presentation.wrappedValue.dismiss()
                    }
                    .buttonStyle(BigButtonStyle())
                }
            }
        }
    }

    private var medalCard: some View {
        let p = progress.medalProgress()
        let ready = progress.medalReady()
        let claimed = progress.medalClaimed()
        return MetaCard(highlight: ready) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: "rosette").foregroundColor(Theme.gold)
                    Text(lang.t("medal.title")).font(Theme.rounded(19, .heavy)).foregroundColor(Theme.brown)
                }
                Text(lang.t("medal.text", ChallengeRewards.medalDaily, ChallengeRewards.medalWeekly))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                HStack {
                    Text(lang.t("medal.daily", min(p.daily, ChallengeRewards.medalDaily), ChallengeRewards.medalDaily))
                        .font(Theme.rounded(13, .bold)).foregroundColor(Theme.brown)
                    ProgressBar(value: p.daily, target: ChallengeRewards.medalDaily)
                }
                HStack {
                    Text(lang.t("medal.weekly", min(p.weekly, ChallengeRewards.medalWeekly), ChallengeRewards.medalWeekly))
                        .font(Theme.rounded(13, .bold)).foregroundColor(Theme.brown)
                    ProgressBar(value: p.weekly, target: ChallengeRewards.medalWeekly)
                }
                RewardChips(reward: ChallengeRewards.medal)
                if claimed {
                    Label(lang.t("challenge.done"), systemImage: "checkmark.seal.fill")
                        .font(Theme.rounded(16, .heavy))
                        .foregroundColor(Theme.green)
                } else if ready {
                    Button(lang.t("common.claim")) { granted = progress.claimMedal() }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                }
            }
        }
    }
}

// MARK: - Задания новичка

struct QuestsSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var granted: Granted?
    @State private var grand = false
    @State private var day = min(max(1, PlayerProgress.shared.welcomeDay), WelcomeQuests.days)

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    SheetHeader(title: lang.t("quests.title"),
                                subtitle: lang.t("quests.subtitle", min(progress.welcomeDay, WelcomeQuests.days), WelcomeQuests.days)) {
                        presentation.wrappedValue.dismiss()
                    }
                    grandCard
                    dayTabs
                    dayBlock(day)
                }
                .padding(20)
            }
            if let granted = granted {
                RewardPopup(title: lang.t(grand ? "quests.grand.title" : "common.received"), granted: granted) {
                    self.granted = nil
                }
            }
        }
    }

    private enum DayState { case locked, open, done }

    private func state(_ d: Int) -> DayState {
        if d > progress.welcomeDay { return .locked }
        let quests = WelcomeQuests.all.filter { $0.day == d }
        return quests.allSatisfy { progress.questClaimed($0) } ? .done : .open
    }

    /// Табы дней: будущие серые с замком и не открываются, закрытые зеленые.
    private var dayTabs: some View {
        HStack(spacing: 6) {
            ForEach(1...WelcomeQuests.days, id: \.self) { d in
                let st = state(d)
                let claimable = WelcomeQuests.all.contains { $0.day == d && progress.canClaim($0) }
                Button {
                    guard st != .locked else {
                        Toast.info(lang.t("quests.in", d - progress.welcomeDay), icon: "lock.fill")
                        return
                    }
                    withAnimation(.easeOut(duration: 0.15)) { day = d }
                } label: {
                    VStack(spacing: 2) {
                        Text(lang.t("streak.short", d))
                            .font(Theme.rounded(11, .heavy))
                        Group {
                            switch st {
                            case .locked: Image(systemName: "lock.fill")
                            case .done: Image(systemName: "checkmark")
                            case .open: Text("\(d)")
                            }
                        }
                        .font(.system(size: 15, weight: .heavy, design: .rounded))
                    }
                    .foregroundColor(st == .locked ? Theme.brownSoft.opacity(0.6) : (st == .done || day == d ? .white : Theme.brown))
                    .frame(maxWidth: .infinity)
                    .frame(height: 52)
                    .background(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .fill(tabColor(st, selected: day == d))
                    )
                    .overlay(
                        RoundedRectangle(cornerRadius: 12, style: .continuous)
                            .stroke(day == d ? Theme.brown.opacity(0.5) : Color.clear, lineWidth: 2)
                    )
                    .overlay(alignment: .topTrailing) {
                        if claimable { BadgeDot().offset(x: 3, y: -3) }
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func tabColor(_ st: DayState, selected: Bool) -> Color {
        switch st {
        case .locked: return Theme.brown.opacity(0.08)
        case .done: return Theme.green
        case .open: return selected ? Theme.orange : Theme.card
        }
    }

    private var grandCard: some View {
        let done = WelcomeQuests.all.filter { progress.questClaimed($0) }.count
        return MetaCard(highlight: progress.welcomeGrandReady) {
            HStack(spacing: 12) {
                Image(uiImage: Art.image(KitchenStyle.image("diner")))
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(width: 70, height: 110)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                VStack(alignment: .leading, spacing: 8) {
                    Text(lang.t("quests.grand")).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
                    RewardChips(reward: WelcomeQuests.grand, perRow: 3, tileWidth: 66)
                    ProgressBar(value: done, target: WelcomeQuests.all.count, color: Theme.green)
                    Text("\(done) / \(WelcomeQuests.all.count)")
                        .font(Theme.rounded(12, .bold)).foregroundColor(Theme.brownSoft)
                    if progress.welcomeGrandReady {
                        Button(lang.t("common.claim")) {
                            grand = true
                            granted = progress.claimWelcomeGrand()
                        }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                    }
                }
            }
        }
    }

    private func dayBlock(_ day: Int) -> some View {
        let quests = WelcomeQuests.all.filter { $0.day == day }
        return VStack(alignment: .leading, spacing: 8) {
            Text(lang.t("quests.day", day)).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
            ForEach(quests) { q in questRow(q) }
        }
    }

    private func questRow(_ q: Quest) -> some View {
        let value = progress.stat(q.stat)
        let claimed = progress.questClaimed(q)
        return MetaCard(highlight: progress.canClaim(q)) {
            VStack(alignment: .leading, spacing: 8) {
                HStack {
                    Text(lang.t("task." + q.stat.rawValue, q.target))
                        .font(Theme.rounded(15, .heavy))
                        .foregroundColor(Theme.brown)
                    Spacer()
                    if claimed {
                        Image(systemName: "checkmark.seal.fill").font(.system(size: 22)).foregroundColor(Theme.green)
                    }
                }
                HStack {
                    ProgressBar(value: value, target: q.target, color: claimed ? Theme.green : Theme.orange)
                    Text("\(min(value, q.target))/\(q.target)")
                        .font(Theme.rounded(12, .bold)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
                RewardChips(reward: q.reward)
                if progress.canClaim(q) {
                    Button(lang.t("common.claim")) {
                        grand = false
                        granted = progress.claim(q)
                    }
                    .buttonStyle(BigButtonStyle(color: Theme.green))
                }
            }
        }
    }
}

// MARK: - Ачивки

struct AchievementsSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var granted: Granted?
    @State private var category: Achievement.Category = .kitchen
    /// Порядок карточек замораживается, пока открыто окно награды: после закрытия карточка плавно уезжает на место.
    @State private var frozen: [String]?

    private var shown: [Achievement] {
        let sorted = progress.sortedAchievements(category)
        guard let frozen = frozen else { return sorted }
        let rest = sorted.filter { !frozen.contains($0.id) }
        return frozen.compactMap { id in sorted.first { $0.id == id } } + rest
    }

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    SheetHeader(title: lang.t("ach.title"), subtitle: lang.t("ach.subtitle")) {
                        presentation.wrappedValue.dismiss()
                    }
                    starTrack
                    categoryTabs
                    ForEach(shown) { a in row(a) }
                }
                .padding(20)
            }
            if let granted = granted {
                RewardPopup(title: lang.t("common.received"), granted: granted) {
                    self.granted = nil
                    withAnimation(.spring(response: 0.55, dampingFraction: 0.85)) { frozen = nil }
                }
            }
        }
    }

    // MARK: Звезды ачивок и шкала наград

    private var starTrack: some View {
        let stars = progress.achievementStars
        return MetaCard(highlight: AchievementTrack.milestones.contains { progress.canClaimMilestone($0) }) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    Image(systemName: "star.circle.fill").font(.system(size: 28)).foregroundColor(Theme.gold)
                    VStack(alignment: .leading, spacing: 0) {
                        Text(lang.t("achv.total", stars, Achievements.maxStars))
                            .font(Theme.rounded(18, .heavy))
                            .foregroundColor(Theme.brown)
                        Text(lang.t("achv.total.text"))
                            .font(Theme.rounded(12, .semibold))
                            .foregroundColor(Theme.brownSoft)
                    }
                }
                ScrollViewReader { proxy in
                    ScrollView(.horizontal, showsIndicators: false) {
                        HStack(alignment: .top, spacing: 8) {
                            ForEach(AchievementTrack.milestones) { m in milestoneCell(m, stars: stars).id(m.stars) }
                        }
                        .padding(.vertical, 4)
                    }
                    .onAppear {
                        let next = AchievementTrack.milestones.first { !progress.milestoneClaimed($0) }
                        if let next = next { proxy.scrollTo(next.stars, anchor: .center) }
                    }
                }
            }
        }
    }

    private func milestoneCell(_ m: AchievementTrack.Milestone, stars: Int) -> some View {
        let reached = stars >= m.stars
        let claimed = progress.milestoneClaimed(m)
        return VStack(spacing: 6) {
            HStack(spacing: 3) {
                Image(systemName: "star.fill").font(.system(size: 12)).foregroundColor(reached ? Theme.gold : Theme.brownSoft)
                Text("\(m.stars)").font(Theme.rounded(14, .heavy)).foregroundColor(reached ? Theme.brown : Theme.brownSoft)
            }
            RewardChips(reward: m.reward, perRow: 1, tileWidth: 92)
            Group {
                if claimed {
                    Image(systemName: "checkmark.circle.fill").foregroundColor(Theme.green)
                } else if reached {
                    Button(lang.t("common.claim")) { granted = progress.claimMilestone(m) }
                        .font(Theme.rounded(12, .heavy))
                        .foregroundColor(.white)
                        .padding(.horizontal, 10)
                        .frame(height: 26)
                        .background(Capsule().fill(Theme.green))
                } else {
                    Image(systemName: "lock.fill").foregroundColor(Theme.brownSoft.opacity(0.6))
                }
            }
            .frame(height: 26)
        }
        .frame(width: 100)
        .padding(.vertical, 6)
        .background(RoundedRectangle(cornerRadius: 12).fill(reached ? Theme.gold.opacity(0.16) : Theme.cream.opacity(0.7)))
    }

    // MARK: Категории

    private var categoryTabs: some View {
        HStack(spacing: 6) {
            ForEach(Achievement.Category.allCases, id: \.self) { c in
                let claimable = Achievements.all.contains { $0.category == c && progress.canClaim($0) }
                Button { withAnimation(.easeOut(duration: 0.15)) { category = c; frozen = nil } } label: {
                    VStack(spacing: 2) {
                        Image(systemName: symbol(c)).font(.system(size: 16, weight: .bold))
                        Text(lang.t("ach.cat." + c.rawValue))
                            .font(Theme.rounded(11, .heavy))
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                    }
                    .foregroundColor(category == c ? .white : Theme.brownSoft)
                    .frame(maxWidth: .infinity)
                    .frame(height: 50)
                    .background(RoundedRectangle(cornerRadius: 12, style: .continuous).fill(category == c ? Theme.orange : Theme.card))
                    .overlay(alignment: .topTrailing) {
                        if claimable { BadgeDot().offset(x: 3, y: -3) }
                    }
                }
                .buttonStyle(.plain)
            }
        }
    }

    private func symbol(_ c: Achievement.Category) -> String {
        switch c {
        case .kitchen: return "fork.knife"
        case .habits: return "calendar"
        case .collection: return "books.vertical.fill"
        case .pantry: return "square.grid.3x3.fill"
        }
    }

    private func row(_ a: Achievement) -> some View {
        let tier = progress.claimedTiers(a)
        let value = progress.stat(a.stat)
        let complete = tier >= a.tiers.count
        let target = complete ? a.tiers.last ?? 1 : a.tiers[tier]
        return MetaCard(highlight: progress.canClaim(a)) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 12) {
                    Image(systemName: a.symbol)
                        .font(.system(size: 20, weight: .bold))
                        .foregroundColor(.white)
                        .frame(width: 44, height: 44)
                        .background(Circle().fill(complete ? Theme.gold : Theme.orange))
                    VStack(alignment: .leading, spacing: 3) {
                        Text(lang.t("ach." + a.id)).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                        HStack(spacing: 2) {
                            ForEach(0..<a.tiers.count, id: \.self) { i in
                                Image(systemName: "star.fill")
                                    .font(.system(size: 12))
                                    .foregroundColor(i < tier ? Theme.gold : Theme.brown.opacity(0.15))
                            }
                        }
                    }
                    Spacer(minLength: 0)
                }
                Text(lang.t("task." + a.stat.rawValue, target))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 8) {
                    ProgressBar(value: value, target: target, color: complete ? Theme.gold : Theme.orange)
                    Text("\(min(value, target))/\(target)")
                        .font(Theme.rounded(13, .bold)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
                if !complete {
                    RewardChips(reward: Achievements.reward(tier: tier), perRow: 4, tileWidth: 72)
                    if progress.canClaim(a) {
                        Button(lang.t("common.claim")) {
                            frozen = shown.map(\.id)
                            granted = progress.claim(a)
                        }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                    }
                }
            }
        }
        .id(a.id)
    }
}

// MARK: - Фоны

struct BackgroundsSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation

    private let columns = [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)]

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    SheetHeader(title: lang.t("bg.title"), subtitle: lang.t("bg.subtitle")) {
                        presentation.wrappedValue.dismiss()
                    }
                    LazyVGrid(columns: columns, spacing: 12) {
                        ForEach(KitchenStyle.all) { style in tile(style) }
                    }
                }
                .padding(20)
            }
        }
    }

    private func tile(_ style: KitchenStyle) -> some View {
        let owned = progress.owns(style)
        let equipped = progress.background == style.id
        return VStack(spacing: 8) {
            Image(uiImage: Art.image(KitchenStyle.image(style.id)))
                .resizable()
                .aspectRatio(contentMode: .fill)
                .frame(height: 190)
                .frame(maxWidth: .infinity)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous)
                    .stroke(equipped ? Theme.orange : Color.clear, lineWidth: 3))
            Text(lang.t("bg." + style.id)).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brown)
            action(style, owned: owned, equipped: equipped)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 18, style: .continuous).fill(Theme.card))
    }

    @ViewBuilder
    private func action(_ style: KitchenStyle, owned: Bool, equipped: Bool) -> some View {
        if equipped {
            Label(lang.t("bg.equipped"), systemImage: "checkmark.circle.fill")
                .font(Theme.rounded(13, .heavy))
                .foregroundColor(Theme.green)
                .frame(height: 34)
        } else if owned {
            smallButton(lang.t("bg.equip"), Theme.orange) { progress.equip(style) }
        } else if style.source == .shop {
            Button {
                if progress.buy(style) {
                    Audio.shared.play(.chest)
                    Toast.success(lang.t("bg.bought"))
                } else {
                    Toast.error(lang.t("common.nocoins"))
                }
            } label: {
                HStack(spacing: 4) { CoinIcon(size: 18); Text("\(style.price)") }
                    .font(Theme.rounded(15, .heavy))
                    .foregroundColor(.white)
                    .padding(.horizontal, 14)
                    .frame(height: 34)
                    .background(Capsule().fill(Theme.green))
            }
            .buttonStyle(.plain)
        } else {
            Text(lang.t("bg.source." + sourceKey(style)))
                .font(Theme.rounded(12, .bold))
                .foregroundColor(Theme.brownSoft)
                .multilineTextAlignment(.center)
                .frame(height: 34)
        }
    }

    private func sourceKey(_ style: KitchenStyle) -> String {
        switch style.source {
        case .free: return "free"
        case .shop: return "shop"
        case .welcome: return "welcome"
        case .event: return "event"
        case .gourmet: return "gourmet"
        case .biome: return style.id
        }
    }

    private func smallButton(_ title: String, _ color: Color, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(Theme.rounded(15, .heavy))
                .foregroundColor(.white)
                .padding(.horizontal, 14)
                .frame(height: 34)
                .background(Capsule().fill(color))
        }
        .buttonStyle(.plain)
    }
}
