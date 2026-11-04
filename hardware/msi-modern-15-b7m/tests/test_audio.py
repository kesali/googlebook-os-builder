"""Exercise HD-audio preparation and laptop XML routing; never open a real sound device."""

from pathlib import Path
import unittest

REPO = Path(__file__).resolve().parents[3]
BOARD = "etc/audio/sof-rt5682_alc5682ivs_tas2563"


import sys
sys.path.insert(0, str(REPO / "tests"))
from recipe_support import patched_audio


class AudioRouteTests(unittest.TestCase):
    def setUp(self):
        self.config, self.mixer = patched_audio(
            self, BOARD, "hardware/msi-modern-15-b7m/vendor/audio-msi.patch")

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
    def test_msi_service_is_laptop_only_and_restarts_hal_after_its_codec(self):
        text = (REPO / "hardware/msi-modern-15-b7m/vendor/audio-msi.rc").read_text()
        self.assertIn("on boot && property:ro.boot.gbos_builder.graphics=amd", text)
        self.assertIn("on boot && property:ro.boot.gbos_builder.graphics=amd-vulkan", text)
        self.assertIn("/vendor/bin/get_variant_audio /sys ALC256", text)
        self.assertIn("on property:vendor.audio.gbos_builder.ready=ALC256\n    restart vendor.audio-hal-aidl", text)
        self.assertNotIn("mount", text)


if __name__ == "__main__":
    unittest.main()
