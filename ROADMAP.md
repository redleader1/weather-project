# Weather Station — Project Roadmap & Checklist

This document captures every planned task discussed. Work through phases in order —
each phase unblocks the next. Check boxes off as tasks are completed.

Last updated: 2026-04-28

---

## Phase 1 — DynamoDB Migration

Goal: Replace the legacy `Weather-Data_V10` table (1M+ records, no TTL) with a clean
`weather-data` table that has TTL enabled from the start. No data is being migrated —
clean break.

- [x] **Create new DynamoDB table `weather-data`** in us-east-1
  - Partition key: `nodeId` (String)
  - Sort key: `eventTimestamp` (String)
  - GSI: `eventDateDay-index` — partition key `eventDateDay` (String), projection ALL
  - TTL attribute: `14DayTTL`
  - Billing: on-demand (pay-per-request) — better fit than provisioned for this workload

- [x] **Update Node 1 API Gateway Lambda** (`aws/lambda/node1-api-gateway/lambda_function.py`)
  - Change `TABLE_NAME` from `Weather-Data_V10` to `weather-data`
  - Add `14DayTTL` to the `put_item` call (Node 1 records currently never expire)
  - Deploy updated Lambda to AWS
  - Send a test POST and verify record appears in new table

- [x] **Update IoT Core Rule**
  - Updated `smithfield_test` rule to target `weather-data`
  - Updated IAM policy `AWS_IOT_Publish_DynamoDB` to allow writes to new table (was locked to old table)
  - Verified Node 2 and Node 3 data appears in new table

- [x] **Update weather-website Lambda env variable**
  - `TABLE_NAME` updated to `weather-data` on `web_test_3`

- [x] **Verify all three nodes writing to `weather-data`**
  - Confirmed records from `outside-01`, `garden-01`, `outside-home`

- [x] **Delete `Weather-Data_V10`**
  - Deleted — status `DELETING` confirmed

- [x] **Bonus: delete stale IoT rules**
  - Removed `bay_window_test`, `raspi_weather_multimeasure`, `raspi_weather`

---

## Phase 2 — GitHub + CI/CD

Goal: Source control for all code, automated deployments for Lambdas and the future
S3 static site. No AWS credentials stored in GitHub.

### GitHub Repository

- [x] **Initialize git** in the `weather-project/` folder
- [x] **Create `.gitignore`** — excludes certs, pycache, .DS_Store, archive/, build artifacts
- [x] **Create GitHub repository** (`redleader1/weather-project`, private)
- [x] **Initial commit and push**
- [ ] **Protect `main` branch** — require PR or direct push only from your account

### AWS IAM OIDC for GitHub Actions

- [x] **Create OIDC Identity Provider** in AWS IAM
  - Provider URL: `https://token.actions.githubusercontent.com`
  - Audience: `sts.amazonaws.com`
  - ARN: `arn:aws:iam::673842895830:oidc-provider/token.actions.githubusercontent.com`

- [x] **Create IAM Role** `github-actions-weather-deploy`
  - Trust policy: allows `repo:redleader1/weather-project:*` to assume role
  - Permissions policy: `github-actions-weather-deploy` (v1) — Lambda deploy, S3, CF invalidation
  - Role ARN: `arn:aws:iam::673842895830:role/github-actions-weather-deploy`

### GitHub Actions Workflows

- [x] **Lambda deploy workflow** (`.github/workflows/deploy-lambda.yml`)
  - Trigger: push to `main` that changes files in `aws/lambda/`
  - Uses `dorny/paths-filter` to detect which Lambda changed; separate job per Lambda
  - weather-website → `web_test_3`, node1-api-gateway → `WeatherApi`, admin-panel → `admin-panel`
  - weather-website and admin-panel jobs invalidate their respective CF paths after deploy

- [x] **S3 static site workflow** (`.github/workflows/deploy-site.yml`) — ready for Phase 4
  - Trigger: push to `main` that changes files in `site/`
  - Steps: configure AWS credentials → sync to S3 → CF invalidation

- [x] **Test Lambda deploy end-to-end**
  - Multiple Lambda changes pushed and auto-deployed via GitHub Actions ✅

### Pi Auto-Update via Git Pull

- [ ] **Clone repo on each Pi** (Nodes 2 and 3 first, Node 4 when provisioned)
  ```bash
  cd /home/weather
  git clone https://github.com/your-username/weather-project.git
  ```

- [ ] **Write git-pull update script** for each node
  - Check for changes with `git fetch`
  - If changes exist, `git pull` and restart the collector
  - Log the update with timestamp

- [ ] **Add update script to cron** on each Pi (daily or every few hours)
- [ ] **Test**: push a small change to a collector script, verify Pi picks it up

---

## Phase 3 — Lambda Refactor (JSON API)

Goal: Fix the three documented bugs, refactor the weather Lambda to return JSON
instead of HTML. HTML rendering moves to the browser (Phase 4).

### Bug Fixes

- [x] **Fix timezone bug**
  - `datetime.now(EASTERN)` with `ZoneInfo("America/New_York")` — deployed

- [x] **Fix field casing bug**
  - Stats loop updated to `['tempF', 'pressure', 'co2']` — high/low now populating

- [x] **Fix DynamoDB pagination**
  - `LastEvaluatedKey` loop in place — no more silent truncation

### Weather Lambda → JSON API

- [x] **Refactor `lambda_handler`** to return JSON response instead of HTML
  - Response shape: `{ nodes: [{nodeId, latest, today}], date, asOf }`
  - `latest` contains clean sensor fields only (strips DynamoDB internals)
  - Node 1 legacy `TempF` key normalised to `tempF` in output
  - DynamoDB `Decimal` types handled via custom `serialize()` function

- [x] **Add CORS header** to Lambda response so browser JS can call it
  - `Access-Control-Allow-Origin` driven by `CORS_ORIGIN` env var (default: CloudFront domain)

- [ ] **Update Lambda function name/description** in AWS to reflect new purpose

### Admin Panel Lambda

- [x] **Create `aws/lambda/admin-panel/lambda_function.py`**
  - Queries most recent record per nodeId (reverse-sorted query, Limit=1)
  - Computes minutes since last report in Eastern time
  - Returns JSON: nodeId, lastSeen, minutesAgo, status (ok / warning / offline)
  - Thresholds: >90 min = warning, >180 min = offline
  - NODE_IDS configurable via env var for easy Node 4 addition

- [x] **Deploy admin Lambda to AWS**
  - Function ARN: `arn:aws:lambda:us-east-1:673842895830:function:admin-panel`
  - Execution role: `web_test_3-role-jadlm83n` (shared — has DynamoDB read access)
  - Env vars: `TABLE_NAME=weather-data`, `NODE_IDS=garden-01,outside-01,outside-home`

- [x] **Create Lambda function URL** for admin Lambda
  - URL: `https://7rjw3uf5ebgoxlx3qoo6oekekm0rcbjm.lambda-url.us-east-1.on.aws/`

- [x] **Wire into CloudFront** as `/admin` origin — done as part of Phase 4 distribution update

---

## Phase 4 — S3 Static Website ✅

Goal: Move all HTML/CSS/JS into a static S3 site served by CloudFront. Browser
JavaScript fetches data from the Lambda JSON API. Design updates become S3 uploads.

### S3 Setup

- [x] **Create S3 bucket** `weather-site-static` in us-east-1
- [x] **Disable public access** — CloudFront is the only reader via OAC
- [x] **Create CloudFront Origin Access Control (OAC)** — ID: `E3DHKP1DVBOZME`
- [x] **Update CloudFront distribution** origins and behaviors:
  - Default (`/`) → S3 bucket (static site)
  - `/api/*` → WeatherApiOrigin (weather Lambda)
  - `/admin/*` → AdminPanelOrigin (admin Lambda)
  - Custom error: 403 → index.html / 200 (handles missing S3 keys)
- [x] **Lambda CORS** — already configured with CloudFront domain

### Static Site — `site/` Folder

- [x] **`site/index.html`** — weather dashboard
- [x] **`site/css/styles.css`** — custom styles on top of Bootstrap 5
- [x] **`site/js/weather.js`** — fetches `/api/` and `/admin/` in parallel, renders cards

### Website Features Delivered

- [x] **Bootstrap 5** CDN
- [x] **Current conditions card** per node: temp (°F + °C), humidity, pressure, CO₂ (if available), lux (if available)
- [x] **High / low today** — temp, pressure, CO₂ ranges per node
- [x] **"Last updated" timestamp** per node (minutes ago + exact Eastern timestamp)
- [x] **NWS weather alerts** — fetched from `https://api.weather.gov/alerts/active?zone=NYZ072`
  — update `NWS_ZONE` in `weather.js` for your area
- [x] **60-second auto-refresh** with countdown timer in footer
- [x] **Responsive layout** — Bootstrap grid, mobile-friendly
- [x] **Node status indicator** — ok / warning / offline badge per card; offline cards dimmed

---

## Phase 4.5 — Custom Domain (bigredsweather.com) ✅

Goal: Serve the weather dashboard at `bigredsweather.com` (and `www.bigredsweather.com`)
instead of the default CloudFront domain. Domain already registered in Route 53.

- [x] **Request an SSL/TLS certificate** in AWS Certificate Manager (ACM)
  - Requested in us-east-1 for `bigredsweather.com` and `www.bigredsweather.com`
  - ACM cert ARN: `arn:aws:acm:us-east-1:673842895830:certificate/623d66d6-9114-4531-a4f9-3a7f92463ae8`

- [x] **Fix Route 53 nameserver mismatch**
  - Hosted zone nameservers (ns-1882, ns-142, ns-958, ns-1335) didn't match domain registration
  - Fixed via `aws route53domains update-domain-nameservers` — cert issued minutes after

- [x] **Add the domain as a CloudFront alias**
  - Updated distribution with `bigredsweather.com` and `www.bigredsweather.com` as CNAMEs
  - Attached ACM certificate; TLSv1.2_2021, sni-only

- [x] **Create Route 53 DNS records**
  - `bigredsweather.com` → A Alias → `d33w9ue2h7llgj.cloudfront.net`
  - `www.bigredsweather.com` → A Alias → `d33w9ue2h7llgj.cloudfront.net`

- [x] **Update CORS_ORIGIN env var** on both Lambdas to `https://bigredsweather.com`

- [ ] **Update `NWS_ZONE`** to the correct zone for your location
  - Find your zone at `https://alerts.weather.gov/`
  - Currently using `NYZ072` as placeholder; stored in Secrets Manager `weather/api-keys`

---

## Phase 5 — Secrets Manager ✅

Goal: Learn the Secrets Manager pattern by integrating it into the Lambda functions.
Pis are excluded — their auth is handled by IoT Core certificates.

- [x] **Create secret `weather/api-keys`** in Secrets Manager
  - ARN: `arn:aws:secretsmanager:us-east-1:673842895830:secret:weather/api-keys-FBc9yq`
  - Content: `{"nws_zone": "NYZ072"}` — NWS zone served to the frontend dynamically

- [x] **Create and attach IAM policy** `lambda-weather-secrets`
  - Allows `secretsmanager:GetSecretValue` on the secret ARN
  - Attached to Lambda execution role `web_test_3-role-jadlm83n`

- [x] **Update weather Lambda** to fetch secret at cold start
  - `_load_secrets()` runs at module level — cached for Lambda container lifetime
  - `NWS_ZONE` sourced from secret; falls back to `NYZ072` if Secrets Manager unreachable
  - `nws_zone` included in every API response so the frontend never hardcodes it

- [x] **Update `weather.js`** to read `nws_zone` from API response
  - `fetchAlerts(weather.nws_zone || 'NYZ072')` — no hardcoded zone in frontend

- [x] **Update Lambda env vars** — `SECRET_NAME=weather/api-keys` on `web_test_3`

- [ ] **Update `NWS_ZONE`** to the correct zone for your location
  - Find your zone at `https://alerts.weather.gov/`
  - Update the secret value: `aws secretsmanager update-secret --secret-id weather/api-keys --secret-string '{"nws_zone": "YOUR_ZONE"}'`
  - No Lambda redeploy needed — takes effect on next cold start

- [x] **Pattern documented** — future API keys (e.g. paid weather service) go in this secret

---

## Phase 6 — Provisioning + Shared Utilities

Goal: Make adding a new node (Node 4 and beyond) a repeatable, documented process.
Shared Python utilities reduce copy-paste between node collectors.

### Shared Python Utilities

- [x] **`nodes/shared/payload.py`**
  - `c_to_f(c)`, `now_keys_eastern()`, `ttl_14_days_epoch()`, `build_payload(node_id, readings)`
  - Handles lux (float, rounded to 2dp), co2 (int ppm), defaults for missing sensors

- [x] **`nodes/shared/aws_iot.py`**
  - `connect_mqtt(node_id, cert_dir, endpoint, client_id)` → connected `mqtt_connection`
  - `publish(mqtt_connection, node_id, payload)` — publishes to `weather/{node_id}/telemetry`
  - `disconnect_mqtt(mqtt_connection)` — clean disconnect

- [x] **Update `nodes/node-02-garden/collector.py`** to use shared utilities
- [x] **Update `nodes/node-03-outside-home/collector.py`** to use shared utilities
- [ ] **Test both nodes still publish correctly** after refactor (deploy via git push, verify in DynamoDB)

### Provisioning Scripts

- [x] **`provisioning/provision-iot.sh`**
  - Args: `NODE_ID`
  - Creates IoT Thing, certificate + key pair, attaches `weather-node-policy`
  - Writes cert files to `certs/` (gitignored)

- [x] **`provisioning/setup-pi.sh`**
  - Args: `NODE_ID`, `PI_IP`, optional `PI_USER` (default: `weather`)
  - SSHes into Pi: installs deps, creates venv, clones repo, adds cron entries

- [x] **`provisioning/README.md`** — 9-step end-to-end guide for provisioning a new node

---

## Phase 7 — Node 4

Goal: Commission the fourth node using the provisioning scripts built in Phase 6.

- [ ] **Confirm sensor model** — update `nodes/node-04-tbd/README.md`
- [ ] **Assign `nodeId`** and update CLAUDE.md node inventory
- [ ] **Run `provision-iot.sh`** to register in IoT Core
- [ ] **Run `setup-pi.sh`** on the Pi
- [ ] **Verify data appears in `weather-data` DynamoDB** under the new `nodeId`
- [ ] **Verify node appears in the website dashboard**
- [ ] **Update `nodes/node-04-tbd/README.md`** with final sensor and location details

---

## Ongoing / Housekeeping

- [ ] Delete old root-level folders once comfortable: `mylamda/`, `myLamnda2/`,
  `collection-scripts/`, `misc-scripts/`, `backups/`, `project/`
- [ ] Confirm IoT Core has a rule for each active node's topic
- [ ] Review DynamoDB on-demand billing after 30 days — confirm cost is reasonable
- [ ] Add CloudWatch alarm on Lambda error rate (simple, free tier)
