"Put document(s) to CouchDB from a JSON file."

from __future__ import print_function, absolute_import

import json
import sys

import couchdb

from orderportal import constants
from orderportal import settings
from orderportal import utils


def put_documents(db, filepaths=[], verbose=False):
    docs = []
    try:
        if filepaths:
            for filepath in filepaths:
                if verbose:
                    print('reading', filepath)
                with open(filepath, 'r') as infile:
                    add_docs(docs, json.load(infile))
        else:
            filepath = '[stdin]'
            add_docs(docs, json.load(sys.stdin))
    except ValueError:
        sys.exit("item in file {0} not a dictionary".format(filepath))
    except KeyError:
        sys.exit("item in file {0} lacks '_id'".format(filepath))
    if verbose:
        print(len(docs), 'documents')
    for doc in docs:
        if doc['_id'] in db:
            print('document', doc['_id'], 'already exists; not overwritten',
                  file=sys.stderr)
        else:
            try:
                del doc['_rev']
            except KeyError:
                pass
            db.save(doc)
            if verbose:
                print('saved', doc['_id'])

def add_docs(docs, data):
    if isinstance(data, dict):
        if not '_id' in data: raise KeyError
        docs.append(data)
    elif isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                if not '_id' in item: raise KeyError
                docs.append(item)
            else:
                raise ValueError
    else:
        raise ValueError

def get_args():
    parser = utils.get_command_line_parser(description=
        'Put document(s) to CouchDB from JSON file.')
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings)
    put_documents(utils.get_db(),
                  filepaths=args,
                  verbose=options.verbose)
