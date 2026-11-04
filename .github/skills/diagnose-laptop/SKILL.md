---
name: diagnose-laptop
description: "Use when diagnosing gbos-builder laptop boot loops, app crashes, missing devices or slow behavior: safely recover saved Android logs, identify the failing layer and verify against authoritative upstream sources."
---

# Diagnose a laptop failure

## Boundaries

Read [project rules](../../../AGENTS.md), the [spec index](../../../docs/specs/README.md),
the affected spec and the worktree before investigating. Diagnosis is not permission to
change code, mount personal files, repair filesystems or deploy an image. Keep private logs
local; report only relevant filtered excerpts.

## Procedure

1. Establish the exact symptom, selected boot entry, last known working build and whether
   the failure is reproducible. Ask for missing evidence rather than assuming a cause.
2. Prefer already retrieved logs under ignored `out/`. Persistent capture is opt-in: for fresh
   evidence, have the owner reboot with **Googlebook OS (diagnostic logs)** and reproduce the
   problem before retrieval. Normal boots preserve old captures, so verify their identity/time.
   This is a self-service/AI-assisted workflow, not a promise to retain every crash. Follow the
   [log recovery procedure](../../../docs/specs/laptop-hardware.md#recovering-the-new-boot-logs)
   when new evidence is needed: have the owner run `make laptop-logs` and select the USB.
   Read the resulting `out/laptop-logs/latest/current/` and `previous/`; do not ask for manual
   debugfs/chown commands unless the convenience tool fails. It needs no image build.
   For manual recovery, identify the USB by stable identity, verify its current
   layout and locate metadata by partition name, never a remembered partition number.
   Use read-only debugfs or an owner-approved `ro,noload` mount; retrieve only the relevant
   `gbos-builder-bootlog/current/` and `previous/` files. Let the owner handle sudo credentials.
3. Never replay a journal or repair the USB directly. If unclean shutdown prevents reading,
   explain the problem and ask before recovery on a private copy. Follow the spec's tmpfs
   and swap precautions; never retain copied security state as ordinary evidence.
4. Correlate `boot-id`, `boot.txt`, `hardware.txt`, kernel logs, `android-boot.log*`,
   Android logs and `crash.log*` by boot and time. Missing retained evidence is not proof
   that no failure occurred. Check rotated streams and the previous boot when appropriate.
5. Isolate the layer before proposing changes:
   - Device absent: inspect saved PCI/USB discovery, driver binding, aliases, firmware and
     probe errors. Compare host Linux read-only without recording audio or opening personal data.
   - Device present but unusable: inspect HAL enumeration, selected card/PCM, framework routes,
     permissions and relevant SELinux denials. Do not add a driver for an already detected device.
   - App exit: inspect the fatal/tombstone evidence, app ABI and selected native bridge.
     Distinguish translator, graphics, codec and app errors; do not infer one from the symptom.
   - Slowness: measure the bottleneck and compare the smallest practical options first.
6. Trace the relevant implementation in authoritative upstream source and issue discussions.
   Treat earlier hobby-port findings as hypotheses; verify them against local logs and tests.
   Try unchanged upstream, a suitable pinned fix, settings, then whole-file additions/removals
   before proposing a source patch. Do not edit compiled executables.
7. Present the evidence, uncertainty, one focused recommendation and its verification method.
   Wait for implementation approval. Keep HDMI, camera, microphone and unrelated failures
   separate unless evidence establishes a shared cause.

## Live console

Use the existing `make console COMMAND='...'` interface only while the VM runs. Filter logs
on the guest, for example `logcat -d -s AudioFlinger | tail -n 200`; never dump unbounded
`logcat -b all`. A serial shell or boot-complete property is not proof of a usable screen.
