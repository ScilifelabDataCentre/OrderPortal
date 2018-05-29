"""API example script: Edit an order; fields, title, tags and history.

NOTE: The upload operation URL requires the IUID for the order.

NOTE: You need to change several variables to make this work. See below.

NOTE: This uses the third-party 'requests' module, which is much nicer than
the standard 'urllib' module.
"""

from __future__ import print_function
import json
import sys
import requests # http://docs.python-requests.org/en/master/

# Change the following:
API_KEY = '7f075a4c5b324e3ca63f22d8dc0929c4'  # API key for the user account.
BASE_URL = 'http://localhost:8886'  # Base URL for your OrderPortal instance.
ORDER_ID = 'NMI00603'  # The ID or IUID for the order.


url = "{base}/api/v1/order/{id}".format(base=BASE_URL,
                                        id=ORDER_ID)
headers = {'X-OrderPortal-API-key': API_KEY}

data = {'title': 'New title',
        'tags': ['first_tag', 'second_tag'],  # NOTE: identifier format!
        'fields': {'Expected_results': 'Great!',
                   'Node_support': 'UmU'},
        'history': {'review': '2018-05-30'}
}
response = requests.post(url, headers=headers, json=data)

if response.status_code != 200:
    sys.exit("{} {}".format(response.status_code, response.reason))

print(json.dumps(response.json(), indent=2))
