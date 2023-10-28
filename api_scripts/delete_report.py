"""API example script: Delete a report for an order.

NOTE: You need to review/change the upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import base64
import json
import os

import requests

# Base URL for your OrderPortal instance.
BASE_URL = "http://localhost:8881/"

# The IUID for the report.
REPORT_IUID = "f753f72504b04186aa5ee03a41fa955e"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = f"{BASE_URL}api/v1/report/{REPORT_IUID}"
headers = {"X-OrderPortal-API-key": API_KEY}

response = requests.delete(url, headers=headers)
assert response.status_code == 204, (response.status_code, response.reason)
