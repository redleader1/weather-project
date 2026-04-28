import boto3
import logging
import math
import os
from datetime import datetime
# CI/CD test — 2026-04-28
# FIX FOR DB NAME

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Load the DynamoDB table name from environment variables
TABLE_NAME = os.environ.get('TABLE_NAME', 'weather-data')

# Initialize the DynamoDB client
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(TABLE_NAME)


def get_daily_records():
    """
    Get the most recent records along with max and min values for TempF, Pressure,
    and CO2 for each nodeId for the current day.

    KNOWN ISSUES:
    - datetime.now() has no timezone — Lambda runs in UTC, so near midnight Eastern
      this will query the wrong day. Fix: use ZoneInfo("America/New_York").
    - Min/max loop checks for 'TempF' and 'CO2' (old casing). Nodes now send
      'tempF' and 'co2' (lowercase). Fix: update keys to match current standard.
    - DynamoDB query has no pagination. If a day's data exceeds 1 MB the response
      will be silently truncated. Fix: follow LastEvaluatedKey in a loop.
    """
    try:
        current_day = datetime.now().strftime('%Y-%m-%d')
        logger.info(f"Querying for records on: {current_day}")

        response = table.query(
            IndexName='eventDateDay-index',
            KeyConditionExpression=boto3.dynamodb.conditions.Key('eventDateDay').eq(current_day)
        )

        node_stats = {}
        for item in response['Items']:
            node_id = item['nodeId']
            if node_id not in node_stats:
                node_stats[node_id] = {
                    'latest': item,
                    'max_TempF': -math.inf,
                    'min_TempF': math.inf,
                    'max_Pressure': -math.inf,
                    'min_Pressure': math.inf,
                    'max_CO2': -math.inf,
                    'min_CO2': math.inf,
                }

            stats = node_stats[node_id]

            # Update the latest record
            if item['eventTimestamp'] > stats['latest']['eventTimestamp']:
                stats['latest'] = item

            # KNOWN ISSUE: checks old-cased keys ('TempF', 'CO2') — nodes now send
            # 'tempF' and 'co2'. Min/max will be None for all current nodes until fixed.
            for key in ['TempF', 'Pressure', 'CO2']:
                if key in item:
                    value = float(item[key])
                    stats[f'max_{key}'] = max(value, stats[f'max_{key}'])
                    stats[f'min_{key}'] = min(value, stats[f'min_{key}'])

        records = []
        for stats in node_stats.values():
            record = stats['latest']
            record.update({
                'max_TempF': stats['max_TempF'] if stats['max_TempF'] != -math.inf else None,
                'min_TempF': stats['min_TempF'] if stats['min_TempF'] != math.inf else None,
                'max_Pressure': stats['max_Pressure'] if stats['max_Pressure'] != -math.inf else None,
                'min_Pressure': stats['min_Pressure'] if stats['min_Pressure'] != math.inf else None,
                'max_CO2': stats['max_CO2'] if stats['max_CO2'] != -math.inf else None,
                'min_CO2': stats['min_CO2'] if stats['min_CO2'] != math.inf else None,
            })
            records.append(record)

        return records

    except Exception as e:
        logger.error(f"Error querying table: {str(e)}")
        raise


def generate_html(records):
    """
    Generate an HTML string to display the records as tiles.

    KNOWN ISSUES:
    - Checks both 'tempF' and 'TempF' to handle old/new casing inconsistency.
      Once all nodes standardise on lowercase, remove 'TempF' from the key list.
    - Max/min display lines are commented out (data not currently populating —
      see get_daily_records issue above).
    - Bootstrap 4.3.1 CDN is outdated; upgrade to 5.x when overhauling.
    - No weather graphics, icons, or NWS alerts yet.
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
        f'<title>Weather Data Tiles</title>'
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

        # 'TempF' included alongside 'tempF' to handle Node 1 legacy casing
        for key in ['tempF', 'pressure', 'humidity', 'co2', 'lux', 'TempF']:
            if value := record.get(key):
                html += f'<p class="card-text">{key}: {value}</p>'

        # Max/min commented out — not populating due to field casing bug above
        # html += f'<p class="card-text">Max Temp F: {record.get("max_TempF")}</p>'
        # html += f'<p class="card-text">Min Temp F: {record.get("min_TempF")}</p>'
        # html += f'<p class="card-text">Max Pressure: {record.get("max_Pressure")}</p>'
        # html += f'<p class="card-text">Min Pressure: {record.get("min_Pressure")}</p>'
        # html += f'<p class="card-text">Max CO2: {record.get("max_CO2")}</p>'
        # html += f'<p class="card-text">Min CO2: {record.get("min_CO2")}</p>'

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
            'Content-Type': 'text/html'
        }
    }
