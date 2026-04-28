import boto3
import json
import logging
import os
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME  = os.environ.get('TABLE_NAME',  'weather-data')
CORS_ORIGIN = os.environ.get('CORS_ORIGIN', 'https://d33w9ue2h7llgj.cloudfront.net')

# Comma-separated list of nodeIds to monitor.
# Add new nodes here (or update the Lambda env var) when Node 4 is commissioned.
NODE_IDS = os.environ.get('NODE_IDS', 'garden-01,outside-01,outside-home').split(',')

# Status thresholds
WARN_MINUTES    = 90
OFFLINE_MINUTES = 180

dynamodb = boto3.resource('dynamodb')
table    = dynamodb.Table(TABLE_NAME)

EASTERN = ZoneInfo("America/New_York")


def serialize(val):
    """Convert DynamoDB Decimal to int or float for JSON output."""
    if isinstance(val, Decimal):
        return int(val) if val % 1 == 0 else float(val)
    return val


def get_node_status(node_id):
    """
    Query the single most recent record for a nodeId and return its health status.

    Uses a reverse-sorted query on the main table (nodeId PK + eventTimestamp SK)
    with Limit=1 — one read regardless of how much history exists.
    """
    response = table.query(
        KeyConditionExpression=boto3.dynamodb.conditions.Key('nodeId').eq(node_id),
        ScanIndexForward=False,  # newest first
        Limit=1,
    )

    items = response.get('Items', [])
    if not items:
        return {
            'nodeId':     node_id,
            'lastSeen':   None,
            'minutesAgo': None,
            'status':     'offline',
        }

    last_seen = items[0]['eventTimestamp']  # "YYYY-MM-DD HH:MM" Eastern

    # Parse as Eastern time — timestamps are stored in Eastern by all nodes
    last_seen_dt = datetime.strptime(last_seen, '%Y-%m-%d %H:%M').replace(tzinfo=EASTERN)
    minutes_ago  = int((datetime.now(EASTERN) - last_seen_dt).total_seconds() / 60)

    if minutes_ago >= OFFLINE_MINUTES:
        status = 'offline'
    elif minutes_ago >= WARN_MINUTES:
        status = 'warning'
    else:
        status = 'ok'

    return {
        'nodeId':     node_id,
        'lastSeen':   last_seen,
        'minutesAgo': minutes_ago,
        'status':     status,
    }


def lambda_handler(event, context):
    cors_headers = {
        'Content-Type':                 'application/json',
        'Access-Control-Allow-Origin':  CORS_ORIGIN,
        'Access-Control-Allow-Methods': 'GET',
        'Access-Control-Allow-Headers': 'Content-Type',
    }

    try:
        nodes = [get_node_status(node_id) for node_id in NODE_IDS]
        logger.info(f"Admin panel: checked {len(nodes)} nodes — statuses: "
                    f"{[n['status'] for n in nodes]}")

        return {
            'statusCode': 200,
            'body': json.dumps({
                'nodes': nodes,
                'asOf':  datetime.now(EASTERN).strftime('%Y-%m-%d %I:%M %p ET'),
                'thresholds': {
                    'warnMinutes':    WARN_MINUTES,
                    'offlineMinutes': OFFLINE_MINUTES,
                },
            }, default=serialize),
            'headers': cors_headers,
        }

    except Exception as e:
        logger.error(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body':       json.dumps({'error': 'Internal server error'}),
            'headers':    cors_headers,
        }
