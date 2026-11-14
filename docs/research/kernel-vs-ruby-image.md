# Does the pinned kernel match the Ruby image's kernel?

Researched 2026-11-14. No builds run, no devices touched. Primary sources only.

## What "Ruby image" is
- `sources.mk` (RUBY_RECOVERY_*): Google's official `ruby-user` recovery, build **16693588**,
  `https://dl.google.com/device/recovery/ruby-user/16693588/recovery.zip`, pinned by SHA-256.
  `config.mk` lines 6-7 make it the default `RECOVERY_IMAGE`.
- Unpacked metadata (`out/google/inventory.txt`, from `make unpack`): fingerprint
  `Android/desktop_system/desktop:17/CL3B.260622.276.R5/16693588:user/release-keys`.
- `docs/build-guide.md:381` calls it the Lenovo Googlebook 15 (`ruby`). That device label is
  repo prose, not a Google source; the Google URL only proves the codename `ruby`.
  Not identified: other Ruby builds/revisions; only 16693588 is examined.

## Primary link: GKI_BUILD 16302624 -> source commit
Google's CI manifest for the build (`GKI_BUILD` in `sources.mk`),
<https://ci.android.com/builds/submitted/16302624/kernel_x86_64/latest/raw/manifest_16302624.xml>
(fetched 2026-11-14), contains:
- `<superproject name="kernel/superproject" remote="aosp" revision="common-android17-6.18-2026-06" />`
- `<project path="common" name="kernel/common" revision="3938c8d97142d5cf31543aa96f864a2cf832dda0" upstream="android17-6.18-2026-06" dest-branch="android17-6.18-2026-06" />`

So Google's build 16302624 was built from kernel/common commit 3938c8d9..., which is `KERNEL_REV`
in `sources.mk`. The tag `android17-6.18-2026-06_r52` on android.googlesource.com/kernel/common
(queried via `?format=JSON`) resolves to the same commit: author Mon Sep 07 2026, committer
Wed Sep 09 2026 ("ANDROID: pKVM: x86: Mediate host's GSMI commands to coreboot's SMM").
"June" is the release-branch/tag name, not the commit date.

## Source/release match (verified)
| Item | Local inspection of the image (`out/google/kernel/version.txt`, from `make unpack`) | This repo |
|---|---|---|
| Release | `6.18.21-android17-5-g3938c8d97142-ab16302624` | same (`out/gki/build/include/config/kernel.release`) |
| Commit | `g3938c8d97142` | `KERNEL_REV 3938c8d97142d5cf31543aa96f864a2cf832dda0` (`sources.mk`) |
| Google build | `ab16302624` | `GKI_BUILD := 16302624` |
| Compiler | clang r584948c (22.0.1) | `CLANG_DIR := clang-r584948c` |

The extracted image metadata is inspection evidence only; the authoritative source link is the
manifest above. It also agrees: the image was built Wed Sep 9 14:58:55 UTC 2026, matching the
commit's committer date. The recovery fingerprint CL3B.260622 (June 22) is the system build, a
separate component. The checked-out source `Makefile` reports 6.18.21.

## Not binary/config identity
Matching source and release string does not mean the built kernel is identical to Google's
(see below): our config differs deliberately and the bzImage is not byte-identical.


## Config differences (deliberate)
Compared Google's config extracted from the image (`out/google/kernel/config`) with the built `out/gki/build/.config`. 24 Google settings
changed, all from `kernel/gki.config` and hardware recipes: `SYSTEM_TRUSTED_KEYS` set to Google's
certs; AMD pinctrl/I2C-HID/DesignWare, i915, amdgpu, ACPI_WMI, ath/mt76/realtek WLAN, cfg80211,
HCIBTUSB, PS2 mouse, RMI4, AMD ACP sound, IGB, EROFS zstd, RELAY, HWMON enabled. Many more
options are only added (new modules). `scripts/gki-kernel.sh` also sets KBUILD_BUILD_TIMESTAMP,
user and host, so those differ from the image's `kleaf@build-host`.

## ABI/module compatibility
`scripts/gki-kernel.sh` forces Google's config as base, the same release string, and
KBUILD_GENDWARFKSYMS_STABLE; `tools/kabi_check.py` compares Module.symvers with Google's
`vmlinux.symvers` (GKI_SYMVERS_SHA). `docs/specs/kernel.md` (verified 2026-11-14) reports all
4,501 Google exports and CRCs unchanged. I did not re-run that check; it is repo-reported.
The bzImage is not byte-identical to Google's because of the config changes above.
