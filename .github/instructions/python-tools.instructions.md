---
description: "Use when writing Python tools, generic tests or hardware recipe tests: standard library only, safety checks, unittest regression tests."
applyTo: ["tools/**/*.py", "tests/**/*.py", "hardware/**/tests/**/*.py"]
---
# Python tools and tests

- Python 3 standard library only; tools run in the builder container.
- Use four-space indentation and descriptive `snake_case` names. Prefer ordinary loops and small,
  focused functions over nested comprehensions or clever abstractions.
- Start with a module docstring: what the tool does and what it guarantees not to touch.
- Fail loudly with `raise SystemExit("what went wrong")`; no silent fallbacks or guessed defaults.
- Safety checks are features: refusing devices/symlinks, checking sizes and extents, reading back
  writes, comparing metadata. Never weaken one to make a build pass — find the real cause.
- Tests use `unittest`, temporary directories and fake inputs — never real disks, devices or
  network. Generic tests live in `tests/test_*.py`; hardware-specific tests and fixtures live
  in the owning recipe's `tests/`. Shared fixture helpers stay in `tests/recipe_support.py`.
  `make test` runs generic tests and all recipes, including unselected ones. For a focused run,
  use `scripts/builder.sh python3 tools/run_tests.py <test-file-or-directory> [...]`.
- Every bug fixed in a tool gets a regression test (e.g. the `modules.dep` trailing-space test in
  [tests/test_overlay.py](../../tests/test_overlay.py)).
- Python never writes changes into Google's image: those are lists and `.patch` files under
  `android/<target>/` or explicitly selected [hardware recipes](../../hardware/)
  (see [scripts/android-overlay.sh](../../scripts/android-overlay.sh)).
