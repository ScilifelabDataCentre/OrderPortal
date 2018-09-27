"""OrderPortal: A portal for orders to a facility from its users.
An order can be a project application, a request, a report, etc.
"""

from __future__ import print_function, absolute_import

import os


__version__ = '3.5.10'

# Default settings, may be changed in a settings YAML file.
settings = dict(
    ROOT_DIR=os.path.dirname(__file__),
    BASE_URL='http://localhost/',
    TORNADO_DEBUG=False,
    LOGGING_DEBUG=False,
    LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
    DATABASE_SERVER='http://localhost:5984/',
    DATABASE_NAME='orderportal',
    MARKDOWN_URL='http://daringfireball.net/projects/markdown/syntax',
    SITE_DIR='{ROOT_DIR}/site',
    SITE_NAME='OrderPortal',
    ACCOUNT_MESSAGES_FILEPATH='{SITE_DIR}/account_messages.yaml',
    ORDER_STATUSES_FILEPATH='{SITE_DIR}/order_statuses.yaml',
    ORDER_TRANSITIONS_FILEPATH='{SITE_DIR}/order_transitions.yaml',
    ORDER_MESSAGES_FILEPATH='{SITE_DIR}/order_messages.yaml',
    UNIVERSITIES_FILEPATH='{SITE_DIR}/swedish_universities.yaml',
    COUNTRY_CODES_FILEPATH='{SITE_DIR}/country_codes.yaml',
    SUBJECT_TERMS_FILEPATH='{SITE_DIR}/subject_terms.yaml',
    SITE_PERSONAL_DATA_POLICY='The data will be used only for activities directly related to this site.',
    GDPR_INFO_URL=None,
    TERMINOLOGY=dict(),         # Terms translation lookup.
    MIN_PASSWORD_LENGTH=8,
    LOGIN_MAX_AGE_DAYS=14,
    LOGIN_MAX_FAILURES=6,
    DISPLAY_DEFAULT_PAGE_SIZE=25,
    DISPLAY_MAX_RECENT_ORDERS=10,
    DISPLAY_ORDERS_MOST_RECENT=500,
    DISPLAY_MAX_PENDING_ACCOUNTS=10,
    DISPLAY_DEFAULT_MAX_LOG=20,
    DISPLAY_NEWS=True,
    DISPLAY_MAX_NEWS=4,
    DISPLAY_EVENTS=True,
    ORDER_IDENTIFIER_FORMAT=None,
    ORDER_IDENTIFIER_REGEXP=None,
    ORDER_USER_TAGS=True,
    ORDER_LINKS=True,
    ORDERS_LIST_TAGS=True,
    ORDERS_LIST_FIELDS=[],
    ORDERS_LIST_STATUSES=[],
    ORDERS_SEARCH_FIELDS=[],
    ACCOUNT_INVOICE_INFO=True,
    ACCOUNT_FUNDER_INFO=True,
    ACCOUNT_FUNDER_INFO_GENDER=True,
    ACCOUNT_FUNDER_INFO_GROUP_SIZE=True,
    ACCOUNT_FUNDER_INFO_SUBJECT=True,
    ACCOUNT_DEFAULT_COUNTRY_CODE='SE',
    )
