"""Check this recipe using local fixtures, never real hardware."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))


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
