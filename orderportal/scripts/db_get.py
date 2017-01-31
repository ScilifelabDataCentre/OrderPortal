"Get document(s) from CouchDB and write to a JSON file."

from __future__ import print_function, absolute_import

import json
import sys

import couchdb

from orderportal import constants
from orderportal import settings
from orderportal import utils


def get_documents(db, docids=[], filepath=None):
    docs = []
    for docid in docids:
        try:
            doc = db[docid]
        except couchdb.ResourceNotFound:
            print('no such document', docid, file=sys.stderr)
        else:
            docs.append(doc)
    if docs:
        if filepath:
            outfile = open(filepath, 'w')
            print('writing to', filepath)
        else:
            outfile = sys.stdout
        json.dump(docs, outfile, indent=2)
    else:
        print('no such document(s)', file=sys.stderr)

def get_args():
    parser = utils.get_command_line_parser(description=
        'Get document(s) from CouchDB and write to JSON file.')
    parser.add_option("-w", "--write",
                      action='store', dest='FILE', default=None,
                      metavar="FILE", help="filepath of file to write")
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings)
    get_documents(utils.get_db(),
                  docids=args,
                  filepath=options.FILE)
