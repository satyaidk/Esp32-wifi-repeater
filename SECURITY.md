# Security policy

## Reporting a vulnerability

Please report vulnerabilities privately through GitHub: open the repository's
**Security** tab and choose **Report a vulnerability**. Do not open a public
issue for security problems.

Include the affected commit, your ESP-IDF version, the steps to reproduce and
the impact you observed. You should receive an initial response within
14 days.

Vulnerabilities in upstream code that this project's patches do not touch
should also be reported to
[martin-ger/esp32_nat_router](https://github.com/martin-ger/esp32_nat_router).

## Supported versions

Only the latest commit on the default branch is supported.

## Security model

What this build does by default:

| Area | Default |
|--|--|
| Setup Wi-Fi | WPA2/WPA3 with an owner-chosen passphrase; never open unless the owner explicitly sets an empty password |
| Web UI | Admin password required (salted SHA-256 in NVS); reachable from the AP side only |
| Remote console, packet capture, VPN, MQTT | Off (MQTT compiled out) |
| Logs | Wi-Fi passwords, the admin password and VPN keys are not logged |
| Input | SSIDs, AP passphrases and the AP IP are validated before storage |

Known limitations (by design or upstream behaviour, not vulnerabilities in
themselves):

- The web UI is plain HTTP. Credentials typed into it can be sniffed by
  anyone already joined to the downstream network.
- Wi-Fi credentials are stored unencrypted in NVS; the serial command
  `show config` prints them to the local console. Physical access to the
  board is full access.
- Firmware images built from this repository contain the setup passphrase and
  admin password. Never publish `build/`.
- Flash encryption and secure boot are not enabled.

## Hardening checklist for owners

1. Use long, unique passwords in `config/secrets.local`; keep the admin
   password different from any Wi-Fi password.
2. After setup, give the downstream network a new passphrase on the Getting
   Started page.
3. Keep the web UI bound to the AP (`web_ui bind ap`, the default here), or
   disable it after setup (`web_ui disable`).
4. Set your country (`set_wifi_country <CC>`) and do not exceed legal
   transmit power.
5. Erase the board (`python tools/repeater.py erase-flash -p COMx --yes`)
   before giving it away.
