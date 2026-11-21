#!/bin/bash
# Кладёт GoogleService-Info.plist в приложение перед xcodegen (только сборка для App Store).
# Берётся из секрета GOOGLE_SERVICE_INFO_PLIST (содержимое файла или base64), иначе из
# tools/analytics/GoogleService-Info.plist (файл в .gitignore). Без файла статистика в приложении выключена.
#
# Использование: tools/analytics/add_firebase_config.sh [ожидаемый bundle ID]
# Если файла нет, он испорчен или выписан на другой bundle ID, сборка не падает: статистика просто выключена.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)"
DEST="$DIR/../../Sortelier/Resources/GoogleService-Info.plist"
EXPECTED_ID="${1:-}"

skip() {
  rm -f "$DEST"
  echo "::warning::$1 Статистика в этой сборке выключена."
  exit 0
}

if [ -n "${GOOGLE_SERVICE_INFO_PLIST:-}" ]; then
  if printf '%s' "$GOOGLE_SERVICE_INFO_PLIST" | grep -q "<plist"; then
    printf '%s' "$GOOGLE_SERVICE_INFO_PLIST" > "$DEST"
  elif ! printf '%s' "$GOOGLE_SERVICE_INFO_PLIST" | base64 --decode > "$DEST" 2>/dev/null; then
    skip "Секрет GOOGLE_SERVICE_INFO_PLIST не похож ни на plist, ни на base64."
  fi
elif [ -f "$DIR/GoogleService-Info.plist" ]; then
  cp "$DIR/GoogleService-Info.plist" "$DEST"
else
  skip "GoogleService-Info.plist не найден (секрет GOOGLE_SERVICE_INFO_PLIST не задан)."
fi

# Испорченный файл уронил бы приложение в FirebaseApp.configure(), поэтому проверяем ключи.
for key in BUNDLE_ID GOOGLE_APP_ID API_KEY GCM_SENDER_ID PROJECT_ID; do
  value="$(/usr/libexec/PlistBuddy -c "Print :$key" "$DEST" 2>/dev/null)" \
    || skip "В GoogleService-Info.plist нет ключа $key."
  [ -n "$value" ] || skip "В GoogleService-Info.plist пустой ключ $key."
done
GOOGLE_APP_ID="$(/usr/libexec/PlistBuddy -c "Print :GOOGLE_APP_ID" "$DEST")"
# Значение не печатаем: проверяем только формат iOS-приложения Firebase.
[[ "$GOOGLE_APP_ID" =~ ^1:[0-9]+:ios:[0-9a-f]+$ ]] \
  || skip "GOOGLE_APP_ID в GoogleService-Info.plist не похож на iOS-приложение Firebase (1:<номер>:ios:<hex>)."
BUNDLE_ID="$(/usr/libexec/PlistBuddy -c "Print :BUNDLE_ID" "$DEST")"
if [ -n "$EXPECTED_ID" ] && [ "$BUNDLE_ID" != "$EXPECTED_ID" ]; then
  skip "GoogleService-Info.plist выписан на $BUNDLE_ID, а приложение собирается как $EXPECTED_ID."
fi
echo "Firebase Analytics подключён ($BUNDLE_ID)."
