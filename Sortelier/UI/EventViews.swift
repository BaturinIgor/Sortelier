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
    @State private var raceIntro = false

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
            if raceIntro {
                RaceStartView(rivals: RaceEvent.rivals(seed: progress.race.seed)) { withAnimation { raceIntro = false } }
                    .transition(.opacity)
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
                passBanner(event, state: s)
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

    @ViewBuilder
    private func passBanner(_ event: GameEvent, state: EventState) -> some View {
        HStack(spacing: 10) {
            Image(systemName: "ticket.fill").foregroundColor(Theme.gold)
            VStack(alignment: .leading, spacing: 2) {
                Text(lang.t("event.pass")).font(Theme.rounded(14, .heavy)).foregroundColor(Theme.brown)
                Text(lang.t(state.pass ? "event.pass.active" : "event.pass.text"))
                    .font(Theme.rounded(12, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer()
            if !state.pass {
                Button {
                    Task { @MainActor in
                        if case .done = await Store.shared.buy(.eventPass) {
                            Audio.shared.play(.chest)
                            Haptics.success()
                        } else if !Store.shared.canPurchase {
                            Toast.error(lang.t("shop.unavailable"))
                        }
                    }
                } label: {
                    Text(Store.shared.price(.eventPass))
                        .font(Theme.rounded(14, .heavy))
                        .foregroundColor(.white)
                        .padding(.horizontal, 12)
                        .frame(height: 32)
                        .background(Capsule().fill(Theme.green))
                }
                .buttonStyle(.plain)
            } else {
                Image(systemName: "checkmark.seal.fill").foregroundColor(Theme.green)
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
            RewardChips(reward: reward, perRow: 1, tileWidth: 88)
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
        let race = progress.race
        return MetaCard(highlight: progress.canClaimRace || (progress.canStartRace && !progress.raceActive)) {
            VStack(alignment: .leading, spacing: 10) {
                header(event)
                Text(lang.t("event.race.rules", RaceEvent.goal, RaceEvent.perDay))
                    .font(Theme.rounded(13, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .fixedSize(horizontal: false, vertical: true)
                HStack(spacing: 6) {
                    ForEach(1...RaceEvent.perDay, id: \.self) { i in
                        Capsule()
                            .fill(i <= progress.racesToday ? EventUI.color(.race) : Theme.brown.opacity(0.12))
                            .frame(height: 8)
                    }
                }
                if progress.raceActive {
                    ForEach(Array(progress.raceStandings().enumerated()), id: \.element.id) { i, row in
                        raceRow(place: i + 1, row: row)
                    }
                    if let place = progress.racePlace {
                        Text(lang.t("event.race.place", place)).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                        RewardChips(reward: RaceEvent.reward(place: place))
                        Button(lang.t("common.claim")) { granted = progress.claimRace() }
                            .buttonStyle(BigButtonStyle(color: Theme.green))
                    } else if progress.raceOver {
                        Text(lang.t("event.race.over")).font(Theme.rounded(15, .heavy)).foregroundColor(Theme.brownSoft)
                        startButton
                    } else {
                        Text(lang.t("event.race.progress", race.wins, RaceEvent.goal))
                            .font(Theme.rounded(14, .heavy))
                            .foregroundColor(EventUI.color(.race))
                    }
                } else {
                    Text(lang.t("event.race.prizes")).font(Theme.rounded(14, .heavy)).foregroundColor(Theme.brown)
                    HStack(spacing: 8) {
                        ForEach(1...3, id: \.self) { place in
                            VStack(spacing: 2) {
                                Text(lang.t("event.race.placeShort", place))
                                    .font(Theme.rounded(12, .heavy))
                                    .foregroundColor(Theme.brownSoft)
                                RewardChips(reward: RaceEvent.reward(place: place), perRow: 1, tileWidth: 92)
                            }
                        }
                    }
                    .frame(maxWidth: .infinity)
                    startButton
                }
            }
        }
    }

    @ViewBuilder
    private var startButton: some View {
        if progress.canStartRace {
            Button(lang.t("event.race.start", progress.racesToday + 1, RaceEvent.perDay)) {
                progress.startRace()
                Audio.shared.play(.unlock)
                withAnimation { raceIntro = true }
            }
            .buttonStyle(BigButtonStyle(color: Theme.red))
        } else {
            Label(lang.t("event.race.tomorrow", Lang.time(Day.secondsToMidnight(progress.now))), systemImage: "moon.zzz.fill")
                .font(Theme.rounded(13, .bold))
                .foregroundColor(Theme.brownSoft)
                .monospacedDigit()
        }
    }

    private func raceRow(place: Int, row: PlayerProgress.RaceRow) -> some View {
        HStack(spacing: 10) {
            Text("\(place)")
                .font(Theme.rounded(15, .heavy))
                .foregroundColor(place == 1 ? Theme.gold : Theme.brownSoft)
                .frame(width: 20)
            if let look = row.look {
                SpriteImage(name: "customer_\(look)_" + (row.finished != nil ? "joy" : "happy"), size: 34)
            } else {
                Image(systemName: "person.crop.circle.fill").font(.system(size: 30)).foregroundColor(Theme.orange)
            }
            VStack(alignment: .leading, spacing: 3) {
                Text(row.isPlayer ? lang.t("event.race.you") : lang.t("event.race.chef", row.name))
                    .font(Theme.rounded(14, row.isPlayer ? .heavy : .bold))
                    .foregroundColor(Theme.brown)
                ProgressBar(value: row.wins, target: RaceEvent.goal, color: row.isPlayer ? Theme.orange : Theme.brownSoft)
            }
            if row.finished != nil {
                Image(systemName: "flag.checkered").foregroundColor(Theme.green)
            } else {
                Text("\(row.wins)/\(RaceEvent.goal)")
                    .font(Theme.rounded(12, .bold))
                    .foregroundColor(Theme.brownSoft)
                    .monospacedDigit()
            }
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
        let soon = EventKind.allCases.filter { !activeKinds.contains($0) }.compactMap { EventCalendar.next($0, progress.now) }
        return VStack(alignment: .leading, spacing: 10) {
            if !soon.isEmpty {
                Text(lang.t("event.soon")).font(Theme.rounded(17, .heavy)).foregroundColor(Theme.brown)
            }
            ForEach(soon) { event in soonCard(event) }
        }
    }

    /// Будущий ивент: картинка, название, что в нем и сколько ждать.
    private func soonCard(_ event: GameEvent) -> some View {
        HStack(spacing: 12) {
            soonPicture(event)
                .frame(width: 74, height: 74)
                .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
            VStack(alignment: .leading, spacing: 4) {
                Text(EventUI.title(event, lang: lang))
                    .font(Theme.rounded(16, .heavy))
                    .foregroundColor(Theme.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                Text(lang.t("event.\(event.kind.rawValue).about"))
                    .font(Theme.rounded(12, .semibold))
                    .foregroundColor(Theme.brownSoft)
                    .lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                Label(lang.t("event.starts", Lang.time(event.start.timeIntervalSince(progress.now))), systemImage: "clock")
                    .font(Theme.rounded(12, .heavy))
                    .foregroundColor(EventUI.color(event.kind))
                    .monospacedDigit()
            }
            Spacer(minLength: 0)
        }
        .padding(10)
        .background(
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .fill(LinearGradient(colors: [EventUI.color(event.kind).opacity(0.18), Theme.card],
                                     startPoint: .leading, endPoint: .trailing))
        )
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
                EventUI.color(.hunt).opacity(0.25)
                GoldSprite(name: event.theme, size: 58)
            }
        case .race:
            ZStack {
                EventUI.color(.race).opacity(0.2)
                HStack(spacing: -16) {
                    ForEach([2, 5, 8], id: \.self) { look in SpriteImage(name: "customer_\(look)_joy", size: 38) }
                }
                Image(systemName: "flag.checkered").font(.system(size: 18, weight: .bold)).foregroundColor(Theme.brown)
                    .offset(x: 22, y: -22)
            }
        case .double:
            ZStack {
                EventUI.color(.double).opacity(0.22)
                CoinIcon(size: 40).offset(x: -8, y: 6)
                Text("x2").font(Theme.rounded(26, .heavy)).foregroundColor(Theme.green).offset(x: 12, y: -12)
            }
        }
    }
}


/// Старт заезда: повара выбегают на дорожки, отсчет 3-2-1 и "Старт!".
struct RaceStartView: View {
    let rivals: [Rival]
    let done: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var shown = 0
    @State private var count = 3
    @State private var go = false

    var body: some View {
        ZStack {
            Color.black.opacity(0.55).ignoresSafeArea()
            VStack(spacing: 18) {
                Text(lang.t("event.race.title"))
                    .font(Theme.rounded(26, .heavy))
                    .foregroundColor(.white)
                VStack(spacing: 8) {
                    lane(0, label: lang.t("event.race.you")) {
                        Image(systemName: "person.crop.circle.fill").font(.system(size: 34)).foregroundColor(Theme.orange)
                    }
                    ForEach(Array(rivals.enumerated()), id: \.element.id) { i, r in
                        lane(i + 1, label: r.name) { SpriteImage(name: "customer_\(r.look)_happy", size: 38) }
                    }
                }
                .padding(.horizontal, 24)
                ZStack {
                    if go {
                        Text(lang.t("event.race.go"))
                            .font(Theme.rounded(54, .heavy))
                            .foregroundColor(Theme.gold)
                            .transition(.scale.combined(with: .opacity))
                    } else {
                        Text("\(count)")
                            .font(Theme.rounded(64, .heavy))
                            .foregroundColor(.white)
                            .id(count)
                            .transition(.scale.combined(with: .opacity))
                    }
                }
                .frame(height: 80)
            }
        }
        .onAppear(perform: run)
    }

    private func lane<Avatar: View>(_ i: Int, label: String, @ViewBuilder avatar: () -> Avatar) -> some View {
        HStack(spacing: 10) {
            avatar()
            Text(label).font(Theme.rounded(15, .heavy)).foregroundColor(.white)
            Spacer()
            Image(systemName: "flag.checkered").foregroundColor(.white.opacity(0.7))
        }
        .padding(.horizontal, 12)
        .frame(height: 48)
        .background(RoundedRectangle(cornerRadius: 14).fill(Color.white.opacity(0.12)))
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
