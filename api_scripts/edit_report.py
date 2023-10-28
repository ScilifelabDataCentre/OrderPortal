"""API example script: Edit the content and status of a report for an order.

NOTE: You need to review/change the upper-case variables.

NOTE: The 'order' and 'owner' of the report cannot be edited.

NOTE: The third-party 'requests' module is used.
"""

import base64
import json
import os

import requests

# Base URL for your OrderPortal instance.
BASE_URL = "http://localhost:8881/"

# The IUID for the report.
REPORT_IUID = "47b413b0823043bdace5e33e81b7a099"

# The name and content type of the file to upload as a report.
FILENAME = "README.md"
CONTENT_TYPE = "text/markdown"

API_KEY = os.environ["ORDERPORTAL_API_KEY"]


url = f"{BASE_URL}api/v1/report/{REPORT_IUID}"
headers = {"X-OrderPortal-API-key": API_KEY}

# Use the file content as in 'add_report.py', but add another line to show file update.
with open(FILENAME, "rb") as infile:
    updated_content = infile.read() + b"\n\nAnother spurious line added."

indata = dict(name="README updated",
              status="published",
              file=dict(data=base64.b64encode(updated_content).decode("utf-8"),
                        filename="updated_" + FILENAME,
                        content_type=CONTENT_TYPE))

response = requests.post(url, json=indata, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

outdata = response.json()
print(json.dumps(outdata, indent=2))
