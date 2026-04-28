# Node 04 — TBD

## Status: 🔨 In Progress

Details to be filled in once the node is ready to configure.

## Hardware (planned)
- **Device:** Raspberry Pi (model TBD)
- **Sensors (planned):**
  - Temperature + Humidity sensor (model TBD — e.g. SHT31, AHT20, or BME280)
  - Barometric pressure sensor (model TBD — e.g. BME280, BMP390)
  - Note: if BME280 is used, it covers temp + humidity + pressure in one chip

## Identifiers (TBD)
| Field | Value |
|-------|-------|
| nodeId | TBD |
| MQTT client_id | TBD |
| IoT topic | `weather/{nodeId}/telemetry` |

## Setup Checklist
Use the provisioning scripts in `/provisioning/` when this node is ready:

- [ ] Choose and document sensor model(s)
- [ ] Assign a `nodeId` and update this README
- [ ] Run `provision-iot.sh` to register in AWS IoT Core
- [ ] Copy certs to Pi at `/home/weather/weather-station/certs/{nodeId}.*`
- [ ] Copy `collector.py` from Node 3 as starting point, update sensor imports + `NODE_ID`
- [ ] Copy `run.sh` from Node 2 as starting point, update paths
- [ ] Add cron entry on Pi
- [ ] Verify data appears in DynamoDB under the new `nodeId`
- [ ] Update this README with final details

## Notes
- Follow Node 3 (`outside-home`) as the collector template
- Follow Node 2 (`garden`) run.sh as the runner script template
- Default `lux` and `co2` to `0` if those sensors are not present
