---
description: "Use when editing the Makefile, sources.mk, config.mk or docker/Dockerfile: target help text, source pins, per-component dependencies, incremental builds."
applyTo: ["Makefile", "*.mk", "hardware/**/*.mk", "docker/**"]
---
# Build system

- Keep Make recipes tab-indented and target dependencies explicit. Prefer named variables and
  simple rules over nested Make functions; explain non-obvious automatic variables where used.
- Every user-facing target has `## help text`; `make` lists them.
- Anything that compiles or runs tools goes through `$(BUILDER)`, not the host.
- Pin by something a person can read: a release tag or version. A Git source with a release tag
  gets `*_TAG` plus its commit in `*_REV`; the build checks they match, because tags can move.
  Without a tag, say in a comment where a person can check the commit (e.g. Google's manifest).
- Before adding a source build, look for an official prebuilt that works unchanged. A source pin's
  comment says why it is built (we patch it, or no suitable prebuilt exists).
- A new input is URL + version + SHA-256 in [sources.mk](../../sources.mk). Download and source
  paths include the hash (e.g. `$(DL)/mesa-$(MESA_SHA).tar.xz`,
  `$(OUT)/src/mesa-$(MESA_SHA)-$(MESA_PATCH_SHA)`), so a pin or patch change gets a new file or
  tree, and no rule needs to depend on `sources.mk` or the fetch script.
- Prefer an upstream release or commit that already has a needed fix over carrying a patch. When a
  pin changes, check each patch applied to that source and remove those upstream now covers.
- Keep dependencies per component: an input should rebuild only what uses it (vendor-only inputs
  hang off `$(ANDROID)/vendor_a.img`; each `android/<partition>/` directory and its files are
  prerequisites of that partition only).
- Selected [hardware recipes](../../hardware/) contribute optional native component Make
  fragments and partition lists. Declare source patches explicitly and preserve ordering;
  include recipe assets and directories in the consuming partition's prerequisites.
- Steps with their own incremental logic (Kbuild, Meson) depend on `FORCE`; their scripts must not
  touch outputs whose bytes did not change, and configure only when their settings change.
  Other rules always replace their output, so they run once per input change, not every build.
- No blanket clean target: `out/src/` may hold source edits and `out/android/disk.img` holds Android's data.
- Settings users may override go in [config.mk](../../config.mk) with `?=` and a one-line comment.
