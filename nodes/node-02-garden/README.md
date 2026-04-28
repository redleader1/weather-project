# Node 02 — Garden

## Status: ✅ Active

Located on the first floor of the condo, in the garden area.

## Hardware
- **Device:** Raspberry Pi (model TBD)
- **Sensors:**
  - SCD4X (SCD41) — CO2 (ppm), temperature (°C), relative humidity (%)
  - BMP3XX — barometric pressure (hPa)
  - BH1750 — ambient light (lux)

## Identifiers
| Field | Value |
|-------|-------|
| nodeId | `garden-01` |
| MQTT client_id | `weather-garden-{hostname}` (dynamic) |
| IoT topic | `weather/garden-01/telemetry` |

## Certificate Paths (on Pi)
```
/home/weather/weather-station/certs/garden-01.cert.pem
/home/weather/weather-station/certs/garden-01.private.key
/home/weather/weather-station/certs/root-CA.crt
```

Note: This node uses `/home/weather/weather-station/certs/` — different from Node 3
which uses `/home/weather/ws/`. Keep this consistent when provisioning future nodes
(pick one convention and document it in provisioning scripts).

## Payload Fields
| Field | Source | Notes |
|-------|--------|-------|
| `nodeId` | config | `garden-01` |
| `eventTimestamp` | system clock | Eastern time, `YYYY-MM-DD HH:MM` |
| `eventDateDay` | system clock | Eastern time, `YYYY-MM-DD` |
| `tempF` / `tempC` | SCD41 | SCD41 temp used as canonical |
| `humidity` | SCD41 | |
| `co2` | SCD41 | Integer (ppm) |
| `pressure` | BMP3XX | hPa |
| `lux` | BH1750 | |
| `14DayTTL` | computed | 14 days from now, Unix epoch |

## Files
- `collector.py` — current working script

## Notes
- CO2 is stored as `int` (ppm), not float — intentional
- Uses `socket.gethostname()` in `client_id` to prevent duplicate-client disconnects
- SCD41 temperature is used as the primary temp reading (not BMP3XX), because the
  SCD41 is better calibrated for ambient air temperature
- SCD41 requires ~5 seconds before first measurement is ready after `start_periodic_measurement()`
