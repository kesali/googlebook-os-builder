"""Exercise disposable super-image guards and byte-for-byte payload verification."""

import io
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from lp import Extent, Partition
from super_candidate import build, regular_file, verify_payload


class SuperCandidateTests(unittest.TestCase):
    def test_regular_file_rejects_directory_and_symlink(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "image"
            image.write_bytes(b"payload")
            link = root / "link"
            link.symlink_to(image)
            self.assertEqual(regular_file(image), image)
            for path in (root, link, root / "missing"):
                with self.subTest(path=path), self.assertRaisesRegex(ValueError, "regular file"):
                    regular_file(path)

    def test_existing_output_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.write_bytes(b"keep")
            for output in (source, root / "dangling"):
                if output != source:
                    output.symlink_to(root / "missing")
                with self.assertRaisesRegex(ValueError, "Refusing to replace"):
                    build(source, source, root, source, output)
            self.assertEqual(source.read_bytes(), b"keep")

    def test_output_outside_repository_out_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.write_bytes(b"keep")
            with self.assertRaisesRegex(ValueError, "out/"):
                build(source, source, root, source, root / "output")

    def test_android_disk_output_is_rejected_even_if_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.write_bytes(b"keep")
            output = Path(__file__).resolve().parents[1] / "out/android/disk.img"
            # Existing outputs are rejected earlier; exercise the absent-file guard.
            from unittest.mock import patch
            with patch.object(Path, "exists", return_value=False), \
                    patch.object(Path, "is_symlink", return_value=False), \
                    self.assertRaisesRegex(ValueError, "never Android's disk.img"):
                build(source, source, root, source, output)

    def test_payload_and_padding_are_verified_across_extents(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "payload"
            source.write_bytes(b"a" * 512 + b"b" * 3)
            partition = Partition("vendor_dlkm_a", "group", [
                Extent(1, 0, 1, 0), Extent(1, 0, 3, 0)])
            image = bytes(512) + b"a" * 512 + bytes(512) + b"bbb" + bytes(509)
            verify_payload(io.BytesIO(image), partition, source)
            for changed in (image[:512] + b"x" + image[513:], image[:-1] + b"x", image[:-1]):
                with self.subTest(), self.assertRaisesRegex(ValueError, "Payload or padding"):
                    verify_payload(io.BytesIO(changed), partition, source)

    def test_payload_larger_than_extents_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "payload"
            source.write_bytes(b"a" * 513)
            partition = Partition("vendor_dlkm_a", "group", [Extent(1, 0, 0, 0)])
            with self.assertRaisesRegex(ValueError, "Truncated payload"):
                verify_payload(io.BytesIO(b"a" * 512), partition, source)


if __name__ == "__main__":
    unittest.main()
