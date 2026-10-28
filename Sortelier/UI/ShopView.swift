import SwiftUI

/// Ссылки для экрана покупок. Политику опубликуем к релизу, пока она лежит в репозитории.
enum Legal {
    static let terms = URL(string: "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/")!
    static let privacy = URL(string: "https://github.com/BaturinIgor/Sortelier/blob/main/PRIVACY.md")!
}

/// Магазин: VIP, стартовый набор, монеты, наборы и бустеры за монеты.
struct ShopSheet: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @ObservedObject private var store = Store.shared
    @Environment(\.presentationMode) private var presentation
    @State private var granted: Granted?
    @State private var vipActivated = false

    private let columns = [GridItem(.flexible(), spacing: 10), GridItem(.flexible(), spacing: 10)]

    var body: some View {
        ZStack {
            Theme.background.ignoresSafeArea()
            ScrollView(showsIndicators: false) {
                VStack(alignment: .leading, spacing: 14) {
                    SheetHeader(title: lang.t("shop.title"), subtitle: nil) { presentation.wrappedValue.dismiss() }
                    notice
                    VIPCard(buy: buy)
                    if !progress.starterBought { starter }
                    sectionTitle(lang.t("shop.coins"))
                    LazyVGrid(columns: columns, spacing: 10) {
                        ForEach(ShopItem.coinPacks) { item in coinTile(item) }
                    }
                    sectionTitle(lang.t("shop.packs"))
                    packRow(.boosters, symbol: "sparkles", title: lang.t("shop.item.boosters"))
                    packRow(.lives, symbol: "heart.fill", title: lang.t("shop.item.lives"))
                    sectionTitle(lang.t("shop.boosters"))
                    LazyVGrid(columns: columns, spacing: 10) {
                        ForEach(Booster.allCases) { booster in boosterTile(booster) }
                    }
                    footer
                }
                .padding(20)
            }
            if let granted = granted {
                RewardPopup(title: lang.t("shop.thanks"), granted: granted) { self.granted = nil }
            }
            if vipActivated {
                VIPActivatedPopup { vipActivated = false }
            }
        }
        .onAppear { Analytics.log("shop_open") }
    }

    @ViewBuilder
    private var notice: some View {
        if store.products.isEmpty {
            Label(lang.t(Store.testMode ? "shop.test" : "shop.unavailable"), systemImage: "info.circle.fill")
                .font(Theme.rounded(13, .semibold))
                .foregroundColor(Theme.brownSoft)
                .padding(10)
                .frame(maxWidth: .infinity, alignment: .leading)
                .background(RoundedRectangle(cornerRadius: 12).fill(Theme.card))
        }
    }

    private func sectionTitle(_ text: String) -> some View {
        Text(text)
            .font(Theme.rounded(18, .heavy))
            .foregroundColor(Theme.brown)
            .padding(.top, 4)
    }

    private var starter: some View {
        MetaCard(highlight: true) {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Image(systemName: "gift.fill").font(.system(size: 26)).foregroundColor(Theme.orange)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(lang.t("shop.item.starter")).font(Theme.rounded(18, .heavy)).foregroundColor(Theme.brown)
                        Text(lang.t("shop.starter.once")).font(Theme.rounded(12, .semibold)).foregroundColor(Theme.brownSoft)
                    }
                    Spacer()
                }
                RewardChips(reward: ShopItem.starter.reward)
                priceButton(.starter)
            }
        }
    }

    private func coinTile(_ item: ShopItem) -> some View {
        VStack(spacing: 6) {
            ZStack(alignment: .topTrailing) {
                SpriteImage(name: item.coinSprite, size: 74)
                    .frame(height: 74)
                    .frame(maxWidth: .infinity)
                if let bonus = item.bonusPercent {
                    Text("+\(bonus)%")
                        .font(Theme.rounded(11, .heavy))
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Theme.red))
                }
            }
            Text("\(item.reward.coins)").font(Theme.rounded(18, .heavy)).foregroundColor(Theme.brown).monospacedDigit()
            HStack(spacing: 4) {
                ForEach(item.reward.chestList.map { $0.0 }, id: \.self) { kind in
                    SpriteImage(name: kind.sprite, size: 22)
                    let n = item.reward.chests[kind.rawValue] ?? 1
                    if n > 1 { Text("×\(n)").font(Theme.rounded(11, .heavy)).foregroundColor(Theme.brownSoft) }
                }
            }
            .frame(height: 22)
            priceButton(item)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card))
    }

    private func packRow(_ item: ShopItem, symbol: String, title: String) -> some View {
        MetaCard {
            VStack(alignment: .leading, spacing: 8) {
                HStack(spacing: 8) {
                    Image(systemName: symbol).font(.system(size: 20, weight: .bold)).foregroundColor(Theme.orange)
                    Text(title).font(Theme.rounded(16, .heavy)).foregroundColor(Theme.brown)
                    Spacer()
                }
                RewardChips(reward: item.reward)
                priceButton(item)
            }
        }
    }

    private func boosterTile(_ booster: Booster) -> some View {
        VStack(spacing: 6) {
            Image(systemName: booster.symbol)
                .font(.system(size: 22, weight: .bold))
                .foregroundColor(.white)
                .frame(width: 46, height: 46)
                .background(Circle().fill(booster == .pause ? Theme.blue : Theme.orange))
            Text(lang.t("booster." + booster.rawValue))
                .font(Theme.rounded(13, .heavy))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(lang.t("shop.have", progress.count(booster)))
                .font(Theme.rounded(11, .semibold))
                .foregroundColor(Theme.brownSoft)
            Button {
                if progress.buy(booster) {
                    Audio.shared.play(.coin)
                    Toast.success(lang.t("shop.bought", lang.t("booster." + booster.rawValue)))
                } else {
                    Toast.error(lang.t("common.nocoins"))
                }
            } label: {
                HStack(spacing: 4) { CoinIcon(size: 16); Text("\(booster.price)") }
                    .font(Theme.rounded(14, .heavy))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 32)
                    .background(Capsule().fill(Theme.green))
            }
            .buttonStyle(.plain)
        }
        .padding(10)
        .background(RoundedRectangle(cornerRadius: 16, style: .continuous).fill(Theme.card))
    }

    private func priceButton(_ item: ShopItem) -> some View {
        Button { buy(item) } label: {
            ZStack {
                if store.busy == item {
                    ProgressView().tint(.white)
                } else {
                    Text(store.price(item))
                }
            }
            .font(Theme.rounded(16, .heavy))
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .frame(height: 38)
            .background(Capsule().fill(store.canPurchase ? Theme.green : Theme.brownSoft.opacity(0.5)))
        }
        .buttonStyle(.plain)
        .disabled(store.busy != nil)
    }

    private var footer: some View {
        VStack(spacing: 10) {
            Button(lang.t("shop.restore")) {
                Task { @MainActor in
                    let ok = await store.restore()
                    if ok { Toast.success(lang.t("shop.restored")) } else { Toast.error(lang.t("shop.restore.failed")) }
                }
            }
            .font(Theme.rounded(15, .heavy))
            .foregroundColor(Theme.orange)
            HStack(spacing: 16) {
                Link(lang.t("shop.terms"), destination: Legal.terms)
                Link(lang.t("shop.privacy"), destination: Legal.privacy)
            }
            .font(Theme.rounded(13, .bold))
            .foregroundColor(Theme.brownSoft)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 8)
    }

    private func buy(_ item: ShopItem) {
        guard store.canPurchase else {
            Toast.error(lang.t("shop.unavailable"))
            return
        }
        Task { @MainActor in
            switch await store.buy(item) {
            case let .done(result):
                Audio.shared.play(.chest)
                Haptics.success()
                if item.isVIP {
                    vipActivated = true
                } else if item == .eventPass {
                    Toast.success(lang.t("event.pass.active"))
                } else {
                    granted = result
                }
            case .pending:
                Toast.info(lang.t("shop.pending"), icon: "hourglass")
            case .cancelled:
                break
            case .unavailable:
                Toast.error(lang.t("shop.unavailable"))
            case .failed:
                Toast.error(lang.t("shop.failed"))
            }
        }
    }
}

/// Карточка VIP: что дает, цены недели и месяца, условия подписки.
struct VIPCard: View {
    let buy: (ShopItem) -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @ObservedObject private var store = Store.shared

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "crown.fill").font(.system(size: 26)).foregroundColor(Theme.gold)
                Text("VIP").font(Theme.rounded(24, .heavy)).foregroundColor(.white)
                Spacer()
                if let left = progress.vipLeft {
                    Text(lang.t("vip.active", Lang.duration(minutes: Int(left / 60))))
                        .font(Theme.rounded(12, .heavy))
                        .foregroundColor(Theme.vip)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 4)
                        .background(Capsule().fill(Color.white))
                }
            }
            VStack(alignment: .leading, spacing: 6) {
                perk("play.slash.fill", lang.t("vip.perk.ads"))
                perk("bitcoinsign.circle.fill", lang.t("vip.perk.coins"))
                perk("heart.fill", lang.t("vip.perk.lives", VIP.maxLives))
                perk("gift.fill", lang.t("vip.perk.daily"))
            }
            HStack(spacing: 10) {
                planButton(.vipWeek, title: lang.t("vip.week"))
                planButton(.vipMonth, title: lang.t("vip.month"), badge: lang.t("vip.save"))
            }
            Text(lang.t("vip.terms"))
                .font(Theme.rounded(11, .medium))
                .foregroundColor(.white.opacity(0.85))
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .background(
            RoundedRectangle(cornerRadius: 20, style: .continuous)
                .fill(LinearGradient(colors: [Theme.vip, Color(red: 0.32, green: 0.16, blue: 0.55)],
                                     startPoint: .topLeading, endPoint: .bottomTrailing))
                .shadow(color: Theme.vip.opacity(0.4), radius: 10, y: 4)
        )
    }

    private func perk(_ symbol: String, _ text: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: symbol).foregroundColor(Theme.gold).frame(width: 22)
            Text(text).font(Theme.rounded(14, .bold)).foregroundColor(.white)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func planButton(_ item: ShopItem, title: String, badge: String? = nil) -> some View {
        Button { buy(item) } label: {
            VStack(spacing: 2) {
                Text(title).font(Theme.rounded(13, .heavy))
                if store.busy == item {
                    ProgressView().tint(Theme.vip)
                } else {
                    Text(store.price(item)).font(Theme.rounded(18, .heavy))
                }
            }
            .foregroundColor(Theme.vip)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 8)
            .background(RoundedRectangle(cornerRadius: 14, style: .continuous).fill(Color.white))
            .overlay(alignment: .topTrailing) {
                if let badge = badge {
                    Text(badge)
                        .font(Theme.rounded(10, .heavy))
                        .foregroundColor(.white)
                        .padding(.horizontal, 6)
                        .padding(.vertical, 2)
                        .background(Capsule().fill(Theme.red))
                        .offset(x: 4, y: -8)
                }
            }
        }
        .buttonStyle(.plain)
        .disabled(store.busy != nil)
    }
}

/// Стопка монет для паков: чем дороже пак, тем выше стопка.
struct CoinStack: View {
    let count: Int

    var body: some View {
        ZStack {
            ForEach(0..<min(count + 1, 6), id: \.self) { i in
                CoinIcon(size: 30)
                    .offset(x: CGFloat(i % 2 == 0 ? -8 : 8) * (i == 0 ? 0 : 1), y: CGFloat(-i) * 5 + 10)
            }
        }
    }
}

struct VIPActivatedPopup: View {
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var appear = false

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            Panel(padding: 22) {
                VStack(spacing: 14) {
                    Image(systemName: "crown.fill")
                        .font(.system(size: 60))
                        .foregroundColor(Theme.gold)
                        .scaleEffect(appear ? 1 : 0.3)
                    Text(lang.t("vip.welcome")).font(Theme.rounded(24, .heavy)).foregroundColor(Theme.brown)
                    Text(lang.t("vip.welcome.text"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brownSoft)
                        .multilineTextAlignment(.center)
                    Button(lang.t("common.ok"), action: close).buttonStyle(BigButtonStyle())
                }
                .frame(maxWidth: 290)
            }
        }
        .onAppear { withAnimation(.spring(response: 0.4, dampingFraction: 0.5)) { appear = true } }
    }
}

/// Корона VIP в верхней панели.
struct VIPBadge: View {
    @EnvironmentObject private var progress: PlayerProgress
    let action: () -> Void

    var body: some View {
        if progress.isVIP {
            Button(action: action) {
                Image(systemName: "crown.fill")
                    .font(.system(size: 18, weight: .bold))
                    .foregroundColor(Theme.gold)
                    .frame(width: 40, height: 40)
                    .background(Circle().fill(Theme.vip))
            }
            .buttonStyle(.plain)
        }
    }
}
