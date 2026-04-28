from awscrt import mqtt
from awsiot import mqtt_connection_builder

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import json
import time

import board
import adafruit_bme280


def c_to_f(c: float) -> float:
    return (c * 9 / 5) + 32


def now_keys_eastern():
    dt = datetime.now(ZoneInfo("America/New_York"))
    return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d %H:%M")


def ttl_14_days_epoch():
    return int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp())


# ---------- BME280 ----------
i2c = board.I2C()
bme280 = adafruit_bme280.Adafruit_BME280_I2C(i2c)

# ---------- AWS IoT ----------
endpoint = "a2v8psfnp297g7-ats.iot.us-east-1.amazonaws.com"

client_id = "weather-outside-home"
node_id = "outside-home"

cert_filepath = "/home/weather/ws/outside-home.cert.pem"
pri_key_filepath = "/home/weather/ws/outside-home.private.key"
ca_filepath = "/home/weather/ws/root-CA.crt"

topic = f"weather/{node_id}/telemetry"

mqtt_connection = mqtt_connection_builder.mtls_from_path(
    endpoint=endpoint,
    cert_filepath=cert_filepath,
    pri_key_filepath=pri_key_filepath,
    ca_filepath=ca_filepath,
    client_id=client_id,
    clean_session=False,
    keep_alive_secs=30,
)

mqtt_connection.connect().result()
print("Connected to AWS IoT Core")

try:
    while True:
        temp_c = round(float(bme280.temperature), 2)
        temp_f = round(c_to_f(temp_c), 2)
        humidity = round(float(bme280.humidity), 2)
        pressure = round(float(bme280.pressure), 2)  # hPa

        eventDateDay, eventTimestamp = now_keys_eastern()

        payload = {
            "nodeId": node_id,
            "eventTimestamp": eventTimestamp,
            "eventDateDay": eventDateDay,

            "lux": 0,
            "pressure": pressure,
            "tempC": temp_c,
            "tempF": temp_f,
            "humidity": humidity,

            "14DayTTL": ttl_14_days_epoch(),
        }

        mqtt_connection.publish(
            topic=topic,
            payload=json.dumps(payload),
            qos=mqtt.QoS.AT_LEAST_ONCE,
        )

        print(f"Published: {payload}")
        time.sleep(60)

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    mqtt_connection.disconnect().result()
    print("Disconnected")
