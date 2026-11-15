#!/usr/bin/env bash
# Builds Cairn.dmg on a Mac: a small installer app and a note, in a disk image.
#
#   scripts/build-dmg.sh [output folder, default dist]
#
# The app only opens Terminal and runs install.sh of this release, so there is one installer for every way of installing.
# It is signed ad hoc (no Apple developer certificate), which is why the note explains "Open Anyway".
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-$ROOT/dist}"
VERSION="$(sed -n 's/^VERSION = "\(.*\)"/\1/p' "$ROOT/cairn/config.py")"
[ -n "$VERSION" ] || { echo "Cannot read the version from cairn/config.py" >&2; exit 1; }
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
APP="$STAGE/Install Cairn.app"

cp -R "$ROOT/packaging/macos/Install Cairn.app" "$APP"
mkdir -p "$APP/Contents/Resources"
cp "$ROOT/install.sh" "$APP/Contents/Resources/install.sh"
chmod 755 "$APP/Contents/Resources/install.sh" "$APP/Contents/MacOS/install-cairn"
sed -i.bak "s/__VERSION__/$VERSION/g" "$APP/Contents/Info.plist" && rm -f "$APP/Contents/Info.plist.bak"

# icon, from the one the app already has
if command -v sips >/dev/null 2>&1 && command -v iconutil >/dev/null 2>&1; then
  SET="$STAGE/AppIcon.iconset"
  mkdir -p "$SET"
  for size in 16 32 64 128 256 512; do
    sips -z "$size" "$size" "$ROOT/cairn/web/icon-512.png" --out "$SET/icon_${size}x${size}.png" >/dev/null
  done
  cp "$SET/icon_32x32.png" "$SET/icon_16x16@2x.png"
  cp "$SET/icon_64x64.png" "$SET/icon_32x32@2x.png"
  cp "$SET/icon_256x256.png" "$SET/icon_128x128@2x.png"
  cp "$SET/icon_512x512.png" "$SET/icon_256x256@2x.png"
  rm "$SET/icon_64x64.png"
  iconutil -c icns "$SET" -o "$APP/Contents/Resources/AppIcon.icns"
  rm -rf "$SET"
fi

command -v codesign >/dev/null 2>&1 && codesign --force --deep --sign - "$APP"
cp "$ROOT/packaging/macos/Read me first.txt" "$STAGE/Read me first.txt"

mkdir -p "$OUT"
rm -f "$OUT/Cairn.dmg"
hdiutil create -volname "Cairn $VERSION" -srcfolder "$STAGE" -ov -format UDZO "$OUT/Cairn.dmg" >/dev/null
(cd "$OUT" && shasum -a 256 Cairn.dmg >Cairn.dmg.sha256)
echo "Built $OUT/Cairn.dmg ($VERSION)"
cat "$OUT/Cairn.dmg.sha256"
