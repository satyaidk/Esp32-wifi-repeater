# Third-party components and build notes

Research date: **2026-10-23**. All facts below were checked against the
sources listed on that date, mostly by reading the source code itself.

## Upstream firmware

| | |
|--|--|
| Project | ESP32 NAT Router by Martin Ger |
| Repository | <https://github.com/martin-ger/esp32_nat_router> |
| Pinned commit | `119e0a3d98a7c580a0fd119fde27d189cda25d39` (2026-10-21, "firmware build for lastest changes"), app version 2.4.22 |
| How it is used | Git submodule at `upstream/esp32_nat_router`; exported and patched into `build/src` at build time. Not copied into this repository. |
| README | <https://github.com/martin-ger/esp32_nat_router/blob/master/README.md> |
| Wiki | <https://github.com/martin-ger/esp32_nat_router/wiki> (cloned at commit `b79e1e3`, 2026-10-21) — pages *Building*, *Installation*, *Hardware*, *Security*, *CLI Reference* were read |
| Release tags | None. Upstream ships prebuilt binaries in `firmware_*` directories instead. |

### Upstream licensing

GitHub reports **no repository-level license** for upstream, and there is no
LICENSE file in the tree. Individual files declare:

| Files | License |
|--|--|
| Most headers in `include/`, `main/led_strip_status.c`, `components/mqtt_ha/mqtt_ha.c` | `SPDX-License-Identifier: MIT` |
| `components/dhcpserver/dhcpserver.c` | Apache-2.0, © 2015-2025 Espressif Systems |
| `components/cmd_system/cmd_system.c` | Public Domain / CC0 (ESP-IDF example code) |
| WireGuard component (see below) | BSD-3-Clause (notice reproduced in upstream README) |
| `main/esp32_nat_router.c` and several other sources | No license header |

Because of this, this repository does not redistribute upstream source. Files
in this repository are original work under the MIT License (see `LICENSE`),
including the patches in `patches/`. A compiled firmware image contains
upstream code; the images built here also contain your setup passwords and
must not be published anyway.

### Upstream branches reviewed

| Branch | Head reviewed | Notes |
|--|--|--|
| `master` | `119e0a3` | Selected (NAT router) |
| `esp32_wifi_repeater` | `cec6ebe` (2026-10-16, v2.4.12) | Layer-2 bridge, "still under development" per its README; reviewed, not built |
| `WT32-ETH01` | not reviewed | Ethernet board variant, not applicable |

## Toolchain

| Component | Version | Source |
|--|--|--|
| ESP-IDF | **v5.5.4**, commit `735507283d5b2f9fb363a1901172dbd9e847945d` | <https://github.com/espressif/esp-idf> |
| Why v5.5.4 | Upstream's prebuilt `firmware_esp32/esp32_nat_router.bin` app descriptor reports `idf v5.5.4`; upstream commit `5527364` "IDF v5.5.4; optimized compile"; `platformio.ini` comment "Multi-target builds use idf.py … (IDF 5.5.4)". v5.5.5 and v5.5.6 exist but are not what upstream tested. | |
| Compiler | xtensa-esp-elf GCC 14.2.0 (`esp-14.2.0_20260121`) | installed by `install.ps1 esp32` |
| CMake / Ninja / ccache | 3.30.2 / 1.12.1 / 4.12.1 | installed by ESP-IDF |
| esptool | 4.12.0 (bundled) | <https://github.com/espressif/esptool> |
| esp-idf-kconfig / idf-component-manager | 2.5.4 / 2.5.2 | ESP-IDF Python environment |
| CI image | `espressif/idf:v5.5.4` (Docker Hub tag verified to exist) | <https://hub.docker.com/r/espressif/idf> |

## Managed components (pinned in `config/dependencies.lock`)

| Component | Version | Source | License |
|--|--|--|--|
| `esp_wireguard` | git `02a24fad29365db09e0088df2f8c4414632fe35a` | <https://github.com/martin-ger/esp_wireguard_idf_5.5.x> (fork of Kenta Ida's `esp_wireguard`) | BSD-3-Clause (© 2021 Kenta Ida, © 2021 Daniel Hope) |
| `espressif/mdns` | 1.14.0 | <https://components.espressif.com/components/espressif/mdns> | Apache-2.0 (Espressif) |
| `espressif/led_strip` | 3.1.1 | <https://components.espressif.com/components/espressif/led_strip> | Apache-2.0 (Espressif) |

The `component_hash` of `esp_wireguard` in the lock (`d3845c88…`) is the hash
of an LF checkout, computed with idf-component-manager's own `hash_dir`. A CRLF
checkout (Git for Windows default) hashes to `d6a3aefc…` and fails
verification, which is why `repeater.py` forces `core.autocrlf=false` for the
git processes ESP-IDF starts.

Licenses were read from the `LICENSE` file of each downloaded component
(`build/src/managed_components/*/LICENSE`); `esp_wireguard` also declares
`license: BSD-3-Clause` in its `idf_component.yml`.

## Espressif documentation used

| Topic | Source |
|--|--|
| AP+STA channel priority: "the channel of the external AP … has higher priority over the ESP AP channel" | ESP-IDF v5.5.4 `docs/en/api-guides/wifi.rst` (`WIFI_MODE_APSTA`) |
| Country code policy in AP+STA mode | same file, country/region table |
| RNG is only pseudo-random until Wi-Fi is started (why patch 0001 runs after `wifi_init`) | ESP-IDF v5.5.4 `docs/en/api-reference/system/random.rst` |
| Wi-Fi API reference | <https://docs.espressif.com/projects/esp-idf/en/latest/esp32/api-reference/network/esp_wifi.html> |
| Power supply ≥ 500 mA at 3.3 V; GPIO0/GPIO2 strapping | <https://docs.espressif.com/projects/esp-hardware-design-guidelines/en/latest/esp32/schematic-checklist.html> |

## Facts verified in upstream source (not taken from documentation)

| Fact | Location |
|--|--|
| Default AP SSID `ESP32_NAT_Router`, empty password → `WIFI_AUTH_OPEN` | `main/esp32_nat_router.c` `app_main`, `wifi_init` |
| AP IP default `192.168.4.1`, netmask always /24 | `include/wifi_config.h`, `wifi_init` |
| AP channel 0 (auto) in AP+STA builds; `set_ap_channel` only with Ethernet uplink | `wifi_init`, CLI help |
| Reconnect backoff 250 ms doubling to 16 s, no reboot unless `set_watchdog` | `STA_RECONNECT_*`, `led_status_thread` |
| Factory reset: BOOT (GPIO0 on ESP32) held 5 s erases NVS namespace `esp32_nat` | `led_status_thread`, `FACTORY_RESET_HOLD_MS 5000`. Note: the wiki *Installation* page says 10 s; source and wiki *Hardware* page say 5 s. |
| Max AP clients 8 on ESP32 | `include/router_config.h` `AP_MAX_CONNECTIONS` |
| Web password stored as salted SHA-256; clearing stores `""` | `components/cmd_router/cmd_router.c` |
| Web UI bound to AP+STA+VPN by default | `components/http_server/http_server.c` `s_web_bind` |
| `/config` and `/vpn` logged raw query strings | `http_server.c` (fixed by patch 0002) |
| Getting Started page resets the AP IP to `192.168.4.1` | `http_server.c` `setup_get_handler` |
| `set_ap_ip` stored unvalidated input; `<8` char AP password → open AP; SSIDs truncated to 31 bytes by `strlcpy` | `cmd_router.c`, `wifi_init` (fixed by patch 0003) |
| `CONFIG_MQTT_HOMEASSISTANT=n` broke CMake configure | `components/mqtt_ha/CMakeLists.txt` (fixed by patch 0004) |
| Console 115200 baud | `CONFIG_ESP_CONSOLE_UART_BAUDRATE` in the generated sdkconfig |

## Not verified

- **Silicon Labs CP210x driver page**
  (<https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers>)
  returned HTTP 403 to automated fetching; the URL is the vendor's long-standing
  driver page but its current contents were not checked.
- **All runtime behaviour on hardware.** No ESP32 was connected during this
  work. Behaviour described in the docs comes from source review and
  compilation, not from a running device.
- The `esp32_wifi_repeater` branch was not built.
- Upstream's throughput figure (5–15 Mbps) is upstream's statement and was not
  reproduced.
