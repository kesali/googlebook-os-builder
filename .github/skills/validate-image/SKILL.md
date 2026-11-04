---
name: validate-image
description: "Use when validating a finished gbos-builder change: focused tests, kernel ABI, Android image metadata and fit, no-write repeat builds, and bounded graphical QEMU regression checks."
---

# Validate an image change

## Boundaries

- Read [project rules](../../../AGENTS.md), the [spec index](../../../docs/specs/README.md)
  and the affected component spec. Check the worktree and preserve unrelated changes.
- Run validation only after the owner agrees the final implementation is ready. Ask before
  long builds or downloads. Build inside the existing builder.
- Never write physical disks, recreate `out/android/disk.img`, delete editable source trees,
  weaken checks or change SELinux enforcement. Stop a running VM before updating its image;
  stop only task-owned processes, otherwise ask the owner.

## Procedure

1. Choose checks proportional to the change. Documentation-only changes need link checks;
   logic needs focused tests; image changes need an image build; boot/runtime changes need
   a bounded boot check. Do not start a full suite without a reason.
2. Run selected unittest modules together through the builder, for example:
   ```sh
   scripts/builder.sh python3 tools/run_tests.py \
     tests/test_laptop_modules.py tests/test_overlay.py hardware/drivers/hda-audio/tests
   ```
   Select files/directories for the actual diff; the example is not a mandatory list.
   `make test` also discovers all recipe-local tests, regardless of build selection.
3. For image changes, run `make android-image`. Keep output and timings under a
   task-specific ignored `out/` directory. Require the existing config/kABI checks,
   compiled-module checks, filesystem metadata read-back and partition-fit checks to pass.
   Never bypass a failed safeguard to obtain an image.
4. For build behavior changes, compare rebuilt outputs and metadata against a known baseline.
   For incremental-build verification, record published artifact and disk sizes/timestamps,
   repeat the same build and compare them. Require no partition or boot-file writes and no
   published-output timestamp changes. Measure build time separately from guest startup.
5. For boot/runtime changes, run `make qemu-check`. It checks boot completion,
   stable service PIDs, SELinux enforcing and softpipe; inspect the resulting
   [screenshot](../../../out/qemu/screen.png) yourself. A property or PNG dimensions alone
   do not establish a usable screen. Verify an actual input response before claiming input
   works. See the [QEMU spec](../../../docs/specs/qemu.md) for shutdown and console pitfalls.
6. Confirm the bounded VM exited. Retain useful evidence, remove task-created scratch files,
   and update only affected specs with actual results and remaining hardware checks.

## Report

State commands/results, whether the screenshot was inspected, no-write repeat evidence,
and what was not tested. QEMU cannot prove physical AMD GPU, ACP microphone, HDMI audio or
camera behavior. Do not deploy or commit as a side effect of validation.
