import XCTest

/// Сценарии с настоящими нажатиями: игра открывается с тестовым прогрессом (-uiDemo), тест жмет кнопки
/// и сохраняет снимки экрана. Строки "UITEST:" из лога CI складывает в отчет.
final class FlowTests: XCTestCase {
    override func setUp() {
        continueAfterFailure = true
    }

    private func launch(_ args: [String]) -> XCUIApplication {
        let app = XCUIApplication()
        app.launchArguments = ["-uiDemo", "-uiLang", "ru"] + args
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

    /// Нажимает кнопку с текстом; index - какую по счету из совпавших (вкладка и раздел могут называться одинаково).
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
        log("tap '\(text)' -> \(target.label) hittable=\(target.isHittable) frame=\(target.frame)")
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

    /// Вкладка "Ивенты" с карты, переключение на "Испытания" и "Новичку" нажатием.
    func testEventsSections() {
        let app = launch(["-uiScreen", "map"])
        shot(app, "01_map")
        let tabs = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Ивенты"))
        log("buttons 'Ивенты': \(tabs.count)")
        tap(app, "Ивенты", index: max(0, tabs.count - 1))
        shot(app, "02_events")
        tap(app, "Испытания")
        shot(app, "03_challenges")
        check(app, "Испытание дня", "раздел Испытания")
        tap(app, "Новичку")
        shot(app, "04_quests")
        check(app, "Главный приз", "раздел Новичку")
        tap(app, "Испытания")
        shot(app, "05_challenges_again")
        check(app, "Испытание дня", "снова Испытания")
        log("tree:\n" + String(app.debugDescription.prefix(6000)))
    }

    /// Те же переходы, когда игра открыта сразу на разделе ивентов.
    func testEventsSectionsDirect() {
        let app = launch(["-uiScreen", "events"])
        tap(app, "Испытания")
        shot(app, "11_challenges")
        check(app, "Испытание дня", "прямо: раздел Испытания")
        tap(app, "Новичку")
        shot(app, "12_quests")
        check(app, "Главный приз", "прямо: раздел Новичку")
    }

    /// Для сравнения: разделы вкладки "Кухня".
    func testKitchenSections() {
        let app = launch(["-uiScreen", "book"])
        tap(app, "Награды")
        shot(app, "21_achievements")
        check(app, "Шеф-повар", "кухня: Награды")
    }

    /// Задания новичка: 7 штук на день, "Перейти" ведет на карту или в нужный раздел.
    func testQuestsGo() {
        let app = launch(["-uiScreen", "quests"])
        shot(app, "31_quests")
        let go = app.buttons.matching(NSPredicate(format: "label CONTAINS %@", "Перейти"))
        log("кнопок Перейти: \(go.count)")
        app.swipeUp()
        sleep(1)
        tap(app, "Перейти")
        shot(app, "32_after_go")
        log("после Перейти: карта \(element(app, "Звезды кухни").exists), испытания \(element(app, "Испытание дня").exists)")
    }

    /// Монеты за карточки книги.
    func testBookCoins() {
        let app = launch(["-uiScreen", "book", "-uiStore"])
        shot(app, "41_book")
        check(app, "Забрать", "книга: кнопка Забрать")
        tap(app, "Забрать")
        shot(app, "42_book_collected")
    }

    /// Карта: карточка звезд листается на прошлую кухню.
    func testMapBiomes() {
        let app = launch(["-uiScreen", "map"])
        shot(app, "51_map")
        let back = app.buttons["biome.prev"]
        log("стрелка кухни: \(back.exists) \(back.label)")
        if back.exists { back.tap(); sleep(2) }
        shot(app, "52_map_prev_biome")
        check(app, "Американская", "карта: прошлая кухня в карточке")
    }
}
