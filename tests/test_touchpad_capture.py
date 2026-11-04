"""Check bounded Elantech capture with fake sysfs and commands, never real input devices."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
from hardware_recipes import expand
SCRIPT = REPO / "android/system_ext/touchpad-capture.sh"


class TouchpadCaptureTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.logs = self.work / "logs"
        (self.logs / "current").mkdir(parents=True)
        self.sys = self.work / "sys"
        (self.sys / "class/input").mkdir(parents=True)
        self.dev = self.work / "dev"
        (self.dev / "input").mkdir(parents=True)
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.invocations = self.work / "invocations"
        self.tool("getevent",
                  'printf "%s\\n" "$@" >> "$INVOCATIONS"\n'
                  'if [ "$1" = -p ]; then\n'
                  '    test "$#" -eq 2\n'
                  '    for axis in 0030 0035 0036 003a; do\n'
                  '        if [ "$axis" = "${OMIT_AXIS:-none}" ]; then continue; fi\n'
                  '        printf "    %s : value 0, min 0, max 3000, fuzz 0, flat 0, resolution 31\\n" "$axis"\n'
                  '    done\n'
                  '    exit "${AXIS_STATUS:-0}"\n'
                  'fi\n'
                  'test "$#" -eq 4\n'
                  'test "$1" = -t && test "$2" = -c && test "$3" = 32768\n'
                  'printf "[   60.000001] 0003 0035 00000080\\n"\n'
                  'printf "[   60.000002] 0000 0000 00000000\\n"\n'
                  'exit "${GETEVENT_STATUS:-0}"\n')
        self.tool("timeout",
                  'test "$1" = -k && test "$2" = 2\n'
                  'duration=$3\n'
                  'test "$duration" = 180 || test "$duration" = 5\n'
                  'shift 3\n'
                  '"$@"\n'
                  'if [ "$duration" = 5 ]; then exit "${AXIS_TIMEOUT_STATUS:-0}"; fi\n'
                  'exit "${TIMEOUT_STATUS:-0}"\n')
        self.tool("sync", "exit 0\n")

    def tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)

    def device(self, number, name="ETPS/2 Elantech Touchpad"):
        device = self.sys / f"class/input/event{number}/device"
        (device / "capabilities").mkdir(parents=True)
        for field, value in {
            "name": name, "phys": "isa0060/serio1/input0", "properties": "5",
            "capabilities/ev": "b", "capabilities/key": "e520 10000 0 0 0 0",
            "capabilities/abs": "661800011000003",
        }.items():
            (device / field).write_text(value + "\n")
        node = self.dev / f"input/event{number}"
        node.touch()
        return node

    def capture(self, **extra_env):
        # Emulate only the character-node predicate; commands receive regular fixture files.
        wrapper = ('test() { if [ "$1" = -c ]; then command test -f "$2"; '
                   'else command test "$@"; fi; }; script=$1; shift; . "$script"')
        return subprocess.run(
            ["sh", "-c", wrapper, "capture", str(SCRIPT),
             str(self.logs), str(self.sys), str(self.dev)],
            env=dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                     INVOCATIONS=str(self.invocations), **extra_env),
            capture_output=True, text=True)

    def test_selects_only_elantech_and_records_timestamped_events(self):
        self.device(1, "AT Translated Set 2 keyboard")
        self.device(2, "USB Optical Mouse")
        selected = self.device(9)
        result = self.capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.invocations.read_text().splitlines(),
                         ["-p", str(selected), "-t", "-c", "32768", str(selected)])
        output = self.logs / "current/touchpad.log"
        text = output.read_text()
        self.assertIn("limit_seconds=180\nlimit_events=32768\n", text)
        self.assertIn("status=capturing\n", text)
        self.assertIn("axis_info_begin\n", text)
        self.assertIn("0035 : value 0, min 0, max 3000, fuzz 0, flat 0, resolution 31\n", text)
        self.assertIn("axis_info_end\n", text)
        self.assertIn("start_unix_seconds=", text)
        self.assertIn("[   60.000002] 0000 0000 00000000\n", text)
        self.assertTrue(text.endswith("status=event-limit\n"))
        self.assertEqual(output.stat().st_mode & 0o777, 0o600)

    def test_no_touchpad_does_not_open_keyboard(self):
        self.device(0, "AT Translated Set 2 keyboard")
        result = self.capture()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.invocations.exists())
        self.assertIn("status=not-present\n",
                      (self.logs / "current/touchpad.log").read_text())

    def test_ambiguous_touchpad_is_rejected(self):
        self.device(2)
        self.device(9)
        result = self.capture()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Multiple Elantech touchpads", result.stderr)
        self.assertFalse(self.invocations.exists())

    def test_time_limit_retains_events_and_is_explicit(self):
        self.device(9)
        result = self.capture(TIMEOUT_STATUS="124")
        self.assertEqual(result.returncode, 0, result.stderr)
        text = (self.logs / "current/touchpad.log").read_text()
        self.assertIn("[   60.000001]", text)
        self.assertTrue(text.endswith("status=time-limit\n"))

    def test_capture_failure_is_reported_with_partial_events(self):
        self.device(9)
        result = self.capture(GETEVENT_STATUS="1")
        self.assertNotEqual(result.returncode, 0)
        text = (self.logs / "current/touchpad.log").read_text()
        self.assertIn("status=failed exit=1\n", text)
        self.assertIn("dali touchpad capture failed", text)
        self.assertNotIn("status=event-limit", text)

    def test_axis_query_failure_or_timeout_stops_before_capture(self):
        self.device(9)
        for extra_env in ({"AXIS_STATUS": "1"}, {"AXIS_TIMEOUT_STATUS": "124"}):
            with self.subTest(extra_env=extra_env):
                result = self.capture(**extra_env)
                self.assertNotEqual(result.returncode, 0)
                text = (self.logs / "current/touchpad.log").read_text()
                self.assertIn("Axis query failed", text)
                self.assertNotIn("status=capturing", text)
                self.assertNotIn("-t", self.invocations.read_text().splitlines())
                (self.logs / "current/touchpad.log").unlink()
                self.invocations.unlink()

    def test_successful_query_with_missing_axis_metadata_is_rejected(self):
        self.device(9)
        for axis in ("0030", "0035", "0036", "003a"):
            with self.subTest(axis=axis):
                result = self.capture(OMIT_AXIS=axis)
                self.assertNotEqual(result.returncode, 0)
                text = (self.logs / "current/touchpad.log").read_text()
                self.assertIn(f"Axis query omitted range/resolution for {axis}", text)
                self.assertNotIn("status=capturing", text)
                (self.logs / "current/touchpad.log").unlink()
                self.invocations.unlink()

    def test_existing_capture_is_never_overwritten(self):
        output = self.logs / "current/touchpad.log"
        output.write_text("keep partial capture\n")
        result = self.capture()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_text(), "keep partial capture\n")
        self.assertFalse(self.invocations.exists())

    def test_output_symlink_is_rejected(self):
        target = self.work / "private"
        target.write_text("keep\n")
        (self.logs / "current/touchpad.log").symlink_to(target)
        self.assertNotEqual(self.capture().returncode, 0)
        self.assertEqual(target.read_text(), "keep\n")

    def test_input_node_symlink_is_rejected(self):
        node = self.device(9)
        node.unlink()
        node.symlink_to(self.work / "missing")
        self.assertNotEqual(self.capture().returncode, 0)
        self.assertFalse(self.invocations.exists())

    def test_missing_device_node_is_rejected(self):
        self.device(9).unlink()
        self.assertNotEqual(self.capture().returncode, 0)
        self.assertFalse(self.invocations.exists())

    def test_init_and_policy_keep_capture_separate_and_read_only(self):
        init = (REPO / "android/system_ext/bootlog.rc").read_text()
        service = init.split("service dali_touchpad_capture ", 1)[1].split("\n\n", 1)[0]
        self.assertIn("group log input\n", service)
        self.assertIn("seclabel u:r:dali_touchpad_diag:s0\n", service)
        self.assertIn("oneshot\n", service)
        policy = (REPO / "android/system/bootlog-policy.patch").read_text()
        self.assertIn("input_device (dir (getattr search))", policy)
        self.assertIn("input_device (chr_file (getattr open read ioctl))", policy)
        self.assertIn("(ioctl chr_file (0x4501 0x4502 0x4506 0x4507 0x4508 0x4509 "
                      "(range 0x4518 0x451b) (range 0x4521 0x453f) "
                      "(range 0x4540 0x457f)))", policy)
        for permission in ("write", "append", "setattr"):
            self.assertNotRegex(policy, rf"input_device \(chr_file \([^)]*\b{permission}\b")
        self.assertNotIn("(permissive", policy)
        self.assertNotIn("0x4590", policy)
        self.assertNotIn("0x45a0", policy)
        script = SCRIPT.read_text()
        self.assertNotIn("getevent -t -c 32768\n", script)
        self.assertIn('getevent -t -c 32768 "$node"', script)
        self.assertIn('timeout -k 2 5 getevent -p "$node"', script)


class ElantechCalibrationTests(unittest.TestCase):
    def test_device_named_override_changes_only_single_contact_palm_width(self):
        device_name = "ETPS/2 Elantech Touchpad"
        filename = "".join(character if character.isascii() and (
            character.isalnum() or character in "-_") else "_"
                           for character in device_name) + ".idc"
        self.assertEqual(filename, "ETPS_2_Elantech_Touchpad.idc")
        calibration = REPO / "android/vendor" / filename
        settings = [line.strip() for line in calibration.read_text().splitlines()
                    if line.strip() and not line.startswith("#")]
        self.assertEqual(settings, ["gestureProp.Palm_Width = 50.0"])
        # Both captured single-finger maxima fit without disabling the 75 mm multi-palm limit.
        threshold = float(settings[0].split("=")[1])
        self.assertGreater(threshold, 1540 / 32)
        self.assertGreater(threshold, 1078 / 32)
        self.assertLess(threshold, 75.0)
        entries = [line.split() for line in expand(REPO / "android/vendor/install.list").splitlines()
                   if line.strip() and not line.startswith("#")]
        self.assertIn([f"usr/idc/{filename}", "0644", "0:0",
                       "vendor_configs_file", f"./{filename}"], entries)


if __name__ == "__main__":
    unittest.main()
