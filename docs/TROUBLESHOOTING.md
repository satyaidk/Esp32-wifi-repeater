# Troubleshooting

Start every investigation with the serial log: `python tools/repeater.py
monitor -p COMx` (115200 baud, exit with `Ctrl+]`). Most problems name
themselves there. Useful console commands: `show status`, `show config`,
`heap`, `scan`, `help`.

- [Build problems](#build-problems)
- [Board not showing as a COM port](#board-not-showing-as-a-com-port)
- [Flashing fails](#flashing-fails)
- [Setup AP not visible](#setup-ap-not-visible)
- [Cannot log in to the web UI](#cannot-log-in-to-the-web-ui)
- [Uplink does not connect](#uplink-does-not-connect)
- [5 GHz-only home network](#5-ghz-only-home-network)
- [Connected but no internet](#connected-but-no-internet)
- [DHCP, DNS or NAT problems](#dhcp-dns-or-nat-problems)
- [Weak signal and interference](#weak-signal-and-interference)
- [Reboot loop, low heap, too many clients](#reboot-loop-low-heap-too-many-clients)
- [Unstable power or overheating](#unstable-power-or-overheating)

## Build problems

| Message | Cause and fix |
|--|--|
| `IDF_PATH is not set` | Run ESP-IDF's export script in this terminal first: `C:\Users\<you>\esp\v5.5.4\esp-idf\export.ps1`. |
| `ESP-IDF x.y.z is active but this project is pinned to 5.5.4` | Another IDF is exported. Open a new terminal and export v5.5.4. |
| `config/secrets.local not found` | `python tools/repeater.py init-secrets`, or copy `config/secrets.example`. |
| `config/secrets.local is invalid` | The message lists each rule that failed (length, placeholder, quote/backslash, trigraph `??(`, admin = AP password, too many symbols for the login field). |
| `… must be 8-63 characters` from the C compiler (`_Static_assert`) | Someone bypassed `repeater.py` and ran `idf.py` directly without secrets. Use `repeater.py build`. |
| `… does not apply to upstream …` | A patch no longer matches the pinned commit, usually after moving the submodule. See CONTRIBUTING.md. |
| `cannot delete …\build\src` | A terminal, editor or serial monitor has that folder or a file in it open. Close it and retry. |
| `upstream commit … is not available` | `git submodule update --init --recursive`. |
| `upstream/esp32_nat_router is tracked as ordinary files, not as a git submodule` | The project's `.git` folder was recreated (deleted and re-initialised, or created by a GUI), so `git add` committed upstream as plain files and CI cannot find the pinned commit. Run the commands printed with the error, then commit. Avoid deleting `.git`: it also holds the submodule's repository (`.git/modules`). |

## Board not showing as a COM port

1. Use a data-capable Micro-USB cable. Many cables are charge-only; if
   Windows makes no connect sound and Device Manager does not change, try
   another cable.
2. Open Device Manager → *Ports (COM & LPT)*. The DevKit V1 appears as
   *Silicon Labs CP210x USB to UART Bridge (COMx)*. In PowerShell:

   ```powershell
   Get-CimInstance Win32_PnPEntity | Where-Object Name -match '\(COM\d+\)' | Select-Object Name
   ```

   Ports named *Standard Serial over Bluetooth link* are not the board.
3. If the device appears with a warning icon or under *Other devices* as
   *CP2102 USB to UART Bridge Controller*, install the Silicon Labs CP210x VCP
   driver from <https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers>
   and replug. Windows 10/11 usually installs it automatically, so only do
   this if the port is missing.
4. Some DevKit clones use a CH340 instead of a CP2102; check the chip next to
   the USB connector. Then you need the CH340 driver instead.

## Flashing fails

| Symptom | Fix |
|--|--|
| `Could not open COMx, the port is busy or doesn't exist` | Wrong port number, or another program (serial monitor, Arduino IDE, PuTTY) holds the port. Close it. |
| `Failed to connect to ESP32: No serial data received` / stuck at `Connecting....` | Auto-reset did not enter download mode. Hold **BOOT**, start the flash command, release BOOT when `Writing at 0x…` appears. If that fails: hold BOOT, tap **EN**, release BOOT, then flash. |
| Flash starts but fails midway | Try a slower baud rate: `python tools/repeater.py flash -p COMx -b 115200`. Use a short cable and a USB port directly on the PC. |
| `A fatal error occurred: … chip is ESP32-S3/C3` | Wrong board. This project targets the classic ESP32 only. |
| Board boots the old firmware | NVS settings survive reflashing by design. To start over: hold BOOT for 5 s, or `python tools/repeater.py erase-flash -p COMx --yes` (erases everything) and flash again. |

## Setup AP not visible

- Check the boot log for `AP started`. If the log shows a reset loop, see
  [Reboot loop](#reboot-loop-low-heap-too-many-clients).
- The setup SSID is the one in your `config/secrets.local`, not upstream's
  `ESP32_NAT_Router`.
- The AP is 2.4 GHz only. Some phones hide 2.4 GHz networks in power-saving
  modes; laptops with 5 GHz-only adapters cannot see it.
- After setup, the AP has the SSID you chose on the Getting Started page; a
  hidden SSID (`set_ap_hidden`) is not broadcast.
- The AP always runs on the uplink's channel. Channels 12–13 are not legal or
  not scanned in some countries; set the country with `set_wifi_country <CC>`.

## Cannot log in to the web UI

- The login is the **admin** password from `config/secrets.local`, not the
  Wi-Fi password.
- Forgot it: on the serial console run `set_router_password <new>`, or factory
  reset (hold BOOT 5 s), which restores the build-time password.
- `http://192.168.4.1` does not load from the home network: by design the UI
  answers only on the AP side. To also allow the home network side, run
  `web_ui bind all` on the serial console.
- After changing the AP IP, the UI moves to that address.

## Uplink does not connect

Look for `disconnected - retry to connect to the AP` followed by `scheduling
STA reconnect in N ms` (N grows to 16000). The AP and UI stay usable meanwhile.

- **Wrong password:** fix it on the Getting Started page or with
  `set_sta <ssid> <password>` and `restart`. Passwords are case-sensitive.
- **SSID longer than 31 bytes:** not supported (the firmware rejects it).
- **64-character hex PSK:** not supported; use the passphrase instead.
- **WPA3-only or WPA2-Enterprise networks:** WPA3 needs a matching
  configuration on the router; Enterprise needs the `-u`/`-e` options of
  `set_sta` (see `help set_sta`).
- **Out of range:** `scan` shows the network's RSSI from the board's position.

## 5 GHz-only home network

The ESP-WROOM-32 has a 2.4 GHz radio only. A network that `scan` does not list
is likely 5 GHz-only. Enable the 2.4 GHz band on the router (it may be under
"band steering" or "smart connect"; a separate 2.4 GHz SSID is the most
reliable option).

## Connected but no internet

1. `show status` on the board: is the uplink connected and does it have an
   IP? If not, see [Uplink does not connect](#uplink-does-not-connect).
2. On the board, `ping 1.1.1.1` and `ping example.com`. If the first fails,
   the home network has no internet or blocks the board (MAC filtering,
   captive portal, client isolation).
3. **Subnet clash:** if the home network uses `192.168.4.x`, the board's AP
   subnet collides with it. Fix: `set_ap_ip 192.168.5.1`, then `restart`, and
   reconnect clients. (This also clears DHCP reservations and port mappings.)
4. On the client, check that the gateway is `192.168.4.1` and DNS is set
   (`ipconfig /all`). If the client has a manual IP or DNS, remove it.
5. Some phones report "no internet" when their connectivity check is slow;
   try opening a website anyway.

## DHCP, DNS or NAT problems

| Symptom | Check |
|--|--|
| Client gets `169.254.x.x` | DHCP failed: too many clients (max 8), or the client was blocked (`dhcp_reserve` with `0.0.0.0`, or `set_ap_known_only on`). |
| IP works, names do not resolve | `show config` → `DNS Server` under the AP section (`(upstream)` by default). Set a public resolver: `set_ap_dns 1.1.1.1`, `restart`. |
| DNS shows `192.168.4.1` and every site opens the setup page | No uplink is configured; the captive-portal DNS is active. Finish setup. |
| Nothing routes although the uplink is up | `set_ap_nat` without arguments must print `NAT: enabled`; if not, `set_ap_nat on` and `restart`. Routed mode (`off`) needs static routes on the home router. |
| Devices on the home LAN cannot reach a downstream device | Expected with NAT. Add a mapping: `portmap add TCP 8080 192.168.4.2 80`. |

## Weak signal and interference

- Read the uplink RSSI in `show status`. As a rough guide, better than
  -67 dBm is comfortable, -70 to -80 dBm is marginal, worse is unreliable.
- Move the board, not just the client: the uplink has to be good for anything
  downstream to work.
- Keep the PCB antenna end (the end opposite the USB connector) clear of
  metal, the battery and cables; raise the board; avoid placing it behind
  walls, appliances or on the floor.
- Crowded 2.4 GHz channels slow everything down; since the board follows the
  home router's channel, choose a quieter channel (1, 6 or 11) on the router.
- More detail: [RANGE_AND_POWER.md](RANGE_AND_POWER.md).

## Reboot loop, low heap, too many clients

- Read the reset reason printed at boot (`rst:0x…`) and any `Guru Meditation`
  or `abort()` message just before the reset; include it in bug reports.
- `Brownout detector was triggered`: the supply sags during Wi-Fi transmit.
  See [Unstable power](#unstable-power-or-overheating).
- `heap` shows current and minimum free heap. If the minimum keeps falling,
  disable optional features you enabled (VPN, PCAP, remote console,
  per-client stats) and report it.
- The AP accepts at most 8 clients; extra clients are refused.
- If you enabled the reconnect watchdog (`set_watchdog N`), the board reboots
  after N seconds without uplink by design. `set_watchdog 0` disables it.

## Unstable power or overheating

- Espressif recommends a 3.3 V supply able to deliver at least 500 mA for the
  ESP32. Weak USB ports, long thin cables and small boost converters cause
  brownouts during transmit bursts.
- Never connect an 18650 cell directly to the 3V3 pin. With a TP4056 +
  MT3608, set the MT3608 to 5.0 V with a multimeter **before** connecting it
  to VIN, and check polarity.
- The ESP32 runs warm under continuous Wi-Fi traffic. Do not enclose it
  airtight or put it in direct sun; if the board becomes too hot to touch,
  power it down and improve ventilation.
- See [RANGE_AND_POWER.md](RANGE_AND_POWER.md#power).
