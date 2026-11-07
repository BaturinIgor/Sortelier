"""Страница игры в App Store Connect через API: тексты на всех языках, скриншоты, категория,
возрастной рейтинг, бесплатная цена. Запуск в CI (workflow "Store screenshots") после build.py.

python3 tools/appstore/store_upload.py [--no-shots]
Ключ: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8. Повторный запуск обновляет тексты и заменяет скриншоты.
"""
import argparse
import glob
import hashlib
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(__file__))
import json

from iap import BUNDLE, LAST_ERROR, call, errors, get_all, rel  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
META = os.path.join(ROOT, "appstore", "metadata")
SHOTS = os.path.join(ROOT, "appstore", "screenshots")
REPO = "https://github.com/BaturinIgor/Sortelier/blob/main/"
PRIVACY_URL = REPO + "PRIVACY.md"
SUPPORT_URL = REPO + "SUPPORT.md"
COPYRIGHT = "2026 Igor Baturin"


def read(loc, name):
    p = os.path.join(META, loc, name)
    return open(p, encoding="utf-8").read().strip() if os.path.exists(p) else None


def upload_file(kind, rel_name, rel_type, owner, path):
    data = open(path, "rb").read()
    r = call("POST", f"/v1/{kind}", {"data": {"type": kind,
             "attributes": {"fileName": os.path.basename(path), "fileSize": len(data)},
             "relationships": {rel_name: rel(rel_type, owner)}}})
    if not r:
        return False
    sid = r["data"]["id"]
    for op in r["data"]["attributes"]["uploadOperations"]:
        req = urllib.request.Request(op["url"], data=data[op["offset"]:op["offset"] + op["length"]], method=op["method"],
                                     headers={h["name"]: h["value"] for h in op.get("requestHeaders", [])})
        urllib.request.urlopen(req).read()
    call("PATCH", f"/v1/{kind}/{sid}", {"data": {"type": kind, "id": sid,
         "attributes": {"uploaded": True, "sourceFileChecksum": hashlib.md5(data).hexdigest()}}})
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-shots", action="store_true")
    args = ap.parse_args()
    locales = sorted(d for d in os.listdir(META) if os.path.isdir(os.path.join(META, d)))
    app = get_all(f"/v1/apps?filter[bundleId]={BUNDLE}")[0]["id"]

    # --- информация о приложении: название, подзаголовок, политика, категория, рейтинг ---
    infos = get_all(f"/v1/apps/{app}/appInfos")
    info = next((i for i in infos if i["attributes"].get("appStoreState") in
                 ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED", None)
                 or i["attributes"].get("state") in ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED")), infos[0])["id"]
    call("PATCH", f"/v1/appInfos/{info}", {"data": {"type": "appInfos", "id": info, "relationships": {
        "primaryCategory": rel("appCategories", "GAMES"),
        "primarySubcategoryOne": rel("appCategories", "GAMES_PUZZLE"),
        "primarySubcategoryTwo": rel("appCategories", "GAMES_CASUAL")}}})
    have = {l["attributes"]["locale"]: l["id"] for l in get_all(f"/v1/appInfos/{info}/appInfoLocalizations")}
    for loc in locales:
        attrs = {"name": read(loc, "name.txt"), "subtitle": read(loc, "subtitle.txt"), "privacyPolicyUrl": PRIVACY_URL}
        if loc in have:
            call("PATCH", f"/v1/appInfoLocalizations/{have[loc]}", {"data": {"type": "appInfoLocalizations", "id": have[loc], "attributes": attrs}})
        else:
            call("POST", "/v1/appInfoLocalizations", {"data": {"type": "appInfoLocalizations",
                 "attributes": dict(attrs, locale=loc), "relationships": {"appInfo": rel("appInfos", info)}}})
    print("app info", len(locales), "locales")

    # возрастной рейтинг: без насилия, азарта и прочего; реклама есть. API принимает только полный
    # набор полей одним запросом; поля, которые оно требует сверх известных, дописываем по ответу.
    age = call("GET", f"/v1/appInfos/{info}/ageRatingDeclaration")
    if age and age.get("data"):
        aid = age["data"]["id"]
        fields = {f: "NONE" for f in (
            "alcoholTobaccoOrDrugUseOrReferences", "contests", "gamblingSimulated", "horrorOrFearThemes",
            "matureOrSuggestiveThemes", "medicalOrTreatmentInformation", "profanityOrCrudeHumor",
            "sexualContentGraphicAndNudity", "sexualContentOrNudity", "violenceCartoonOrFantasy",
            "violenceRealistic", "violenceRealisticProlongedGraphicOrSadistic", "gunsOrOtherWeapons")}
        fields.update({"gambling": False, "unrestrictedWebAccess": False, "lootBox": False, "advertising": True,
                       "messagingAndChat": False, "userGeneratedContent": False, "parentalControls": False,
                       "ageAssurance": False, "healthOrWellnessTopics": False, "socialMedia": False})
        done = False
        for attempt in range(6):
            if call("PATCH", f"/v1/ageRatingDeclarations/{aid}", {"data": {"type": "ageRatingDeclarations", "id": aid,
                                                                           "attributes": fields}}) is not None:
                done = True
                errors[:] = [e for e in errors if "ageRatingDeclarations" not in e]
                break
            try:
                errs = json.loads(LAST_ERROR["text"]).get("errors", [])
            except ValueError:
                break
            changed = False
            for e in errs:
                name = (e.get("source") or {}).get("pointer", "").rsplit("/", 1)[-1]
                if not name:
                    continue
                if e.get("code", "").endswith("REQUIRED") and name not in fields:
                    fields[name] = False
                elif name in fields and fields[name] is False and "REQUIRED" not in e.get("code", ""):
                    fields[name] = "NONE"  # поле оказалось перечислением, а не да/нет
                elif name in fields and "REQUIRED" not in e.get("code", ""):
                    fields.pop(name)  # API такого поля не знает
                else:
                    continue
                changed = True
            if not changed:
                break
        print("age rating", "set" if done else "FAILED", len(fields), "fields")

    # --- цена: бесплатно ---
    if not (call("GET", f"/v1/apps/{app}/appPriceSchedule") or {}).get("data"):
        free = next((p["id"] for p in get_all(f"/v1/apps/{app}/appPricePoints?filter[territory]=USA&limit=200")
                     if float(p["attributes"].get("customerPrice") or 0) == 0), None)
        if free:
            call("POST", "/v1/appPriceSchedules", {"data": {"type": "appPriceSchedules", "relationships": {
                "app": rel("apps", app), "baseTerritory": rel("territories", "USA"),
                "manualPrices": {"data": [{"type": "appPrices", "id": "${p}"}]}}},
                "included": [{"type": "appPrices", "id": "${p}", "attributes": {"startDate": None},
                              "relationships": {"appPricePoint": rel("appPricePoints", free)}}]})
            print("price: free")

    # --- версия 1.0: тексты и скриншоты ---
    versions = get_all(f"/v1/apps/{app}/appStoreVersions?filter[platform]=IOS")
    version = next((v for v in versions if v["attributes"]["appStoreState"] in
                    ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED")), None)
    if not version:
        sys.exit("no editable App Store version")
    vid = version["id"]
    first = len(versions) == 1
    call("PATCH", f"/v1/appStoreVersions/{vid}", {"data": {"type": "appStoreVersions", "id": vid,
         "attributes": {"copyright": COPYRIGHT, "versionString": "1.0"}}})
    have = {l["attributes"]["locale"]: l["id"] for l in get_all(f"/v1/appStoreVersions/{vid}/appStoreVersionLocalizations")}
    for loc in locales:
        attrs = {"description": read(loc, "description.txt"), "keywords": read(loc, "keywords.txt"),
                 "promotionalText": read(loc, "promotional_text.txt"), "supportUrl": SUPPORT_URL}
        if not first:
            attrs["whatsNew"] = read(loc, "release_notes.txt")
        if loc in have:
            call("PATCH", f"/v1/appStoreVersionLocalizations/{have[loc]}", {"data": {"type": "appStoreVersionLocalizations", "id": have[loc], "attributes": attrs}})
        else:
            r = call("POST", "/v1/appStoreVersionLocalizations", {"data": {"type": "appStoreVersionLocalizations",
                     "attributes": dict(attrs, locale=loc), "relationships": {"appStoreVersion": rel("appStoreVersions", vid)}}})
            if r:
                have[loc] = r["data"]["id"]
    print("version texts", len(locales), "locales")

    if not args.no_shots:
        for loc in locales:
            files = sorted(glob.glob(os.path.join(SHOTS, loc, "*.jpg")))
            if not files or loc not in have:
                continue
            sets = {s["attributes"]["screenshotDisplayType"]: s["id"] for s in
                    get_all(f"/v1/appStoreVersionLocalizations/{have[loc]}/appScreenshotSets")}
            sid = sets.get("APP_IPHONE_67")
            if sid:
                for old in get_all(f"/v1/appScreenshotSets/{sid}/appScreenshots"):
                    call("DELETE", f"/v1/appScreenshots/{old['id']}")
            else:
                r = call("POST", "/v1/appScreenshotSets", {"data": {"type": "appScreenshotSets",
                         "attributes": {"screenshotDisplayType": "APP_IPHONE_67"},
                         "relationships": {"appStoreVersionLocalization": rel("appStoreVersionLocalizations", have[loc])}}})
                if not r:
                    continue
                sid = r["data"]["id"]
            n = sum(upload_file("appScreenshots", "appScreenshotSet", "appScreenshotSets", sid, f) for f in files)
            print("screenshots", loc, n)

    print("errors:", len(errors))
    for e in errors:
        print(" ", e)


if __name__ == "__main__":
    main()
