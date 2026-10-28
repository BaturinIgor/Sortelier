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

/// Плашки с содержимым награды, по 3 в ряд.
struct RewardChips: View {
    let reward: Reward
    var card: String?
    @EnvironmentObject private var lang: Lang

    var body: some View {
        let chips = makeChips()
        let rows = stride(from: 0, to: chips.count, by: 3).map { Array(chips[$0..<min($0 + 3, chips.count)]) }
        return VStack(spacing: 6) {
            ForEach(rows.indices, id: \.self) { r in
                HStack(spacing: 6) {
                    ForEach(rows[r].indices, id: \.self) { i in rows[r][i] }
                }
            }
        }
    }

    private func chip<Icon: View>(_ text: String, @ViewBuilder icon: () -> Icon) -> AnyView {
        AnyView(
            HStack(spacing: 4) {
                icon()
                Text(text)
                    .font(Theme.rounded(13, .heavy))
                    .foregroundColor(Theme.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
            .padding(.horizontal, 8)
            .frame(height: 28)
            .background(Capsule().fill(Theme.cream))
        )
    }

    private func makeChips() -> [AnyView] {
        var chips: [AnyView] = []
        if reward.coins > 0 {
            chips.append(chip("\(reward.coins)") { CoinIcon(size: 16) })
        }
        for (booster, n) in reward.boosterList {
            chips.append(chip("×\(n)") {
                Image(systemName: booster.symbol).font(.system(size: 12, weight: .bold)).foregroundColor(Theme.orange)
            })
        }
        if reward.unlimitedMinutes > 0 {
            chips.append(chip(Lang.duration(minutes: reward.unlimitedMinutes)) {
                Image(systemName: "heart.fill").font(.system(size: 12)).foregroundColor(Theme.red)
            })
        }
        if reward.lives > 0 {
            chips.append(chip("+\(reward.lives)") {
                Image(systemName: "heart.fill").font(.system(size: 12)).foregroundColor(Theme.red)
            })
        }
        if reward.energy > 0 {
            chips.append(chip("+\(reward.energy)") {
                Image(systemName: "bolt.fill").font(.system(size: 12)).foregroundColor(Theme.gold)
            })
        }
        if let card = card {
            chips.append(chip(lang.t("reward.card")) { GoldSprite(name: RareCards.sprite(card), size: 22) })
        } else if reward.rareCard {
            chips.append(chip(lang.t("reward.card")) {
                Image(systemName: "sparkles").font(.system(size: 12, weight: .bold)).foregroundColor(Theme.gold)
            })
        }
        if let bg = reward.background {
            chips.append(chip(lang.t("bg." + bg)) {
                Image(systemName: "photo.fill").font(.system(size: 12)).foregroundColor(Theme.green)
            })
        }
        return chips
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

/// Окно "Получено" после нажатия "Забрать".
struct RewardPopup: View {
    let title: String
    let granted: Granted
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var appear = false

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    if let card = granted.card {
                        GoldSprite(name: RareCards.sprite(card), size: 110)
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
                    if let card = granted.card {
                        Text(lang.t("reward.card.name", lang.t(Catalog.shared.dish(card) != nil ? "dish." + card : "item." + card)))
                            .font(Theme.rounded(15, .bold))
                            .foregroundColor(Theme.orange)
                    }
                    RewardChips(reward: granted.reward, card: granted.card)
                    Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle())
                }
                .frame(maxWidth: 300)
            }
        }
        .onAppear {
            Audio.shared.play(granted.card != nil ? .unlock : .chest)
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
    @State private var message: String?

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
                                    if progress.buyFreeze() { Audio.shared.play(.coin) } else { message = lang.t("common.nocoins") }
                                } label: {
                                    HStack { Text(lang.t("streak.freeze.buy")); CoinIcon(size: 20); Text("\(StreakRewards.freezePrice)") }
                                }
                                .buttonStyle(BigButtonStyle(color: Color(red: 0.3, green: 0.6, blue: 0.95)))
                            }
                            if let message = message {
                                Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
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
                HStack(spacing: 8) {
                    RewardChips(reward: ChallengeRewards.daily)
                    Text(lang.t("challenge.daily.card"))
                        .font(Theme.rounded(12, .bold))
                        .foregroundColor(Theme.brownSoft)
                }
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
                    ForEach(1...WelcomeQuests.days, id: \.self) { day in
                        dayBlock(day)
                    }
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
                    RewardChips(reward: WelcomeQuests.grand)
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
        let unlocked = day <= progress.welcomeDay
        return VStack(alignment: .leading, spacing: 8) {
            HStack {
                Text(lang.t("quests.day", day)).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
                Spacer()
                if !unlocked {
                    Label(lang.t("quests.in", day - progress.welcomeDay), systemImage: "lock.fill")
                        .font(Theme.rounded(13, .bold))
                        .foregroundColor(Theme.brownSoft)
                }
            }
            ForEach(quests) { q in questRow(q, unlocked: unlocked) }
        }
        .opacity(unlocked ? 1 : 0.6)
    }

    private func questRow(_ q: Quest, unlocked: Bool) -> some View {
        let value = progress.stat(q.stat)
        let claimed = progress.questClaimed(q)
        return MetaCard(highlight: progress.canClaim(q)) {
            VStack(alignment: .leading, spacing: 8) {
                Text(lang.t("task." + q.stat.rawValue, q.target))
                    .font(Theme.rounded(15, .heavy))
                    .foregroundColor(Theme.brown)
                HStack {
                    ProgressBar(value: value, target: q.target, color: claimed ? Theme.green : Theme.orange)
                    Text("\(min(value, q.target))/\(q.target)")
                        .font(Theme.rounded(12, .bold)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
                HStack {
                    RewardChips(reward: q.reward)
                    Spacer()
                    if claimed {
                        Image(systemName: "checkmark.seal.fill").font(.system(size: 22)).foregroundColor(Theme.green)
                    } else if progress.canClaim(q) {
                        Button(lang.t("common.claim")) {
                            grand = false
                            granted = progress.claim(q)
                        }
                        .font(Theme.rounded(15, .heavy))
                        .foregroundColor(.white)
                        .padding(.horizontal, 14)
                        .frame(height: 34)
                        .background(Capsule().fill(Theme.green))
                    }
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

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    SheetHeader(title: lang.t("ach.title"), subtitle: lang.t("ach.subtitle")) {
                        presentation.wrappedValue.dismiss()
                    }
                    ForEach(Achievements.all) { a in row(a) }
                }
                .padding(20)
            }
            if let granted = granted {
                RewardPopup(title: lang.t("common.received"), granted: granted) { self.granted = nil }
            }
        }
    }

    private func row(_ a: Achievement) -> some View {
        let tier = progress.claimedTiers(a)
        let value = progress.stat(a.stat)
        let complete = tier >= a.tiers.count
        let target = complete ? a.tiers.last ?? 1 : a.tiers[tier]
        return MetaCard(highlight: progress.canClaim(a)) {
            HStack(alignment: .top, spacing: 12) {
                Image(systemName: a.symbol)
                    .font(.system(size: 22, weight: .bold))
                    .foregroundColor(.white)
                    .frame(width: 46, height: 46)
                    .background(Circle().fill(complete ? Theme.gold : Theme.orange))
                VStack(alignment: .leading, spacing: 6) {
                    HStack {
                        Text(lang.t("ach." + a.id)).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                        Spacer()
                        HStack(spacing: 1) {
                            ForEach(0..<a.tiers.count, id: \.self) { i in
                                Image(systemName: "star.fill")
                                    .font(.system(size: 10))
                                    .foregroundColor(i < tier ? Theme.gold : Theme.brown.opacity(0.15))
                            }
                        }
                    }
                    Text(lang.t("task." + a.stat.rawValue, target))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                    HStack {
                        ProgressBar(value: value, target: target, color: complete ? Theme.gold : Theme.orange)
                        Text("\(min(value, target))/\(target)")
                            .font(Theme.rounded(12, .bold)).foregroundColor(Theme.brownSoft).monospacedDigit()
                    }
                    if !complete {
                        HStack {
                            RewardChips(reward: Achievements.reward(tier: tier))
                            Spacer()
                            if progress.canClaim(a) {
                                Button(lang.t("common.claim")) { granted = progress.claim(a) }
                                    .font(Theme.rounded(15, .heavy))
                                    .foregroundColor(.white)
                                    .padding(.horizontal, 14)
                                    .frame(height: 34)
                                    .background(Capsule().fill(Theme.green))
                            }
                        }
                    }
                }
            }
        }
    }
}

// MARK: - Фоны

struct BackgroundsSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @Environment(\.presentationMode) private var presentation
    @State private var message: String?

    private let columns = [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)]

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    SheetHeader(title: lang.t("bg.title"), subtitle: lang.t("bg.subtitle")) {
                        presentation.wrappedValue.dismiss()
                    }
                    if let message = message {
                        Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
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
                    message = nil
                } else {
                    message = lang.t("common.nocoins")
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
