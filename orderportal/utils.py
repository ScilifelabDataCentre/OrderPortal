"Various utility functions."

from __future__ import print_function, absolute_import

import collections
import csv
import datetime
import hashlib
import io
import logging
import mimetypes
import optparse
import os
import sys
import time
import traceback
import unicodedata
import urllib
import urlparse
import uuid
from cStringIO import StringIO

import couchdb
import tornado.web
import xlsxwriter
import yaml

import orderportal
from . import constants
from . import designs
from . import settings


def get_command_line_parser(usage='usage: %prog [options]', description=None):
    "Get the base command line argument parser."
    # optparse is used (rather than argparse) due to Python 2.6
    parser = optparse.OptionParser(usage=usage, description=description)
    parser.add_option('-s', '--settings',
                      action='store', dest='settings',
                      default='{ROOT_DIR}/settings.yaml',
                      metavar="FILE", help="filepath of settings YAML file")
    parser.add_option('-p', '--pidfile',
                      action='store', dest='pidfile', default=None,
                      metavar="FILE", help="filepath of file to contain PID")
    parser.add_option('-f', '--force',
                      action="store_true", dest="force", default=False,
                      help='force action, rather than ask for confirmation')
    return parser

def load_settings(filepath):
    """Load and return the settings from the given file path.
    Raise IOError if settings file could not be read.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if a settings variable value is invalid.
    """
    # Read the settings file, updating the defaults
    with open(expand_filepath(filepath)) as infile:
        settings.update(yaml.safe_load(infile))
    settings['SETTINGS_FILEPATH'] = filepath
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
    logging.basicConfig(**kwargs)
    logging.info("OrderPortal version %s", orderportal.__version__)
    logging.info("ROOT_DIR: %s", settings['ROOT_DIR'])
    logging.info("SITE_DIR: %s", settings['SITE_DIR'])
    logging.info("settings: %s", settings['SETTINGS_FILEPATH'])
    logging.info("logging debug: %s", settings['LOGGING_DEBUG'])
    logging.info("tornado debug: %s", settings['TORNADO_DEBUG'])
    # Check settings
    for key in ['BASE_URL','DATABASE_SERVER','DATABASE_NAME','COOKIE_SECRET']:
        if key not in settings:
            raise KeyError("No settings['{0}'] item.".format(key))
        if not settings[key]:
            raise ValueError("settings['{0}'] has invalid value.".format(key))
    logging.info("CouchDB database name: %s", settings['DATABASE_NAME'])
    if len(settings.get('COOKIE_SECRET', '')) < 10:
        raise ValueError("settings['COOKIE_SECRET'] not set, or too short.")
    # Read account messages YAML file.
    logging.info("account messages: %s", settings['ACCOUNT_MESSAGES_FILEPATH'])
    with open(expand_filepath(settings['ACCOUNT_MESSAGES_FILEPATH'])) as infile:
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
    logging.info("order statuses: %s", settings['ORDER_STATUSES_FILEPATH'])
    with open(expand_filepath(settings['ORDER_STATUSES_FILEPATH'])) as infile:
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
    logging.info("order transitions: %s", 
                 settings['ORDER_TRANSITIONS_FILEPATH'])
    with open(expand_filepath(settings['ORDER_TRANSITIONS_FILEPATH'])) as infile:
        settings['ORDER_TRANSITIONS'] = yaml.safe_load(infile)
    # Read order messages YAML file.
    logging.info("order messages: %s", settings['ORDER_MESSAGES_FILEPATH'])
    with open(expand_filepath(settings['ORDER_MESSAGES_FILEPATH'])) as infile:
        settings['ORDER_MESSAGES'] = yaml.safe_load(infile)
    # Read universities YAML file.
    filepath = settings.get('UNIVERSITIES_FILEPATH')
    if not filepath:
        settings['UNIVERSITIES'] = dict()
    else:
        logging.info("universities lookup: %s", filepath)
        with open(expand_filepath(filepath)) as infile:
            unis = yaml.safe_load(infile)
        unis = unis.items()
        unis.sort(key=lambda i: (i[1].get('rank'), i[0]))
        settings['UNIVERSITIES'] = collections.OrderedDict(unis)
    # Read country codes YAML file
    filepath = settings.get('COUNTRY_CODES_FILEPATH')
    if not filepath:
        settings['COUNTRIES'] = []
    else:
        logging.info("country codes: %s", filepath)
        with open(expand_filepath(filepath)) as infile:
            settings['COUNTRIES'] = yaml.safe_load(infile)
        settings['COUNTRIES_LOOKUP'] = dict([(c['code'], c['name'])
                                             for c in settings['COUNTRIES']])
    # Read subject terms YAML file.
    filepath = settings.get('SUBJECT_TERMS_FILEPATH')
    if not filepath:
        settings['subjects'] = []
    else:
        logging.info("subject terms: %s", filepath)
        with open(expand_filepath(filepath)) as infile:
            settings['subjects'] = yaml.safe_load(infile)
    settings['subjects_lookup'] = dict([(s['code'], s['term'])
                                        for s in settings['subjects']])
    # Settings computable from others.
    settings['DATABASE_SERVER_VERSION'] = get_dbserver().version()
    if 'PORT' not in settings:
        parts = urlparse.urlparse(settings['BASE_URL'])
        items = parts.netloc.split(':')
        if len(items) == 2:
            settings['PORT'] = int(items[1])
        elif parts.scheme == 'http':
            settings['PORT'] =  80
        elif parts.scheme == 'https':
            settings['PORT'] =  443
        else:
            raise ValueError('Could not determine port from BASE_URL.')

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

def expand_filepath(filepath):
    "Expand variables (ROOT_DIR and SITE_DIR) in filepaths."
    filepath = filepath.replace('{SITE_DIR}', settings['SITE_DIR'])
    filepath = filepath.replace('{ROOT_DIR}', settings['ROOT_DIR'])
    if not os.path.isabs(filepath):
        filepath = os.path.join(settings['ROOT_DIR'], filepath)
    return filepath

def get_dbserver():
    server = couchdb.Server(settings['DATABASE_SERVER'])
    if settings.get('DATABASE_ACCOUNT') and settings.get('DATABASE_PASSWORD'):
        server.resource.credentials = (settings.get('DATABASE_ACCOUNT'),
                                       settings.get('DATABASE_PASSWORD'))
    return server

def get_db():
    "Return the handle for the CouchDB database."
    server = get_dbserver()
    try:
        return server[settings['DATABASE_NAME']]
    except couchdb.http.ResourceNotFound:
        raise KeyError("CouchDB database '%s' does not exist." % 
                       settings['DATABASE_NAME'])

def initialize(db=None):
    "Load the design documents, or update."
    if db is None:
        db = get_db()
    designs.load_design_documents(db)

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

def to_ascii(value):
    "Convert any non-ASCII character to its closest ASCII equivalent."
    if not isinstance(value, unicode):
        value = unicode(value, 'utf-8')
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')

def to_utf8(value):
    "Convert string value to UTF-8 representation."
    if isinstance(value, basestring):
        if not isinstance(value, unicode):
            value = unicode(value, 'utf-8')
        return value.encode('utf-8')
    else:
        return value

def to_unicode(value):
    "Convert string value to unicode assuming UTF-8."
    if isinstance(value, basestring) and not isinstance(value, unicode):
        return unicode(value, 'utf-8')
    else:
        return value

def to_bool(value):
    "Convert the value into a boolean, interpreting various string values."
    if isinstance(value, bool): return value
    if not value: return False
    lowvalue = value.lower()
    if lowvalue in constants.TRUE: return True
    if lowvalue in constants.FALSE: return False
    raise ValueError(u"invalid boolean: '{0}'".format(value))

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

def csv_safe_row(row):
    "Make all values in the row safe for CSV. See 'csv_safe'."
    row = list(row)
    for pos, value in enumerate(row):
        row[pos] = csv_safe(value)
    return row

def csv_safe(value):
    """Remove any beginning character '=-+@' from string value.
    Also convert to UTF-8. Change None to empty string.
    See http://georgemauer.net/2017/10/07/csv-injection.html
    """
    if isinstance(value, basestring):
        while len(value) and value[0] in '=-+@':
            value = value[1:]
        value = to_utf8(value)
    elif value is None:
        value = ''
    return value

def get_json(id, type):
    "Return the initialized JSON dictionary with id and type."
    result = collections.OrderedDict()
    result['id'] = id
    result['type'] = type
    result['site'] = settings['SITE_NAME']
    result['timestamp'] = timestamp()
    return result

def get_account_name(account=None, value=None):
    """Return person name of accountas 'lastname, firstname'.
    'account' is an account document.
    'value' is a row value from a view."""
    if account is not None:
        last_name = account.get('last_name')
        first_name = account.get('first_name')
    elif value is not None:
        first_name, last_name = value
    if last_name:
        if first_name:
            name = u"{0}, {1}".format(last_name, first_name)
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
    sha256 = hashlib.sha256(settings['PASSWORD_SALT'])
    sha256.update(to_utf8(password))
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
    db.save(entry)

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

    def __init__(self):
        self.csvbuffer = StringIO()
        self.writer = csv.writer(self.csvbuffer, quoting=csv.QUOTE_NONNUMERIC)

    def writerow(self, row):
        self.writer.writerow(csv_safe_row(row))

    def create_worksheet(self, name):
        pass

    def getvalue(self):
        return self.csvbuffer.getvalue()


class XlsxWriter(object):
    "Write rows serially to an XLSX file."

    def __init__(self):
        self.xlsxbuffer = io.BytesIO()
        self.workbook = xlsxwriter.Workbook(self.xlsxbuffer, {'in_memory':True})

    def create_worksheet(self, name):
        self.ws = self.workbook.add_worksheet(name)
        self.x = 0

    def writerow(self, row):
        for y, item in enumerate(row):
            self.ws.write(self.x, y, to_unicode(item))
        self.x += 1

    def getvalue(self):
        self.workbook.close()
        self.xlsxbuffer.seek(0)
        return self.xlsxbuffer.getvalue()
