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
                      action='store', dest='FILE', default='dump.tar.gz',
                      metavar="FILE", help="filepath of dump file to load")
    return parser.parse_args()

def init_database(verbose=False, dumpfilepath=None):
    db = utils.get_db(create=True)
    if verbose:
        print('wiping out database...')
    wipeout_database(db)
    if verbose:
        print('wiped out database')
    load_designs(db, verbose=verbose)
    # No specific items set here; done on-the-fly in e.g. get_next_number
    db.save(dict(_id='orders',
                 orderportal_doctype=constants.META))
    if verbose:
        print('created meta documents')
    if verbose:
        print('loaded designs')
    load_texts(db, settings['INITIAL_TEXTS_FILEPATH'], verbose=verbose)
    if dumpfilepath:
        dumpfilepath = utils.expand_filepath(dumpfilepath)
        try:
            undump(db, dumpfilepath, verbose=verbose)
        except IOError:
            print('Warning: could not load', dumpfilepath)
    elif verbose:
        print('no dump file loaded')

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
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    init_database(dumpfilepath=options.FILE,
                  verbose=options.verbose)
