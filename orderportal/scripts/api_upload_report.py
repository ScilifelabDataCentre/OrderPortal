"""API example script: Uploading the order report.

NOTE: The upload operation URL requires the IUID for the order;
      the order identifier (NMI00603 in this case) won't work for this call.

NOTE: You need to change several variables to make this work. See below.

NOTE: This uses the third-party 'requests' module, which is better than
the standard 'urllib' module.
"""



import sys

# Third-party package: http://docs.python-requests.org/en/master/
import requests

# Variables whose values must be changed for your site:
BASE_URL = 'http://localhost:8886'  # Base URL for your OrderPortal instance.
API_KEY = '7f075a4c5b324e3ca63f22d8dc0929c4'  # API key for the user account.
ORDER_IUID = 'b1abccfbc77048e1941034d7c0101f22'  # The IUID for the order!

url = "{base}/api/v1/order/{iuid}/report".format(base=BASE_URL,
                                                 iuid=ORDER_IUID)
headers = {'X-OrderPortal-API-key': API_KEY,
           'content-type': 'text/plain'}
data = 'Some text in a report.\nAnd a second line.'

# NOTE: The method PUT is used to upload a report to the order.
response = requests.put(url, headers=headers, data=data)
assert response.status_code == 200, (response.status_code, response.reason)

print('report uploaded')
