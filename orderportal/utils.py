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

from orderportal import constants
from orderportal import designs
from orderportal import settings


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

    # Set logging state
    if settings.get('LOGGING_DEBUG'):
        kwargs = dict(level=logging.DEBUG)
    else:
        kwargs = dict(level=logging.INFO)
    try:
        kwargs['format'] = settings['LOGGING_FORMAT']
    except KeyError:
        pass
    try:
        filepath = settings['LOGGING_FILEPATH']
        if not filepath: raise KeyError
        kwargs['filename'] = filepath
    except KeyError:
        pass
    try:
        filemode = settings['LOGGING_FILEMODE']
        if not filemode: raise KeyError
        kwargs['filemode'] = filemode
    except KeyError:
        pass
    settings["LOG"] = log
    if log:
        logging.basicConfig(**kwargs)
        logging.info(f"OrderPortal version {constants.VERSION}")
        logging.info(f"ROOT: {constants.ROOT}")
        logging.info(f"SITE_DIR: {settings['SITE_DIR']}")
        logging.info(f"settings: {settings['SETTINGS_FILE']}")
        logging.info(f"logging debug: {settings['LOGGING_DEBUG']}")
        logging.info(f"tornado debug: {settings['TORNADO_DEBUG']}")

    # Check some settings.
    for key in ['BASE_URL','DATABASE_SERVER','DATABASE_NAME','COOKIE_SECRET']:
        if key not in settings:
            raise KeyError(f"No settings['{key}'] item.")
        if not settings[key]:
            raise ValueError(f"settings['{key}'] has invalid value.")
    if len(settings.get('COOKIE_SECRET', '')) < 10:
        raise ValueError("settings['COOKIE_SECRET'] not set, or too short.")
    # Read account messages YAML file.
    filepath = os.path.join(settings["SITE_DIR"], 
                            settings["ACCOUNT_MESSAGES_FILE"])
    logging.info(f"account messages: {filepath}")
    with open(filepath) as infile:
        settings['ACCOUNT_MESSAGES'] = yaml.safe_load(infile)
    # Set recipients, which are hardwired into the source code.
    # Also checks for missing message for a status.
    try:
        settings['ACCOUNT_MESSAGES'][constants.PENDING]['recipients'] = ['admin']
        settings['ACCOUNT_MESSAGES'][constants.ENABLED]['recipients'] = ['account']
        settings['ACCOUNT_MESSAGES'][constants.DISABLED]['recipients'] = ['account']
        settings['ACCOUNT_MESSAGES'][constants.RESET]['recipients'] = ['account']
    except KeyError:
        raise ValueError('Account messages file: missing message for status')

    # Check valid order identifier format; prefix all upper case characters
    if settings['ORDER_IDENTIFIER_FORMAT']:
        for c in settings['ORDER_IDENTIFIER_FORMAT']:
            if not c.isalpha(): break
            if not c.isupper():
                raise ValueError('ORDER_IDENTIFIER_FORMAT prefix must be'
                                 ' all upper-case characters')

    # Read order statuses definitions YAML file.
    filepath = os.path.join(settings["SITE_DIR"],
                            settings["ORDER_STATUSES_FILE"])
    logging.info(f"order statuses: {filepath}")
    with open(filepath) as infile:
        settings['ORDER_STATUSES'] = yaml.safe_load(infile)
    settings['ORDER_STATUSES_LOOKUP'] = lookup = dict()
    initial = None
    for status in settings['ORDER_STATUSES']:
        if status['identifier'] in lookup:
            raise ValueError("Order status '%s' multiple definitions." %
                             status['identifier'])
        lookup[status['identifier']] = status
        if status.get('initial'): initial = status
    if not initial:
        raise ValueError('No initial order status defined.')
    settings['ORDER_STATUS_INITIAL'] = initial

    # Read order status transition definiton YAML file.
    filepath = os.path.join(settings["SITE_DIR"],
                            settings["ORDER_TRANSITIONS_FILE"])
    logging.info(f"order transitions: {filepath}")
    with open(filepath) as infile:
        settings['ORDER_TRANSITIONS'] = yaml.safe_load(infile)

    # Read order messages YAML file.
    filepath = os.path.join(settings["SITE_DIR"],
                            settings["ORDER_MESSAGES_FILE"])
    logging.info(f"order messages: {filepath}")
    with open(filepath) as infile:
        settings['ORDER_MESSAGES'] = yaml.safe_load(infile)

    # Read universities YAML file.
    filepath = settings.get("UNIVERSITIES_FILE")
    if not filepath:
        settings['UNIVERSITIES'] = dict()
    else:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logging.info(f"universities lookup: {filepath}")
        with open(filepath) as infile:
            unis = yaml.safe_load(infile)
        unis = list(unis.items())
        unis.sort(key=lambda i: (i[1].get('rank'), i[0]))
        settings['UNIVERSITIES'] = dict(unis)

    # Read country codes YAML file
    filepath = settings.get("COUNTRY_CODES_FILE")
    if not filepath:
        settings['COUNTRIES'] = []
    else:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logging.info(f"country codes: {filepath}")
        with open(filepath) as infile:
            settings['COUNTRIES'] = yaml.safe_load(infile)
        settings['COUNTRIES_LOOKUP'] = dict([(c['code'], c['name'])
                                             for c in settings['COUNTRIES']])

    # Read subject terms YAML file.
    filepath = settings.get("SUBJECT_TERMS_FILE")
    if not filepath:
        settings['subjects'] = []
    else:
        filepath = os.path.join(settings["SITE_DIR"], filepath)
        logging.info(f"subject terms: {filepath}")
        with open(filepath) as infile:
            settings['subjects'] = yaml.safe_load(infile)
    settings['subjects_lookup'] = dict([(s['code'], s['term'])
                                        for s in settings['subjects']])

    # Settings computable from others.
    parts = urllib.parse.urlparse(settings['BASE_URL'])
    if not settings.get('BASE_URL_PATH_PREFIX') and parts.path:
        settings['BASE_URL_PATH_PREFIX'] = parts.path.rstrip('/') or None
    # BASE_URL should not contain any path part.
    settings['BASE_URL'] = "%s://%s/" % (parts.scheme, parts.netloc)

def terminology(word):
    "Return the display term for the given word. Use itself by default."
    try:
        istitle = word.istitle()
        word = settings['TERMINOLOGY'][word.lower()]
    except KeyError:
        pass
    else:
        if istitle: word = word.title()
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
    name = settings["DATABASE_NAME"]
    try:
        return server[name]
    except couchdb2.NotFoundError:
        raise KeyError(f"CouchDB database '{name}' does not exist.")

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

def get_iuid():
    "Return a unique instance identifier."
    return uuid.uuid4().hex

def timestamp(days=None):
    """Current date and time (UTC) in ISO format, with millisecond precision.
    Add the specified offset in days, if given.
    """
    instant = datetime.datetime.utcnow()
    if days:
        instant += datetime.timedelta(days=days)
    instant = instant.isoformat()
    return instant[:17] + "%06.3f" % float(instant[17:]) + "Z"

def epoch_to_iso(epoch):
    """Convert the given number of seconds since the epoch
    to date and time in ISO format.
    """
    dt = datetime.datetime.fromtimestamp(float(epoch))
    return dt.isoformat() + 'Z'

def today(days=None):
    """Current date (UTC) in ISO format.
    Add the specified offset in days, if given.
    """
    instant = datetime.datetime.utcnow()
    if days:
        instant += datetime.timedelta(days=days)
    result = instant.isoformat()
    return result[:result.index('T')]

def to_bool(value):
    "Convert the value into a boolean, interpreting various string values."
    if isinstance(value, bool): return value
    if not value: return False
    lowvalue = value.lower()
    if lowvalue in constants.TRUE: return True
    if lowvalue in constants.FALSE: return False
    raise ValueError("invalid boolean: '{0}'".format(value))

def convert(type, value):
    "Convert the string representation to the given type."
    if value is None: return None
    if value == '': return None
    if type == 'int':
        return int(value)
    elif type == 'float':
        return float(value)
    elif type == 'boolean':
        return to_bool(value)
    else:
        return value

def markdown2html(text, safe=False):
    "Process the text from Markdown to HTML."
    text = text or ''
    if not safe:
        text = tornado.escape.xhtml_escape(text)
    return markdown.markdown(text, output_format='html5')

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
        while len(value) and value[0] in '=-+@':
            value = value[1:]
    elif value is None:
        value = ''
    return value

def get_json(id, type):
    "Return a JSON dictionary initialized with with id and type."
    result = dict()
    result['id'] = id
    result['type'] = type
    result['site'] = settings['SITE_NAME']
    result['timestamp'] = timestamp()
    return result

def get_account_name(account=None, value=None):
    """Return person name of account as 'lastname, firstname'.
    'account' is an account document.
    'value' is a row value from a view.
    """
    if account is not None:
        last_name = account.get('last_name')
        first_name = account.get('first_name')
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
    if len(password) < settings['MIN_PASSWORD_LENGTH']:
        raise ValueError("Password must be at least {0} characters long.".
                         format(settings['MIN_PASSWORD_LENGTH']))

def hashed_password(password):
    "Return the password in hashed form."
    sha256 = hashlib.sha256()
    sha256.update(settings['PASSWORD_SALT'].encode())
    sha256.update(password.encode())
    return sha256.hexdigest()

def log(db, rqh, entity, changed=dict()):
    "Add a log entry for the change of the given entity."
    entry = dict(_id=get_iuid(),
                 entity=entity['_id'],
                 entity_type=entity[constants.DOCTYPE],
                 changed=changed,
                 modified=timestamp())
    entry[constants.DOCTYPE] = constants.LOG
    if rqh:
        # xheaders argument to HTTPServer takes care of X-Real-Ip
        # and X-Forwarded-For
        entry['remote_ip'] = rqh.request.remote_ip
        try:
            entry['user_agent'] = rqh.request.headers['User-Agent']
        except KeyError:
            pass
    try:
        entry['account'] = rqh.current_user['email']
    except (AttributeError, TypeError, KeyError):
        pass
    db.put(entry)

def get_filename_extension(content_type):
    "Return filename extension, correcting for silliness in 'mimetypes'."
    try:
        return constants.MIME_EXTENSIONS[content_type]
    except KeyError:
        return mimetypes.guess_extension(content_type)

def parse_field_table_column(coldef):
    """Parse the input field table column definition.
    Return dictionary with identifier, type and options (if any).
    """
    parts = [p.strip() for p in coldef.split(';')]
    if len(parts) == 1:
        return {'identifier': coldef, 'type': 'string'}
    else:
        result = {'identifier': parts[0], 'type': parts[1]}
        if result['type'] == 'select':
            result['options'] = parts[2].split('|')
        return result


class CsvWriter(object):
    "Write rows serially to a CSV file."

    def __init__(self, worksheet='Main'):
        self.csvbuffer = io.StringIO()
        self.writer = csv.writer(self.csvbuffer, quoting=csv.QUOTE_NONNUMERIC)

    def writerow(self, row):
        self.writer.writerow(csv_safe_row(row))

    def new_worksheet(self, name):
        self.writer.writerow(('',))

    def getvalue(self):
        return self.csvbuffer.getvalue()


class XlsxWriter(object):
    "Write rows serially to an XLSX file."

    def __init__(self, worksheet='Main'):
        self.xlsxbuffer = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.xlsxbuffer, {'in_memory':True})
        self.ws = self.workbook.add_worksheet(worksheet)
        self.x = 0

    def new_worksheet(self, name):
        self.ws = self.workbook.add_worksheet(name)
        self.x = 0

    def writerow(self, row):
        for y, item in enumerate(row):
            if isinstance(item, str):
                self.ws.write(self.x, y, item.replace('\r', ''))
            else:
                self.ws.write(self.x, y, item)
        self.x += 1

    def getvalue(self):
        self.workbook.close()
        self.xlsxbuffer.seek(0)
        return self.xlsxbuffer.getvalue()
