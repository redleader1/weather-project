#!/usr/bin/env bash
# provision-iot.sh — Register a new weather node in AWS IoT Core.
#
# Run this on your Mac (with AWS CLI configured as eriks_mac) BEFORE setting
# up the Pi. It creates the IoT Thing, a dedicated certificate, and attaches
# the standard weather-node policy.
#
# Usage:
#   ./provisioning/provision-iot.sh <NODE_ID>
#
# Example:
#   ./provisioning/provision-iot.sh outside-bedroom
#
# Output:
#   Creates certs/{NODE_ID}.cert.pem
#           certs/{NODE_ID}.private.key
#           certs/root-CA.crt           (shared; only downloaded once)
#   Prints the certificate ARN for reference.
#
# After running this script, copy the certs/ folder to the Pi:
#   scp certs/{NODE_ID}.cert.pem certs/{NODE_ID}.private.key certs/root-CA.crt \
#       weather@<PI_IP>:/home/weather/ws/

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
if [ $# -lt 1 ]; then
    echo "Usage: $0 <NODE_ID>"
    echo "Example: $0 outside-bedroom"
    exit 1
fi

NODE_ID="$1"
REGION="us-east-1"
POLICY_NAME="weather-node-policy"
CERT_DIR="$(dirname "$0")/../certs"
mkdir -p "${CERT_DIR}"

echo "=== Provisioning IoT node: ${NODE_ID} ==="

# ── 1. Create the IoT Thing ───────────────────────────────────────────────────
echo "[1/5] Creating IoT Thing..."
aws iot create-thing \
    --thing-name "${NODE_ID}" \
    --region "${REGION}" \
    --output text \
    --query 'thingArn'

# ── 2. Create certificate + key pair ─────────────────────────────────────────
echo "[2/5] Creating certificate..."
CERT_JSON=$(aws iot create-keys-and-certificate \
    --set-as-active \
    --region "${REGION}")

CERT_ARN=$(echo "${CERT_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['certificateArn'])")
CERT_ID=$(echo  "${CERT_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['certificateId'])")

echo "${CERT_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['certificatePem'])" \
    > "${CERT_DIR}/${NODE_ID}.cert.pem"

echo "${CERT_JSON}" | python3 -c "import sys,json; print(json.load(sys.stdin)['keyPair']['PrivateKey'])" \
    > "${CERT_DIR}/${NODE_ID}.private.key"

chmod 600 "${CERT_DIR}/${NODE_ID}.private.key"
echo "    Certificate ARN: ${CERT_ARN}"

# ── 3. Download root CA (once; skip if already present) ──────────────────────
echo "[3/5] Downloading root CA..."
if [ ! -f "${CERT_DIR}/root-CA.crt" ]; then
    curl -sSL \
        "https://www.amazontrust.com/repository/AmazonRootCA1.pem" \
        -o "${CERT_DIR}/root-CA.crt"
    echo "    Downloaded root-CA.crt"
else
    echo "    root-CA.crt already present, skipping."
fi

# ── 4. Ensure the standard policy exists, then attach it ─────────────────────
echo "[4/5] Attaching policy '${POLICY_NAME}' to certificate..."

# Create the policy if it doesn't exist yet
if ! aws iot get-policy --policy-name "${POLICY_NAME}" --region "${REGION}" > /dev/null 2>&1; then
    echo "    Policy not found — creating it now..."
    aws iot create-policy \
        --policy-name "${POLICY_NAME}" \
        --policy-document '{
            "Version": "2012-10-17",
            "Statement": [{
                "Effect":   "Allow",
                "Action":   ["iot:Connect", "iot:Publish"],
                "Resource": "*"
            }]
        }' \
        --region "${REGION}" \
        --output text \
        --query 'policyArn'
fi

aws iot attach-policy \
    --policy-name "${POLICY_NAME}" \
    --target "${CERT_ARN}" \
    --region "${REGION}"

# ── 5. Attach certificate to the Thing ───────────────────────────────────────
echo "[5/5] Attaching certificate to Thing '${NODE_ID}'..."
aws iot attach-thing-principal \
    --thing-name "${NODE_ID}" \
    --principal "${CERT_ARN}" \
    --region "${REGION}"

# ── Done ──────────────────────────────────────────────────────────────────────
echo ""
echo "=== Done! Cert files written to ${CERT_DIR}/ ==="
echo ""
echo "Next step — copy certs to the Pi:"
echo "  scp ${CERT_DIR}/${NODE_ID}.cert.pem \\"
echo "      ${CERT_DIR}/${NODE_ID}.private.key \\"
echo "      ${CERT_DIR}/root-CA.crt \\"
echo "      weather@<PI_IP>:/home/weather/ws/"
echo ""
echo "Then run:  ./provisioning/setup-pi.sh ${NODE_ID} <PI_IP>"
