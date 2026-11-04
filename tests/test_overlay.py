"""The declared Android changes and the scripts that apply and check them."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import zipfile
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand
OVERLAY = REPO / "scripts/android-overlay.sh"
VENDOR_LIBS = REPO / "scripts/check-vendor-libs.sh"
REPLACEMENTS = REPO / "scripts/check-replacements.sh"


def entries(path):
    return [line.split() for line in expand(path).splitlines()
            if line.strip() and not line.startswith("#")]


class OverlayTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.root = self.work / "root"
        self.changes = self.work / "changes"
        self.inputs = self.work / "inputs"
        for path in (self.root / "etc", self.root / "bin", self.root / "lib64", self.changes, self.inputs):
            path.mkdir(parents=True)
        (self.root / "etc/build.prop").write_text("a=1\nb=2\n")
        (self.root / "bin/old").write_text("old\n")

    def write(self, name, text):
        (self.changes / name).write_text(text)

    def run_overlay(self, before="", after=""):
        """Run the overlay under fakeroot, with optional shell setup and inspection around it."""
        script = f'{before}\nbash "{OVERLAY}" changes root input=inputs\n{after}'
        return subprocess.run(["fakeroot", "bash", "-euc", script], cwd=self.work,
                              capture_output=True, text=True)

    def test_removes_installs_and_patches_in_place(self):
        (self.inputs / "tool").write_text("tool\n")
        self.write("rc", "service\n")
        self.write("remove.list", "# comment\nbin/old\n")
        self.write("install.list",
                   "# path mode owner type source\n"
                   "bin/tool      0755 0:2000 tool_exec   input/tool\n"
                   "etc/init/     0755 0:0    vendor_file -\n"
                   "etc/init/x.rc 0644 0:0    -           ./rc\n")
        self.write("props.patch",
                   "Why this change is needed.\n\n"
                   "--- a/etc/build.prop\n+++ b/etc/build.prop\n"
                   "@@ -1,2 +1,2 @@\n-a=1\n+a=2\n b=2\n")
        result = self.run_overlay(
            before="chown 0:2000 root/etc/build.prop; chmod 640 root/etc/build.prop\n"
                   "setfattr -n security.selinux -v u:object_r:prop_file:s0 root/etc/build.prop",
            after="cd root; stat -c '%n %a %u:%g' etc/build.prop bin/tool etc/init etc/init/x.rc\n"
                  "getfattr -h --absolute-names -d -m security.selinux etc/build.prop bin/tool etc/init etc/init/x.rc")
        self.assertEqual(result.returncode, 0, result.stderr)
        for line in ("changes: remove bin/old", "changes: install etc/init/x.rc", "changes: patch props.patch"):
            self.assertIn(line, result.stdout)
        for line in ("etc/build.prop 640 0:2000", "bin/tool 755 0:2000",
                     "etc/init 755 0:0", "etc/init/x.rc 644 0:0",
                     'security.selinux="u:object_r:prop_file:s0"',
                     'security.selinux="u:object_r:tool_exec:s0"',
                     'security.selinux="u:object_r:vendor_file:s0"'):
            self.assertIn(line, result.stdout)
        self.assertEqual((self.root / "etc/build.prop").read_text(), "a=2\nb=2\n")
        self.assertEqual((self.root / "bin/tool").read_text(), "tool\n")
        self.assertFalse((self.root / "bin/old").exists())

    def test_refuses_undeclared_or_unsafe_changes(self):
        patch = "--- a/etc/build.prop\n+++ b/etc/build.prop\n@@ -1 +1 @@\n-a=9\n+a=2\n"
        cases = {
            "cannot remove missing bin/none": {"remove.list": "bin/none\n"},
            "not a path inside the partition: ../outside": {"remove.list": "../outside\n"},
            "bin/old already exists": {"install.list": "bin/old 0644 0:0 - input/tool\n"},
            "missing source input/none": {"install.list": "bin/new 0644 0:0 - input/none\n"},
            "unknown input other/": {"install.list": "bin/new 0644 0:0 - other/tool\n"},
            "install.list needs 5 columns": {"install.list": "bin/new 0644 0:0 ./x\n"},
            "bad.patch does not apply": {"bad.patch": patch},
        }
        (self.inputs / "tool").write_text("tool\n")
        for message, files in cases.items():
            with self.subTest(message):
                shutil.rmtree(self.changes)
                self.changes.mkdir()
                for name, text in files.items():
                    self.write(name, text)
                result = self.run_overlay()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(message, result.stderr)
        self.assertEqual((self.root / "etc/build.prop").read_text(), "a=1\nb=2\n")

    def test_vendor_programs_must_link_to_lib64_or_llndk(self):
        program = Path(shutil.which("true")).resolve()
        shutil.copy(program, self.root / "bin/program")
        needed = subprocess.run(["readelf", "-d", str(program)], capture_output=True, text=True).stdout
        library = needed.split("(NEEDED)")[1].split("[")[1].split("]")[0]
        self.write("install.list", "bin/program 0755 0:0 - input/program\n"
                                   "etc/build.prop 0644 0:0 - input/props\n")
        llndk = self.work / "llndk.txt"
        check = ["bash", str(VENDOR_LIBS), str(self.changes / "install.list"), str(self.root), str(llndk)]
        llndk.write_text("libother.so\n")
        result = subprocess.run(check, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(f"vendor/bin/program needs {library}", result.stderr)
        llndk.write_text(f"{library}\n")
        result = subprocess.run(check, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_refuses_symlinked_parent_for_each_operation(self):
        outside = self.work / "outside"
        outside.mkdir()
        (self.root / "linked").symlink_to(outside, target_is_directory=True)
        (self.inputs / "tool").write_text("tool\n")
        cases = {
            "remove.list": "linked/build.prop\n",
            "install.list": "linked/new 0644 0:0 - input/tool\n",
            "props.patch": "--- a/linked/build.prop\n+++ b/linked/build.prop\n"
                           "@@ -1 +1 @@\n-a=1\n+a=2\n",
        }
        for name, text in cases.items():
            with self.subTest(operation=name):
                (outside / "build.prop").write_text("a=1\n")
                self.write(name, text)
                result = self.run_overlay()
                (self.changes / name).unlink()
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("parent directory is missing or a symlink", result.stderr)
                self.assertEqual((outside / "build.prop").read_text(), "a=1\n")
                self.assertFalse((outside / "new").exists())

    def test_refuses_patching_a_symlink(self):
        outside = self.work / "outside.prop"
        outside.write_text("a=1\n")
        (self.root / "etc/link.prop").symlink_to(outside)
        self.write("props.patch", "--- a/etc/link.prop\n+++ b/etc/link.prop\n"
                                 "@@ -1 +1 @@\n-a=1\n+a=2\n")
        result = self.run_overlay()
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("not an existing regular file", result.stderr)
        self.assertEqual(outside.read_text(), "a=1\n")


class ReplacementTests(unittest.TestCase):
    """A file listed in both remove.list and install.list must be a drop-in for Google's."""

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.google = self.work / "google"
        self.root = self.work / "root"
        self.changes = self.work / "changes"
        for path in (self.google / "lib64", self.google / "bin", self.google / "apex",
                     self.root / "lib64", self.root / "bin", self.root / "apex", self.changes):
            path.mkdir(parents=True)

    def library(self, path, symbols):
        source = self.work / "library.c"
        source.write_text("".join(f"int {symbol}(void) {{ return 0; }}\n" for symbol in symbols))
        subprocess.run(["cc", "-shared", "-fPIC", "-o", str(path), str(source)], check=True)

    def program(self, path, library, symbol):
        """A program that imports SYMBOL from LIBRARY, as Google's programs import from theirs."""
        source = self.work / "program.c"
        source.write_text(f"int {symbol}(void);\nint main(void) {{ return {symbol}(); }}\n")
        subprocess.run(["cc", "-o", str(path), str(source), str(library)], check=True)

    def apex(self, path, manifest, payload, filesystem):
        image = self.work / f"{path.name}.payload"
        if filesystem == "erofs":
            subprocess.run(["mkfs.erofs", "--quiet", str(image), str(payload)], check=True)
        else:
            subprocess.run(["mke2fs", "-q", "-t", "ext4", "-O", "^has_journal", "-d", str(payload),
                            str(image), "1M"], check=True)
        with zipfile.ZipFile(path, "w") as apex:
            apex.writestr("apex_manifest.pb", manifest)
            apex.write(image, "apex_payload.img")

    def check(self, *replaced):
        """Replace the Google files at REPLACED paths and run the check against the root."""
        (self.changes / "remove.list").write_text("".join(f"{path}\n" for path in replaced))
        (self.changes / "install.list").write_text(
            "".join(f"{path} 0644 0:0 - input/{path}\n" for path in replaced))
        partition = self.work / "google.img"
        partition.unlink(missing_ok=True)
        subprocess.run(["mkfs.erofs", "--quiet", str(partition), str(self.google)], check=True)
        return subprocess.run(["bash", str(REPLACEMENTS), str(partition), str(self.changes), str(self.root)],
                              capture_output=True, text=True)

    def test_library_must_keep_the_exports_programs_import(self):
        self.library(self.google / "lib64/libx.so", ["used", "internal"])
        self.program(self.root / "bin/program", self.google / "lib64/libx.so", "used")
        self.library(self.root / "lib64/libx.so", ["used", "internal", "extra"])
        result = self.check("lib64/libx.so")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("lib64/libx.so is a drop-in replacement", result.stdout)

        # Our source builds may drop internal helpers that no program imports.
        self.library(self.root / "lib64/libx.so", ["used"])
        result = self.check("lib64/libx.so")
        self.assertEqual(result.returncode, 0, result.stderr)

        self.library(self.root / "lib64/libx.so", ["internal"])
        result = self.check("lib64/libx.so")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("lib64/libx.so: replacement lacks exports", result.stderr)
        self.assertIn("used", result.stderr)

        (self.root / "lib64/libx.so").write_text("not ELF\n")
        result = self.check("lib64/libx.so")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("replacement is not an ELF file", result.stderr)

    def test_apex_must_match_name_version_files_and_public_exports(self):
        google, ours = self.work / "google-payload", self.work / "our-payload"
        for payload in (google, ours):
            (payload / "lib64").mkdir(parents=True)
            (payload / "etc").mkdir()
            (payload / "etc/config.txt").write_text(payload.name)
        self.library(google / "lib64/libc.so", ["allocate", "internal"])
        self.library(google / "lib64/libprivate.so", ["helper", "newer_helper"])
        self.apex(self.google / "apex/runtime.apex", b"runtime 1", google, "erofs")
        # The partition links to the APEX's public files through symlinks, as Google's
        # system/lib64/libc.so does to the runtime APEX.
        (self.root / "lib64/libc.so").symlink_to("/apex/runtime/lib64/libc.so")

        cases = [
            ("same", b"runtime 1", ["allocate", "internal", "extra"], None, None),
            # Nothing in the partition imports "internal", but programs on every partition
            # link to the APEX's public files, so they must export everything Google's do.
            ("missing export", b"runtime 1", ["allocate"], None, "./lib64/libc.so: replacement lacks exports"),
            ("other version", b"runtime 2", ["allocate", "internal"], None, "different name or version"),
            ("extra file", b"runtime 1", ["allocate", "internal"], "etc/extra.txt", "different file list"),
        ]
        for name, manifest, symbols, extra, error in cases:
            with self.subTest(case=name):
                self.library(ours / "lib64/libc.so", symbols)
                # Private files only serve the APEX's own build, which comes as a whole.
                self.library(ours / "lib64/libprivate.so", ["helper"])
                if extra:
                    (ours / extra).write_text("extra")
                self.apex(self.root / "apex/runtime.apex", manifest, ours, "ext4")
                result = self.check("apex/runtime.apex")
                if extra:
                    (ours / extra).unlink()
                if error is None:
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertIn("apex/runtime.apex is a drop-in replacement", result.stdout)
                else:
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertIn(error, result.stderr)

        self.library(ours / "lib64/libc.so", ["allocate", "internal"])
        self.apex(self.root / "apex/runtime.apex", b"runtime 1", ours, "ext4")
        (self.root / "lib64/libc.so").unlink()
        result = self.check("apex/runtime.apex")
        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("no symlink into /apex/runtime shows which of its files are public", result.stderr)


class ChangeDataTests(unittest.TestCase):
    def test_vendor_dlkm_unblocks_msi_hda_audio(self):
        patch = (REPO / "android/vendor_dlkm/modules.patch").read_text()
        self.assertIn("-blocklist snd_hda_intel", patch)
        self.assertNotIn("+blocklist snd_hda_intel", patch)
        self.assertIn(
            "-options snd_sof_intel_hda_generic hda_model=alc-2024y-chromebook dmic_num=4",
            patch,
        )
        self.assertIn(
            "+softdep snd_hda_intel pre: snd_hda_codec_alc269 snd_hda_codec_atihdmi",
            patch,
        )

    def test_laptop_density_is_only_set_in_amd_graphics_profile(self):
        amd = (REPO / "android/system_ext/graphics-amd.rc").read_text()
        softpipe = (REPO / "android/system_ext/graphics-softpipe.rc").read_text()
        self.assertIn("setprop qemu.sf.lcd_density 160", amd)
        self.assertNotIn("qemu.sf.lcd_density", softpipe)

    def test_install_lists_have_five_columns(self):
        for path in sorted(REPO.glob("android/*/install.list")):
            for entry in entries(path):
                with self.subTest(path=path.parent.name, entry=entry[0]):
                    self.assertEqual(len(entry), 5)

    def test_every_file_in_a_change_directory_is_used(self):
        for changes in sorted(path for path in (REPO / "android").iterdir() if path.is_dir()):
            install = changes / "install.list"
            sources = {entry[4] for entry in entries(install)} if install.exists() else set()
            for path in sorted(changes.iterdir()):
                with self.subTest(path=f"{changes.name}/{path.name}"):
                    self.assertTrue(path.name in ("remove.list", "install.list")
                                    or path.suffix == ".patch" or f"./{path.name}" in sources,
                                    "not a list or patch, and not a source in install.list")

    def test_first_stage_modules_are_loaded_in_install_order(self):
        changes = REPO / "android/module_ramdisk"
        patch = (changes / "modules.patch").read_text()
        # Android reads a trailing space in modules.dep as an empty dependency.
        self.assertNotRegex(patch, r"(?m)[ \t]$")
        installed = [Path(entry[0]).name for entry in entries(changes / "install.list")]
        load = patch.split("+++ b/lib/modules/modules.load\n", 1)[1]
        added = [line[1:] for line in load.splitlines() if line.startswith("+")]
        self.assertEqual(added, installed)


if __name__ == "__main__":
    unittest.main()
