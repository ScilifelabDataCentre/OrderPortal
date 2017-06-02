"""OrderPortal: A portal for orders (a.k.a. requests, project applications)
to a facility from its users.
"""

from __future__ import print_function, absolute_import

import os


__version__ = '3.3.3'

# Default settings, may be changed in a settings YAML file.
settings = dict(
    ROOT=os.path.dirname(__file__),
    BASE_URL='http://localhost/',
    TORNADO_DEBUG=False,
    LOGGING_DEBUG=False,
    LOGGING_FORMAT='%(levelname)s [%(asctime)s] %(message)s',
    PROCESSORS=[],
    SITE_DIR='{ROOT}/generic',
    SITE_NAME='OrderPortal',
    DB_SERVER='http://localhost:5984/',
    COUCHDB_HOME='http://couchdb.apache.org/',
    BOOTSTRAP_HOME='http://getbootstrap.com/',
    BOOTSTRAP_CSS_URL='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.6/css/bootstrap.min.css',
    BOOTSTRAP_JS_URL='https://maxcdn.bootstrapcdn.com/bootstrap/3.3.6/js/bootstrap.min.js',
    JQUERY_HOME='https://jquery.com/',
    JQUERY_URL='https://code.jquery.com/jquery-1.12.4.min.js',
    JQUERY_UI_HOME='https://jqueryui.com/',
    JQUERY_UI_URL='https://code.jquery.com/ui/1.11.4/jquery-ui.min.js',
    JQUERY_UI_THEME_URL='https://code.jquery.com/ui/1.11.4/themes/smoothness/jquery-ui.css',
    JQUERY_LOCALTIME_HOME='https://github.com/GregDThomas/jquery-localtime',
    JQUERY_LOCALTIME_VERSION='0.9.1',  # Must agree with file in ./static
    DATATABLES_HOME='https://www.datatables.net/',
    DATATABLES_CSS_URL='https://cdn.datatables.net/1.10.11/css/dataTables.bootstrap.min.css',
    DATATABLES_JS_URL='https://cdn.datatables.net/1.10.11/js/jquery.dataTables.min.js',
    DATATABLES_BOOTSTRAP_JS_URL='https://cdn.datatables.net/1.10.11/js/dataTables.bootstrap.min.js',
    MIN_PASSWORD_LENGTH=8,
    LOGIN_MAX_AGE_DAYS=14,
    LOGIN_MAX_FAILURES=6,
    DISPLAY_DEFAULT_PAGE_SIZE=25,
    DISPLAY_MAX_RECENT_ORDERS=10,
    DISPLAY_ORDERS_MOST_RECENT=500,
    DISPLAY_MAX_PENDING_ACCOUNTS=10,
    DISPLAY_DEFAULT_MAX_LOG=20,
    DISPLAY_MAX_NEWS=4,
    INITIAL_TEXTS_FILEPATH='{SITE_DIR}/initial_texts.yaml',
    ACCOUNT_MESSAGES_FILEPATH='{SITE_DIR}/account_messages.yaml',
    ORDER_STATUSES_FILEPATH='{SITE_DIR}/order_statuses.yaml',
    ORDER_TRANSITIONS_FILEPATH='{SITE_DIR}/order_transitions.yaml',
    ORDER_USER_TAGS=True,
    ORDER_TABLE_NEW_ROWS=4,
    ORDERS_LIST_TAGS=True,
    ORDERS_LIST_FIELDS=[],
    ORDERS_LIST_STATUSES=[],
    ORDER_MESSAGES_FILEPATH='{SITE_DIR}/order_messages.yaml',
    ACCOUNT_INVOICE_INFO=True,
    ACCOUNT_FUNDER_INFO=True,
    ACCOUNT_FUNDER_INFO_GENDER=True,
    ACCOUNT_FUNDER_INFO_GROUP_SIZE=True,
    ACCOUNT_FUNDER_INFO_SUBJECT=True,
    UNIVERSITIES_FILEPATH='{SITE_DIR}/swedish_universities.yaml',
    COUNTRY_CODES_FILEPATH='{SITE_DIR}/country_codes.yaml',
    SUBJECT_TERMS_FILEPATH='{SITE_DIR}/subjects.yaml',
    DOCUMENTATION_URL='https://github.com/pekrau/OrderPortal/wiki',
    MARKDOWN_URL='http://daringfireball.net/projects/markdown/syntax',
    )
