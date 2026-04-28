# Node 03 — Outside Home

## Status: ✅ Active — Reference Implementation

Located outside the condo, at the bay window. This is the cleanest, most up-to-date
implementation and serves as the template for all new nodes.

## Hardware
- **Device:** Raspberry Pi (model TBD)
- **Sensors:**
  - BME280 — temperature (°C/°F), relative humidity (%), barometric pressure (hPa)
  - No CO2 sensor — `co2` field defaults to `0`
  - No light sensor — `lux` field defaults to `0`

## Identifiers
| Field | Value |
|-------|-------|
| nodeId | `outside-home` |
| MQTT client_id | `weather-outside-home` |
| IoT topic | `weather/outside-home/telemetry` |

## Certificate Paths (on Pi)
```
/home/weather/ws/outside-home.cert.pem
/home/weather/ws/outside-home.private.key
/home/weather/ws/root-CA.crt
```

Note: This node uses `/home/weather/ws/` for certs — Node 2 uses `/home/weather/weather-station/certs/`.
This inconsistency should be resolved in the provisioning scripts (pick one convention).

## Payload Fields
| Field | Source | Notes |
|-------|--------|-------|
| `nodeId` | config | `outside-home` |
| `eventTimestamp` | system clock | Eastern time, `YYYY-MM-DD HH:MM` |
| `eventDateDay` | system clock | Eastern time, `YYYY-MM-DD` |
| `tempF` / `tempC` | BME280 | |
| `humidity` | BME280 | |
| `pressure` | BME280 | hPa |
| `lux` | hardcoded | `0` — no sensor |
| `co2` | hardcoded | `0` — no sensor |
| `14DayTTL` | computed | 14 days from now, Unix epoch |

## Files
- `collector.py` — current working script (copy of `BME280-collection_AWSIOT.py`)
- `run.sh` — cron launcher with network + DNS wait loops

## Pi Script Filename
The script on the Pi is still named `BME280-collection_AWSIOT.py` (not `collector.py`).
The `run.sh` references that original name. If you rename it on the Pi, update the
two references in `run.sh` (`pgrep -f` and `nohup python` lines).

## Virtual Environment
Uses `/home/weather/ws/.venv/` — run.sh activates it before launching the script.

## Run Script Features
- Ping check (1.1.1.1) before DNS check — handles interface not up yet at boot
- DNS wait loop with diagnostic dump of `/etc/resolv.conf` on failure
- Duplicate process guard via `pgrep`
- Post-launch `pgrep` confirmation that process actually started

## Publish Interval
60 seconds (`time.sleep(60)`)
