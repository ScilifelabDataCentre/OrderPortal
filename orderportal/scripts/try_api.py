"""Try accessing the API.
NOTE: You need to change several items in this script to make it work:
- The domain name must match your instance.
- The API key is set for your account; see your account page.
- The order IUID need to be changed, of course.
NOTE: This uses the third-party 'requests' module, which is much nicer than
the standard 'urllib' module.
"""

from __future__ import print_function

import json

# http://docs.python-requests.org/en/master/
import requests

headers = {'X-OrderPortal-API-key': '5fa35b9f880e49a984b60108b2af03d9'}

url = 'http://your.domain.org/api/v1/order/91ae8130006447628e5b192b1dcd8f00'

response = requests.get(url, headers=headers)
if response.status_code != 200:
    print(response.status_code)
else:
    print(json.dumps(response.json(), indent=2))
