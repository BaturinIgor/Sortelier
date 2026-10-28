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
struct MergeView: View {
    let close: () -> Void
    @StateObject private var model = MergeModel()
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var selected: MergeItem?
    @State private var granted: Granted?
    @State private var showEnergy = false
    @State private var toast: String?

    var body: some View {
        ZStack {
            KitchenBackground(veil: 0.2)
            VStack(spacing: 10) {
                header
                MergeOrdersRow(game: model.game) { order in
                    granted = model.game.deliver(order)
                    if granted != nil { Audio.shared.play(.customer) }
                }
                SpriteView(scene: model.scene, options: [.allowsTransparency])
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                info
            }
            .padding(.horizontal, 12)
            .padding(.bottom, 8)
            if let text = toast {
                Text(text)
                    .font(Theme.rounded(15, .bold))
                    .foregroundColor(.white)
                    .padding(.horizontal, 16)
                    .padding(.vertical, 10)
                    .background(Capsule().fill(Theme.brown.opacity(0.9)))
                    .frame(maxHeight: .infinity, alignment: .bottom)
                    .padding(.bottom, 120)
            }
            if showEnergy {
                EnergyPopup { showEnergy = false }
            }
            if let granted = granted {
                RewardPopup(title: lang.t("merge.order.done"), granted: granted) { self.granted = nil }
            }
        }
        .onAppear {
            model.scene.onSelect = { item in selected = item }
            model.scene.onSpawnFail = { result in
                switch result {
                case .noEnergy: showEnergy = true
                case .boardFull: flash(lang.t("merge.full"))
                case .spawned: break
                }
            }
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            CircleIconButton(symbol: "xmark", size: 42, action: close)
            Text(lang.t("merge.title"))
                .font(Theme.rounded(20, .heavy))
                .foregroundColor(Theme.brown)
                .padding(.horizontal, 12)
                .frame(height: 40)
                .background(Capsule().fill(Theme.card))
            Spacer()
            Button { showEnergy = true } label: { EnergyPill() }.buttonStyle(.plain)
            CoinsPill()
        }
        .padding(.top, 6)
    }

    @ViewBuilder
    private var info: some View {
        if let item = selected {
            VStack(spacing: 6) {
                Text(itemName(item))
                    .font(Theme.rounded(15, .heavy))
                    .foregroundColor(Theme.brown)
                HStack(spacing: 2) {
                    ForEach(item.chain.items.indices, id: \.self) { i in
                        SpriteImage(name: item.chain.items[i], size: 30, silhouette: i > progressTier(item.chain))
                            .padding(2)
                            .background(RoundedRectangle(cornerRadius: 8).fill(i == item.tier ? Theme.gold.opacity(0.4) : Color.clear))
                        if i < item.chain.items.count - 1 {
                            Image(systemName: "chevron.right").font(.system(size: 8, weight: .bold)).foregroundColor(Theme.brownSoft)
                        }
                    }
                }
            }
            .padding(10)
            .frame(maxWidth: .infinity)
            .background(RoundedRectangle(cornerRadius: 16).fill(Theme.card.opacity(0.95)))
        } else {
            Text(lang.t("merge.hint"))
                .font(Theme.rounded(13, .semibold))
                .foregroundColor(Theme.brownSoft)
                .multilineTextAlignment(.center)
                .padding(10)
                .frame(maxWidth: .infinity)
                .background(RoundedRectangle(cornerRadius: 16).fill(Theme.card.opacity(0.95)))
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

    private func flash(_ text: String) {
        withAnimation { toast = text }
        DispatchQueue.main.asyncAfter(deadline: .now() + 1.6) { withAnimation { toast = nil } }
    }
}

struct MergeOrdersRow: View {
    @ObservedObject var game: MergeGame
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
            RewardChips(reward: order.reward)
                .scaleEffect(0.8)
                .frame(height: 30)
            Button(lang.t("merge.give")) { deliver(order) }
                .font(Theme.rounded(13, .heavy))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 30)
                .background(Capsule().fill(ready ? Theme.green : Theme.brownSoft.opacity(0.5)))
                .disabled(!ready)
        }
        .padding(8)
        .frame(maxWidth: .infinity)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card)
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(ready ? Theme.green : Color.clear, lineWidth: 2)))
    }
}

struct EnergyPill: View {
    @EnvironmentObject private var progress: PlayerProgress

    var body: some View {
        Pill(text: label) {
            Image(systemName: "bolt.fill").font(.system(size: 18)).foregroundColor(Theme.gold)
        }
    }

    private var label: String {
        if let next = progress.nextEnergyIn { return "\(progress.energy) · " + Lang.time(next) }
        return "\(progress.energy)"
    }
}

struct EnergyPopup: View {
    let close: () -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @State private var message: String?

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
                            if ok { progress.addMergeEnergy(MergeBalance.adEnergy) } else { message = lang.t("ads.limit") }
                        }
                    } label: {
                        HStack { Image(systemName: "play.rectangle.fill"); Text(lang.t("merge.energy.ad", MergeBalance.adEnergy)) }
                    }
                    .buttonStyle(BigButtonStyle(color: Theme.green))
                    AdsLeftLabel()
                    Button {
                        if !progress.buyEnergy() { message = lang.t("common.nocoins") }
                    } label: {
                        HStack { Text(lang.t("merge.energy.buy", MergeBalance.buyEnergy)); CoinIcon(size: 20); Text("\(MergeBalance.buyEnergyPrice)") }
                    }
                    .buttonStyle(BigButtonStyle())
                    if let message = message {
                        Text(message).font(Theme.rounded(14, .semibold)).foregroundColor(Theme.red)
                    }
                    Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle(color: Theme.brownSoft))
                }
                .frame(maxWidth: 300)
            }
        }
    }
}
