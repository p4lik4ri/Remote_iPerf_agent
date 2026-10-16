# File: app/influxdb.py

import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from app.app_config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET
import app.utils as utils

client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

logger = utils.get_app_logger()

import json  # Ensure json is imported

import json
import logging
from influxdb_client import InfluxDBClient, Point, WritePrecision
from app.app_config import INFLUXDB_URL, INFLUXDB_TOKEN, INFLUXDB_ORG, INFLUXDB_BUCKET
import app.utils as utils

# Initialize InfluxDB Client
client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
write_api = client.write_api(write_options=SYNCHRONOUS)

logger = utils.get_app_logger()

def write_to_influxdb(data):
    """
    Write experiment result data to InfluxDB with correct units.

    - Jitter: Already in milliseconds (ms) (no conversion needed)
    - Packet Loss: Already in percentage (%) (DO NOT multiply by 100)
    - Throughput: Already in Mbps (no conversion needed)
    - Timestamp: Convert from seconds to nanoseconds
    """

    try:
        if isinstance(data, dict) and "results" in data:
            data = data["results"]

        if not isinstance(data, list):
            logger.error("Expected a list of results, but got: %s", type(data))
            return  # Stop execution if data format is incorrect
        
        for result in data:
            if not isinstance(result, dict):
                logger.warning("Skipping non-dictionary result: %s", result)
                continue

            logger.info("Processing result: %s", result)

            if result.get("Status") == "Success":
                for entry in result.get("Result", []):
                    if not isinstance(entry, dict):
                        logger.warning("Skipping non-dictionary entry: %s", entry)
                        continue

                    logger.info("Processing entry: %s", entry)

                    try:
                        timestamp_ns = int(float(entry["timestamp"]) * 1e9)

                        jitter_ms = round(float(entry["jitter"]), 3)

                        packet_loss_percent = round(float(entry["packetLoss"]), 3)

                        throughput_mbps = round(float(entry["throughput"]), 2)

                        point = (
                            Point("network_metrics")
                            .field("jitter_ms", jitter_ms)  # Jitter in ms
                            .field("packetLoss_percent", packet_loss_percent)  # Packet loss in %
                            .field("throughput_Mbps", throughput_mbps)  # Throughput in Mbps
                            .time(timestamp_ns, WritePrecision.NS)  # Timestamp in nanoseconds
                        )

                        # Write to InfluxDB
                        write_api.write(bucket=INFLUXDB_BUCKET, record=point)
                        logger.info(f"Wrote point: jitter={jitter_ms} ms, packetLoss={packet_loss_percent} %, throughput={throughput_mbps} Mbps")
                    
                    except Exception as inner_e:
                        logger.error(f"Error processing entry {entry}: {inner_e}")

            else:
                logger.warning(f"Skipping result as Status is not 'Success': {result}")

        logger.info("Data written to InfluxDB successfully.")

    except Exception as e:
        logger.error(f"Error writing to InfluxDB: {e}")




