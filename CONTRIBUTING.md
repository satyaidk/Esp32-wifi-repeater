# Contributing

Thank you for helping. This project is small and deliberately conservative:
it changes upstream firmware only through reviewed patches, and every claim in
the documentation must be backed by a measurement or a source.

## Ground rules

- Do not commit secrets. `config/secrets.local` and `build/` are git-ignored;
  keep it that way. CI fails if `config/secrets.local` is tracked.
- Do not edit `upstream/esp32_nat_router` or `build/src`. Upstream changes go
  into `patches/`.
- Do not add numbers to the docs that you did not measure. Mark untested
  behaviour as untested.
- Use only on networks you own or are authorised to use. Contributions that
  add deauthentication, password cracking or other offensive features will not
  be accepted.

## Development setup

Follow [docs/BUILD_AND_FLASH.md](docs/BUILD_AND_FLASH.md) sections 1–4. Then
check that everything passes before you change anything:

```powershell
python -m unittest discover -s tests -v
python tests\host\run_host_tests.py
python tools\repeater.py build
```

## Changing the firmware (adding or editing a patch)

Patches are `git format-patch` files applied in file-name order to the
pinned upstream commit. Work in a separate LF clone so line endings match:

```bash
# from the directory that contains this repository
git -c core.autocrlf=false clone esp32-wifi-repeater/upstream/esp32_nat_router upstream-work
cd upstream-work
git config core.autocrlf false
git checkout -b work 119e0a3d98a7c580a0fd119fde27d189cda25d39
git am ../esp32-wifi-repeater/patches/*.patch

# edit, then commit with a message that explains the defect and the fix
git commit -a

git format-patch --no-signature --zero-commit -o ../patches-new 119e0a3d98a7c580a0fd119fde27d189cda25d39
```

Copy the files from `patches-new` into `patches/`, keeping or choosing short
kebab-case names; only the numeric prefix order matters. To change an
existing patch, amend the matching commit (`git commit --fixup <sha>` then
`git rebase --autosquash 119e0a3`, which needs no editor on Git 2.44 or newer)
and regenerate all files.

Then run the full check above. If the patch changes behaviour, update
[docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (patch table),
[docs/TEST_PLAN.md](docs/TEST_PLAN.md) and the CHANGELOG.

## Updating upstream or ESP-IDF

1. `git -C upstream/esp32_nat_router fetch` and check out the new commit.
2. Update `UPSTREAM_COMMIT` and `UPSTREAM_VERSION` in `tools/repeater.py`.
3. Rebase the patches in an LF clone (`git am -3`), regenerate them.
4. Delete `config/dependencies.lock` if upstream's `main/idf_component.yml`
   changed; the next build records a new one. Review the diff.
5. For a new ESP-IDF, update `REQUIRED_IDF_VERSION`, the CI container tag and
   [ADR 0004](docs/adr/0004-pin-esp-idf-5-5-4.md).
6. Rebuild, rerun the tests, update
   [THIRD_PARTY_AND_BUILD_NOTES.md](THIRD_PARTY_AND_BUILD_NOTES.md) and
   [docs/BUILD_AND_FLASH.md](docs/BUILD_AND_FLASH.md#measured-build-results)
   with the new measurements, and stage the submodule pointer
   (`git add upstream/esp32_nat_router`).

## Tests

- Python: `tests/test_repeater_tool.py` (standard-library `unittest`).
- Host C: `tests/host/test_input_validation.c`; add a `CHECK(...)` per case.
- Hardware: add or update rows in [docs/TEST_PLAN.md](docs/TEST_PLAN.md) and
  record real results only.

## Pull requests

- One logical change per pull request, with a description of what changed,
  why, and how it was tested (see the PR template).
- Keep code comments explaining *why*, matching the surrounding style.
- Documentation changes are reviewed as carefully as code.
