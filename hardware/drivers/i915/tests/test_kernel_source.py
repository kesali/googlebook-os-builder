"""Check this recipe using local fixtures, never real hardware."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "tests"))
from recipe_support import inspect_kernel_recipes, recipe_patch, patched_text


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


if __name__ == "__main__":
    unittest.main()
