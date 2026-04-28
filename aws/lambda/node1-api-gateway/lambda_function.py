"""
Lambda: node1-api-gateway
Triggered by: API Gateway POST /WeatherApi
Endpoint: https://1iawimadei.execute-api.us-east-1.amazonaws.com/prod/WeatherApi

PURPOSE:
    Receives HTTP POST data from Node 1 (parents-house) and writes it to DynamoDB.
    This is the ONLY ingestion path for Node 1. It translates Node 1's ISO 8601
    eventDate field into the eventDateDay + eventTimestamp format used by the table.

WARNING — DO NOT MODIFY THIS LAMBDA WITHOUT EXTREME CARE:
    Node 1 is physically inaccessible. If this Lambda breaks, Node 1 data stops
    flowing with no way to fix the sender. Any schema or field changes must be
    backward-compatible with Node 1's payload format.

NODE 1 PAYLOAD FORMAT (sent by the Pi):
    {
        "nodeId":    "outside-01",
        "eventDate": "2025-01-15T14:30:00-05:00",   # ISO 8601 with timezone offset
        "lux":       123.45,
        "pressure":  1013.25,
        "tempC":     20.50,
        "tempF":     68.90,
        "humidity":  55.20
        # Note: no co2 field (Node 1 has no CO2 sensor)
        # Note: no 14DayTTL (Node 1 records do not auto-expire)
    }

KNOWN ISSUES:
    - No 14DayTTL written — Node 1 records accumulate indefinitely in DynamoDB.
      These must be manually pruned if storage becomes a concern.
    - Uses low-level dynamodb.client (not boto3.resource) — Item values require
      explicit type descriptors e.g. {'S': '...'}, {'N': '...'}.
    - No eventDateDay GSI write — actually it IS written (formatted_day → eventDateDay),
      so Node 1 records do appear in the eventDateDay-index GSI. Good.
"""

import json
import os
import boto3
from datetime import datetime, timezone, timedelta

dynamodb = boto3.client('dynamodb')

TABLE_NAME = os.environ.get('TABLE_NAME', 'weather-data')


def ttl_14_days_epoch():
    return int((datetime.now(timezone.utc) + timedelta(days=14)).timestamp())


def lambda_handler(event, context):
    try:
        # Check if the request body is not None
        if 'body' not in event or event['body'] is None:
            raise ValueError("Request body is empty or None.")

        # Parse the JSON data from the HTTP request body
        data = json.loads(event['body'])

        # Verify that all required fields exist
        required_fields = ['nodeId', 'eventDate', 'lux', 'pressure', 'tempC', 'tempF', 'humidity']
        for field in required_fields:
            if field not in data:
                raise ValueError(f"'{field}' is missing in the JSON data.")

        # Translate ISO 8601 eventDate into the table's two timestamp fields
        parsed_date = datetime.strptime(data['eventDate'], '%Y-%m-%dT%H:%M:%S%z')
        formatted_day       = parsed_date.strftime('%Y-%m-%d')       # eventDateDay
        formatted_timestamp = parsed_date.strftime('%Y-%m-%d %H:%M') # eventTimestamp

        # Write to DynamoDB (low-level client — types must be explicit)
        dynamodb.put_item(
            TableName=TABLE_NAME,
            Item={
                'nodeId':         {'S': data['nodeId']},
                'eventTimestamp': {'S': formatted_timestamp},
                'eventDateDay':   {'S': formatted_day},
                'lux':            {'N': str(data['lux'])},
                'pressure':       {'N': str(data['pressure'])},
                'tempC':          {'N': str(data['tempC'])},
                'tempF':          {'N': str(data['tempF'])},
                'humidity':       {'N': str(data['humidity'])},
                '14DayTTL':       {'N': str(ttl_14_days_epoch())},
            }
        )

        return {
            'statusCode': 200,
            'body': json.dumps('Data stored successfully')
        }

    except Exception as e:
        return {
            'statusCode': 400,
            'body': json.dumps(f'Error: {str(e)}')
        }
