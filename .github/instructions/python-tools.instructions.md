---
description: "Use when writing or editing Python tools in tools/ or tests in tests/: standard library only, safety checks, unittest regression tests."
applyTo: ["tools/**/*.py", "tests/**/*.py"]
---
# Python tools and tests

- Python 3 standard library only; tools run in the builder container.
- Start with a module docstring: what the tool does and what it guarantees not to touch.
- Fail loudly with `raise SystemExit("what went wrong")`; no silent fallbacks or guessed defaults.
- Safety checks are features: refusing devices/symlinks, checking sizes and extents, reading back
  writes, comparing metadata. Never weaken one to make a build pass — find the real cause.
- Tests use `unittest` in `tests/test_*.py`, temporary directories and fake inputs — never real
  disks, devices or network. Run with `make test`.
- Every bug fixed in a tool gets a regression test (e.g. the `modules.dep` trailing-space test in
  [tests/test_android.py](../../tests/test_android.py)).
