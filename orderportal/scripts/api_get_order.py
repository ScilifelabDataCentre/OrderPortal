"""API example script: Get order data.

NOTE: You need to change several variables to make this work. See below.

NOTE: This uses the third-party 'requests' module, which is better than
the standard 'urllib' module.
"""

import json

# Third-party package: http://docs.python-requests.org/en/master/
import requests

# Variables whose values must be changed for your site:

# Base URL for the OrderPortal instance.
BASE_URL = 'https://ngisweden.scilifelab.se/orders'

# API key for the user account. Must be changed (this is a dummy).
API_KEY = '7f075a4c5b324e3ca63f22d8dc0929c4'

# The ID for the order. The IUID can also be used.
ORDER_ID = 'NGI10904'


url = "{base}/api/v1/order/{id}".format(base=BASE_URL,
                                        id=ORDER_ID)
headers = {'X-OrderPortal-API-key': API_KEY}

response = requests.get(url, headers=headers)
assert response.status_code == 200, (response.status_code, response.reason)

print(json.dumps(response.json(), indent=2))
