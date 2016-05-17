"""Test accessing API.
NOTE: Both the API key and the order IUID need to be changed
to match your account and an order at your installation.
"""

from __future__ import print_function, absolute_import

import json
import requests

headers = {'X-OrderPortal-API-key': '5fa35b9f880e49a984b60108b2af03d9'}

url = 'http://localhost:8886/api/v1/order/91ae8130006447628e5b192b1dcd8f00'

response = requests.get(url, headers=headers)
if response.status_code != 200:
    print(response.status_code)
else:
    print(json.dumps(response.json(), indent=2))
