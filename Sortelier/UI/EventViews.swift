import SwiftUI

enum EventUI {
    static func icon(_ kind: EventKind) -> String {
        switch kind {
        case .season: return "icon_star"
        case .hunt: return "icon_map"
        case .race: return "icon_flag"
        case .double: return "coin_icon"
        }
    }

    static func color(_ kind: EventKind) -> Color {
        switch kind {
        case .season: return Theme.orange
        case .hunt: return Theme.gold
        case .race: return Theme.red
        case .double: return Theme.green
        }
    }

    static func title(_ event: GameEvent, lang: Lang) -> String {
        switch event.kind {
        case .season: return lang.t("event.season." + event.theme)
        case .hunt: return lang.t("event.hunt.title", lang.itemName(event.theme))
        case .race: return lang.t("event.race.title")
        case .double: return lang.t("event.double.title")
        }
    }

    static func gainText(_ gain: PlayerProgress.EventGain, lang: Lang) -> String {
        switch gain.kind {
        case .season: return lang.t("event.gain.season", lang.t("event.season." + gain.theme), gain.amount, gain.total)
        case .hunt: return lang.t("event.gain.hunt", gain.amount, lang.itemName(gain.theme), gain.total)
        case .race: return lang.t("event.gain.race", gain.total, RaceEvent.goal)
        case .double: return ""
        }
    }
}

/// Вкладка "Ивенты": ивенты, испытания и задания новичка.
struct EventsHub: View {
    let play: (LevelData, PlayMode) -> Void
    @EnvironmentObject private var router: Router
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var granted: Granted?
    @State private var grandTitle = false
    @State private var raceIntro = false

    private var sections: [SegmentPicker<EventsSection>.Item] {
        var items: [SegmentPicker<EventsSection>.Item] = [
            .init(id: .events, title: lang.t("events.section.events"), icon: "icon_ticket", badge: progress.eventsClaimable),
            .init(id: .challenges, title: lang.t("events.section.challenges"), icon: "icon_calendar", badge: !progress.dailyDone())
        ]
        if progress.welcomeActive {
            items.append(.init(id: .quests, title: lang.t("events.section.quests"), icon: "icon_gift", badge: progress.questsClaimable))
        }
        return items
    }

    private var section: EventsSection {
        router.eventsSection == .quests && !progress.welcomeActive ? .events : router.eventsSection
    }

    var body: some View {
        ZStack {
            ScreenScaffold(title: lang.t("tab.events"), back: { router.open(.map) }) {
                SegmentPicker(items: sections, selection: $router.eventsSection)
                Group {
                    switch section {
                    case .events: EventsContent(play: play, granted: $granted, raceIntro: $raceIntro)
                    case .challenges: ChallengesContent(play: play, granted: $granted)
                    case .quests: QuestsContent(granted: $granted, grandTitle: $grandTitle)
                    }
                }
                .id(section)
                .transition(.opacity)
            }
            if let granted = granted {
                RewardPopup(title: lang.t(grandTitle ? "quests.grand.title" : "common.received"), granted: granted) {
                    self.granted = nil
                }
            }
            if raceIntro {
                RaceStartView(rivals: RaceEvent.rivals(seed: progress.race.seed)) { withAnimation { raceIntro = false } }
                    .transition(.opacity)
            }
        }
    }
}

/// Список идущих ивентов и анонсы будущих.
struct EventsContent: View {
    let play: (LevelData, PlayMode) -> Void
    @Binding var granted: Granted?
    @Binding var raceIntro: Bool
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        VStack(spacing: 14) {
            ForEach(progress.activeEvents) { event in card(event) }
            upcoming
        }
    }

    @ViewBuilder
    private func card(_ event: GameEvent) -> some View {
        switch event.kind {
        case .season: seasonCard(event)
        case .hunt: huntCard(event)
        case .race: raceCard(event)
        case .double: doubleCard(event)
        }
    }

    private func title(_ event: GameEvent) -> some View {
        CardTitle(icon: EventUI.icon(event.kind), title: EventUI.title(event, lang: lang), timer: Lang.time(event.left(progress.now)))
    }

    // MARK: Сезонный ивент

    private func seasonCard(_ event: GameEvent) -> some View {
        let s = progress.eventState(event.id)
        let levels = EventLevelStore.shared.levels(theme: event.theme)
        return MetaCard(highlight: progress.eventClaimable(event)) {
            VStack(alignment: .leading, spacing: 12) {
                title(event)
                Image(uiImage: Art.image(KitchenStyle.image(event.theme)))
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(height: 84)
                    .frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Theme.paperBorder, lineWidth: 2.5))
                    .overlay(
                        StrokeText(text: lang.t("event.season.text"), size: 14, color: .white, stroke: Theme.woodDark, width: 1.5, drop: 2)
                            .padding(.horizontal, 12)
                    )
                HStack(spacing: 6) {
                    SpriteImage(name: "icon_star", size: 28)
                    Text(lang.t("event.stamps", s.points)).font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                }
                EventTrack(event: event, state: s, pass: true, granted: $granted)
                passBanner(event, state: s)
                Text(lang.t("event.levels", min(s.levels, levels.count), levels.count))
                    .font(Theme.rounded(14, .heavy))
                    .foregroundColor(Theme.brownSoft)
                if s.levels < levels.count {
                    Button(lang.t("event.play", s.levels + 1)) {
                        play(levels[s.levels], .event(event.id, event.theme, s.levels))
                    }
                    .buttonStyle(GameButtonStyle(palette: .orange))
                } else {
                    DoneLabel(text: lang.t("event.levels.done"))
                }
            }
        }
    }

    @ViewBuilder
    private func passBanner(_ event: GameEvent, state: EventState) -> some View {
        HStack(spacing: 10) {
            SpriteImage(name: "icon_ticket", size: 40)
            VStack(alignment: .leading, spacing: 2) {
                Text(lang.t("event.pass")).font(Theme.rounded(15, .black)).foregroundColor(Theme.brown)
                Text(lang.t(state.pass ? "event.pass.active" : "event.pass.text"))
                    .font(Theme.rounded(12, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 4)
            if !state.pass {
                Button(Store.shared.price(.eventPass)) {
                    Task { @MainActor in
                        if case .done = await Store.shared.buy(.eventPass) {
                            Audio.shared.play(.chest)
                            Haptics.success()
                        } else if !Store.shared.canPurchase {
                            Toast.error(lang.t("shop.unavailable"))
                        }
                    }
                }
                .buttonStyle(SmallButtonStyle(palette: .green))
            } else {
                SpriteImage(name: "icon_check", size: 30)
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(InsetBackground(color: Color(red: 1.0, green: 0.92, blue: 0.62)))
    }

    // MARK: Охота

    private func huntCard(_ event: GameEvent) -> some View {
        let s = progress.eventState(event.id)
        return MetaCard(highlight: progress.eventClaimable(event)) {
            VStack(alignment: .leading, spacing: 12) {
                title(event)
                HStack(spacing: 12) {
                    GoldSprite(name: event.theme, size: 60)
                    Text(lang.t("event.hunt.text", lang.itemName(event.theme)))
                        .font(Theme.rounded(14, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Text(lang.t("event.hunt.count", s.points)).font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                EventTrack(event: event, state: s, pass: false, granted: $granted)
            }
        }
    }

    // MARK: Гонка

    private func raceCard(_ event: GameEvent) -> some View {
        let race = progress.race
        return MetaCard(highlight: progress.canClaimRace || (progress.canStartRace && !progress.raceActive && progress.nextRaceGivesChests)) {
            VStack(alignment: .leading, spacing: 12) {
                title(event)
                Text(lang.t("event.race.rules2", RaceEvent.goal, RaceEvent.chestRaces))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 8) {
                    SpriteImage(name: ChestKind.gold.sprite, size: 30)
                    Text(lang.t("event.race.chests", progress.chestRacesLeft, RaceEvent.chestRaces))
                        .font(Theme.rounded(14, .black))
                        .foregroundColor(progress.chestRacesLeft > 0 ? Theme.brown : Theme.brownSoft)
                    Spacer(minLength: 0)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 6)
                .background(InsetBackground(radius: 12))
                if progress.raceActive {
                    VStack(spacing: 6) {
                        ForEach(Array(progress.raceStandings().enumerated()), id: \.element.id) { i, row in
                            raceRow(place: i + 1, row: row)
                        }
                    }
                    if let place = progress.racePlace {
                        Text(lang.t("event.race.place", place)).font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                            .frame(maxWidth: .infinity)
                        RewardChips(reward: RaceEvent.reward(place: place, chests: progress.raceGivesChests))
                        Button(lang.t("common.claim")) { granted = progress.claimRace() }
                            .buttonStyle(GameButtonStyle(palette: .green))
                    } else if progress.raceOver {
                        Text(lang.t("event.race.over")).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brownSoft)
                        startButton
                    } else {
                        Text(lang.t("event.race.progress", race.wins, RaceEvent.goal))
                            .font(Theme.rounded(15, .black))
                            .foregroundColor(Theme.red)
                            .frame(maxWidth: .infinity)
                    }
                } else {
                    Text(lang.t("event.race.prizes")).font(Theme.rounded(15, .black)).foregroundColor(Theme.brown)
                    HStack(alignment: .top, spacing: 8) {
                        ForEach(1...3, id: \.self) { place in
                            VStack(spacing: 6) {
                                PlaceBadge(place: place)
                                RewardChips(reward: RaceEvent.reward(place: place, chests: progress.nextRaceGivesChests),
                                            perRow: 1, tileWidth: 60)
                            }
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 8)
                            .background(InsetBackground(radius: 14, color: Theme.card))
                        }
                    }
                    startButton
                }
            }
        }
    }

    @ViewBuilder
    private var startButton: some View {
        if !progress.nextRaceGivesChests && !progress.raceActive {
            Text(lang.t("event.race.coinsOnly", Lang.time(Day.secondsToMidnight(progress.now))))
                .font(Theme.rounded(13, .bold))
                .foregroundColor(Theme.brownSoft)
                .monospacedDigit()
                .fixedSize(horizontal: false, vertical: true)
        }
        if progress.canStartRace {
            Button(lang.t("event.race.startNext")) {
                progress.startRace()
                Audio.shared.play(.unlock)
                withAnimation { raceIntro = true }
            }
            .buttonStyle(GameButtonStyle(palette: .red))
        }
    }

    private func raceRow(place: Int, row: PlayerProgress.RaceRow) -> some View {
        HStack(spacing: 10) {
            PlaceBadge(place: place, size: 28)
            Group {
                if let look = row.look {
                    SpriteImage(name: "customer_\(look)_" + (row.finished != nil ? "joy" : "happy"), size: 40)
                } else {
                    SpriteImage(name: "icon_chef", size: 38)
                }
            }
            .frame(width: 40)
            VStack(alignment: .leading, spacing: 4) {
                Text(row.isPlayer ? lang.t("event.race.you") : lang.t("event.race.chef", row.name))
                    .font(Theme.rounded(14, row.isPlayer ? .black : .heavy))
                    .foregroundColor(Theme.brown)
                    .lineLimit(1)
                ProgressBar(value: row.wins, target: RaceEvent.goal, color: row.isPlayer ? Theme.orange : Theme.brownSoft, height: 12)
            }
            Group {
                if row.finished != nil {
                    SpriteImage(name: "icon_flag", size: 30)
                } else {
                    Text("\(row.wins)/\(RaceEvent.goal)")
                        .font(Theme.rounded(13, .black))
                        .foregroundColor(Theme.brownSoft)
                        .monospacedDigit()
                }
            }
            .frame(width: 36)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 6)
        .background(InsetBackground(radius: 12, color: row.isPlayer ? Color(red: 1.0, green: 0.88, blue: 0.62) : Theme.cream))
    }

    // MARK: Двойные выходные

    private func doubleCard(_ event: GameEvent) -> some View {
        MetaCard(highlight: progress.canClaimDoubleBonus(event)) {
            VStack(alignment: .leading, spacing: 12) {
                title(event)
                Text(lang.t("event.double.text"))
                    .font(Theme.rounded(14, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                if progress.canClaimDoubleBonus(event) {
                    RewardChips(reward: Reward(unlimitedMinutes: DoubleEvent.bonusMinutes))
                    Button(lang.t("event.double.claim")) { granted = progress.claimDoubleBonus(event) }
                        .buttonStyle(GameButtonStyle(palette: .green))
                } else {
                    DoneLabel(text: lang.t("event.double.claimed"))
                }
            }
        }
    }

    // MARK: Скоро

    private var upcoming: some View {
        let activeKinds = Set(progress.activeEvents.map(\.kind))
        let soon = EventKind.allCases.filter { !activeKinds.contains($0) }.compactMap { EventCalendar.next($0, progress.now) }
        return VStack(spacing: 12) {
            if !soon.isEmpty {
                SectionTitle(title: lang.t("event.soon"), color: Theme.orange)
            }
            ForEach(soon) { event in soonCard(event) }
        }
    }

    /// Будущий ивент: картинка, название, что в нем и сколько ждать.
    private func soonCard(_ event: GameEvent) -> some View {
        HStack(spacing: 12) {
            soonPicture(event)
                .frame(width: 78, height: 78)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Theme.paperBorder, lineWidth: 2.5))
            VStack(alignment: .leading, spacing: 4) {
                Text(EventUI.title(event, lang: lang))
                    .font(Theme.rounded(17, .black))
                    .foregroundColor(Theme.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                Text(lang.t("event.\(event.kind.rawValue).about"))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                TimerBadge(text: lang.t("event.starts", Lang.time(event.start.timeIntervalSince(progress.now))))
            }
            Spacer(minLength: 0)
        }
        .padding(12)
        .background(PaperBackground(radius: 18))
    }

    @ViewBuilder
    private func soonPicture(_ event: GameEvent) -> some View {
        switch event.kind {
        case .season:
            Image(uiImage: Art.image(KitchenStyle.image(event.theme)))
                .resizable()
                .aspectRatio(contentMode: .fill)
        case .hunt:
            ZStack {
                Color(red: 1.0, green: 0.9, blue: 0.6)
                GoldSprite(name: event.theme, size: 60)
            }
        case .race:
            ZStack {
                Color(red: 1.0, green: 0.82, blue: 0.75)
                HStack(spacing: -18) {
                    ForEach([2, 5, 8], id: \.self) { look in SpriteImage(name: "customer_\(look)_joy", size: 40) }
                }
                SpriteImage(name: "icon_flag", size: 30).offset(x: 24, y: -22)
            }
        case .double:
            ZStack {
                Color(red: 0.85, green: 0.95, blue: 0.75)
                CoinIcon(size: 44).offset(x: -8, y: 6)
                StrokeText(text: "x2", size: 24, color: .white, stroke: ButtonPalette.green.dark, width: 1.5, drop: 2)
                    .offset(x: 16, y: -16)
            }
        }
    }
}

/// Номер места: золото, серебро, бронза, дальше бумага.
struct PlaceBadge: View {
    let place: Int
    var size: CGFloat = 30

    private var colors: (Color, Color) {
        switch place {
        case 1: return (Color(red: 1.0, green: 0.85, blue: 0.35), Color(red: 0.55, green: 0.33, blue: 0.05))
        case 2: return (Color(red: 0.86, green: 0.89, blue: 0.95), Color(red: 0.36, green: 0.40, blue: 0.50))
        case 3: return (Color(red: 0.92, green: 0.62, blue: 0.38), Color(red: 0.45, green: 0.22, blue: 0.08))
        default: return (Theme.cream, Theme.chipBorder)
        }
    }

    var body: some View {
        ZStack {
            Circle().fill(colors.0)
            Circle().strokeBorder(colors.1, lineWidth: 2.5)
            Text("\(place)").font(Theme.rounded(size * 0.5, .black)).foregroundColor(colors.1)
        }
        .frame(width: size, height: size)
    }
}

/// Шкала ивента: колонки одной ширины. Сверху золотая ветка пропуска, посередине ступени на общей линии,
/// снизу бесплатные награды. Лента подглядывает следующую колонку и сама едет к текущей ступени.
struct EventTrack: View {
    let event: GameEvent
    let state: EventState
    let pass: Bool
    @Binding var granted: Granted?
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    private let cell: CGFloat = 92

    var body: some View {
        let tiers = progress.tiers(event)
        let current = tiers.indices.first { i in
            (state.points >= tiers[i].points && !state.claimed.contains(i)) || state.points < tiers[i].points
        } ?? max(0, tiers.count - 1)
        return StepTrack(count: tiers.count, current: current, cellWidth: cell) { i in
            VStack(spacing: 6) {
                if pass {
                    rewardCell(i, tiers[i].pass, isPass: true, reached: state.points >= tiers[i].points,
                               claimed: state.claimedPass.contains(i), locked: !state.pass)
                }
                marker(points: tiers[i].points, reached: state.points >= tiers[i].points)
                rewardCell(i, tiers[i].free, isPass: false, reached: state.points >= tiers[i].points,
                           claimed: state.claimed.contains(i), locked: false)
            }
        }
    }

    /// Ступень на общей линии: отрезок шире колонки, чтобы соседние отрезки сливались в одну линию.
    private func marker(points: Int, reached: Bool) -> some View {
        ZStack {
            Capsule()
                .fill(reached ? EventUI.color(event.kind) : Theme.woodDark.opacity(0.35))
                .frame(width: cell + 12, height: 8)
            ZStack {
                Circle().fill(reached ? EventUI.color(event.kind) : Theme.cream)
                Circle().strokeBorder(reached ? Theme.woodDark : Theme.chipBorder, lineWidth: 2.5)
                Text("\(points)")
                    .font(Theme.rounded(14, .black))
                    .foregroundColor(reached ? .white : Theme.brownSoft)
                    .modifier(Outline(color: reached ? Theme.woodDark : .clear, width: 1))
            }
            .frame(width: 38, height: 38)
        }
        .frame(width: cell, height: 40)
    }

    private func rewardCell(_ index: Int, _ reward: Reward, isPass: Bool, reached: Bool, claimed: Bool, locked: Bool) -> some View {
        VStack(spacing: 4) {
            RewardMini(reward: reward, icon: 34)
                .frame(height: 56)
                .opacity(claimed ? 0.5 : 1)
            Group {
                if claimed {
                    SpriteImage(name: "icon_check", size: 28)
                } else if locked {
                    SpriteImage(name: "icon_lock", size: 26)
                } else if reached {
                    Button(lang.t("common.claim")) { granted = progress.claimTier(event, index, pass: isPass) }
                        .buttonStyle(GameButtonStyle(palette: .green, height: 30, fontSize: 13, radius: 10))
                } else {
                    Color.clear
                }
            }
            .frame(height: 34)
        }
        .padding(.top, 8)
        .padding(.horizontal, 5)
        .frame(width: cell, height: 108)
        .background(
            InsetBackground(radius: 14, color: isPass ? Color(red: 1.0, green: 0.88, blue: 0.5) : Theme.cream)
        )
        .overlay(alignment: .topLeading) {
            if isPass { SpriteImage(name: "icon_ticket", size: 22).offset(x: -4, y: -6) }
        }
    }
}

/// Старт заезда: повара выезжают на дорожки, отсчет 3-2-1 и "Старт!".
struct RaceStartView: View {
    let rivals: [Rival]
    let done: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var shown = 0
    @State private var count = 3
    @State private var go = false

    var body: some View {
        ZStack {
            Dim(opacity: 0.65)
            VStack(spacing: 18) {
                Ribbon(title: lang.t("event.race.title"), size: 22)
                VStack(spacing: 8) {
                    lane(0, label: lang.t("event.race.you")) { SpriteImage(name: "icon_chef", size: 40) }
                    ForEach(Array(rivals.enumerated()), id: \.element.id) { i, r in
                        lane(i + 1, label: r.name) { SpriteImage(name: "customer_\(r.look)_happy", size: 42) }
                    }
                }
                .padding(.horizontal, 24)
                ZStack {
                    if go {
                        StrokeText(text: lang.t("event.race.go"), size: 56, color: Theme.gold, stroke: Theme.woodDark, width: 3, drop: 5)
                            .transition(.scale.combined(with: .opacity))
                    } else {
                        StrokeText(text: "\(count)", size: 70, color: .white, stroke: Theme.woodDark, width: 3, drop: 5)
                            .id(count)
                            .transition(.scale.combined(with: .opacity))
                    }
                }
                .frame(height: 90)
            }
        }
        .onAppear(perform: run)
    }

    private func lane<Avatar: View>(_ i: Int, label: String, @ViewBuilder avatar: () -> Avatar) -> some View {
        HStack(spacing: 10) {
            avatar().frame(width: 44)
            Text(label).font(Theme.rounded(16, .black)).foregroundColor(Color(red: 1.0, green: 0.93, blue: 0.8))
                .outlined(Theme.woodDark, width: 1)
            Spacer()
            SpriteImage(name: "icon_flag", size: 30)
        }
        .padding(.horizontal, 12)
        .frame(height: 52)
        .background(
            ZStack {
                RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Theme.woodDark).offset(y: 3)
                WoodBackground().clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
                RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Theme.woodDark, lineWidth: 2.5)
            }
        )
        .offset(x: shown > i ? 0 : -420)
        .opacity(shown > i ? 1 : 0)
    }

    private func run() {
        for i in 0...rivals.count {
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.12 * Double(i)) {
                withAnimation(.spring(response: 0.45, dampingFraction: 0.75)) { shown = i + 1 }
                Audio.shared.play(.pick, volume: 0.6)
            }
        }
        for (k, n) in [2, 1].enumerated() {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.4 + 0.7 * Double(k)) {
                withAnimation(.spring(response: 0.3, dampingFraction: 0.6)) { count = n }
                Audio.shared.play(.place)
                Haptics.light()
            }
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.7) { Audio.shared.play(.place) }
        DispatchQueue.main.asyncAfter(deadline: .now() + 2.8) {
            withAnimation(.spring(response: 0.35, dampingFraction: 0.5)) { go = true }
            Audio.shared.play(.combo)
            Haptics.success()
        }
        DispatchQueue.main.asyncAfter(deadline: .now() + 3.7, execute: done)
    }
}
