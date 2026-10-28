import Foundation

/// Ивенты: печати сезонного ивента, охота, гонка поваров, двойные выходные.
extension PlayerProgress {
    struct EventGain: Identifiable {
        let id: String
        let kind: EventKind
        let theme: String
        let amount: Int
        let total: Int
    }

    func eventState(_ id: String) -> EventState { data.meta.events[id] ?? EventState() }

    var activeEvents: [GameEvent] { EventCalendar.active(now) }

    /// Начисляет ивенты за победу. Возвращает, что выросло, и бонус двойных выходных.
    func eventsAfterWin(mode: PlayMode, isNewLevel: Bool, stars: Int, coinsAdded: Int) -> (gains: [EventGain], bonus: Int) {
        var gains: [EventGain] = []
        let date = Date()
        for event in EventCalendar.active(date) {
            var s = eventState(event.id)
            switch event.kind {
            case .season:
                let n = SeasonEvent.stamps(mode: mode, isNewLevel: isNewLevel, stars: stars)
                s.points += n
                gains.append(EventGain(id: event.id, kind: .season, theme: event.theme, amount: n, total: s.points))
            case .hunt:
                let n = max(1, stars) + (mode.isChallenge ? 1 : 0)
                s.points += n
                gains.append(EventGain(id: event.id, kind: .hunt, theme: event.theme, amount: n, total: s.points))
            case .race:
                var r = data.meta.race
                if r.joined != nil && r.finished == nil && !r.claimed && !raceOver {
                    r.wins += 1
                    if r.wins >= RaceEvent.goal { r.finished = date }
                    data.meta.race = r
                    gains.append(EventGain(id: event.id, kind: .race, theme: "", amount: 1, total: r.wins))
                }
            case .double:
                break
            }
            data.meta.events[event.id] = s
        }
        var bonus = 0
        if EventCalendar.double(date) != nil && coinsAdded > 0 {
            bonus = coinsAdded * (DoubleEvent.multiplier - 1)
            data.coins += bonus
            data.meta.stats[Stat.coinsEarned.rawValue, default: 0] += bonus
        }
        save()
        return (gains, bonus)
    }

    // MARK: - Шкала наград

    func tiers(_ event: GameEvent) -> [EventTier] {
        switch event.kind {
        case .season: return SeasonEvent.tiers(theme: event.theme)
        case .hunt: return HuntEvent.tiers
        default: return []
        }
    }

    func canClaimTier(_ event: GameEvent, _ index: Int, pass: Bool) -> Bool {
        let s = eventState(event.id)
        let list = tiers(event)
        guard list.indices.contains(index), s.points >= list[index].points else { return false }
        if pass { return s.pass && !s.claimedPass.contains(index) && !list[index].pass.isEmpty }
        return !s.claimed.contains(index)
    }

    func claimTier(_ event: GameEvent, _ index: Int, pass: Bool) -> Granted? {
        guard canClaimTier(event, index, pass: pass) else { return nil }
        var s = eventState(event.id)
        if pass { s.claimedPass.append(index) } else { s.claimed.append(index) }
        data.meta.events[event.id] = s
        save()
        let tier = tiers(event)[index]
        data.meta.stats[Stat.eventRewards.rawValue, default: 0] += 1
        return grant(pass ? tier.pass : tier.free, source: "event_\(event.kind.rawValue)")
    }

    // MARK: - Уровни сезонного ивента

    func completeEventLevel(_ eventId: String, index: Int) -> Bool {
        var s = eventState(eventId)
        guard index == s.levels else { return false }
        s.levels += 1
        data.meta.events[eventId] = s
        save()
        return true
    }

    // MARK: - Гонка поваров

    var race: RaceState { data.meta.race }

    /// Сколько заездов уже начато сегодня.
    var racesToday: Int { data.meta.race.day == Day.key() ? data.meta.race.started : 0 }

    /// Заезд идет: начат, награда не забрана и он еще не закончился.
    var raceActive: Bool { race.joined != nil && !race.claimed }

    /// Заезд закончился: игрок дошел до финиша или все соперники финишировали раньше.
    var raceOver: Bool {
        guard let joined = race.joined, !race.claimed else { return false }
        if race.finished != nil { return true }
        return RaceEvent.rivals(seed: race.seed).allSatisfy { $0.finishTime(joined: joined) <= now }
    }

    /// Можно начать новый заезд: прошлый закончен и не исчерпан лимит на сегодня.
    var canStartRace: Bool {
        race.joined == nil || race.claimed || (raceOver && race.finished == nil)
    }

    /// Дает ли текущий заезд сундуки (первые три заезда дня).
    var raceGivesChests: Bool { race.started <= RaceEvent.chestRaces }

    /// Даст ли сундуки следующий заезд.
    var nextRaceGivesChests: Bool { racesToday < RaceEvent.chestRaces }

    /// Сколько заездов с сундуками осталось сегодня.
    var chestRacesLeft: Int { max(0, RaceEvent.chestRaces - racesToday) }

    func startRace() {
        guard canStartRace else { return }
        var r = RaceState()
        let today = Day.key()
        r.day = today
        r.started = racesToday + 1
        r.joined = Date()
        r.seed = UInt64.random(in: 1...UInt64.max)
        data.meta.race = r
        save()
        Analytics.log("race_join", ["number": r.started])
    }

    struct RaceRow: Identifiable {
        let id: String
        let name: String
        let look: Int?
        let wins: Int
        let finished: Date?
        let isPlayer: Bool
    }

    func raceStandings() -> [RaceRow] {
        guard let joined = race.joined else { return [] }
        var rows = RaceEvent.rivals(seed: race.seed).map { r -> RaceRow in
            let finish = r.finishTime(joined: joined)
            return RaceRow(id: "rival\(r.id)", name: r.name, look: r.look, wins: r.wins(joined: joined, now: now),
                           finished: finish <= now ? finish : nil, isPlayer: false)
        }
        rows.append(RaceRow(id: "player", name: "", look: nil, wins: race.wins, finished: race.finished, isPlayer: true))
        return rows.sorted { a, b in
            switch (a.finished, b.finished) {
            case let (fa?, fb?): return fa < fb
            case (_?, nil): return true
            case (nil, _?): return false
            default: return a.wins == b.wins ? a.isPlayer : a.wins > b.wins
            }
        }
    }

    /// Место игрока, когда он дошел до финиша.
    var racePlace: Int? {
        guard race.finished != nil else { return nil }
        return (raceStandings().firstIndex { $0.isPlayer } ?? 4) + 1
    }

    var canClaimRace: Bool { racePlace != nil && !race.claimed }

    func claimRace() -> Granted? {
        guard canClaimRace, let place = racePlace else { return nil }
        data.meta.race.claimed = true
        if place == 1 { data.meta.stats[Stat.raceWins.rawValue, default: 0] += 1 }
        data.meta.stats[Stat.eventRewards.rawValue, default: 0] += 1
        save()
        Analytics.log("race_finish", ["place": place])
        return grant(RaceEvent.reward(place: place, chests: raceGivesChests), source: "race")
    }

    // MARK: - Двойные выходные

    func canClaimDoubleBonus(_ event: GameEvent) -> Bool {
        !eventState(event.id).bonusDays.contains(Day.key())
    }

    func claimDoubleBonus(_ event: GameEvent) -> Granted? {
        guard canClaimDoubleBonus(event) else { return nil }
        var s = eventState(event.id)
        s.bonusDays.append(Day.key())
        data.meta.events[event.id] = s
        save()
        return grant(Reward(unlimitedMinutes: DoubleEvent.bonusMinutes), source: "double")
    }

    // MARK: - Значок на карте

    var eventsClaimable: Bool {
        activeEvents.contains { eventClaimable($0) }
    }

    /// Есть ли в ивенте что забрать (или гонка с сундуками ждет старта).
    func eventClaimable(_ event: GameEvent) -> Bool {
        switch event.kind {
        case .season, .hunt:
            return tiers(event).indices.contains(where: { canClaimTier(event, $0, pass: false) || canClaimTier(event, $0, pass: true) })
        case .race:
            return canClaimRace || (canStartRace && !raceActive && nextRaceGivesChests)
        case .double:
            return canClaimDoubleBonus(event)
        }
    }
}
