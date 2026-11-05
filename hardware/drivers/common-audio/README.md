# Common audio: build-checked, hardware untested

Reuse Google's existing HDA controller and codec modules, dependencies and discovery aliases.
These include Realtek, Conexant, IDT, VIA, Analog Devices, Cirrus and Creative codecs.
The existing laptop integration already removes Google's `snd_hda_intel` blocklist entry.
No replacement driver or additional global mixer/HAL policy is necessary for inclusion.

This recipe supplies unchanged `ctefx.bin` and its license from the pinned linux-firmware
archive for Google's existing `snd-hda-codec-ca0132` module. Its firmware declarations request
this file; the pinned upstream CA0132 source uses it as the default/fallback DSP image.
Alternative `ctefx-desktop.bin` / `ctefx-r3di.bin` are absent from this archive and not supplied.
Do not treat this as verified coverage of those variants.

Google also includes Intel SOF controller drivers and some newer IPC4 firmware/topologies.
That is not complete firmware/topology coverage for every Intel generation. Broadening SOF
needs a suitable pinned official firmware distribution and exact platform/topology matching;
this recipe does not add guessed topology files or switch DSP driver selection.

## Laptop configuration

Driver availability is not working Android sound. Users can supply model-specific ALSA
mixer settings and Android HAL routes through existing device recipes; follow
[the recipe guide](../../../docs/build-guide.md#hardware-recipes) and the existing
[MSI](../../msi-modern-15-b7m/) / [Lenovo](../../lenovo-e50-80/) examples.
Match the laptop model and codec/card identity, never an unstable ALSA card number.
Record speaker, headphone and microphone results separately.

No automatic card renaming, amplifier programming, routing, SELinux changes or firmware
updates are added for unknown laptops. Existing tested MSI/Lenovo paths stay unchanged.
New coverage is **build-checked; hardware untested**, not functional audio support.

66 combined focused tests pass, including synthetic audio firmware extraction/refusals and
repeat timestamps. The combined image passes packaging/read-back and fit checks; normal and
diagnostic QEMU reach setup with enforcing SELinux. QEMU has no emulated sound card, so this
does not validate audio. [Evidence](../../../out/common-hardware-validation/).
