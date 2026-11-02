"""Boot-log retention and readiness, using only temporary files and fake Android tools."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
PREPARE = REPO / "android/system_ext/bootlog-prepare.sh"
BOOT_ONE = "11111111-1111-1111-1111-111111111111"
BOOT_TWO = "22222222-2222-2222-2222-222222222222"
BOOT_THREE = "33333333-3333-3333-3333-333333333333"


class BootlogTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.logs = self.work / "logs"
        self.logs.mkdir()
        self.boot_id = self.work / "boot-id"
        self.ready = self.work / "ready"
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.tool("getprop", 'test "${FAIL_GETPROP:-0}" = 0 || exit 1\n'
                  'case "$1" in\n'
                  'ro.build.fingerprint) echo test/fingerprint ;;\n'
                  'ro.boot.dali.graphics) echo amd ;;\n'
                  'ro.boot.bootreason) echo cold ;;\n'
                  '*) exit 1 ;;\n'
                  'esac\n')
        self.tool("setprop", 'printf "%s %s\\n" "$1" "$2" > "$READY_FILE"\n')
        self.tool("sync", 'exit 0\n')

    def tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)

    def prepare(self, boot_id=BOOT_ONE, **extra_env):
        self.boot_id.write_text(boot_id + "\n")
        self.ready.unlink(missing_ok=True)
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                   READY_FILE=str(self.ready), **extra_env)
        return subprocess.run(["sh", str(PREPARE), str(self.logs), str(self.boot_id)],
                              env=env, capture_output=True, text=True)

    def assert_ready(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.ready.read_text(), "sys.dali.bootlog.ready 1\n")

    def test_first_boot_records_identity_before_readiness(self):
        self.assert_ready(self.prepare())
        current = self.logs / "current"
        self.assertEqual((current / "boot-id").read_text(), BOOT_ONE + "\n")
        self.assertIn("fingerprint=test/fingerprint\n", (current / "boot.txt").read_text())
        self.assertIn("graphics_boot_property=amd\n", (current / "boot.txt").read_text())
        self.assertEqual(current.stat().st_mode & 0o777, 0o700)
        self.assertFalse((self.logs / "previous").exists())

    def test_same_boot_restart_preserves_streams(self):
        self.assert_ready(self.prepare())
        log = self.logs / "current/kernel.log"
        log.write_text("first failure\n")
        stamp = log.stat().st_mtime_ns
        self.assert_ready(self.prepare())
        self.assertEqual(log.read_text(), "first failure\n")
        self.assertEqual(log.stat().st_mtime_ns, stamp)
        self.assertFalse((self.logs / "previous").exists())

    def test_two_boots_retained_and_all_archive_names_removed(self):
        self.assert_ready(self.prepare())
        current = self.logs / "current"
        for stream in ("kernel", "android"):
            for suffix in ("", ".1", ".2", ".3", ".4", ".5", ".6", ".7"):
                (current / f"{stream}.log{suffix}").write_text("old\n")
        self.assert_ready(self.prepare(BOOT_TWO))
        self.assertEqual((self.logs / "previous/boot-id").read_text(), BOOT_ONE + "\n")
        (current / "android.log").write_text("new\n")
        self.assert_ready(self.prepare(BOOT_THREE))
        previous = self.logs / "previous"
        self.assertEqual((previous / "boot-id").read_text(), BOOT_TWO + "\n")
        self.assertEqual((previous / "android.log").read_text(), "new\n")
        self.assertEqual(set(path.name for path in previous.iterdir()),
                         {"boot-id", "boot.txt", "android.log"})
        self.assertEqual(set(path.name for path in self.logs.iterdir()), {"current", "previous"})

    def test_interrupted_directory_switch_keeps_previous_boot(self):
        self.assert_ready(self.prepare())
        (self.logs / "current/kernel.log").write_text("keep\n")
        (self.logs / "current").rename(self.logs / "previous")
        self.assert_ready(self.prepare(BOOT_TWO))
        self.assertEqual((self.logs / "previous/kernel.log").read_text(), "keep\n")

    def test_interrupted_creation_keeps_previous_boot(self):
        self.assert_ready(self.prepare())
        (self.logs / "current").rename(self.logs / "previous")
        (self.logs / "current").mkdir()
        self.assert_ready(self.prepare(BOOT_TWO))
        self.assertEqual((self.logs / "previous/boot-id").read_text(), BOOT_ONE + "\n")

    def test_unexpected_previous_file_stops_without_readiness(self):
        self.assert_ready(self.prepare())
        self.assert_ready(self.prepare(BOOT_TWO))
        unknown = self.logs / "previous/not-a-log"
        unknown.write_text("do not delete\n")
        result = self.prepare(BOOT_THREE)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dali_bootlog_prepare failed", result.stderr)
        self.assertFalse(self.ready.exists())
        self.assertEqual(unknown.read_text(), "do not delete\n")
        self.assertEqual((self.logs / "current/boot-id").read_text(), BOOT_TWO + "\n")

    def test_symlinked_directory_or_marker_is_rejected(self):
        outside = self.work / "outside"
        outside.mkdir()
        link = self.logs / "current"
        link.symlink_to(outside, target_is_directory=True)
        self.assertNotEqual(self.prepare().returncode, 0)
        self.assertFalse(self.ready.exists())
        link.unlink()
        link.mkdir()
        marker = link / "boot-id"
        marker.symlink_to(outside / "missing")
        self.assertNotEqual(self.prepare().returncode, 0)
        self.assertFalse(self.ready.exists())
        self.assertFalse((outside / "missing").exists())

    def test_identity_command_failure_is_not_hidden(self):
        result = self.prepare(FAIL_GETPROP="1")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("dali_bootlog_prepare failed", result.stderr)
        self.assertFalse(self.ready.exists())

    def test_invalid_boot_id_is_rejected(self):
        for boot_id in ("", "bad", "../" * 12):
            with self.subTest(boot_id=boot_id):
                self.assertNotEqual(self.prepare(boot_id).returncode, 0)
                self.assertFalse(self.ready.exists())
                self.assertFalse((self.logs / "current").exists())

    def test_collectors_are_native_bounded_and_readiness_gated(self):
        text = (REPO / "android/system_ext/bootlog.rc").read_text()
        self.assertIn("setprop ro.logd.kernel true", text)
        self.assertIn("on property:sys.dali.bootlog.ready=1", text)
        commands = [line.split() for line in text.splitlines()
                    if line.startswith("service dali_") and "/system/bin/logcat" in line]
        self.assertEqual(len(commands), 2)
        for command in commands:
            self.assertEqual(command[2], "/system/bin/logcat")
            self.assertEqual(command[command.index("-v") + 1], "long")
            self.assertEqual(int(command[command.index("-r") + 1]), 256)
            self.assertEqual(int(command[command.index("-n") + 1]), 7)
            self.assertTrue(command[-1].startswith("/metadata/dali-bootlog/current/"))
        self.assertEqual(commands[0][commands[0].index("-b") + 1], "kernel")
        self.assertEqual(commands[1][commands[1].index("-b") + 1], "main,system,crash,events")

    def test_policy_allows_rotation_only_in_our_directory_type(self):
        policy = (REPO / "android/system/bootlog-policy.patch").read_text()
        permissions = [line for line in policy.splitlines()
                       if line.startswith("+(allow dali_bootlog dali_bootlog_file (dir")]
        self.assertEqual(len(permissions), 1)
        self.assertIn("rename", permissions[0])
        self.assertIn("rmdir", permissions[0])
        self.assertNotIn("(permissive", policy)
        self.assertNotIn("(capability", policy)
        self.assertNotIn("blk_file", policy)


if __name__ == "__main__":
    unittest.main()
