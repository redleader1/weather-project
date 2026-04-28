#!/usr/bin/env bash
set -euo pipefail

LOG="/home/weather/ws/cron_bme280.log"
exec >>"$LOG" 2>&1

echo "----- $(date) run_bme280.sh starting -----"

export HOME="/home/weather"
export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

cd /home/weather/ws

ENDPOINT="a2v8psfnp297g7-ats.iot.us-east-1.amazonaws.com"

# Wait for network connectivity
echo "$(date) waiting for network..."
for i in {1..60}; do
  if ping -c 1 -W 1 1.1.1.1 >/dev/null 2>&1; then
    echo "$(date) network OK"
    break
  fi
  sleep 2
done

# Wait for DNS resolution of IoT endpoint
echo "$(date) waiting for DNS for $ENDPOINT ..."
for i in {1..120}; do
  if /home/weather/ws/.venv/bin/python - <<PY >/dev/null 2>&1
import socket
socket.gethostbyname("$ENDPOINT")
PY
  then
    echo "$(date) DNS OK"
    break
  fi
  sleep 2
done

# Log resolver state if DNS still failing — then bail
if ! /home/weather/ws/.venv/bin/python - <<PY >/dev/null 2>&1
import socket
socket.gethostbyname("$ENDPOINT")
PY
then
  echo "$(date) ERROR: DNS still failing"
  echo "---- /etc/resolv.conf ----"
  cat /etc/resolv.conf || true
  echo "--------------------------"
  exit 1
fi

source /home/weather/ws/.venv/bin/activate

# Prevent duplicate processes
if pgrep -f "/home/weather/ws/BME280-collection_AWSIOT.py" >/dev/null; then
  echo "$(date) publisher already running; exiting"
  exit 0
fi

echo "$(date) starting publisher..."
nohup python /home/weather/ws/BME280-collection_AWSIOT.py \
  >> /home/weather/ws/weather.log 2>&1 &

sleep 1
pgrep -af "/home/weather/ws/BME280-collection_AWSIOT.py" || true

echo "----- $(date) run_bme280.sh done -----"
