""" OrderPortal: Initialize the order database, directly towards CouchDB.
1) Wipeout the old database.
2) Load the design documents.
"""

from __future__ import unicode_literals, print_function, absolute_import

import sys

from orderportal import utils


def get_args():
    parser = utils.get_command_line_parser(description=
        'Initialize the database, deleting all old data,'
        ' optionally load from order dump file.')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE', default='dump.tar.gz',
                      metavar="FILE", help="filepath of dump file to load")
    return parser.parse_args()

def init_database(verbose=False, dumpfilepath=None):
    db = utils.get_db(create=True)
    utils.wipeout_database(db)
    if verbose:
        print('wiped out order database', file=sys.stderr)
    utils.load_designs(db)
    if verbose:
        print('loaded designs', file=sys.stderr)
    if dumpfilepath:
        try:
            utils.undump(db, dumpfilepath, verbose=verbose)
        except IOError:
            print('Warning: could not load', dumpfilepath)
    elif verbose:
        print('no dump file loaded', file=sys.stderr)


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
