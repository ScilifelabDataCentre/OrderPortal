""" OrderPortal: Initialize the order database, directly towards CouchDB.
1) Wipe out the old database.
2) Load the design documents.
3) Load the dump file, if given.
4) Load the initial texts from files, unless already loaded.
"""

from __future__ import print_function, absolute_import

import sys

import couchdb
import yaml

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import admin
from orderportal.scripts.dump import undump
from orderportal.init.load_designs import load_designs

INIT_TEXTS_FILEPATH = 'init_texts.yaml'

def init_database(dumpfilepath=None):
    db = utils.get_db(create=True)
    print('wiping out database...')
    wipeout_database(db)
    print('wiped out database')
    load_designs(db)
    print('loaded designs')
    # No specific items set here; done on-the-fly in e.g. get_next_number
    db.save(dict(_id='order',
                 orderportal_doctype=constants.META))
    print('created meta documents')
    if dumpfilepath:
        try:
            print('reading dump file...')
            undump(db, dumpfilepath)
        except IOError:
            print('Warning: could not load', dumpfilepath)
    else:
        print('no dump file loaded')
    # Load texts from the initial texts YAML file. Only if missing in db!
    print('loading any missing texts from', INIT_TEXTS_FILEPATH)
    try:
        with open(INIT_TEXTS_FILEPATH) as infile:
            texts = yaml.safe_load(infile)
    except IOError:
        print('Warning: could not load', INIT_TEXTS_FILEPATH)
        texts = dict()
    for name in constants.TEXTS:
        if len(list(db.view('text/name', key=name))) == 0:
            with admin.TextSaver(db=db) as saver:
                saver['name'] = name
                saver['text'] = texts.get(name, '')
            

def wipeout_database(db):
    """Wipe out the contents of the database.
    This doc-by-doc approach is used rather than total delete of
    the database instance, since that may require additional privileges.
    """
    for doc in db:
        del db[doc]


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Initialize the database, deleting all old data,'
        ' optionally load from dump file.')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE', default=None,
                      metavar="FILE", help="filepath of dump file to load")
    (options, args) = parser.parse_args()
    if not options.force:
        response = raw_input('about to delete everything; really sure? [n] > ')
        if not utils.to_bool(response):
            sys.exit('aborted')
    utils.load_settings(filepath=options.settings)
    init_database(dumpfilepath=options.FILE)
