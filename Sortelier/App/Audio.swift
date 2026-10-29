import AVFoundation

/// Музыка и звуки. Категория ambient: игра уважает беззвучный режим и не глушит чужую музыку.
final class Audio {
    static let shared = Audio()

    enum Effect: String, CaseIterable {
        case pick, place, invalid, triple, dish, coin, combo, star1, star2, star3, win, button, chest, customer, unlock
        case pop, swoosh, boom, sparkle, crack, glass
    }

    private var pools: [Effect: [AVAudioPlayer]] = [:]
    private var cursor: [Effect: Int] = [:]
    private var music: AVAudioPlayer?
    private var track = "music_kitchen"
    private var started = false
    private let musicVolume: Float = 0.45

    private init() {}

    func start() {
        guard !started else { return }
        started = true
        try? AVAudioSession.sharedInstance().setCategory(.ambient, mode: .default, options: [.mixWithOthers])
        try? AVAudioSession.sharedInstance().setActive(true)
        for effect in Effect.allCases {
            guard let url = Bundle.main.url(forResource: "sfx_" + effect.rawValue, withExtension: "wav") else { continue }
            let count = effect == .pop ? 4 : ([.pick, .place, .coin, .button, .crack, .glass].contains(effect) ? 3 : 2)
            pools[effect] = (0..<count).compactMap { _ in
                let player = try? AVAudioPlayer(contentsOf: url)
                player?.prepareToPlay()
                return player
            }
        }
        updateMusic()
    }

    /// Запуск звука уходит с главного потока: при каскадах на "Рынке" звуков много, а play() может занимать миллисекунды.
    private let queue = DispatchQueue(label: "sortelier.audio", qos: .userInitiated)

    func play(_ effect: Effect, volume: Float = 1) {
        guard PlayerProgress.shared.settings.sound, let pool = pools[effect], !pool.isEmpty else { return }
        let index = (cursor[effect] ?? 0) % pool.count
        cursor[effect] = index + 1
        let player = pool[index]
        queue.async {
            player.volume = volume
            player.currentTime = 0
            player.play()
        }
    }

    /// Включает или выключает музыку по настройке, с плавным переходом громкости.
    func updateMusic() {
        if PlayerProgress.shared.settings.music {
            if music == nil, let url = Bundle.main.url(forResource: track, withExtension: "m4a")
                ?? Bundle.main.url(forResource: "music_kitchen", withExtension: "m4a") {
                music = try? AVAudioPlayer(contentsOf: url)
                music?.numberOfLoops = -1
                music?.volume = 0
                music?.prepareToPlay()
            }
            guard let player = music else { return }
            if !player.isPlaying { player.play() }
            player.setVolume(musicVolume, fadeDuration: 1.5)
        } else if let player = music, player.isPlaying {
            player.setVolume(0, fadeDuration: 0.4)
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.45) { [weak self] in
                if !PlayerProgress.shared.settings.music { self?.music?.pause() }
            }
        }
    }

    /// Смена мелодии (у каждой кухни своя) с плавным переходом.
    func setTrack(_ name: String) {
        guard name != track else { return }
        track = name
        guard started, let old = music else { return }
        music = nil
        old.setVolume(0, fadeDuration: 0.6)
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.65) { old.stop() }
        updateMusic()
    }

    /// После возврата в приложение плеер мог остановиться.
    func resume() {
        guard started else { return }
        try? AVAudioSession.sharedInstance().setActive(true)
        updateMusic()
    }
}
