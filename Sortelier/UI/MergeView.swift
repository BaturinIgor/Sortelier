import SwiftUI
import SpriteKit

final class MergeModel: ObservableObject {
    let game: MergeGame
    let scene: MergeScene

    init() {
        game = MergeGame()
        scene = MergeScene(game: game)
    }
}

/// Экран кладовой: заказы сверху, доска, подсказка по цепочке снизу.
/// Высоты панелей фиксированы, чтобы доска не прыгала, когда меняется подсказка.
struct MergeView: View {
    let close: () -> Void
    @StateObject private var model = MergeModel()
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    /// Что показать внизу: предмет на доске (с номером клетки) или нужное для заказа.
    @State private var focus: Focus?
    @State private var granted: Granted?
    @State private var showEnergy = false

    enum Focus: Equatable {
        case cell(Int, MergeItem)
        case order(MergeOrder)
    }

    private let infoHeight: CGFloat = 112

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.2)
            VStack(spacing: 10) {
                header
                MergeOrdersRow(game: model.game, focused: focusedOrder, select: { order in
                    focus = .order(order)
                    model.scene.clearSelection()
                }, deliver: { order in
                    granted = model.game.deliver(order)
                    if granted != nil {
                        Audio.shared.play(.customer)
                        focus = nil
                    }
                })
                .frame(height: 150)
                SpriteView(scene: model.scene, options: [.allowsTransparency])
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                info
                    .frame(height: infoHeight)
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 8)
            if showEnergy {
                EnergyPopup { showEnergy = false }
            }
            if let granted = granted {
                RewardPopup(title: lang.t("merge.order.done"), granted: granted) { self.granted = nil }
            }
        }
        .onAppear {
            model.scene.onSelect = { index, item in
                if let index = index, let item = item { focus = .cell(index, item) } else { focus = nil }
            }
            model.scene.onSpawnFail = { result in
                switch result {
                case .noEnergy: showEnergy = true
                case .boardFull: Toast.error(lang.t("merge.full"))
                case .spawned: break
                }
            }
        }
    }

    private var focusedOrder: Int? {
        if case let .order(order) = focus { return order.id }
        return nil
    }

    private var header: some View {
        HStack(spacing: 8) {
            CircleIconButton(symbol: "xmark", size: 42, action: close)
            Text(lang.t("merge.title"))
                .font(Theme.rounded(20, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .padding(.horizontal, 12)
                .frame(height: 40)
                .background(Capsule().fill(Theme.card))
                .layoutPriority(1)
            Spacer(minLength: 4)
            Button { showEnergy = true } label: { EnergyPill() }.buttonStyle(.plain)
            CoinsPill()
        }
        .padding(.top, 6)
    }

    @ViewBuilder
    private var info: some View {
        Group {
            switch focus {
            case let .cell(index, item):
                cellInfo(index, item)
            case let .order(order):
                orderInfo(order)
            case nil:
                hintInfo
            }
        }
        .padding(10)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(RoundedRectangle(cornerRadius: 16).fill(Theme.card.opacity(0.95)))
    }

    private var hintInfo: some View {
        VStack(spacing: 8) {
            Text(lang.t("merge.hint"))
                .font(Theme.rounded(13, .semibold))
                .foregroundColor(Theme.brownSoft)
                .multilineTextAlignment(.center)
                .lineLimit(3)
                .minimumScaleFactor(0.8)
            Button {
                Ads.shared.showRewarded(placement: "merge_supply") { ok in
                    guard ok else { return Toast.error(lang.t("ads.limit")) }
                    let added = model.game.addSupply()
                    if added == 0 { Toast.error(lang.t("merge.full")) } else { Audio.shared.play(.chest) }
                }
            } label: {
                HStack(spacing: 6) {
                    AdIcon()
                    Text(lang.t("merge.supply", MergeBalance.supplyItems))
                }
                .font(Theme.rounded(14, .heavy))
                .foregroundColor(.white)
                .padding(.horizontal, 14)
                .frame(height: 34)
                .background(Capsule().fill(Theme.green))
            }
            .buttonStyle(.plain)
        }
    }

    private func cellInfo(_ index: Int, _ item: MergeItem) -> some View {
        VStack(spacing: 6) {
            HStack {
                Text(itemName(item))
                    .font(Theme.rounded(15, .heavy))
                    .foregroundColor(Theme.brown)
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
                Spacer()
                Button {
                    let coins = model.game.sell(at: index)
                    if coins > 0 {
                        Audio.shared.play(.coin)
                        Toast.success(lang.t("merge.sold", coins), icon: "bitcoinsign.circle.fill")
                        focus = nil
                        model.scene.clearSelection()
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text(lang.t("merge.sell"))
                        CoinIcon(size: 16)
                        Text("\(item.sellPrice)")
                    }
                    .font(Theme.rounded(13, .heavy))
                    .foregroundColor(.white)
                    .padding(.horizontal, 12)
                    .frame(height: 30)
                    .background(Capsule().fill(Theme.orange))
                }
                .buttonStyle(.plain)
            }
            chainRow(item, highlight: item.tier)
        }
    }

    private func orderInfo(_ order: MergeOrder) -> some View {
        VStack(spacing: 6) {
            Text(lang.t("merge.order.how"))
                .font(Theme.rounded(14, .heavy))
                .foregroundColor(Theme.brown)
            ForEach(order.needs.indices, id: \.self) { i in
                chainRow(order.needs[i], highlight: order.needs[i].tier, upTo: order.needs[i].tier)
            }
        }
    }

    /// Цепочка от первой ступени: подсвечена нужная, дальше нужной в заказе не показываем.
    private func chainRow(_ item: MergeItem, highlight: Int, upTo: Int? = nil) -> some View {
        let items = item.chain.items
        let last = min(items.count - 1, upTo ?? items.count - 1)
        let size: CGFloat = last >= 6 ? 28 : 32
        return HStack(spacing: 2) {
            SpriteImage(name: item.chain.generator, size: size)
            Image(systemName: "chevron.right").font(.system(size: 8, weight: .bold)).foregroundColor(Theme.brownSoft)
            ForEach(0...last, id: \.self) { i in
                SpriteImage(name: items[i], size: size, silhouette: i > progressTier(item.chain))
                    .padding(2)
                    .background(RoundedRectangle(cornerRadius: 8).fill(i == highlight ? Theme.gold.opacity(0.45) : Color.clear))
                if i < last {
                    Image(systemName: "chevron.right").font(.system(size: 8, weight: .bold)).foregroundColor(Theme.brownSoft)
                }
            }
        }
    }

    /// Ступени выше достигнутой показываем силуэтами: интересно, что дальше.
    private func progressTier(_ chain: MergeChain) -> Int {
        max(model.game.data.bestTier + 1, model.game.data.cells.compactMap { $0 }.filter { $0.chain == chain }.map(\.tier).max() ?? 0)
    }

    private func itemName(_ item: MergeItem) -> String {
        let id = item.sprite
        return id.hasPrefix("dish_") ? lang.dishName(String(id.dropFirst(5))) : lang.itemName(id)
    }
}

struct MergeOrdersRow: View {
    @ObservedObject var game: MergeGame
    let focused: Int?
    let select: (MergeOrder) -> Void
    let deliver: (MergeOrder) -> Void
    @EnvironmentObject private var lang: Lang

    var body: some View {
        HStack(spacing: 8) {
            ForEach(game.data.orders) { order in
                card(order)
            }
        }
    }

    private func card(_ order: MergeOrder) -> some View {
        let ready = game.canDeliver(order)
        return VStack(spacing: 6) {
            HStack(spacing: 2) {
                ForEach(order.needs.indices, id: \.self) { i in
                    ZStack(alignment: .bottomTrailing) {
                        SpriteImage(name: order.needs[i].sprite, size: order.needs.count > 1 ? 36 : 46)
                        if game.has(order.needs[i]) {
                            Image(systemName: "checkmark.circle.fill")
                                .font(.system(size: 14))
                                .foregroundColor(Theme.green)
                                .background(Circle().fill(Color.white))
                        }
                    }
                }
            }
            .frame(height: 48)
            RewardChips(reward: order.reward, perRow: 2, tileWidth: 46, compact: true)
                .frame(height: 44)
            Button(lang.t("merge.give")) { deliver(order) }
                .font(Theme.rounded(13, .heavy))
                .foregroundColor(.white)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
                .frame(maxWidth: .infinity)
                .frame(height: 30)
                .background(Capsule().fill(ready ? Theme.green : Theme.brownSoft.opacity(0.5)))
                .disabled(!ready)
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card)
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous)
                .stroke(ready ? Theme.green : (focused == order.id ? Theme.gold : Color.clear), lineWidth: 2)))
        .contentShape(Rectangle())
        .onTapGesture { select(order) }
    }
}

/// Энергия: число и под ним мелко таймер до следующей единицы.
struct EnergyPill: View {
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        HStack(spacing: 5) {
            Image(systemName: "bolt.fill").font(.system(size: 18)).foregroundColor(Theme.gold)
            VStack(alignment: .leading, spacing: -2) {
                Text("\(progress.energy)")
                    .font(Theme.rounded(16))
                    .foregroundColor(Theme.brown)
                    .monospacedDigit()
                if let next = progress.nextEnergyIn {
                    Text(Lang.time(next))
                        .font(Theme.rounded(10, .bold))
                        .foregroundColor(Theme.brownSoft)
                        .monospacedDigit()
                }
            }
        }
        .padding(.leading, 6)
        .padding(.trailing, 10)
        .frame(height: 36)
        .background(Capsule().fill(Theme.card).shadow(color: Theme.brown.opacity(0.18), radius: 4, y: 2))
    }
}

struct EnergyPopup: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    Image(systemName: "bolt.fill").font(.system(size: 50)).foregroundColor(Theme.gold)
                    Text(lang.t("merge.energy", progress.energy, MergeBalance.maxEnergy))
                        .font(Theme.rounded(22, .heavy))
                        .foregroundColor(Theme.brown)
                    if let next = progress.nextEnergyIn {
                        Text(lang.t("merge.energy.next", Lang.time(next)))
                            .font(Theme.rounded(14, .semibold))
                            .foregroundColor(Theme.brownSoft)
                    }
                    Text(lang.t("merge.energy.text"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                    Button {
                        Ads.shared.showRewarded(placement: "energy") { ok in
                            if ok { progress.addMergeEnergy(MergeBalance.adEnergy) } else { Toast.error(lang.t("ads.limit")) }
                        }
                    } label: {
                        HStack { AdIcon(); Text(lang.t("merge.energy.ad", MergeBalance.adEnergy)) }
                    }
                    .buttonStyle(BigButtonStyle(color: Theme.green))
                    AdsLeftLabel()
                    Button {
                        if !progress.buyEnergy() { Toast.error(lang.t("common.nocoins")) }
                    } label: {
                        HStack { Text(lang.t("merge.energy.buy", MergeBalance.buyEnergy)); CoinIcon(size: 20); Text("\(MergeBalance.buyEnergyPrice)") }
                    }
                    .buttonStyle(BigButtonStyle())
                    Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                }
                .frame(maxWidth: 300)
            }
        }
    }
}
