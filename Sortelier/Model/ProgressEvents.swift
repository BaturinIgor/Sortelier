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
                if s.joined != nil && s.finished == nil {
                    s.wins += 1
                    if s.wins >= RaceEvent.goal { s.finished = date }
                    gains.append(EventGain(id: event.id, kind: .race, theme: "", amount: 1, total: s.wins))
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

    func joinRace(_ event: GameEvent) {
        var s = eventState(event.id)
        guard s.joined == nil else { return }
        s.joined = Date()
        data.meta.events[event.id] = s
        save()
        Analytics.log("race_join")
    }

    struct RaceRow: Identifiable {
        let id: String
        let name: String
        let look: Int?
        let wins: Int
        let finished: Date?
        let isPlayer: Bool
    }

    func raceStandings(_ event: GameEvent) -> [RaceRow] {
        let s = eventState(event.id)
        guard let joined = s.joined else { return [] }
        let at = min(now, event.end)
        var rows = RaceEvent.rivals(eventId: event.id).map { r -> RaceRow in
            let finish = r.finishTime(joined: joined)
            return RaceRow(id: "rival\(r.id)", name: r.name, look: r.look, wins: r.wins(joined: joined, now: at),
                           finished: finish <= at ? finish : nil, isPlayer: false)
        }
        rows.append(RaceRow(id: "player", name: "", look: nil, wins: s.wins, finished: s.finished, isPlayer: true))
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
    func racePlace(_ event: GameEvent) -> Int? {
        guard eventState(event.id).finished != nil else { return nil }
        return (raceStandings(event).firstIndex { $0.isPlayer } ?? 4) + 1
    }

    func canClaimRace(_ event: GameEvent) -> Bool {
        racePlace(event) != nil && !eventState(event.id).raceClaimed
    }

    func claimRace(_ event: GameEvent) -> Granted? {
        guard canClaimRace(event), let place = racePlace(event) else { return nil }
        var s = eventState(event.id)
        s.raceClaimed = true
        data.meta.events[event.id] = s
        save()
        return grant(RaceEvent.reward(place: place), source: "race")
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
        for event in activeEvents {
            switch event.kind {
            case .season, .hunt:
                if tiers(event).indices.contains(where: { canClaimTier(event, $0, pass: false) || canClaimTier(event, $0, pass: true) }) {
                    return true
                }
            case .race:
                if canClaimRace(event) || eventState(event.id).joined == nil { return true }
            case .double:
                if canClaimDoubleBonus(event) { return true }
            }
        }
        return false
    }
}
