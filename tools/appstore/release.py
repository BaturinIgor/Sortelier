"""Готовит версию из project.yml к проверке в App Store Connect:
ждет, пока сборка этой версии обработается, привязывает самую свежую сборку к версии и ставит
контактную почту для проверяющего. С --submit еще и отправляет версию на проверку.

python3 tools/appstore/release.py [--build N] [--submit] [--wait-minutes 60]
Ключ: ASC_KEY_ID, ASC_ISSUER_ID, ASC_KEY_P8. Запуск в CI (workflow "App Store release").
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(__file__))
from iap import BUNDLE, call, errors, get_all, rel  # noqa: E402
from store_upload import marketing_version  # noqa: E402

CONTACT_EMAIL = "dawnwell.app+sortelier@gmail.com"
EDITABLE = ("PREPARE_FOR_SUBMISSION", "DEVELOPER_REJECTED", "REJECTED", "METADATA_REJECTED")


def find_build(app, vstring, number, wait_minutes):
    """Сборка версии vstring: номер number или самая свежая. Ждет окончания обработки."""
    deadline = time.time() + wait_minutes * 60
    while True:
        builds = get_all(f"/v1/builds?filter[app]={app}&filter[preReleaseVersion.version]={vstring}"
                         f"&sort=-uploadedDate&limit=20")
        if number:
            builds = [b for b in builds if b["attributes"]["version"] == str(number)]
        build = builds[0] if builds else None
        state = build["attributes"].get("processingState") if build else None
        print("build", build["attributes"]["version"] if build else "-", state or "not uploaded yet")
        if state == "VALID":
            return build
        if state in ("FAILED", "INVALID"):
            sys.exit(f"build {build['attributes']['version']} is {state}")
        if time.time() > deadline:
            sys.exit("no processed build in time")
        time.sleep(60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", type=int, default=0, help="номер сборки (по умолчанию самая свежая)")
    ap.add_argument("--submit", action="store_true", help="отправить версию на проверку")
    ap.add_argument("--wait-minutes", type=int, default=60)
    args = ap.parse_args()

    app = get_all(f"/v1/apps?filter[bundleId]={BUNDLE}")[0]["id"]
    vstring = marketing_version()
    versions = get_all(f"/v1/apps/{app}/appStoreVersions?filter[platform]=IOS")
    version = next((v for v in versions if v["attributes"]["versionString"] == vstring), None)
    if not version or version["attributes"]["appStoreState"] not in EDITABLE:
        sys.exit(f"version {vstring} is not editable: {version and version['attributes']['appStoreState']}")
    vid = version["id"]

    build = find_build(app, vstring, args.build, args.wait_minutes)
    # шифрование: в Info.plist ITSAppUsesNonExemptEncryption = false, но на случай старой сборки отвечаем явно
    if build["attributes"].get("usesNonExemptEncryption") is None:
        call("PATCH", f"/v1/builds/{build['id']}", {"data": {"type": "builds", "id": build["id"],
             "attributes": {"usesNonExemptEncryption": False}}})
    call("PATCH", f"/v1/appStoreVersions/{vid}/relationships/build", rel("builds", build["id"]))
    print("version", vstring, "-> build", build["attributes"]["version"])

    # контакт для проверяющего: почта поддержки (имя и телефон уже заполнены в App Store Connect)
    detail = (call("GET", f"/v1/appStoreVersions/{vid}/appStoreReviewDetail") or {}).get("data")
    if detail:
        call("PATCH", f"/v1/appStoreReviewDetails/{detail['id']}", {"data": {"type": "appStoreReviewDetails",
             "id": detail["id"], "attributes": {"contactEmail": CONTACT_EMAIL}}})
        print("review contact email set")
    else:
        print("! no review details yet: fill contact info in App Store Connect once")

    if args.submit:
        sub = call("POST", "/v1/reviewSubmissions", {"data": {"type": "reviewSubmissions",
                   "attributes": {"platform": "IOS"}, "relationships": {"app": rel("apps", app)}}})
        if sub:
            sid = sub["data"]["id"]
            call("POST", "/v1/reviewSubmissionItems", {"data": {"type": "reviewSubmissionItems",
                 "relationships": {"reviewSubmission": rel("reviewSubmissions", sid),
                                   "appStoreVersion": rel("appStoreVersions", vid)}}})
            call("PATCH", f"/v1/reviewSubmissions/{sid}", {"data": {"type": "reviewSubmissions", "id": sid,
                 "attributes": {"submitted": True}}})
            print("submitted for review")

    print("errors:", len(errors))
    for e in errors:
        print(" ", e)
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
