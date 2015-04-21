" OrderPortal: Various constants."

from __future__ import unicode_literals, print_function, absolute_import

import re
import os.path

# Patterns
ID_RX  = re.compile(r'^[a-z][_a-z0-9]*$', re.IGNORECASE)
IUID_RX  = re.compile(r'^[0-9a-f]{32}$')
EMAIL_RX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

# Content types (MIME types)
JSON_MIME      = 'application/json'

# CouchDB
# For view ranges: CouchDB uses the Unicode Collation Algorithm,
# which is not the same as the ASCII collation sequence.
# The endkey is inclusive, by default.
HIGH_CHAR = 'ZZZZZZZZ'

# Entity documents
DOCTYPE     = 'orderportal_doctype'
USER        = 'user'
FIELD       = 'field'
FORM        = 'form'
ORDER       = 'order'
PUBLICATION = 'publication'
USER        = 'user'
LOG         = 'log'
ENTITIES    = frozenset([USER, FIELD, ORDER, PUBLICATION])

# Field types
STRING  = dict(value='string', label='String')
INTEGER = dict(value='int', label='Integer')
FLOAT   = dict(value='float', label='Float')
BOOLEAN = dict(value='boolean', label='Boolean')
URL     = dict(value='url', label='URL')
SELECT  = dict(value='select', label='Select')
GROUP   = dict(value='group', label='Group')
TYPES   = (STRING, INTEGER, FLOAT, BOOLEAN, URL, SELECT, GROUP)
TYPES_SET   = frozenset([t['value'] for t in TYPES])
TYPE_LABELS = dict([(t['value'], t['label']) for t in TYPES])

# Boolean string values
TRUE  = frozenset(['true', 'yes', 't', 'y', '1'])
FALSE = frozenset(['false', 'no', 'f', 'n', '0'])

# User
USER_COOKIE    = 'orderportal_user'
API_KEY_HEADER = 'X-Orderportal-Api-Key'
TOKEN_HEADER   = 'X-Orderportal-Token'
# User states
PENDING       = 'pending'
ENABLED       = 'enabled'
DISABLED      = 'disabled'
USER_STATUSES = frozenset([PENDING, ENABLED, DISABLED])
# User role
ADMIN      = 'admin'
STAFF      = 'staff'
STD_ROLE   = USER
USER_ROLES = frozenset([USER, STAFF, ADMIN])
# Form states
FORM_STATUSES = frozenset([PENDING, ENABLED, DISABLED])
FORM_TRANSITONS = {PENDING: (ENABLED, DISABLED),
                   ENABLED: (DISABLED,),
                   DISABLED: ()}

# To be filled in from separate YAML file
ORDER_STATES = {}
ORDER_TRANSITIONS = {}

# Password
MIN_PASSWORD_LENGTH = 6

# Display
DEFAULT_MAX_DISPLAY_LOG = 20

# Source code directory
ROOT = os.path.dirname(__file__)
