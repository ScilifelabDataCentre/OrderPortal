"""OrderPortal: A portal for orders to a facility from its users.
An order can be a project application, a request, a report, etc.
"""

import copy
import os.path
import re
import sys

import pycountry


__version__ = "10.1.0"


class Constants:
    def __setattr__(self, key, value):
        raise ValueError("setting constant is not allowed")

    VERSION = __version__
    SOURCE_URL = "https://github.com/pekrau/OrderPortal"
    ROOT = os.path.dirname(os.path.abspath(__file__))

    PYTHON_VERSION = ".".join([str(i) for i in sys.version_info[0:3]])
    PYTHON_URL = "https://www.python.org/"

    TORNADO_URL = "https://pypi.org/project/tornado/"
    COUCHDB_URL = "https://couchdb.apache.org/"
    COUCHDB2_URL = "https://pypi.org/project/couchdb2"
    REQUESTS_URL = "https://docs.python-requests.org/"
    XLSXWRITER_URL = "https://pypi.org/project/XlsxWriter/"
    MARKDOWN_URL = "https://pypi.org/project/Markdown/"
    MARKDOWN_NOTATION_INFO_URL = "https://www.markdownguide.org/cheat-sheet/"
    PYYAML_URL = "https://pypi.org/project/PyYAML/"

    BOOTSTRAP_VERSION = "3.4.1"
    BOOTSTRAP_URL = "https://getbootstrap.com/docs/3.4/"

    JQUERY_VERSION = "1.12.4"
    JQUERY_URL = "https://jquery.com/"

    JQUERY_UI_VERSION = "1.11.4"

    JQUERY_LOCALTIME_VERSION = "0.9.1"
    JQUERY_LOCALTIME_URL = "https://plugins.jquery.com/jquery.localtime/"

    DATATABLES_VERSION = "1.10.11"
    DATATABLES_URL = "https://datatables.net/"

    LOGGING_FORMAT = "%(asctime)s %(name)s %(levelname)s %(message)s"

    ID_RX = re.compile(r"^[a-z][_a-z0-9]*$", re.IGNORECASE)
    NAME_RX = re.compile(r"^[^/]+$")
    IUID_RX = re.compile(r"^[0-9a-f]{32}$")
    DATE_RX = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}$")  # Works until 9999 CE...
    EMAIL_RX = re.compile(r"^[^@]+@[^@]+\.[^@]+$")

    # For CouchDB view ranges: CouchDB uses the Unicode Collation Algorithm,
    # which is not the same as the ASCII collation sequence.
    # The endkey is inclusive, by default.
    CEILING = "ZZZZZZZZ"

    # Entity document types.
    DOCTYPE = "orderportal_doctype"
    ACCOUNT = "account"
    GROUP = "group"
    FORM = "form"
    ORDER = "order"
    NEWS = "news"
    EVENT = "event"
    TEXT = "text"
    INFO = "info"
    FILE = "file"
    MESSAGE = "message"
    REPORT = "report"
    LOG = "log"
    META = "meta"
    ENTITIES = frozenset([ACCOUNT, GROUP, FORM, ORDER, INFO, FILE, MESSAGE, REPORT])

    # # System attachments to order.
    # SYSTEM = "system"
    # SYSTEM_REPORT = "system_report"

    # Field types.
    STRING = "string"
    EMAIL = "email"
    INT = "int"
    FLOAT = "float"
    BOOLEAN = "boolean"
    URL = "url"
    SELECT = "select"
    MULTISELECT = "multiselect"
    ### TEXT = "text" Already defined above.
    DATE = "date"
    TABLE = "table"
    ### GROUP   = 'group' Already defined above.
    ### FILE    = 'file' Already defined above.
    TYPES = (
        STRING,
        EMAIL,
        INT,
        FLOAT,
        BOOLEAN,
        URL,
        SELECT,
        MULTISELECT,
        TEXT,
        DATE,
        TABLE,
        FILE,
        GROUP,
    )
    TYPE_HTML = {
        STRING: "text",
        INT: "number",
        DATE: "date",
        EMAIL: "email",
        URL: "url",
    }
    # Step for use with input type 'float'.
    FLOAT_STEP = "0.0000001"
    # Number of new rows to show in field table edit view.
    FIELD_TABLE_ADD_N_ROWS = 4

    # Forbidden meta document id's; have changed format or been removed.
    # Re-using these id's would likely create backwards incompatibility issues.
    FORBIDDEN_META_IDS = frozenset(
        ["account_messages", "order_messages", "global_modes"]
    )

    # Text types.
    DISPLAY = "display"
    ### ACCOUNT = "account" Already defined above.
    ### ORDER = "order" Already defined above.

    # Boolean string values.
    TRUE = frozenset(["true", "yes", "t", "y", "1"])
    FALSE = frozenset(["false", "no", "f", "n", "0"])

    # User login account.
    USER_COOKIE = "orderportal_user"
    API_KEY_HEADER = "X-OrderPortal-API-key"

    # Account statuses; hard-wired!
    PENDING = "pending"
    ENABLED = "enabled"
    DISABLED = "disabled"
    RESET = "reset"
    ACCOUNT_STATUSES = (PENDING, ENABLED, DISABLED, RESET)

    # Account roles.
    USER = "user"
    STAFF = "staff"
    ADMIN = "admin"
    ACCOUNT_ROLES = (USER, STAFF, ADMIN)

    # Form statuses; hard-wired!
    TESTING = "testing"
    FORM_STATUSES = (PENDING, TESTING, ENABLED, DISABLED)

    # The possible order statuses are now hard-wired.
    # The two first order statuses must always be present!
    # All statuses are stored in a meta document 'order_statuses' in the database,
    # with the changes made from the admin.DEFAULT_ORDER_STATUSES
    PREPARATION = "preparation"
    SUBMITTED = "submitted"
    REVIEW = "review"
    QUEUED = "queued"
    WAITING = "waiting"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PROCESSING = "processing"
    ACTIVE = "active"
    ANALYSIS = "analysis"
    ONHOLD = "onhold"
    HALTED = "halted"
    ABORTED = "aborted"
    TERMINATED = "terminated"
    CANCELLED = "cancelled"
    FINISHED = "finished"
    COMPLETED = "completed"
    CLOSED = "closed"
    DELIVERED = "delivered"
    INVOICED = "invoiced"
    ARCHIVED = "archived"
    UNDEFINED = "undefined"
    ORDER_STATUSES = (
        PREPARATION,
        SUBMITTED,
        REVIEW,
        QUEUED,
        WAITING,
        ACCEPTED,
        REJECTED,
        PROCESSING,
        ACTIVE,
        ANALYSIS,
        ONHOLD,
        HALTED,
        ABORTED,
        TERMINATED,
        CANCELLED,
        FINISHED,
        COMPLETED,
        CLOSED,
        DELIVERED,
        INVOICED,
        ARCHIVED,
        UNDEFINED,
    )

    # Delimiters to remove when searching for orders.
    ORDERS_SEARCH_DELIMS_LINT = (":", ",", ";", "'")
    # Words to remove when searching for orders.
    ORDERS_SEARCH_LINT = (
        "an",
        "to",
        "in",
        "on",
        "of",
        "and",
        "the",
        "is",
        "was",
        "not",
    )

    # Sources in account for autopopulating an order field.
    # NOTE: This must be kept in sync with code in 'order.py' 'OrderSaver.autopopulate'.
    ORDER_AUTOPOPULATE_SOURCES = (
        "university",
        "department",
        "phone",
        "invoice_ref",
        "invoice_vat",
        "address.university",
        "address.department",
        "address.address",
        "address.zip",
        "address.city",
        "address.country",
        "invoice_address.university",
        "invoice_address.department",
        "invoice_address.address",
        "invoice_address.zip",
        "invoice_address.city",
        "invoice_address.country",
    )

    # Terminology: terms that can be translated to other terms.
    TERMINOLOGY_TERMS = ("order", "orders")

    # Report statuses; hard-wired!
    # REVIEW = "review" Already defined above.
    PUBLISHED = "published"
    APPROVED = "approved"
    # REJECTED = "rejected" Already defined above.
    REPORT_STATUSES = (REVIEW, PUBLISHED, REJECTED)
    REPORT_REVIEW_STATUSES = (REVIEW, APPROVED, REJECTED)

    ALL_STATUSES = frozenset(
        ACCOUNT_STATUSES
        + FORM_STATUSES
        + ORDER_STATUSES
        + REPORT_STATUSES
        + REPORT_REVIEW_STATUSES
    )

    # Content types (MIME types).
    HTML_MIMETYPE = "text/html"
    JSON_MIMETYPE = "application/json"
    CSV_MIMETYPE = "text/csv"
    ZIP_MIMETYPE = "application/zip"
    TEXT_MIMETYPE = "text/plain"
    BIN_MIMETYPE = "application/octet-stream"
    PDF_MIMETYPE = "application/pdf"
    JPEG_MIMETYPE = "image/jpeg"
    PNG_MIMETYPE = "image/png"
    XLSX_MIMETYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    XLSM_MIMETYPE = "application/vnd.ms-excel.sheet.macroEnabled.12"

    # Hard-wired mapping content type -> extension (overriding mimetypes module).
    MIMETYPE_EXTENSIONS = {
        TEXT_MIMETYPE: ".txt",
        JPEG_MIMETYPE: ".jpg",
        XLSM_MIMETYPE: ".xlsm",
        XLSX_MIMETYPE: ".xlsx",
    }

    # Content-type to icon mapping.
    CONTENT_TYPE_ICONS = {
        JSON_MIMETYPE: "json.png",
        CSV_MIMETYPE: "csv.png",
        TEXT_MIMETYPE: "text.png",
        HTML_MIMETYPE: "html.png",
        PDF_MIMETYPE: "pdf.png",
        PNG_MIMETYPE: "image.png",
        JPEG_MIMETYPE: "image.png",
        "application/vnd.ms-excel": "excel.png",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "excel.png",
        "application/vnd.ms-excel": "excel.png",
        XLSX_MIMETYPE: "excel.png",
        XLSM_MIMETYPE: "excel.png",
        "application/msword": "word.png",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "word.png",
        "application/vnd.ms-powerpoint": "ppt.png",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "ppt.png",
    }
    DEFAULT_CONTENT_TYPE_ICON = "binary.png"

    COUNTRIES = dict(
        sorted([(c.alpha_2, c.name) for c in pycountry.countries], key=lambda c: c[1])
    )


constants = Constants()


DEFAULT_SETTINGS = dict(
    TORNADO_DEBUG=False,
    LOGGING_DEBUG=False,
    BASE_URL="http://localhost:8881/",
    BASE_URL_PATH_PREFIX=None,
    PORT=8881,  # The port used by tornado.
    DATABASE_SERVER="http://localhost:5984/",
    DATABASE_NAME="orderportal",
    DATABASE_ACCOUNT="orderportal_account",
    DATABASE_PASSWORD=None,
    COOKIE_SECRET=None,
    PASSWORD_SALT=None,
    SETTINGS_FILE=None,
    SITE_DIR=os.path.normpath(os.path.join(constants.ROOT, "../site")),
    SITE_STATIC_DIR=os.path.normpath(os.path.join(constants.ROOT, "../site/static")),
    SITE_NAME="OrderPortal",
    SITE_FAVICON="orderportal32.png",
    SITE_NAVBAR_ICON="orderportal32.png",
    SITE_HOME_ICON="orderportal144.png",
    SITE_CSS_FILE=None,
    SITE_HOST_URL=None,
    SITE_HOST_ICON=None,
    SITE_HOST_TITLE=None,
    ORDER_MESSAGES_FILE="order_messages.yaml",
    SUBJECT_TERMS_FILE="subject_terms.yaml",
    ORDER_IDENTIFIER_FORMAT="OP{0:=05d}",
    ORDER_IDENTIFIER_FIRST=1,
    MAIL_SERVER=None,  # If not set, then no emails can be sent.
    MAIL_DEFAULT_SENDER=None,  # If not set, MAIL_USERNAME will be used.
    MAIL_PORT=25,
    MAIL_USE_SSL=False,
    MAIL_USE_TLS=False,
    MAIL_EHLO=None,
    MAIL_USERNAME=None,
    MAIL_PASSWORD=None,
    MAIL_REPLY_TO=None,
    DISPLAY_MENU_LIGHT=False,
    DISPLAY_MENU_ITEM_URL=None,
    DISPLAY_MENU_ITEM_TEXT=None,
    DISPLAY_DEFAULT_PAGE_SIZE=25,  # Number of paged items in a table.
    DISPLAY_MAX_PENDING_ACCOUNTS=10,  # Max number in home page for admin and staff.
    DISPLAY_DEFAULT_MAX_LOG=20,  # Max number of log items displayed.
    DISPLAY_NEWS=True,
    DISPLAY_MAX_NEWS=4,
    DISPLAY_EVENTS=True,
    DISPLAY_MENU_INFORMATION=True,
    DISPLAY_MENU_DOCUMENTS=True,
    DISPLAY_MENU_CONTACT=True,
    DISPLAY_MENU_ABOUT_US=True,
    DISPLAY_TEXT_MARKDOWN_NOTATION_INFO=True,
)

# Settings to be modified by 'settings.yaml' file, by computed values, or from database.
settings = copy.deepcopy(DEFAULT_SETTINGS)
