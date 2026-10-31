"""The boot-file script: what it writes into the disk's EFI-SYSTEM partition, and when it refuses."""

import fcntl
import hashlib
from pathlib import Path
import subprocess
import tempfile
import unittest

from tools import deploy

REPO = Path(__file__).resolve().parents[1]
BOOT_SCRIPT = REPO / "scripts/android-boot.sh"

SECTOR = 512
MIB = 2048  # sectors

# Android's disk in miniature: a data partition on each side of EFI-SYSTEM. FAT32 needs at least
# 65525 clusters, and with 4 KiB clusters that takes more than 256 MiB.
ESP_START = 2 * MIB
ESP_SECTORS = 300 * MIB
DISK_SECTORS = 304 * MIB  # sparse; the last MiB holds the backup partition table


class AndroidBootTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.work = Path(directory.name)
        self.disk = self.work / "disk.img"
        self.esp = f"{self.disk}@@{ESP_START * SECTOR}"
        self.make_disk()

    def make_disk(self):
        table = [
            "label: gpt",
            f'start={MIB}, size={MIB}, type=L, name="before"',
            f'start={ESP_START}, size={ESP_SECTORS}, type=U, name="EFI-SYSTEM"',
            f'start={ESP_START + ESP_SECTORS}, size={MIB}, type=L, name="after"',
        ]
        with self.disk.open("wb") as image:
            image.truncate(DISK_SECTORS * SECTOR)
        subprocess.run(["sfdisk", "--quiet", "--no-reread", str(self.disk)],
                       input="\n".join(table) + "\n", text=True, check=True)
        subprocess.run(["mkfs.vfat", "-F", "32", "-s", "8", "-n", "DALI-BOOT", "--offset", str(ESP_START),
                        str(self.disk), str(ESP_SECTORS // 2)], capture_output=True, check=True)
        # Data on both sides of the boot partition: writing must stop at its edges.
        self.write(MIB * SECTOR, b"B" * MIB * SECTOR)
        self.write((ESP_START + ESP_SECTORS) * SECTOR, b"A" * MIB * SECTOR)

    def write(self, offset, data):
        with self.disk.open("r+b") as image:
            image.seek(offset)
            image.write(data)

    def make_bundle(self, kernel):
        """Fake build outputs with the repository's menu and command line, as the Makefile bundles them."""
        inputs = self.work / "inputs"
        inputs.mkdir(exist_ok=True)
        for name, data in (("kernel", kernel), ("initramfs.gz", b"initrd"), ("BOOTX64.EFI", b"grub")):
            (inputs / name).write_bytes(data)
        bundle = self.work / "bundle"
        deploy.bundle([*(inputs / name for name in deploy.COMPONENTS[:3]), REPO / "boot/android-menu.cfg"],
                      bundle, "android", REPO / "android/cmdline.txt")
        return bundle

    def run_script(self, bundle, disk=None):
        return subprocess.run(["bash", str(BOOT_SCRIPT), str(disk or self.disk), str(bundle)],
                              capture_output=True, text=True)

    def disk_hash(self):
        result = hashlib.sha256()
        with self.disk.open("rb") as image:
            while block := image.read(1 << 20):
                result.update(block)
        return result.hexdigest()

    def outside_esp(self):
        """Every byte of the disk except EFI-SYSTEM: both partition tables and both neighbours."""
        with self.disk.open("rb") as image:
            head = image.read(ESP_START * SECTOR)
            image.seek((ESP_START + ESP_SECTORS) * SECTOR)
            return head, image.read()

    def files_in_esp(self):
        """The boot files as the partition holds them, copied out with mtools."""
        directory = Path(tempfile.mkdtemp(dir=self.work))
        subprocess.run(["mcopy", "-s", "-n", "-i", self.esp, "::EFI", "::dali", str(directory)], check=True)
        return {str(path.relative_to(directory)): path.read_bytes()
                for path in directory.rglob("*") if path.is_file()}

    def assert_refused(self, message, disk=None):
        before = self.disk_hash()
        result = self.run_script(self.make_bundle(b"kernel one"), disk)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(message, result.stderr)
        self.assertEqual(self.disk_hash(), before)

    def test_boot_files_land_in_the_partition_and_nothing_else_changes(self):
        outside = self.outside_esp()
        result = self.run_script(self.make_bundle(b"kernel one"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

        files = self.files_in_esp()
        kernel = f"dali/kernel-{deploy.digest(b'kernel one')}"
        self.assertEqual(sorted(files), sorted([
            "EFI/BOOT/BOOTX64.EFI", "dali/format", "dali/grub.cfg", kernel,
            f"dali/initramfs-{deploy.digest(b'initrd')}",
        ]))
        self.assertEqual(files["EFI/BOOT/BOOTX64.EFI"], b"grub")
        self.assertEqual(files[kernel], b"kernel one")
        self.assertEqual(files["dali/format"], b"gbos-dali-android-v1\n")
        self.assertIn(kernel.encode(), files["dali/grub.cfg"])
        self.assertEqual(self.outside_esp(), outside)

    def test_a_second_run_with_the_same_files_writes_nothing(self):
        bundle = self.make_bundle(b"kernel one")
        self.assertEqual(self.run_script(bundle).returncode, 0)
        before = (self.disk.stat().st_mtime_ns, self.disk_hash())
        result = self.run_script(bundle)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("up to date", result.stdout)
        self.assertEqual((self.disk.stat().st_mtime_ns, self.disk_hash()), before)

    def test_a_new_build_replaces_the_old_files_instead_of_adding_to_them(self):
        self.assertEqual(self.run_script(self.make_bundle(b"kernel one")).returncode, 0)
        result = self.run_script(self.make_bundle(b"kernel two"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        files = self.files_in_esp()
        self.assertIn(f"dali/kernel-{deploy.digest(b'kernel two')}", files)
        self.assertNotIn(f"dali/kernel-{deploy.digest(b'kernel one')}", files)

    def test_an_interrupted_run_is_repaired_by_running_again(self):
        bundle = self.make_bundle(b"kernel one")
        self.assertEqual(self.run_script(bundle).returncode, 0)
        subprocess.run(["mdel", "-i", self.esp, f"::dali/kernel-{deploy.digest(b'kernel one')}"], check=True)
        result = self.run_script(bundle)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.files_in_esp()[f"dali/kernel-{deploy.digest(b'kernel one')}"], b"kernel one")

    def test_refuses_a_partition_that_is_not_the_dali_boot_file_system(self):
        subprocess.run(["mlabel", "-i", self.esp, "::OTHER"], check=True)
        self.assert_refused("not the DALI-BOOT file system")

    def test_refuses_a_partition_without_a_file_system(self):
        self.write(ESP_START * SECTOR, bytes(MIB * SECTOR))
        self.assert_refused("not the DALI-BOOT file system")

    def test_refuses_a_disk_without_an_efi_system_partition(self):
        subprocess.run(["sfdisk", "--quiet", "--no-reread", "--delete", str(self.disk), "2"], check=True)
        self.assert_refused("no EFI-SYSTEM")

    def test_refuses_anything_but_a_disk_image_file(self):
        self.assert_refused("not a disk image file", disk=self.work)

    def test_refuses_while_the_disk_is_in_use(self):
        with open(f"{self.disk}.lock", "w") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self.assert_refused("already in use")


if __name__ == "__main__":
    unittest.main()
