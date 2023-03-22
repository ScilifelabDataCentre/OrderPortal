"""API example script: Add a report to an order.

Since the file contents needs to be provided at the same time as
the name, status and (optionally) reviewers are set, the contents
must be provided in the JSON indata, and must therefore be 
base64-encoded in UTF-8.

NOTE: You need to change several upper-case variables.

NOTE: The third-party 'requests' module is used.
"""

import base64
import json
import os

import requests

# Base URL for your OrderPortal instance.
BASE_URL = "http://localhost:8881/"

# The ID for the order. The IUID can also be used.
ORDER_ID = "OP0032"

# The name and content type of the file to upload as a report.
FILENAME = "README.md"
CONTENT_TYPE = "text/markdown"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = f"{BASE_URL}api/v1/report"
headers = {"X-OrderPortal-API-key": API_KEY}

with open(FILENAME, "rb") as infile:
    content = infile.read()

indata = dict(order=ORDER_ID,
              name="README",
              status="review",
              file=dict(data=base64.b64encode(content).decode("utf-8"),
                        filename=FILENAME,
                        content_type=CONTENT_TYPE))

response = requests.post(url, json=indata, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()
print(json.dumps(outdata, indent=2))
