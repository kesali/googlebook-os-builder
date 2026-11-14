#!/system/bin/sh
set -eu

if [ "$#" -ne 1 ] || [ ! -d "$1/class/drm" ]; then
    echo "graphics selector: expected a sysfs root containing class/drm" >&2
    exit 1
fi

sys_root=$1
selected_profile=softpipe
found_gpu=false

for device in "$sys_root"/class/drm/card[0-9]*/device; do
    if [ ! -L "$device/driver" ]; then
        continue
    fi

    driver_path=$(readlink "$device/driver") || {
        echo "graphics selector: cannot read $device/driver" >&2
        exit 1
    }
    driver=${driver_path##*/}
    case "$driver" in
        amdgpu)
            candidate=amd
            ;;
        i915|xe)
            candidate=intel-anv
            # shortcut: only 8086:1616 selects HasVK, expand generation detection when another
            # Intel generation is verified.
            if [ -r "$device/device" ]; then
                device_id=$(cat "$device/device") || {
                    echo "graphics selector: cannot read $device/device" >&2
                    exit 1
                }
                if [ "$device_id" = "0x1616" ]; then
                    candidate=intel-hasvk
                fi
            else
                echo "graphics selector: cannot inspect Intel device ID; trying ANV" >&2
            fi
            ;;
        *)
            continue
            ;;
    esac

    if [ "$found_gpu" = false ]; then
        selected_profile=$candidate
        found_gpu=true
    fi
    if [ -r "$device/boot_vga" ]; then
        boot_vga=$(cat "$device/boot_vga") || {
            echo "graphics selector: cannot read $device/boot_vga" >&2
            exit 1
        }
        if [ "$boot_vga" = "1" ]; then
            selected_profile=$candidate
            break
        fi
    fi
done

echo "graphics selector: profile=$selected_profile"
setprop sys.gbos_builder.graphics "$selected_profile"
