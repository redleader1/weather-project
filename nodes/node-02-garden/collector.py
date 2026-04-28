"""
Node 02 — Garden collector
Sensors: SCD41 (CO2, temperature, humidity), BMP3XX (pressure), BH1750 (lux)
nodeId:  garden-01
"""

import sys
import os
import socket
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
from payload import build_payload
from aws_iot import connect_mqtt, publish, disconnect_mqtt

import board
import adafruit_bmp3xx
from adafruit_scd4x import SCD4X
import adafruit_bh1750

# ── Config ────────────────────────────────────────────────────────────────────
NODE_ID   = "garden-01"
CERT_DIR  = "/home/weather/weather-station/certs"
# Use hostname in client_id to prevent duplicate-client disconnects if the
# script is restarted while another instance is still connected.
CLIENT_ID = f"weather-garden-{socket.gethostname()}"

PUBLISH_EVERY_SEC = 60

# ── Hardware ──────────────────────────────────────────────────────────────────
i2c        = board.I2C()
bmp        = adafruit_bmp3xx.BMP3XX_I2C(i2c)   # pressure (hPa)
scd        = SCD4X(i2c)                         # CO2 (ppm), temp (°C), humidity (%)
lux_sensor = adafruit_bh1750.BH1750(i2c)        # light (lux)

scd.start_periodic_measurement()

# ── Connect ───────────────────────────────────────────────────────────────────
mqtt_connection = connect_mqtt(NODE_ID, cert_dir=CERT_DIR, client_id=CLIENT_ID)
print(f"Connected to AWS IoT Core as {CLIENT_ID}")

# ── Publish loop ──────────────────────────────────────────────────────────────
try:
    while True:
        # SCD41 updates on its own ~5-second cycle; wait for a fresh reading.
        if not scd.data_ready:
            print("SCD41 not ready yet; waiting...")
            time.sleep(5)
            continue

        readings = {
            "tempC":    scd.temperature,          # SCD41 used as canonical temp source
            "humidity": scd.relative_humidity,
            "pressure": bmp.pressure,
            "co2":      scd.CO2,                  # integer ppm
            "lux":      lux_sensor.lux,
        }

        payload = build_payload(NODE_ID, readings)
        publish(mqtt_connection, NODE_ID, payload)
        print(f"Published: {payload}")

        time.sleep(PUBLISH_EVERY_SEC)

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    scd.stop_periodic_measurement()
    disconnect_mqtt(mqtt_connection)
    print("Disconnected")
