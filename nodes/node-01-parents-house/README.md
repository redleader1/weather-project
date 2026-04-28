# Node 01 — Parents House

## Status: 🔒 LOCKED — Do Not Modify

This node is physically inaccessible. The script is preserved here for reference only.
**Do not attempt to deploy updates to this node.**

## Hardware
- **Device:** Raspberry Pi (model unknown)
- **Sensors:**
  - BH1750 — ambient light (lux)
  - MS8607 — temperature (°C/°F), relative humidity (%), barometric pressure (hPa)

## Identifiers
| Field | Value |
|-------|-------|
| nodeId | `outside-01` |
| MQTT client_id | N/A — uses API Gateway |
| IoT topic | N/A — uses API Gateway |

## Ingestion Path (Legacy)
This node does **NOT** use MQTT / IoT Core. It sends data via HTTP POST to API Gateway:

```
POST https://1iawimadei.execute-api.us-east-1.amazonaws.com/prod/WeatherApi
```

Payload format differs from all other nodes:
- Uses `eventDate` (ISO 8601 full timestamp) instead of `eventDateDay` + `eventTimestamp`
- Does not include `14DayTTL`
- `nodeId` is `outside-01`

## Files
- `collector.py` — original script, reference only

## Known Limitations
- No TTL on DynamoDB records (data does not expire automatically)
- Timestamp format differs from standard — handled by the API Gateway Lambda
- If the API Gateway Lambda or its DynamoDB write logic is ever modified, verify Node 1
  data continues to land correctly
