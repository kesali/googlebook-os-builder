"""Shared recipe-test fixture operations; never touch hardware or build images."""

from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

REPO = ROOT = Path(__file__).resolve().parents[1]


def inspect_kernel_recipes(*arguments):
    return subprocess.run(
        ["make", "--no-print-directory", "-f", str(ROOT / "Makefile"), "-f", "-",
         "inspect-kernel-recipes", *arguments],
        cwd=ROOT, capture_output=True, text=True,
        input=".PHONY: inspect-kernel-recipes\ninspect-kernel-recipes:\n"
              "\t@printf '%s\\n' '$(KERNEL_PATCHES)' '$(KERNEL_PATCH_SHA)' '$(KERNEL_SRC)'\n",
    )


def recipe_patch(name):
    matches = list((ROOT / "hardware/drivers").glob(f"*/{name}"))
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one recipe patch named {name}: {matches}")
    return matches[0]


def patched_text(name):
    """The new side of a source patch: context and added lines, without the header."""
    patch = recipe_patch(name).read_text()
    return "\n".join(line[1:] for line in patch.splitlines()
                     if line.startswith((" ", "+")) and not line.startswith("+++"))


def patched_audio(test, directory, patch):
    """Apply a laptop audio patch to Google's board files copied to DIRECTORY."""
    temporary = tempfile.TemporaryDirectory()
    test.addCleanup(temporary.cleanup)
    root = Path(temporary.name)
    shutil.copytree(REPO / "hardware/drivers/hda-audio/tests/fixtures", root / directory)
    result = subprocess.run(
        ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(REPO / patch)],
        cwd=root, capture_output=True, text=True,
    )
    test.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    return (ET.parse(root / directory / "audio_config.xml").getroot(),
            ET.parse(root / directory / "mixer_paths.xml").getroot())


CAMERA_TABLE = REPO / "tests/camera/internal_usb_camera_info.txtpb"


def front_camera_entry(usb_id, name):
    return (
        "camera_modules {\n"
        f'  key: "{usb_id}" # {name}\n'
        "  value {\n"
        "    facing: FACING_FRONT\n"
        "  }\n"
        "}\n"
    )


def patched_camera_table(test, *patches):
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        config = root / "etc/camera/internal_usb_camera_info.txtpb"
        config.parent.mkdir(parents=True)
        shutil.copyfile(CAMERA_TABLE, config)
        for patch_file in patches:
            result = subprocess.run(
                ["patch", "--batch", "--fuzz=0", "-p1", "-i", str(REPO / patch_file)],
                cwd=root, capture_output=True, text=True,
            )
            test.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return config.read_text()
