import SwiftUI

// MARK: - Плитки наград

/// Подпись под иконкой награды: число, "×3", длительность. Названия не пишем: они длинные и обрезаются,
/// полное название и описание открываются по тапу.
func rewardAmount(_ item: RewardItem, short: Bool = true) -> String {
    switch item {
    case let .coins(n): return n >= 10000 ? String(format: "%.0fK", Double(n) / 1000) : "\(n)"
    case let .booster(_, n): return "×\(n)"
    case let .unlimited(m): return short ? Lang.durationShort(minutes: m) : Lang.duration(minutes: m)
    case let .lives(n): return "+\(n)"
    case let .energy(n): return "+\(n)"
    case let .chest(_, n): return "×\(n)"
    case let .market(_, n): return "×\(n)"
    case .background, .guest: return ""
    }
}

/// Плитка одной награды: квадрат на бумажной вставке, объемная иконка и число. Тап - описание.
struct RewardTile: View {
    let item: RewardItem
    var size: CGFloat = 64
    var dimmed = false

    var body: some View {
        Button { RewardInfo.show(item) } label: {
            VStack(spacing: 0) {
                RewardItemIcon(item: item, size: size * 0.56)
                    .frame(height: size * 0.6)
                let amount = rewardAmount(item)
                if !amount.isEmpty {
                    Text(amount)
                        .font(Theme.rounded(size * 0.23, .black))
                        .foregroundColor(Theme.brown)
                        .lineLimit(1)
                        .minimumScaleFactor(0.6)
                        .monospacedDigit()
                }
            }
            .frame(width: size, height: size * 1.06)
            .background(InsetBackground(radius: size * 0.22))
            .opacity(dimmed ? 0.55 : 1)
            .contentShape(Rectangle())
        }
        .buttonStyle(PressScaleStyle())
    }
}

/// Награда рядами одинаковых плиток по центру. Прежнее имя оставлено для всех экранов.
struct RewardChips: View {
    let reward: Reward
    var card: String?
    var perRow = 4
    var tileWidth: CGFloat = 64
    /// Компактно: мелкие плитки (заказы кладовой).
    var compact = false

    var body: some View {
        let size: CGFloat = compact ? 44 : min(max(tileWidth, 52), 72)
        let items = reward.items
        let per = max(1, compact ? 6 : perRow)
        let rows = stride(from: 0, to: items.count, by: per).map { Array(items[$0..<min($0 + per, items.count)]) }
        return VStack(spacing: 8) {
            ForEach(rows.indices, id: \.self) { r in
                HStack(spacing: 8) {
                    ForEach(rows[r]) { item in RewardTile(item: item, size: size) }
                }
            }
        }
        .frame(maxWidth: .infinity)
    }
}

/// Награда в одну строку мелкими значками с числом: для клеток шкал и лент.
struct RewardMini: View {
    let reward: Reward
    var icon: CGFloat = 30
    var max = 2

    var body: some View {
        let items = reward.items
        let shown = Array(items.prefix(items.count > max ? max - 1 : max))
        let rest = items.count - shown.count
        HStack(spacing: 4) {
            ForEach(shown) { item in
                Button { RewardInfo.show(item) } label: {
                    VStack(spacing: 0) {
                        RewardItemIcon(item: item, size: icon)
                            .frame(height: icon)
                        Text(rewardAmount(item))
                            .font(Theme.rounded(12, .black))
                            .foregroundColor(Theme.brown)
                            .lineLimit(1)
                            .minimumScaleFactor(0.6)
                    }
                }
                .buttonStyle(PressScaleStyle())
            }
            if rest > 0 {
                Text("+\(rest)")
                    .font(Theme.rounded(13, .black))
                    .foregroundColor(Theme.brownSoft)
            }
        }
    }
}

// MARK: - Подписи и мелочи

/// Строка "значок + текст" на бумаге: время до конца, счетчики.
struct InfoLabel: View {
    let icon: String
    let text: String
    var color: Color = Theme.brownSoft
    var size: CGFloat = 13

    var body: some View {
        HStack(spacing: 4) {
            if let sprite = GameIcon.sprite(for: icon) {
                SpriteImage(name: sprite, size: size * 1.5)
            } else {
                Image(systemName: icon).font(.system(size: size, weight: .heavy))
            }
            Text(text).font(Theme.rounded(size, .heavy)).monospacedDigit()
        }
        .foregroundColor(color)
    }
}

/// Таймер на темной плашке: сколько осталось.
struct TimerBadge: View {
    let text: String

    var body: some View {
        HStack(spacing: 4) {
            Image(systemName: "clock.fill").font(.system(size: 11, weight: .heavy))
            Text(text).font(Theme.rounded(12, .black)).monospacedDigit()
        }
        .foregroundColor(Color(red: 1.0, green: 0.91, blue: 0.68))
        .padding(.horizontal, 9)
        .frame(height: 24)
        .background(Capsule().fill(Theme.woodDark.opacity(0.85)))
    }
}

/// Заголовок секции на экране: лента по центру.
struct SectionTitle: View {
    let title: String
    var color: Color = Theme.red

    var body: some View {
        Ribbon(title: title, color: color, dark: color == Theme.red ? Theme.ribbonDark : Theme.woodDark, size: 17)
            .frame(maxWidth: .infinity)
            .padding(.top, 6)
            .padding(.bottom, 2)
    }
}
