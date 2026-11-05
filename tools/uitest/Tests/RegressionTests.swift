import XCTest

/// Проверка после слияния веток: переходы между фичами разных веток настоящими нажатиями.
/// Строки "UITEST:" и снимки CI складывает в отчет (ветка ci-uitest).
final class RegressionTests: XCTestCase {
    override func setUp() {
        continueAfterFailure = true
    }

    private func launch(_ args: [String]) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-uiDemo", "-uiLang", "ru", "-uiNoIntro"] + args
        app.launch()
        sleep(4)
        return app
    }

    private func shot(_ app: XCUIApplication, _ name: String) {
        let attachment = XCTAttachment(screenshot: app.screenshot())
        attachment.name = name
        attachment.lifetime = .keepAlways
        add(attachment)
    }

    private func log(_ text: String) { print("UITEST: " + text) }

    private func element(_ app: XCUIApplication, _ text: String) -> XCUIElement {
        let predicate = NSPredicate(format: "label CONTAINS %@", text)
        let button = app.buttons.matching(predicate).firstMatch
        return button.exists ? button : app.staticTexts.matching(predicate).firstMatch
    }

    @discardableResult
    private func tap(_ app: XCUIApplication, _ text: String, index: Int = 0) -> Bool {
        let predicate = NSPredicate(format: "label CONTAINS %@", text)
        let buttons = app.buttons.matching(predicate)
        let target: XCUIElement
        if buttons.count > index {
            target = buttons.element(boundBy: index)
        } else {
            let texts = app.staticTexts.matching(predicate)
            guard texts.count > index else {
                log("tap '\(text)': NOT FOUND")
                return false
            }
            target = texts.element(boundBy: index)
        }
        log("tap '\(text)' -> \(target.label) hittable=\(target.isHittable)")
        if target.isHittable {
            target.tap()
        } else {
            target.coordinate(withNormalizedOffset: CGVector(dx: 0.5, dy: 0.5)).tap()
        }
        sleep(2)
        return true
    }

    private func check(_ app: XCUIApplication, _ text: String, _ what: String) {
        let ok = element(app, text).waitForExistence(timeout: 3)
        log("\(what): \(ok ? "OK" : "FAIL") (ищем '\(text)')")
    }

    /// Карта -> "Продуктовый ряд" -> список глав -> уровень -> игра.
    func testMarketFromMap() {
        let app = launch(["-uiScreen", "map"])
        tap(app, "Продуктовый ряд")
        shot(app, "61_market")
        check(app, "Уровень", "рынок открылся с карты")
        tap(app, "Главы")
        shot(app, "62_chapters")
        app.tap()
        sleep(1)
        tap(app, "Уровень", index: app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Уровень")).count - 1)
        shot(app, "63_popup")
        check(app, "Играть", "окно уровня рынка")
        tap(app, "Играть")
        sleep(2)
        shot(app, "64_m3_level")
    }

    /// Окно жизней на карте рынка должно появляться поверх рынка, а не после выхода с него.
    func testMarketLivesPopup() {
        let app = launch(["-uiScreen", "market"])
        shot(app, "60_market_header")
        let pill = app.buttons["market.lives"]
        log("кнопка жизней на рынке: \(pill.exists)")
        if pill.exists { pill.tap(); sleep(2) }
        shot(app, "65_market_lives")
        check(app, "Жизни:", "окно жизней поверх рынка")
    }

    /// Карта -> "Мастерская" (слияние) и огород, потом назад на карту.
    func testRailScreens() {
        let app = launch(["-uiScreen", "map"])
        tap(app, "Мастерская")
        shot(app, "71_merge")
        let pills = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "12450"))
        log("монеты в шапке мастерской видны: \(pills.count) кнопок, frame \(pills.firstMatch.frame)")
        log("tree merge:\n" + String(app.debugDescription.prefix(2500)))
        tap(app, "Огород")
        shot(app, "72_garden_or_same")
    }

    /// Ачивки: "Перейти" в разделе "Мастерская шефа" ведет в мастерскую, в "Коллекции" - в альбом или книгу.
    func testAchievementsGo() {
        let app = launch(["-uiScreen", "achievements"])
        tap(app, "Мастерская шефа")
        shot(app, "81_ach_pantry")
        if tap(app, "Перейти") { shot(app, "82_after_go_pantry") }
        let app2 = launch(["-uiScreen", "achievements"])
        tap(app2, "Коллекция")
        if tap(app2, "Перейти") { shot(app2, "83_after_go_collection") }
    }

    /// Магазин: разделы по нажатию и переход по монетам из шапки книги.
    func testShopSections() {
        let app = launch(["-uiScreen", "book"])
        tap(app, "12")
        shot(app, "91_coins_from_header")
        check(app, "Монеты", "магазин открылся")
        tap(app, "Бустеры")
        shot(app, "92_shop_boosters")
        tap(app, "3 в ряд")
        shot(app, "93_shop_market")
        tap(app, "Выгодно")
        shot(app, "94_shop_offers")
    }

    /// Напоминание про огород, когда игра открыта на мастерской: мастерская закрывается, открывается огород.
    func testPushGardenOverMerge() {
        let app = launch(["-uiScreen", "merge", "-uiPush", "garden"])
        sleep(2)
        shot(app, "95_push_garden_over_merge")
    }
}
