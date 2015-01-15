" OrderPortal: Various utility functions and mixins. "

from __future__ import unicode_literals, print_function, absolute_import

import os
import socket
import logging
import collections
import urlparse
import urllib
import uuid
import json
import tarfile
from cStringIO import StringIO
import time
import datetime
import unicodedata
import mimetypes

import tornado.web
import couchdb
import requests
import yaml

import orderportal
from orderportal import settings
from . import constants


# Corrections and additions to standard mimetypes data.
EXTENSIONS = {
    constants.BIN_MIME:         '.bin',
    'application/docbook+xml':  '.xml',
    'application/xml':          '.xml',  # Else '.wsdl'
    constants.JPEG_MIME:        '.jpg',  # Else '.jpe'
    constants.TEXT_MIME:        '.txt',  # Else '.ksh'
    'text/x-rst':               '.rst',
    constants.MARKDOWN_MIME:    '.md',
    'application/x-gdbm':       '.gdb',
    'application/x-fasta':      '.fasta',
    'application/x-sqlite3':    '.db3',
}

def guess_extension(ct):
    "Guess the filename extension from content type, with corrections."
    try:
        return EXTENSIONS[ct]
    except KeyError:
        return mimetypes.guess_extension(ct)


def load_settings(filepath=None):
    """Load and return the settings from the file path given by
    1) the command line argument,
    2) the environment variable ORDERPORTAL_SETTINGS,
    3) the first existing file in a predefined list of filepaths.
    Raise IOError if no readable settings file was found.
    Raise KeyError if a settings variable is missing.
    Raise ValueError if the settings variable value is invalid.
    """
    if not filepath:
        filepath = os.environ.get('ORDERPORTAL_SETTINGS')
    if not filepath:
        homedir = os.path.expandvars('$HOME')
        basedir = constants.ROOT
        hostname = socket.gethostname().split('.')[0]
        for filepath in [os.path.join(homedir, "{}.yaml".format(hostname)),
                         os.path.join(homedir, 'default.yaml'),
                         os.path.join(basedir, "{}.yaml".format(hostname)),
                         os.path.join(basedir, 'default.yaml')]:
            if os.path.exists(filepath) and \
               os.path.isfile(filepath) and \
               os.access(filepath, os.R_OK):
                break
        else:
            raise IOError('no readable settings file found')
    with open(filepath) as infile:
        settings.update(yaml.safe_load(infile))
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
        kwargs['filename'] = settings['LOGGING_FILENAME']
    except KeyError:
        pass
    try:
        kwargs['filemode'] = settings['LOGGING_FILEMODE']
    except KeyError:
        pass
    logging.basicConfig(**kwargs)
    logging.info("settings from %s", filepath)
    # Check settings
    for key in ['BASE_URL', 'DB_SERVER', 'DB_DATABASE', 'COOKIE_SECRET']:
        if key not in settings:
            raise KeyError("no settings['{}'] item".format(key))
        if not settings[key]:
            raise ValueError("settings['{}'] has invalid value".format(key))
    if len(settings.get('COOKIE_SECRET', '')) < 10:
        raise ValueError("settings['COOKIE_SECRET'] not set, or too short")
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

def get_db(create=False):
    """Return the handle for the CouchDB database.
    If 'create' is True, then create the database if it does not exist.
    """
    server = couchdb.Server(settings['DB_SERVER'])
    try:
        return server[settings['DB_DATABASE']]
    except couchdb.http.ResourceNotFound:
        if create:
            return server.create(settings['DB_DATABASE'])
        else:
            raise KeyError("CouchDB database '%s' does not exist" %
                           settings['DB_DATABASE'])

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
    return instant[:-9] + "%06.3f" % float(instant[-9:]) + "Z"

def to_ascii(value):
    "Convert any non-ASCII character to its closest ASCII equivalent."
    if not isinstance(value, unicode):
        value = unicode(value, 'utf-8')
    return unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')

def to_bool(value):
    "Convert the value into a boolean, interpreting various string values."
    if not value: return False
    lowvalue = value.lower()
    if lowvalue in constants.TRUE: return True
    if lowvalue in constants.FALSE: return False
    raise ValueError("invalid boolean: '{}'".format(value))

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

def load_designs(db, root=os.path.join(constants.ROOT, 'designs')):
    "Load all CouchDB database design documents."
    for design in os.listdir(root):
        views = dict()
        path = os.path.join(root, design)
        if not os.path.isdir(path): continue
        path = os.path.join(root, design, 'views')
        for filename in os.listdir(path):
            name, ext = os.path.splitext(filename)
            if ext != '.js': continue
            with open(os.path.join(path, filename)) as codefile:
                code = codefile.read()
            if name.startswith('map_'):
                name = name[len('map_'):]
                key = 'map'
            elif name.startswith('reduce_'):
                name = name[len('reduce_'):]
                key = 'reduce'
            else:
                key = 'map'
            views.setdefault(name, dict())[key] = code
        id = "_design/%s" % design
        try:
            doc = db[id]
        except couchdb.http.ResourceNotFound:
            logging.debug("loading %s", id)
            db.save(dict(_id=id, views=views))
        else:
            if doc['views'] != views:
                doc['views'] = views
                logging.debug("updating %s", id)
                db.save(doc)
            else:
                logging.debug("no change %s", id)

def wipeout_database(db):
    """Wipe out the contents of the database.
    This is used rather than total delete of the database instance,
    since that may require additional privileges, depending on
    the setup.
    """
    for doc in db:
        del db[doc]

def dump(db, filepath):
    "Dump contents of the database to a tar file, optionally gzip compressed."
    count_items = 0
    count_files = 0
    if filepath.endswith('.gz'):
        mode = 'w:gz'
    else:
        mode = 'w'
    outfile = tarfile.open(filepath, mode=mode)
    for key in db:
        if not constants.IUID_RX.match(key): continue
        doc = db[key]
        del doc['_rev']
        info = tarfile.TarInfo(doc['_id'])
        data = json.dumps(doc)
        info.size = len(data)
        outfile.addfile(info, StringIO(data))
        count_items += 1
        for attname in doc.get('_attachments', dict()):
            info = tarfile.TarInfo("{}_att/{}".format(doc['_id'], attname))
            attfile = db.get_attachment(doc, attname)
            if attfile is None:
                data = ''
            else:
                data = attfile.read()
                attfile.close()
            info.size = len(data)
            outfile.addfile(info, StringIO(data))
            count_files += 1
    outfile.close()
    logging.info("dumped %s items and %s files to %s",
                 count_items, count_files, filepath)

def undump(db, filename):
    """Reverse of dump; load all items from a tar file.
    Items are just added to the database, ignoring existing items.
    """
    count_items = 0
    count_files = 0
    attachments = dict()
    infile = tarfile.open(filename, mode='r')
    for item in infile:
        itemfile = infile.extractfile(item)
        itemdata = itemfile.read()
        itemfile.close()
        if item.name in attachments:
            # This relies on an attachment being after its item in the tarfile.
            db.put_attachment(doc, itemdata, **attachments.pop(item.name))
            count_files += 1
        else:
            doc = json.loads(itemdata)
            # If the user document already exists, do not load again.
            if doc[constants.DOCTYPE] == constants.USER:
                rows = db.view('user/username', key=doc['username'])
                if len(list(rows)) != 0: continue
            atts = doc.pop('_attachments', dict())
            db.save(doc)
            count_items += 1
            for attname, attinfo in atts.items():
                key = "{}_att/{}".format(doc['_id'], attname)
                attachments[key] = dict(filename=attname,
                                        content_type=attinfo['content_type'])
    infile.close()
    return count_items, count_files
