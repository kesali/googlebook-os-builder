---
name: bring-up-driver
description: "Use when adding or enabling a missing gbos-dali laptop kernel driver: establish host binding, prefer upstream configuration, package signed modules and aliases, preserve Google kABI, then verify physical enumeration before HAL routing."
---

# Bring up one missing driver

## Scope and approval

Read [project rules](../../../AGENTS.md), the [kernel spec](../../../docs/specs/kernel.md),
the [hardware spec](../../../docs/specs/laptop-hardware.md) and applicable
[file instructions](../../../.github/instructions/). Check the worktree first.
Establish whether the approved change is driver-only or includes userspace routing.
A missing app feature does not prove a missing driver.

## Procedure

1. Compare saved Android hardware/kernel evidence with read-only host Linux binding:
   PCI/USB IDs, revision, driver, child devices and exposed interfaces. Do not depend on
   unstable ALSA card numbers or generic card names.
2. Read the pinned upstream Kconfig, Makefiles, probe conditions, aliases and dependencies.
   Use unchanged upstream code first. Prefer a suitable pin or settings over a source patch;
   patch only when simpler options cannot work and the owner approves.
3. Check what Google already ships. Reuse suitable signed/prebuilt helpers unchanged; do not
   replace them merely because the same source build produces a copy.
4. For an approved module addition, wire every relevant surface:
   - [kernel config](../../../kernel/gki.config): explicit modular settings and dependencies;
     preserve the agreed built-ins, Google release, toolchain, certificate and ABI whitelist.
   - [publication list](../../../kernel/laptop-modules.list) and
     [packager](../../../scripts/laptop-modules.sh): selected upstream paths only; preserve
     path checks, signing, replacement refusal and symbol/CRC validation.
   - [install list](../../../android/vendor_dlkm/install.list): explicit signed modules.
   - [module metadata patch](../../../android/vendor_dlkm/modules.patch): dependencies,
     device aliases and only necessary, justified preloads. Generate Google text patches with
     `diff -u` from pristine originals; keep an explanatory header and removal condition.
   - [module checker](../../../tools/laptop_module_check.py) and
     [tests](../../../tests/test_laptop_modules.py): cover changed behavior and safeguard failures.
5. Distinguish module filenames from compiled names: hyphens and underscores can differ.
   Verify aliases and dependency closure against built `modinfo`, not guesses. Android
   hotplug may need explicit child-platform aliases/preloads; do not assume desktop modprobe
   behavior. Preserve unrelated working module metadata.
6. Document the candidate honestly, then obtain final validation approval. Use the
   [image validation workflow](../validate-image/SKILL.md): config/kABI, signatures/imports,
   dependencies/aliases, image metadata/fit, unchanged repeat and relevant QEMU regression.
   A failed check is a reason to fix the integration, not weaken the check.
7. Hand physical deployment to the owner. Require fresh laptop evidence of actual driver
   binding and its interface before declaring hardware success. QEMU cannot emulate the
   laptop's ACP/GPU. Driver enumeration alone does not establish app functionality.

For audio, keep working speakers/headphones intact. A newly exposed capture PCM and an Android
`InternalMic` route are separate stages; do not silently expand driver-only work into HAL or
SELinux changes. Update only affected component specs with results and the next agreed action.
