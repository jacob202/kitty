# Honda Ridgeline (2019-2022) — J35A9 Specifications

## Engine

- **Engine:** J35A9 3.5L SOHC i-VTEC V6
- **Power:** 280 hp @ 6000 rpm
- **Torque:** 262 lb-ft @ 4700 rpm
- **Compression:** 11.5:1
- **Fuel:** Regular 87 octane (premium not required but improves knock margin)
- **Oil:** 0W-20 full synthetic, 4.5L with filter
- **Firing order:** 1-4-2-5-3-6

## Transmission

- **Type:** 6-speed automatic with paddle shifters
- **AWD:** Intelligent Variable Torque Management (i-VTM4) with torque vectoring rear differential
- **TC clutch:** Torque converter with lock-up clutch (known shudder issue at low speed)

## Key OBD PIDs (SAE J1979)

| PID | Name | Normal Range |
|-----|------|-------------|
| 0x0C | Engine RPM | 650–750 idle |
| 0x06 | STFT Bank 1 | ±5% normal |
| 0x07 | LTFT Bank 1 | ±2% ideal, <±5% acceptable |
| 0x08 | STFT Bank 2 | ±5% normal |
| 0x09 | LTFT Bank 2 | ±2% ideal, <±5% acceptable |
| 0x05 | Coolant Temp | 88–98°C normal operating |
| 0x0B | MAP | 25–35 kPa at idle |
| 0x11 | Throttle Position | 14–17% at idle |
| 0x0D | Vehicle Speed | — |
| 0x15 | O2 B1S2 Voltage | 0.1–0.9V cycling (closed loop) |
| 0x19 | O2 B2S2 Voltage | 0.1–0.9V cycling (closed loop) |

## Fuel Trim Thresholds

| Range | Meaning |
|-------|---------|
| < ±2% | Normal — ECU satisfied |
| ±2–5% | Watch — monitor trend |
| > ±5% | Investigate — active correction |
| > ±10% | Fault likely pending — could set DTC soon |

**Bank imbalance** (B1 vs B2 delta >3% LTFT): points to bank-specific issue.

## Service Intervals

| Service | Interval | Notes |
|---------|----------|-------|
| Engine oil | 5,000 km | 0W-20 full synthetic (Honda Genuine or equiv.) |
| Engine air filter | 30,000 km | Earlier if dusty/gravel roads |
| Cabin air filter | 15,000 km | — |
| Spark plugs | 100,000 km | NGK iridium, all 6 |
| Transmission fluid | 48,000 km | Honda DW-1 only, do NOT use aftermarket |
| Transfer case fluid | 48,000 km | Honda VTF |
| Rear diff fluid | 48,000 km | Honda DPS-F |
| Brake fluid | 45,000 km or 3 years | DOT 3 |
| Coolant | 150,000 km first, then 60,000 km | Honda Type 2 blue |
| Timing belt | N/A — chain driven | No replacement interval |

## Bank Layout (J35A9)

- **Bank 1:** Cylinder 1-3-5 (rear bank, passenger side on Ridgeline)
- **Bank 2:** Cylinder 2-4-6 (front bank, driver's side on Ridgeline)

Bank 2 is the front-facing bank. The exhaust manifold on Bank 2 is more prone to gasket failure on 2019-2021 models due to thermal cycling and casting tolerances.
