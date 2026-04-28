#!/usr/bin/env bash
set -euo pipefail

LOG="/home/weather/weather-station/cron_garden.log"
exec >>"$LOG" 2>&1

echo "----- $(date) run_garden.sh starting -----"

export PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"

cd /home/weather/weather-station

ENDPOINT="a2v8psfnp297g7-ats.iot.us-east-1.amazonaws.com"

# Wait for DNS at boot (up to 4 minutes)
for i in {1..120}; do
  if /home/weather/weather-station/garden/bin/python - <<PY >/dev/null 2>&1
import socket
socket.gethostbyname("$ENDPOINT")
PY
  then
    break
  fi
  sleep 2
done

# Prevent duplicate processes
if pgrep -f "/home/weather/weather-station/garden_publisher.py" >/dev/null; then
  echo "$(date) already running"
  exit 0
fi

echo "$(date) starting publisher"
nohup /home/weather/weather-station/garden/bin/python \
  /home/weather/weather-station/garden_publisher.py \
  >> /home/weather/weather-station/garden.log 2>&1 &
