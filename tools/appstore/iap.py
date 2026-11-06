"""Заводит покупки Sortelier в App Store Connect через API.

Запуск (в CI, workflow "App Store purchases"): python3 tools/appstore/iap.py
Ключ берется из переменных ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8 (секреты GitHub).
Скрипт можно запускать повторно: что уже создано, пропускается, недостающее (переводы, цены) дозаполняется.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

import jwt  # pyjwt[crypto]

BUNDLE = os.environ.get("BUNDLE_ID", "com.personal.sortelier")
API = "https://api.appstoreconnect.apple.com"

# id товара -> (тип, цена USD, en (название, описание), ru (название, описание))
# название до 30 символов, описание до 55
IAPS = {
    "coinss": ("CONSUMABLE", "0.99", ("500 coins", "500 coins and a bronze chest"), ("500 монет", "500 монет и бронзовый сундук")),
    "coinsm": ("CONSUMABLE", "2.99", ("1,800 coins", "1,800 coins and a silver chest"), ("1 800 монет", "1 800 монет и серебряный сундук")),
    "coinsl": ("CONSUMABLE", "4.99", ("3,500 coins", "3,500 coins and a gold chest"), ("3 500 монет", "3 500 монет и золотой сундук")),
    "coinsxl": ("CONSUMABLE", "9.99", ("8,000 coins", "8,000 coins and two gold chests"), ("8 000 монет", "8 000 монет и два золотых сундука")),
    "coinsxxl": ("CONSUMABLE", "19.99", ("18,000 coins", "18,000 coins, gold and star chests"), ("18 000 монет", "18 000 монет, золотые и звездный сундуки")),
    "boosters": ("CONSUMABLE", "1.99", ("Booster pack", "3 of each sorting booster and a chest"), ("Набор бустеров", "По 3 бустера для сортировки и сундук")),
    "market": ("CONSUMABLE", "1.99", ("Market Match boosters", "Boosters for the match-3 mini-game"), ("Бустеры для «3 в ряд»", "Бустеры для мини-игры «Продуктовый ряд»")),
    "lives": ("CONSUMABLE", "0.99", ("Unlimited lives 2 h", "Play without losing lives for 2 hours"), ("Безлимитные жизни 2 ч", "Играй 2 часа, не тратя жизни")),
    "eventpass": ("CONSUMABLE", "2.99", ("Event pass", "Extra rewards on the event track"), ("Пропуск ивента", "Дополнительные награды на шкале ивента")),
    "jar": ("CONSUMABLE", "2.99", ("Tip jar", "Break the jar and take all saved coins"), ("Банка чаевых", "Разбей банку и забери накопленные монеты")),
    "starter": ("NON_CONSUMABLE", "0.99", ("Starter pack", "Coins, boosters and a chest, once only"), ("Стартовый набор", "Монеты, бустеры и сундук, один раз")),
}
SUBS = {
    "vipweek": ("ONE_WEEK", "1.99", 2, ("VIP for a week", "Ad rewards instantly, x1.5 coins, 8 lives"), ("VIP на неделю", "Награды без рекламы, монеты x1.5, 8 жизней")),
    "vipmonth": ("ONE_MONTH", "4.99", 1, ("VIP for a month", "Ad rewards instantly, x1.5 coins, 8 lives"), ("VIP на месяц", "Награды без рекламы, монеты x1.5, 8 жизней")),
}
GROUP = ("VIP", ("VIP", "Sortelier"), ("VIP", "Sortelier"))
REVIEW_NOTE = "Shop tab in the game. Purchases grant in-game items immediately."


def token():
    key = os.environ["ASC_KEY_P8"].replace("\\n", "\n")
    now = int(time.time())
    return jwt.encode({"iss": os.environ["ASC_ISSUER_ID"], "iat": now, "exp": now + 1100, "aud": "appstoreconnect-v1"},
                      key, algorithm="ES256", headers={"kid": os.environ["ASC_KEY_ID"], "typ": "JWT"})


TOKEN = None
errors = []


def call(method, path, body=None):
    global TOKEN
    TOKEN = TOKEN or token()
    url = path if path.startswith("http") else API + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Authorization": "Bearer " + TOKEN, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        text = e.read().decode(errors="replace")
        print(f"! {method} {path}: {e.code} {text[:600]}")
        errors.append(f"{method} {path}: {e.code}")
        return None


def get_all(path):
    out, url = [], path
    while url:
        r = call("GET", url)
        if not r:
            break
        out += r.get("data", [])
        url = r.get("links", {}).get("next")
    return out


def rel(kind, id_):
    return {"data": {"type": kind, "id": id_}}


def find_price_point(path, price):
    for p in get_all(path + ("&" if "?" in path else "?") + "filter[territory]=USA&limit=200"):
        if p["attributes"].get("customerPrice") == price:
            return p["id"]
    print(f"! price point {price} not found in {path}")
    errors.append(f"price {price}")
    return None


def main():
    apps = get_all(f"/v1/apps?filter[bundleId]={BUNDLE}")
    if not apps:
        sys.exit(f"App {BUNDLE} not found in App Store Connect")
    app = apps[0]["id"]
    print("app", app, apps[0]["attributes"]["name"])
    territories = [t["id"] for t in get_all("/v1/territories?limit=200")]

    # --- покупки ---
    have = {p["attributes"]["productId"]: p for p in get_all(f"/v1/apps/{app}/inAppPurchasesV2?limit=200")}
    for key, (kind, price, en, ru) in IAPS.items():
        pid = f"{BUNDLE}.{key}"
        if pid in have:
            iap = have[pid]["id"]
            print("exists", pid)
        else:
            r = call("POST", "/v2/inAppPurchases", {"data": {"type": "inAppPurchases", "attributes": {
                "name": en[0], "productId": pid, "inAppPurchaseType": kind, "reviewNote": REVIEW_NOTE},
                "relationships": {"app": rel("apps", app)}}})
            if not r:
                continue
            iap = r["data"]["id"]
            print("created", pid)
        locs = {l["attributes"]["locale"] for l in get_all(f"/v2/inAppPurchases/{iap}/inAppPurchaseLocalizations")}
        for locale, (name, desc) in (("en-US", en), ("ru", ru)):
            if locale not in locs:
                call("POST", "/v1/inAppPurchaseLocalizations", {"data": {"type": "inAppPurchaseLocalizations",
                     "attributes": {"locale": locale, "name": name, "description": desc},
                     "relationships": {"inAppPurchaseV2": rel("inAppPurchases", iap)}}})
        if not call("GET", f"/v2/inAppPurchases/{iap}/iapPriceSchedule"):
            point = find_price_point(f"/v2/inAppPurchases/{iap}/pricePoints", price)
            if point:
                call("POST", "/v1/inAppPurchasePriceSchedules", {
                    "data": {"type": "inAppPurchasePriceSchedules", "relationships": {
                        "inAppPurchase": rel("inAppPurchases", iap),
                        "baseTerritory": rel("territories", "USA"),
                        "manualPrices": {"data": [{"type": "inAppPurchasePrices", "id": "${p1}"}]}}},
                    "included": [{"type": "inAppPurchasePrices", "id": "${p1}", "attributes": {"startDate": None},
                                  "relationships": {"inAppPurchasePricePoint": rel("inAppPurchasePricePoints", point)}}]})
        if not call("GET", f"/v2/inAppPurchases/{iap}/inAppPurchaseAvailability"):
            call("POST", "/v1/inAppPurchaseAvailabilities", {"data": {"type": "inAppPurchaseAvailabilities",
                 "attributes": {"availableInNewTerritories": True},
                 "relationships": {"inAppPurchase": rel("inAppPurchases", iap),
                                   "availableTerritories": {"data": [{"type": "territories", "id": t} for t in territories]}}}})

    # --- подписка VIP ---
    groups = {g["attributes"]["referenceName"]: g["id"] for g in get_all(f"/v1/apps/{app}/subscriptionGroups?limit=50")}
    group = groups.get(GROUP[0])
    if not group:
        r = call("POST", "/v1/subscriptionGroups", {"data": {"type": "subscriptionGroups",
                 "attributes": {"referenceName": GROUP[0]}, "relationships": {"app": rel("apps", app)}}})
        group = r and r["data"]["id"]
        print("created group", group)
    if not group:
        return
    glocs = {l["attributes"]["locale"] for l in get_all(f"/v1/subscriptionGroups/{group}/subscriptionGroupLocalizations")}
    for locale, (name, app_name) in (("en-US", GROUP[1]), ("ru", GROUP[2])):
        if locale not in glocs:
            call("POST", "/v1/subscriptionGroupLocalizations", {"data": {"type": "subscriptionGroupLocalizations",
                 "attributes": {"locale": locale, "name": name, "customAppName": app_name},
                 "relationships": {"subscriptionGroup": rel("subscriptionGroups", group)}}})
    subs = {s["attributes"]["productId"]: s["id"] for s in get_all(f"/v1/subscriptionGroups/{group}/subscriptions?limit=50")}
    for key, (period, price, level, en, ru) in SUBS.items():
        pid = f"{BUNDLE}.{key}"
        sub = subs.get(pid)
        if not sub:
            r = call("POST", "/v1/subscriptions", {"data": {"type": "subscriptions", "attributes": {
                "name": en[0], "productId": pid, "subscriptionPeriod": period, "groupLevel": level,
                "reviewNote": REVIEW_NOTE, "familySharable": False},
                "relationships": {"group": rel("subscriptionGroups", group)}}})
            if not r:
                continue
            sub = r["data"]["id"]
            print("created", pid)
        else:
            print("exists", pid)
        locs = {l["attributes"]["locale"] for l in get_all(f"/v1/subscriptions/{sub}/subscriptionLocalizations")}
        for locale, (name, desc) in (("en-US", en), ("ru", ru)):
            if locale not in locs:
                call("POST", "/v1/subscriptionLocalizations", {"data": {"type": "subscriptionLocalizations",
                     "attributes": {"locale": locale, "name": name, "description": desc},
                     "relationships": {"subscription": rel("subscriptions", sub)}}})
        if not get_all(f"/v1/subscriptions/{sub}/prices?limit=1"):
            point = find_price_point(f"/v1/subscriptions/{sub}/pricePoints", price)
            if point:
                # базовая цена в США и пересчет Apple для остальных стран
                points = [point] + [p["id"] for p in get_all(f"/v1/subscriptionPricePoints/{point}/equalizations?limit=200")]
                for p in points:
                    call("POST", "/v1/subscriptionPrices", {"data": {"type": "subscriptionPrices",
                         "attributes": {"startDate": None, "preserveCurrentPrice": False},
                         "relationships": {"subscription": rel("subscriptions", sub),
                                           "subscriptionPricePoint": rel("subscriptionPricePoints", p)}}})
                print("prices", pid, len(points))
        if not call("GET", f"/v1/subscriptions/{sub}/subscriptionAvailability"):
            call("POST", "/v1/subscriptionAvailabilities", {"data": {"type": "subscriptionAvailabilities",
                 "attributes": {"availableInNewTerritories": True},
                 "relationships": {"subscription": rel("subscriptions", sub),
                                   "availableTerritories": {"data": [{"type": "territories", "id": t} for t in territories]}}}})

    print("errors:", len(errors))
    for e in errors:
        print(" ", e)


if __name__ == "__main__":
    main()
