"""API example script: Get order data.

NOTE: You need to change several upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import json
import os

import requests


# Base URL for the OrderPortal instance.
BASE_URL = "http://localhost:8881/"

# The identifier for the order. The IUID can also be used.
ORDER_ID = "OP0031"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = f"{BASE_URL}api/v1/order/{ORDER_ID}"
headers = {"X-OrderPortal-API-key": API_KEY}

response = requests.get(url, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()

print(json.dumps(outdata, indent=2))
