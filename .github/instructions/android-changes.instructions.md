---
description: "Use when changing Google's Android image through android/ or hardware/ recipes: native lists and source-derived patches, preserving ordering and metadata."
applyTo: ["android/**", "hardware/**/*.install", "hardware/**/*.remove", "hardware/**/*.patches", "hardware/**/vendor/*.patch", "hardware/**/vendor_dlkm/*.patch", "hardware/**/module_ramdisk/*.patch"]
---
# Changes to Google's image

- Each target has one change directory: [android/system/](../../android/system/),
  [android/system_ext/](../../android/system_ext/), [android/vendor/](../../android/vendor/),
  [android/vendor_dlkm/](../../android/vendor_dlkm/),
  [android/module_ramdisk/](../../android/module_ramdisk/). The format is in the header of
  [scripts/android-overlay.sh](../../scripts/android-overlay.sh).
- Hardware-specific changes live in explicitly selected [recipes](../../hardware/).
  Base lists include native `<partition>.install`, `<partition>.remove` and
  `<partition>[-group].patches` fragments at explicit positions. Recipe-local install sources
  start with `./` relative to the recipe directory; patch fragments name recipe-relative files.
  Keep shared OS changes common and preserve application order. See [README](../../README.md#hardware-recipes).
- Change Google's image only when QEMU or the laptop requires it. First try a setting, such as
  the kernel command line, bootconfig or QEMU options, that leaves Google's files unchanged.
  Every patch must be checked and may need updating when Google's image changes.
- Delete whole files with `remove.list`; add files with `install.list` (path, mode, uid:gid,
  SELinux type or `-`, source). To replace a file, list it in both. Comment *why* above each group.
- Edit a Google text file only with a `.patch`. Generate it from Google's pristine file, never a
  previous build output, and keep it minimal:
  ```sh
  diff -u --label a/etc/foo --label b/etc/foo google/etc/foo edited/etc/foo >> android/vendor/foo.patch
  ```
  Start the patch with a few lines saying why it is needed and when it can be dropped (text before
  the first `---` is ignored by patch).
  Patches apply with `--fuzz=0`, so a Google image update that moves the context fails loudly.
- No Python or ad-hoc scripts that write changes; no binary or byte-offset edits.
- Every file in a change directory must be used by `install.list` or be a list/patch
  (`make test` checks this). `patches.list` declares overlay patch order, including recipe fragments;
  without it, standalone change directories retain sorted `*.patch` behavior.
- New first-stage modules: add them through the selected `module_ramdisk.install` fragment and to
  both `modules.dep` and `modules.load` in its source-derived patch; the build checks dependencies against
  Google's QEMU driver build. No trailing space after `name.ko:`.
