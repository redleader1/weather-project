# Weather Station Ecosystem — Project Context

## Overview

A distributed weather monitoring system using Raspberry Pi nodes that publish sensor data to AWS
IoT Core, store readings in DynamoDB, and display results via a Lambda-backed website. There is
also a planned admin panel for monitoring system health.

This file is the source of truth for all project assumptions. Read it at the start of every
session before making changes.

---

## Architecture

### Target Architecture (in progress)
```
Pi Node (Python + cron)
    └── MQTT via AWS IoT SDK
        └── AWS IoT Core  (topic: weather/{nodeId}/telemetry)
            └── IoT Rule  (writes to DynamoDB)
                └── DynamoDB table: weather-data  (new — TTL enabled)
                    ├── Lambda: weather-api        (returns JSON — /api path) (AWS: `web_test_3`)
                    └── Lambda: admin-panel        (node health — planned)

Exception — Node 1 (parents-house):
    HTTP POST → API Gateway → Lambda (node1-api-gateway) → DynamoDB: weather-data

CloudFront Distribution (E2TUI9GEVJDFSQ)
    ├── /       → S3 bucket  (static HTML/CSS/JS)
    ├── /api    → Lambda URL (JSON weather data)
    └── /admin  → Lambda URL (admin panel — planned)

GitHub → GitHub Actions (OIDC) → Lambda deploy + S3 deploy + CF invalidation
GitHub → Pi cron (git pull)    → auto-update collector scripts
```

### Current Architecture (being replaced)
```
Pi Node → IoT Core → DynamoDB: Weather-Data_V10 → Lambda (returns HTML) → CloudFront
```

**Exception — Node 1 (parents-house):**
Follows a legacy path via HTTP POST to API Gateway, NOT MQTT. The API Gateway routes to a
separate Lambda that writes to DynamoDB. This path must never be broken. Do not modify
Node 1's Pi script or API Gateway endpoint — only the downstream Lambda and table can change.

---

## Technology Decisions

These decisions were made deliberately — do not revisit without good reason.

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | New DynamoDB table `weather-data` | Clean start with TTL; drop `Weather-Data_V10` |
| Edge management | No IoT Greengrass | Overkill for 4 nodes; git pull is sufficient |
| Secrets | AWS Secrets Manager for Lambdas only | Pi certs managed by IoT Core; no Greengrass |
| Website delivery | S3 static site via CloudFront | Simpler updates; Lambda becomes JSON API only |
| Deployments | GitHub Actions with OIDC auth | No stored AWS credentials in GitHub |
| Pi code updates | Git pull via cron | Simple, reliable, no extra infrastructure |
| HTML rendering | Browser-side JS fetches JSON from Lambda | Clean separation of data and presentation |

---

## Public URLs

| Service | URL |
|---------|-----|
| CloudFront (public) | `https://d33w9ue2h7llgj.cloudfront.net` |
| Lambda function URL (direct, current) | `https://4pwj6hzjxonvxr4dsf4xqzodsi0aqivd.lambda-url.us-east-1.on.aws` |
| CloudFront Distribution ID | `E2TUI9GEVJDFSQ` |
| AWS Account ID | `673842895830` |
| IAM User (local CLI) | `eriks_mac` |
| AWS Account ID | `673842895830` |
| IAM User (local CLI) | `eriks_mac` |

**CloudFront cache invalidation** — run after any Lambda or S3 deploy:
```bash
aws cloudfront create-invalidation --distribution-id E2TUI9GEVJDFSQ --paths "/*"
```

**Note:** Once S3 static site is wired up, HTML changes will only require an S3 upload
(via GitHub Actions). Lambda deploys will only be needed when data logic changes.

---

## Node Inventory

| # | Name | Location | nodeId | Sensors | Status |
|---|------|----------|--------|---------|--------|
| 1 | parents-house | Parents' house | `outside-01` | BH1750 (lux), MS8607 (temp/humidity/pressure) | 🔒 Locked — do not modify |
| 2 | garden | Condo, first floor garden | `garden-01` | SCD4X/SCD41 (CO2/temp/humidity), BMP3XX (pressure), BH1750 (lux) | ✅ Active |
| 3 | outside-home | Condo, bay window (exterior) | `outside-home` | BME280 (temp/humidity/pressure) | ✅ Active — reference implementation |
| 4 | TBD | TBD | TBD | BME280 or equiv (temp/humidity/pressure) | 🔨 In progress |

### Node 1 — Parents House (LOCKED)
- **Cannot be modified** — physically inaccessible
- Sends via HTTP POST to API Gateway (legacy path)
- API endpoint: `https://1iawimadei.execute-api.us-east-1.amazonaws.com/prod/WeatherApi`
- Payload uses `eventDate` (ISO 8601 format), `nodeId: "outside-01"`
- Does NOT include `14DayTTL` or `eventDateDay`
- Do not change the API Gateway, its Lambda, or the DynamoDB schema in ways that break this
- Ingestion Lambda: `aws/lambda/node1-api-gateway/lambda_function.py` (AWS function name: `WeatherApi`)
  - Translates `eventDate` → `eventDateDay` + `eventTimestamp` before writing to DynamoDB
  - Does NOT write `14DayTTL` — Node 1 records accumulate indefinitely (no auto-expiry)
  - Uses low-level `boto3.client` (not `boto3.resource`)

### Node 2 — Garden (ACTIVE)
- Script: `nodes/node-02-garden/collector.py`
- Runner: `nodes/node-02-garden/run.sh`
- nodeId: `garden-01`, MQTT client_id: `weather-garden-{hostname}`
- Sensors: SCD41 (CO2, temp, humidity), BMP3XX (pressure), BH1750 (lux)
- SCD41 temperature is used as the canonical temperature reading (not BMP3XX)
- CO2 stored as integer ppm
- Cert path on Pi: `/home/weather/weather-station/certs/`
- Working dir on Pi: `/home/weather/weather-station/`
- Script filename on Pi: `garden_publisher.py` (our project calls it `collector.py`)

### Node 3 — Outside Home (REFERENCE)
- The most current, cleanest implementation — use as the template for all new nodes
- Script: `nodes/node-03-outside-home/collector.py`
- Runner: `nodes/node-03-outside-home/run.sh`
- Uses `awscrt` / `awsiot` MQTT SDK
- Topic: `weather/outside-home/telemetry`
- Certificate paths on Pi: `/home/weather/ws/outside-home.{cert.pem,private.key}`
- Python venv on Pi: `/home/weather/ws/.venv/`
- Script filename on Pi: `BME280-collection_AWSIOT.py` (our project calls it `collector.py`)

### Node 4 — TBD (IN PROGRESS)
- Sensors: temperature + humidity + barometric pressure (sensor model TBD)
- Location TBD
- Will follow Node 3 as the template once sensor model is confirmed

---

## DynamoDB Schema

**Table:** `weather-data` (new — replacing `Weather-Data_V10`)
**Region:** `us-east-1`

| Attribute | Type | Format | Role |
|-----------|------|--------|------|
| `nodeId` | String | e.g. `outside-home` | Partition key (PK) |
| `eventTimestamp` | String | `YYYY-MM-DD HH:MM` (Eastern) | Sort key (SK) |
| `eventDateDay` | String | `YYYY-MM-DD` | GSI partition key |
| `14DayTTL` | Number | Unix epoch (seconds) | DynamoDB TTL attribute |

**GSI:** `eventDateDay-index`
- Partition key: `eventDateDay`
- Projection: ALL
- Purpose: query all nodes' readings for a given calendar day

### Standard Payload — All Nodes Must Send This

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

**Rules:**
- All sensor readings rounded to 2 decimal places
- `lux` defaults to `0` if the node has no light sensor
- `co2` defaults to `0` if the node has no CO2 sensor
- Timestamps in **Eastern time (America/New_York)** — use `zoneinfo.ZoneInfo("America/New_York")`
- `eventTimestamp` format: `"%Y-%m-%d %H:%M"` — no seconds
- `eventDateDay` format: `"%Y-%m-%d"`
- `14DayTTL` = `int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp())`

**Field casing standard:** all lowercase (`tempF`, `tempC`, `humidity`, `pressure`, `lux`, `co2`).
The old Lambda used `TempF` and `CO2` (mixed case) — this was a bug. Use lowercase everywhere.

---

## AWS IoT Core

**Endpoint:** `a2v8psfnp297g7-ats.iot.us-east-1.amazonaws.com`
**Topic pattern:** `weather/{nodeId}/telemetry`
**QoS:** `AT_LEAST_ONCE`
**SDK:** `awscrt` + `awsiot` (`awsiotsdk` Python package)

### Certificate Layout on Pi

```
/home/weather/ws/
├── {nodeId}.cert.pem
├── {nodeId}.private.key
└── root-CA.crt          # shared across all nodes
```

**Pi user:** `weather`
**Working directory:** `/home/weather/ws/`

---

## Folder Structure

```
weather-project/
├── CLAUDE.md                             # ← you are here
│
├── nodes/
│   ├── shared/                           # Shared utilities imported by all collectors
│   │   ├── aws_iot.py                    # MQTT connection helper (planned)
│   │   ├── payload.py                    # Payload builder: timestamps, TTL, defaults (planned)
│   │   └── sensors/                      # Sensor driver wrappers (planned)
│   │       ├── bme280.py
│   │       ├── scd4x.py
│   │       ├── bmp3xx.py
│   │       ├── ms8607.py
│   │       └── bh1750.py
│   │
│   ├── node-01-parents-house/            # 🔒 REFERENCE ONLY — do not modify or deploy
│   │   ├── README.md
│   │   └── collector.py                  # Original script, preserved for reference
│   │
│   ├── node-02-garden/                   # ⚠️ Script not yet retrieved
│   │   └── README.md
│   │
│   ├── node-03-outside-home/             # ✅ Active — reference implementation
│   │   ├── README.md
│   │   ├── collector.py                  # Current working script
│   │   └── run.sh                        # Cron runner (planned)
│   │
│   └── node-04-tbd/                      # 🔨 In progress
│       └── README.md
│
├── aws/
│   ├── lambda/
│   │   ├── weather-website/              # Public-facing weather dashboard
│   │   │   └── lambda_function.py        # Authoritative version (to be built)
│   │   └── admin-panel/                  # System health panel (planned)
│   │       └── lambda_function.py
│   └── dynamodb/
│       └── schema.md                     # Full schema documentation
│
├── provisioning/                         # Scripts to set up a new node end-to-end
│   ├── README.md
│   ├── provision-iot.sh                  # Registers thing + cert in AWS IoT Core (planned)
│   └── setup-pi.sh                       # Pi: installs deps, venv, cron entry (planned)
│
└── archive/                              # Old scripts — do not use, kept for reference
    ├── collection-scripts/
    ├── lambda-old/
    ├── misc-scripts/
    └── backups/
```

---

## Known Issues & Inconsistencies

These are documented so they can be fixed on writable nodes (2, 3, 4):

1. **Field casing inconsistency** — Old Lambda reads both `tempF` and `TempF`, `co2` and `CO2`.
   Standard going forward: all lowercase.
2. **Cert path inconsistency** — Node 2 uses `/home/weather/weather-station/certs/`, Node 3 uses
   `/home/weather/ws/`. Standardize in provisioning scripts going forward.
3. **Venv naming inconsistency** — Node 2 venv is at `weather-station/garden/` (named after the
   node), Node 3 venv is at `ws/.venv/` (hidden folder, generic name). Both work fine. Provisioning
   scripts will standardize on `/home/weather/weather-station/.venv/` for all future nodes.
4. **Two Lambda versions** — `mylamda/` and `myLamnda2/` both exist in archive. Neither is
   authoritative. The new version lives in `aws/lambda/weather-website/`.
4. **Node 1 payload difference** — Uses `eventDate` (ISO 8601) instead of `eventDateDay` +
   `eventTimestamp`. The API Gateway Lambda handles the translation. Do not change this.
5. **Node 3 has no `lux` or `co2` sensor** — Currently sends `"lux": 0` as a placeholder.
   This is correct behavior — keep it.

---

## Project Goals & Roadmap

See `ROADMAP.md` for the full detailed checklist. Summary of phases:

### Phase 1 — DynamoDB Migration ← START HERE
- [ ] Create new `weather-data` table with TTL enabled
- [ ] Update Node 1 API Gateway Lambda → new table + add TTL
- [ ] Update IoT Rule → new table
- [ ] Verify all nodes writing to new table
- [ ] Delete `Weather-Data_V10`

### Phase 2 — GitHub + CI/CD
- [ ] Create GitHub repo, push project, configure .gitignore
- [ ] Set up AWS IAM OIDC provider for GitHub Actions
- [ ] Write GitHub Actions workflows (Lambda deploy, S3 deploy, CF invalidation)
- [ ] Set up git pull cron on each Pi for auto-updates

### Phase 3 — Lambda Refactor (JSON API)
- [ ] Fix timezone bug, field casing bug, pagination bug
- [ ] Refactor weather Lambda to return JSON (not HTML)
- [ ] Create admin-panel Lambda (node health, last-seen)

### Phase 4 — S3 Static Website
- [ ] Create S3 bucket + CloudFront origin for static content
- [ ] Build HTML/CSS/JS site that fetches from Lambda JSON API
- [ ] Wire CloudFront: / → S3, /api → Lambda, /admin → admin Lambda
- [ ] Add NWS weather alerts, icons, high/low, auto-refresh

### Phase 5 — Secrets Manager
- [ ] Add Secrets Manager integration to Lambdas
- [ ] Document pattern for future API keys

### Phase 6 — Provisioning + Shared Utilities
- [ ] Write `nodes/shared/payload.py` and `aws_iot.py`
- [ ] Write `provisioning/provision-iot.sh` and `setup-pi.sh`
- [ ] Update Node 2 + 3 collectors to use shared utilities

### Phase 7 — Node 4
- [ ] Confirm sensor model, run provisioning scripts, verify data

---

## Development Guidelines

- **Double-check all code before presenting it** — the user is actively learning and may not
  catch subtle errors. Verify logic, field names, and AWS API calls carefully.
- **Node 1 data must keep flowing** — never modify the API Gateway ingestion path.
- **Node 3 is the reference** — when in doubt about how a collector should behave, look there.
- **Test on Node 3 first** before applying changes to Node 2.
- **Python versions:** Pi nodes run Python 3.11+; Lambda runs Python 3.12 (check AWS console).
- **AWS region:** `us-east-1` for all services.
- **Timezone:** All timestamps in Eastern (`America/New_York`) using `zoneinfo`.
- **Never hardcode AWS credentials** — use IoT certificates for Pi nodes, IAM roles for Lambda.
