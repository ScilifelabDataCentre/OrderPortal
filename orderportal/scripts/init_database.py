""" OrderPortal: Initialize the order database, directly towards CouchDB.
1) Wipes out the old database.
2) Loads the design documents.
3) Loads the initial texts file, as defined in the configuration file.
"""

from __future__ import print_function, absolute_import

import sys

import yaml

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts.dump import undump
from orderportal.scripts.load_designs import load_designs
from orderportal.scripts.load_texts import load_texts


def get_args():
    parser = utils.get_command_line_parser(description=
        'Initialize the database, deleting all old data,'
        ' optionally load from dump file.')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE', default=None,
                      metavar="FILE", help="filepath of dump file to load")
    return parser.parse_args()

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
        dumpfilepath = utils.expand_filepath(dumpfilepath)
        try:
            print('reading dump file...')
            undump(db, dumpfilepath)
        except IOError:
            print('Warning: could not load', dumpfilepath)
    else:
        print('no dump file loaded')
    load_texts(db, settings['INITIAL_TEXTS_FILEPATH'], overwrite=False)
    print('loaded initial texts file', settings['INITIAL_TEXTS_FILEPATH'])

def wipeout_database(db):
    """Wipe out the contents of the database.
    This is used rather than total delete of the database instance, since
    that may require additional privileges, depending on the setup.
    """
    for doc in db:
        del db[doc]


if __name__ == '__main__':
    (options, args) = get_args()
    if not options.force:
        response = raw_input('about to delete everything; really sure? [n] > ')
        if not utils.to_bool(response):
            sys.exit('aborted')
    utils.load_settings(filepath=options.settings)
    init_database(dumpfilepath=options.FILE)
