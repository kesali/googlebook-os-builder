"""The declared Android changes and the scripts that apply and check them."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
OVERLAY = REPO / "scripts/android-overlay.sh"
VENDOR_LIBS = REPO / "scripts/check-vendor-libs.sh"


def entries(path):
    return [line.split() for line in path.read_text().splitlines()
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


class ChangeDataTests(unittest.TestCase):
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
