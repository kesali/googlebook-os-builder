"""The Android disk script: the FAT32 boot partition it creates, and when it refuses to."""

import json
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
DISK_SCRIPT = REPO / "scripts/android-disk.sh"

SECTOR = 512
MIB = 2048  # sectors

# Google's disk in miniature: EFI-SYSTEM (64 MiB), KERN-A (512 MiB) right after it, the vbmeta
# partitions, then userdata. As in Google's table, userdata is entry 1 and KERN-A entry 2.
ESP_START = 1 * MIB
KERN_START = ESP_START + 64 * MIB
KERN_END = KERN_START + 512 * MIB
DISK_SIZE = 19 * 1024 * MIB  # sparse, like Google's image: mkfs.vfat picks cluster sizes by disk size
USERDATA_GIB = 32  # the Makefile's default


def layout(disk):
    """The partitions of a disk image, by name."""
    result = subprocess.run(["sfdisk", "--json", str(disk)], stdout=subprocess.PIPE, text=True, check=True)
    partitions = json.loads(result.stdout)["partitiontable"]["partitions"]
    return {partition["name"]: partition for partition in partitions}


def read_sectors(disk, start, count):
    with disk.open("rb") as image:
        image.seek(start * SECTOR)
        return image.read(count * SECTOR)


def fat32_geometry(boot_sector):
    """Total sectors and cluster count of a FAT32 file system, from its boot sector."""
    sectors_per_cluster = boot_sector[13]
    reserved_sectors, = struct.unpack_from("<H", boot_sector, 14)
    fat_count = boot_sector[16]
    total_sectors, fat_sectors = struct.unpack_from("<II", boot_sector, 32)
    data_sectors = total_sectors - reserved_sectors - fat_count * fat_sectors
    return total_sectors, data_sectors // sectors_per_cluster


class AndroidDiskTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.recovery = self.work / "recovery.bin"
        self.output = self.work / "out/disk.img"

    def make_recovery(self, gap=0, with_kern_a=True):
        """Write Google's disk in miniature; a gap moves KERN-A away from EFI-SYSTEM."""
        kern_start = KERN_START + gap
        table = ["label: gpt", f'start={KERN_END + 2 * MIB}, size={MIB}, type=L, name="userdata"']
        if with_kern_a:
            table.append(f'start={kern_start}, size={KERN_END - kern_start}, type=L, name="KERN-A"')
        table += [f'start={ESP_START}, size={KERN_START - ESP_START}, type=U, name="EFI-SYSTEM"',
                  f'start={KERN_END}, size={MIB}, type=L, name="vbmeta_a"',
                  f'start={KERN_END + MIB}, size={MIB}, type=L, name="vbmeta_b"']
        with self.recovery.open("wb") as image:
            image.truncate(DISK_SIZE * SECTOR)
        subprocess.run(["sfdisk", "--quiet", "--no-reread", str(self.recovery)],
                       input="\n".join(table) + "\n", text=True, check=True)
        # Data right after KERN-A: the emptiness check has to stop where KERN-A ends.
        self.write(KERN_END * SECTOR, b"A" * MIB * SECTOR + b"B" * MIB * SECTOR)

    def write(self, offset, data):
        with self.recovery.open("r+b") as image:
            image.seek(offset)
            image.write(data)

    def run_script(self):
        return subprocess.run(["bash", str(DISK_SCRIPT), str(self.recovery), str(USERDATA_GIB), str(self.output)],
                              capture_output=True, text=True)

    def test_empty_kern_a_becomes_part_of_a_fat32_boot_partition(self):
        self.make_recovery()
        before = layout(self.recovery)
        result = self.run_script()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        after = layout(self.output)

        self.assertNotIn("KERN-A", after)
        esp_before, esp = before["EFI-SYSTEM"], after["EFI-SYSTEM"]
        self.assertEqual(esp["start"], esp_before["start"])
        self.assertEqual(esp["size"], esp_before["size"] + before["KERN-A"]["size"])
        # Android finds its disk through this partition's ID.
        self.assertEqual((esp["type"], esp["uuid"]), (esp_before["type"], esp_before["uuid"]))

        boot_sector = read_sectors(self.output, esp["start"], 1)
        self.assertEqual(boot_sector[71:90], b"DALI-BOOT  FAT32   ")  # label, then file system type
        total_sectors, clusters = fat32_geometry(boot_sector)
        self.assertLessEqual(total_sectors, esp["size"])
        self.assertGreater(total_sectors, esp["size"] - MIB)  # it fills the partition
        # Firmware tells FAT32 from FAT16 by the cluster count, and Linux would not notice.
        self.assertGreaterEqual(clusters, 65525)

        for name in ("vbmeta_a", "vbmeta_b"):
            partition = before[name]
            self.assertEqual(after[name]["start"], partition["start"])
            self.assertEqual(after[name]["uuid"], partition["uuid"])
            self.assertEqual(read_sectors(self.output, partition["start"], partition["size"]),
                             read_sectors(self.recovery, partition["start"], partition["size"]))
        verify = subprocess.run(["sfdisk", "--verify", str(self.output)], capture_output=True, text=True)
        self.assertEqual(verify.returncode, 0, verify.stdout + verify.stderr)

    def test_refuses_to_format_unless_an_empty_kern_a_follows_an_empty_efi_system(self):
        cases = [
            ("data in the first byte of EFI-SYSTEM", {}, ESP_START * SECTOR),
            ("data in the last byte of EFI-SYSTEM", {}, KERN_START * SECTOR - 1),
            ("data in the first byte of KERN-A", {}, KERN_START * SECTOR),
            ("data in the last byte of KERN-A", {}, KERN_END * SECTOR - 1),
            ("a gap between EFI-SYSTEM and KERN-A", {"gap": MIB}, None),
            ("no KERN-A", {"with_kern_a": False}, None),
        ]
        for name, options, dirty_byte in cases:
            with self.subTest(name):
                self.make_recovery(**options)
                if dirty_byte is not None:
                    self.write(dirty_byte, b"\x01")
                result = self.run_script()
                self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
                self.assertIn("refusing to format", result.stderr)
                self.assertEqual(list(self.output.parent.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
