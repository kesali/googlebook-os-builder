"""Check kernel source preparation using local fake repositories, never the real source tree."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


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
        self.emulator_patch.write_text(self.patch("original", "emulator"))
        self.handoff_patch.write_text(self.patch("emulator", "handoff"))
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
             self.revision, str(self.emulator_patch), str(self.handoff_patch),
             str(cache if cache is not None else self.cache), str(self.destination)],
            capture_output=True, text=True, env=env,
        )

    def test_patches_in_order_without_copying_existing_source_edits(self):
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "state.txt").read_text(), "handoff\n")
        self.assertTrue((self.destination / ".ready").exists())
        self.assertEqual((self.cache / "state.txt").read_text(), "local source edit\n")

    def test_source_can_be_prepared_without_an_existing_cache(self):
        result = self.prepare(cache=self.work / "missing-cache")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.destination / "state.txt").read_text(), "handoff\n")

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
                 "-i", str(ROOT / "kernel/drm-firmware-handoff.patch")],
                cwd=source, check=True, capture_output=True, text=True,
            )
            drm_text = drm.read_text()
            handoff = "ret = dali_remove_firmware_fb(parent, driver->name);"
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
