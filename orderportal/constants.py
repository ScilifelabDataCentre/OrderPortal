" OrderPortal: Various constants."

from __future__ import unicode_literals, print_function, absolute_import

import re
import os.path

# Content types (MIME types)
TEXT_MIME      = 'text/plain'
MARKDOWN_MIME  = 'text/x-markdown'
HTML_MIME      = 'text/html'
XHTML_MIME     = 'application/xhtml+xml'
JPEG_MIME      = 'image/jpeg'
PNG_MIME       = 'image/png'
BIN_MIME       = 'application/octet-stream'
JSON_MIME      = 'application/json'
WWWFORM_MIME   = 'application/x-www-form-urlencoded'
MULTIPART_MIME = 'multipart/form-data'
TEXT_MIMES     = frozenset([TEXT_MIME, MARKDOWN_MIME])
HTML_MIMES     = frozenset([HTML_MIME, XHTML_MIME])
IMAGE_MIMES    = frozenset([JPEG_MIME, PNG_MIME])

# Patterns
IUID_RX  = re.compile(r'^[0-9a-f]{32}$')
PATH_RX  = re.compile(r'^(?:/[a-z][-a-z0-9_]*){2,}$', re.IGNORECASE)
NAME_RX  = re.compile(r'^[a-z][-a-z0-9_]*$', re.IGNORECASE)
EMAIL_RX = re.compile(r'^[^@]+@[^@]+\.[^@]+$')

# CouchDB
# For view ranges: CouchDB uses the Unicode Collation Algorithm,
# which is not the same as the ASCII collation sequence.
# The endkey is inclusive, by default.
HIGH_CHAR = 'ZZZZZZZZ'

# Documents
DOCTYPE  = 'orderportal_doctype'
FIELD    = 'field'
ORDER    = 'order'
USER     = 'user'
LOG      = 'log'
ENTITIES = frozenset([FIELD, ORDER])

# Value types
STRING  = dict(value='string', label='String')
INTEGER = dict(value='int', label='Integer')
FLOAT   = dict(value='float', label='Float')
BOOLEAN = dict(value='boolean', label='Boolean')
URI     = dict(value='anyURI', label='URI')
TYPES   = (STRING, INTEGER, FLOAT, BOOLEAN, URI)
TYPES_SET   = frozenset([t['value'] for t in TYPES])
TYPE_LABELS = dict([(t['value'], t['label']) for t in TYPES])

# Boolean string values
TRUE  = frozenset(['true', 'yes', 't', 'y', '1'])
FALSE = frozenset(['false', 'no', 'f', 'n', '0'])

# User
USER_COOKIE    = 'orderportal_user'
API_KEY_HEADER = 'X-Orderportal-Api-Key'
TOKEN_HEADER   = 'X-Orderportal-Token'
PENDING        = 'pending'
ACTIVE         = 'active'
BLOCKED        = 'blocked'
USER_STATUSES  = frozenset([PENDING, ACTIVE, BLOCKED])
ADMIN          = 'admin'
STD_ROLE       = USER
USER_ROLES     = frozenset([USER, ADMIN])

# Display
DEFAULT_MAX_DISPLAY_LOG = 20

# Source code directory
ROOT = os.path.dirname(__file__)
