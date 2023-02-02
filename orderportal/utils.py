"Various utility functions."

import csv
import datetime
import hashlib
import io
import logging
import mimetypes
import os
import os.path
import sys
import time
import traceback
import urllib.request, urllib.parse, urllib.error
import urllib.parse
import uuid

import couchdb2
import markdown
import tornado.web
import tornado.escape
import xlsxwriter
import yaml

from orderportal import constants, settings, parameters


LOG_DESIGN_DOC = {
    "views": {
        "account": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.account) return;
    emit([doc.account, doc.modified], null);
}"""},
        "entity": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    emit([doc.entity, doc.modified], null);
}"""},
        "login_failure": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.changed.login_failure) return;
    emit([doc.entity, doc.modified], doc.changed.login_failure);
}"""}
    }
}

META_DESIGN_DOC = {
    "views": {
        "id": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'meta') return;
    emit(doc._id, null);
}"""}
    }
}


def load_settings(filepath=None, log=True):
    """Load the settings. The file path first specified is used.
    1) The argument to this procedure (possibly from a command line argument).
    2) The path environment variable ORDERPORTAL_SETTINGS.
    3) The file '../site/settings.yaml' relative to this directory.
    If 'log' is True, activate logging according to DEBUG settings.
    Raise IOError if settings file could not be read.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if a settings variable value is invalid.
    """
    parameters["SETTINGS_KEYS"] = set(settings.keys())
    site_dir = settings["SITE_DIR"]
    if not os.path.exists(site_dir):
        raise IOError(f"The required site directory '{site_dir}' does not exist.")
    if not os.path.isdir(site_dir):
        raise IOError(f"The site directory path '{site_dir}' is not a directory.")
    # Find and read the settings file, updating the defaults.
    if not filepath:
        try:
            filepath = os.environ["ORDERPORTAL_SETTINGS"]
        except KeyError:
            filepath = os.path.join(site_dir, "settings.yaml")
    with open(filepath) as infile:
        settings.update(yaml.safe_load(infile))
    settings["SETTINGS_FILE"] = filepath
    parameters["SETTINGS_KEYS"].add("SETTINGS_FILE")

    # Set logging state
    if settings.get("LOGGING_DEBUG"):
        kwargs = dict(level=logging.DEBUG)
    else:
        kwargs = dict(level=logging.INFO)
    try:
        kwargs["format"] = settings["LOGGING_FORMAT"]
    except KeyError:
        pass
    try:
        filepath = settings["LOGGING_FILEPATH"]
        if not filepath:
            raise KeyError
        kwargs["filename"] = filepath
    except KeyError:
        pass
    try:
        filemode = settings["LOGGING_FILEMODE"]
        if not filemode:
            raise KeyError
        kwargs["filemode"] = filemode
    except KeyError:
        pass
    if log:
        logging.basicConfig(**kwargs)
        logging.info(f"OrderPortal version {constants.VERSION}")
        logging.info(f"ROOT: {constants.ROOT}")
        logging.info(f"SITE_DIR: {settings['SITE_DIR']}")
        logging.info(f"settings: {settings['SETTINGS_FILE']}")
        logging.info(f"logging debug: {settings['LOGGING_DEBUG']}")
        logging.info(f"tornado debug: {settings['TORNADO_DEBUG']}")

    # Check some settings.
    for key in ["BASE_URL", "DATABASE_SERVER", "DATABASE_NAME", "COOKIE_SECRET"]:
        if key not in settings:
            raise KeyError(f"No settings['{key}'] item.")
        if not settings[key]:
            raise ValueError(f"settings['{key}'] has invalid value.")
    if len(settings.get("COOKIE_SECRET", "")) < 10:
        raise ValueError("settings['COOKIE_SECRET'] not set, or too short.")

    # Check valid order identifier format; prefix all upper case characters
    if not settings["ORDER_IDENTIFIER_FORMAT"]:
        raise ValueError("Undefined ORDER_IDENTIFIER_FORMAT")
    if not isinstance(settings["ORDER_IDENTIFIER_FIRST"], int):
        raise ValueError("ORDER_IDENTIFIER_FIRST is not an integer")
    if not settings["ORDER_IDENTIFIER_FORMAT"][0].isalpha():
        raise ValueError(
            "ORDER_IDENTIFIER_FORMAT prefix contain at least one alphabetical character"
        )
    for c in settings["ORDER_IDENTIFIER_FORMAT"]:
        if not c.isalpha():
            break
        if not c.isupper():
            raise ValueError(
                "ORDER_IDENTIFIER_FORMAT prefix must be all upper-case characters"
            )

    # Read order messages YAML file.
    filepath = settings.get("ORDER_MESSAGES_FILE")
    if filepath:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logging.info(f"order messages file: {filepath}")
        with open(filepath) as infile:
            settings["ORDER_MESSAGES"] = yaml.safe_load(infile) or {}
    else:
        settings["ORDER_MESSAGES"] = {}

    # Read universities YAML file.
    filepath = settings.get("UNIVERSITIES_FILE")
    if filepath:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logging.info(f"universities lookup file: {filepath}")
        with open(filepath) as infile:
            unis = yaml.safe_load(infile) or {}
        unis = list(unis.items())
        unis.sort(key=lambda i: (i[1].get("rank"), i[0]))
        settings["UNIVERSITIES"] = dict(unis)
    else:
        settings["UNIVERSITIES"] = {}

    # Read subject terms YAML file.
    filepath = settings.get("SUBJECT_TERMS_FILE")
    if filepath:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logging.info(f"subject terms file: {filepath}")
        with open(filepath) as infile:
            settings["SUBJECT_TERMS"] = yaml.safe_load(infile) or []
    else:
        settings["SUBJECT_TERMS"] = []
    settings["SUBJECT_TERMS_LOOKUP"] = dict(
        [(s["code"], s["term"]) for s in settings["SUBJECT_TERMS"]]
    )

    # Settings computable from others.
    parts = urllib.parse.urlparse(settings["BASE_URL"])
    if not settings.get("BASE_URL_PATH_PREFIX") and parts.path:
        settings["BASE_URL_PATH_PREFIX"] = parts.path.rstrip("/") or None
    # BASE_URL should not contain any path part.
    settings["BASE_URL"] = "%s://%s/" % (parts.scheme, parts.netloc)


def terminology(word):
    "Return the display term for the given word. Use itself by default."
    try:
        istitle = word.istitle()
        word = settings["TERMINOLOGY"][word.lower()]
    except KeyError:
        pass
    else:
        if istitle:
            word = word.title()
    return word


def get_dbserver():
    "Return the CouchDB2 handle for the CouchDB server."
    kwargs = dict(href=settings["DATABASE_SERVER"])
    if settings.get("DATABASE_ACCOUNT") and settings.get("DATABASE_PASSWORD"):
        kwargs["username"] = settings["DATABASE_ACCOUNT"]
        kwargs["password"] = settings["DATABASE_PASSWORD"]
    return couchdb2.Server(**kwargs)


def get_db():
    "Return the handle for the CouchDB database."
    server = get_dbserver()
    try:
        return server[settings["DATABASE_NAME"]]
    except couchdb2.NotFoundError:
        raise KeyError(
            f"""CouchDB database '{settings["DATABASE_NAME"]}' does not exist."""
        )


def load_design_documents(db):
    "Load the design documents for the entities."
    import orderportal.account
    import orderportal.event
    import orderportal.file
    import orderportal.form
    import orderportal.group
    import orderportal.info
    import orderportal.message
    import orderportal.news
    import orderportal.order
    import orderportal.admin    # Yes, admin

    if db.put_design("account", orderportal.account.DESIGN_DOC):
        logging.info("Updated 'account' design document.")
    if db.put_design("event", orderportal.event.DESIGN_DOC):
        logging.info("Updated 'event' design document.")
    if db.put_design("file", orderportal.file.DESIGN_DOC):
        logging.info("Updated 'file' design document.")
    if db.put_design("form", orderportal.form.DESIGN_DOC):
        logging.info("Updated 'form' design document.")
    if db.put_design("group", orderportal.group.DESIGN_DOC):
        logging.info("Updated 'group' design document.")
    if db.put_design("info", orderportal.info.DESIGN_DOC):
        logging.info("Updated 'info' design document.")
    if db.put_design("log", LOG_DESIGN_DOC):
        logging.info("Updated 'log' design document.")
    if db.put_design("message", orderportal.message.DESIGN_DOC):
        logging.info("Updated 'message' design document.")
    if db.put_design("meta", META_DESIGN_DOC):
        logging.info("Updated 'meta' design document.")
    if db.put_design("news", orderportal.news.DESIGN_DOC):
        logging.info("Updated 'news' design document.")
    # Replace variables in the function body according to 'settings'.
    func = orderportal.order.DESIGN_DOC["views"]["keyword"]["map"]
    delims_lint = "".join(settings["ORDERS_SEARCH_DELIMS_LINT"])
    lint = "{%s}" % ", ".join(["'%s': 1" % w for w in settings["ORDERS_SEARCH_LINT"]])
    func = func.format(delims_lint=delims_lint, lint=lint)
    orderportal.order.DESIGN_DOC["views"]["keyword"]["map"] = func
    if db.put_design("order", orderportal.order.DESIGN_DOC):
        logging.info("Updated 'order' design document.")
    if db.put_design("text", orderportal.admin.DESIGN_DOC): # Yes, admin
        logging.info("Updated 'text' design document.")


def get_count(db, designname, viewname, key=None):
    "Get the reduce value for the name view and the given key."
    if key is None:
        view = db.view(designname, viewname, reduce=True)
    else:
        view = db.view(designname, viewname, key=key, reduce=True)
    try:
        return list(view)[0].value
    except IndexError:
        return 0


def get_counts(db):
    "Get the counts for the most important types of entities in the database."
    return dict(n_orders=get_count(db, "order", "status"),
                n_forms=get_count(db, "form", "all"),
                n_accounts=get_count(db, "account", "all"),
                n_documents=len(db))


def get_iuid():
    "Return a unique instance identifier."
    return uuid.uuid4().hex


def get_document(db, identifier):
    """Get the database document by identifier, else None.
    The identifier may be an account email, account API key, file name, info name,
    order identifier, or '_id' of the CouchDB document.
    """
    if not identifier:          # If empty string, database info is returned.
        return None
    for designname, viewname in [
        ("account", "email"),
        ("account", "api_key"),
        ("file", "name"),
        ("info", "name"),
        ("order", "identifier"),
    ]:
        try:
            view = db.view(
                designname, viewname, key=identifier, reduce=False, include_docs=True
            )
            result = list(view)
            if len(result) == 1:
                return result[0].doc
        except KeyError:
            pass
    try:
        return db[identifier]
    except couchdb2.NotFoundError:
        return None


def timestamp(days=None):
    """Current date and time (UTC) in ISO format, with millisecond precision.
    Add the specified offset in days, if given.
    """
    instant = datetime.datetime.utcnow()
    if days:
        instant += datetime.timedelta(days=days)
    instant = instant.isoformat()
    return instant[:17] + "%06.3f" % float(instant[17:]) + "Z"


def today(days=None):
    """Current date (UTC) in ISO format.
    Add the specified offset in days, if given.
    """
    instant = datetime.datetime.utcnow()
    if days:
        instant += datetime.timedelta(days=days)
    result = instant.isoformat()
    return result[: result.index("T")]


def to_bool(value):
    "Convert the value into a boolean, interpreting various string values."
    if isinstance(value, bool):
        return value
    if not value:
        return False
    lowvalue = value.lower()
    if lowvalue in constants.TRUE:
        return True
    if lowvalue in constants.FALSE:
        return False
    raise ValueError("invalid boolean: '{0}'".format(value))


def convert(type, value):
    "Convert the string representation to the given type."
    if value is None:
        return None
    if value == "":
        return None
    if type == "int":
        return int(value)
    elif type == "float":
        return float(value)
    elif type == "boolean":
        return to_bool(value)
    else:
        return value


def markdown2html(text, safe=False):
    "Process the text from Markdown to HTML."
    text = text or ""
    if not safe:
        text = tornado.escape.xhtml_escape(text)
    return markdown.markdown(text, output_format="html5")


def csv_safe_row(row):
    "Make all values in the row safe for CSV. See 'csv_safe'."
    row = list(row)
    for pos, value in enumerate(row):
        row[pos] = csv_safe(value)
    return row


def csv_safe(value):
    """Remove any beginning character '=-+@' from string value.
    Change None to empty string.
    See http://georgemauer.net/2017/10/07/csv-injection.html
    """
    if isinstance(value, str):
        while len(value) and value[0] in "=-+@":
            value = value[1:]
    elif value is None:
        value = ""
    return value


def get_json(id, type):
    "Return a JSON dictionary initialized with with id and type."
    result = dict()
    result["id"] = id
    result["type"] = type
    result["site"] = settings["SITE_NAME"]
    result["timestamp"] = timestamp()
    return result


def get_account_name(account=None, value=None):
    """Return person name of account as 'lastname, firstname'.
    'account' is an account document.
    'value' is a row value from a view.
    """
    if account is not None:
        last_name = account.get("last_name")
        first_name = account.get("first_name")
    elif value is not None:
        first_name, last_name = value
    if last_name:
        if first_name:
            name = "{0}, {1}".format(last_name, first_name)
        else:
            name = last_name
    else:
        name = first_name
    return name


def check_password(password):
    """Check that the password is long and complex enough.
    Raise ValueError otherwise."""
    if len(password) < settings["MIN_PASSWORD_LENGTH"]:
        raise ValueError(
            "Password must be at least {0} characters long.".format(
                settings["MIN_PASSWORD_LENGTH"]
            )
        )


def hashed_password(password):
    "Return the password in hashed form."
    sha256 = hashlib.sha256()
    sha256.update(settings["PASSWORD_SALT"].encode())
    sha256.update(password.encode())
    return sha256.hexdigest()


def log(db, rqh, entity, changed=dict()):
    "Add a log entry for the change of the given entity."
    entry = dict(
        _id=get_iuid(),
        entity=entity["_id"],
        entity_type=entity[constants.DOCTYPE],
        changed=changed,
        modified=timestamp(),
    )
    entry[constants.DOCTYPE] = constants.LOG
    if rqh:
        # xheaders argument to HTTPServer takes care of X-Real-Ip
        # and X-Forwarded-For
        entry["remote_ip"] = rqh.request.remote_ip
        try:
            entry["user_agent"] = rqh.request.headers["User-Agent"]
        except KeyError:
            pass
    try:
        entry["account"] = rqh.current_user["email"]
    except (AttributeError, TypeError, KeyError):
        pass
    db.put(entry)


def get_filename_extension(content_type):
    "Return filename extension, correcting for silliness in 'mimetypes'."
    try:
        return constants.MIMETYPE_EXTENSIONS[content_type]
    except KeyError:
        return mimetypes.guess_extension(content_type)


def parse_field_table_column(coldef):
    """Parse the input field table column definition.
    Return dictionary with identifier, type and options (if any).
    """
    parts = [p.strip() for p in coldef.split(";")]
    if len(parts) == 1:
        return {"identifier": coldef, "type": "string"}
    else:
        result = {"identifier": parts[0], "type": parts[1]}
        if result["type"] == "select":
            result["options"] = parts[2].split("|")
        return result


class CsvWriter(object):
    "Write rows serially to a CSV file."

    def __init__(self, worksheet="Main"):
        self.csvbuffer = io.StringIO()
        self.writer = csv.writer(self.csvbuffer, quoting=csv.QUOTE_NONNUMERIC)

    def writerow(self, row):
        self.writer.writerow(csv_safe_row(row))

    def new_worksheet(self, name):
        self.writer.writerow(("",))

    def getvalue(self):
        return self.csvbuffer.getvalue()


class XlsxWriter(object):
    "Write rows serially to an XLSX file."

    def __init__(self, worksheet="Main"):
        self.xlsxbuffer = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.xlsxbuffer, {"in_memory": True})
        self.ws = self.workbook.add_worksheet(worksheet)
        self.x = 0

    def new_worksheet(self, name):
        self.ws = self.workbook.add_worksheet(name)
        self.x = 0

    def writerow(self, row):
        for y, item in enumerate(row):
            if isinstance(item, str):
                self.ws.write(self.x, y, item.replace("\r", ""))
            else:
                self.ws.write(self.x, y, item)
        self.x += 1

    def getvalue(self):
        self.workbook.close()
        self.xlsxbuffer.seek(0)
        return self.xlsxbuffer.getvalue()
