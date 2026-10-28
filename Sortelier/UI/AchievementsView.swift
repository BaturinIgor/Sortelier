import SwiftUI

// MARK: - Достижения

/// Достижения по категориям: сверху общий счетчик звезд и лента наград за звезды.
/// Выполненные стоят наверху; после "Забрать" карточка остается на месте, пока открыто окно награды,
/// потом плавно уезжает на свое место.
struct AchievementsContent: View {
    @Binding var granted: Granted?
    @Binding var frozen: [String]?
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var category: Achievement.Category = .kitchen

    private var shown: [Achievement] {
        let sorted = progress.sortedAchievements(category)
        guard let frozen = frozen else { return sorted }
        let rest = sorted.filter { !frozen.contains($0.id) }
        return frozen.compactMap { id in sorted.first { $0.id == id } } + rest
    }

    private var categories: [SegmentPicker<Achievement.Category>.Item] {
        Achievement.Category.allCases.map { c in
            .init(id: c, title: lang.t("ach.cat." + c.rawValue), icon: nil,
                  badge: Achievements.all.contains { $0.category == c && progress.canClaim($0) })
        }
    }

    var body: some View {
        VStack(spacing: 14) {
            starTrack
            SegmentPicker(items: categories, selection: Binding(get: { category }, set: { c in
                frozen = nil
                category = c
            }))
            ForEach(shown) { a in row(a) }
        }
    }

    // MARK: Звезды и лента наград

    private var starTrack: some View {
        let stars = progress.achievementStars
        let milestones = AchievementTrack.milestones
        let current = milestones.firstIndex { !progress.milestoneClaimed($0) } ?? max(0, milestones.count - 1)
        return MetaCard(highlight: milestones.contains { progress.canClaimMilestone($0) }) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 10) {
                    SpriteImage(name: "icon_star", size: 48)
                    VStack(alignment: .leading, spacing: 1) {
                        Text(lang.t("achv.total", stars, Achievements.maxStars))
                            .font(Theme.rounded(18, .black))
                            .foregroundColor(Theme.brown)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                        Text(lang.t("achv.total.text"))
                            .font(Theme.rounded(12, .semibold))
                            .foregroundColor(Theme.brownSoft)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                StepTrack(count: milestones.count, current: current, cellWidth: 92) { i in
                    milestoneColumn(milestones[i], stars: stars)
                }
            }
        }
    }

    private func milestoneColumn(_ m: AchievementTrack.Milestone, stars: Int) -> some View {
        let reached = stars >= m.stars
        let claimed = progress.milestoneClaimed(m)
        return VStack(spacing: 6) {
            ZStack {
                Capsule()
                    .fill(reached ? Theme.gold : Theme.woodDark.opacity(0.35))
                    .frame(width: 104, height: 8)
                HStack(spacing: 1) {
                    SpriteImage(name: "icon_star", size: 20)
                    Text("\(m.stars)").font(Theme.rounded(14, .black)).foregroundColor(reached ? .white : Theme.brownSoft)
                        .modifier(Outline(color: reached ? Theme.woodDark : .clear, width: 1))
                }
                .padding(.horizontal, 8)
                .frame(height: 30)
                .background(
                    ZStack {
                        Capsule().fill(reached ? Color(red: 0.95, green: 0.64, blue: 0.23) : Theme.cream)
                        Capsule().strokeBorder(reached ? Theme.woodDark : Theme.chipBorder, lineWidth: 2.5)
                    }
                )
            }
            .frame(width: 92, height: 32)
            VStack(spacing: 4) {
                RewardMini(reward: m.reward, icon: 34)
                    .frame(height: 56)
                    .opacity(claimed ? 0.5 : 1)
                Group {
                    if claimed {
                        SpriteImage(name: "icon_check", size: 28)
                    } else if reached {
                        Button(lang.t("common.claim")) { granted = progress.claimMilestone(m) }
                            .buttonStyle(GameButtonStyle(palette: .green, height: 30, fontSize: 13, radius: 10))
                    } else {
                        SpriteImage(name: "icon_lock", size: 24).opacity(0.8)
                    }
                }
                .frame(height: 34)
            }
            .padding(.top, 8)
            .padding(.horizontal, 5)
            .frame(width: 92, height: 108)
            .background(InsetBackground(radius: 14, color: reached && !claimed ? Color(red: 1.0, green: 0.88, blue: 0.5) : Theme.cream))
        }
    }

    // MARK: Карточка достижения

    private func row(_ a: Achievement) -> some View {
        let tier = progress.claimedTiers(a)
        let value = progress.stat(a.stat)
        let complete = tier >= a.tiers.count
        let target = complete ? a.tiers.last ?? 1 : a.tiers[tier]
        return MetaCard(highlight: progress.canClaim(a)) {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 12) {
                    ZStack {
                        Circle().fill(Theme.woodDark).offset(y: 3)
                        Circle().fill(LinearGradient(colors: complete ? [Color(red: 1.0, green: 0.88, blue: 0.45), Color(red: 0.95, green: 0.64, blue: 0.23)]
                                                     : [ButtonPalette.orange.top, ButtonPalette.orange.bottom],
                                                     startPoint: .top, endPoint: .bottom))
                        Circle().strokeBorder(Theme.woodDark, lineWidth: 2.5)
                        Image(systemName: a.symbol)
                            .font(.system(size: 20, weight: .heavy))
                            .foregroundColor(.white)
                            .modifier(Outline(color: ButtonPalette.orange.dark, width: 1))
                    }
                    .frame(width: 48, height: 48)
                    VStack(alignment: .leading, spacing: 3) {
                        Text(lang.t("ach." + a.id)).font(Theme.rounded(17, .black)).foregroundColor(Theme.brown)
                            .lineLimit(1)
                            .minimumScaleFactor(0.7)
                        StarsRow(count: tier, size: 13, spacing: 1, total: a.tiers.count)
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
                        .font(Theme.rounded(13, .black)).foregroundColor(Theme.brownSoft).monospacedDigit()
                }
                if !complete {
                    RewardChips(reward: Achievements.reward(tier: tier), perRow: 4, tileWidth: 60)
                    if progress.canClaim(a) {
                        Button(lang.t("common.claim")) {
                            frozen = shown.map(\.id)
                            granted = progress.claim(a)
                        }
                        .buttonStyle(GameButtonStyle(palette: .green))
                    }
                }
            }
        }
        .id(a.id)
    }
}

// MARK: - Фоны

/// Фоны кухни сеткой по три: превью целиком, название в две строки, внизу цена или откуда взять.
struct BackgroundsContent: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    private let columns = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        VStack(spacing: 12) {
            Text(lang.t("bg.subtitle"))
                .font(Theme.rounded(14, .semibold))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(12)
                .frame(maxWidth: .infinity)
                .background(InsetBackground())
            LazyVGrid(columns: columns, spacing: 12) {
                ForEach(KitchenStyle.all) { style in tile(style) }
            }
        }
    }

    private func tile(_ style: KitchenStyle) -> some View {
        let owned = progress.owns(style)
        let equipped = progress.background == style.id
        let ratio: CGFloat = 1170.0 / 2532.0
        return VStack(spacing: 6) {
            Image(uiImage: Art.image(KitchenStyle.image(style.id)))
                .resizable()
                .aspectRatio(ratio, contentMode: .fit)
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(equipped ? Theme.orange : Theme.paperBorder, lineWidth: equipped ? 4 : 2))
                .overlay(alignment: .topTrailing) {
                    if equipped { SpriteImage(name: "icon_check", size: 30).offset(x: 6, y: -6) }
                }
                .saturation(owned ? 1 : 0.85)
            Text(lang.t("bg." + style.id))
                .font(Theme.rounded(13, .black))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.8)
                .frame(height: 36)
            action(style, owned: owned, equipped: equipped)
                .frame(height: 38)
        }
        .padding(8)
        .background(PaperBackground(radius: 16, highlight: equipped))
    }

    @ViewBuilder
    private func action(_ style: KitchenStyle, owned: Bool, equipped: Bool) -> some View {
        if equipped {
            Text(lang.t("bg.equipped"))
                .font(Theme.rounded(13, .black))
                .foregroundColor(Theme.green)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
        } else if owned {
            Button(lang.t("bg.equip")) {
                progress.equip(style)
                Audio.shared.play(.place)
            }
            .buttonStyle(GameButtonStyle(palette: .orange, height: 32, fontSize: 14, radius: 10))
        } else if style.source == .shop {
            Button {
                if progress.buy(style) {
                    Audio.shared.play(.chest)
                    Toast.success(lang.t("bg.bought"))
                } else {
                    Toast.error(lang.t("common.nocoins"))
                }
            } label: {
                HStack(spacing: 3) { CoinIcon(size: 18); Text("\(style.price)") }
            }
            .buttonStyle(GameButtonStyle(palette: .green, height: 32, fontSize: 14, radius: 10))
        } else {
            Text(lang.t("bg.source." + sourceKey(style)))
                .font(Theme.rounded(11, .heavy))
                .foregroundColor(Theme.brownSoft)
                .multilineTextAlignment(.center)
                .lineLimit(2)
                .minimumScaleFactor(0.7)
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
}
