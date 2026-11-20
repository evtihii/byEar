#!/bin/zsh
# Збирає Holosii.app поруч із server.py: zsh mac/build.sh
set -e
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
APP="$ROOT/Holosii.app"
TMP="$(mktemp -d)"

# іконка
swift make_icon.swift "$TMP/icon.png"
mkdir -p "$TMP/Holosii.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$TMP/icon.png" --out "$TMP/Holosii.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$TMP/icon.png" --out "$TMP/Holosii.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$TMP/Holosii.iconset" -o "$TMP/Holosii.icns"

# стара збірка — у Кошик (нічого не видаляємо назавжди)
if [ -d "$APP" ]; then
  mkdir -p ~/.Trash/Holosii_app_old
  mv "$APP" ~/.Trash/Holosii_app_old/Holosii_$(date +%Y%m%d_%H%M%S).app
fi
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O main.swift -o "$APP/Contents/MacOS/Holosii" -framework Cocoa -framework WebKit
cp "$TMP/Holosii.icns" "$APP/Contents/Resources/Holosii.icns"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>Голосій</string>
  <key>CFBundleDisplayName</key><string>Голосій</string>
  <key>CFBundleIdentifier</key><string>local.holosii.app</string>
  <key>CFBundleExecutable</key><string>Holosii</string>
  <key>CFBundleIconFile</key><string>Holosii</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>$(date +%Y%m%d%H%M)</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>HolosiiServerDir</key><string>$ROOT</string>
  <key>NSMicrophoneUsageDescription</key><string>Голосій записує голос для диктування коментаря; розпізнає локальний Whisper, запис нікуди не надсилається.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
EOF
codesign --force --deep -s - "$APP"
rm -rf "$TMP"
echo "Готово: $APP"
