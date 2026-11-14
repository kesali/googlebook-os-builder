# Laptop hardware

**Status:** partial — the goal is best-effort support for most x86-64-v3 laptops, starting
with USB boot, native display and basic input. Current MSI graphics work is owner-reported;
the camera is not detected and shows a black screen.
**Last verified:** 2026-11-13 — owner report; no new hardware logs supplied.

## Goal
Provide best-effort support for most x86-64-v3 laptops, starting with USB boot, native
display and basic input. Keep the MSI Modern 15 B7M, Lenovo E50-80 and QEMU as the
available regression targets.

## Current state
| Device | Current status |
|---|---|
| MSI graphics | Owner reports working on the Mesa 26.3.0 image; renderer not confirmed |
| MSI camera | Not detected; camera app shows a black screen (owner report) |
| MSI Wi-Fi, touchpad, keyboard, speakers, microphone and video | Not retested on Mesa 26.3.0 |
| MSI Bluetooth, HDMI audio, headphones, brightness slider | Not verified |
| Lenovo peripherals | Current-image status unverified |
| Other Intel display devices | i915 alias passes GKI/image checks; Google Xe remains included; physical binding and display unverified |

Common network, touchpad and audio recipes package selected modules, firmware and
device-specific configuration. New hardware claims require physical testing; QEMU cannot
verify laptop devices.

## Decisions
- Keep QEMU and the MSI/Lenovo as available regression targets. No installer or dual
  boot. Treat additional laptop support as best-effort until physical results exist.
- Add only missing drivers, sign modules with the kernel key, and preserve Google's
  helpers and ABI checks.
- Keep native display drivers; do not add a simpledrm fallback. The generic i915 alias
  only requests module loading; preserve Google's Xe module and aliases, and let the
  drivers' PCI tables and force-probe checks determine binding.
- Keep model-specific density, audio routing and backlight naming scoped to the known
  devices; do not infer them from a generic graphics-family match.
- Keep Google's audio and lights HALs. Do not grant generic sysfs write access or
  advertise unverified outputs as working.
- Use the reviewed USB identity, layout checks, explicit confirmation and read-back for
  owner-run updates. Never reflash existing data or write physical media during validation.
- Retrieve diagnostics only from the opt-in boot-log partition; keep logs private and
  share filtered excerpts.

## Files
- [hardware/drivers.list](../../hardware/drivers.list) and
  [hardware/devices.list](../../hardware/devices.list) — selected recipes.
- [kernel/laptop-modules.list](../../kernel/laptop-modules.list) and
  [kernel/firmware.list](../../kernel/firmware.list) — modules and firmware.
- [hardware/drivers/hda-audio/](../../hardware/drivers/hda-audio/) — bounded audio-card
  selection.
- [android/system_ext/hardware-snapshot.sh](../../android/system_ext/hardware-snapshot.sh) —
  read-only device diagnostics.
- [tools/update_usb.py](../../tools/update_usb.py) — owner-run incremental update.

## Verify
Run `make test` and `make android-image`; require kernel ABI, module, filesystem metadata
and fit checks. Repeat the build and confirm no partition or boot-file writes. Use
disposable enforcing QEMU for boot regressions. Physical peripheral checks are owner-run.

## Pitfalls
- Hardware card and device numbers vary; do not copy QEMU mixer values into laptop
  profiles.
- SELinux may intentionally hide card IDs from the serial shell; use the scoped selector
  and read-only snapshot.
- A boot-complete property or correctly sized screenshot does not prove a usable desktop.
- Never recover a journal on a physical USB; use an owner-approved temporary copy.

## Actions
- [ ] Validate the generic Intel slice — done when a laptop reports native display and
  basic input; do not claim untested devices work.
- [ ] Diagnose the MSI camera — done when current diagnostic logs identify whether the
  USB device is enumerated and why preview fails.
- [ ] Retest remaining MSI peripherals — done when the owner confirms the current image's
  Wi-Fi, input, audio, video, Bluetooth, brightness and HDMI behavior.
