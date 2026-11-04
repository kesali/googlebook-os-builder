"""Check kernel source preparation using local fake repositories, never the real source tree."""

import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from recipe_support import inspect_kernel_recipes


ROOT = Path(__file__).resolve().parents[1]


class KernelRecipeTests(unittest.TestCase):
    def test_selected_patches_keep_order_without_fast_flips_override(self):
        result = inspect_kernel_recipes()
        self.assertEqual(result.returncode, 0, result.stderr)
        paths, digest, source = result.stdout.splitlines()
        self.assertEqual(paths.split(), [
            "hardware/drivers/drm-handoff/drm-firmware-handoff.patch",
            "hardware/drivers/amdgpu/msi-backlight.patch",
            "hardware/drivers/renoir-acp/renoir-capture-buffers.patch",
            "hardware/drivers/i915/i915-gen4-primary-alpha.patch",
        ])
        patch_bytes = b"".join((ROOT / path).read_bytes() for path in paths.split())
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


if __name__ == "__main__":
    unittest.main()
