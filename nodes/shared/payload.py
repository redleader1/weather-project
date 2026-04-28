"""
shared/payload.py — Standard payload helpers for all weather station nodes.

Usage in a collector:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
    from payload import build_payload
"""

from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")


def c_to_f(c: float) -> float:
    """Convert Celsius to Fahrenheit, rounded to 2 decimal places."""
    return round((c * 9 / 5) + 32, 2)


def now_keys_eastern() -> tuple[str, str]:
    """
    Return (eventDateDay, eventTimestamp) in Eastern time.
    eventDateDay:   'YYYY-MM-DD'
    eventTimestamp: 'YYYY-MM-DD HH:MM'
    """
    dt = datetime.now(EASTERN)
    return dt.strftime("%Y-%m-%d"), dt.strftime("%Y-%m-%d %H:%M")


def ttl_14_days_epoch() -> int:
    """Return Unix epoch (seconds) 14 days from now (UTC)."""
    return int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp())


def build_payload(node_id: str, readings: dict) -> dict:
    """
    Build a complete DynamoDB / MQTT payload from raw sensor readings.

    Required keys in readings:
        tempC     (float) — temperature in Celsius
        humidity  (float) — relative humidity %
        pressure  (float) — barometric pressure in hPa

    Optional keys (default to 0 if absent):
        lux  (float) — ambient light in lux
        co2  (int)   — CO2 concentration in ppm

    Returns a dict matching the standard DynamoDB schema:
        nodeId, eventTimestamp, eventDateDay,
        tempC, tempF, humidity, pressure, lux, co2, 14DayTTL
    """
    event_date_day, event_timestamp = now_keys_eastern()

    temp_c = round(float(readings["tempC"]), 2)
    temp_f = c_to_f(temp_c)

    return {
        "nodeId":         node_id,
        "eventTimestamp": event_timestamp,
        "eventDateDay":   event_date_day,
        "tempC":          temp_c,
        "tempF":          temp_f,
        "humidity":       round(float(readings["humidity"]), 2),
        "pressure":       round(float(readings["pressure"]), 2),
        "lux":            round(float(readings.get("lux", 0)), 2),
        "co2":            int(readings.get("co2", 0)),    # CO2 is always integer ppm
        "14DayTTL":       ttl_14_days_epoch(),
    }
