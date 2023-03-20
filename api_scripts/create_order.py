"""API example script: Create an order from a given form.

NOTE: You need to change several upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import json
import os

import requests

# Base URL for the OrderPortal instance.
BASE_URL = "http://localhost:8881"

# The IUID of the form to create the order from.
FORM_IUID = "2582a559166d43f5aec6818becb919b5"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = "{base}/api/v1/order".format(base=BASE_URL)
headers = {"X-OrderPortal-API-key": API_KEY}

indata = {"title": "A new order created by API call",
          "form": FORM_IUID}

response = requests.post(url, headers=headers, json=indata)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()

print(json.dumps(outdata, indent=2))
