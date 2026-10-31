#!/usr/bin/env python3
"""Make the small, explicit filesystem changes for the QEMU development image.

Run under fakeroot so ownership and SELinux xattrs survive EROFS reconstruction.
Existing files are rewritten in place, not replaced with unlabelled temporary files.
"""

import argparse
import os
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parents[1]
VENDOR_FILE = "u:object_r:vendor_file:s0"
VENDOR_CONFIG = "u:object_r:vendor_configs_file:s0"
SPHAL = "u:object_r:same_process_hal_file:s0"


def install(source, destination, label, executable=False):
    missing = []
    parent = destination.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for directory in reversed(missing):
        directory.mkdir(mode=0o755)
        os.chown(directory, 0, 0)
        os.setxattr(directory, "security.selinux", VENDOR_FILE.encode())
    destination.write_bytes(source.read_bytes())
    os.chmod(destination, 0o755 if executable else 0o644)
    os.chown(destination, 0, 2000 if executable else 0)
    os.setxattr(destination, "security.selinux", label.encode())


def needed(path):
    output = subprocess.check_output(["readelf", "-d", str(path)], text=True)
    return re.findall(r"\(NEEDED\).*?\[([^]]+)\]", output)


def dependencies(roots, vendor, donors, platform, label):
    pending = list(roots)
    seen = set()
    while pending:
        binary = pending.pop()
        if binary in seen:
            continue
        seen.add(binary)
        for name in needed(binary):
            if "/" in name:
                raise ValueError(f"Unexpected library path in {binary}: {name}")
            if (vendor / "lib64" / name).exists() or name in platform:
                continue
            candidates = [directory / name for directory in donors]
            source = next((path for path in candidates if path.is_file()), None)
            if source is None:
                raise ValueError(f"Unresolved dependency of {binary.name}: {name}")
            target = vendor / "lib64" / name
            install(source, target, label)
            pending.append(target)


def properties(path, changes):
    values = {}
    for line in changes.read_text().splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            name, value = line.split("=", 1)
            if name in values:
                raise ValueError(f"Duplicate property: {name}")
            values[name] = value
    lines = [line for line in path.read_text().splitlines() if line.split("=", 1)[0] not in values]
    lines += [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n")


def remove_hals(path, names):
    tree = ET.parse(path)
    manifest = tree.getroot()
    for hal in list(manifest.findall("hal")):
        if hal.findtext("name") in names:
            manifest.remove(hal)
    ET.indent(tree)
    tree.write(path, encoding="utf-8", xml_declaration=True)


def vendor(root, emulator, mesa, google, crossystem):
    donor = emulator / "vendor"
    gatekeeper = emulator / "gatekeeper"
    api = re.compile(r"^ro\.vendor\.build\.version\.sdk=(\d+)$", re.M)
    target_api = api.findall((root / "build.prop").read_text())
    donor_api = api.findall((donor / "build.prop").read_text())
    if target_api != ["37"] or target_api != donor_api:
        raise ValueError(f"Security donor API mismatch: {donor_api} vs {target_api}")
    llndk = subprocess.check_output([
        "dump.erofs", "--path=/system/etc/llndk.libraries.txt", "--cat",
        str(google / "super/system_a.img"),
    ], text=True).splitlines()

    for name in (
        "android.hardware.gatekeeper-service.trusty",
        "android.hardware.security.secretkeeper.trusty",
        "android.hardware.security.secretkeeper.trusty.desktop",
        "android.hardware.weaver-service.android-desktop",
        "vendor.google.desktop.oemlock-service",
        "hal_desktop_charge_control_default",
    ):
        (root / f"etc/init/{name}.rc").unlink(missing_ok=True)
        (root / f"etc/vintf/manifest/{name}.xml").unlink(missing_ok=True)
    (root / "etc/vintf/manifest/com.android.desktop.power.charge_control.xml").unlink(missing_ok=True)
    (root / "apex/com.google.android.hardware.biometrics.face.apex").unlink(missing_ok=True)

    keymint = "android.hardware.security.keymint-service"
    keymint_binary = root / "bin/hw" / keymint
    install(donor / "bin/hw" / keymint, keymint_binary, "u:object_r:hal_keymint_default_exec:s0", True)
    install(donor / f"etc/init/{keymint}.rc", root / f"etc/init/{keymint}.rc", VENDOR_CONFIG)
    for name in ("keymint", "secureclock", "sharedsecret"):
        xml = f"android.hardware.security.{name}-service.xml"
        install(donor / "etc/vintf/manifest" / xml, root / "etc/vintf/manifest" / xml, VENDOR_CONFIG)

    gk_binary = root / "bin/hw/android.hardware.gatekeeper-service"
    install(gatekeeper / "bin/hw/android.hardware.gatekeeper-service.nonsecure",
            gk_binary, "u:object_r:hal_gatekeeper_default_exec:s0", True)
    install(HERE / "android/gatekeeper.rc", root / "etc/init/android.hardware.gatekeeper-service.rc", VENDOR_CONFIG)
    fragments = list((gatekeeper / "etc/vintf").glob("*.xml"))
    if not fragments:
        raise ValueError("Software Gatekeeper has no VINTF manifest")
    for fragment in fragments:
        install(fragment, root / "etc/vintf/manifest" / fragment.name, VENDOR_CONFIG)
    dependencies([keymint_binary, gk_binary], root,
                 [gatekeeper / "lib64", donor / "lib64"], set(llndk), VENDOR_FILE)

    mesa_lib = mesa / "install/lib64"
    graphics = []
    for name in ("libEGL_mesa.so", "libGLESv1_CM_mesa.so", "libGLESv2_mesa.so"):
        target = root / "lib64/egl" / name
        install(mesa_lib / name, target, SPHAL)
        graphics.append(target)
    install(mesa_lib / "libgallium_dri.so", root / "lib64/libgallium_dri.so", SPHAL)
    dependencies(graphics + [root / "lib64/libgallium_dri.so"], root, [mesa_lib], set(llndk), SPHAL)
    properties(root / "build.prop", HERE / "android/vendor.props")
    contexts = root / "etc/selinux/vendor_file_contexts"
    with contexts.open("a") as stream:
        stream.write("\n/dev/dri/card[0-9]+ u:object_r:gpu_device:s0\n")
        stream.write("/dev/dri/renderD[0-9]+ u:object_r:gpu_device:s0\n")

    # The VM cannot flash hardware. Also remove updaters so this developer image cannot
    # replace itself with Google's incompatible OTA; only our explicit build updates it.
    for name in ("flashrom", "futility", "vpd", "fwtool", "elogtool",
                 "fwupd-binder", "fwupd_blocking_update", "fwupdmgr",
                 "hw/vendor.google.desktop.futility-executor"):
        (root / "bin" / name).unlink(missing_ok=True)
    for name in ("futility-executor", "desktop_kernel_max_rollforward_boot", "fwupd"):
        (root / f"etc/init/{name}.rc").unlink(missing_ok=True)
    (root / "etc/vintf/manifest/vendor.google.desktop.futility-executor.xml").unlink(missing_ok=True)
    for name in ("usr/share/fwupd", "etc/fwupd"):
        if (root / name).exists():
            shutil.rmtree(root / name)
    # Preserve the existing firmware_tool_exec label and ownership.
    (root / "bin/crossystem").write_bytes(crossystem.read_bytes())


def system_ext(root):
    (root / "etc/init/desktop-trusty_security_vm_launcher.rc").unlink()
    remove_hals(root / "etc/vintf/manifest.xml", {
        "android.desktop.security.finger_guard",
        "android.hardware.security.keymint", "android.hardware.security.secureclock",
        "android.hardware.security.sharedsecret", "com.android.trusty.rust.KeyMintProvisioningService",
    })
    install(HERE / "android/dali-qemu.rc", root / "etc/init/zz-dali-qemu.rc",
            "u:object_r:system_file:s0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("partition", choices=["vendor", "system_ext", "system"])
    parser.add_argument("root", type=Path)
    parser.add_argument("emulator", type=Path)
    parser.add_argument("mesa", type=Path)
    parser.add_argument("google", type=Path)
    parser.add_argument("crossystem", type=Path)
    args = parser.parse_args()
    if "FAKEROOTKEY" not in os.environ:
        parser.error("Run under fakeroot; otherwise Android metadata would be lost")
    if args.partition == "vendor":
        vendor(args.root, args.emulator, args.mesa, args.google, args.crossystem)
    elif args.partition == "system_ext":
        system_ext(args.root)
    else:
        for service in ("update_engine", "timberslide"):
            (args.root / f"system/etc/init/{service}.rc").unlink()


if __name__ == "__main__":
    main()
