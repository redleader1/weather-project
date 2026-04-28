#!/usr/bin/env bash
# setup-pi.sh — Configure a Raspberry Pi as a new weather station node.
#
# Run this on your Mac AFTER provision-iot.sh and AFTER copying certs to the Pi.
# It SSHes into the Pi and sets up the Python venv, installs dependencies,
# clones the GitHub repo, and installs the cron entries.
#
# Usage:
#   ./provisioning/setup-pi.sh <NODE_ID> <PI_IP> [PI_USER]
#
# Example:
#   ./provisioning/setup-pi.sh outside-bedroom 192.168.1.42
#   ./provisioning/setup-pi.sh outside-bedroom 192.168.1.42 weather
#
# Prerequisites:
#   - SSH key auth set up for weather@<PI_IP>
#   - Certs already copied to /home/weather/ws/ on the Pi
#     (run provision-iot.sh first, then: scp certs/... weather@<PI_IP>:/home/weather/ws/)

set -euo pipefail

# ── Args ──────────────────────────────────────────────────────────────────────
if [ $# -lt 2 ]; then
    echo "Usage: $0 <NODE_ID> <PI_IP> [PI_USER]"
    echo "Example: $0 outside-bedroom 192.168.1.42"
    exit 1
fi

NODE_ID="${1}"
PI_IP="${2}"
PI_USER="${3:-weather}"

REPO_URL="https://github.com/redleader1/weather-project.git"
WORK_DIR="/home/weather/ws"
VENV_DIR="${WORK_DIR}/.venv"
REPO_DIR="${WORK_DIR}/weather-project"
COLLECTOR_SRC="${REPO_DIR}/nodes/node-${NODE_ID}/collector.py"
# On the Pi, the script filename convention differs per node.
# You may need to adjust SCRIPT_NAME if the Pi expects a different filename.
SCRIPT_NAME="collector.py"

echo "=== Setting up Pi at ${PI_USER}@${PI_IP} for node: ${NODE_ID} ==="

ssh "${PI_USER}@${PI_IP}" bash -s << REMOTE
set -euo pipefail

echo "[1/5] Installing system dependencies..."
sudo apt-get update -qq
sudo apt-get install -y -qq python3 python3-pip python3-venv git i2c-tools

echo "[2/5] Creating Python venv at ${VENV_DIR}..."
mkdir -p "${WORK_DIR}"
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

echo "[3/5] Installing Python packages..."
pip install --upgrade pip --quiet
pip install awsiotsdk adafruit-circuitpython-bme280 adafruit-circuitpython-bmp3xx \
            adafruit-circuitpython-scd4x adafruit-circuitpython-bh1750 --quiet

echo "[4/5] Cloning / updating GitHub repo..."
if [ -d "${REPO_DIR}/.git" ]; then
    echo "    Repo already exists — pulling latest..."
    git -C "${REPO_DIR}" pull
else
    git clone "${REPO_URL}" "${REPO_DIR}"
fi

echo "[5/5] Installing cron entries..."

# Auto-update cron: pull latest from GitHub daily at 3 AM
UPDATE_CRON="0 3 * * * cd ${REPO_DIR} && git pull >> ${WORK_DIR}/git-pull.log 2>&1"

# Collector restart-on-reboot entry
BOOT_CRON="@reboot sleep 30 && ${WORK_DIR}/run.sh >> ${WORK_DIR}/cron.log 2>&1"

# Add cron entries if not already present
(crontab -l 2>/dev/null || true; echo "${UPDATE_CRON}"; echo "${BOOT_CRON}") \
    | sort -u | crontab -

echo ""
echo "=== Pi setup complete ==="
echo ""
echo "Next steps (manual):"
echo "  1. Enable I2C on the Pi if not already enabled:"
echo "       sudo raspi-config  → Interface Options → I2C → Enable"
echo "  2. Verify sensors are detected:"
echo "       i2cdetect -y 1"
echo "  3. Run a manual test:"
echo "       source ${VENV_DIR}/bin/activate && python ${COLLECTOR_SRC}"
echo "  4. Reboot to confirm cron starts the collector automatically:"
echo "       sudo reboot"
REMOTE

echo ""
echo "=== Remote setup finished ==="
