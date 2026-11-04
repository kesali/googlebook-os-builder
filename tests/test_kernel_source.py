"""Check kernel source preparation using local fake repositories, never the real source tree."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


def inspect_kernel_recipes(*arguments):
    return subprocess.run(
        ["make", "--no-print-directory", "-f", str(ROOT / "Makefile"), "-f", "-",
         "inspect-kernel-recipes", *arguments],
        cwd=ROOT, capture_output=True, text=True,
        input=".PHONY: inspect-kernel-recipes\ninspect-kernel-recipes:\n"
              "\t@printf '%s\\n' '$(KERNEL_PATCHES)' '$(KERNEL_PATCH_SHA)' '$(KERNEL_SRC)'\n",
    )


def recipe_patch(name):
    matches = list((ROOT / "hardware/drivers").glob(f"*/{name}"))
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one recipe patch named {name}: {matches}")
    return matches[0]


class KernelRecipeTests(unittest.TestCase):
    def test_selected_patches_keep_baseline_order_and_bytes(self):
        result = inspect_kernel_recipes()
        self.assertEqual(result.returncode, 0, result.stderr)
        paths, digest, source = result.stdout.splitlines()
        self.assertEqual(paths.split(), [
            "hardware/drivers/drm-handoff/drm-firmware-handoff.patch",
            "hardware/drivers/amdgpu/msi-backlight.patch",
            "hardware/drivers/amdgpu/amdgpu-fast-flips.patch",
            "hardware/drivers/renoir-acp/renoir-capture-buffers.patch",
            "hardware/drivers/i915/i915-gen4-primary-alpha.patch",
        ])
        patch_bytes = b"".join((ROOT / path).read_bytes() for path in paths.split())
        self.assertEqual(hashlib.sha256(patch_bytes).hexdigest(),
                         "0af5689168b66909fd4b25dff041b637ceb32cb6bada48957274ed2407a651b2")
        self.assertTrue(source.endswith("-" + digest))
        self.assertEqual(hashlib.sha256(patch_bytes).hexdigest(), digest)

    def test_selection_and_order_change_only_the_source_patch_hash(self):
        original = inspect_kernel_recipes()
        self.assertEqual(original.returncode, 0, original.stderr)
        original_source = original.stdout.splitlines()[2]
        for selected in ("i915", "i915 renoir-acp amdgpu", ""):
            with self.subTest(selected=selected):
                result = inspect_kernel_recipes(f"HARDWARE_DRIVERS=cpu-vex drm-handoff {selected}")
                self.assertEqual(result.returncode, 0, result.stderr)
                paths, digest, source = result.stdout.splitlines()
                self.assertEqual(paths.split()[0], "hardware/drivers/drm-handoff/drm-firmware-handoff.patch")
                self.assertNotEqual(source, original_source)
                self.assertEqual(source.rsplit("-", 1)[0], original_source.rsplit("-", 1)[0])
                self.assertTrue(source.endswith("-" + digest))
                if selected == "i915":
                    self.assertEqual(len(paths.split()), 2)

    def test_unknown_selected_recipe_fails_instead_of_silently_omitting_it(self):
        result = inspect_kernel_recipes("HARDWARE_DRIVERS=cpu-vex missing-driver")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing hardware recipe: hardware/drivers/missing-driver", result.stderr)

    def test_moved_patch_timestamp_does_not_replace_existing_source(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            (source / ".ready").touch()
            os.utime(source / ".ready", (1, 1))
            builder_ready = source / "builder-ready"
            builder_ready.touch()
            result = subprocess.run(
                ["make", "--no-print-directory", "-n", "sources",
                 f"KERNEL_SRC={source}", f"BUILD_READY={builder_ready}"],
                cwd=ROOT, capture_output=True, text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("kernel-source.sh", result.stdout)
            self.assertNotIn("fetch.sh", result.stdout)


class VendoredEmulatorTests(unittest.TestCase):
    def make(self, *arguments, extra_rules=None):
        command = ["make", "--no-print-directory", "-f", str(ROOT / "Makefile")]
        if extra_rules is not None:
            command.extend(["-f", "-"])
        return subprocess.run(
            [*command, *arguments], cwd=ROOT, input=extra_rules,
            capture_output=True, text=True,
        )

    def test_vendored_patch_matches_working_baseline(self):
        patch = ROOT / "hardware/drivers/cpu-vex/vex-emulate.patch"
        self.assertEqual(
            hashlib.sha256(patch.read_bytes()).hexdigest(),
            "d8decdcffc7a87aea0386ec3ca8476e607f5a26f0ef127e4f051f65ab84e8e0f",
        )
        self.assertNotIn("$(EMU_URL)", (ROOT / "Makefile").read_text())
        self.assertNotIn("\nEMU_URL :=", (ROOT / "sources.mk").read_text())

    def test_new_patch_timestamp_does_not_replace_existing_source(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory)
            ready = source / ".ready"
            ready.touch()
            os.utime(ready, (1, 1))
            builder_ready = source / "builder-ready"
            builder_ready.touch()
            result = self.make(
                "-n", "sources", f"KERNEL_SRC={source}", "KERNEL_PATCHES=",
                f"BUILD_READY={builder_ready}",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertNotIn("kernel-source.sh", result.stdout)
            self.assertNotIn("fetch.sh", result.stdout)

    def test_emulator_content_changes_select_a_new_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            patch = Path(directory) / "emulator.patch"
            caches = []
            for contents in (b"original patch\n", b"modified patch\n"):
                patch.write_bytes(contents)
                result = self.make(
                    "inspect-emulator", f"EMU_PATCH={patch}",
                    extra_rules=".PHONY: inspect-emulator\n"
                    "inspect-emulator:\n\t@printf '%s\\n' '$(KERNEL_CACHE)'\n",
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertTrue(
                    result.stdout.strip().endswith(hashlib.sha256(contents).hexdigest()),
                    result.stdout,
                )
                caches.append(result.stdout.strip())
            self.assertNotEqual(caches[0], caches[1])


class KernelSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name)
        self.origin = self.work / "origin"
        subprocess.run(["git", "init", "--quiet", str(self.origin)], check=True)
        (self.origin / "state.txt").write_text("original\n")
        self.git("add", "state.txt")
        self.commit("Original source")
        self.git("tag", "test-release")
        self.revision = self.git("rev-parse", "HEAD").stdout.strip()

        self.cache = self.work / "existing-source"
        subprocess.run(
            ["git", "clone", "--quiet", "--depth=1", self.origin.as_uri(), str(self.cache)],
            check=True,
        )
        (self.cache / "state.txt").write_text("local source edit\n")
        self.emulator_patch = self.work / "emulator.patch"
        self.handoff_patch = self.work / "handoff.patch"
        self.backlight_patch = self.work / "backlight.patch"
        self.emulator_patch.write_text(self.patch("original", "emulator"))
        self.handoff_patch.write_text(self.patch("emulator", "handoff"))
        self.backlight_patch.write_text(self.patch("handoff", "backlight"))
        self.destination = self.work / "new-source"

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.origin), *arguments],
            check=True, capture_output=True, text=True,
        )

    def commit(self, message):
        self.git("-c", "user.name=Test", "-c", "user.email=test@example.invalid",
                 "commit", "--quiet", "-m", message)

    def patch(self, before, after):
        return f"--- a/state.txt\n+++ b/state.txt\n@@ -1 +1 @@\n-{before}\n+{after}\n"

    def prepare(self, cache=None, env=None):
        return subprocess.run(
            ["bash", str(ROOT / "scripts/kernel-source.sh"), str(self.origin), "test-release",
             self.revision, str(cache if cache is not None else self.cache), str(self.destination),
             str(self.emulator_patch), str(self.handoff_patch), str(self.backlight_patch)],
            capture_output=True, text=True, env=env,
        )

    def test_patches_in_order_without_copying_existing_source_edits(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "state.txt").read_text(), "backlight\n")
        self.assertTrue((self.destination / ".ready").exists())
        self.assertEqual((self.cache / "state.txt").read_text(), "local source edit\n")

    def test_source_can_be_prepared_without_an_existing_cache(self):
        result = self.prepare(cache=self.work / "missing-cache")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "state.txt").read_text(), "backlight\n")

    def test_moved_tag_is_rejected_even_with_cached_objects(self):
        (self.origin / "state.txt").write_text("new revision\n")
        self.git("add", "state.txt")
        self.commit("Move release")
        self.git("tag", "-f", "test-release")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("does not point at the pinned commit", result.stderr)
        self.assertFalse(self.destination.exists())

    def test_failed_second_patch_leaves_no_partial_checkout(self):
        self.handoff_patch.write_text(self.patch("different", "handoff"))
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.work.glob("new-source.partial.*")), [])
        self.assertEqual((self.cache / "state.txt").read_text(), "local source edit\n")

    def test_existing_destination_is_never_replaced(self):
        self.destination.mkdir()
        (self.destination / "owner-edit").write_text("keep\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to replace", result.stderr)
        self.assertEqual((self.destination / "owner-edit").read_text(), "keep\n")

    def test_failed_backlight_patch_leaves_no_partial_checkout(self):
        self.backlight_patch.write_text(self.patch("wrong source", "backlight"))
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.work.glob("new-source.partial.*")), [])
        self.assertEqual((self.cache / "state.txt").read_text(), "local source edit\n")

    def test_dangling_destination_symlink_is_not_followed_or_replaced(self):
        target = self.work / "missing-owner-source"
        self.destination.symlink_to(target, target_is_directory=True)
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to replace", result.stderr)
        self.assertTrue(self.destination.is_symlink())
        self.assertFalse(target.exists())

    def test_destination_created_during_checkout_is_not_modified(self):
        fake_bin = self.work / "fake-bin"
        fake_bin.mkdir()
        patch = fake_bin / "patch"
        patch.write_text(
            '#!/bin/sh\n'
            '"$REAL_PATCH" "$@"\n'
            'status=$?\n'
            'if [ "$status" -eq 0 ]; then\n'
            '    mkdir -p "$TEST_DESTINATION"\n'
            '    printf "keep\\n" > "$TEST_DESTINATION/owner-edit"\n'
            'fi\n'
            'exit "$status"\n'
        )
        patch.chmod(0o755)
        env = os.environ.copy()
        env["PATH"] = str(fake_bin) + os.pathsep + env["PATH"]
        env["REAL_PATCH"] = shutil.which("patch")
        env["TEST_DESTINATION"] = str(self.destination)

        result = self.prepare(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Refusing to replace", result.stderr)
        self.assertEqual((self.destination / "owner-edit").read_text(), "keep\n")
        self.assertEqual([path.name for path in self.destination.iterdir()], ["owner-edit"])
        self.assertEqual(list(self.work.glob("new-source.partial.*")), [])


def patched_text(name):
    """The new side of a source patch: context and added lines, without the header."""
    patch = recipe_patch(name).read_text()
    return "\n".join(line[1:] for line in patch.splitlines()
                     if line.startswith((" ", "+")) and not line.startswith("+++"))


class RenoirCapturePatchTests(unittest.TestCase):
    def test_patch_accepts_android_buffers_and_preserves_legacy_limits(self):
        original = (
            "#define CAPTURE_MIN_NUM_PERIODS     4\n"
            "#define CAPTURE_MAX_NUM_PERIODS     4\n"
            "#define CAPTURE_MAX_PERIOD_SIZE     8192\n"
            "#define CAPTURE_MIN_PERIOD_SIZE     4096\n"
            "\n"
            "#define MAX_BUFFER (CAPTURE_MAX_PERIOD_SIZE * CAPTURE_MAX_NUM_PERIODS)\n"
            "#define MIN_BUFFER MAX_BUFFER\n"
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            header = source / "sound/soc/amd/renoir/rn_acp3x.h"
            header.parent.mkdir(parents=True)
            header.write_text(original)
            subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1",
                 "-i", str(recipe_patch("renoir-capture-buffers.patch"))],
                cwd=source, check=True, capture_output=True, text=True,
            )
            text = header.read_text()
        self.assertEqual(text, original.replace(
            "CAPTURE_MIN_NUM_PERIODS     4", "CAPTURE_MIN_NUM_PERIODS     2").replace(
            "CAPTURE_MIN_PERIOD_SIZE     4096", "CAPTURE_MIN_PERIOD_SIZE     1024"))
        limits = {name: int(value) for directive, name, value in
                  (line.split() for line in text.splitlines() if line.startswith("#define CAPTURE_"))}
        for frames, periods in ((480, 2), (960, 2), (512, 4), (1024, 4)):
            with self.subTest(frames=frames, periods=periods):
                period_bytes = frames * 2 * 4
                self.assertGreaterEqual(periods, limits["CAPTURE_MIN_NUM_PERIODS"])
                self.assertLessEqual(periods, limits["CAPTURE_MAX_NUM_PERIODS"])
                self.assertGreaterEqual(period_bytes, limits["CAPTURE_MIN_PERIOD_SIZE"])
                self.assertLessEqual(period_bytes, limits["CAPTURE_MAX_PERIOD_SIZE"])
                self.assertLessEqual(period_bytes * periods, 32768)
        self.assertEqual(limits, {
            "CAPTURE_MIN_NUM_PERIODS": 2, "CAPTURE_MAX_NUM_PERIODS": 4,
            "CAPTURE_MIN_PERIOD_SIZE": 1024, "CAPTURE_MAX_PERIOD_SIZE": 8192,
        })

    def test_patch_is_in_kernel_source_inputs(self):
        result = inspect_kernel_recipes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("hardware/drivers/renoir-acp/renoir-capture-buffers.patch",
                      result.stdout.splitlines()[0].split())


class IntelPrimaryAlphaPatchTests(unittest.TestCase):
    def test_primary_alpha_patch_is_wired_and_keeps_reference_changes(self):
        name = "i915-gen4-primary-alpha.patch"
        result = inspect_kernel_recipes()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(f"hardware/drivers/i915/{name}", result.stdout.splitlines()[0].split())
        patch = recipe_patch(name).read_text()
        self.assertIn("70538d7", patch)
        self.assertEqual(patch.count("+\tDRM_FORMAT_ARGB8888,"), 2)
        self.assertEqual(patch.count("+\tDRM_FORMAT_ABGR8888,"), 2)
        self.assertEqual(
            [line for line in patch.splitlines() if line.startswith("--- ")],
            ["--- a/drivers/gpu/drm/i915/display/i9xx_plane.c"],
        )

    def test_alpha_scanout_preserves_vlv_chv_and_opaque_formats(self):
        text = patched_text("i915-gen4-primary-alpha.patch")
        switch = text[text.index("\tcase DRM_FORMAT_XBGR8888:"):
                      text.index("\tcase DRM_FORMAT_XRGB2101010:")]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "alpha.c"
            program = Path(temporary) / "alpha"
            source.write_text(
                "#include <assert.h>\n#include <stdbool.h>\n"
                "enum { DRM_FORMAT_XBGR8888, DRM_FORMAT_ARGB8888, DRM_FORMAT_ABGR8888 };\n"
                "enum { DISP_FORMAT_RGBX888=1, DISP_FORMAT_BGRX888=2,\n"
                "       DISP_FORMAT_BGRA888=4, DISP_FORMAT_RGBA888=8 };\n"
                "static int control(bool vlv, bool chv, int format) {\n"
                "    struct { struct { bool valleyview, cherryview; } platform; }\n"
                "        device = { {vlv, chv} }, *display = &device;\n"
                "    int dspcntr = 0;\n"
                "    switch (format) {\n" + switch + "\n    }\n"
                "    return dspcntr;\n}\n"
                "int main(void) {\n"
                "    for (int vlv=0; vlv<=1; vlv++) for (int chv=0; chv<=1; chv++) {\n"
                "        assert(control(vlv,chv,DRM_FORMAT_XBGR8888)==DISP_FORMAT_RGBX888);\n"
                "        assert(control(vlv,chv,DRM_FORMAT_ARGB8888)==\n"
                "               (vlv||chv ? DISP_FORMAT_BGRA888 : DISP_FORMAT_BGRX888));\n"
                "        assert(control(vlv,chv,DRM_FORMAT_ABGR8888)==\n"
                "               (vlv||chv ? DISP_FORMAT_RGBA888 : DISP_FORMAT_RGBX888));\n"
                "    }\n}\n"
            )
            subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(program)],
                           check=True, capture_output=True, text=True)
            subprocess.run([str(program)], check=True)


class BacklightPatchTests(unittest.TestCase):
    def test_only_first_msi_panel_uses_google_hal_name(self):
        text = patched_text("msi-backlight.patch")
        naming = text[text.index("\tsnprintf(bl_name"):text.index("\tdm->backlight_dev")]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "backlight.c"
            program = Path(temporary) / "backlight"
            source.write_text(
                "#include <stdio.h>\n#include <stdlib.h>\n#include <string.h>\n"
                "#define DMI_SYS_VENDOR 0\n#define DMI_PRODUCT_NAME 1\n"
                "#define strscpy(dst, src, size) snprintf(dst, size, \"%s\", src)\n"
                "static const char *dmi[2];\n"
                "static int dmi_match(int key, const char *value) {\n"
                "    return strcmp(dmi[key], value) == 0;\n}\n"
                "int main(int argc, char **argv) {\n"
                "    if (argc != 5) return 2;\n"
                "    dmi[0] = argv[1]; dmi[1] = argv[2];\n"
                "    struct minor { int index; } primary = { atoi(argv[3]) };\n"
                "    struct drm { struct minor *primary; } device = { &primary }, *drm = &device;\n"
                "    struct connector { int bl_idx; } connector = { atoi(argv[4]) }, *aconnector = &connector;\n"
                "    char bl_name[16];\n" + naming + "\n    puts(bl_name);\n}\n"
            )
            subprocess.run(["cc", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(program)],
                           check=True, capture_output=True, text=True)
            cases = [
                ("Micro-Star International Co., Ltd.", "Modern 15 B7M", "0", "0", "backlight"),
                ("Micro-Star International Co., Ltd.", "Modern 15 B7M", "2", "0", "backlight"),
                ("Micro-Star International Co., Ltd.", "Modern 15 B7M", "2", "1", "amdgpu_bl3"),
                ("Other", "Modern 15 B7M", "2", "0", "amdgpu_bl2"),
                ("Micro-Star International Co., Ltd.", "Other", "2", "0", "amdgpu_bl2"),
            ]
            for vendor, model, minor, panel, expected in cases:
                with self.subTest(vendor=vendor, model=model, minor=minor, panel=panel):
                    result = subprocess.run([str(program), vendor, model, minor, panel],
                                            check=True, capture_output=True, text=True)
                    self.assertEqual(result.stdout.strip(), expected)


class FastFlipPatchTests(unittest.TestCase):
    def test_old_display_engines_reset_planes_only_for_real_modesets(self):
        text = patched_text("amdgpu-fast-flips.patch")
        helper = text[text.index("static bool dm_state_needs_modeset"):
                      text.index("static bool should_reset_plane")]
        start = text.index("\tif (amdgpu_ip_version(adev, DCE_HWIP, 0) < IP_VERSION(3, 2, 0)")
        condition = text[start:text.index("\t\treturn true;", start) + len("\t\treturn true;")]
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "fast_flips.c"
            program = Path(temporary) / "fast_flips"
            source.write_text(
                "#include <stdbool.h>\n#include <stdio.h>\n#include <stdlib.h>\n"
                "struct drm_crtc { int unused; };\n"
                "struct drm_crtc_state { bool needs_modeset; };\n"
                "struct drm_atomic_state { bool allow_modeset; int crtcs; struct drm_crtc_state *crtc; };\n"
                "#define for_each_new_crtc_in_state(state, c, new_state, i) \\\n"
                "    for ((i) = 0; (i) < (state)->crtcs && ((c) = NULL, (void)(c), \\\n"
                "         (new_state) = &(state)->crtc[i], 1); (i)++)\n"
                "static bool drm_atomic_crtc_needs_modeset(const struct drm_crtc_state *state) {\n"
                "    return state->needs_modeset;\n}\n"
                "#define IP_VERSION(major, minor, revision) (((major) << 16) | ((minor) << 8) | (revision))\n"
                "#define DCE_HWIP 0\n"
                "struct amdgpu_device { int dce; };\n"
                "static int amdgpu_ip_version(const struct amdgpu_device *adev, int block, int instance) {\n"
                "    (void)block; (void)instance; return adev->dce;\n}\n"
                + helper +
                "static bool forced_reset(struct drm_atomic_state *state, struct amdgpu_device *adev) {\n"
                + condition + "\n    return false;\n}\n"
                "int main(int argc, char **argv) {\n"
                "    if (argc < 4) return 2;\n"
                "    struct amdgpu_device device = { IP_VERSION(atoi(argv[1]), atoi(argv[2]), 0) };\n"
                "    struct drm_crtc_state crtc[4];\n"
                "    struct drm_atomic_state state = { atoi(argv[3]), argc - 4, crtc };\n"
                "    for (int i = 0; i < state.crtcs; i++) crtc[i].needs_modeset = atoi(argv[i + 4]);\n"
                "    puts(forced_reset(&state, &device) ? \"reset\" : \"fast\");\n}\n"
            )
            subprocess.run(["cc", "-std=gnu11", "-Wall", "-Wextra", "-Werror", str(source), "-o", str(program)],
                           check=True, capture_output=True, text=True)
            # DCN version, allow_modeset, then whether each CRTC in the commit needs a modeset.
            cases = [
                (("2", "1", "1", "0", "0"), "fast"),    # Android page flip on internal panel + HDMI
                (("2", "1", "1", "0", "1"), "reset"),   # HDMI connected or mode change
                (("2", "1", "1"), "fast"),              # no CRTC in the commit
                (("2", "1", "0", "1"), "fast"),         # later checks handle modesets without the flag
                (("3", "2", "1", "1"), "fast"),         # DCN 3.2+ never used the hack
            ]
            for arguments, expected in cases:
                with self.subTest(arguments=arguments):
                    result = subprocess.run([str(program), *arguments],
                                            check=True, capture_output=True, text=True)
                    self.assertEqual(result.stdout.strip(), expected)


class FramebufferPatchTests(unittest.TestCase):
    def test_handoff_precedes_minor_allocation_and_reports_errors(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary)
            drm = source / "drivers/gpu/drm/drm_drv.c"
            aperture = source / "drivers/video/aperture.c"
            drm.parent.mkdir(parents=True)
            aperture.parent.mkdir(parents=True)
            drm.write_text(
                "\tmutex_destroy(&dev->filelist_mutex);\n}\n\n"
                "static int drm_dev_init(struct drm_device *dev,\n"
                "\t\t\tconst struct drm_driver *driver,\n"
                "\t\t\tstruct device *parent)\n{\n"
                "\tret = drmm_add_action_or_reset(dev, drm_dev_init_release, NULL);\n"
                "\tif (ret)\n\t\treturn ret;\n\n"
                "\tinode = drm_fs_inode_new();\n\tif (IS_ERR(inode)) {\n"
                "\t\tret = PTR_ERR(inode);\n\t}\n"
                "\tret = drm_minor_alloc(dev, DRM_MINOR_PRIMARY);\n}\n"
            )
            aperture.write_text(
                "\treturn ret;\n\n}\nEXPORT_SYMBOL(aperture_remove_conflicting_pci_devices);\n"
            )
            subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1",
                 "-i", str(ROOT / "hardware/drivers/drm-handoff/drm-firmware-handoff.patch")],
                cwd=source, check=True, capture_output=True, text=True,
            )
            drm_text = drm.read_text()
            handoff = "ret = gbos_builder_remove_firmware_fb(parent, driver->name);"
            self.assertLess(drm_text.index("drmm_add_action_or_reset"), drm_text.index(handoff))
            self.assertLess(drm_text.index(handoff), drm_text.index("drm_minor_alloc"))
            self.assertIn('dev_err(parent, "Failed to remove firmware framebuffer: %d\\n", ret);',
                          drm_text)
            self.assertIn("goto err;", drm_text)
            aperture_text = aperture.read_text()
            self.assertIn("if (!dev_is_pci(dev))\n\t\treturn 0;", aperture_text)
            self.assertIn("return aperture_remove_conflicting_pci_devices", aperture_text)


if __name__ == "__main__":
    unittest.main()
