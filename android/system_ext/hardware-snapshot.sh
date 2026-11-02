#!/system/bin/sh
# Read: the boot-log directory and sysfs/procfs/dev roots. Write: one read-only hardware snapshot.
set -eu
umask 077
trap 'status=$?; if [ "$status" -ne 0 ]; then echo "dali hardware snapshot failed (status $status)" >&2; fi' EXIT

logs=$1
sys_root=$2
proc_root=$3
dev_root=$4
current=$logs/current
temporary=$current/hardware.txt.tmp
output=$current/hardware.txt

test -d "$logs" && test ! -L "$logs"
test -d "$current" && test ! -L "$current"
for root in "$sys_root" "$proc_root" "$dev_root"; do
    test -d "$root" && test ! -L "$root"
done
test ! -L "$output"
if [ -e "$output" ]; then
    test -f "$output"
fi
test ! -L "$temporary"
if [ -e "$temporary" ]; then
    test -f "$temporary"
    rm -f "$temporary"
fi

snapshot_file() {
    label=$1
    path=$2
    printf '%s=' "$label"
    if [ -r "$path" ]; then
        if cat "$path"; then
            printf '\n'
        else
            printf '[read failed]\n'
        fi
    else
        echo '[missing or unreadable]'
    fi
}

{
    echo "backlight_devices:"
    found=0
    for device in "$sys_root"/class/backlight/*; do
        if [ ! -e "$device" ] && [ ! -L "$device" ]; then
            continue
        fi
        found=1
        printf 'device=%s\n' "${device##*/}"
        if target=$(readlink -f "$device" 2>&1); then
            printf 'target=%s\n' "$target"
        else
            printf 'target=[unavailable] %s\n' "$target"
        fi
        for field in type brightness actual_brightness max_brightness; do
            snapshot_file "$field" "$device/$field"
        done
        ls -lZ "$device/brightness" || echo '[brightness label unavailable]'
    done
    if [ "$found" -eq 0 ]; then
        echo none
    fi

    echo "sound_cards:"
    found=0
    for card in "$sys_root"/class/sound/card[0-9]*; do
        if [ ! -e "$card" ] && [ ! -L "$card" ]; then
            continue
        fi
        found=1
        printf 'card=%s\n' "${card##*/}"
        if target=$(readlink -f "$card" 2>&1); then
            printf 'target=%s\n' "$target"
        else
            printf 'target=[unavailable] %s\n' "$target"
        fi
        snapshot_file id "$card/id"
        snapshot_file number "$card/number"
        for chip in "$card"/device/hdaudioC*D*/chip_name; do
            if [ -e "$chip" ]; then
                snapshot_file chip_name "$chip"
            fi
        done
    done
    if [ "$found" -eq 0 ]; then
        echo none
    fi
    snapshot_file asound_cards "$proc_root/asound/cards"
    snapshot_file asound_pcm "$proc_root/asound/pcm"

    echo "loaded_sound_modules:"
    if [ -r "$proc_root/modules" ]; then
        grep '^snd' "$proc_root/modules" || {
            status=$?
            if [ "$status" -eq 1 ]; then
                echo none
            else
                echo '[read failed]'
            fi
        }
    else
        echo '[missing or unreadable]'
    fi

    echo "sound_device_nodes:"
    if [ -d "$dev_root/snd" ]; then
        found=0
        for node in "$dev_root"/snd/*; do
            case "$node" in
                "$dev_root"/snd/\*) continue ;;
            esac
            found=1
            printf '%s\n' "${node##*/}"
        done
        if [ "$found" -eq 0 ]; then
            echo none
        fi
    else
        echo absent
    fi
} > "$temporary"
mv "$temporary" "$output"
sync
