"Various utility functions."

from __future__ import print_function, absolute_import

import collections
import datetime
import hashlib
import logging
import mimetypes
import optparse
import os
import socket
import sys
import time
import traceback
import unicodedata
import urllib
import urlparse
import uuid

import couchdb
import tornado.web
import yaml

import orderportal
from . import constants
from . import settings
from .processors.baseprocessor import BaseProcessor


def get_command_line_parser(usage='usage: %prog [options]', description=None):
    "Get the base command line argument parser."
    # optparse is used (rather than argparse) since
    # this code must be possible to run under Python 2.6
    parser = optparse.OptionParser(usage=usage, description=description)
    parser.add_option('-s', '--settings',
                      action='store', dest='settings', default=None,
                      metavar="FILE", help="filename of settings YAML file")
    parser.add_option('-p', '--pidfile',
                      action='store', dest='pidfile', default=None,
                      metavar="FILE", help="filename of file containing PID")
    parser.add_option('-f', '--force',
                      action="store_true", dest="force", default=False,
                      help='force action, rather than ask for confirmation')
    return parser

def load_settings(filepath=None):
    """Load and return the settings from the file path given by
    1) the argument to this procedure,
    2) the environment variable ORDERPORTAL_SETTINGS,
    3) the first existing file in a predefined list of filepaths.
    Raise ValueError if no settings file was given.
    Raise IOError if settings file could not be read.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if a settings variable value is invalid.
    """
    if not filepath:
        filepath = os.environ.get('ORDERPORTAL_SETTINGS')
    if not filepath:
        hostname = socket.gethostname().split('.')[0]
        basedir = os.path.dirname(__file__)
        for filepath in [os.path.join(basedir, "{0}.yaml".format(hostname)),
                         os.path.join(basedir, 'default.yaml'),
                         os.path.join(basedir, 'settings.yaml')]:
            if os.path.exists(filepath) and os.path.isfile(filepath):
                break
        else:
            raise ValueError('No settings file specified.')
    # Read the settings file, updating the defaults
    with open(filepath) as infile:
        settings.update(yaml.safe_load(infile))
    settings['SETTINGS_FILEPATH'] = filepath
    # Set current working dir to be ROOT while reading the files
    orig_dir = os.getcwd()
    os.chdir(settings['ROOT'])
    # Expand environment variables (ROOT, SITE_DIR) once and for all
    for key, value in settings.items():
        if isinstance(value, (str, unicode)):
            settings[key] = expand_filepath(value)
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
        kwargs['filename'] = settings['LOGGING_FILEPATH']
    except KeyError:
        pass
    try:
        kwargs['filemode'] = settings['LOGGING_FILEMODE']
    except KeyError:
        pass
    logging.basicConfig(**kwargs)
    logging.info("OrderPortal version %s", orderportal.__version__)
    logging.info("settings from %s", settings['SETTINGS_FILEPATH'])
    logging.info("logging debug %s", settings['LOGGING_DEBUG'])
    logging.info("tornado debug %s", settings['TORNADO_DEBUG'])
    # Check settings
    for key in ['BASE_URL', 'DB_SERVER', 'COOKIE_SECRET', 'DATABASE']:
        if key not in settings:
            raise KeyError("No settings['{0}'] item.".format(key))
        if not settings[key]:
            raise ValueError("settings['{0}'] has invalid value.".format(key))
    if len(settings.get('COOKIE_SECRET', '')) < 10:
        raise ValueError("settings['COOKIE_SECRET'] not set, or too short.")
    # Load processor modules and the classes in them
    paths = settings.get('PROCESSORS', [])
    settings['PROCESSORS'] = {}
    for path in paths:
        try:
            fromlist = '.'.join(path.split('.')[:-1])
            module = __import__(path, fromlist=fromlist)
        except:
            logging.error("could not import processor module %s\n%s",
                          path,
                          traceback.format_exc(limit=20))
        else:
            for name in dir(module):
                entity = getattr(module, name)
                if isinstance(entity, type) and \
                   issubclass(entity, BaseProcessor) and \
                   entity != BaseProcessor:
                    name = entity.__module__ + '.' + entity.__name__
                    settings['PROCESSORS'][name] = entity
                    logging.debug("loaded processor %s", name)
    # Read order state definitions and transitions
    logging.debug("Order statuses from %s", settings['ORDER_STATUSES_FILEPATH'])
    with open(settings['ORDER_STATUSES_FILEPATH']) as infile:
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
    logging.debug("Order transitions from %s", 
                  settings['ORDER_TRANSITIONS_FILEPATH'])
    with open(settings['ORDER_TRANSITIONS_FILEPATH']) as infile:
        settings['ORDER_TRANSITIONS'] = yaml.safe_load(infile)
    # Account messages
    try:
        filepath = settings['ACCOUNT_MESSAGES_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['ACCOUNT_MESSAGES'] = dict()
    else:
        logging.debug("Account messages from %s", filepath)
        with open(filepath) as infile:
            settings['ACCOUNT_MESSAGES'] = yaml.safe_load(infile)
    # Order messages
    try:
        filepath = settings['ORDER_MESSAGES_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['ORDER_MESSAGES'] = dict()
    else:
        logging.debug("Order messages from %s", filepath)
        with open(filepath) as infile:
            settings['ORDER_MESSAGES'] = yaml.safe_load(infile)
    # Read universities lookup
    try:
        filepath = settings['UNIVERSITIES_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['UNIVERSITIES'] = dict()
    else:
        logging.debug("Universities lookup from %s", filepath)
        with open(filepath) as infile:
            unis = yaml.safe_load(infile)
        unis = unis.items()
        unis.sort(lambda i,j: cmp((i[1].get('rank'), i[0]),
                                  (j[1].get('rank'), j[0])))
        settings['UNIVERSITIES'] = collections.OrderedDict(unis)
    # Read country codes
    try:
        filepath = settings['COUNTRY_CODES_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['COUNTRIES'] = []
    else:
        logging.debug("Country codes from %s", filepath)
        with open(filepath) as infile:
            settings['COUNTRIES'] = yaml.safe_load(infile)
        settings['COUNTRIES_LOOKUP'] = dict([(c['code'], c['name'])
                                             for c in settings['COUNTRIES']])
    # Read subject terms
    try:
        filepath = settings['SUBJECT_TERMS_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['subjects'] = []
    else:
        logging.debug("Subject terms from %s", filepath)
        with open(filepath) as infile:
            settings['subjects'] = yaml.safe_load(infile)
    settings['subjects_lookup'] = dict([(s['code'], s['term'])
                                        for s in settings['subjects']])
    # Settings computable from others
    settings['DB_SERVER_VERSION'] = couchdb.Server(settings['DB_SERVER']).version()
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
    # Set back current working dir
    os.chdir(orig_dir)

def terminology(word):
    "Return the display term for the given word. Use itself by default."
    try:
        istitle = word.istitle()
        word = settings['TERMS'][word.lower()]
    except KeyError:
        pass
    else:
        if istitle: word = word.title()
    return word

def expand_filepath(filepath):
    "Expand environment variables (ROOT and SITE_DIR) in filepaths."
    filepath = os.path.expandvars(filepath)
    old = None
    while filepath != old:
        old = filepath
        try:
            filepath = filepath.replace('{SITE_DIR}', settings['SITE_DIR'])
        except KeyError:
            pass
        filepath = filepath.replace('{ROOT}', settings['ROOT'])
    return filepath

def get_dbserver():
    return couchdb.Server(settings['DB_SERVER'])

def get_db(create=False):
    """Return the handle for the CouchDB database.
    If 'create' is True, then create the database if it does not exist.
    """
    server = get_dbserver()
    name = settings['DATABASE']
    try:
        return server[name]
    except couchdb.http.ResourceNotFound:
        if create:
            return server.create(name)
        else:
            raise KeyError("CouchDB database '%s' does not exist." % name)

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
    "Convert value to UTF-8 representation."
    if isinstance(value, basestring):
        if not isinstance(value, unicode):
            value = unicode(value, 'utf-8')
        return value.encode('utf-8')
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

def absolute_path(filename):
    "Return the absolute path given the current directory."
    return os.path.join(settings['ROOT'], filename)

def check_password(password):
    """Check that the password is long and complex enough.
    Raise ValueError otherwise."""
    if len(password) < settings['MIN_PASSWORD_LENGTH']:
        raise ValueError("Password must be at least {0} characters long.".
                         format(settings['MIN_PASSWORD_LENGTH']))

def hashed_password(password):
    "Return the password in hashed form."
    sha256 = hashlib.sha256(settings['PASSWORD_SALT'])
    sha256.update(password)
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
    if content_type == 'text/plain':
        return '.txt'
    if content_type == 'image/jpeg':
        return '.jpg'
    return mimetypes.guess_extension(content_type)
