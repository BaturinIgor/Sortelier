import SwiftUI

@main
struct SortelierApp: App {
    @StateObject private var progress = PlayerProgress.shared
    @StateObject private var lang = Lang.shared
    @Environment(\.scenePhase) private var scenePhase

    init() {
        #if DEBUG
        UIDebug.prepare()
        #endif
    }

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(progress)
                .environmentObject(lang)
                .environment(\.layoutDirection, lang.direction)
                .statusBarHidden()
                .onAppear {
                    Analytics.start()
                    RemoteConfig.shared.refresh(force: true)
                    Audio.shared.start()
                    Store.shared.start()
                    PlayerProgress.shared.ensureWelcomeStart()
                }
        }
        .onChange(of: scenePhase) { phase in
            switch phase {
            case .active:
                Audio.shared.resume()
                RemoteConfig.shared.refresh()
                Notifications.clearDelivered()
            case .background:
                Notifications.reschedule()
            default:
                break
            }
        }
    }
}

struct LevelLaunch: Identifiable {
    let id = UUID()
    let level: LevelData
    var mode: PlayMode = .main
}

struct RootView: View {
    @State private var launch: LevelLaunch?
    @ObservedObject private var router = Router.shared
    @EnvironmentObject private var progress: PlayerProgress
    @EnvironmentObject private var lang: Lang

    var body: some View {
        ZStack(alignment: .bottom) {
            ZStack {
                switch router.tab {
                case .map: MapView(play: play)
                case .shop: ShopScreen()
                case .events: EventsHub(play: play)
                case .album: AlbumScreen()
                case .kitchen: KitchenHub()
                }
            }
            .transition(.opacity)
            .fullScreenCover(isPresented: $router.merge) {
                MergeView(close: { router.merge = false })
                    .statusBarHidden()
                    .environmentObject(PlayerProgress.shared)
                    .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
            }
            Color.clear
                .fullScreenCover(isPresented: $router.market) {
                    MarketMapView(close: { router.market = false })
                        .statusBarHidden()
                        .environmentObject(PlayerProgress.shared)
                        .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
                }
            Color.clear
                .fullScreenCover(isPresented: $router.recipe) {
                    BigRecipeView(close: { router.recipe = false })
                        .statusBarHidden()
                        .environmentObject(PlayerProgress.shared)
                        .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
                }
            Color.clear
                .fullScreenCover(isPresented: $router.garden) {
                    GardenView(close: { router.garden = false })
                        .statusBarHidden()
                        .environmentObject(PlayerProgress.shared)
                        .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
                }
            MainTabBar()
            if router.jar {
                JarPopup { router.jar = false }.zIndex(6)
            }
            if router.settings {
                SettingsScreen()
                    .transition(.move(edge: .trailing))
                    .zIndex(5)
            }
            if router.lives {
                LivesPopup { router.lives = false }.zIndex(6)
            }
            if router.streak {
                StreakPopup { router.streak = false }.zIndex(6)
            }
        }
        .environmentObject(router)
        .fullScreenCover(item: $launch) { item in
            LevelHost(level: item.level, mode: item.mode, close: {
                launch = nil
                Audio.shared.setTrack(Biomes.music(PlayerProgress.shared.mapBiome))
            })
                .statusBarHidden()
                .environmentObject(PlayerProgress.shared)
                .environmentObject(Lang.shared).environment(\.layoutDirection, Lang.shared.direction)
                .environmentObject(Router.shared)
        }
        .onAppear {
            #if DEBUG
            UIDebug.apply(router)
            if let launch = UIDebug.levelLaunch() {
                DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) { play(launch.level, launch.mode) }
            }
            #endif
        }
    }

    private func play(_ level: LevelData, _ mode: PlayMode) {
        launch = LevelLaunch(level: level, mode: mode)
    }
}
