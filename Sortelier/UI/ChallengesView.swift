import SwiftUI

// MARK: - Испытания

/// Испытание дня, недели и медаль месяца.
struct ChallengesContent: View {
    let play: (LevelData, PlayMode) -> Void
    @Binding var granted: Granted?
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        VStack(spacing: 14) {
            dailyCard
            weeklyCard
            medalCard
        }
    }

    private var dailyCard: some View {
        let done = progress.dailyDone()
        return MetaCard(highlight: !done) {
            VStack(alignment: .leading, spacing: 12) {
                CardTitle(icon: "icon_calendar", title: lang.t("challenge.daily.title"),
                          timer: Lang.time(Day.secondsToMidnight(progress.now)))
                Text(lang.t("challenge.daily.text"))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                RewardChips(reward: ChallengeRewards.daily)
                if done {
                    DoneLabel(text: lang.t("challenge.done"))
                } else if let level = ChallengeStore.shared.dailyLevel() {
                    Button(lang.t("challenge.play")) { play(level, .daily(Day.key())) }
                        .buttonStyle(GameButtonStyle(palette: .orange))
                }
            }
        }
    }

    private var weeklyCard: some View {
        let week = Day.weekKey()
        let done = progress.weeklyDone(week)
        let set = ChallengeStore.shared.weeklySet()
        return MetaCard(highlight: done < 3) {
            VStack(alignment: .leading, spacing: 12) {
                CardTitle(icon: "icon_trophy", title: lang.t("challenge.weekly.title"),
                          timer: Lang.time(Day.secondsToWeekEnd(progress.now)))
                if let set = set {
                    Text(lang.t("rule." + set.rule + ".title"))
                        .font(Theme.rounded(16, .black))
                        .foregroundColor(Theme.orange)
                    Text(lang.t("rule." + set.rule + ".text"))
                        .font(Theme.rounded(14, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
                HStack(spacing: 8) {
                    ForEach(0..<3, id: \.self) { i in
                        ProgressBar(value: i < done ? 1 : 0, target: 1, color: Theme.green, height: 12)
                    }
                }
                RewardChips(reward: ChallengeRewards.weekly)
                if done >= 3 {
                    DoneLabel(text: lang.t("challenge.done"))
                } else if let set = set, set.levels.count > done {
                    Button(lang.t("challenge.weekly.play", done + 1)) { play(set.levels[done], .weekly(week, done)) }
                        .buttonStyle(GameButtonStyle(palette: .orange))
                }
            }
        }
    }

    private var medalCard: some View {
        let p = progress.medalProgress()
        let ready = progress.medalReady()
        let claimed = progress.medalClaimed()
        return MetaCard(highlight: ready) {
            VStack(alignment: .leading, spacing: 12) {
                CardTitle(icon: "icon_medal", title: lang.t("medal.title"))
                Text(lang.t("medal.text", ChallengeRewards.medalDaily, ChallengeRewards.medalWeekly))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                progressLine(lang.t("medal.daily", min(p.daily, ChallengeRewards.medalDaily), ChallengeRewards.medalDaily),
                             p.daily, ChallengeRewards.medalDaily)
                progressLine(lang.t("medal.weekly", min(p.weekly, ChallengeRewards.medalWeekly), ChallengeRewards.medalWeekly),
                             p.weekly, ChallengeRewards.medalWeekly)
                RewardChips(reward: ChallengeRewards.medal)
                if claimed {
                    DoneLabel(text: lang.t("challenge.done"))
                } else if ready {
                    Button(lang.t("common.claim")) { granted = progress.claimMedal() }
                        .buttonStyle(GameButtonStyle(palette: .green))
                }
            }
        }
    }

    private func progressLine(_ title: String, _ value: Int, _ target: Int) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title).font(Theme.rounded(14, .heavy)).foregroundColor(Theme.brown)
            ProgressBar(value: value, target: target)
        }
    }
}

// MARK: - Задания новичка

/// Задания на 7 дней: вкладки дней (будущие закрыты, выполненные зеленые) и главный приз.
struct QuestsContent: View {
    @Binding var granted: Granted?
    @Binding var grandTitle: Bool
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var day = min(max(1, PlayerProgress.shared.welcomeDay), WelcomeQuests.days)

    var body: some View {
        VStack(spacing: 14) {
            grandCard
            dayTabs
            SectionTitle(title: lang.t("quests.day", day), color: Theme.orange)
            ForEach(WelcomeQuests.all.filter { $0.day == day }) { q in questRow(q) }
        }
    }

    private enum DayState { case locked, open, done }

    private func state(_ d: Int) -> DayState {
        if d > progress.welcomeDay { return .locked }
        let quests = WelcomeQuests.all.filter { $0.day == d }
        return quests.allSatisfy { progress.questClaimed($0) } ? .done : .open
    }

    private var dayTabs: some View {
        HStack(spacing: 5) {
            ForEach(1...WelcomeQuests.days, id: \.self) { d in
                let st = state(d)
                let claimable = WelcomeQuests.all.contains { $0.day == d && progress.canClaim($0) }
                Button {
                    guard st != .locked else {
                        Toast.info(lang.t("quests.in", d - progress.welcomeDay), icon: "lock.fill")
                        return
                    }
                    Audio.shared.play(.button, volume: 0.5)
                    withAnimation(.easeOut(duration: 0.15)) { day = d }
                } label: {
                    dayTile(d, st, selected: day == d)
                        .overlay(alignment: .topTrailing) {
                            if claimable { BadgeDot().offset(x: 4, y: -4) }
                        }
                }
                .buttonStyle(PressScaleStyle())
            }
        }
    }

    private func dayTile(_ d: Int, _ st: DayState, selected: Bool) -> some View {
        let palette: ButtonPalette = st == .locked ? .gray : (st == .done ? .green : (selected ? .orange : .paper))
        let shape = RoundedRectangle(cornerRadius: 12, style: .continuous)
        return VStack(spacing: 1) {
            Text(lang.t("streak.short", d))
                .font(Theme.rounded(11, .black))
                .lineLimit(1)
                .minimumScaleFactor(0.6)
            Group {
                switch st {
                case .locked: SpriteImage(name: "icon_lock", size: 22).opacity(0.7)
                case .done: SpriteImage(name: "icon_check", size: 24)
                case .open: Text("\(d)").font(Theme.rounded(18, .black))
                }
            }
            .frame(height: 24)
        }
        .foregroundColor(palette.text)
        .modifier(Outline(color: palette == .paper ? .clear : palette.dark, width: 1))
        .frame(maxWidth: .infinity)
        .frame(height: 58)
        .background(
            ZStack {
                shape.fill(palette.dark).offset(y: selected ? 1 : 3)
                shape.fill(LinearGradient(colors: [palette.top, palette.bottom], startPoint: .top, endPoint: .bottom))
                shape.strokeBorder(palette.dark, lineWidth: selected ? 3 : 2)
            }
        )
        .offset(y: selected ? 2 : 0)
    }

    private var grandCard: some View {
        let done = WelcomeQuests.all.filter { progress.questClaimed($0) }.count
        return MetaCard(highlight: progress.welcomeGrandReady) {
            HStack(alignment: .top, spacing: 12) {
                BackgroundThumb(id: "diner", width: 72)
                VStack(alignment: .leading, spacing: 10) {
                    Text(lang.t("quests.grand")).font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                        .fixedSize(horizontal: false, vertical: true)
                    RewardChips(reward: WelcomeQuests.grand, perRow: 3, tileWidth: 56)
                    HStack(spacing: 8) {
                        ProgressBar(value: done, target: WelcomeQuests.all.count, color: Theme.green)
                        Text("\(done)/\(WelcomeQuests.all.count)")
                            .font(Theme.rounded(13, .black)).foregroundColor(Theme.brownSoft).monospacedDigit()
                    }
                    if progress.welcomeGrandReady {
                        Button(lang.t("common.claim")) {
                            grandTitle = true
                            granted = progress.claimWelcomeGrand()
                        }
                        .buttonStyle(GameButtonStyle(palette: .green, height: 44))
                    }
                }
            }
        }
    }

    private func questRow(_ q: Quest) -> some View {
        let value = progress.stat(q.stat)
        let claimed = progress.questClaimed(q)
        return MetaCard(highlight: progress.canClaim(q)) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    Text(lang.t("task." + q.stat.rawValue, q.target))
                        .font(Theme.rounded(16, .black))
                        .foregroundColor(Theme.brown)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                    if claimed { SpriteImage(name: "icon_check", size: 30) }
                }
                HStack(spacing: 8) {
                    ProgressBar(value: value, target: q.target, color: claimed ? Theme.green : Theme.orange)
                    Text("\(min(value, q.target))/\(q.target)")
                        .font(Theme.rounded(13, .black)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
                RewardChips(reward: q.reward)
                if progress.canClaim(q) {
                    Button(lang.t("common.claim")) {
                        grandTitle = false
                        granted = progress.claim(q)
                    }
                    .buttonStyle(GameButtonStyle(palette: .green))
                }
            }
        }
    }
}

/// Превью фона кухни целиком, как обои телефона: полка сверху, стена, стол снизу.
struct BackgroundThumb: View {
    let id: String
    var width: CGFloat = 96
    var selected = false

    var body: some View {
        let shape = RoundedRectangle(cornerRadius: width * 0.12, style: .continuous)
        Image(uiImage: Art.image(KitchenStyle.image(id)))
            .resizable()
            .aspectRatio(1170.0 / 2532.0, contentMode: .fill)
            .frame(width: width, height: width * 2532.0 / 1170.0)
            .clipShape(shape)
            .overlay(shape.strokeBorder(selected ? Theme.orange : Theme.paperBorder, lineWidth: selected ? 4 : 2.5))
    }
}
