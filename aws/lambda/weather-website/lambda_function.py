import boto3
import logging
import math
import os
from datetime import datetime
from zoneinfo import ZoneInfo

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load the DynamoDB table name from environment variables
TABLE_NAME = os.environ.get('TABLE_NAME', 'weather-data')

# Initialize the DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)

EASTERN = ZoneInfo("America/New_York")


def get_daily_records():
    """
    Return the most recent record per nodeId plus daily max/min stats
    for tempF, pressure, and co2.

    Fixes applied vs original version:
    - Timezone: datetime.now(EASTERN) so the correct Eastern date is always used
    - Field casing: stats loop now uses lowercase keys (tempF, pressure, co2)
      matching the standard payload written by all current nodes
    - Pagination: follows LastEvaluatedKey so days with > 1 MB of records
      are never silently truncated
    """
    try:
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
                    'latest': item,
                    'max_tempF': -math.inf,
                    'min_tempF': math.inf,
                    'max_pressure': -math.inf,
                    'min_pressure': math.inf,
                    'max_co2': -math.inf,
                    'min_co2': math.inf,
                }

            stats = node_stats[node_id]

            # Track the most recent record for this node
            if item['eventTimestamp'] > stats['latest']['eventTimestamp']:
                stats['latest'] = item

            # Lowercase keys match the current standard payload
            for key in ['tempF', 'pressure', 'co2']:
                if key in item:
                    value = float(item[key])
                    stats[f'max_{key}'] = max(value, stats[f'max_{key}'])
                    stats[f'min_{key}'] = min(value, stats[f'min_{key}'])

        records = []
        for stats in node_stats.values():
            record = stats['latest']
            record.update({
                'max_tempF':     stats['max_tempF']     if stats['max_tempF']     != -math.inf else None,
                'min_tempF':     stats['min_tempF']     if stats['min_tempF']     != math.inf  else None,
                'max_pressure':  stats['max_pressure']  if stats['max_pressure']  != -math.inf else None,
                'min_pressure':  stats['min_pressure']  if stats['min_pressure']  != math.inf  else None,
                'max_co2':       stats['max_co2']       if stats['max_co2']       != -math.inf else None,
                'min_co2':       stats['min_co2']       if stats['min_co2']       != math.inf  else None,
            })
            records.append(record)

        return records

    except Exception as e:
        logger.error(f"Error querying table: {str(e)}")
        raise


def generate_html(records):
    """
    Generate an HTML string displaying current conditions per node.
    Max/min stats are now wired up following the field casing fix.
    """
    bootstrap_cdn = (
        '<link rel="stylesheet" '
        'href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css" '
        'crossorigin="anonymous">'
    )
    sorted_records = sorted(records, key=lambda x: x.get('eventTimestamp', ''), reverse=True)

    html = (
        f'<!DOCTYPE html><html lang="en"><head>'
        f'<meta charset="UTF-8">'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f'{bootstrap_cdn}'
        f'<title>Weather Data</title>'
        f'</head><body>'
    )
    html += '<div class="container mt-4"><h1>Sensor Data</h1><div class="row">'

    for record in sorted_records:
        node_info = f' - Node: {record.get("nodeId", "N/A")}'
        timestamp_str = record.get("eventTimestamp", "N/A")
        date_info = (
            datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M").strftime("%Y-%m-%d %I:%M %p")
            if timestamp_str != "N/A"
            else "Invalid Timestamp"
        )

        html += '<div class="col-md-4 mb-4"><div class="card">'
        html += f'<div class="card-header">{date_info}{node_info}</div>'
        html += '<div class="card-body">'

        # Current readings
        # 'TempF' retained alongside 'tempF' to handle Node 1 legacy casing
        for key in ['tempF', 'TempF', 'humidity', 'pressure', 'co2', 'lux']:
            if value := record.get(key):
                html += f'<p class="card-text">{key}: {value}</p>'

        # Daily high / low — now populated after field casing fix
        for label, key in [
            ('High Temp F', 'max_tempF'), ('Low Temp F',  'min_tempF'),
            ('High Pressure', 'max_pressure'), ('Low Pressure', 'min_pressure'),
            ('High CO2',  'max_co2'),  ('Low CO2',   'min_co2'),
        ]:
            val = record.get(key)
            if val is not None:
                html += f'<p class="card-text">{label}: {val}</p>'

        html += '</div></div></div>'

    html += '</div></div></body></html>'
    return html


def lambda_handler(event, context):
    """
    AWS Lambda function handler.
    """
    records = get_daily_records()
    html_content = generate_html(records)
    logger.info(f"Generated HTML content with {len(records)} records.")

    return {
        'statusCode': 200,
        'body': html_content,
        'headers': {
            'Content-Type': 'text/html',
        }
    }
