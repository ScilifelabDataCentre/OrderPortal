"OrderPortal: Load all CouchDB database design documents."

from __future__ import print_function, absolute_import

import os
import sys

import couchdb

from orderportal import constants
from orderportal import utils


def get_args():
    parser = utils.get_command_line_parser(description=
        'Reload all CouchDB design documents.')
    return parser.parse_args()

def load_designs(db, verbose=False, root=None):
    "Load all CouchDB database design documents."
    if root is None:
        root = os.path.join(constants.ROOT, 'designs')
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
            if verbose: print('loading', id, file=sys.stderr)
            db.save(dict(_id=id, views=views))
        else:
            if doc['views'] != views:
                doc['views'] = views
                if verbose: print('updating', id, file=sys.stderr)
                db.save(doc)
            elif verbose:
                print('no change', id, file=sys.stderr)


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    load_designs(utils.get_db(),
                 verbose=options.verbose)
