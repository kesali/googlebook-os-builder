"""Boot-log retention and readiness, using only temporary files and fake Android tools."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
PREPARE = REPO / "android/system_ext/bootlog-prepare.sh"
SNAPSHOT = REPO / "android/system_ext/hardware-snapshot.sh"
BOOT_ONE = "11111111-1111-1111-1111-111111111111"
BOOT_TWO = "22222222-2222-2222-2222-222222222222"
BOOT_THREE = "33333333-3333-3333-3333-333333333333"


class BootlogTests(unittest.TestCase):
    def test_persistent_logging_requires_explicit_boot_opt_in(self):
        text = (REPO / "android/system_ext/bootlog.rc").read_text()
        actions = {}
        services = {}
        current = None
        for line in text.splitlines():
            if line.startswith(("on ", "service ")):
                current = []
                (actions if line.startswith("on ") else services)[line] = current
            elif line.startswith("    ") and current is not None:
                current.append(line.strip())
        self.assertEqual(actions["on early-init && property:ro.boot.gbos_builder.logs=1"],
                         ["setprop ro.logd.kernel true"])
        self.assertEqual(actions["on post-fs && property:ro.boot.gbos_builder.logs=1"], [
            "mkdir /metadata/gbos-builder-bootlog 0700 logd log",
            "restorecon_recursive /metadata/gbos-builder-bootlog",
            "start gbos_builder_bootlog_prepare",
        ])
        for trigger in actions:
            self.assertTrue("property:ro.boot.gbos_builder.logs=1" in trigger
                            or "property:sys.gbos_builder.bootlog.ready=1" in trigger, trigger)
        for service, options in services.items():
            self.assertIn("disabled", options, service)
        menu = (REPO / "boot/android-menu.cfg").read_text()
        self.assertIn('menuentry "Googlebook OS" {\n    boot_android\n}', menu)
        self.assertIn('menuentry "Googlebook OS (diagnostic logs)" {\n'
                      '    boot_android androidboot.gbos_builder.logs=1\n}', menu)
        self.assertNotIn("androidboot.gbos_builder.logs", (REPO / "android/cmdline.txt").read_text())
        self.assertIn('"--diagnostic-logs"', (REPO / "tools/android_smoke.py").read_text())

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
                  'ro.boot.gbos_builder.graphics) echo amd ;;\n'
                  'ro.dalvik.vm.native.bridge) echo "${NATIVE_BRIDGE:-libhoudini.so}" ;;\n'
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
        self.assertEqual(self.ready.read_text(), "sys.gbos_builder.bootlog.ready 1\n")

    def test_first_boot_records_identity_before_readiness(self):
        self.assert_ready(self.prepare())
        current = self.logs / "current"
        self.assertEqual((current / "boot-id").read_text(), BOOT_ONE + "\n")
        self.assertIn("fingerprint=test/fingerprint\n", (current / "boot.txt").read_text())
        self.assertIn("graphics_boot_property=amd\n", (current / "boot.txt").read_text())
        self.assertIn("native_bridge=libhoudini.so\n", (current / "boot.txt").read_text())
        self.assertEqual(current.stat().st_mode & 0o777, 0o700)
        self.assertFalse((self.logs / "previous").exists())

    def test_selected_native_bridge_is_recorded(self):
        self.assert_ready(self.prepare(NATIVE_BRIDGE="libndk_translation.so"))
        self.assertIn("native_bridge=libndk_translation.so\n",
                      (self.logs / "current/boot.txt").read_text())

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
        for stream in ("kernel", "android", "android-boot", "crash"):
            for suffix in ("", ".1", ".2", ".3", ".4", ".5", ".6", ".7"):
                (current / f"{stream}.log{suffix}").write_text("old\n")
        (current / "touchpad.log").write_text("status=capturing\n")
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
        self.assertIn("gbos_builder_bootlog_prepare failed", result.stderr)
        self.assertFalse(self.ready.exists())
        self.assertEqual(unknown.read_text(), "do not delete\n")
        self.assertEqual((self.logs / "current/boot-id").read_text(), BOOT_TWO + "\n")

    def test_previous_snapshot_symlink_stops_rotation(self):
        self.assert_ready(self.prepare())
        self.assert_ready(self.prepare(BOOT_TWO))
        target = self.work / "outside"
        target.write_text("keep\n")
        snapshot = self.logs / "previous/hardware.txt"
        snapshot.symlink_to(target)

        result = self.prepare(BOOT_THREE)

        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.ready.exists())
        self.assertTrue(snapshot.is_symlink())
        self.assertEqual(target.read_text(), "keep\n")
        self.assertEqual((self.logs / "current/boot-id").read_text(), BOOT_TWO + "\n")

    def test_previous_touchpad_symlink_stops_rotation(self):
        self.assert_ready(self.prepare())
        self.assert_ready(self.prepare(BOOT_TWO))
        target = self.work / "outside"
        target.write_text("keep\n")
        (self.logs / "previous/touchpad.log").symlink_to(target)
        result = self.prepare(BOOT_THREE)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(self.ready.exists())
        self.assertEqual(target.read_text(), "keep\n")

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
        self.assertIn("gbos_builder_bootlog_prepare failed", result.stderr)
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
        self.assertIn("on property:sys.gbos_builder.bootlog.ready=1", text)
        self.assertIn("on property:sys.boot_completed=1 && property:sys.gbos_builder.bootlog.ready=1\n"
                      "    start gbos_builder_hardware_snapshot\n"
                      "    stop gbos_builder_android_boot_log\n", text)
        self.assertIn("seclabel u:r:gbos_builder_hardware_diag:s0", text)
        commands = [line.split() for line in text.splitlines()
                    if line.startswith("service gbos_builder_") and "/system/bin/logcat" in line]
        self.assertEqual(len(commands), 4)
        rotate_kib = {}
        for command in commands:
            self.assertEqual(command[2], "/system/bin/logcat")
            self.assertEqual(command[command.index("-v") + 1], "long")
            self.assertEqual(int(command[command.index("-n") + 1]), 7)
            rotate_kib[command[1]] = int(command[command.index("-r") + 1])
            # The live file plus seven archives must stay within 16 MiB per stream per boot.
            self.assertLessEqual(rotate_kib[command[1]] * 8, 16 * 1024)
            self.assertTrue(command[-1].startswith("/metadata/gbos-builder-bootlog/current/"))
        self.assertEqual(rotate_kib, {"gbos_builder_kernel_log": 256, "gbos_builder_android_log": 256,
                                      "gbos_builder_android_boot_log": 1024, "gbos_builder_crash_log": 256})
        self.assertEqual(commands[0][commands[0].index("-b") + 1], "kernel")
        self.assertEqual(commands[1][commands[1].index("-b") + 1], "main,system,crash,events")
        self.assertEqual(commands[2][1], "gbos_builder_android_boot_log")

        def without_rotate_size(command):
            index = command.index("-r")
            return command[2:index] + command[index + 2:-1]

        self.assertEqual(without_rotate_size(commands[2]), without_rotate_size(commands[1]))
        self.assertEqual(commands[2][-1], "/metadata/gbos-builder-bootlog/current/android-boot.log")
        self.assertEqual(commands[3][commands[3].index("-b") + 1], "crash")
        self.assertEqual(commands[3][-1], "/metadata/gbos-builder-bootlog/current/crash.log")
        self.assertNotIn("stop gbos_builder_crash_log", text)
        for command in commands:
            self.assertIn(f"    start {command[1]}\n", text)

    def test_retired_touchpad_capture_has_no_runtime_or_policy_access(self):
        init = (REPO / "android/system_ext/bootlog.rc").read_text()
        installs = (REPO / "android/system_ext/install.list").read_text()
        policy = (REPO / "android/system/bootlog-policy.patch").read_text()
        self.assertNotIn("touchpad", init)
        self.assertNotIn("touchpad-capture", installs)
        self.assertFalse((REPO / "android/system_ext/touchpad-capture.sh").exists())
        self.assertNotIn("gbos_builder_touchpad_diag", policy)
        self.assertNotIn("input_device", policy)

    def test_policy_allows_rotation_only_in_our_directory_type(self):
        policy = (REPO / "android/system/bootlog-policy.patch").read_text()
        permissions = [line for line in policy.splitlines()
                       if line.startswith("+(allow gbos_builder_bootlog gbos_builder_bootlog_file (dir")]
        self.assertEqual(len(permissions), 1)
        self.assertIn("rename", permissions[0])
        self.assertIn("rmdir", permissions[0])
        self.assertNotIn("(permissive", policy)
        self.assertNotIn("(capability", policy)
        self.assertNotIn("blk_file", policy)
        self.assertIn("gbos_builder_hardware_diag proc_asound", policy)
        self.assertIn("gbos_builder_hardware_diag proc_modules", policy)
        self.assertIn("gbos_builder_hardware_diag audio_device", policy)
        self.assertIn("gbos_builder_hardware_diag sysfs", policy)
        self.assertIn("gbos_builder_hardware_diag device (dir (search))", policy)
        self.assertNotIn("allow gbos_builder_hardware_diag audio_device (chr_file", policy)

    def test_hardware_snapshot_reads_only_declared_device_metadata(self):
        script = SNAPSHOT.read_text()
        for path in ("/class/backlight/*", "/class/sound/card[0-9]*",
                     "/asound/cards", "/asound/pcm", "/modules", "/snd/*",
                     "/class/drm/card[0-9]*-*", "/devices/system/cpu/amd_pstate/status",
                     "/devices/system/cpu/cpufreq/policy[0-9]*"):
            self.assertIn(path, script)
        self.assertNotRegex(script, r'(?m)^.*(?:>|>>)\s*"\$sys_root')
        self.assertNotIn("chmod", script)


class HardwareSnapshotTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.logs = self.work / "logs"
        (self.logs / "current").mkdir(parents=True)
        self.sys = self.work / "sys"
        self.proc = self.work / "proc"
        self.dev = self.work / "dev"
        for root in (self.sys, self.proc, self.dev):
            root.mkdir()

    def snapshot(self):
        return subprocess.run(
            ["sh", str(SNAPSHOT), str(self.logs), str(self.sys), str(self.proc), str(self.dev)],
            capture_output=True, text=True)

    def test_records_backlight_and_audio_device_details(self):
        backlight = self.sys / "class/backlight/amdgpu_bl0"
        backlight.mkdir(parents=True)
        (backlight / "type").write_text("raw\n")
        (backlight / "brightness").write_text("128\n")
        (backlight / "actual_brightness").write_text("128\n")
        (backlight / "max_brightness").write_text("255\n")
        card = self.sys / "class/sound/card1"
        chip = card / "device/hdaudioC1D0"
        chip.mkdir(parents=True)
        (card / "id").write_text("Generic_1\n")
        (card / "number").write_text("1\n")
        (chip / "chip_name").write_text("Realtek ALC256\n")
        asound = self.proc / "asound"
        asound.mkdir()
        (asound / "cards").write_text(" 1 [Generic_1]: HD-Audio Generic - Realtek ALC256\n")
        (asound / "pcm").write_text("01-00: ALC256 Analog : playback 1 : capture 1\n")
        (self.proc / "modules").write_text("snd_hda_intel 1 0 - Live 0x0\n")
        sound_devices = self.dev / "snd"
        sound_devices.mkdir()
        (sound_devices / "controlC1").touch()
        (sound_devices / "pcmC1D0p").touch()

        result = self.snapshot()

        self.assertEqual(result.returncode, 0, result.stderr)
        hardware = (self.logs / "current/hardware.txt").read_text()
        self.assertIn("device=amdgpu_bl0\n", hardware)
        self.assertIn("brightness=128\n", hardware)
        self.assertIn("max_brightness=255\n", hardware)
        self.assertIn("card=card1\n", hardware)
        self.assertIn("id=Generic_1\n", hardware)
        self.assertIn("chip_name=Realtek ALC256\n", hardware)
        self.assertIn("asound_cards= 1 [Generic_1]: HD-Audio Generic - Realtek ALC256\n", hardware)
        self.assertIn("snd_hda_intel", hardware)
        self.assertIn("controlC1", hardware)
        self.assertFalse((self.logs / "current/hardware.txt.tmp").exists())

    def test_records_display_connectors_and_cpu_frequency_policy(self):
        connector_target = self.work / "devices/card0/card0-HDMI-A-1"
        connector_target.mkdir(parents=True)
        (connector_target / "status").write_text("connected\n")
        (connector_target / "enabled").write_text("enabled\n")
        (connector_target / "dpms").write_text("On\n")
        (connector_target / "modes").write_text("1920x1080\n1280x720\n")
        drm = self.sys / "class/drm"
        drm.mkdir(parents=True)
        (drm / "card0-HDMI-A-1").symlink_to(connector_target)
        (drm / "renderD128").mkdir()
        cpu = self.sys / "devices/system/cpu"
        (cpu / "amd_pstate").mkdir(parents=True)
        (cpu / "amd_pstate/status").write_text("active\n")
        policy = cpu / "cpufreq/policy11"
        policy.mkdir(parents=True)
        (policy / "scaling_driver").write_text("amd-pstate-epp\n")
        (policy / "scaling_governor").write_text("performance\n")
        (policy / "energy_performance_preference").write_text("performance\n")

        result = self.snapshot()

        self.assertEqual(result.returncode, 0, result.stderr)
        hardware = (self.logs / "current/hardware.txt").read_text()
        self.assertIn("connector=card0-HDMI-A-1\n", hardware)
        self.assertIn("status=connected\n", hardware)
        self.assertIn("modes=1920x1080\n1280x720\n", hardware)
        self.assertNotIn("renderD128", hardware)
        self.assertIn("amd_pstate_status=active\n", hardware)
        self.assertIn("policy=policy11\n", hardware)
        self.assertIn("scaling_driver=amd-pstate-epp\n", hardware)
        self.assertIn("energy_performance_preference=performance\n", hardware)
        self.assertIn("scaling_max_freq=[missing or unreadable]\n", hardware)

    def test_reports_absent_devices_and_missing_sound_files(self):
        result = self.snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        hardware = (self.logs / "current/hardware.txt").read_text()
        self.assertIn("backlight_devices:\nnone\n", hardware)
        self.assertIn("sound_cards:\nnone\n", hardware)
        self.assertIn("asound_cards=[missing or unreadable]", hardware)
        self.assertIn("asound_pcm=[missing or unreadable]\n", hardware)
        self.assertIn("loaded_sound_modules:\n[missing or unreadable]", hardware)
        self.assertIn("sound_device_nodes:\nabsent\n", hardware)
        self.assertIn("display_connectors:\nnone\n", hardware)
        self.assertIn("cpu_frequency:\namd_pstate_status=[missing or unreadable]\nnone\n", hardware)

    def test_refuses_symlinked_output(self):
        target = self.work / "outside"
        target.write_text("keep\n")
        (self.logs / "current/hardware.txt").symlink_to(target)
        result = self.snapshot()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gbos-builder hardware snapshot failed", result.stderr)
        self.assertEqual(target.read_text(), "keep\n")

    def test_empty_proc_file_keeps_next_section_on_a_new_line(self):
        (self.proc / "asound").mkdir()
        (self.proc / "asound/pcm").touch()
        result = self.snapshot()
        self.assertEqual(result.returncode, 0, result.stderr)
        hardware = (self.logs / "current/hardware.txt").read_text()
        self.assertIn("asound_pcm=\nloaded_sound_modules:\n", hardware)

    def test_refuses_directory_at_output_path(self):
        (self.logs / "current/hardware.txt").mkdir()
        result = self.snapshot()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gbos-builder hardware snapshot failed", result.stderr)
        self.assertEqual(list((self.logs / "current/hardware.txt").iterdir()), [])


if __name__ == "__main__":
    unittest.main()
