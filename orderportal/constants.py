" OrderPortal: Various constants."

from __future__ import print_function, absolute_import

import re

# Patterns
ID_RX    = re.compile(r'^[a-z][_a-z0-9]*$', re.IGNORECASE)
NAME_RX  = re.compile(r'^[^/]+$')
IUID_RX  = re.compile(r'^[0-9a-f]{32}$')
DATE_RX  = re.compile(r'^[0-9]{4}-[0-9]{2}-[0-9]{2}$') # Safe until 9999 CE...
EMAIL_RX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

# Content types (MIME types)
HTML_MIME = 'text/html'
JSON_MIME = 'application/json'
CSV_MIME  = 'text/csv'

# CouchDB
# For view ranges: CouchDB uses the Unicode Collation Algorithm,
# which is not the same as the ASCII collation sequence.
# The endkey is inclusive, by default.
CEILING = 'ZZZZZZZZ'

# Entity documents
DOCTYPE = 'orderportal_doctype'
ACCOUNT = 'account'
GROUP   = 'group'
FORM    = 'form'
ORDER   = 'order'
NEWS    = 'news'
EVENT   = 'event'
TEXT    = 'text'
INFO    = 'info'
FILE    = 'file'
MESSAGE = 'message'
LOG     = 'log'
META    = 'meta'
ENTITIES = frozenset([ACCOUNT, GROUP, FORM, ORDER, INFO, FILE, MESSAGE])

# Field types
STRING  = 'string'
INT     = 'int'
FLOAT   = 'float'
BOOLEAN = 'boolean'
URL     = 'url'
SELECT  = 'select'
MULTISELECT  = 'multiselect'
TEXT    = 'text'
DATE    = 'date'
TABLE   = 'table'
### This constant already defined above.
### GROUP   = 'group'
### FILE    = 'file'
TYPES = [STRING, INT, FLOAT, BOOLEAN, URL, SELECT, MULTISELECT,
         TEXT, DATE, TABLE, FILE, GROUP]
TYPE_LABELS = {INT: 'integer'}
TYPE_HTML = {STRING: 'text', INT: 'number'}

# Boolean string values
TRUE  = frozenset(['true', 'yes', 't', 'y', '1'])
FALSE = frozenset(['false', 'no', 'f', 'n', '0'])

# Default global modes for database initialization
DEFAULT_GLOBAL_MODES = dict(allow_registration=True,
                            allow_login=True,
                            allow_order_creation=True,
                            allow_order_editing=True)

# User login account
USER_COOKIE = 'orderportal_user'
API_KEY_HEADER = 'X-OrderPortal-API-key'

# Account status; hard-wired!
PENDING  = 'pending'
ENABLED  = 'enabled'
DISABLED = 'disabled'
ACCOUNT_STATUSES = [PENDING, ENABLED, DISABLED]

# Account role
USER  = 'user'
STAFF = 'staff'
ADMIN = 'admin'
ACCOUNT_ROLES = [USER, STAFF, ADMIN]

# Form status; hard-wired!
TESTING = 'testing'
FORM_STATUSES = [PENDING, TESTING, ENABLED, DISABLED]

# Content-type to icon mapping
CONTENT_TYPE_ICONS = {
    JSON_MIME: 'json.png',
    CSV_MIME: 'csv.png',
    HTML_MIME: 'html.png',
    'application/pdf': 'pdf.png',
    'image/png': 'image.png',
    'image/jpeg': 'image.png',
    'application/vnd.ms-excel': 'excel.png',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': 'excel.png',
    'application/vnd.ms-excel': 'excel.png',
    'application/msword': 'word.png',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'word.png',
    'application/vnd.ms-powerpoint': 'ppt.png',
    'application/vnd.openxmlformats-officedocument.presentationml.presentation': 'ppt.png',
    'text/plain': 'text.png',
    }
DEFAULT_CONTENT_TYPE_ICON = 'binary.png'
