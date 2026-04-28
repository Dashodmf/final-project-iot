import os
import time
import random
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS

# InfluxDB Configuration
url = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
token = os.getenv("INFLUXDB_TOKEN", "my-super-secret-auth-token")
org = os.getenv("INFLUXDB_ORG", "my-org")
bucket = os.getenv("INFLUXDB_BUCKET", "sensor_data")

def main():
    print(f"Connecting to InfluxDB at {url}...", flush=True)

    # Initialize the client
    with InfluxDBClient(url=url, token=token, org=org) as client:
        write_api = client.write_api(write_options=SYNCHRONOUS)

        print("Starting data transmission loop...", flush=True)
        while True:
            try:
                # Generate sample data
                temperature = random.uniform(20.0, 30.0)
                humidity = random.uniform(40.0, 60.0)

                # Create a point
                point = Point("environment") \
                    .tag("location", "office") \
                    .field("temperature", temperature) \
                    .field("humidity", humidity) \
                    .time(time.time_ns(), WritePrecision.NS)

                # Write data
                write_api.write(bucket=bucket, org=org, record=point)

                print(f"Sent data: Temp={temperature:.2f}, Humidity={humidity:.2f}", flush=True)

                # Wait for a bit
                time.sleep(2)

            except Exception as e:
                print(f"Error sending data: {e}", flush=True)
                time.sleep(10)

if __name__ == "__main__":
    main()