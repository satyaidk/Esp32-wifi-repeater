# ADR 0004: Pin ESP-IDF v5.5.4 and build with idf.py

- Status: Accepted
- Date: 2026-10-23

## Context

Newer ESP-IDF patch releases exist (v5.5.5, v5.5.6 at the time of writing).
Upstream's own evidence for the version it builds with:

- the app descriptor of upstream's prebuilt `firmware_esp32/esp32_nat_router.bin`
  (v2.4.22) reports `idf v5.5.4`;
- upstream commit `5527364` is titled "IDF v5.5.4; optimized compile";
- `platformio.ini` states that multi-target builds use `idf.py` with
  IDF 5.5.4 and that the PlatformIO file is for IDE integration.

The WireGuard dependency is a fork named for IDF 5.5.x
(`martin-ger/esp_wireguard_idf_5.5.x`).

## Decision

- Require exactly ESP-IDF v5.5.4 (`REQUIRED_IDF_VERSION`); `repeater.py`
  reads `tools/cmake/version.cmake` from `IDF_PATH` and stops on a mismatch
  unless `--allow-idf-mismatch` is given.
- Build with `idf.py`, not PlatformIO, so there is one framework and one set
  of instructions.
- CI uses the official `espressif/idf:v5.5.4` container image.

## Consequences

- The firmware is built with the same SDK as upstream's tested binaries.
- Moving to a newer IDF is a deliberate change: bump the constant, rebuild,
  re-run the test plan.
