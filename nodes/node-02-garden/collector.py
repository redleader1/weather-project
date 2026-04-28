from awscrt import mqtt
from awsiot import mqtt_connection_builder

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import time
import socket

import board
import busio
import adafruit_bmp3xx
from adafruit_scd4x import SCD4X
import adafruit_bh1750


# ---------------- Helpers ----------------

def c_to_f(c: float) -> float:
    return (c * 9 / 5) + 32


def now_keys_eastern():
    dt = datetime.now(ZoneInfo("America/New_York"))
    return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d %H:%M")


def ttl_14_days_epoch():
    return int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp())


# ---------------- Sensors ----------------

i2c = board.I2C()  # uses Blinka; shared I2C bus
bmp = adafruit_bmp3xx.BMP3XX_I2C(i2c)   # pressure (hPa)
scd = SCD4X(i2c)                        # CO2 (ppm), temp (C), RH (%)
lux_sensor = adafruit_bh1750.BH1750(i2c)  # light (lux)

scd.start_periodic_measurement()


# ---------------- AWS IoT / MQTT ----------------

ENDPOINT  = "a2v8psfnp297g7-ats.iot.us-east-1.amazonaws.com"

# Make client_id unique per Pi to avoid unexpected disconnects
CLIENT_ID = f"weather-garden-{socket.gethostname()}"
NODE_ID   = "garden-01"

CERT_PATH = "/home/weather/weather-station/certs/garden-01.cert.pem"
KEY_PATH  = "/home/weather/weather-station/certs/garden-01.private.key"
CA_PATH   = "/home/weather/weather-station/certs/root-CA.crt"

TOPIC = f"weather/{NODE_ID}/telemetry"

PUBLISH_EVERY_SEC = 60


def main():
    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=ENDPOINT,
        cert_filepath=CERT_PATH,
        pri_key_filepath=KEY_PATH,
        ca_filepath=CA_PATH,
        client_id=CLIENT_ID,
        clean_session=False,
        keep_alive_secs=30,
    )

    mqtt_connection.connect().result()
    print(f"Connected to AWS IoT Core. Publishing to {TOPIC} as {CLIENT_ID}")

    try:
        while True:
            # SCD41 can take a few seconds before first ready
            if not scd.data_ready:
                print("SCD41 not ready yet; waiting...")
                time.sleep(5)
                continue

            # Read sensors
            co2      = int(round(float(scd.CO2)))
            temp_c   = round(float(scd.temperature), 2)   # SCD41 temp as canonical
            temp_f   = round(c_to_f(temp_c), 2)
            humidity = round(float(scd.relative_humidity), 2)
            pressure = round(float(bmp.pressure), 2)       # hPa
            lux      = round(float(lux_sensor.lux), 2)

            eventDateDay, eventTimestamp = now_keys_eastern()

            payload = {
                # DynamoDB keys
                "nodeId":         NODE_ID,
                "eventTimestamp": eventTimestamp,
                # GSI partition key
                "eventDateDay":   eventDateDay,
                # Measurements
                "lux":      lux,
                "pressure": pressure,
                "tempC":    temp_c,
                "tempF":    temp_f,
                "humidity": humidity,
                "co2":      co2,
                # TTL
                "14DayTTL": ttl_14_days_epoch(),
            }

            mqtt_connection.publish(
                topic=TOPIC,
                payload=json.dumps(payload),
                qos=mqtt.QoS.AT_LEAST_ONCE,
            )
            print(f"Published: {payload}")
            time.sleep(PUBLISH_EVERY_SEC)

    except KeyboardInterrupt:
        print("\nStopping...")

    finally:
        mqtt_connection.disconnect().result()
        print("Disconnected")


if __name__ == "__main__":
    main()
