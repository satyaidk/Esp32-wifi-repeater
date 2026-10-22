# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Reproducible build of upstream `martin-ger/esp32_nat_router` v2.4.22
  (commit `119e0a3`) for the classic ESP32 with ESP-IDF v5.5.4, via
  `tools/repeater.py` (`init-secrets`, `check-secrets`, `prepare`, `build`,
  `flash`, `monitor`, `erase-flash`, `info`, `clean`).
- Patch 0001: WPA2/WPA3 setup AP and admin password from build-time values;
  web UI restricted to the AP side on first boot; build fails without valid
  credentials.
- Patch 0002: no Wi-Fi passwords or WireGuard keys in the `/config` and `/vpn`
  request logs.
- Patch 0003: validation of SSIDs, AP passphrases and the AP IP address in
  the CLI and web UI.
- Patch 0004: upstream MQTT component configures when compiled out.
- Pinned managed component versions (`config/dependencies.lock`).
- Python unit and staging integration tests; host C tests for input
  validation; GitHub Actions workflow.
- Documentation: architecture and ADRs, build and flash guide, test plan,
  troubleshooting, range and power notes, two-board plan, learning path,
  third-party notes.

- Patch 0005: optional build-time uplink (`CONFIG_REPEATER_UPLINK_SSID`,
  `CONFIG_REPEATER_UPLINK_PASSWORD`) and AP address (`CONFIG_REPEATER_AP_IP`)
  in the secrets file; settings saved on the device still take precedence.
- `--secrets FILE` on every command (one secrets file per board) and
  `flash --erase`; a warning when a secrets file is not git-ignored.
- `docs/FLASHING_GUIDE.md`: step-by-step flashing, where to put Wi-Fi details,
  what can be customised, and a second repeater.

### Fixed

- Firmware CI job failed with `The downloaded component "esp_wireguard" is
  corrupted`: the pinned component hash had been recorded from a Windows
  checkout with CRLF line endings. `repeater.py` now forces LF checkouts for
  the ESP-IDF component manager and the lock holds the LF hash, so the same
  lock verifies on Windows and Linux.
- GitHub Actions moved to Node 24 majors (`checkout@v7`, `setup-python@v7`,
  `upload-artifact@v7`); Node 20 is deprecated on GitHub runners.
- CI could not find upstream commit `119e0a3`: `upstream/esp32_nat_router`
  had been committed as ordinary files instead of a submodule. It is a pinned
  submodule again, `repeater.py` now detects this layout and prints the
  repair commands, and tests guard the submodule pointer.

### Not yet verified

- No hardware test has been run (see `docs/TEST_PLAN.md`).
