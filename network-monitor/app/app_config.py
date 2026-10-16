'''
Application configuration
'''
import os
# Logging related values
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
INFLUXDB_TOKEN = os.getenv("INFLUXDB_TOKEN", "4JQlHZu4-CVuKKwJLt39cz5U1Zj0QxeBn-6yi7fgLWZVT_SF-Cq8dQ4y_7LimM2XgC7PCj9jAIN3wg-n-V8F2g==")
INFLUXDB_ORG = os.getenv("INFLUXDB_ORG", "network-monitor-org")
INFLUXDB_BUCKET = os.getenv("INFLUXDB_BUCKET", "network-monitor-bucket")