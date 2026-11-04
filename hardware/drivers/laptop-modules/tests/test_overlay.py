"""The declared Android changes and the scripts that apply and check them."""

from pathlib import Path
import unittest


REPO = Path(__file__).resolve().parents[4]


class ChangeDataTests(unittest.TestCase):
    def test_vendor_dlkm_unblocks_msi_hda_audio(self):
        patch = (REPO / "hardware/drivers/laptop-modules/vendor_dlkm/modules.patch").read_text()
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


if __name__ == "__main__":
    unittest.main()
