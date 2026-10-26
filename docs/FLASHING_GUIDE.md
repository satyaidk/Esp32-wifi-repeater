# Step-by-step guide: flash and set up the repeater

This guide takes you from a new ESP32 DevKit V1 to a working Wi-Fi repeater on
Windows. It also shows where to enter your Wi-Fi names and passwords, what you
can change later, and how to add a second repeater.

> **Status:** the firmware builds and its build-time checks are tested, but no
> board had been flashed when this guide was written. If a step behaves
> differently on your board, note it in [TEST_PLAN.md](TEST_PLAN.md) and
> [TROUBLESHOOTING.md](TROUBLESHOOTING.md).

- [How the repeater works](#how-the-repeater-works)
- [Step 1: What you need](#step-1-what-you-need)
- [Step 2: Install the tools (once)](#step-2-install-the-tools-once)
- [Step 3: Download the project](#step-3-download-the-project)
- [Step 4: Enter your Wi-Fi details](#step-4-enter-your-wi-fi-details)
- [Step 5: Build the firmware](#step-5-build-the-firmware)
- [Step 6: Connect the board](#step-6-connect-the-board)
- [Step 7: Flash the firmware](#step-7-flash-the-firmware)
- [Step 8: Connect your phone and check the internet](#step-8-connect-your-phone-and-check-the-internet)
- [Step 9: Change settings later](#step-9-change-settings-later)
- [Step 10: Add a second repeater](#step-10-add-a-second-repeater)
- [Common problems](#common-problems)

## How the repeater works

Two Wi-Fi networks are involved:

```mermaid
flowchart LR
    Router["Your router<br/>existing Wi-Fi"] -->|"board joins as a client"| ESP32["ESP32 repeater"]
    ESP32 -->|"board broadcasts"| Phone["Phones and laptops<br/>join the repeater network"]
```

| | Existing Wi-Fi ("uplink") | Repeater network |
|--|--|--|
| Created by | Your home router | The ESP32 |
| Who connects to it | The ESP32 | Your phones and laptops |
| Where you set its name and password | `CONFIG_REPEATER_UPLINK_SSID` / `CONFIG_REPEATER_UPLINK_PASSWORD` in your secrets file, **or** the Getting Started web page | `CONFIG_REPEATER_SETUP_AP_SSID` / `CONFIG_REPEATER_SETUP_AP_PASSWORD` in your secrets file, **or** the Getting Started web page |
| Requirements | Must be 2.4 GHz (the ESP32 has no 5 GHz radio). WPA/WPA2/WPA3-Personal or open. | Name 1–31 bytes, password 8–63 characters |

The repeater gives its clients addresses `192.168.4.x` and forwards their
traffic to your router (NAT). The board's own address on the repeater network
is `192.168.4.1`, where its web page lives.

## Step 1: What you need

- ESP32 DevKit V1 (ESP-WROOM-32) and a **data** Micro-USB cable (charge-only
  cables do not work)
- A Windows 10/11 PC with Git and Python 3.9 or newer
  (`git --version`, `python --version` in PowerShell)
- About 3 GB of free disk space
- The name and password of the 2.4 GHz Wi-Fi you want to repeat

## Step 2: Install the tools (once)

Open **PowerShell** and run:

```powershell
mkdir C:\Users\$env:USERNAME\esp\v5.5.4
cd C:\Users\$env:USERNAME\esp\v5.5.4
git clone -b v5.5.4 --depth 1 --recursive --shallow-submodules https://github.com/espressif/esp-idf.git
cd esp-idf
.\install.ps1 esp32
```

This installs ESP-IDF v5.5.4, the exact version this project is built with.
You only do this once.

**Every time you open a new PowerShell window** for this project, first run:

```powershell
C:\Users\$env:USERNAME\esp\v5.5.4\esp-idf\export.ps1
```

## Step 3: Download the project

```powershell
cd C:\Users\$env:USERNAME\Desktop
git clone --recursive https://github.com/satyaidk/wifi-repeater-with-esp32.git
cd wifi-repeater-with-esp32
```

Use `git clone --recursive`, not GitHub's "Download ZIP": the ZIP does not
contain the upstream firmware the build needs.

## Step 4: Enter your Wi-Fi details

All names and passwords go into **one file**, `config\secrets.local`. Git
ignores this file, so it never ends up on GitHub.

### 4.1 Create the file

```powershell
python tools\repeater.py init-secrets
```

This writes `config\secrets.local` with a repeater network name and two random
passwords. Open it in VS Code or Notepad:

```powershell
code config\secrets.local      # or: notepad config\secrets.local
```

### 4.2 Fill it in

A complete example (every value here is a made-up placeholder):

```ini
# The Wi-Fi network the repeater broadcasts (phones and laptops join this one).
CONFIG_REPEATER_SETUP_AP_SSID="MyHome-Extender"
CONFIG_REPEATER_SETUP_AP_PASSWORD="choose-a-wifi-password"

# Login for the web page at http://192.168.4.1
CONFIG_REPEATER_ADMIN_PASSWORD="choose-a-different-admin-password"

# Optional: the existing Wi-Fi to repeat.
CONFIG_REPEATER_UPLINK_SSID="MyHomeWiFi"
CONFIG_REPEATER_UPLINK_PASSWORD="my-home-wifi-password"

# Optional: the repeater's own address (only change for a second board).
# CONFIG_REPEATER_AP_IP="192.168.4.1"
```

In the generated file, the optional lines start with `# ` (switched off). To
use one, delete the `# ` at the start of the line and replace the
`REPLACE_ME_…` text.

| Line | What it is | Required | Rules |
|--|--|--|--|
| `CONFIG_REPEATER_SETUP_AP_SSID` | Name of the network the repeater broadcasts | Yes | 1–31 bytes; must differ from your home Wi-Fi name |
| `CONFIG_REPEATER_SETUP_AP_PASSWORD` | Password of that network (WPA2/WPA3) | Yes | 8–63 characters |
| `CONFIG_REPEATER_ADMIN_PASSWORD` | Login for the web page | Yes | 8–63 characters; must differ from the repeater Wi-Fi password |
| `CONFIG_REPEATER_UPLINK_SSID` | Name of your existing 2.4 GHz Wi-Fi | No | 0–31 bytes, exactly as your phone shows it (case-sensitive) |
| `CONFIG_REPEATER_UPLINK_PASSWORD` | Password of your existing Wi-Fi | No | Empty for an open network, otherwise 8–63 characters |
| `CONFIG_REPEATER_AP_IP` | The repeater's own address; clients get the same `/24` | No (default `192.168.4.1`) | Like `192.168.5.1`; last number 1–254 |

Rules for every value: keep it inside the double quotes; no `"` or `\`; no
space at the start or end; passwords use only the normal keyboard characters
(English letters, digits, symbols). The build checks all of this and tells you
exactly which line is wrong.

**If you leave the existing-Wi-Fi lines switched off,** the repeater starts in
setup mode and you choose the network on its web page in step 8. Both ways
work; the file is quicker if you know the password.

**Not sure of your home Wi-Fi name or band?** While your PC is connected to
it, run `netsh wlan show interfaces`. `SSID` is the name. The network must be
2.4 GHz: Windows shows this as `Band` (on newer versions), or check that
`Channel` is between 1 and 13. If your router only offers 5 GHz, enable the
2.4 GHz band in its settings.

### 4.3 Check the file

```powershell
python tools\repeater.py check-secrets
```

`config/secrets.local is valid` means you can continue. Otherwise the message
names each problem.

## Step 5: Build the firmware

```powershell
python tools\repeater.py build
```

The first build downloads components and takes a few minutes; later builds
are much faster. It ends with:

```text
[repeater] app image ... bytes = 83.9% of the 1572864-byte OTA slot
[repeater] release images for esp32: build/release/esp32
```

The build also tells you which home Wi-Fi it will join, if you set one
(`build-time uplink 'MyHomeWiFi'`).

## Step 6: Connect the board

1. Plug the board into the PC with the data cable.
2. Find its port. In PowerShell:

   ```powershell
   Get-CimInstance Win32_PnPEntity | Where-Object Name -match '\(COM\d+\)' | Select-Object Name
   ```

   Look for **Silicon Labs CP210x USB to UART Bridge (COMx)**. Ports named
   *Standard Serial over Bluetooth link* are not the board.
3. No CP210x entry? Try another cable. If Device Manager shows an unknown
   device, install the Silicon Labs CP210x driver:
   <https://www.silabs.com/developer-tools/usb-to-uart-bridge-vcp-drivers>.

The examples below use `COM5`; use your number.

## Step 7: Flash the firmware

The first time, erase the board completely and flash, with the serial monitor
open afterwards:

```powershell
python tools\repeater.py flash -p COM5 --erase --monitor
```

`--erase` wipes everything on the board, including settings left by earlier
firmware, so the values from your secrets file are used.

**If it stops at `Connecting....`:** press and hold the **BOOT** button on the
board until you see `Writing at 0x...`, then release it. If that does not
help: hold BOOT, press and release **EN**, release BOOT, and run the command
again.

What to look for in the monitor after the board restarts:

| Log line | Meaning |
|--|--|
| `First boot: router password initialised from build configuration` | Your admin password was stored |
| `First boot: web UI restricted to the AP interface` | The web page only answers on the repeater network |
| `Using build-time uplink SSID 'MyHomeWiFi'` | It is using the existing Wi-Fi from your file |
| `AP started` | The repeater network is on the air |
| `got ip:192.168.x.y` | It joined your home Wi-Fi and got an address |
| `disconnected - retry to connect to the AP` (repeating) | It cannot join your home Wi-Fi: wrong name/password, 5 GHz-only, or out of range |

Close the monitor with **Ctrl+]**. Open it again at any time:

```powershell
python tools\repeater.py monitor -p COM5
```

In the monitor you can also type commands after the `esp32>` prompt, for
example `show status`.

## Step 8: Connect your phone and check the internet

**If you put your home Wi-Fi in the file:**

1. On your phone, join the repeater network (`CONFIG_REPEATER_SETUP_AP_SSID`)
   with `CONFIG_REPEATER_SETUP_AP_PASSWORD`.
2. Open any website. That's it.

**If you did not:**

1. Join the repeater network as above. A setup page may open by itself;
   otherwise open `http://192.168.4.1`.
2. Log in with `CONFIG_REPEATER_ADMIN_PASSWORD`.
3. Open **Getting Started**: choose your home Wi-Fi, enter its password, and
   optionally a new name and password for the repeater network. Click
   **Save**; the board restarts.
4. Join the repeater network again (with the new name/password if you changed
   them) and open a website.

**Check it on the board** (in the monitor): `show status` should show
`Uplink AP: connected (ch N, -XX dBm)`. Values better than about -67 dBm are a
good place for the board.

**Check it on a laptop** joined to the repeater network:

```powershell
ipconfig /all              # IPv4 192.168.4.x, Default Gateway 192.168.4.1
nslookup example.com
ping -n 10 1.1.1.1
```

## Step 9: Change settings later

**The most important rule:** settings saved on the board always win over the
secrets file. The file only provides the starting values, used when the board
has nothing saved (after `--erase` or a factory reset). So there are two ways
to change something:

- **On the running board** (web page or serial command): takes effect after a
  restart and survives reflashing.
- **In the secrets file:** edit it, then `python tools\repeater.py flash -p COM5 --erase`.
  Without `--erase`, the old saved settings stay in use.

| What to change | Web page (`http://192.168.4.1`) | Serial command (then `restart`) | Secrets file line |
|--|--|--|--|
| Repeater network name and password | Getting Started, or Configuration → Access Point | `set_ap "MyHome-Extender" "new-wifi-password"` | `CONFIG_REPEATER_SETUP_AP_SSID` / `_PASSWORD` |
| Existing Wi-Fi to repeat | Getting Started, or WiFi Scan → Connect | `set_sta "MyHomeWiFi" "home-password"` | `CONFIG_REPEATER_UPLINK_SSID` / `_PASSWORD` |
| Admin password | Password section of the main page | `set_router_password "new-admin-password"` | `CONFIG_REPEATER_ADMIN_PASSWORD` |
| Repeater address / subnet | Configuration → AP IP | `set_ap_ip 192.168.5.1` | `CONFIG_REPEATER_AP_IP` |
| Hide the repeater network name | Configuration | `set_ap_hidden on` | — |
| Security mode | Configuration | `set_ap_auth wpa2` (or `wpa3`, `wpa2wpa3`) | — |
| Your country's channel rules | — | `set_wifi_country IN` (your 2-letter code) | — |
| Transmit power limit | — | `set_tx_power 15` (2–20 dBm, `0` = default) | — |
| DNS server for clients | Configuration | `set_ap_dns 1.1.1.1` | — |
| Board name on your home network | Configuration | `set_hostname my-repeater` | — |
| Status LED (often GPIO2 on DevKit V1; check your board) | — | `set_led_gpio 2` | — |
| Allow the web page from your home network too | Configuration | `web_ui bind all` | — |

Notes:

- Put names or passwords that contain spaces in double quotes, as shown.
- `show config` lists the values saved on the board. `<undef>` means nothing is
  saved and the value from your secrets file is in use.
- **Factory reset:** hold **BOOT** for 5 seconds (or type `factory_reset`).
  All saved settings are erased and the board starts again with the values
  from the firmware you flashed.
- Never leave the repeater network without a password: the firmware only
  allows that if you explicitly set an empty password.
- The firmware image contains the passwords from your secrets file. Do not
  share the `build` folder.

## Step 10: Add a second repeater

To reach further, a second board can repeat the **first repeater's** network.
This has not been tested on hardware yet; read
[TWO_BOARD_PLAN.md](TWO_BOARD_PLAN.md) for the trade-offs (every hop shares
one channel, so speed drops). If both locations can reach your router, it is
better to connect both boards directly to the router (two separate files with
your home Wi-Fi as uplink).

1. Set up board 1 as above, e.g. repeater network `MyHome-Extender`.
2. Create a second secrets file. The name must end in `.local` so Git ignores it:

   ```powershell
   python tools\repeater.py init-secrets --secrets config\board2.local --ssid "MyHome-Extender-2"
   ```

3. Edit `config\board2.local`:

   ```ini
   CONFIG_REPEATER_UPLINK_SSID="MyHome-Extender"            # board 1's network
   CONFIG_REPEATER_UPLINK_PASSWORD="board-1-wifi-password"  # board 1's network password
   CONFIG_REPEATER_AP_IP="192.168.5.1"                     # must differ from board 1
   ```

   The different address is required: board 2 receives a `192.168.4.x` address
   from board 1, so its own network must use another subnet.
4. Plug in board 2 and flash it with that file:

   ```powershell
   python tools\repeater.py flash -p COM6 --secrets config\board2.local --erase --monitor
   ```

5. Board 2's web page is at `http://192.168.5.1`.

Each board needs its own build, so build and flash one board at a time. The
second build takes longer because the configuration changes.

## Common problems

| Problem | What to do |
|--|--|
| `IDF_PATH is not set` | Run `export.ps1` (step 2) in this window first |
| `config/secrets.local is invalid` | Fix the lines the message lists (step 4.2) |
| Stuck at `Connecting....` | Hold BOOT while flashing (step 7) |
| `disconnected - retry ...` keeps repeating | Wrong home Wi-Fi name/password, 5 GHz-only network, or too far away |
| Changed the secrets file but nothing changed on the board | Saved settings win: flash with `--erase`, or change it on the web page |
| Phone connected but no internet | `show status`; if your home network also uses `192.168.4.x`, set `CONFIG_REPEATER_AP_IP="192.168.5.1"` (or `set_ap_ip 192.168.5.1`) |
| Forgot the admin password | `set_router_password` in the monitor, or hold BOOT 5 s |

More: [TROUBLESHOOTING.md](TROUBLESHOOTING.md). Technical details:
[BUILD_AND_FLASH.md](BUILD_AND_FLASH.md), [ARCHITECTURE.md](ARCHITECTURE.md).
Use the repeater only with networks you own or are allowed to use.
