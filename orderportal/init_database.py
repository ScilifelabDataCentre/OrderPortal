""" OrderPortal: Initialize the order database, directly towards CouchDB.
The database must exist, and the account for accessing it must have been set up.
1) Load the design documents.
2) Load the dump file, if given.
3) Load the initial texts from file, unless already loaded.
"""

import os.path
import sys

import couchdb
import yaml

from orderportal import admin
from orderportal import constants
from orderportal import designs
from orderportal import settings
from orderportal import utils
from orderportal.dump import undump


def init_database(dumpfilepath=None):
    filepath = os.path.join(settings["SITE_DIR"], "init_texts.yaml")
    db = utils.get_db()
    try:
        db['order']
    except couchdb.ResourceNotFound:
        pass
    else:
        sys.exit('Error: database is not empty')
    utils.initialize(db)
    # No specific items set here; done on-the-fly in e.g. get_next_number
    db.save(dict(_id='order',
                 orderportal_doctype=constants.META))
    print('created meta documents')
    if dumpfilepath:
        try:
            print('reading dump file...')
            undump(db, dumpfilepath)
            designs.regenerate_views_indexes(db)
        except IOError:
            print('Warning: could not load', dumpfilepath)
    else:
        print('no dump file loaded')
    # Load texts from the initial texts YAML file. Only if missing in db!
    print('loading any missing texts from', filepath)
    try:
        with open(filepath) as infile:
            texts = yaml.safe_load(infile)
    except IOError:
        print('Warning: could not load', filepath)
        texts = dict()
    for name in constants.TEXTS:
        if len(list(db.view('text/name', key=name))) == 0:
            with admin.TextSaver(db=db) as saver:
                saver['name'] = name
                saver['text'] = texts.get(name, '')


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Initialize the database, optionally load from dump file.')
    parser.add_option("-L", "--load",
                      action='store', dest='FILE', default=None,
                      metavar="FILE", help="filepath of dump file to load")
    (options, args) = parser.parse_args()
    utils.load_settings()
    init_database(dumpfilepath=options.FILE)
