#!/system/bin/sh
# Read: log directory and kernel boot ID. Rotate only our two named boot records.
# Signal readiness only after successful preparation; collector restarts do not rotate boots.
set -eu
umask 077
trap 'status=$?; if [ "$status" -ne 0 ]; then echo "dali_bootlog_prepare failed (status $status)" >&2; fi' EXIT

logs=$1
read -r boot_id < "$2"
test "${#boot_id}" -eq 36
case "$boot_id" in
    *[!0-9a-f-]*) echo "Invalid kernel boot ID" >&2; exit 1 ;;
esac
test -d "$logs" && test ! -L "$logs"
cd "$logs"
for directory in current previous; do
    test ! -L "$directory"
    if [ -e "$directory" ]; then
        test -d "$directory"
    fi
done

saved_id=
test ! -L current/boot-id
if [ -f current/boot-id ]; then
    read -r saved_id < current/boot-id
fi
if [ -n "$saved_id" ] && [ "$saved_id" != "$boot_id" ]; then
    if [ -d previous ]; then
        # Do not recursively delete: an unexpected file must stop rotation, not be erased.
        test ! -L previous/hardware.txt
        test ! -L previous/hardware.txt.tmp
        rm -f previous/boot-id previous/boot.txt
        for stream in kernel android android-boot; do
            rm -f "previous/$stream.log"
            for index in 1 2 3 4 5 6 7; do
                rm -f "previous/$stream.log.$index"
            done
        done
        rm -f previous/hardware.txt previous/hardware.txt.tmp
        rmdir previous
    fi
    mv current previous
fi
if [ ! -d current ]; then
    mkdir current
fi
printf '%s\n' "$boot_id" > current/boot-id
fingerprint=$(getprop ro.build.fingerprint)
test -n "$fingerprint"
graphics=$(getprop ro.boot.dali.graphics)
bootreason=$(getprop ro.boot.bootreason)
{
    echo "boot_id=$boot_id"
    echo "fingerprint=$fingerprint"
    echo "graphics_boot_property=$graphics"
    echo "bootreason=$bootreason"
} > current/boot.txt
sync
setprop sys.dali.bootlog.ready 1
