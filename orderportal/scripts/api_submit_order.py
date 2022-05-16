"""API example script: Submit the order.

NOTE: You need to change several variables to make this work. See below.

NOTE: This uses the third-party 'requests' module, which is better than
the standard 'urllib' module.
"""

import sys

import json

# Third-party package: http://docs.python-requests.org/en/master/
import requests

# Variables whose values must be changed for your site:
BASE_URL = "http://localhost:8886"  # Base URL for your OrderPortal instance.
API_KEY = "7f075a4c5b324e3ca63f22d8dc0929c4"  # API key for the user account.
ORDER_ID = "NMI00603"  # The ID for the order. The IUID can also be used.


url = "{base}/api/v1/order/{id}".format(base=BASE_URL, id=ORDER_ID)
headers = {"X-OrderPortal-API-key": API_KEY}

# First just get the order data as JSON. It contains all allowed transitions.
response = requests.get(url, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

# Get the URL for the transition to status 'submitted'.
data = response.json()
try:
    url = data["links"]["submitted"]["href"]
except KeyError:
    print("Error: No href for submit; the order status does not allow it.")
    sys.exit()

# Actually do the transition by the POST method.
response = requests.post(url, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

data = response.json()
if data["status"] == "submitted":
    print("Order submitted.")
else:
    print("Error: Order was not submitted.")
