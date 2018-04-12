"OrderPortal: Load all CouchDB database design documents."

from __future__ import print_function, absolute_import

import os
import sys

import couchdb

from orderportal import constants
from orderportal import settings
from orderportal import utils


MAP_TEMPLATE = """function(doc) {{
  if (doc.orderportal_doctype !== 'order') return;
  var value = doc.fields.{fieldid};
  if (!value) return;
  var type = typeof(value);
  if (type === 'string') {{
    var words = value.replace(/[:,']/g, " ").toLowerCase().split(/\s+/);
  }} else if (type === 'number') {{
    var words = [value.toString()];
  }} else {{
    var words = value;
  }};
  if (words.length) {{
    words.forEach(function(word) {{
      if (word.length > 2 && !lint[word]) emit(word, null);
    }});
  }};
}};
var lint = {{'and': 1, 'the': 1, 'was': 1, 'not': 1}};"""

def load_designs(db, root_dir=None):
    "Load all CouchDB database design documents."
    # First the static ones from files.
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
    # Next the dynamic search fields defined in settings.
    try:
        doc = db['_design/fields']
    except couchdb.ResourceNotFound:
        doc = dict(_id='_design/fields')
    doc['views'] = dict()
    for field in settings['ORDERS_SEARCH_FIELDS']:
        if not constants.ID_RX.match(field):
            print("ERROR: search field %s invalid identifier; ignored." % field)
            continue
        doc['views'][field] = dict(map=MAP_TEMPLATE.format(fieldid=field))
    print('updating order search fields', file=sys.stderr)
    db.save(doc)

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
    for field in settings['ORDERS_SEARCH_FIELDS']:
        if constants.ID_RX.match(field):
            viewnames.append("fields/%s" % field)
    for viewname in viewnames:
        print('regenerating view', viewname)
        view = db.view(viewname)
        count = 0
        for row in view:
            count += 1
            if count > 4: break


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Reload all CouchDB design documents.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings)
    db = utils.get_db()
    load_designs(db)
    regenerate_views(db)
