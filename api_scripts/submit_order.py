"""API example script: Submit the order.

NOTE: You need to change several upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import json
import os
import sys

import requests


# Base URL for your OrderPortal instance.
BASE_URL = "http://localhost:8881/"

# The ID for the order. The IUID can also be used.
ORDER_ID = "OP0032"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = "{base}api/v1/order/{id}".format(base=BASE_URL, id=ORDER_ID)
headers = {"X-OrderPortal-API-key": API_KEY}

# First just get the order data as JSON. It contains all allowed transitions.
response = requests.get(url, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

# Get the URL for the transition to status 'submitted'.
outdata = response.json()
try:
    url = outdata["links"]["submitted"]["href"]
except KeyError:
    print("Error: No href for submit; the order status does not allow it.")
    sys.exit()

# Actually do the transition by the POST method.
response = requests.post(url, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()
if outdata["status"] == "submitted":
    print("Order submitted.")
else:
    print("Error: Order was not submitted.")
