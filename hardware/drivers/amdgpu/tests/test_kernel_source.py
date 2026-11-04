"""Check this recipe using local fixtures, never real hardware."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))
from recipe_support import patched_text


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


if __name__ == "__main__":
    unittest.main()
