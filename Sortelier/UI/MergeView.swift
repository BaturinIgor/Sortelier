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
            StrokeText(text: lang.t("merge.title"), size: 21, weight: .black, color: Color(red: 1.0, green: 0.95, blue: 0.84),
                       stroke: Theme.woodDark, width: 1.5, drop: 2)
                .lineLimit(1)
                .minimumScaleFactor(0.6)
                .padding(.horizontal, 14)
                .frame(height: 42)
                .background(
                    ZStack {
                        Capsule().fill(Theme.woodDark).offset(y: 3)
                        WoodBackground().clipShape(Capsule())
                        Capsule().strokeBorder(Theme.woodDark, lineWidth: 2.5)
                    }
                )
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
        .background(PaperBackground(radius: 16))
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
            }
            .buttonStyle(GameButtonStyle(palette: .green, height: 36, fontSize: 15, fullWidth: false, radius: 12))
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
                        Toast.success(lang.t("merge.sold", coins))
                        focus = nil
                        model.scene.clearSelection()
                    }
                } label: {
                    HStack(spacing: 4) {
                        Text(lang.t("merge.sell"))
                        CoinIcon(size: 18)
                        Text("\(item.sellPrice)")
                    }
                }
                .buttonStyle(GameButtonStyle(palette: .orange, height: 32, fontSize: 14, fullWidth: false, radius: 11))
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
            chevron
            ForEach(0...last, id: \.self) { i in
                SpriteImage(name: items[i], size: size, silhouette: i > progressTier(item.chain))
                    .padding(2)
                    .background(RoundedRectangle(cornerRadius: 8).fill(i == highlight ? Theme.gold.opacity(0.45) : Color.clear))
                if i < last { chevron }
            }
        }
    }

    private var chevron: some View {
        BackArrowShape()
            .stroke(Theme.brownSoft, style: StrokeStyle(lineWidth: 2, lineCap: .round, lineJoin: .round))
            .frame(width: 5, height: 9)
            .rotationEffect(.degrees(180))
            .flipsForRightToLeftLayoutDirection(true)
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
                            SpriteImage(name: "icon_check", size: 18)
                        }
                    }
                }
            }
            .frame(height: 48)
            RewardChips(reward: order.reward, perRow: 2, tileWidth: 46, compact: true)
                .frame(height: 44)
            Button(lang.t("merge.give")) { deliver(order) }
                .buttonStyle(GameButtonStyle(palette: ready ? .green : .gray, height: 30, fontSize: 13, radius: 10))
                .disabled(!ready)
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(PaperBackground(radius: 16, highlight: ready || focused == order.id))
        .contentShape(Rectangle())
        .onTapGesture { select(order) }
    }
}

/// Энергия: число и под ним мелко таймер до следующей единицы.
struct EnergyPill: View {
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        HStack(spacing: 5) {
            SpriteImage(name: "icon_energy", size: 28)
            VStack(alignment: .leading, spacing: -2) {
                Text("\(progress.energy)")
                    .font(Theme.rounded(16, .black))
                    .foregroundColor(Color(red: 1.0, green: 0.91, blue: 0.68))
                    .monospacedDigit()
                if let next = progress.nextEnergyIn {
                    Text(Lang.time(next))
                        .font(Theme.rounded(10, .heavy))
                        .foregroundColor(Color(red: 1.0, green: 0.91, blue: 0.68).opacity(0.8))
                        .monospacedDigit()
                }
            }
        }
        .padding(.leading, 4)
        .padding(.trailing, 12)
        .frame(height: 38)
        .background(
            ZStack {
                Capsule().fill(Theme.woodDark)
                Capsule().strokeBorder(Color.black.opacity(0.35), lineWidth: 2)
            }
        )
    }
}

struct EnergyPopup: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("merge.energy", progress.energy, MergeBalance.maxEnergy), close: close) {
                VStack(spacing: 12) {
                    SpriteImage(name: "icon_energy", size: 84)
                    if let next = progress.nextEnergyIn {
                        Text(lang.t("merge.energy.next", Lang.time(next)))
                            .font(Theme.rounded(15, .heavy))
                            .foregroundColor(Theme.brown)
                            .monospacedDigit()
                    }
                    Text(lang.t("merge.energy.text"))
                        .font(Theme.rounded(13, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button {
                        Ads.shared.showRewarded(placement: "energy") { ok in
                            if ok { progress.addMergeEnergy(MergeBalance.adEnergy) } else { Toast.error(lang.t("ads.limit")) }
                        }
                    } label: {
                        HStack(spacing: 6) { AdIcon(); Text(lang.t("merge.energy.ad", MergeBalance.adEnergy)) }
                    }
                    .buttonStyle(GameButtonStyle(palette: .green))
                    AdsLeftLabel()
                    Button {
                        if !progress.buyEnergy() { Toast.error(lang.t("common.nocoins")) }
                    } label: {
                        HStack(spacing: 6) { Text(lang.t("merge.energy.buy", MergeBalance.buyEnergy)); CoinIcon(size: 24); Text("\(MergeBalance.buyEnergyPrice)") }
                    }
                    .buttonStyle(GameButtonStyle(palette: .orange))
                }
            }
        }
    }
}
