# Hardware support

Start with the [recipe guide](../docs/build-guide.md#hardware-recipes).

## Where does my change belong?

| Change | Location |
|---|---|
| Only kernel options, without extra files | [Shared kernel config](../kernel/gki.config), grouped with a short reason |
| Reusable driver support needing patches, firmware, module packaging or tests | A recipe under [drivers/](drivers/) |
| Laptop-specific settings or quirks | A device recipe, such as [Lenovo](lenovo-e50-80/) or [MSI](msi-modern-15-b7m/) |

Simple kernel options do not need their own driver directory. A dedicated driver recipe does
not require source patches: firmware or module packaging can justify one too.

[drivers.list](drivers.list) and [devices.list](devices.list) select the combined image's
recipes. Shared kernel options apply to every build. Adding a recipe also requires its native
fragments to be wired into the appropriate base lists; follow the guide rather than copying
an entire laptop's configuration.

Put recipe-specific tests and fixtures in that recipe's `tests/` directory. `make hardware-check`
checks declarations; `make test` runs generic tests and all recipe tests, including unselected
recipes. Neither proves that hardware works: record physical results and limitations separately.
