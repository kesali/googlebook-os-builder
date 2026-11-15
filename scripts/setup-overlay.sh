#!/usr/bin/env bash
# Read: Google's partitions, Android build tools and the setup overlay sources.
# Write: a signed overlay APK and a persistent local signing identity.
#
#   setup-overlay.sh GOOGLE BUILDTOOLS SOURCES KEY_DIR OUTPUT
set -euo pipefail
google=$(realpath -e "$1") buildtools=$(realpath -e "$2") sources=$(realpath -e "$3")
key_dir=$(realpath -s -m "$4") output=$(realpath -m "$5")
umask 077
mkdir -p "$(dirname "$key_dir")" "$(dirname "$output")"
work=$(mktemp -d "$output.partial.XXXXXX")
trap 'rm -rf "$work"' EXIT

# Keep the same signing identity across USB updates that preserve userdata.
exec 9>"$key_dir.lock"
flock -x 9
if [ ! -e "$key_dir" ]; then
    if [ -e "$output" ]; then
        echo "Setup overlay signing identity is missing; restore $key_dir before rebuilding." >&2
        exit 1
    fi
    mkdir -m 700 "$work/key"
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$work/key/key.pem"
    openssl req -new -x509 -key "$work/key/key.pem" -out "$work/key/cert.pem" \
        -days 36500 -subj '/CN=gbos-builder setup overlay/'
    openssl pkcs8 -topk8 -nocrypt -in "$work/key/key.pem" -outform DER -out "$work/key/key.pk8"
    rm "$work/key/key.pem"
    mv -T "$work/key" "$key_dir"
fi
if [ -L "$key_dir" ] || [ ! -f "$key_dir/key.pk8" ] || [ -L "$key_dir/key.pk8" ] \
        || [ ! -f "$key_dir/cert.pem" ] || [ -L "$key_dir/cert.pem" ]; then
    echo "Setup overlay signing identity is incomplete or unsafe: $key_dir" >&2
    exit 1
fi

for file in aapt2 zipalign apksigner lib/apksigner.jar lib64/libc++.so; do
    mkdir -p "$work/tools/$(dirname "$file")"
    unzip -p "$buildtools" "android-37.0/$file" > "$work/tools/$file"
done
chmod 755 "$work/tools/aapt2" "$work/tools/zipalign" "$work/tools/apksigner"
export LD_LIBRARY_PATH="$work/tools/lib64"

dump.erofs --path=/priv-app/SetupWizardDesktopPrebuilt_cl3b/SetupWizardDesktopPrebuilt_cl3b.apk \
    --cat "$google/super/system_ext_a.img" > "$work/google.apk"
dump.erofs --path=/system/framework/framework-res.apk --cat "$google/super/system_a.img" > "$work/framework.apk"
mkdir -p "$work/res/raw" "$work/res/xml"
unzip -p "$work/google.apk" res/Wi.xml > "$work/res/raw/wizard_script_connect_and_update_flow.xml"
patch --batch --forward --fuzz=0 --no-backup-if-mismatch --reject-file=- \
    -p1 -d "$work/res/raw" < "$sources/wizard-script.patch"
cp "$sources/overlays.xml" "$work/res/xml/overlays.xml"
"$work/tools/aapt2" compile --dir "$work/res" -o "$work/compiled.zip"
"$work/tools/aapt2" link -I "$work/framework.apk" --manifest "$sources/AndroidManifest.xml" \
    --auto-add-overlay -o "$work/unsigned.apk" "$work/compiled.zip"
"$work/tools/zipalign" -f 4 "$work/unsigned.apk" "$work/aligned.apk"
"$work/tools/apksigner" sign --key "$key_dir/key.pk8" --cert "$key_dir/cert.pem" \
    --out "$work/overlay.apk" "$work/aligned.apk"
"$work/tools/apksigner" verify "$work/overlay.apk"
if ! cmp -s "$work/overlay.apk" "$output"; then
    mv "$work/overlay.apk" "$output"
fi
