"""Exercise Mesa publication without compiling or downloading its dependencies."""

import hashlib
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
    def test_iris_uses_pinned_native_shader_tools_not_android_llvm(self):
        native = (ROOT / "scripts/mesa-clc.sh").read_text()
        self.assertIn("-Dgallium-drivers= -Dvulkan-drivers=", native)
        self.assertIn("-Dmesa-clc=enabled", native)
        self.assertIn("src/compiler/clc/mesa_clc src/compiler/spirv/vtn_bindgen2", native)
        script = (ROOT / "scripts/mesa.sh").read_text()
        self.assertIn("-Dmesa-clc=system", script)
        self.assertIn('"$shader_tools/manifest"', script)
        self.assertIn("-Dllvm=disabled -Damd-use-llvm=false", script)

    def test_render_build_exposes_native_vulkan_without_changing_va_configuration(self):
        script = (ROOT / "scripts/mesa.sh").read_text()
        render = script.split('setup "$build/mesa"', 1)[1].split('setup "$va_build"', 1)[0]
        va = script.split('setup "$va_build"', 1)[1]
        self.assertIn("-Dandroid-strict=false", render)
        self.assertNotIn("-Dandroid-strict=false", va)
        self.assertEqual(script.count("-Dandroid-strict=false"), 1)

    def test_stripping_unchanged_libraries_preserves_published_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("bin", "mesa", "drm", "expat", "ndk", "out", "libva/va", "shader-tools/bin",
                         "ndk/toolchains/llvm/prebuilt/linux-x86_64/bin"):
                (root / name).mkdir(parents=True, exist_ok=True)
            (root / "libva/va/va.h").write_text("/* fixture header */\n")
            for name in ("mesa_clc", "vtn_bindgen2"):
                tool = root / "shader-tools/bin" / name
                tool.write_text("#!/bin/sh\nexit 0\n")
                tool.chmod(0o755)
            (root / "shader-tools/manifest").write_text("fixture shader tool hash\n")
            readelf = root / "ndk/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-readelf"
            readelf.write_text(
                "#!/bin/sh\n"
                "printf '1: 00000000 1 FUNC GLOBAL DEFAULT 1 __vaDriverInit_1_22\\n'\n"
            )
            readelf.chmod(0o755)
            meson = root / "bin/meson"
            meson.write_text("""#!/bin/sh
set -eu
case "$1" in
setup)
    printf '%s\\n' "$@" >> "$TRACE"
    mkdir -p "$2/va"
    printf '#define VA_VERSION 1.22.0\\n' > "$2/va/va_version.h"
    ;;
install)
    mkdir -p "$DESTDIR/lib64/pkgconfig" "$DESTDIR/lib64/gbm"
    printf 'prefix=/\\n' > "$DESTDIR/lib64/pkgconfig/test.pc"
    for file in libEGL_mesa.so libGLESv1_CM_mesa.so libGLESv2_mesa.so \\
                libgallium_dri.so libvulkan_radeon.so libvulkan_intel_hasvk.so \\
                libgbm_mesa.so gbm/dri_gbm.so \\
                radeonsi_drv_video.so libdrm_amdgpu.so; do
        printf 'unchanged stripped bytes\\n' > "$DESTDIR/lib64/$file"
    done
    ;;
esac
""")
            cmake = root / "bin/cmake"
            cmake.write_text("#!/bin/sh\nexit 0\n")
            meson.chmod(0o755)
            cmake.chmod(0o755)
            trace = root / "meson.log"
            environment = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}",
                               TRACE=str(trace))
            invocation = ["bash", str(ROOT / "scripts/mesa.sh")]
            invocation.extend(str(root / name) for name in
                              ("mesa", "drm", "expat", "ndk", "out", "libva", "shader-tools"))
            subprocess.run(invocation, env=environment, check=True, capture_output=True)
            cross = next((root / "out").glob("build-*/va-cross.ini"))
            dependency_key = hashlib.sha256(cross.read_bytes()).hexdigest()[:16]
            self.assertIn(f"\n{cross.parent}/va-{dependency_key}\n", trace.read_text())
            self.assertIn(
                f"PKG_CONFIG_LIBDIR={cross.parent}/va-sysroot/lib64/pkgconfig:"
                f"{cross.parent}/sysroot/lib64/pkgconfig",
                cross.read_text())
            published = list((root / "out/install").rglob("*.so*")) + [root / "out/manifest"]
            self.assertEqual(len(published), 11)
            for path in published:
                os.utime(path, ns=(1_000_000_000, 1_000_000_000))
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published}
            subprocess.run(invocation, env=environment, check=True, capture_output=True)
            self.assertEqual(before, {
                path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published})
            readelf.write_text("#!/bin/sh\nprintf 'no VA entry point\\n'\n")
            result = subprocess.run(invocation, env=environment, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not export Google's VA-API 1.22 entry point", result.stderr)
            self.assertEqual(before, {
                path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published})
