# Learning path

A guided route through this project for someone new to embedded networking.
Each step names what to read, what to run, and a small exercise. Steps 1–6
need no hardware.

## Step 1: The networking you need

Read [ARCHITECTURE.md §5](ARCHITECTURE.md#5-packet-path-subnet-and-dns-behaviour).

Concepts: IP address, subnet (`/24`), default gateway, DHCP (who hands out
addresses), DNS (names to addresses), NAT (many private devices behind one
address).

Exercise: run `ipconfig /all` on your PC. Find your IPv4 address, gateway
and DNS server, and work out your home subnet. Would it clash with
`192.168.4.0/24`?

## Step 2: Wi-Fi from the radio's point of view

Read [ARCHITECTURE.md §6](ARCHITECTURE.md#6-radio-and-channel-behaviour) and
[RANGE_AND_POWER.md](RANGE_AND_POWER.md).

Concepts: access point vs station, channels, why one radio means one shared
channel, RSSI in dBm (closer to 0 is stronger), why a NAT repeater is not a
Layer-2 bridge ([ADR 0001](adr/0001-nat-router-over-layer2-bridge.md)).

Exercise: with a Wi-Fi analyser app on your phone, note your home router's
channel and the RSSI in three rooms.

## Step 3: How an ESP-IDF project is configured

Run `python tools/repeater.py prepare`, then look at:

| File | What it teaches |
|--|--|
| `build/src/CMakeLists.txt` | The top-level ESP-IDF project |
| `build/src/main/Kconfig.projbuild` | How options are declared (find the "Secure first-boot defaults" menu) |
| `build/src/sdkconfig.defaults` | Upstream's defaults (forwarding and NAPT switches) |
| [`config/sdkconfig.defaults.repeater`](../config/sdkconfig.defaults.repeater) | This project's overlay |
| `build/sdkconfig.esp32` (after a build) | The merged result |

Exercise: find `CONFIG_LWIP_IPV4_NAPT` in all three layers and explain which
value wins and why.

## Step 4: Reproducible builds

Read the docstring at the top of [`tools/repeater.py`](../tools/repeater.py)
and [ADR 0002](adr/0002-upstream-submodule-with-patch-queue.md).

Concepts: git submodules, pinning a commit, patch queues, line endings
(CRLF/LF), why `sdkconfig.defaults` only applies to a new `sdkconfig`.

Exercise: `git -C build/src diff --stat` shows exactly what the patches
changed in upstream. Read one patch in `patches/` and find the same change in
the diff.

## Step 5: The firmware's event-driven core

Open `build/src/main/esp32_nat_router.c` and find `wifi_event_handler`.
Compare it with the state diagram in
[ARCHITECTURE.md §7](ARCHITECTURE.md#7-connection-state-machine).

Concepts: ESP-IDF event loop, why handlers must not block, one-shot
`esp_timer` for backoff, exponential backoff.

Exercise: answer from the code — how long does the board wait before the
fifth reconnect attempt? (Hint: `STA_RECONNECT_INITIAL_MS`.)

## Step 6: Security as code

Read [ARCHITECTURE.md §8](ARCHITECTURE.md#8-security-model),
[ADR 0003](adr/0003-build-time-setup-credentials.md) and patches 0001–0003.

Concepts: secure defaults, failing closed at build time (`_Static_assert`),
salted password hashes, keeping secrets out of logs and git, input
validation at a shared choke point.

Exercise: add a test to `tests/host/test_input_validation.c` for an address
you think should be rejected, run `python tests/host/run_host_tests.py`, and
decide whether the code or your expectation is wrong.

## Step 7: Tests that need no hardware

Run:

```powershell
python -m unittest discover -s tests -v
python tests\host\run_host_tests.py
```

Concepts: testing pure functions on the host, why the firmware's validation
lives in a header-only file, the difference between compile validation and
device testing.

## Step 8: Hardware

Follow [BUILD_AND_FLASH.md](BUILD_AND_FLASH.md) and run
[TEST_PLAN.md](TEST_PLAN.md) section 2 in order. Record every result,
including failures.

## Step 9: Measure, then extend

- Range walk (T-29) and battery test (T-30).
- The two-board chain ([TWO_BOARD_PLAN.md](TWO_BOARD_PLAN.md)).
- Read the Layer-2 branch upstream and compare its packet path with NAT.
