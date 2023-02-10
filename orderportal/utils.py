"Various utility functions."

import csv
import datetime
import hashlib
import io
import mimetypes
import uuid

import couchdb2
import markdown
import tornado.web
import tornado.escape
import xlsxwriter
import yaml

from orderportal import constants, settings


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
