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


if __name__ == "__main__":
    unittest.main()
