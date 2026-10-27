import SwiftUI

@main
struct SortelierApp: App {
    @StateObject private var progress = PlayerProgress.shared
    @StateObject private var lang = Lang.shared

    var body: some Scene {
        WindowGroup {
            RootView()
                .environmentObject(progress)
                .environmentObject(lang)
                .statusBarHidden()
                .onAppear { Analytics.start() }
        }
    }
}

struct LevelLaunch: Identifiable {
    let id = UUID()
    let level: LevelData
}

struct RootView: View {
    @State private var launch: LevelLaunch?

    var body: some View {
        MapView(play: { level in launch = LevelLaunch(level: level) })
            .fullScreenCover(item: $launch) { item in
                LevelHost(level: item.level, close: { launch = nil })
                    .environmentObject(PlayerProgress.shared)
                    .environmentObject(Lang.shared)
            }
    }
}
