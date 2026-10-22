# ADR 0001: Use the NAT router, not the Layer-2 bridge

- Status: Accepted
- Date: 2026-10-23

## Context

The goal is to extend a home 2.4 GHz network with an ESP32 DevKit V1. Two
upstream implementations exist in `martin-ger/esp32_nat_router`:

- `master` (v2.4.22, commit `119e0a3`): a NAT router. The ESP32 serves its own
  subnet with DHCP and forwards IPv4 through lwIP NAPT.
- `esp32_wifi_repeater` (v2.4.12, commit `cec6ebe`): a Layer-2 repeater that
  keeps clients on the home subnet by rewriting frames in software (IP→MAC
  forwarding database, DHCP transaction-ID proxying, proxy ARP). Upstream
  describes the branch as "still under development".

Plain AP+STA mode is not a bridge: an 802.11 station can only transmit
three-address frames with its own MAC, so either four-address/WDS support or
MAC translation is needed for Layer 2.

## Decision

Build `master`. Do not build or ship the Layer-2 branch in this project.

## Consequences

- Uses stock ESP-IDF forwarding (`CONFIG_LWIP_IP_FORWARD`,
  `CONFIG_LWIP_IPV4_NAPT`) instead of custom frame rewriting.
- Clients live on `192.168.4.0/24`, behind double NAT, invisible to the home
  LAN; mDNS/casting/UPnP discovery does not cross. Port mappings are
  available for inbound needs.
- The decision is revisited if same-subnet operation becomes a requirement
  and the Layer-2 branch is declared stable upstream. The build tooling would
  carry over (different pinned commit and patch set).
