# Range and power

Firmware cannot overcome radio physics. This page explains what limits range
with an ESP32 DevKit V1, how to test it honestly, and how to power the board
safely from a battery. **No range or battery measurements have been made for
this project yet**; use [TEST_PLAN.md](TEST_PLAN.md) T-29 and T-30 to record
your own.

## Range

### What decides how far it reaches

A Wi-Fi link works only if both directions work. Range is set by:

- transmit power and antenna gain at **both** ends: the board, and the phone
  or laptop, which often transmits with less power than the board;
- receiver sensitivity, which falls as the data rate rises, so throughput
  drops long before the link breaks;
- path loss: distance, walls, trees, people, water, metal;
- the Fresnel zone: a clear line of sight is not enough if the ground or an
  obstacle intrudes into the ellipse around it; height helps;
- interference from other 2.4 GHz networks, Bluetooth and microwave ovens.

### The DevKit V1 antenna

The ESP-WROOM-32 module on the DevKit V1 has a PCB trace antenna at the end
of the module farthest from the USB connector. There is no external-antenna
connector (the ESP-WROOM-32**U** variant has one). Modifying the board to add
an antenna is not covered here: it changes the certified radio configuration.

The 50–100 m open-space target is a hypothesis to test, not a specification.
Two things are needed for it at once: the board must hear the home router
well at its position, and clients must reach the board.

### Placement checklist

1. Place the board where its uplink is strong: `show status` prints
   `Uplink AP: connected (ch N, RSSI dBm)`. Roughly: better than -67 dBm is
   comfortable, -70 to -80 dBm marginal.
2. Raise it (1.5–2 m or more) and keep the antenna end clear of metal, the
   battery, the USB cable and walls.
3. Try rotating it 90°; PCB antennas are not uniform in all directions.
4. Choose a quiet channel on the **home router** (1, 6 or 11). The board
   always uses the router's channel.

### Transmit power and regulations

- `set_tx_power <dBm>` sets the maximum transmit power from 2 to 20 dBm;
  `0` restores the default maximum. It needs no extra hardware and should not
  be raised beyond what your country permits.
- `set_wifi_country <CC>` (ISO 3166 code, e.g. `US`, `DE`, `IN`) applies your
  country's channel set. The default is `01`, a world-safe set.
- Legal limits are usually defined as EIRP (transmit power plus antenna gain).
  Do not add amplifiers or high-gain antennas to exceed them.
- At short range, lowering the transmit power reduces current draw and heat
  and can prevent brownouts on weak supplies.

### What throughput to expect

Upstream reports 5–15 Mbps "under reasonable conditions" for the NAT router.
Because uplink and downlink share one channel
([ARCHITECTURE.md](ARCHITECTURE.md#6-radio-and-channel-behaviour)), and data
rates fall with distance, expect less at the edge of coverage. This project
has not measured throughput yet.

## Power

### Requirements

- Espressif's ESP32 hardware design guidelines (schematic checklist)
  recommend a 3.3 V supply that can deliver **no less than 500 mA**. Wi-Fi
  transmit bursts draw short current peaks.
- The ESP32 itself is a 3.3 V device. The DevKit V1 has an on-board 3.3 V
  regulator fed from USB or the VIN (5 V) pin.

### Simplest and most reliable: USB

A 5 V phone charger rated 1 A or more and a short, good cable. Use this for
all first tests, so power problems cannot be confused with firmware problems.

### Battery: 18650 + TP4056 + MT3608

```text
18650 cell ──► TP4056 module (with protection) ──► MT3608 boost (set to 5.0 V) ──► VIN / GND
              B+ / B-                    OUT+ / OUT-                        OUT+ / OUT-
```

1. Use a TP4056 module **with** a protection circuit (marked `OUT+`/`OUT-`
   in addition to `B+`/`B-`) and a protected or quality cell.
2. **Before connecting the ESP32:** connect the battery side, measure the
   MT3608 output with a multimeter and turn its potentiometer until it reads
   5.0 V. These modules can ship set to a much higher voltage.
3. Disconnect, then wire MT3608 `OUT+` → DevKit `VIN`, `OUT-` → `GND`.
   Check polarity twice.
4. Do not power the board from VIN and USB at the same time unless you have
   checked your board's schematic for back-feed protection.
5. **Never connect the cell (up to 4.2 V) to the 3V3 pin.** That bypasses the
   regulator and exceeds the ESP32's supply rating.
6. During a long traffic test (T-23), watch the serial log for `Brownout
   detector was triggered`. If it appears, the supply cannot deliver the
   peaks: improve wiring, add bulk capacitance near VIN, or lower
   `set_tx_power`.

### Estimating battery runtime

Measure, do not guess. With a USB power meter or a multimeter in series,
record the average current at the board's input during typical use, then:

```text
runtime (h) ≈ cell capacity (Wh) × converter efficiency ÷ measured input power (W)
```

Use the cell's real capacity, not the label, and an efficiency you measured
or took from the converter's datasheet at your load.

### Safety

- Do not charge lithium cells unattended, near flammable material, or if the
  cell is dented, swollen or hot.
- Ventilate the enclosure: the ESP32 gets warm under continuous Wi-Fi load.
