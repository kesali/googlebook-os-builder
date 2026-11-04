"""Exercise HD-audio preparation and laptop XML routing; never open a real sound device."""

from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[3]
BOARD = "etc/audio/sof-rt5682_alc5682ivs_tas2563"
LENOVO = "etc/audio/gbos-builder-lenovo-e50-80"


import sys
sys.path.insert(0, str(REPO / "tests"))
from recipe_support import patched_audio


class LenovoAudioRouteTests(unittest.TestCase):
    def setUp(self):
        self.config, self.mixer = patched_audio(
            self, LENOVO, "hardware/lenovo-e50-80/vendor/audio-lenovo.patch")

    def test_all_routes_use_the_alc233_card_and_its_jack_devices(self):
        self.assertEqual(self.config.findtext("SoundCardName"), "hw:sofrt5682")
        self.assertEqual({route.tag for route in self.config.find("HiFi")},
                         {"Speaker", "Headphone", "Mic", "InternalMic"})
        for route in ("Speaker", "Headphone"):
            self.assertEqual(self.config.findtext(f"HiFi/{route}/PlaybackPCM"),
                             "hw:sofrt5682,0")
        for route in ("Mic", "InternalMic"):
            self.assertEqual(self.config.findtext(f"HiFi/{route}/CapturePCM"),
                             "hw:sofrt5682,0")
        self.assertEqual(self.config.findtext("HiFi/Headphone/JackDev"),
                         "HDA Intel PCH Headphone")
        self.assertEqual(self.config.findtext("HiFi/Mic/JackDev"), "HDA Intel PCH Mic")
        self.assertIsNone(self.config.find("HiFi/InternalMic/JackDev"))

    def test_both_microphones_open_the_codec_adc(self):
        for route in ("Mic", "InternalMic"):
            path = self.mixer.find(f"path[@name='{route}']")
            self.assertEqual([(control.get("name"), control.get("value")) for control in path],
                             [("Capture Volume", "23 23"), ("Capture Switch", "1 1")])
        self.assertEqual(self.mixer.find("ctl[@name='Master Playback Volume']").get("value"), "87")

    def test_config_is_bind_mounted_before_the_hal_restarts(self):
        text = (REPO / "hardware/lenovo-e50-80/vendor/audio-lenovo.rc").read_text()
        self.assertIn("on boot && property:ro.boot.gbos_builder.graphics=intel", text)
        self.assertIn("/vendor/bin/get_variant_audio /sys ALC233", text)
        self.assertIn("on property:vendor.audio.gbos_builder.ready=ALC233\n"
                      f"    mount none /vendor/{LENOVO} /vendor/{BOARD} bind\n"
                      "    restart vendor.audio-hal-aidl", text)

    def test_only_the_lenovo_card_id_is_labelled(self):
        patch = (REPO / "hardware/lenovo-e50-80/vendor/audio-policy.patch").read_text()
        added = [line for line in patch.splitlines()
                 if line.startswith("+") and not line.startswith("+++")]
        self.assertIn("+/sys/devices/pci0000:00/0000:00:1b\\.0/sound/card[0-9]+/id "
                      "u:object_r:gbos_builder_audio_id:s0", added)
        self.assertIn("+/sys/devices/pci0000:00/0000:00:1b.0/sound/card* id 0644 root root", added)
        self.assertFalse(any("(allow" in line for line in added))


if __name__ == "__main__":
    unittest.main()
