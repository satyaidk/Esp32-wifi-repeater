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

### Not yet verified

- No hardware test has been run (see `docs/TEST_PLAN.md`).
