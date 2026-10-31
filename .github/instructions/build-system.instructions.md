---
description: "Use when editing the Makefile, sources.mk, config.mk or docker/Dockerfile: target help text, source pins, per-component dependencies, incremental builds."
applyTo: ["Makefile", "*.mk", "docker/**"]
---
# Build system

- Every user-facing target has `## help text`; `make` lists them.
- Anything that compiles or runs tools goes through `$(BUILDER)`, not the host.
- A new input is URL + version + SHA-256 in [sources.mk](../../sources.mk). Paths include the hash
  (e.g. `$(OUT)/src/mesa-$(MESA_SHA)-$(MESA_PATCH_SHA)`), so a pin or patch change gets a fresh tree.
- Keep dependencies per component: an input should rebuild only what uses it (vendor-only inputs
  hang off `$(ANDROID)/vendor_a.img`, the VM init script off `$(ANDROID)/system_ext_a.img`).
- Steps with their own incremental logic (Kbuild, Meson) depend on `FORCE`; their scripts must not
  touch outputs whose bytes did not change.
- No blanket clean target: `out/src/` may hold source edits and `out/android/disk.img` holds Android's data.
- Settings users may override go in [config.mk](../../config.mk) with `?=` and a one-line comment.
