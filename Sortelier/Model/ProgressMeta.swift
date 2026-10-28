import Foundation

/// Мета-прогрессия: статистика, награды, стрик, испытания, задания, ачивки, фоны.
extension PlayerProgress {
    // MARK: - Статистика

    func stat(_ s: Stat) -> Int { data.meta.stats[s.rawValue] ?? 0 }

    func bump(_ s: Stat, by n: Int = 1, save shouldSave: Bool = true) {
        guard n != 0 else { return }
        data.meta.stats[s.rawValue, default: 0] += n
        if shouldSave { save() }
    }

    func record(max s: Stat, _ value: Int) {
        guard value > stat(s) else { return }
        data.meta.stats[s.rawValue] = value
        save()
    }

    /// Итоги уровня одним сохранением.
    func addLevelStats(served: Int, tips: Int, dishes: Int, triples: Int, maxCombo: Int) {
        data.meta.stats[Stat.served.rawValue, default: 0] += served
        data.meta.stats[Stat.tips.rawValue, default: 0] += tips
        data.meta.stats[Stat.dishes.rawValue, default: 0] += dishes
        data.meta.stats[Stat.triples.rawValue, default: 0] += triples
        if maxCombo > stat(.maxCombo) { data.meta.stats[Stat.maxCombo.rawValue] = maxCombo }
        save()
    }

    // MARK: - Выдача наград

    /// Выдает награду. Возвращает, что выдано, с выбранной редкой карточкой.
    @discardableResult
    func grant(_ reward: Reward, source: String) -> Granted {
        data.coins += reward.coins
        for (k, v) in reward.boosters { data.boosters[k, default: 0] += v }
        if reward.lives > 0 { addLife(reward.lives) }
        var card: String?
        var reward = reward
        if reward.rareCard {
            card = drawRareCard()
            if card == nil {
                // все редкие карточки уже есть: вместо карточки монеты
                reward.rareCard = false
                reward.coins += 200
                data.coins += 200
            }
        }
        if let bg = reward.background, !data.meta.backgrounds.contains(bg) {
            data.meta.backgrounds.append(bg)
        }
        if reward.energy > 0 { addEnergy(reward.energy) }
        save()
        if reward.unlimitedMinutes > 0 { addUnlimitedLives(TimeInterval(reward.unlimitedMinutes * 60)) }
        Analytics.log("reward", ["source": source, "coins": reward.coins, "card": card ?? ""])
        return Granted(reward: reward, card: card)
    }

    // MARK: - Редкие карточки

    var rareCards: [String] { data.meta.rareCards }

    func hasRare(_ id: String) -> Bool { data.meta.rareCards.contains(id) }

    private func drawRareCard() -> String? {
        let missing = RareCards.all.filter { !data.meta.rareCards.contains($0) }
        guard let card = missing.randomElement() else { return nil }
        data.meta.rareCards.append(card)
        data.meta.stats[Stat.rareCards.rawValue] = data.meta.rareCards.count
        return card
    }

    // MARK: - Стрик

    var streakDay: Int {
        guard let last = data.meta.streak.lastDay else { return 0 }
        let gap = Day.between(last, Day.key())
        if gap <= 1 { return data.meta.streak.day }
        return gap - 1 <= data.meta.streak.freezes ? data.meta.streak.day : 0
    }

    var playedToday: Bool { data.meta.streak.lastDay == Day.key() }

    /// Стрик сгорит сегодня в полночь, если не пройти уровень.
    var streakAtRisk: Bool { streakDay > 0 && !playedToday }

    var streakFreezes: Int { data.meta.streak.freezes }

    func buyFreeze() -> Bool {
        guard data.meta.streak.freezes < StreakRewards.maxFreezes, spend(StreakRewards.freezePrice) else { return false }
        data.meta.streak.freezes += 1
        save()
        Analytics.log("streak_freeze")
        return true
    }

    /// Засчитывает игровой день. Вызывается при любой победе, награда - только в первый раз за день.
    func registerPlayDay() -> (day: Int, granted: Granted)? {
        let today = Day.key()
        var s = data.meta.streak
        guard s.lastDay != today else { return nil }
        var continues = false
        if let last = s.lastDay {
            let missed = max(0, Day.between(last, today) - 1)
            if missed == 0 {
                continues = true
            } else if missed <= s.freezes {
                s.freezes -= missed
                continues = true
            }
        }
        s.day = continues ? s.day % 7 + 1 : 1
        s.lastDay = today
        data.meta.streak = s
        // длина серии дней без обнуления по циклу: для ачивки
        let run = continues ? (data.meta.stats["streakRun"] ?? 0) + 1 : 1
        data.meta.stats["streakRun"] = run
        if run > stat(.streakBest) { data.meta.stats[Stat.streakBest.rawValue] = run }
        save()
        let granted = grant(StreakRewards.reward(day: s.day), source: "streak")
        Analytics.log("streak_day", ["day": s.day])
        return (s.day, granted)
    }

    // MARK: - Серия шефа

    var chefSeries: Int { data.meta.chefSeries }

    /// Новый уровень пройден. Серия растет, только если на уровне не было поражений.
    func chefWin(level: Int) -> Granted? {
        let key = String(level)
        if data.meta.failed.contains(key) {
            data.meta.failed.removeAll { $0 == key }
            data.meta.chefSeries = 0
            save()
            return nil
        }
        data.meta.chefSeries += 1
        if data.meta.chefSeries > stat(.chefBest) { data.meta.stats[Stat.chefBest.rawValue] = data.meta.chefSeries }
        save()
        guard let reward = ChefSeries.reward(series: data.meta.chefSeries) else { return nil }
        return grant(reward, source: "chef_series")
    }

    func chefFail(level: Int) {
        let key = String(level)
        if !data.meta.failed.contains(key) { data.meta.failed.append(key) }
        data.meta.chefSeries = 0
        save()
    }

    // MARK: - Испытания

    func dailyDone(_ key: String = Day.key()) -> Bool { data.meta.dailyDone.contains(key) }

    func completeDaily(_ key: String) -> Granted? {
        guard !data.meta.dailyDone.contains(key) else { return nil }
        data.meta.dailyDone.append(key)
        data.meta.stats[Stat.dailyDone.rawValue, default: 0] += 1
        save()
        var reward = ChallengeRewards.daily
        reward.rareCard = Double.random(in: 0..<1) < ChallengeRewards.dailyRareChance
        return grant(reward, source: "daily")
    }

    func weeklyDone(_ week: String = Day.weekKey()) -> Int { data.meta.weeklyProgress[week] ?? 0 }

    /// Засчитывает уровень недельного набора. Когда пройдены все 3 - награда.
    func completeWeekly(_ week: String, index: Int) -> Granted? {
        let done = weeklyDone(week)
        guard index == done, done < 3 else { return nil }
        data.meta.weeklyProgress[week] = done + 1
        data.meta.stats[Stat.weeklyLevels.rawValue, default: 0] += 1
        save()
        guard done + 1 == 3 else { return nil }
        data.meta.stats[Stat.weeklyDone.rawValue, default: 0] += 1
        data.meta.weeklyDoneDays.append(Day.key())
        save()
        return grant(ChallengeRewards.weekly, source: "weekly")
    }

    // MARK: - Медаль месяца

    func medalProgress(_ month: String = Day.monthKey()) -> (daily: Int, weekly: Int) {
        let daily = data.meta.dailyDone.filter { $0.hasPrefix(month) }.count
        let weekly = data.meta.weeklyDoneDays.filter { $0.hasPrefix(month) }.count
        return (daily, weekly)
    }

    func medalReady(_ month: String = Day.monthKey()) -> Bool {
        let p = medalProgress(month)
        return !data.meta.medals.contains(month) && p.daily >= ChallengeRewards.medalDaily && p.weekly >= ChallengeRewards.medalWeekly
    }

    func medalClaimed(_ month: String = Day.monthKey()) -> Bool { data.meta.medals.contains(month) }

    var medals: [String] { data.meta.medals }

    func claimMedal(_ month: String = Day.monthKey()) -> Granted? {
        guard medalReady(month) else { return nil }
        data.meta.medals.append(month)
        save()
        return grant(ChallengeRewards.medal, source: "medal")
    }

    // MARK: - Приветственные задания

    /// Запоминает день первого запуска для набора новичка.
    func ensureWelcomeStart() {
        guard data.meta.welcomeStart == nil else { return }
        data.meta.welcomeStart = Day.key()
        save()
    }

    /// День набора новичка, начиная с 1.
    var welcomeDay: Int {
        Day.between(data.meta.welcomeStart ?? Day.key(), Day.key()) + 1
    }

    var welcomeActive: Bool {
        !data.meta.welcomeGrand && welcomeDay <= WelcomeQuests.lifetimeDays
    }

    func questUnlocked(_ q: Quest) -> Bool { q.day <= welcomeDay }

    func questDone(_ q: Quest) -> Bool { stat(q.stat) >= q.target }

    func questClaimed(_ q: Quest) -> Bool { data.meta.questsClaimed.contains(q.id) }

    func canClaim(_ q: Quest) -> Bool { questUnlocked(q) && questDone(q) && !questClaimed(q) }

    func claim(_ q: Quest) -> Granted? {
        guard canClaim(q) else { return nil }
        data.meta.questsClaimed.append(q.id)
        save()
        return grant(q.reward, source: "quest")
    }

    var welcomeGrandReady: Bool {
        !data.meta.welcomeGrand && WelcomeQuests.all.allSatisfy { questClaimed($0) }
    }

    func claimWelcomeGrand() -> Granted? {
        guard welcomeGrandReady else { return nil }
        data.meta.welcomeGrand = true
        save()
        return grant(WelcomeQuests.grand, source: "welcome")
    }

    var questsClaimable: Bool {
        welcomeActive && (WelcomeQuests.all.contains { canClaim($0) } || welcomeGrandReady)
    }

    // MARK: - Ачивки

    func claimedTiers(_ a: Achievement) -> Int { data.meta.achievementTiers[a.id] ?? 0 }

    func canClaim(_ a: Achievement) -> Bool {
        let tier = claimedTiers(a)
        return tier < a.tiers.count && stat(a.stat) >= a.tiers[tier]
    }

    func claim(_ a: Achievement) -> Granted? {
        guard canClaim(a) else { return nil }
        let tier = claimedTiers(a)
        data.meta.achievementTiers[a.id] = tier + 1
        save()
        return grant(Achievements.reward(tier: tier), source: "achievement")
    }

    var achievementsClaimable: Bool { Achievements.all.contains { canClaim($0) } }

    // MARK: - Фоны

    var background: String { data.meta.background }

    func owns(_ style: KitchenStyle) -> Bool { data.meta.backgrounds.contains(style.id) }

    func buy(_ style: KitchenStyle) -> Bool {
        guard style.source == .shop, !owns(style), spend(style.price) else { return false }
        data.meta.backgrounds.append(style.id)
        data.meta.background = style.id
        save()
        Analytics.log("background_buy", ["id": style.id])
        return true
    }

    func equip(_ style: KitchenStyle) {
        guard owns(style) else { return }
        data.meta.background = style.id
        save()
    }

    // MARK: - Уведомления

    var notificationsAsked: Bool { data.meta.notificationsAsked }

    func markNotificationsAsked() {
        data.meta.notificationsAsked = true
        save()
    }

    // MARK: - Энергия (мини-игра, этап 5)

    func addEnergy(_ amount: Int) {
        data.meta.stats["energyBonus", default: 0] += amount
    }
}
