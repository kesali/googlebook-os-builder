#!/system/bin/sh
# Read: one Linux /proc/cpuinfo file. Write: the transient crypto-selection property.
#
#   crypto-select.sh CPUINFO
set -eu
trap 'status=$?; if [ "$status" -ne 0 ]; then echo "gbos-builder crypto selection failed (status $status)" >&2; fi' EXIT

cpuinfo=$1
if [ ! -r "$cpuinfo" ]; then
    echo "gbos-builder crypto: using portable libraries (cannot read $cpuinfo)"
    setprop sys.gbos_builder.crypto.mode portable
    exit 0
fi

processor_count=0
flags_count=0
all_cpus_have_sha_ni=1
while IFS= read -r line; do
    case "$line" in
        processor[[:space:]]*:*)
            processor_count=$((processor_count + 1))
            ;;
        flags[[:space:]]*:*)
            flags_count=$((flags_count + 1))
            case " $line " in
                *" sha_ni "*) ;;
                *) all_cpus_have_sha_ni=0 ;;
            esac
            ;;
    esac
done < "$cpuinfo"

if [ "$processor_count" -gt 0 ] && [ "$processor_count" -eq "$flags_count" ] \
        && [ "$all_cpus_have_sha_ni" -eq 1 ]; then
    echo "gbos-builder crypto: keeping Google's SHA-NI libraries"
    setprop sys.gbos_builder.crypto.mode stock
else
    echo "gbos-builder crypto: using portable libraries (SHA-NI missing or unreported on a CPU)"
    setprop sys.gbos_builder.crypto.mode portable
fi
