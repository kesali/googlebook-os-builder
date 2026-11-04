#!/system/bin/sh
# Read: only the named Elantech input device. Write: a bounded boot-local diagnostic log.
# touchpad-capture.sh LOG_DIRECTORY SYS_ROOT DEV_ROOT
set -eu
umask 077
trap 'status=$?; if [ "$status" -ne 0 ]; then echo "gbos-builder touchpad capture failed (status $status)" >&2; fi' EXIT

logs=$1
sys_root=$2
dev_root=$3
for directory in "$logs" "$logs/current" "$sys_root" "$dev_root"; do
    test -d "$directory" && test ! -L "$directory"
done
output=$logs/current/touchpad.log
test ! -L "$output"
if [ -e "$output" ]; then
    echo "Touchpad capture already exists; refusing to overwrite it" >&2
    exit 1
fi

selected=
for event in "$sys_root"/class/input/event[0-9]*; do
    if [ ! -e "$event" ]; then
        continue
    fi
    read -r name < "$event/device/name"
    if [ "$name" != "ETPS/2 Elantech Touchpad" ]; then
        continue
    fi
    if [ -n "$selected" ]; then
        echo "Multiple Elantech touchpads; refusing ambiguous capture" >&2
        exit 1
    fi
    selected=$event
done

# Publish directly: a hang must not hide the events already collected.
set -C
exec > "$output" 2>&1
echo "limit_seconds=180"
echo "limit_events=32768"
if [ -z "$selected" ]; then
    echo "status=not-present"
    exit 0
fi
node=$dev_root/input/${selected##*/}
test ! -L "$dev_root/input"
test ! -L "$node"
test -c "$node"
printf 'device=%s\nname=ETPS/2 Elantech Touchpad\n' "$node"
for field in phys properties capabilities/ev capabilities/key capabilities/abs; do
    printf '%s=' "$field"
    cat "$selected/device/$field"
done
echo "axis_info_begin"
axis_status=0
axis_info=$(timeout -k 2 5 getevent -p "$node" 2>&1) || axis_status=$?
printf '%s\n' "$axis_info"
if [ "$axis_status" -ne 0 ]; then
    echo "Axis query failed (status $axis_status)" >&2
    exit "$axis_status"
fi
# getevent can exit successfully even if an individual axis ioctl failed.
for axis in 0030 0035 0036 003a; do
    if ! printf '%s\n' "$axis_info" | grep -Eq "(^|[[:space:]])$axis[[:space:]]*:.*min -?[0-9]+, max -?[0-9]+, fuzz [0-9]+, flat [0-9]+, resolution [0-9]+"; then
        echo "Axis query omitted range/resolution for $axis" >&2
        exit 1
    fi
done
echo "axis_info_end"
echo "status=capturing"
started=$(date +%s)
printf 'start_unix_seconds=%s\n' "$started"
status=0
timeout -k 2 180 getevent -t -c 32768 "$node" || status=$?
case "$status" in
    0) echo "status=event-limit" ;;
    124) echo "status=time-limit" ;;
    *) echo "status=failed exit=$status"; exit "$status" ;;
esac
sync
