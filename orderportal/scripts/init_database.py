""" OrderPortal: Initialize the database, working directly towards CouchDB.
1) Wipeout the old database.
2) Load the design documents.
3) Load the dump file, if any.
"""

from __future__ import print_function

import logging
import sys
import optparse
import os
import getpass

from polycentric import settings
from polycentric import constants
from polycentric import utils


def init_database():
    db = utils.get_db(create=True)
    utils.wipeout_database(db)
    logging.INFO('wiped out database')
    utils.load_designs(db)
    logging.INFO('loaded designs')
    # default = 'dump.tar.gz'
    # if options.force:
    #     filename = default
    # else:
    #     filename = raw_input("load data from file? [{}] > ".format(default))
    #     if not filename:
    #         filename = default
    # if os.path.exists(filename):
    #     count_items, count_files = utils.undump(db, filename)
    #     print('undumped', count_items, 'items and',
    #           count_files, 'files from', filename)
    # else:
    #     print('no such file', filename, 'to undump')


if __name__ == '__main__':
    usage = "usage: %prog [options] [settingsfilename]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('-f', '--force',
                      action="store_true", dest="force", default=False,
                      help='force action, rather than ask for confirmation')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE', default='dump.tar.gz',
                      metavar="FILE", help="load dump file FILE")
    (options, args) = parser.parse_args()
    if not options.force:
        response = raw_input('about to delete everything; really sure? [n] > ')
        if not utils.to_bool(response):
            sys.exit('aborted')
    try:
        filepath = args[0]
    except IndexError:
        filepath = None
    utils.load_settings(filepath)
    print('FILE:', options.FILE)
