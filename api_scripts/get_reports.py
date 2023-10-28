"""API example script: Get reports for an order.

NOTE: You need to review/change the upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import json
import os

import requests


# Base URL for the OrderPortal instance.
BASE_URL = "http://localhost:8881"

# The identifier for the order.
ORDER_ID = "OP00013"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = f"{BASE_URL}/api/v1/order/{ORDER_ID}"
headers = {"X-OrderPortal-API-key": API_KEY}

response = requests.get(url, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()

# Download and save the report files in the current directory.
for report in outdata["reports"]:
    response = requests.get(report["links"]["file"]["href"], headers=headers)
    print(report["filename"], len(response.content))
    with open(f"downloaded_{report['filename']}", "wb") as outfile:
        outfile.write(response.content)
