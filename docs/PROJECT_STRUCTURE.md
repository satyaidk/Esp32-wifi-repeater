# Project folder and file structure

This page is a map of the repository: what each top-level folder contains,
where the main files live, and which files are generated locally. The
upstream firmware is included as a pinned Git submodule and is not edited
directly.

```text
.
├── .github/
│   ├── ISSUE_TEMPLATE/
│   │   ├── bug_report.yml
│   │   ├── config.yml
│   │   └── feature_request.yml
│   ├── workflows/
│   │   └── ci.yml
│   └── PULL_REQUEST_TEMPLATE.md
├── config/
│   ├── dependencies.lock           # Pinned ESP-IDF component versions and hashes
│   ├── sdkconfig.defaults.repeater  # Repeater-specific ESP-IDF configuration
│   ├── secrets.example             # Safe template for local configuration
│   └── secrets.local               # Local credentials; generated and git-ignored
├── docs/
│   ├── adr/                        # Architecture decision records
│   │   ├── 0001-nat-router-over-layer2-bridge.md
│   │   ├── 0002-upstream-submodule-with-patch-queue.md
│   │   ├── 0003-build-time-setup-credentials.md
│   │   ├── 0004-pin-esp-idf-5-5-4.md
│   │   └── 0005-minimal-feature-set.md
│   ├── assets/
│   │   └── logo.svg
│   ├── ARCHITECTURE.md             # System design, packet path, build pipeline
│   ├── BUILD_AND_FLASH.md          # Toolchain, build and flashing reference
│   ├── FLASHING_GUIDE.md           # Beginner step-by-step setup guide
│   ├── LEARNING_PATH.md            # Guided introduction to the project
│   ├── PROJECT_STRUCTURE.md        # This repository map
│   ├── RANGE_AND_POWER.md          # Range expectations and power options
│   ├── TEST_PLAN.md                # Host and hardware verification plan
│   ├── TROUBLESHOOTING.md          # Common build and device issues
│   └── TWO_BOARD_PLAN.md           # Configuration for a second repeater
├── patches/                        # Ordered changes applied to upstream at build time
│   ├── 0001-secure-first-boot-defaults.patch
│   ├── 0002-redact-credentials-in-web-logs.patch
│   ├── 0003-validate-ssid-passphrase-ap-ip.patch
│   ├── 0004-fix-mqtt-disabled-build.patch
│   └── 0005-build-time-uplink-and-ap-ip.patch
├── tests/
│   ├── host/
│   │   ├── run_host_tests.py       # Compile and run host-side C tests
│   │   └── test_input_validation.c # Firmware input-validation tests
│   └── test_repeater_tool.py       # Python tool unit and staging tests
├── tools/
│   └── repeater.py                 # Build, flash, monitor and secrets commands
├── upstream/
│   └── esp32_nat_router/            # Pinned upstream Git submodule; do not edit
│       ├── components/              # Router services and UI components
│       │   ├── acl/
│       │   ├── cmd_router/
│       │   ├── cmd_system/
│       │   ├── dhcpserver/
│       │   ├── http_server/
│       │   │   └── pages/           # Embedded web UI pages
│       │   ├── mqtt_ha/
│       │   ├── oled_display/
│       │   ├── pcap_capture/
│       │   ├── remote_console/
│       │   └── syslog/
│       ├── firmware_esp32/          # Upstream prebuilt firmware metadata
│       ├── firmware_esp32_poe_iso/
│       ├── firmware_esp32c3/
│       ├── firmware_esp32c5/
│       ├── firmware_esp32c6/
│       ├── firmware_esp32s3/
│       ├── firmware_wt32_eth01/
│       ├── include/                 # Shared firmware headers
│       ├── main/                    # Main application and network managers
│       ├── CMakeLists.txt
│       ├── README.md
│       ├── index.html
│       ├── platformio.ini
│       ├── sdkconfig.defaults       # Upstream ESP-IDF defaults
│       └── ...                      # Target defaults, manifests and build files
├── .gitattributes                   # Repository line-ending rules
├── .gitignore                       # Ignores secrets, build output and test binaries
├── .gitmodules                      # Upstream submodule declaration
├── CHANGELOG.md
├── CODE_OF_CONDUCT.md
├── CONTRIBUTING.md
├── LICENSE
├── README.md                        # Project overview and quick start
├── SECURITY.md
└── THIRD_PARTY_AND_BUILD_NOTES.md   # Upstream sources, versions and licenses
```

## What is generated locally

`config/secrets.local` is created by `python tools/repeater.py init-secrets`.
It contains credentials and is ignored by Git. The optional
`config/board2.local` follows the same `*.local` ignore rule.

The `build/` directory is also ignored. The build tool recreates it with the
staged upstream source (`build/src/`), ESP-IDF configuration and intermediate
files, and release images under `build/release/esp32/`. Release images embed
the configured setup credentials, so do not share the build directory.

Host test runs may create binaries under `tests/host/`; those are ignored as
well. The upstream folder is a submodule pinned by Git. Local changes should
be made as repository patches in `patches/`, rather than edits to the
submodule working tree.

## Where to start

- Start with [`README.md`](../README.md) for the overview and quick start.
- Use [`FLASHING_GUIDE.md`](FLASHING_GUIDE.md) for first-time setup.
- See [`ARCHITECTURE.md`](ARCHITECTURE.md) for firmware and build design.
- See [`BUILD_AND_FLASH.md`](BUILD_AND_FLASH.md) for toolchain and commands.
