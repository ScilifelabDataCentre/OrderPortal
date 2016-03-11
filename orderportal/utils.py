"OrderPortal: Various utility functions."

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


def get_command_line_parser(usage='usage: %prog [options]', description=None):
    "Get the base command line argument parser."
    # optparse is used (rather than argparse) since
    # this code must be possible to run under Python 2.6
    parser = optparse.OptionParser(usage=usage, description=description)
    parser.add_option('-s', '--settings',
                      action='store', dest='settings', default=None,
                      metavar="FILE", help="filename of settings YAML file")
    parser.add_option('-v', '--verbose',
                      action="store_true", dest="verbose", default=False,
                      help='verbose output of actions taken')
    parser.add_option('-f', '--force',
                      action="store_true", dest="force", default=False,
                      help='force action, rather than ask for confirmation')
    return parser

def load_settings(filepath=None, verbose=False):
    """Load and return the settings from the file path given by
    1) the argument to this procedure,
    2) the environment variable ORDERPORTAL_SETTINGS,
    3) the first existing file in a predefined list of filepaths.
    Raise ValueError if no settings file was given.
    Raise IOError if settings file could not be read.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if the settings variable value is invalid.
    """
    if not filepath:
        filepath = os.environ.get('ORDERPORTAL_SETTINGS')
    if not filepath:
        basedir = constants.ROOT
        hostname = socket.gethostname().split('.')[0]
        for filepath in [os.path.join(basedir, "{0}.yaml".format(hostname)),
                         os.path.join(basedir, 'default.yaml')]:
            if os.path.exists(filepath) and os.path.isfile(filepath):
                break
        else:
            raise ValueError('no settings file specified')
    if verbose:
        print('settings from', filepath, file=sys.stderr)
    with open(filepath) as infile:
        settings.update(yaml.safe_load(infile))
    # Expand environment variables, ROOT and SITE_DIR, once and for all
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
    # Check settings
    for key in ['BASE_URL', 'DB_SERVER', 'COOKIE_SECRET', 'DATABASE']:
        if key not in settings:
            raise KeyError("no settings['{0}'] item".format(key))
        if not settings[key]:
            raise ValueError("settings['{0}'] has invalid value".format(key))
    if len(settings.get('COOKIE_SECRET', '')) < 10:
        raise ValueError("settings['COOKIE_SECRET'] not set, or too short")
    # Read order state definitions and transitions
    with open(settings['ORDER_STATUSES_FILEPATH']) as infile:
        settings['ORDER_STATUSES'] = yaml.safe_load(infile)
    settings['ORDER_STATUSES_LOOKUP'] = lookup = dict()
    initial = None
    for status in settings['ORDER_STATUSES']:
        if status['identifier'] in lookup:
            raise ValueError("order status '%s' multiple definitions" %
                             status['identifier'])
        lookup[status['identifier']] = status
        if status.get('initial'): initial = status
    if not initial:
        raise ValueError('no initial order status defined')
    settings['ORDER_STATUS_INITIAL'] = initial
    with open(settings['ORDER_TRANSITIONS_FILEPATH']) as infile:
        settings['ORDER_TRANSITIONS'] = yaml.safe_load(infile)
    # Account messages
    try:
        filepath = settings['ACCOUNT_MESSAGES_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['ACCOUNT_MESSAGES'] = dict()
    else:
        with open(filepath) as infile:
            settings['ACCOUNT_MESSAGES'] = yaml.safe_load(infile)
    # Order messages
    try:
        filepath = settings['ORDER_MESSAGES_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['ORDER_MESSAGES'] = dict()
    else:
        with open(filepath) as infile:
            settings['ORDER_MESSAGES'] = yaml.safe_load(infile)
    # Read order autopopulate mapping
    try:
        filepath = settings['ORDER_AUTOPOPULATE_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['ORDER_AUTOPOPULATE'] = dict()
    else:
        with open(filepath) as infile:
            settings['ORDER_AUTOPOPULATE'] = yaml.safe_load(infile)
    # Read universities lookup
    try:
        filepath = settings['UNIVERSITIES_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['UNIVERSITIES'] = dict()
    else:
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
        settings['countries'] = []
    else:
        with open(filepath) as infile:
            settings['countries'] = yaml.safe_load(infile)
        settings['countries_lookup'] = dict([(c['code'], c['name'])
                                             for c in settings['countries']])
    # Read subject terms
    try:
        filepath = settings['SUBJECT_TERMS_FILEPATH']
        if not filepath: raise KeyError
    except KeyError:
        settings['subjects'] = []
    else:
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
            raise ValueError('could not determine port from BASE_URL')

def expand_filepath(filepath):
    "Expand environment variables, the ROOT and SITE_DIR in filepaths."
    filepath = os.path.expandvars(filepath)
    old = None
    while filepath != old:
        old = filepath
        try:
            filepath = filepath.replace('{SITE_DIR}', settings['SITE_DIR'])
        except KeyError:
            pass
        filepath = filepath.replace('{ROOT}', constants.ROOT)
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
            raise KeyError("CouchDB database '%s' does not exist" % name)

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

def cmp_modified(i, j):
    "Compare the two documents by their 'modified' values."
    return cmp(i['modified'], j['modified'])

def absolute_path(filename):
    "Return the absolute path given the current directory."
    return os.path.join(constants.ROOT, filename)

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
