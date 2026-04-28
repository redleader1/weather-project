# DynamoDB Schema — Weather-Data_V10

## Table Details

| Property | Value |
|----------|-------|
| Table name | `Weather-Data_V10` |
| AWS Region | `us-east-1` |
| Billing mode | Provisioned (5 RCU / 5 WCU) |
| TTL attribute | `14DayTTL` |

## Key Schema

| Attribute | Type | Role |
|-----------|------|------|
| `nodeId` | String | Partition key (PK) |
| `eventTimestamp` | String | Sort key (SK) |

**Access pattern:** `nodeId` + `eventTimestamp` uniquely identifies a single reading.
To get all readings for a node, query by `nodeId`. Readings within a node are sorted
chronologically by `eventTimestamp`.

## Global Secondary Index (GSI)

| Property | Value |
|----------|-------|
| Index name | `eventDateDay-index` |
| Partition key | `eventDateDay` (String) |
| Sort key | none |
| Projection | ALL |
| Provisioned | 5 RCU / 5 WCU |

**Access pattern:** query all nodes' readings for a given calendar day.
Used by the weather website Lambda to build the daily dashboard.

Example query:
```python
response = table.query(
    IndexName='eventDateDay-index',
    KeyConditionExpression=Key('eventDateDay').eq('2025-01-15')
)
```

## Attribute Reference

| Attribute | Type | Format / Notes |
|-----------|------|----------------|
| `nodeId` | String (PK) | e.g. `outside-home`, `garden-01`, `outside-01` |
| `eventTimestamp` | String (SK) | `YYYY-MM-DD HH:MM` — Eastern time — e.g. `2025-01-15 14:30` |
| `eventDateDay` | String (GSI PK) | `YYYY-MM-DD` — Eastern time |
| `14DayTTL` | Number | Unix epoch seconds, 14 days from publish time |
| `tempF` | Number | Temperature in Fahrenheit, 2 decimal places |
| `tempC` | Number | Temperature in Celsius, 2 decimal places |
| `humidity` | Number | Relative humidity %, 2 decimal places |
| `pressure` | Number | Barometric pressure in hPa, 2 decimal places |
| `lux` | Number | Ambient light in lux, 2 decimal places (0 if no sensor) |
| `co2` | Number | CO2 concentration in ppm, integer (0 if no sensor) |

## Standard Write Payload

All Pi nodes publish this JSON to MQTT; the IoT Rule writes it to DynamoDB.

```json
{
  "nodeId":         "outside-home",
  "eventTimestamp": "2025-01-15 14:30",
  "eventDateDay":   "2025-01-15",
  "tempF":          72.50,
  "tempC":          22.50,
  "humidity":       55.20,
  "pressure":       1013.25,
  "lux":            0,
  "co2":            0,
  "14DayTTL":       1737072600
}
```

## Node 1 Exception

Node 1 (`outside-01`) sends via API Gateway, not MQTT. Its payload uses:
- `eventDate`: ISO 8601 full timestamp (e.g. `2025-01-15T14:30:00-05:00`)
- `nodeId`: `outside-01`
- No `14DayTTL` — records from Node 1 do not expire automatically

The API Gateway Lambda translates this into DynamoDB writes.

## Data Retention

Records with a `14DayTTL` attribute are automatically deleted by DynamoDB after 14 days.
Node 1 records have no TTL and persist indefinitely (until manually pruned).

The `archive-prune-weathertest2.py` script in the archive folder was an early manual
pruning tool — it is no longer needed for TTL-enabled records.

## Re-creating the Table

See `misc-scripts/create-dynamoDB_v2.py` in the archive folder for the original creation
script. To recreate with the same schema:

```python
KeySchema=[
    {'AttributeName': 'nodeId',           'KeyType': 'HASH'},
    {'AttributeName': 'eventTimestamp',   'KeyType': 'RANGE'},
],
AttributeDefinitions=[
    {'AttributeName': 'nodeId',           'AttributeType': 'S'},
    {'AttributeName': 'eventTimestamp',   'AttributeType': 'S'},
    {'AttributeName': 'eventDateDay',     'AttributeType': 'S'},
],
GlobalSecondaryIndexes=[{
    'IndexName': 'eventDateDay-index',
    'KeySchema': [{'AttributeName': 'eventDateDay', 'KeyType': 'HASH'}],
    'Projection': {'ProjectionType': 'ALL'},
}]
```
