"""
shared/aws_iot.py — MQTT connection helpers for all weather station nodes.

Usage in a collector:
    import sys, os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'shared'))
    from aws_iot import connect_mqtt, publish, disconnect_mqtt
"""

import json
from awscrt import mqtt
from awsiot import mqtt_connection_builder

ENDPOINT = "a2v8psfnp297g7-ats.iot.us-east-1.amazonaws.com"
CERT_DIR  = "/home/weather/ws"


def connect_mqtt(
    node_id:   str,
    cert_dir:  str = CERT_DIR,
    endpoint:  str = ENDPOINT,
    client_id: str = None,
):
    """
    Create and connect an MQTT connection for the given node.

    Expects certificate files at:
        {cert_dir}/{node_id}.cert.pem
        {cert_dir}/{node_id}.private.key
        {cert_dir}/root-CA.crt          ← shared across all nodes

    Args:
        node_id:   The node's identifier (e.g. 'outside-home').
        cert_dir:  Directory containing the node's cert files.
                   Defaults to /home/weather/ws (Node 3 / standard layout).
        endpoint:  AWS IoT Core endpoint.
        client_id: MQTT client ID. Defaults to 'weather-{node_id}'.
                   Override when hostname uniqueness is needed (e.g. Node 2).

    Returns:
        A connected mqtt_connection object.
    """
    if client_id is None:
        client_id = f"weather-{node_id}"

    mqtt_connection = mqtt_connection_builder.mtls_from_path(
        endpoint=endpoint,
        cert_filepath=f"{cert_dir}/{node_id}.cert.pem",
        pri_key_filepath=f"{cert_dir}/{node_id}.private.key",
        ca_filepath=f"{cert_dir}/root-CA.crt",
        client_id=client_id,
        clean_session=False,
        keep_alive_secs=30,
    )

    mqtt_connection.connect().result()
    return mqtt_connection


def publish(mqtt_connection, node_id: str, payload: dict) -> None:
    """
    Publish a payload dict to the node's telemetry topic.

    Topic: weather/{node_id}/telemetry
    QoS:   AT_LEAST_ONCE
    """
    topic = f"weather/{node_id}/telemetry"
    mqtt_connection.publish(
        topic=topic,
        payload=json.dumps(payload),
        qos=mqtt.QoS.AT_LEAST_ONCE,
    )


def disconnect_mqtt(mqtt_connection) -> None:
    """Cleanly disconnect from AWS IoT Core."""
    mqtt_connection.disconnect().result()
