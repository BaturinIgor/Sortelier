"""Доступность приложения в App Store по территориям: проверка и возврат в продажу.

python3 tools/appstore/availability.py          показать статусы версий и территории
python3 tools/appstore/availability.py --fix    вернуть в продажу во всех территориях, кроме SKIP

Ключ: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8.
"""
import argparse
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(__file__))
from iap import BUNDLE, call, errors, get_all, rel  # noqa: E402

# материковый Китай: игры там продаются только с лицензией (ISBN), без нее не включаем
SKIP = {"CHN"}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fix", action="store_true")
    args = ap.parse_args()
    app = get_all(f"/v1/apps?filter[bundleId]={BUNDLE}")[0]["id"]

    for v in get_all(f"/v1/apps/{app}/appStoreVersions?filter[platform]=IOS"):
        a = v["attributes"]
        print("version", a["versionString"], a.get("appStoreState"), a.get("appVersionState"), a.get("releaseType"))

    avail = (call("GET", f"/v1/apps/{app}/appAvailabilityV2") or {}).get("data")
    if not avail:
        print("availability: NOT SET")
        terr = []
    else:
        print("availability", avail["id"], "availableInNewTerritories:", avail["attributes"].get("availableInNewTerritories"))
        terr = get_all(f"/v2/appAvailabilities/{avail['id']}/territoryAvailabilities?include=territory&limit=200")
    on = [t for t in terr if t["attributes"].get("available")]
    print(f"territories: {len(on)} available of {len(terr)}")
    print("content statuses:", dict(Counter(s for t in terr for s in t["attributes"].get("contentStatuses") or [])))
    usa = next((t for t in terr if t["relationships"]["territory"]["data"]["id"] == "USA"), None)
    if usa:
        print("USA:", usa["attributes"])

    if args.fix:
        if not avail:
            all_t = [t["id"] for t in get_all("/v1/territories?limit=200") if t["id"] not in SKIP]
            call("POST", "/v2/appAvailabilities", {"data": {"type": "appAvailabilities",
                 "attributes": {"availableInNewTerritories": True},
                 "relationships": {"app": rel("apps", app), "territoryAvailabilities": {"data": [
                     {"type": "territoryAvailabilities", "id": f"${{{t}}}"} for t in all_t]}}},
                 "included": [{"type": "territoryAvailabilities", "id": f"${{{t}}}", "attributes": {"available": True},
                               "relationships": {"territory": rel("territories", t)}} for t in all_t]})
            print("availability created for", len(all_t), "territories")
        else:
            n = 0
            for t in terr:
                tid = t["relationships"]["territory"]["data"]["id"]
                if t["attributes"].get("available") or tid in SKIP:
                    continue
                if call("PATCH", f"/v1/territoryAvailabilities/{t['id']}", {"data": {
                        "type": "territoryAvailabilities", "id": t["id"], "attributes": {"available": True}}}) is not None:
                    n += 1
            print("territories switched on:", n)

    print("errors:", len(errors))
    for e in errors:
        print(" ", e)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
