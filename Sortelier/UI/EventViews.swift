import SwiftUI

enum EventUI {
    static func symbol(_ kind: EventKind) -> String {
        switch kind {
        case .season: return "seal.fill"
        case .hunt: return "magnifyingglass"
        case .race: return "flag.checkered"
        case .double: return "2.circle.fill"
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

struct EventsSheet: View {
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
                    SheetHeader(title: lang.t("event.title"), subtitle: lang.t("event.subtitle")) {
                        presentation.wrappedValue.dismiss()
                    }
                    ForEach(progress.activeEvents) { event in
                        card(event)
                    }
                    upcoming
                }
                .padding(20)
            }
            if let granted = granted {
                RewardPopup(title: lang.t("common.received"), granted: granted) { self.granted = nil }
            }
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

    private func header(_ event: GameEvent) -> some View {
        HStack {
            Image(systemName: EventUI.symbol(event.kind)).foregroundColor(EventUI.color(event.kind))
            Text(EventUI.title(event, lang: lang))
                .font(Theme.rounded(19, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Spacer()
            Label(Lang.time(event.left(progress.now)), systemImage: "clock")
                .font(Theme.rounded(12, .bold))
                .foregroundColor(Theme.brownSoft)
                .monospacedDigit()
        }
    }

    // MARK: - Сезонный ивент

    private func seasonCard(_ event: GameEvent) -> some View {
        let s = progress.eventState(event.id)
        let levels = EventLevelStore.shared.levels(theme: event.theme)
        return MetaCard(highlight: true) {
            VStack(alignment: .leading, spacing: 12) {
                header(event)
                Image(uiImage: Art.image(KitchenStyle.image(event.theme)))
                    .resizable()
                    .aspectRatio(contentMode: .fill)
                    .frame(height: 90)
                    .frame(maxWidth: .infinity)
                    .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                    .overlay(
                        Text(lang.t("event.season.text"))
                            .font(Theme.rounded(13, .heavy))
                            .foregroundColor(.white)
                            .multilineTextAlignment(.center)
                            .padding(8)
                            .background(Capsule().fill(Color.black.opacity(0.35)))
                    )
                HStack {
                    Image(systemName: "seal.fill").foregroundColor(Theme.orange)
                    Text(lang.t("event.stamps", s.points)).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                }
                track(event, state: s)
                passBanner
                HStack {
                    Text(lang.t("event.levels", min(s.levels, levels.count), levels.count))
                        .font(Theme.rounded(14, .bold))
                        .foregroundColor(Theme.brownSoft)
                    Spacer()
                }
                if s.levels < levels.count {
                    Button(lang.t("event.play", s.levels + 1)) {
                        launch = LevelLaunch(level: levels[s.levels], mode: .event(event.id, event.theme, s.levels))
                        presentation.wrappedValue.dismiss()
                    }
                    .buttonStyle(BigButtonStyle())
                } else {
                    Label(lang.t("event.levels.done"), systemImage: "checkmark.seal.fill")
                        .font(Theme.rounded(15, .heavy))
                        .foregroundColor(Theme.green)
                }
            }
        }
    }

    private var passBanner: some View {
        HStack(spacing: 10) {
            Image(systemName: "ticket.fill").foregroundColor(Theme.gold)
            VStack(alignment: .leading, spacing: 2) {
                Text(lang.t("event.pass")).font(Theme.rounded(14, .heavy)).foregroundColor(Theme.brown)
                Text(lang.t("event.pass.soon")).font(Theme.rounded(12, .semibold)).foregroundColor(Theme.brownSoft)
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12).fill(Theme.gold.opacity(0.15)))
    }

    /// Шкала наград: сверху платная ветка, снизу бесплатная.
    private func track(_ event: GameEvent, state: EventState) -> some View {
        let tiers = progress.tiers(event)
        return ScrollView(.horizontal, showsIndicators: false) {
            HStack(alignment: .top, spacing: 8) {
                ForEach(tiers.indices, id: \.self) { i in
                    VStack(spacing: 6) {
                        if event.kind == .season {
                            rewardCell(event, i, tiers[i].pass, pass: true, reached: state.points >= tiers[i].points,
                                       claimed: state.claimedPass.contains(i), locked: !state.pass)
                        }
                        Text("\(tiers[i].points)")
                            .font(Theme.rounded(13, .heavy))
                            .foregroundColor(state.points >= tiers[i].points ? .white : Theme.brownSoft)
                            .frame(width: 34, height: 34)
                            .background(Circle().fill(state.points >= tiers[i].points ? EventUI.color(event.kind) : Theme.cream))
                        rewardCell(event, i, tiers[i].free, pass: false, reached: state.points >= tiers[i].points,
                                   claimed: state.claimed.contains(i), locked: false)
                    }
                }
            }
            .padding(.vertical, 4)
        }
    }

    private func rewardCell(_ event: GameEvent, _ index: Int, _ reward: Reward, pass: Bool, reached: Bool,
                            claimed: Bool, locked: Bool) -> some View {
        VStack(spacing: 4) {
            RewardChips(reward: reward)
                .scaleEffect(0.85)
                .frame(width: 96, height: 64)
            if claimed {
                Image(systemName: "checkmark.circle.fill").foregroundColor(Theme.green)
                    .frame(height: 26)
            } else if locked {
                Image(systemName: "lock.fill").foregroundColor(Theme.brownSoft)
                    .frame(height: 26)
            } else if reached {
                Button(lang.t("common.claim")) { granted = progress.claimTier(event, index, pass: pass) }
                    .font(Theme.rounded(12, .heavy))
                    .foregroundColor(.white)
                    .padding(.horizontal, 10)
                    .frame(height: 26)
                    .background(Capsule().fill(Theme.green))
            } else {
                Color.clear.frame(height: 26)
            }
        }
        .frame(width: 100)
        .padding(.vertical, 4)
        .background(RoundedRectangle(cornerRadius: 12)
            .fill(pass ? Theme.gold.opacity(0.18) : Theme.cream.opacity(0.7)))
    }

    // MARK: - Охота

    private func huntCard(_ event: GameEvent) -> some View {
        let s = progress.eventState(event.id)
        return MetaCard {
            VStack(alignment: .leading, spacing: 10) {
                header(event)
                HStack(spacing: 12) {
                    GoldSprite(name: event.theme, size: 56)
                    Text(lang.t("event.hunt.text", lang.itemName(event.theme)))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .fixedSize(horizontal: false, vertical: true)
                }
                Text(lang.t("event.hunt.count", s.points)).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                track(event, state: s)
            }
        }
    }

    // MARK: - Гонка

    private func raceCard(_ event: GameEvent) -> some View {
        let s = progress.eventState(event.id)
        return MetaCard(highlight: s.joined == nil || progress.canClaimRace(event)) {
            VStack(alignment: .leading, spacing: 10) {
                header(event)
                Text(lang.t("event.race.text", RaceEvent.goal))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                if s.joined == nil {
                    RewardChips(reward: RaceEvent.reward(place: 1))
                    Button(lang.t("event.race.join")) { progress.joinRace(event) }
                        .buttonStyle(BigButtonStyle(color: Theme.red))
                } else {
                    ForEach(Array(progress.raceStandings(event).enumerated()), id: \.element.id) { i, row in
                        raceRow(place: i + 1, row: row)
                    }
                    if let place = progress.racePlace(event) {
                        Text(lang.t("event.race.place", place)).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                        if progress.canClaimRace(event) {
                            RewardChips(reward: RaceEvent.reward(place: place))
                            Button(lang.t("common.claim")) { granted = progress.claimRace(event) }
                                .buttonStyle(BigButtonStyle(color: Theme.green))
                        }
                    }
                }
            }
        }
    }

    private func raceRow(place: Int, row: PlayerProgress.RaceRow) -> some View {
        HStack(spacing: 10) {
            Text("\(place)")
                .font(Theme.rounded(15, .heavy))
                .foregroundColor(place == 1 ? Theme.gold : Theme.brownSoft)
                .frame(width: 20)
            if let look = row.look {
                SpriteImage(name: "customer_\(look)_happy", size: 34)
            } else {
                Image(systemName: "person.crop.circle.fill").font(.system(size: 30)).foregroundColor(Theme.orange)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text(row.isPlayer ? lang.t("event.race.you") : lang.t("event.race.chef", row.name))
                    .font(Theme.rounded(14, row.isPlayer ? .heavy : .bold))
                    .foregroundColor(Theme.brown)
                ProgressBar(value: row.wins, target: RaceEvent.goal, color: row.isPlayer ? Theme.orange : Theme.brownSoft)
            }
            Text("\(row.wins)/\(RaceEvent.goal)")
                .font(Theme.rounded(12, .bold))
                .foregroundColor(Theme.brownSoft)
                .monospacedDigit()
        }
    }

    // MARK: - Двойные выходные

    private func doubleCard(_ event: GameEvent) -> some View {
        MetaCard(highlight: progress.canClaimDoubleBonus(event)) {
            VStack(alignment: .leading, spacing: 10) {
                header(event)
                Text(lang.t("event.double.text"))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                if progress.canClaimDoubleBonus(event) {
                    RewardChips(reward: Reward(unlimitedMinutes: DoubleEvent.bonusMinutes))
                    Button(lang.t("event.double.claim")) { granted = progress.claimDoubleBonus(event) }
                        .buttonStyle(BigButtonStyle(color: Theme.green))
                } else {
                    Label(lang.t("event.double.claimed"), systemImage: "checkmark.seal.fill")
                        .font(Theme.rounded(14, .heavy))
                        .foregroundColor(Theme.green)
                }
            }
        }
    }

    // MARK: - Скоро

    private var upcoming: some View {
        let activeKinds = Set(progress.activeEvents.map(\.kind))
        let soon = EventKind.allCases.filter { !activeKinds.contains($0) }
        return VStack(alignment: .leading, spacing: 8) {
            if !soon.isEmpty {
                Text(lang.t("event.soon")).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
            }
            ForEach(soon, id: \.self) { kind in
                HStack {
                    Image(systemName: EventUI.symbol(kind)).foregroundColor(EventUI.color(kind))
                    Text(lang.t("event.\(kind.rawValue).name")).font(Theme.rounded(15, .bold)).foregroundColor(Theme.brown)
                    Spacer()
                    if let start = EventCalendar.nextStart(kind, progress.now) {
                        Text(Lang.time(start.timeIntervalSince(progress.now)))
                            .font(Theme.rounded(12, .bold))
                            .foregroundColor(Theme.brownSoft)
                            .monospacedDigit()
                    }
                }
                .padding(12)
                .background(RoundedRectangle(cornerRadius: 14).fill(Theme.card.opacity(0.8)))
            }
        }
    }
}
