"""Exercise Mesa publication without compiling or downloading its dependencies."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MesaPublicationTests(unittest.TestCase):
    def test_stripping_unchanged_libraries_preserves_published_timestamps(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("bin", "mesa", "drm", "expat", "ndk", "out"):
                (root / name).mkdir()
            meson = root / "bin/meson"
            meson.write_text("""#!/bin/sh
set -eu
case "$1" in
setup) mkdir -p "$2" ;;
install)
    mkdir -p "$DESTDIR/lib64/pkgconfig" "$DESTDIR/lib64/gbm"
    printf 'prefix=/\\n' > "$DESTDIR/lib64/pkgconfig/test.pc"
    for file in libEGL_mesa.so libGLESv1_CM_mesa.so libGLESv2_mesa.so \\
                libgallium_dri.so libvulkan_radeon.so libgbm_mesa.so gbm/dri_gbm.so; do
        printf 'unchanged stripped bytes\\n' > "$DESTDIR/lib64/$file"
    done
    ;;
esac
""")
            cmake = root / "bin/cmake"
            cmake.write_text("#!/bin/sh\nexit 0\n")
            meson.chmod(0o755)
            cmake.chmod(0o755)
            environment = dict(os.environ, PATH=f"{root / 'bin'}:{os.environ['PATH']}")
            invocation = ["bash", str(ROOT / "scripts/mesa.sh")]
            invocation.extend(str(root / name) for name in ("mesa", "drm", "expat", "ndk", "out"))
            subprocess.run(invocation, env=environment, check=True, capture_output=True)
            published = list((root / "out/install").rglob("*.so")) + [root / "out/manifest"]
            self.assertEqual(len(published), 8)
            for path in published:
                os.utime(path, ns=(1_000_000_000, 1_000_000_000))
            before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published}
            subprocess.run(invocation, env=environment, check=True, capture_output=True)
            self.assertEqual(before, {
                path: (path.read_bytes(), path.stat().st_mtime_ns) for path in published})
