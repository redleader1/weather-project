"""
Node 03 — Outside Home collector
Sensors: BME280 (temperature, humidity, pressure)
nodeId:  outside-home
"""

import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.realpath(__file__)), '..', 'shared'))
from payload import build_payload
from aws_iot import connect_mqtt, publish, disconnect_mqtt

import board
import adafruit_bme280

# ── Config ────────────────────────────────────────────────────────────────────
NODE_ID  = "outside-home"
CERT_DIR = "/home/weather/ws"      # {node_id}.cert.pem, {node_id}.private.key, root-CA.crt

# ── Hardware ──────────────────────────────────────────────────────────────────
i2c    = board.I2C()
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)

# ── Connect ───────────────────────────────────────────────────────────────────
mqtt_connection = connect_mqtt(NODE_ID, cert_dir=CERT_DIR)
print("Connected to AWS IoT Core")

# ── Publish loop ──────────────────────────────────────────────────────────────
try:
    while True:
        readings = {
            "tempC":    bme280.temperature,
            "humidity": bme280.humidity,
            "pressure": bme280.pressure,
            # lux and co2 omitted — node has no light or CO2 sensor; defaults to 0
        }

        payload = build_payload(NODE_ID, readings)
        publish(mqtt_connection, NODE_ID, payload)
        print(f"Published: {payload}")

        time.sleep(60)

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    disconnect_mqtt(mqtt_connection)
    print("Disconnected")
