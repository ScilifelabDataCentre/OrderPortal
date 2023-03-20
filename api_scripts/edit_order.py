"""API example script: Edit an order; fields, title.

NOTE: You need to change several upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import json
import os

import requests

# Base URL for the OrderPortal instance.
BASE_URL = "http://localhost:8881/"

# The identifier for the order. The IUID can also be used.
ORDER_ID = "OP0032"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = f"{BASE_URL}api/v1/order/{ORDER_ID}"
headers = {"X-OrderPortal-API-key": API_KEY}

indata = {
    "title": "Order has been updated via API call",
    # The fields must match the form used for the order.
    # The field identifiers are the keys, not the labels presented in the web.
    "fields": {"number_of_samples": 2,
               "type_of_sample": "protein",
               "description": "A test set of samples."}
}

response = requests.post(url, headers=headers, json=indata)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()

print(json.dumps(outdata, indent=2))
