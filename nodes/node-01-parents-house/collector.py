import time
import datetime
import csv
import board
import adafruit_bh1750
from adafruit_ms8607 import MS8607
import requests
import json

i2c = board.I2C()
sensor = adafruit_bh1750.BH1750(i2c)
sensor2 = MS8607(i2c)

# Your API endpoint URL
api_url = "https://1iawimadei.execute-api.us-east-1.amazonaws.com/prod/WeatherApi"

# Assuming you want to run this loop indefinitely, you can use 'while True:'
# If you want to send data periodically, uncomment the next line to set the delay
# delay = 60 # Delay in seconds

while True:
    
    lux = round(float(sensor.lux),2)
    pressure = round(float(sensor2.pressure),2)
    temp_C = round(float(sensor2.temperature),2)
    temp_F = round(float(sensor2.temperature*(9/5)+32),2)
    humidity = round(float(sensor2.relative_humidity),2)
    now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
    
    # Adding nodeId to your data
    data = {
        "nodeId": "outside-01",
        "eventDate": now,
        "lux": lux,
        "pressure": pressure,
        "tempC": temp_C,
        "tempF": temp_F,
        "humidity": humidity
    }

    # Set headers for JSON content
    headers = {
        "Content-Type": "application/json"
    }

    # Send a POST request
    payload = json.dumps(data)
    response = requests.post(api_url, data=payload, headers=headers)

    # Check the response
    if response.status_code == 200:
        print("Data sent successfully for eventDate:", data["eventDate"])
    else:
        print("Failed to send data for eventDate:", data["eventDate"])
        print("Status code:", response.status_code)
        print("Response content:", response.text)
        
    # If you uncomment the delay, remember to import 'time' and add 'time.sleep(delay)'
    # time.sleep(delay)
    
    break # Remove this if you want the loop to run indefinitely




#!/usr/bin/python3

import time
import datetime
import csv
import board
import adafruit_bh1750
from adafruit_ms8607 import MS8607
import requests
import json

i2c = board.I2C()
sensor = adafruit_bh1750.BH1750(i2c)
sensor2 = MS8607(i2c)

#delay = 60


# Your API endpoint URL
api_url = "https://1iawimadei.execute-api.us-east-1.amazonaws.com/prod/WeatherApi"

while True:
    
    lux = round(float(sensor.lux),2)
    pressure = round(float(sensor2.pressure),2)
    temp_C = round(float(sensor2.temperature),2)
    temp_F = round(float(sensor2.temperature*(9/5)+32),2)
    humidity = round(float(sensor2.relative_humidity),2)
    now = datetime.datetime.now().astimezone().replace(microsecond=0).isoformat()
    
    data = [
    {
        "eventDate": now,
        "lux": lux,
        "pressure": pressure,
        "tempC": temp_C,
        "tempF": temp_F,
        "humidity": humidity
    }
    ]

    # Set headers for JSON content
    headers = {
        "Content-Type": "application/json"
    }

# Loop through the sample data and send a POST request for each row
    for data in data:
        payload = json.dumps(data)
        response = requests.post(api_url, data=payload, headers=headers)

        # Check the response for each row
        if response.status_code == 200:
            print("Data sent successfully for eventDate:", data["eventDate"])
        else:
            print("Failed to send data for eventDate:", data["eventDate"])
            print("Status code:", response.status_code)
            print("Response content:", response.text)
        
        
    break
