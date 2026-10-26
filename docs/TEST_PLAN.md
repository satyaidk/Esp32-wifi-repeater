# Test plan

Status legend:

- **Pass** — executed, with the evidence named in the row.
- **Not run (requires hardware)** — needs an ESP32 board, phones/laptops or
  the home router. No board was attached when this plan was last executed
  (2026-10-23; the only serial ports present were Bluetooth links), so none of
  these have results yet. Fill in the result columns as you run them.

Never record a result you did not observe.

## 1. Build and host-side tests (no hardware)

| ID | Test | How | Expected | Status (2026-10-23) |
|--|--|--|--|--|
| T-01 | Firmware builds for the classic ESP32 | `python tools/repeater.py build` (ESP-IDF v5.5.4) | Exit 0, `CONFIG_IDF_TARGET="esp32"` in `build/sdkconfig.esp32` | **Pass** — see [BUILD_AND_FLASH.md](BUILD_AND_FLASH.md#measured-build-results) |
| T-02 | Patches apply to the pinned upstream on any OS | `python tools/repeater.py prepare --force` | 5 × `applied …`, staged files LF | **Pass** — Windows with `core.autocrlf=true`; Linux in CI host-tests job |
| T-03 | Build-time secrets validation | `python -m unittest discover -s tests -v` | All tests OK | **Pass** — 47 tests |
| T-04 | Device-side input validation (`input_validation.h`) | `python tests/host/run_host_tests.py` | `0 failures` | **Pass** — MSVC `/W4 /WX` |
| T-05 | Kconfig keeps symbols literal | ESP-IDF `kconfgen` on a defaults file with `$HOME`, `$(…)`, `${…}`, `#`, `%`, backtick, UTF-8 SSID | Values unchanged in `sdkconfig.h` | **Pass** (manual run, documented in BUILD_AND_FLASH.md) |
| T-06 | Image fits its OTA slot with headroom | `build/release/esp32/build_info.json` | < 95 % of 1536 KiB | **Pass** — 83.9 % |
| T-07 | Secret-bearing log strings removed | Search the app image for `VPN query => %s` and the `/config` `Found URL query => %s` site | Absent; `Config form submitted (%u bytes)` present | **Pass** (static check; runtime check is T-21) |
| T-08 | Flash command reaches the serial port | `python tools/repeater.py flash -p COM99` (port that does not exist) | esptool invoked with offsets 0x1000/0x8000/0xF000/0x20000, fails only at "Could not open COM99" | **Pass** |
| T-09 | Build refuses unsafe secrets | `check-secrets --file config/secrets.example` | Exit 2, placeholder errors | **Pass** |
| T-34 | Pinned component hashes verify on every OS | Build on Windows (`core.autocrlf=true`) and in the Linux CI container with the same `config/dependencies.lock` | No `downloaded component … is corrupted`; `hash_dir` of `esp_wireguard` = `d3845c88…` on both | **Pass** on Windows; Linux: pending the next CI run |
| T-35 | Build-time uplink and AP address compile in | `build --secrets <file with uplink + CONFIG_REPEATER_AP_IP="192.168.5.1">` in a separate `REPEATER_BUILD_DIR` | Values present in `sdkconfig.h` and the image; log line `Using build-time uplink SSID` present | **Pass** — see [BUILD_AND_FLASH.md](BUILD_AND_FLASH.md#validation-log) |
| T-36 | Compile-time guards of patch 0005 | `xtensa-esp32-elf-gcc -std=gnu17 -Werror=all` on the `_Static_assert`s with good and bad values | 3 valid cases compile; short uplink password, password without SSID, 32-byte SSID and malformed AP IP fail | **Pass** (7/7 cases) |

## 2. Single board on hardware

Prerequisites: board flashed with your own build, serial monitor open
(`python tools/repeater.py monitor -p COMx`), a phone and a laptop, access to
the home router. Record the board's serial log for every test.

| ID | Test | Steps | Expected | Result |
|--|--|--|--|--|
| T-10 | Flash and boot | `python tools/repeater.py flash -p COMx --erase --monitor` | Flash verifies; boot log shows `ESP32 NAT ROUTER` banner, `AP started`; no reset loop for 5 min | Not run (requires hardware) |
| T-11 | Setup AP is encrypted | Scan from a phone | SSID from `secrets.local`; security WPA2/WPA3; joining with a wrong password fails; joining with the right one succeeds | Not run (requires hardware) |
| T-12 | Setup UI requires login | Open `http://192.168.4.1` after joining | Login prompt; admin password works; AP password does not; serial log shows `First boot: router password initialised` once | Not run (requires hardware) |
| T-13 | UI not reachable from the home LAN | After T-14, from a PC on the home network open `http://<board STA IP>` | Connection refused/closed; serial log `HTTP connection rejected (interface not allowed …)` | Not run (requires hardware) |
| T-14 | Correct uplink credentials connect | Getting Started page: home SSID + password, new AP SSID/password, Save | Reboot; log `got ip:192.168.x.y`; `show status` shows `Uplink AP: connected (ch N, RSSI dBm)` | Not run (requires hardware) |
| T-15 | Wrong uplink password recovers | Enter a wrong uplink password | Log shows repeated `disconnected - retry` with backoff growing to 16000 ms; AP and UI stay reachable; fixing the password restores the uplink without reflashing | Not run (requires hardware) |
| T-16 | Client gets IP, gateway, DNS | Windows: `ipconfig /all`; Android/iOS: Wi-Fi details | IPv4 `192.168.4.x`, gateway `192.168.4.1`, DNS = home router's DNS (or `set_ap_dns` value) | Not run (requires hardware) |
| T-17 | DNS and internet through NAT | `nslookup example.com`, `ping -n 20 1.1.1.1`, `curl -I https://example.com`; throughput with a speed test or `iperf3 -c <server on home LAN>` | Name resolves; pings reply; HTTP 200/301; record Mbps down/up and median ping | Not run (requires hardware) |
| T-18 | Heap is stable | `heap` every 10 min during T-23 | Free heap does not trend down; record min free | Not run (requires hardware) |
| T-19 | Home router restart | Power-cycle the home router | Board logs disconnect, retries with backoff, reconnects by itself after the router is back; no reboot (unless `set_watchdog` is set); clients regain internet | Not run (requires hardware) |
| T-20 | Signal loss | Carry the board out of range for 2 min, then back | Same as T-19 | Not run (requires hardware) |
| T-21 | No secrets in logs | Save `/config` with new AP/uplink passwords while capturing the monitor log; search the log for each password | No password appears; only `Config form submitted (N bytes)` | Not run (requires hardware) |
| T-22 | Client limit | Connect clients one by one | 8 associate; a 9th is refused | Not run (requires hardware) |
| T-23 | Sustained traffic | 30 min video stream or `iperf3 -t 1800` | No disconnect or reboot; note throughput over time | Not run (requires hardware) |
| T-24 | Factory reset with BOOT | Hold BOOT 5 s | Log `BOOT button held … factory reset!`; board restarts with the build-time setup SSID, AP password and admin password | Not run (requires hardware) |
| T-25 | Factory reset from CLI | `factory_reset` | As T-24 | Not run (requires hardware) |
| T-26 | Input validation on device | `set_ap_ip garbage`, `set_ap_ip 192.168.4.255`, `set_ap MyAP 1234567` | Each prints `Invalid …` and changes nothing (`show config`). Optionally `set_ap MyAP ""` prints `AP will be open`: this really opens the AP after `restart`, so restore it at once with `set_ap <ssid> <password>` | Not run (requires hardware) |
| T-27 | 5 GHz-only network | `scan` near a 5 GHz-only network | Network is not listed | Not run (requires hardware) |
| T-37 | Build-time uplink on first boot | Set `CONFIG_REPEATER_UPLINK_SSID`/`_PASSWORD`, `flash --erase` | Log `Using build-time uplink SSID '…'` then `got ip:`; clients have internet without using the web page | Not run (requires hardware) |
| T-38 | Saved settings win over the file | After T-37, set another uplink on the Getting Started page; `restart` | Board uses the saved uplink; `show config` shows it. After a factory reset (T-24) it returns to the build-time uplink | Not run (requires hardware) |
| T-28 | Channel following | Change the home router's channel | Board's AP moves to the new channel (`show status`, phone Wi-Fi analyser) | Not run (requires hardware) |

## 3. Range and power

| ID | Test | Steps | Record | Result |
|--|--|--|--|--|
| T-29 | Range walk | Line of sight, board 1.5–2 m above ground, antenna end unobstructed. At 10 m steps to 100 m: phone RSSI of the board's AP, `show status` uplink RSSI, speed test, ping | Table of distance vs RSSI, Mbps, ping, loss | Not run (requires hardware) |
| T-30 | Battery supply | 18650 → TP4056 (with protection) → MT3608 set to 5.0 V (measured before connecting) → VIN | Voltage at VIN under load; any `Brownout detector was triggered` in the log during T-23 | Not run (requires hardware) |

Template for T-29:

| Distance (m) | Phone RSSI (dBm) | Board uplink RSSI (dBm) | Down (Mbps) | Up (Mbps) | Ping median (ms) | Loss (%) | Notes |
|--|--|--|--|--|--|--|--|
| 10 | | | | | | | |
| 20 | | | | | | | |

## 4. Two boards (only after section 2 passes)

| ID | Test | Expected | Result |
|--|--|--|--|
| T-31 | Chain: board 2 uplink = board 1 AP, board 2 AP on `192.168.5.1` ([TWO_BOARD_PLAN.md](TWO_BOARD_PLAN.md)) | Client on board 2 gets `192.168.5.x` and internet; record throughput vs single board | Not run (requires hardware) |
| T-32 | Chain without changing board 2's AP IP | Expected to fail (subnet clash); confirms the documented requirement | Not run (requires hardware) |
| T-33 | Star: both boards uplink to the home router | Both work independently | Not run (requires hardware) |
