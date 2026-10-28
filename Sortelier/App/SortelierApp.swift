import SwiftUI

@main
struct SortelierApp: App {
    @StateObject private var progress = PlayerProgress.shared
    @StateObject private var lang = Lang.shared
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(progress)
                .environmentObject(lang)
                .statusBarHidden()
                .onAppear {
                    Analytics.start()
                    Audio.shared.start()
                    PlayerProgress.shared.ensureWelcomeStart()
                }
        }
        .onChange(of: scenePhase) { phase in
            switch phase {
            case .active:
                Audio.shared.resume()
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

    var body: some View {
        MapView(play: { level, mode in launch = LevelLaunch(level: level, mode: mode) })
            .fullScreenCover(item: $launch) { item in
                LevelHost(level: item.level, mode: item.mode, close: { launch = nil })
                    .environmentObject(PlayerProgress.shared)
                    .environmentObject(Lang.shared)
            }
    }
}
