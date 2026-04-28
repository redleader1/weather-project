# Weather Station — Project Roadmap & Checklist

This document captures every planned task discussed. Work through phases in order —
each phase unblocks the next. Check boxes off as tasks are completed.

Last updated: 2026-04-25

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

- [ ] **Initialize git** in the `weather-project/` folder
  ```bash
  git init
  git branch -M main
  ```

- [ ] **Create `.gitignore`** — must exclude:
  ```
  # Credentials — never commit
  *.pem
  *.key
  *.crt

  # Python
  .venv/
  venv/
  __pycache__/
  *.pyc

  # macOS
  .DS_Store

  # Build artifacts
  *.zip
  *.pkg

  # Archive folder — large, not useful in git
  archive/

  # IDE
  *.code-workspace
  ```

- [ ] **Create GitHub repository** (private recommended)
- [ ] **Initial commit and push**
- [ ] **Protect `main` branch** — require PR or direct push only from your account

### AWS IAM OIDC for GitHub Actions

- [ ] **Create OIDC Identity Provider** in AWS IAM
  - Provider URL: `https://token.actions.githubusercontent.com`
  - Audience: `sts.amazonaws.com`

- [ ] **Create IAM Role** `github-actions-weather-deploy`
  - Trust policy: allow your specific GitHub repo to assume this role
  - Permissions needed:
    - `lambda:UpdateFunctionCode` on your Lambda ARNs
    - `s3:PutObject`, `s3:DeleteObject` on the static site bucket (Phase 4)
    - `cloudfront:CreateInvalidation` on distribution `E2TUI9GEVJDFSQ`
    - `secretsmanager:GetSecretValue` (Phase 5, add later)

- [ ] **Note the Role ARN** — needed in GitHub Actions workflows

### GitHub Actions Workflows

- [ ] **Lambda deploy workflow** (`.github/workflows/deploy-lambda.yml`)
  - Trigger: push to `main` that changes files in `aws/lambda/`
  - Steps: configure AWS credentials (OIDC) → zip Lambda → update function code → CF invalidation
  - Separate job per Lambda (weather-website, node1-api-gateway, admin-panel)

- [ ] **S3 static site workflow** (`.github/workflows/deploy-site.yml`) — Phase 4
  - Trigger: push to `main` that changes files in `site/`
  - Steps: configure AWS credentials → sync to S3 → CF invalidation

- [ ] **Test Lambda deploy end-to-end**
  - Make a small change to `aws/lambda/weather-website/lambda_function.py`
  - Push to `main`, watch Actions tab, verify Lambda updated in AWS

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

- [ ] **Fix timezone bug**
  - Replace `datetime.now()` with `datetime.now(ZoneInfo("America/New_York"))`
  - Affects `get_daily_records()` — wrong day queried after ~7–8pm Eastern currently

- [ ] **Fix field casing bug**
  - Update min/max stats loop from `['TempF', 'Pressure', 'CO2']`
    to `['tempF', 'pressure', 'co2']`
  - This unblocks high/low display which has been broken since field casing was standardized

- [ ] **Fix DynamoDB pagination**
  - Wrap `table.query()` in a loop that follows `LastEvaluatedKey`
  - Without this, days with many records (all nodes, every minute) silently truncate at 1 MB

### Weather Lambda → JSON API

- [ ] **Refactor `lambda_handler`** to return JSON response instead of HTML
  ```json
  {
    "nodes": [
      {
        "nodeId": "outside-home",
        "latest": { ...most recent record... },
        "today": { "maxTempF": 72.5, "minTempF": 58.2, ... }
      }
    ],
    "asOf": "2025-01-15 14:30 ET"
  }
  ```

- [ ] **Add CORS header** to Lambda response so browser JS can call it
  - `Access-Control-Allow-Origin: https://d33w9ue2h7llgj.cloudfront.net`

- [ ] **Update Lambda function name/description** in AWS to reflect new purpose

### Admin Panel Lambda

- [ ] **Create `aws/lambda/admin-panel/lambda_function.py`**
  - Query DynamoDB for most recent record per `nodeId`
  - Compute minutes since last report for each node
  - Return JSON: node name, last seen timestamp, minutes ago, status (ok / warning / offline)
  - Thresholds: >90 min = warning, >180 min = offline

- [ ] **Deploy admin Lambda to AWS**
- [ ] **Create Lambda function URL** for admin Lambda
- [ ] **Wire into CloudFront** as `/admin` origin (Phase 4)

---

## Phase 4 — S3 Static Website

Goal: Move all HTML/CSS/JS into a static S3 site served by CloudFront. Browser
JavaScript fetches data from the Lambda JSON API. Design updates become S3 uploads.

### S3 Setup

- [ ] **Create S3 bucket** `weather-site-static` (or similar) in us-east-1
- [ ] **Disable public access** — CloudFront will be the only reader (use OAC)
- [ ] **Create CloudFront Origin Access Control (OAC)** for the S3 bucket
- [ ] **Update CloudFront distribution** origins and behaviors:
  - Default (`/`) → S3 bucket (static site)
  - `/api/*` → weather Lambda URL
  - `/admin/*` → admin Lambda URL
- [ ] **Update Lambda CORS** to allow the CloudFront domain

### Static Site — `site/` Folder

- [ ] **Create `site/` folder** in project root (this goes in GitHub)
  ```
  site/
  ├── index.html
  ├── admin.html
  ├── css/
  │   └── styles.css
  └── js/
      └── weather.js
  ```

- [ ] **`weather.js`** — fetches `/api` on load and every 60 seconds, renders data into DOM
- [ ] **`index.html`** — weather dashboard UI (see Phase 4 design tasks below)
- [ ] **`admin.html`** — node health UI

### Website Design

- [ ] **Bootstrap 5** (upgrade from 4.3.1)
- [ ] **Weather icons** — inline SVG set (no external dependencies)
- [ ] **Current conditions card** per node: temp, humidity, pressure, CO2 (if available), lux (if available)
- [ ] **High / low today** — now works once field casing bug is fixed
- [ ] **"Last updated" timestamp** per node with Eastern timezone
- [ ] **NWS weather alerts** — fetch from `https://api.weather.gov/alerts/active?zone=NYZ072`
  (update zone code for your area — free, no API key required)
- [ ] **60-second auto-refresh** of data (no page reload — just re-fetch JSON)
- [ ] **Responsive layout** — works on phone and desktop
- [ ] **Node status indicator** — subtle visual if a node hasn't reported recently

---

## Phase 5 — Secrets Manager

Goal: Learn the Secrets Manager pattern by integrating it into the Lambda functions.
Pis are excluded — their auth is handled by IoT Core certificates.

- [ ] **Create a placeholder secret** in Secrets Manager (e.g. `weather/api-keys`)
  - Even if empty now, establishes the pattern
  - Use SecretString with JSON: `{"nws_zone": "NYZ072"}` (config, not really secret, but good practice)

- [ ] **Update Lambda IAM roles** with `secretsmanager:GetSecretValue` on the secret ARN

- [ ] **Update Lambda code** to fetch the secret at cold start
  ```python
  import boto3, json
  sm = boto3.client('secretsmanager', region_name='us-east-1')
  secret = json.loads(sm.get_secret_value(SecretId='weather/api-keys')['SecretString'])
  ```

- [ ] **Document the pattern** — when a real API key is needed (e.g. paid weather service),
  add it here rather than in environment variables

- [ ] **Update GitHub Actions IAM role** with secretsmanager permissions if needed for deploy

---

## Phase 6 — Provisioning + Shared Utilities

Goal: Make adding a new node (Node 4 and beyond) a repeatable, documented process.
Shared Python utilities reduce copy-paste between node collectors.

### Shared Python Utilities

- [ ] **`nodes/shared/payload.py`**
  - `now_keys_eastern()` → `(eventDateDay, eventTimestamp)`
  - `ttl_14_days_epoch()` → int
  - `build_payload(node_id, readings)` → full standard dict with defaults for lux/co2
  - `c_to_f(c)` → float

- [ ] **`nodes/shared/aws_iot.py`**
  - `connect_mqtt(node_id, cert_dir, endpoint)` → connected `mqtt_connection`
  - Encapsulates all the `mtls_from_path` boilerplate

- [ ] **Update `nodes/node-02-garden/collector.py`** to use shared utilities
- [ ] **Update `nodes/node-03-outside-home/collector.py`** to use shared utilities
- [ ] **Test both nodes still publish correctly** after refactor

### Provisioning Scripts

- [ ] **`provisioning/provision-iot.sh`**
  - Takes `NODE_ID` as argument
  - Creates IoT Thing in AWS IoT Core
  - Creates and downloads certificate + private key
  - Creates and attaches IoT policy
  - Outputs cert files ready to copy to Pi

- [ ] **`provisioning/setup-pi.sh`**
  - Takes `NODE_ID` and sensor type as arguments
  - Installs Python dependencies (`awsiotsdk`, `adafruit-*` libs)
  - Creates Python venv at `/home/weather/weather-station/`
  - Clones GitHub repo
  - Copies appropriate `collector.py` and `run.sh` for the node
  - Adds cron entry for `run.sh`
  - Adds cron entry for git-pull update script

- [ ] **`provisioning/README.md`** — step-by-step instructions for provisioning a new node end-to-end

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
