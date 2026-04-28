import boto3
import json
import logging
import math
import os
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME   = os.environ.get('TABLE_NAME',   'weather-data')
CORS_ORIGIN  = os.environ.get('CORS_ORIGIN',  'https://bigredsweather.com')
SECRET_NAME  = os.environ.get('SECRET_NAME',  'weather/api-keys')

dynamodb = boto3.resource('dynamodb')
table    = dynamodb.Table(TABLE_NAME)

EASTERN = ZoneInfo("America/New_York")

# ── Secrets Manager — loaded once at cold start ─────────────────────
# Fetching outside the handler means the secret is cached for the
# lifetime of the Lambda container (typically minutes to hours).
# To rotate a value, update the secret in AWS — the next cold start
# picks it up automatically. No redeploy needed.
def _load_secrets():
    try:
        sm  = boto3.client('secretsmanager', region_name='us-east-1')
        raw = sm.get_secret_value(SecretId=SECRET_NAME)['SecretString']
        return json.loads(raw)
    except Exception as e:
        logger.warning(f"Could not load secrets ({e}) — using defaults")
        return {}

_secrets = _load_secrets()
NWS_ZONE = _secrets.get('nws_zone', 'NYZ072')

# Sensor fields to include in the API response (strips DynamoDB internals
# like 14DayTTL, eventDateDay, nodeId which appears at the parent level).
SENSOR_FIELDS = ['eventTimestamp', 'tempF', 'tempC', 'humidity', 'pressure', 'lux', 'co2']


def serialize(val):
    """Convert a DynamoDB Decimal to int or float for JSON output."""
    if isinstance(val, Decimal):
        return int(val) if val % 1 == 0 else float(val)
    return val


def clean_reading(item):
    """
    Return a dict containing only sensor fields from a raw DynamoDB item.
    Normalises Node 1's legacy 'TempF' key → 'tempF' so all nodes are consistent.
    """
    reading = {}
    for field in SENSOR_FIELDS:
        if field in item:
            reading[field] = serialize(item[field])

    # Node 1 sends TempF (capital T and F) — normalise to tempF
    if 'tempF' not in reading and 'TempF' in item:
        reading['tempF'] = serialize(item['TempF'])

    return reading


def get_daily_data():
    """
    Query today's records (Eastern time) and return a list of per-node dicts,
    each containing the latest reading and daily high/low stats.
    """
    current_day = datetime.now(EASTERN).strftime('%Y-%m-%d')
    logger.info(f"Querying for records on: {current_day}")

    # Paginated query — follows LastEvaluatedKey until all items are fetched
    items = []
    kwargs = {
        'IndexName': 'eventDateDay-index',
        'KeyConditionExpression': boto3.dynamodb.conditions.Key('eventDateDay').eq(current_day),
    }
    while True:
        response = table.query(**kwargs)
        items.extend(response.get('Items', []))
        last_key = response.get('LastEvaluatedKey')
        if not last_key:
            break
        kwargs['ExclusiveStartKey'] = last_key

    logger.info(f"Total items fetched: {len(items)}")

    node_stats = {}
    for item in items:
        node_id = item['nodeId']
        if node_id not in node_stats:
            node_stats[node_id] = {
                'latest':       item,
                'max_tempF':    -math.inf,
                'min_tempF':    math.inf,
                'max_pressure': -math.inf,
                'min_pressure': math.inf,
                'max_co2':      -math.inf,
                'min_co2':      math.inf,
            }

        stats = node_stats[node_id]

        # Track the most recent record
        if item['eventTimestamp'] > stats['latest']['eventTimestamp']:
            stats['latest'] = item

        # Accumulate daily stats — lowercase keys match current standard payload
        for key in ['tempF', 'pressure', 'co2']:
            if key in item:
                value = float(item[key])
                stats[f'max_{key}'] = max(value, stats[f'max_{key}'])
                stats[f'min_{key}'] = min(value, stats[f'min_{key}'])

    nodes = []
    for node_id, stats in sorted(node_stats.items()):
        today = {
            'maxTempF':    round(stats['max_tempF'],    2) if stats['max_tempF']    != -math.inf else None,
            'minTempF':    round(stats['min_tempF'],    2) if stats['min_tempF']    != math.inf  else None,
            'maxPressure': round(stats['max_pressure'], 2) if stats['max_pressure'] != -math.inf else None,
            'minPressure': round(stats['min_pressure'], 2) if stats['min_pressure'] != math.inf  else None,
            'maxCo2':      round(stats['max_co2'],      2) if stats['max_co2']      != -math.inf else None,
            'minCo2':      round(stats['min_co2'],      2) if stats['min_co2']      != math.inf  else None,
        }
        nodes.append({
            'nodeId': node_id,
            'latest': clean_reading(stats['latest']),
            'today':  today,
        })

    return {
        'nodes':    nodes,
        'date':     current_day,
        'asOf':     datetime.now(EASTERN).strftime('%Y-%m-%d %I:%M %p ET'),
        'nws_zone': NWS_ZONE,
    }


def lambda_handler(event, context):
    cors_headers = {
        'Content-Type':                 'application/json',
        'Access-Control-Allow-Origin':  CORS_ORIGIN,
        'Access-Control-Allow-Methods': 'GET',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    try:
        data = get_daily_data()
        logger.info(f"Returning data for {len(data['nodes'])} nodes.")
        return {
            'statusCode': 200,
            'body':       json.dumps(data, default=serialize),
            'headers':    cors_headers,
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body':       json.dumps({'error': 'Internal server error'}),
            'headers':    cors_headers,
        }
