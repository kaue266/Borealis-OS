#!/usr/bin/env bash
set -euo pipefail
root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
cd "$root"
sdk=${ANDROID_SDK_ROOT:?Set ANDROID_SDK_ROOT to your Android SDK directory}
tools="$sdk/build-tools/35.0.0"
platform="$sdk/platforms/android-35/android.jar"
out="$root/build"
mkdir -p "$out/classes" "$out/dex" "$out/dist" "$out/keys" "$out/generated"
"$tools/aapt2" compile --dir res -o "$out/resources.zip"
"$tools/aapt2" link -o "$out/base.apk" -I "$platform" --manifest AndroidManifest.xml --java "$out/generated" "$out/resources.zip"
find src "$out/generated" -name '*.java' -print > "$out/sources.txt"
javac -encoding UTF-8 --release 8 -classpath "$platform" -d "$out/classes" @"$out/sources.txt"
(cd "$out/classes"; jar cf "$out/classes.jar" .)
"$tools/d8" --min-api 33 --lib "$platform" --output "$out/dex" "$out/classes.jar"
cp "$out/base.apk" "$out/unsigned.apk"
(cd "$out/dex"; zip -q "$out/unsigned.apk" classes.dex)
"$tools/zipalign" -f 4 "$out/unsigned.apk" "$out/aligned.apk"
if [[ ! -f "$out/keys/development.jks" ]]; then
  keytool -genkeypair -keystore "$out/keys/development.jks" -storepass android -keypass android \
    -alias nebula-development -keyalg RSA -keysize 2048 -validity 10000 -dname 'CN=Nebula Development' >/dev/null
fi
"$tools/apksigner" sign --ks "$out/keys/development.jks" --ks-key-alias nebula-development \
  --ks-pass pass:android --key-pass pass:android --out "$out/dist/Borealis-Space-v2.0-alpha.apk" "$out/aligned.apk"
"$tools/apksigner" verify --verbose "$out/dist/Borealis-Space-v2.0-alpha.apk"
(cd "$out/dist"; sha256sum Borealis-Space-v2.0-alpha.apk > Borealis-Space-v2.0-alpha.apk.sha256)
