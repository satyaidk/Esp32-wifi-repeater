# ADR 0005: Keep the feature set minimal for routing stability

- Status: Accepted
- Date: 2026-10-23

## Context

Upstream offers many optional features: WireGuard VPN, packet capture,
remote console, MQTT/Home Assistant, syslog, OLED, LED strips. Upstream warns
that each costs several KB of RAM and that enabling all of them can exhaust
the ESP32. A range extender needs routing, DHCP, DNS, the web UI and the
serial CLI.

## Decision

- Keep upstream's runtime defaults: VPN, PCAP, remote console, syslog and
  per-client statistics stay off until enabled.
- Compile MQTT/Home Assistant out (`CONFIG_MQTT_HOMEASSISTANT=n`). This needed
  patch 0004 because upstream's component did not configure with the option
  off.
- WireGuard stays compiled in: upstream's `main` component requires it
  unconditionally, and removing it would need a larger patch. It uses no RAM
  while disabled (upstream README).

## Consequences

- One fewer network client in the image. Upstream's Kconfig help estimates
  the MQTT feature at about 58 KB of flash; this project has not measured the
  difference itself (it only builds the MQTT-off variant).
- Re-enabling MQTT means setting `CONFIG_MQTT_HOMEASSISTANT=y` in
  `config/sdkconfig.defaults.repeater`.
