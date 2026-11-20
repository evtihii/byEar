#!/bin/zsh
# Збирає ByEar.app поруч із server.py: zsh mac/build.sh
set -e
cd "$(dirname "$0")"
ROOT="$(cd .. && pwd)"
APP="$ROOT/ByEar.app"
TMP="$(mktemp -d)"

# іконка
swift make_icon.swift "$TMP/icon.png"
mkdir -p "$TMP/ByEar.iconset"
for s in 16 32 128 256 512; do
  sips -z $s $s "$TMP/icon.png" --out "$TMP/ByEar.iconset/icon_${s}x${s}.png" >/dev/null
  sips -z $((s*2)) $((s*2)) "$TMP/icon.png" --out "$TMP/ByEar.iconset/icon_${s}x${s}@2x.png" >/dev/null
done
iconutil -c icns "$TMP/ByEar.iconset" -o "$TMP/ByEar.icns"

# стара збірка — у Кошик (нічого не видаляємо назавжди)
if [ -d "$APP" ]; then
  mkdir -p ~/.Trash/ByEar_app_old
  mv "$APP" ~/.Trash/ByEar_app_old/ByEar_$(date +%Y%m%d_%H%M%S).app
fi
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
swiftc -O main.swift -o "$APP/Contents/MacOS/ByEar" -framework Cocoa -framework WebKit
cp "$TMP/ByEar.icns" "$APP/Contents/Resources/ByEar.icns"

cat > "$APP/Contents/Info.plist" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>CFBundleName</key><string>наСлух</string>
  <key>CFBundleDisplayName</key><string>наСлух</string>
  <key>CFBundleIdentifier</key><string>local.byear.app</string>
  <key>CFBundleExecutable</key><string>ByEar</string>
  <key>CFBundleIconFile</key><string>ByEar</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>CFBundleVersion</key><string>$(date +%Y%m%d%H%M)</string>
  <key>LSMinimumSystemVersion</key><string>13.0</string>
  <key>NSHighResolutionCapable</key><true/>
  <key>ByEarServerDir</key><string>$ROOT</string>
  <key>NSMicrophoneUsageDescription</key><string>наСлух записує голос для диктування коментаря; розпізнає локальний Whisper, запис нікуди не надсилається.</string>
  <key>NSAppTransportSecurity</key><dict><key>NSAllowsLocalNetworking</key><true/></dict>
</dict></plist>
EOF
codesign --force --deep -s - "$APP"
rm -rf "$TMP"
echo "Готово: $APP"
