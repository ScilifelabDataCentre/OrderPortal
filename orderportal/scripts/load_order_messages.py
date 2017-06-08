"Load the order messages document into the database."

from __future__ import print_function, absolute_import

import os
import sys

import couchdb
import yaml

from orderportal import constants
from orderportal import settings
from orderportal import utils


def load_order_messages(db):
    "Load the order messages document."
    filepath = settings['ORDER_MESSAGES_FILEPATH']
    if not filepath: raise KeyError('no filepath')
    print("Order messages from %s", filepath)
    with open(filepath) as infile:
        doc = yaml.safe_load(infile)
    doc['_id'] = 'order_messages'
    doc[constants.DOCTYPE] = constants.META
    print('saving order messages in database')
    db.save(doc)

def get_args():
    parser = utils.get_command_line_parser(description=
        'Load the order messages document.')
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings)
    db = utils.get_db()
    load_order_messages(db)
