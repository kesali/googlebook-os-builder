"""Exercise MSI audio preparation and XML routing; never open a real sound device."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[1]
SELECTOR = REPO / "android/vendor/get_variant_audio"


class AudioRouteTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        audio = root / "etc/audio/sof-rt5682_alc5682ivs_tas2563"
        shutil.copytree(REPO / "tests/audio", audio)
        result = subprocess.run(
            ["patch", "--batch", "--fuzz=0", "-p1", "-i",
             str(REPO / "android/vendor/audio-msi.patch")],
            cwd=root, capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.config = ET.parse(audio / "audio_config.xml").getroot()
        self.mixer = ET.parse(audio / "mixer_paths.xml").getroot()

    def test_internal_mic_uses_named_acp_card_not_analog_headset(self):
        self.assertEqual(self.config.findtext("SoundCardName"), "hw:sofrt5682")
        route = self.config.find("HiFi/InternalMic")
        self.assertIsNotNone(route)
        self.assertEqual(route.findtext("CapturePCM"), "hw:acp,0")
        self.assertEqual(route.findtext("CaptureChannelMap/FL"), "0")
        self.assertEqual(route.findtext("CaptureChannelMap/FR"), "1")
        self.assertIsNone(route.find("JackDev"))
        self.assertIsNone(route.find("CaptureMixerElem"))
        path = self.mixer.find("path[@name='InternalMic']")
        self.assertIsNotNone(path)
        self.assertEqual(list(path), [])

    def test_existing_analog_routes_and_capture_controls_are_preserved(self):
        for route in ("Speaker", "Headphone"):
            self.assertEqual(self.config.findtext(f"HiFi/{route}/PlaybackPCM"),
                             "hw:sofrt5682,0")
        self.assertEqual(self.config.findtext("HiFi/Mic/CapturePCM"), "hw:sofrt5682,0")
        self.assertEqual(self.config.findtext("HiFi/Mic/JackDev"), "HD-Audio Generic Mic")
        self.assertEqual(self.config.findtext("HiFi/Headphone/JackDev"),
                         "HD-Audio Generic Headphone")
        self.assertEqual(self.mixer.find("ctl[@name='Capture Switch']").get("value"), "0 0")
        headset = self.mixer.find("path[@name='Mic']")
        self.assertEqual([(control.get("name"), control.get("value")) for control in headset],
                         [("Capture Volume", "23 23"), ("Capture Switch", "1 1")])
        self.assertEqual({route.tag for route in self.config.find("HiFi")},
                         {"Speaker", "Headphone", "Mic", "InternalMic"})


class AudioTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name)
        self.sys = self.work / "sys"
        self.bin = self.work / "bin"
        self.bin.mkdir()
        self.ready = self.work / "ready"
        self.tool("sleep", "exit 0\n")
        self.tool("setprop", 'printf "%s %s\\n" "$1" "$2" > "$READY"\n')
        self.tool("log", 'printf "%s\\n" "$*" >&2\n')

    def tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\nset -eu\n" + body)
        path.chmod(0o755)

    def card(self, number, codec_name, card_id):
        card = self.sys / f"class/sound/card{number}"
        codec = card / f"device/hdaudioC{number}D0"
        codec.mkdir(parents=True)
        (codec / "chip_name").write_text(codec_name + "\n")
        (card / "id").write_text(card_id + "\n")
        return card

    def prepare(self):
        env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}", READY=str(self.ready))
        return subprocess.run(["sh", str(SELECTOR), str(self.sys), "ALC256"],
                              env=env, capture_output=True, text=True)

    def test_selects_codec_not_card_number_or_generic_id(self):
        hdmi = self.card(0, "R6xx HDMI", "Generic")
        analog = self.card(3, "ALC256", "Generic_1")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((analog / "id").read_text(), "sofrt5682")
        self.assertEqual((hdmi / "id").read_text(), "Generic\n")
        self.assertEqual(self.ready.read_text(), "vendor.audio.gbos_builder.ready 1\n")

    def test_card_id_write_contains_no_whitespace(self):
        card = self.card(1, "ALC256", "Generic")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((card / "id").read_bytes(), b"sofrt5682")

    def test_restart_does_not_rewrite_the_renamed_card(self):
        card = self.card(1, "ALC256", "sofrt5682")
        stamp = (card / "id").stat().st_mtime_ns
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((card / "id").stat().st_mtime_ns, stamp)

    def test_waits_for_codec_registration(self):
        card = self.card(1, "not-ready", "Generic_1")
        self.tool("sleep", f"printf 'ALC256\\n' > '{card}/device/hdaudioC1D0/chip_name'\n")
        result = self.prepare()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(self.ready.exists())

    def test_missing_or_different_codec_is_bounded_and_reported(self):
        for name in ("R6xx HDMI", "ALC255"):
            with self.subTest(codec=name):
                card = self.card(1, name, "Generic")
                result = self.prepare()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("No ALC256 sound card appeared", result.stderr)
                self.assertFalse(self.ready.exists())
                self.assertEqual((card / "id").read_text(), "Generic\n")
                (card / "device/hdaudioC1D0/chip_name").unlink()
                (card / "device/hdaudioC1D0").rmdir()

    def test_write_failure_never_signals_readiness(self):
        card = self.card(1, "ALC256", "Generic_1")
        (card / "id").unlink()
        (card / "id").mkdir()
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gbos-builder audio preparation failed", result.stderr)
        self.assertFalse(self.ready.exists())

    def test_property_failure_is_reported(self):
        self.card(1, "ALC256", "Generic_1")
        self.tool("setprop", "exit 1\n")
        result = self.prepare()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("gbos-builder audio preparation failed", result.stderr)

    def test_service_is_laptop_only_and_restarts_hal_after_readiness(self):
        text = (REPO / "android/vendor/audio-msi.rc").read_text()
        self.assertIn("on boot && property:ro.boot.gbos_builder.graphics=amd", text)
        self.assertIn("on boot && property:ro.boot.gbos_builder.graphics=amd-vulkan", text)
        self.assertIn("/vendor/bin/get_variant_audio /sys ALC256", text)
        self.assertIn("on property:vendor.audio.gbos_builder.ready=1\n    restart vendor.audio-hal-aidl", text)
        self.assertNotIn("mount", text)

    def test_policy_does_not_grant_generic_sysfs_write(self):
        patch = (REPO / "android/vendor/audio-policy.patch").read_text()
        allows = [line for line in patch.splitlines() if line.startswith("+(allow ")]
        self.assertIn("+(allow get_variant_audio gbos_builder_audio_id (file (getattr open read write)))",
                      allows)
        self.assertFalse(any("sysfs_" in line or "sysfs " in line for line in allows))
        self.assertNotIn("(permissive", patch)


if __name__ == "__main__":
    unittest.main()
