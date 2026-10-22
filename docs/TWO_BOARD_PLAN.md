# Two-board plan

Status: **analysis only.** Nothing in this document has been tested on
hardware. Get one board working end to end first ([TEST_PLAN.md](TEST_PLAN.md)
T-10 to T-28), then try the topologies below.

Flashing the same firmware to two boards does not make a multi-hop repeater by
itself. Each board is an independent NAT router; how they relate depends only
on which network each board's uplink joins and how each is configured.

## Topology 1: chain (board 2 uplinks to board 1)

```mermaid
flowchart LR
    R["Home router<br/>192.168.1.0/24<br/>channel C"] -->|Wi-Fi| B1
    B1["Board 1<br/>STA 192.168.1.x<br/>AP 192.168.4.1/24"] -->|Wi-Fi| B2
    B2["Board 2<br/>STA 192.168.4.x<br/>AP 192.168.5.1/24"] -->|Wi-Fi| C["Phone<br/>192.168.5.x"]
```

Supported by configuration: board 2's uplink is simply a Wi-Fi network,
which can be board 1's AP.

### Configuration with a secrets file per board (recommended)

Verified against the firmware source and compiled; not tested on hardware.

1. Board 1: `config/secrets.local` with your home Wi-Fi as uplink and its own
   repeater network, e.g. `Repeater-1`. Flash it
   (`python tools/repeater.py flash -p COM5 --erase`).
2. Board 2: a second file whose name ends in `.local` (git-ignored):

   ```powershell
   python tools\repeater.py init-secrets --secrets config\board2.local --ssid "Repeater-2"
   ```

   then set in `config/board2.local`:

   ```ini
   CONFIG_REPEATER_UPLINK_SSID="Repeater-1"
   CONFIG_REPEATER_UPLINK_PASSWORD="<board 1's repeater network password>"
   CONFIG_REPEATER_AP_IP="192.168.5.1"
   ```

   The different AP address is required: board 2's uplink address is in
   board 1's `192.168.4.0/24`, so board 2's own network must be another /24.
3. Flash board 2: `python tools/repeater.py flash -p COM6 --secrets config\board2.local --erase`.
   Its web page is at `http://192.168.5.1`.
4. Optional: `set_wifi_country <CC>` on both boards.

With patch 0005 the Getting Started page resets the AP address to the
board's build-time value (`192.168.5.1` on board 2), not to `192.168.4.1`.

### Configuration at runtime (without a second secrets file)

1. On board 2's **Getting Started** page (`http://192.168.4.1`), choose
   `Repeater-1` as the uplink and set a different AP SSID, e.g. `Repeater-2`.
   Save; board 2 reboots.
2. **Then** change board 2's AP subnet on its serial console:

   ```text
   set_ap_ip 192.168.5.1
   restart
   ```

   or use the AP IP field on the **Configuration** page. Do it after the
   Getting Started page, which resets the AP address to the build-time value
   (`setup_get_handler` in upstream `http_server.c`). `set_ap_ip` to a new
   `/24` also clears board 2's DHCP reservations and port mappings.

### What to expect

| Aspect | Behaviour | Basis |
|--|--|--|
| Addressing | Three subnets, triple NAT (home router, board 1, board 2) | NAPT on each board |
| Channel | Every hop on the home router's channel C: board 1's AP follows C, board 2's STA joins board 1 on C, board 2's AP follows C | ESP-IDF APSTA channel rule (ARCHITECTURE.md §6) |
| Throughput | Lower than one board. All four transmissions (router→B1, B1→B2, B2→phone and back) share the airtime of one channel; a common rule of thumb is roughly half per same-channel hop. **Estimate, not measured.** | Shared-channel store-and-forward |
| Latency | Adds per-hop queuing delay. Not measured. | |
| Roaming | No seamless roaming. Each network has its own SSID and subnet; moving between them means a new DHCP lease and new IP, which breaks open connections. Reusing one SSID would not fix that because the subnets still differ. | NAT design |
| Failure | If board 1 loses its uplink, board 2 stays associated to board 1 but has no internet. If board 1 disappears, board 2 backs off and reconnects when it returns (250 ms to 16 s). | Upstream reconnect logic |
| Client capacity | Board 2 occupies one of board 1's 8 client slots | `AP_MAX_CONNECTIONS` |

### Placement

Put board 1 where it still has a solid link to the home router (check `show
status` → `Uplink AP: connected (ch N, RSSI dBm)`; aim for roughly -67 dBm or
stronger), and board 2 where it has a solid link to board 1. Every hop is only
as good as its weakest direction, often the client's uplink back to the board.

## Topology 2: star (both boards uplink to the home router)

```mermaid
flowchart LR
    R["Home router"] -->|Wi-Fi| B1["Board 1<br/>AP 192.168.4.1"]
    R -->|Wi-Fi| B2["Board 2<br/>AP 192.168.4.1"]
```

If both locations are within reach of the home router, configure both boards
with the home router as uplink. Each board is an independent single-hop
repeater, so neither depends on the other and there is only double NAT. Both
APs can keep `192.168.4.1`: they are separate networks. Both still share the
home router's channel. This is the better choice whenever the geometry allows
it.

## Layer-2 bridging with two boards

The upstream `esp32_wifi_repeater` branch implements single-board Layer-2
bridging in software. Whether two such boards can be chained, and how they
interact, has not been reviewed or tested here, and that branch is described
upstream as under development ([ADR 0001](adr/0001-nat-router-over-layer2-bridge.md)).
No claim is made that it works with two boards.

## When to use other hardware

The ESP32 DevKit V1 has a small PCB antenna, a single 2.4 GHz radio and shared
airtime. If reliable coverage at 50–100 m matters more than the learning
exercise, consider:

- an outdoor point-to-point bridge pair (CPE units with directional antennas)
  feeding a normal access point at the far end;
- a mesh Wi-Fi system with wired or dedicated-radio backhaul;
- an Ethernet or powerline link to a second access point.

These use proper antennas, separate backhaul channels and certified transmit
power. The ESP32 prototype remains useful for learning and for short ranges.
