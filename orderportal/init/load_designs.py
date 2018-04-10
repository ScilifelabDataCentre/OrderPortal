"OrderPortal: Load all CouchDB database design documents."

from __future__ import print_function, absolute_import

import os
import sys

import couchdb

from orderportal import settings
from orderportal import utils


def load_designs(db, root_dir=None):
    "Load all CouchDB database design documents."
    if root_dir is None:
        root_dir = os.path.join(settings['ROOT_DIR'], 'designs')
    for design in os.listdir(root_dir):
        views = dict()
        path = os.path.join(root_dir, design)
        if not os.path.isdir(path): continue
        path = os.path.join(root_dir, design, 'views')
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
            print('loading', id, file=sys.stderr)
            db.save(dict(_id=id, views=views))
        else:
            if doc['views'] != views:
                doc['views'] = views
                print('updating', id, file=sys.stderr)
                db.save(doc)
            else:
                print('no change', id, file=sys.stderr)

def regenerate_views(db, root_dir=None):
    "Trigger CouchDB to regenerate views by accessing them."
    if root_dir is None:
        root_dir = os.path.join(settings['ROOT_DIR'], 'designs')
    viewnames = []
    for design in os.listdir(root_dir):
        path = os.path.join(root_dir, design)
        if not os.path.isdir(path): continue
        path = os.path.join(root_dir, design, 'views')
        for filename in os.listdir(path):
            name, ext = os.path.splitext(filename)
            if ext != '.js': continue
            if name.startswith('map_'):
                name = name[len('map_'):]
            elif name.startswith('reduce_'):
                name = name[len('reduce_'):]
            viewname = design + '/' + name
            if viewname not in viewnames:
                viewnames.append(viewname)
    for viewname in viewnames:
        print('regenerating view', viewname)
        view = db.view(viewname)
        for row in view:
            break
        

if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Reload all CouchDB design documents.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings)
    db = utils.get_db()
    load_designs(db)
    regenerate_views(db)
