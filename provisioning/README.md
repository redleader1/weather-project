# Provisioning a New Weather Node

Follow these steps in order to add a new node to the weather station system.

---

## Prerequisites

- AWS CLI configured on your Mac as `eriks_mac` (or any profile with IoT + IAM access)
- SSH key auth set up for `weather@<PI_IP>`
- A Raspberry Pi with Raspbian/Raspberry Pi OS installed
- Sensors wired to the Pi's I2C bus

---

## Step 1 — Choose a `nodeId`

Pick a descriptive, lowercase, hyphenated ID. Examples: `outside-bedroom`, `basement-01`.

Update `CLAUDE.md` → Node Inventory table with the new node's details.

---

## Step 2 — Register the Node in AWS IoT Core

Run from the project root on your Mac:

```bash
./provisioning/provision-iot.sh <NODE_ID>
```

This creates:
- An IoT Thing named `<NODE_ID>`
- A certificate + private key pair (active, attached to the Thing)
- The `weather-node-policy` IoT policy (created on first run; reused thereafter)
- Output files in `certs/` (gitignored — never commit these)

---

## Step 3 — Copy Certs to the Pi

```bash
scp certs/<NODE_ID>.cert.pem \
    certs/<NODE_ID>.private.key \
    certs/root-CA.crt \
    weather@<PI_IP>:/home/weather/ws/
```

---

## Step 4 — Write the Collector Script

Create `nodes/node-<NODE_ID>/collector.py`. Use `nodes/node-03-outside-home/collector.py`
as the template. Key things to change:

- `NODE_ID` — your new node's ID
- `CERT_DIR` — path on the Pi where certs were copied (default: `/home/weather/ws`)
- Sensor imports and reads — match the sensors actually wired to this Pi

The shared utilities in `nodes/shared/` handle all payload building and MQTT connection
boilerplate — your collector only needs sensor reads and a call to `build_payload`.

---

## Step 5 — Set Up the Pi

```bash
./provisioning/setup-pi.sh <NODE_ID> <PI_IP>
```

This SSHes into the Pi and:
- Installs system packages (`python3-venv`, `git`, `i2c-tools`)
- Creates a Python venv at `/home/weather/ws/.venv/`
- Installs Python dependencies (`awsiotsdk`, `adafruit-*`)
- Clones the GitHub repo to `/home/weather/ws/weather-project/`
- Installs cron entries: daily `git pull` + reboot auto-start

---

## Step 6 — Enable I2C and Test

SSH into the Pi, then:

```bash
# Enable I2C (if not already done)
sudo raspi-config   # Interface Options → I2C → Enable

# Verify sensors are detected on the I2C bus
i2cdetect -y 1

# Run the collector manually to check for errors
source /home/weather/ws/.venv/bin/activate
python /home/weather/ws/weather-project/nodes/node-<NODE_ID>/collector.py
```

You should see `Published: {...}` lines every 60 seconds.

---

## Step 7 — Verify Data in DynamoDB

In the AWS console (or via CLI), check `weather-data` for records with the new `nodeId`:

```bash
aws dynamodb query \
    --table-name weather-data \
    --index-name eventDateDay-index \
    --key-condition-expression "eventDateDay = :d" \
    --expression-attribute-values '{":d": {"S": "'"$(date +%Y-%m-%d)"'"}}' \
    --filter-expression "nodeId = :n" \
    --expression-attribute-values '{":d": {"S": "'"$(date +%Y-%m-%d)"'"}, ":n": {"S": "<NODE_ID>"}}' \
    --region us-east-1 \
    --query 'Items[*].{node: nodeId.S, ts: eventTimestamp.S, temp: tempF.N}' \
    --output table
```

---

## Step 8 — Add Node to the Admin Panel

Update the `NODE_IDS` environment variable on the `admin-panel` Lambda in AWS:

```bash
aws lambda update-function-configuration \
    --function-name admin-panel \
    --environment 'Variables={TABLE_NAME=weather-data,NODE_IDS=garden-01,outside-01,outside-home,<NODE_ID>}' \
    --region us-east-1
```

Then invalidate CloudFront so the site picks up the new node:

```bash
aws cloudfront create-invalidation \
    --distribution-id E2TUI9GEVJDFSQ \
    --paths "/*"
```

---

## Step 9 — Add Node Name to the Website

Edit `site/js/weather.js` → `NODE_NAMES` map:

```js
const NODE_NAMES = {
  'garden-01':    'Garden',
  'outside-01':   "Parents' House",
  'outside-home': 'Outside (Home)',
  '<NODE_ID>':    'Your Display Name Here',   // ← add this line
};
```

Commit and push — GitHub Actions will deploy to S3 automatically.

---

## Troubleshooting

**Collector connects but no data in DynamoDB**
- Check the IoT Rule in AWS IoT Core → Message Routing → Rules → `smithfield_test`
- Verify the rule's SQL filter matches the topic: `weather/+/telemetry`
- Check the rule's IAM role has DynamoDB write permission on `weather-data`

**Certificate error at connect**
- Confirm cert files are in the expected `CERT_DIR` on the Pi
- Confirm the cert filenames match: `{node_id}.cert.pem`, `{node_id}.private.key`, `root-CA.crt`

**Sensor not found (I2C error)**
- Run `i2cdetect -y 1` to list detected I2C addresses
- Check wiring; confirm I2C is enabled (`sudo raspi-config`)
