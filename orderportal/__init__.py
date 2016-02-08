"""OrderPortal: A portal for orders (a.k.a. requests, project applications)
to a facility from its users.
"""

from __future__ import print_function, absolute_import

__version__ = '0.7'

# Default settings, may be changed in a settings YAML file.
settings = dict(SITE_NAME='OrderPortal',
                BASE_URL='http://localhost:8885/',
                DB_SERVER='http://localhost:5984/',
                TORNADO_DEBUG=True,
                LOGGING_DEBUG=True,
                LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
                LOGIN_MAX_AGE_DAYS=6,
                ORDER_STATUSES_FILENAME='{ROOT}/data/order_statuses.yaml',
                ORDERS_LIST_FIELDS=[],
                ORDERS_LIST_STATUSES=[],
                ORDER_TRANSITIONS_FILENAME='{ROOT}/data/order_transitions.yaml',
                UNIVERSITIES_FILENAME='{ROOT}/data/university_list.yaml',
                ACCOUNT_MESSAGES_FILENAME='{ROOT}/data/account_messages.yaml',
                ORDER_MESSAGES_FILENAME='{ROOT}/data/order_messages.yaml',
                MARKDOWN_URL='http://daringfireball.net/projects/markdown/',
                )
