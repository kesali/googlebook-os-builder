"""Exercise Mesa publication without compiling or downloading its dependencies."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))
from hardware_recipes import expand


class MesaPublicationTests(unittest.TestCase):
    def test_build_keeps_zink_and_radv_without_camera_va_driver(self):
        script = (ROOT / "scripts/mesa.sh").read_text()
        self.assertIn("-Dgallium-drivers=softpipe,zink,iris -Dvulkan-drivers=amd,intel_hasvk", script)
        self.assertIn("-Dgallium-va=disabled", script)
        self.assertNotIn("-Dgallium-drivers=radeonsi", script)
        self.assertNotIn("libva", script)
        self.assertNotIn("LIBVA_", (ROOT / "Makefile").read_text())
        self.assertNotIn("LIBVA_", (ROOT / "sources.mk").read_text())
        self.assertIn("-Dandroid-strict=false", script)

        installs = [line.split() for line in
                    expand(ROOT / "hardware/drivers/amdgpu/vendor.install").splitlines()
                    if line and not line.startswith("#")]
        installed_names = {Path(line[0]).name for line in installs}
        self.assertNotIn("radeonsi_drv_video.so", installed_names)
        self.assertNotIn("libdrm_amdgpu.so", installed_names)
        self.assertEqual(list(ROOT.glob("hardware/**/camera-va-driver.patch")), [])

    def test_stripping_unchanged_libraries_preserves_published_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("bin", "mesa", "drm", "expat", "ndk", "out", "shader-tools/bin",
                         "ndk/toolchains/llvm/prebuilt/linux-x86_64/bin"):
                (root / name).mkdir(parents=True, exist_ok=True)
            for name in ("mesa_clc", "vtn_bindgen2"):
                tool = root / "shader-tools/bin" / name
                tool.write_text("#!/bin/sh\nexit 0\n")
                tool.chmod(0o755)
            (root / "shader-tools/manifest").write_text("fixture shader tool hash\n")

            meson = root / "bin/meson"
            meson.write_text("""#!/bin/sh
set -eu
case "$1" in
setup)
    printf '%s\\n' "$@" >> "$TRACE"
    ;;
install)
    mkdir -p "$DESTDIR/lib64/pkgconfig" "$DESTDIR/lib64/gbm"
    printf 'prefix=/\\n' > "$DESTDIR/lib64/pkgconfig/test.pc"
    for file in libEGL_mesa.so libGLESv1_CM_mesa.so libGLESv2_mesa.so \\
                libgallium_dri.so libvulkan_radeon.so libvulkan_intel_hasvk.so \\
                libgbm_mesa.so gbm/dri_gbm.so; do
        printf 'unchanged stripped bytes\\n' > "$DESTDIR/lib64/$file"
    done
    ;;
esac
""")
            cmake = root / "bin/cmake"
            cmake.write_text("""#!/bin/sh
set -eu
if [ "$1" = --install ]; then
    mkdir -p "$DESTDIR/lib64/pkgconfig"
    printf 'prefix=/\\n' > "$DESTDIR/lib64/pkgconfig/expat.pc"
fi
""")
            meson.chmod(0o755)
            cmake.chmod(0o755)
            legacy_outputs = root / "out/install/lib64"
            legacy_outputs.mkdir(parents=True)
            for name in ("radeonsi_drv_video.so", "libdrm_amdgpu.so"):
                (legacy_outputs / name).write_bytes(b"retired camera output")

            trace = root / "meson.log"
            environment = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}",
                               TRACE=str(trace))
            invocation = ["bash", str(ROOT / "scripts/mesa.sh")]
            invocation.extend(str(root / name) for name in
                              ("mesa", "drm", "expat", "ndk", "out", "shader-tools"))
            subprocess.run(invocation, env=environment, check=True, capture_output=True)

            published = list((root / "out/install").rglob("*.so*")) + [root / "out/manifest"]
            self.assertEqual(len(published), 9)
            self.assertFalse(any((legacy_outputs / name).exists()
                                 for name in ("radeonsi_drv_video.so", "libdrm_amdgpu.so")))
            self.assertEqual(trace.read_text().count("setup\n"), 2)

            for path in published:
                os.utime(path, ns=(1_000_000_000, 1_000_000_000))
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published}
            subprocess.run(invocation, env=environment, check=True, capture_output=True)
            self.assertEqual(before, {
                path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published})


if __name__ == "__main__":
    unittest.main()
