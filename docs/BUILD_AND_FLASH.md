# Build and flash

This guide installs the pinned toolchain, builds the firmware for the classic
ESP32 and flashes an ESP32 DevKit V1. Windows (PowerShell) is the primary
path; Linux/macOS differences are noted. It is the technical reference; for a
beginner walk-through including what to put in the secrets file, see
[FLASHING_GUIDE.md](FLASHING_GUIDE.md).

- [1. Install ESP-IDF v5.5.4](#1-install-esp-idf-v554)
- [2. Get the source](#2-get-the-source)
- [3. Create your setup credentials](#3-create-your-setup-credentials)
- [4. Build](#4-build)
- [5. Find the board's COM port](#5-find-the-boards-com-port)
- [6. Flash and monitor](#6-flash-and-monitor)
- [7. First setup and verifying both interfaces](#7-first-setup-and-verifying-both-interfaces)
- [Alternative: flash with esptool only](#alternative-flash-with-esptool-only)
- [Alternative: upstream web installer](#alternative-upstream-web-installer)
- [Measured build results](#measured-build-results)
- [Validation log](#validation-log)

## 1. Install ESP-IDF v5.5.4

Requirements: Git, Python 3.9 or newer, about 3 GB of free disk space for the
esp32-only toolchain. Install ESP-IDF to a path **without spaces**.

```powershell
mkdir C:\Users\$env:USERNAME\esp\v5.5.4
cd C:\Users\$env:USERNAME\esp\v5.5.4
git clone -b v5.5.4 --depth 1 --recursive --shallow-submodules https://github.com/espressif/esp-idf.git
cd esp-idf
.\install.ps1 esp32
```

`install.ps1 esp32` downloads only the classic-ESP32 toolchain into
`%USERPROFILE%\.espressif`. Every new terminal then needs:

```powershell
C:\Users\$env:USERNAME\esp\v5.5.4\esp-idf\export.ps1
```

Linux/macOS: `./install.sh esp32`, then `. ~/esp/v5.5.4/esp-idf/export.sh`.

## 2. Get the source

```powershell
git clone --recursive <this repository's URL> esp32-wifi-repeater
cd esp32-wifi-repeater
```

If you cloned without `--recursive`, the build tool initialises the
`upstream/esp32_nat_router` submodule itself on first use.

The repository path may contain spaces (this project was built from
`C:\Users\…\Desktop\wifi repeater`). If you ever hit a path problem, set
`REPEATER_BUILD_DIR` to a folder without spaces, e.g.
`$env:REPEATER_BUILD_DIR = "C:\esp-build\repeater"`.

## 3. Create your setup credentials

```powershell
python tools\repeater.py init-secrets
```

This writes `config\secrets.local` (git-ignored) with a setup SSID and two
random passwords; it does not print them. Open the file to read them, or edit
the values. Rules are listed in [`config/secrets.example`](../config/secrets.example).
Check the file at any time:

```powershell
python tools\repeater.py check-secrets
```

| Value | Used for | Required |
|--|--|--|
| `CONFIG_REPEATER_SETUP_AP_SSID` | Name of the network the board broadcasts | Yes |
| `CONFIG_REPEATER_SETUP_AP_PASSWORD` | Its WPA2/WPA3 passphrase | Yes |
| `CONFIG_REPEATER_ADMIN_PASSWORD` | Web UI login (`http://192.168.4.1`) | Yes |
| `CONFIG_REPEATER_UPLINK_SSID` / `CONFIG_REPEATER_UPLINK_PASSWORD` | Existing 2.4 GHz Wi-Fi to join on first boot (patch 0005) | No |
| `CONFIG_REPEATER_AP_IP` | The board's address; clients get the same /24 (default `192.168.4.1`) | No |

These are starting values: they apply when the board has no saved settings
(first boot, after `flash --erase`, after a factory reset). Values saved later
on the device win.

A second board uses its own file, e.g. `--secrets config/board2.local` on
`init-secrets`, `check-secrets`, `build` and `flash`. Name such files
`*.local`; the tool warns if a secrets file is not git-ignored.

## 4. Build

```powershell
python tools\repeater.py build
```

What happens ([ARCHITECTURE.md §9](ARCHITECTURE.md#9-build-architecture)):
secrets are validated, the pinned upstream commit is exported to
`build\src` and patched, the sdkconfig is regenerated if any input changed,
`idf.py build` runs for target `esp32`, and the images are copied to
`build\release\esp32` with `SHA256SUMS`, `build_info.json` and
`flash_command.txt`.

The images contain your setup passwords. Do not share `build\`.

Other commands: `python tools\repeater.py --help`.

## 5. Find the board's COM port

Plug the DevKit V1 in with a data-capable Micro-USB cable, then:

- Device Manager → *Ports (COM & LPT)* → *Silicon Labs CP210x USB to UART
  Bridge (COMx)*, or in PowerShell:

  ```powershell
  Get-CimInstance Win32_PnPEntity | Where-Object Name -match '\(COM\d+\)' | Select-Object Name
  ```

- Ports called *Standard Serial over Bluetooth link* are not the board.
- Windows 10/11 normally installs the CP210x driver automatically. Only if
  the port is missing or shows a warning icon, install the Silicon Labs
  CP210x VCP driver: <https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers>.

Linux: `/dev/ttyUSB0` (add yourself to the `dialout` group). macOS:
`/dev/cu.SLAB_USBtoUART` or `/dev/cu.usbserial-*`.

## 6. Flash and monitor

```powershell
python tools\repeater.py flash -p COM5 --erase --monitor
```

Replace `COM5` with your port. This runs `idf.py erase-flash flash monitor`
with the project's build directory and sdkconfig. `--erase` wipes the whole
flash first, including settings saved by earlier firmware, so the values from
your secrets file apply; leave it out to keep the board's saved settings when
updating. Flashing uses 460800 baud (ESP-IDF
default; lower with `-b 115200` if it is unreliable). The monitor runs at
**115200 baud**; exit with `Ctrl+]`.

**BOOT/EN procedure.** The DevKit V1 normally enters download mode
automatically. If the tool stops at `Connecting....`:

1. Press and hold **BOOT**.
2. Start the flash command (or, if it is already waiting, keep holding).
3. Release BOOT once `Writing at 0x…` appears.

If it still fails: hold BOOT, tap **EN** (reset), release BOOT, flash.

Open the monitor later without flashing:

```powershell
python tools\repeater.py monitor -p COM5
```

Erase everything (firmware and all settings) if you need a clean start:

```powershell
python tools\repeater.py erase-flash -p COM5 --yes
```

## 7. First setup and verifying both interfaces

1. On a phone or laptop, join the setup Wi-Fi (`CONFIG_REPEATER_SETUP_AP_SSID`
   / `CONFIG_REPEATER_SETUP_AP_PASSWORD`).
2. Open `http://192.168.4.1` (a captive-portal page may open by itself). Log
   in with `CONFIG_REPEATER_ADMIN_PASSWORD`.
3. **Getting Started:** choose your home network (2.4 GHz) and its password,
   and set the name and password of the network the board should broadcast
   from now on. Save; the board reboots.
4. Verify the **uplink (STA)** on the serial console:

   ```text
   show status
   ```

   Expect `Uplink AP: connected (ch N, -XX dBm)` and an STA IP from your home
   router.
5. Verify the **downlink (AP)** from a client joined to the new network:

   ```powershell
   ipconfig /all            # IPv4 192.168.4.x, gateway 192.168.4.1, DNS set
   nslookup example.com
   ping -n 10 1.1.1.1
   curl.exe -I https://example.com
   ```

6. Run the rest of [TEST_PLAN.md](TEST_PLAN.md) section 2 and record results.

## Alternative: flash with esptool only

`build\release\esp32\flash_command.txt` contains the exact command generated
from ESP-IDF's `flasher_args.json` for your build. For the build recorded
below it was:

```text
python -m esptool --chip esp32 -p <PORT> -b 460800 --before default_reset --after hard_reset write_flash --flash_mode dio --flash_freq 40m --flash_size 4MB 0x1000 bootloader.bin 0x8000 partition-table.bin 0xf000 ota_data_initial.bin 0x20000 esp32_nat_router.bin
```

Run it from `build\release\esp32` inside the ESP-IDF environment (esptool
v4.12.0 is bundled with v5.5.4). These offsets match upstream's documented
ESP32 layout.

## Alternative: upstream web installer

Upstream publishes a browser-based installer at
<https://martin-ger.github.io/esp32_nat_router/> (Web Serial; Chrome or Edge).
Its manifest (`manifest_esp32_wifi.json`, v2.4.22) has an `ESP32` entry that
flashes `firmware_esp32/*` at `0x1000`, `0x8000`, `0xF000` and `0x20000`, so
it targets the classic ESP32.

It installs **upstream's unpatched firmware**: an open `ESP32_NAT_Router` AP,
no web password, query strings with passwords in the log, and none of the
input validation. If you use it, immediately set an AP password and
`set_router_password` from the serial console, and prefer this project's
build for anything beyond a quick trial.

## Measured build results

Recorded on 2026-10-23 on Windows 11 Home (10.0.26300), building from
`C:\Users\nikad\Desktop\wifi repeater` (path with a space).

| Item | Value |
|--|--|
| Upstream | `martin-ger/esp32_nat_router` `119e0a3d98a7c580a0fd119fde27d189cda25d39` (v2.4.22) + patches 0001–0005 |
| ESP-IDF | v5.5.4, commit `735507283d5b2f9fb363a1901172dbd9e847945d` |
| Compiler | `xtensa-esp-elf-gcc` 14.2.0 (crosstool-NG `esp-14.2.0_20260121`) |
| Build tools | CMake 3.30.2, Ninja 1.12.1, ccache 4.12.1, esptool 4.12.0, esp-idf-kconfig 2.5.4, idf-component-manager 2.5.2, Python 3.11.0 |
| Managed components | `esp_wireguard` git `02a24fad29365db09e0088df2f8c4414632fe35a`, `espressif/mdns` 1.14.0, `espressif/led_strip` 3.1.1 ([`config/dependencies.lock`](../config/dependencies.lock)) |
| Target | `esp32` (`CONFIG_IDF_TARGET="esp32"`), DIO, 40 MHz, 4 MB flash |
| Result | `idf.py build` exit code 0 |
| App image | 1,319,904 bytes (0x1423e0) = 83.9 % of the 1,572,864-byte `ota_0` slot; ESP-IDF reports 0x3dc20 bytes (16 %) free (with patch 0005; 1,319,824 bytes before it) |
| Bootloader | 0x58d0 bytes; 0x1730 bytes (21 %) free |
| Build time, first build on this machine | 304 s (includes component downloads, cold compiler cache) |
| Build time, after `repeater.py clean` | 95 s (ccache warm) |
| Build time, nothing changed | 3 s |
| Build time, after a patch or lock change (re-export, ccache warm) | 157 s |
| Compiler warnings | 2, both in the third-party `esp_wireguard` component (see below); none in upstream code or the patches |

Image checksums differ between builds even from identical inputs: upstream's
`CMakeLists.txt` forces the app descriptor to recompile so that it carries
the current build date and time.

### Known third-party warnings

Neither is suppressed. WireGuard is compiled in but disabled at runtime
unless configured.

| Location | Warning | Assessment |
|--|--|--|
| `esp_wireguard/src/crypto/refc/x25519.c:218` | `'mul' reading 32 bytes from a region of size 4 [-Wstringop-overread]` | False positive: `mul()` declares `b` as a full field element but reads only `b[0..nb-1]`; here `nb = 1` and `a24` has one element. |
| `esp_wireguard/src/nacl/crypto_scalarmult/curve25519/ref/smult.c:140` | `unused variable 'i'` | Harmless. |

## Validation log

Commands executed for this project and their outcome (2026-10-23). Commands
that need a board were not run because none was connected.

| Command | Exit | Outcome |
|--|--|--|
| `git clone -b v5.5.4 --depth 1 --recursive --shallow-submodules https://github.com/espressif/esp-idf.git` | 0 | `git describe` → `v5.5.4`, 23 submodules |
| `.\install.ps1 esp32` | 0 | Tools installed |
| `python tools\repeater.py check-secrets --file config\secrets.example` | 2 | Rejected: placeholders (expected) |
| `python tools\repeater.py init-secrets`, `check-secrets` | 0 | Valid secrets file created |
| `python tools\repeater.py build` (first attempt, without patch 0004) | 2 | CMake error in upstream `components/mqtt_ha/CMakeLists.txt` with MQTT disabled → fixed by patch 0004 |
| `python tools\repeater.py build` (second attempt) | 1 | `PermissionError` deleting `build\src`: another shell had it as its working directory. The tool now reports this as a clear error instead of a traceback |
| `python tools\repeater.py clean` then `build` | 0 / 0 | Results above |
| `python tools\repeater.py build` (no changes) | 0 | 3 s, `upstream sources up to date` |
| `python tools\repeater.py flash -p COM99` (port that does not exist) | 2 | esptool invoked with the expected offsets; failed only at `Could not open COM99` (expected) |
| `python -m unittest discover -s tests -v` | 0 | 28 tests OK at first; 47 tests OK after patch 0005 and the lock fix |
| `python tests\host\run_host_tests.py` | 0 | MSVC `/W4 /WX`: 47 checks, 0 failures |
| ESP-IDF `kconfgen` with `$HOME`, `$(…)`, `${…}`, `#`, `%`, backtick, UTF-8 in values | 0 | Values copied literally to `sdkconfig` and `sdkconfig.h` |
| `xtensa-esp32-elf-gcc -std=gnu17 -Wall -Werror=all` on a literal containing `??(` | 1 | `-Werror=trigraphs` → validator now rejects trigraphs |
| GitHub Actions run `39858092916` (firmware job, Linux container) | 2 | `The downloaded component "esp_wireguard" is corrupted`: the lock held the hash of a Windows CRLF checkout (`d6a3aefc…`) |
| `hash_dir` (idf-component-manager) on a CRLF and an LF checkout of `esp_wireguard` `02a24fad` | 0 | `d6a3aefc…` (CRLF) vs `d3845c88…` (LF): cause confirmed |
| `python tools
epeater.py build` with LF-forced git and the LF hash in the lock (Windows) | 0 | Component verified; files on disk LF; `hash_dir` = `d3845c88…` |
| `python toolsepeater.py build --secrets <test file>` with uplink `Example Home WiFi` and `CONFIG_REPEATER_AP_IP="192.168.5.1"` (separate `REPEATER_BUILD_DIR`) | 0 | Values in `sdkconfig.h` and the image (1,319,952 bytes); `192.168.4.1` remains only in display text (an error-message example and two form placeholders) |
| `xtensa-esp32-elf-gcc -std=gnu17 -Werror=all` on patch 0005's `_Static_assert`s | 0/1 | 3 valid cases compile, 4 invalid ones fail with their message |
| Hardware flashing, first boot, routing, reconnect, factory reset | — | **Not run: no ESP32 connected** |
