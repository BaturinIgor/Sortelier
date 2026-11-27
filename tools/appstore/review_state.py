"""Печатает состояние отправки на проверку: черновики reviewSubmissions и их элементы, подписки и группы.
Только чтение. Запуск в CI (workflow "App Store review state")."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from iap import BUNDLE, call, get_all  # noqa: E402

app = get_all(f"/v1/apps?filter[bundleId]={BUNDLE}")[0]["id"]
for s in get_all(f"/v1/apps/{app}/reviewSubmissions?limit=20"):
    print("submission", s["id"], s["attributes"].get("state"), s["attributes"].get("platform"))
    r = call("GET", f"/v1/reviewSubmissions/{s['id']}/items?limit=50&include=appStoreVersion,subscription,inAppPurchaseV2,subscriptionGroup")
    for it in (r or {}).get("data", []):
        rels = {k: (v.get("data") or {}).get("id") for k, v in it.get("relationships", {}).items() if isinstance(v, dict) and v.get("data")}
        print("  item", it["id"], it["attributes"].get("state"), rels)
for g in get_all(f"/v1/apps/{app}/subscriptionGroups?limit=50"):
    print("group", g["id"], g["attributes"])
    for s in get_all(f"/v1/subscriptionGroups/{g['id']}/subscriptions?limit=50"):
        print("  sub", s["id"], s["attributes"].get("productId"), s["attributes"].get("state"))
# Версии и сайт разработчика: AdMob ищет app-ads.txt на домене marketingUrl живой версии.
for v in get_all(f"/v1/apps/{app}/appStoreVersions?limit=10"):
    a = v["attributes"]
    print("version", a.get("versionString"), a.get("appStoreState"), a.get("createdDate"))
    for l in get_all(f"/v1/appStoreVersions/{v['id']}/appStoreVersionLocalizations?limit=50"):
        la = l["attributes"]
        if la.get("locale") in ("en-US", "ru"):
            print("  ", la.get("locale"), "marketing:", la.get("marketingUrl"), "support:", la.get("supportUrl"))
