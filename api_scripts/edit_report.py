"""API example script: Edit the status of a report for an order.

NOTE: Only the report status can be changed via the API.

NOTE: You need to change several upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import json
import os

import requests

# Base URL for your OrderPortal instance.
BASE_URL = "http://localhost:8881/"

# The ID for the order. The IUID can also be used.
ORDER_ID = "OP0032"

# The IUID for the report.
REPORT_IUID = "47b413b0823043bdace5e33e81b7a099"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = f"{BASE_URL}api/v1/report/{REPORT_IUID}"
headers = {"X-OrderPortal-API-key": API_KEY}

indata = dict(status="published")

response = requests.post(url, json=indata, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()
print(json.dumps(outdata, indent=2))
