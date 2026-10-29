import SwiftUI

/// Ссылки для экрана покупок. Политику опубликуем к релизу, пока она лежит в репозитории.
enum Legal {
    static let terms = URL(string: "https://www.apple.com/legal/internet-services/itunes/dev/stdeula/")!
    static let privacy = URL(string: "https://github.com/BaturinIgor/Sortelier/blob/main/PRIVACY.md")!
}

/// Магазин: VIP, стартовый набор, монеты, наборы и бустеры за монеты.
struct ShopScreen: View {
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @EnvironmentObject private var router: Router
    @ObservedObject private var store = Store.shared
    @State private var granted: Granted?
    @State private var vipActivated = false

    private let columns = [GridItem(.flexible(), spacing: 12), GridItem(.flexible(), spacing: 12)]

    var body: some View {
        ZStack {
            ScreenScaffold(title: lang.t("shop.title"), back: { router.open(.map) }) {
                notice
                VIPCard(buy: buy)
                if !progress.starterBought { starter }
                SectionTitle(title: lang.t("shop.coins"))
                LazyVGrid(columns: columns, spacing: 14) {
                    ForEach(ShopItem.coinPacks) { item in coinTile(item) }
                }
                SectionTitle(title: lang.t("shop.packs"))
                packCard(.boosters, icon: "icon_hint", title: lang.t("shop.item.boosters"))
                packCard(.lives, icon: "icon_unlimited", title: lang.t("shop.item.lives"))
                if progress.marketUnlocked {
                    jarCard
                    packCard(.market, icon: "icon_market", title: lang.t("shop.item.market"))
                }
                SectionTitle(title: lang.t("shop.boosters"))
                LazyVGrid(columns: columns, spacing: 14) {
                    ForEach(Booster.allCases) { booster in boosterTile(booster) }
                }
                if progress.marketUnlocked {
                    SectionTitle(title: lang.t("shop.market.boosters"))
                    LazyVGrid(columns: columns, spacing: 14) {
                        ForEach(M3Booster.allCases) { b in marketTile(b) }
                    }
                }
                footer
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
            Text(lang.t(Store.testMode ? "shop.test" : "shop.unavailable"))
                .font(Theme.rounded(13, .semibold))
                .foregroundColor(Theme.brown)
                .multilineTextAlignment(.center)
                .fixedSize(horizontal: false, vertical: true)
                .padding(12)
                .frame(maxWidth: .infinity)
                .background(InsetBackground())
        }
    }

    private var starter: some View {
        Panel(padding: 14, highlight: true) {
            VStack(spacing: 12) {
                HStack(spacing: 10) {
                    SpriteImage(name: "icon_gift", size: 50)
                    VStack(alignment: .leading, spacing: 2) {
                        Text(lang.t("shop.item.starter")).font(Theme.rounded(19, .black)).foregroundColor(Theme.brown)
                        Text(lang.t("shop.starter.once")).font(Theme.rounded(13, .semibold)).foregroundColor(Theme.brownSoft)
                    }
                    Spacer(minLength: 0)
                }
                RewardChips(reward: ShopItem.starter.reward, perRow: 4, tileWidth: 62)
                priceButton(.starter)
            }
        }
    }

    private func coinTile(_ item: ShopItem) -> some View {
        VStack(spacing: 4) {
            SpriteImage(name: item.coinSprite, size: 104)
                .frame(height: 98)
            HStack(spacing: 4) {
                CoinIcon(size: 22)
                Text(Self.grouped(item.reward.coins))
                    .font(Theme.rounded(22, .black))
                    .foregroundColor(Theme.brown)
                    .monospacedDigit()
                    .lineLimit(1)
                    .minimumScaleFactor(0.7)
            }
            HStack(spacing: 3) {
                Text("+").font(Theme.rounded(14, .black)).foregroundColor(Theme.brownSoft)
                ForEach(item.reward.chestList.map { $0.0 }, id: \.self) { kind in
                    Button { RewardInfo.show(.chest(kind, item.reward.chests[kind.rawValue] ?? 1)) } label: {
                        HStack(spacing: 1) {
                            SpriteImage(name: kind.sprite, size: 28)
                            let n = item.reward.chests[kind.rawValue] ?? 1
                            if n > 1 { Text("×\(n)").font(Theme.rounded(13, .black)).foregroundColor(Theme.brownSoft) }
                        }
                    }
                    .buttonStyle(PressScaleStyle())
                }
            }
            .frame(height: 28)
            priceButton(item)
                .padding(.top, 4)
        }
        .padding(.horizontal, 10)
        .padding(.top, 8)
        .padding(.bottom, 6)
        .frame(maxWidth: .infinity)
        .background(PaperBackground())
        .overlay(alignment: .topTrailing) {
            if let bonus = item.bonusPercent {
                Text("+\(bonus)%")
                    .font(Theme.rounded(13, .black))
                    .foregroundColor(.white)
                    .outlined(Theme.ribbonDark, width: 1)
                    .padding(.horizontal, 8)
                    .padding(.vertical, 3)
                    .background(
                        ZStack {
                            RoundedRectangle(cornerRadius: 9, style: .continuous).fill(Theme.red)
                            RoundedRectangle(cornerRadius: 9, style: .continuous).strokeBorder(Theme.ribbonDark, lineWidth: 2)
                        }
                    )
                    .rotationEffect(.degrees(8))
                    .offset(x: 6, y: -6)
            }
        }
    }

    private func packCard(_ item: ShopItem, icon: String, title: String) -> some View {
        Panel(padding: 14) {
            VStack(spacing: 12) {
                HStack(spacing: 10) {
                    SpriteImage(name: icon, size: 40)
                    Text(title).font(Theme.rounded(18, .black)).foregroundColor(Theme.brown)
                        .lineLimit(2)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                }
                RewardChips(reward: item.reward, perRow: 5, tileWidth: 56)
                priceButton(item)
            }
        }
    }

    private func boosterTile(_ booster: Booster) -> some View {
        VStack(spacing: 4) {
            Button { RewardInfo.show(.booster(booster, 1)) } label: {
                SpriteImage(name: booster.icon, size: 62)
            }
            .buttonStyle(PressScaleStyle())
            Text(lang.t("booster." + booster.rawValue))
                .font(Theme.rounded(15, .black))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(lang.t("shop.have", progress.count(booster)))
                .font(Theme.rounded(13, .bold))
                .foregroundColor(Theme.brownSoft)
            Button {
                if progress.buy(booster) {
                    Audio.shared.play(.coin)
                    Toast.success(lang.t("shop.bought", lang.t("booster." + booster.rawValue)))
                } else {
                    Toast.error(lang.t("common.nocoins"))
                }
            } label: {
                HStack(spacing: 4) { CoinIcon(size: 22); Text("\(booster.price)") }
            }
            .buttonStyle(GameButtonStyle(palette: .green, height: 40, fontSize: 18, radius: 13))
            .padding(.top, 2)
        }
        .padding(.horizontal, 10)
        .padding(.top, 10)
        .padding(.bottom, 6)
        .frame(maxWidth: .infinity)
        .background(PaperBackground())
    }

    /// Банка чаевых: копится сама, разбивается покупкой.
    private var jarCard: some View {
        Panel(padding: 14, highlight: progress.jarCanBreak) {
            HStack(spacing: 12) {
                JarGlyph(fill: Double(progress.jarCoins) / Double(TipJar.capacity))
                    .frame(width: 70, height: 84)
                VStack(alignment: .leading, spacing: 6) {
                    Text(lang.t("jar.title")).font(Theme.rounded(18, .black)).foregroundColor(Theme.brown)
                    HStack(spacing: 4) {
                        CoinIcon(size: 22)
                        Text("\(progress.jarCoins) / \(TipJar.capacity)").font(Theme.rounded(16, .black)).foregroundColor(Theme.brown)
                            .monospacedDigit()
                    }
                    if progress.jarCanBreak {
                        priceButton(.jar)
                    } else {
                        Text(lang.t("jar.min", TipJar.minimum)).font(Theme.rounded(12, .bold)).foregroundColor(Theme.brownSoft)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                Spacer(minLength: 0)
            }
        }
    }

    private func marketTile(_ b: M3Booster) -> some View {
        VStack(spacing: 4) {
            Button { RewardInfo.show(.market(b, 1)) } label: {
                SpriteImage(name: b.icon, size: 62)
            }
            .buttonStyle(PressScaleStyle())
            Text(lang.t("m3.booster." + b.rawValue))
                .font(Theme.rounded(15, .black))
                .foregroundColor(Theme.brown)
                .lineLimit(1)
                .minimumScaleFactor(0.7)
            Text(lang.t("shop.have", progress.count(b)))
                .font(Theme.rounded(13, .bold))
                .foregroundColor(Theme.brownSoft)
            Button {
                if progress.buy(b) {
                    Audio.shared.play(.coin)
                    Toast.success(lang.t("shop.bought", lang.t("m3.booster." + b.rawValue)))
                } else {
                    Toast.error(lang.t("common.nocoins"))
                }
            } label: {
                HStack(spacing: 4) { CoinIcon(size: 22); Text("\(MarketBalance.price(b))") }
            }
            .buttonStyle(GameButtonStyle(palette: .green, height: 40, fontSize: 18, radius: 13))
            .padding(.top, 2)
        }
        .padding(.horizontal, 10)
        .padding(.top, 10)
        .padding(.bottom, 6)
        .frame(maxWidth: .infinity)
        .background(PaperBackground())
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
        }
        .buttonStyle(GameButtonStyle(palette: store.canPurchase ? .green : .gray, height: 44, fontSize: 20, radius: 14))
        .disabled(store.busy != nil)
    }

    private var footer: some View {
        VStack(spacing: 12) {
            Button(lang.t("shop.restore")) {
                Task { @MainActor in
                    let ok = await store.restore()
                    if ok { Toast.success(lang.t("shop.restored")) } else { Toast.error(lang.t("shop.restore.failed")) }
                }
            }
            .buttonStyle(GameButtonStyle(palette: .paper, height: 42, fontSize: 16, fullWidth: false))
            HStack(spacing: 18) {
                Link(lang.t("shop.terms"), destination: Legal.terms)
                Link(lang.t("shop.privacy"), destination: Legal.privacy)
            }
            .font(Theme.rounded(13, .heavy))
            .foregroundColor(Color(red: 1.0, green: 0.93, blue: 0.8))
            .outlined(Theme.woodDark, width: 1)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 8)
    }

    /// 18000 -> "18 000": разряды через пробел читаются лучше.
    static func grouped(_ n: Int) -> String {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        f.groupingSeparator = " "
        f.usesGroupingSeparator = true
        return f.string(from: NSNumber(value: n)) ?? "\(n)"
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
                } else if item == .jar, result == nil {
                    Toast.error(lang.t("jar.empty"))
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

/// Карточка VIP: бархатная панель в золотой рамке, что дает, цены недели и месяца, условия подписки.
struct VIPCard: View {
    let buy: (ShopItem) -> Void
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang
    @ObservedObject private var store = Store.shared

    private let velvetTop = Color(red: 0.55, green: 0.32, blue: 0.86)
    private let velvetBottom = Color(red: 0.30, green: 0.14, blue: 0.52)
    private let goldDark = Color(red: 0.55, green: 0.33, blue: 0.05)

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                SpriteImage(name: "icon_crown", size: 46)
                StrokeText(text: "VIP", size: 28, weight: .black, color: Color(red: 1.0, green: 0.86, blue: 0.4), stroke: velvetBottom, width: 2, drop: 3)
                Spacer()
                if let left = progress.vipLeft {
                    Text(lang.t("vip.active", Lang.duration(minutes: Int(left / 60))))
                        .font(Theme.rounded(12, .black))
                        .foregroundColor(velvetBottom)
                        .padding(.horizontal, 10)
                        .padding(.vertical, 5)
                        .background(Capsule().fill(Color(red: 1.0, green: 0.9, blue: 0.55)))
                }
            }
            VStack(alignment: .leading, spacing: 8) {
                perk("icon_ad", lang.t("vip.perk.ads"))
                perk("coin_icon", lang.t("vip.perk.coins"))
                perk("icon_heart", lang.t("vip.perk.lives", VIP.maxLives))
                perk("icon_gift", lang.t("vip.perk.daily"))
            }
            HStack(spacing: 10) {
                planButton(.vipWeek, title: lang.t("vip.week"))
                planButton(.vipMonth, title: lang.t("vip.month"), badge: lang.t("vip.save"))
            }
            Text(lang.t("vip.terms"))
                .font(Theme.rounded(11, .bold))
                .foregroundColor(.white.opacity(0.85))
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .background(
            ZStack {
                RoundedRectangle(cornerRadius: 20, style: .continuous).fill(Theme.woodDark.opacity(0.55)).offset(y: 5)
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .fill(LinearGradient(colors: [velvetTop, velvetBottom], startPoint: .topLeading, endPoint: .bottomTrailing))
                RoundedRectangle(cornerRadius: 20, style: .continuous).inset(by: 4)
                    .strokeBorder(Color(red: 1.0, green: 0.84, blue: 0.4).opacity(0.5), lineWidth: 2)
                RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(goldDark, lineWidth: 3)
            }
        )
    }

    private func perk(_ icon: String, _ text: String) -> some View {
        HStack(spacing: 10) {
            if icon == "coin_icon" { CoinIcon(size: 26) } else { SpriteImage(name: icon, size: 28) }
            Text(text).font(Theme.rounded(15, .heavy)).foregroundColor(.white)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func planButton(_ item: ShopItem, title: String, badge: String? = nil) -> some View {
        Button { buy(item) } label: {
            VStack(spacing: 0) {
                Text(title).font(Theme.rounded(13, .black))
                if store.busy == item {
                    ProgressView().tint(.white)
                } else {
                    Text(store.price(item)).font(Theme.rounded(19, .black))
                }
            }
        }
        .buttonStyle(GameButtonStyle(palette: .gold, height: 54, fontSize: 18, radius: 14))
        .overlay(alignment: .topTrailing) {
            if let badge = badge {
                Text(badge)
                    .font(Theme.rounded(11, .black))
                    .foregroundColor(.white)
                    .outlined(Theme.ribbonDark, width: 1)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 2)
                    .background(Capsule().fill(Theme.red))
                    .overlay(Capsule().strokeBorder(Theme.ribbonDark, lineWidth: 1.5))
                    .offset(x: 6, y: -10)
            }
        }
        .disabled(store.busy != nil)
    }
}

struct VIPActivatedPopup: View {
    let close: () -> Void
    @EnvironmentObject private var lang: Lang
    @State private var appear = false

    var body: some View {
        ZStack {
            Dim().onTapGesture(perform: close)
            PopupCard(title: lang.t("vip.welcome"), close: close, maxWidth: 310) {
                VStack(spacing: 14) {
                    SpriteImage(name: "icon_crown", size: 100)
                        .scaleEffect(appear ? 1 : 0.3)
                    Text(lang.t("vip.welcome.text"))
                        .font(Theme.rounded(15, .semibold))
                        .foregroundColor(Theme.brown)
                        .multilineTextAlignment(.center)
                        .fixedSize(horizontal: false, vertical: true)
                    Button(lang.t("common.ok"), action: close).buttonStyle(GameButtonStyle(palette: .green))
                }
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
                SpriteImage(name: "icon_crown", size: 40)
            }
            .buttonStyle(PressScaleStyle())
        }
    }
}
