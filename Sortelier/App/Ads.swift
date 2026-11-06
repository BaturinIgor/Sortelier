import UIKit
import AppTrackingTransparency
import GoogleMobileAds
import UserMessagingPlatform

/// Реклама за награду через Google AdMob.
/// Порядок запуска: согласие (UMP, нужно для Европы), запрос ATT, старт SDK, загрузка ролика.
/// ID приложения лежит в Info.plist (GADApplicationIdentifier), ID блока - AdMobRewardedUnit.
/// В отладке и в сборке для SideStore показывается тестовый ролик Google (пометка Test Ad, без дохода).
final class Ads: NSObject, FullScreenContentDelegate {
    static let shared = Ads()

    /// Тестовый блок Google для роликов за награду.
    static let testUnit = "ca-app-pub-3940256099942544/1712485313"

    static var unitId: String {
        // свои ролики на тестовых сборках смотреть нельзя: AdMob банит аккаунт за "накрутку"
        #if DEBUG || SIDELOAD
        return testUnit
        #else
        let value = (Bundle.main.object(forInfoDictionaryKey: "AdMobRewardedUnit") as? String) ?? ""
        return value.isEmpty ? testUnit : value
        #endif
    }

    private var started = false
    private var sdkReady = false
    private var loading = false
    private var ad: RewardedAd?
    private var loadedAt = Date.distantPast
    private var retry = 0

    // текущий показ
    private var waiting: ((Bool) -> Void)?
    private var waitPlacement = ""
    private var presenting: ((Bool) -> Void)?
    private var earned = false
    private var placement = ""

    var canShow: Bool { PlayerProgress.shared.isVIP || PlayerProgress.shared.adsLeftToday > 0 }

    /// Нужна ли в настройках кнопка "Настройки рекламы" (обязательна там, где действует GDPR).
    var privacyOptionsRequired: Bool {
        ConsentInformation.shared.privacyOptionsRequirementStatus == .required
    }

    #if DEBUG
    /// В снимках и UI-тестах ролик не показывается: награда сразу.
    private var instant: Bool { UIDebug.demo }
    #endif

    // MARK: запуск

    /// Вызывается при старте: согласие, ATT, SDK. Повторный вызов ничего не делает.
    func start() {
        guard !started else { return }
        started = true
        #if DEBUG
        if instant { return }
        #endif
        let params = RequestParameters()
        ConsentInformation.shared.requestConsentInfoUpdate(with: params) { [weak self] error in
            DispatchQueue.main.async {
                if let error { Analytics.log("ads_consent_error", ["error": error.localizedDescription]) }
                self?.presentConsentIfNeeded()
            }
        }
        // согласие могло быть получено в прошлый запуск: SDK можно стартовать сразу
        if ConsentInformation.shared.canRequestAds { startSDK() }
    }

    private func presentConsentIfNeeded() {
        guard let vc = Self.topController() else {
            DispatchQueue.main.asyncAfter(deadline: .now() + 1) { [weak self] in self?.presentConsentIfNeeded() }
            return
        }
        ConsentForm.loadAndPresentIfRequired(from: vc) { [weak self] error in
            DispatchQueue.main.async {
                if let error { Analytics.log("ads_consent_form_error", ["error": error.localizedDescription]) }
                self?.requestTracking {
                    if ConsentInformation.shared.canRequestAds { self?.startSDK() }
                }
            }
        }
    }

    /// Системный вопрос про отслеживание. Без него реклама идет, но неперсонализированная.
    private func requestTracking(_ done: @escaping () -> Void) {
        guard #available(iOS 14.5, *), ATTrackingManager.trackingAuthorizationStatus == .notDetermined else {
            done()
            return
        }
        // вопрос показывается только у активного приложения: даем окну появиться
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.8) {
            ATTrackingManager.requestTrackingAuthorization { status in
                Analytics.log("att", ["status": status.rawValue])
                DispatchQueue.main.async { done() }
            }
        }
    }

    private func startSDK() {
        guard !sdkReady else { return }
        sdkReady = true
        MobileAds.shared.start { [weak self] _ in
            DispatchQueue.main.async { self?.load() }
        }
    }

    /// Форма выбора согласия из настроек.
    func showPrivacyOptions() {
        guard let vc = Self.topController() else { return }
        ConsentForm.presentPrivacyOptionsForm(from: vc) { [weak self] _ in
            DispatchQueue.main.async {
                if ConsentInformation.shared.canRequestAds { self?.startSDK() }
            }
        }
    }

    // MARK: загрузка

    /// Ролик живет час: старый перезагружаем.
    private var adFresh: Bool { ad != nil && Date().timeIntervalSince(loadedAt) < 3500 }

    private func load() {
        guard sdkReady, !loading, !adFresh else { return }
        loading = true
        RewardedAd.load(with: Self.unitId, request: Request()) { [weak self] ad, error in
            DispatchQueue.main.async {
                guard let self else { return }
                self.loading = false
                if let ad {
                    ad.fullScreenContentDelegate = self
                    self.ad = ad
                    self.loadedAt = Date()
                    self.retry = 0
                    if let waiting = self.waiting {
                        self.waiting = nil
                        self.present(placement: self.waitPlacement, completion: waiting)
                    }
                } else {
                    self.ad = nil
                    Analytics.log("ad_load_error", ["error": error?.localizedDescription ?? ""])
                    self.failWaiting()
                    // повтор с растущей паузой: 4, 8, 16... до 64 секунд
                    self.retry = min(self.retry + 1, 4)
                    let delay = pow(2.0, Double(self.retry)) * 2
                    DispatchQueue.main.asyncAfter(deadline: .now() + delay) { [weak self] in self?.load() }
                }
            }
        }
    }

    // MARK: показ

    func showRewarded(placement: String, completion: @escaping (Bool) -> Void) {
        // VIP получает награду сразу, без рекламы и без расхода лимита
        if PlayerProgress.shared.isVIP {
            Analytics.log("ad_reward_vip", ["placement": placement])
            completion(true)
            return
        }
        guard canShow, presenting == nil, waiting == nil else {
            completion(false)
            return
        }
        #if DEBUG
        if instant {
            PlayerProgress.shared.countAdView()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.4) { completion(true) }
            return
        }
        #endif
        if adFresh {
            present(placement: placement, completion: completion)
            return
        }
        // ролика еще нет: ждем загрузку несколько секунд
        if !started { start() }
        waiting = completion
        waitPlacement = placement
        load()
        DispatchQueue.main.asyncAfter(deadline: .now() + 6) { [weak self] in self?.failWaiting() }
    }

    private func failWaiting() {
        guard let waiting else { return }
        self.waiting = nil
        Toast.info(Lang.shared.t("ads.notReady"), icon: "wifi.exclamationmark")
        waiting(false)
    }

    private func present(placement: String, completion: @escaping (Bool) -> Void) {
        guard let ad, let vc = Self.topController() else {
            completion(false)
            return
        }
        self.ad = nil
        self.placement = placement
        earned = false
        presenting = completion
        Audio.shared.silence(true)
        Analytics.log("ad_show", ["placement": placement])
        ad.present(from: vc) { [weak self] in
            self?.earned = true
        }
    }

    private func finish() {
        Audio.shared.silence(false)
        guard let done = presenting else { return }
        presenting = nil
        if earned {
            PlayerProgress.shared.countAdView()
            Analytics.log("ad_reward", ["placement": placement])
        }
        let ok = earned
        // награда после закрытия ролика, чтобы анимации были видны
        DispatchQueue.main.asyncAfter(deadline: .now() + 0.25) { done(ok) }
        load()
    }

    func adDidDismissFullScreenContent(_ ad: FullScreenPresentingAd) {
        DispatchQueue.main.async { self.finish() }
    }

    func ad(_ ad: FullScreenPresentingAd, didFailToPresentFullScreenContentWithError error: Error) {
        Analytics.log("ad_present_error", ["error": error.localizedDescription])
        DispatchQueue.main.async {
            self.earned = false
            self.finish()
            Toast.info(Lang.shared.t("ads.notReady"), icon: "wifi.exclamationmark")
        }
    }

    // MARK: окно

    /// Верхний контроллер основного окна (не служебных окон тостов и карточек).
    static func topController() -> UIViewController? {
        let scenes = UIApplication.shared.connectedScenes.compactMap { $0 as? UIWindowScene }
        guard let scene = scenes.first(where: { $0.activationState == .foregroundActive }) ?? scenes.first else { return nil }
        let window = scene.windows.first(where: { $0.windowLevel == .normal && $0.isKeyWindow })
            ?? scene.windows.first(where: { $0.windowLevel == .normal })
        var vc = window?.rootViewController
        while let next = vc?.presentedViewController, !next.isBeingDismissed { vc = next }
        return vc
    }
}
