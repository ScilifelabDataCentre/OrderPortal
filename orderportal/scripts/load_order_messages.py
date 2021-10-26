"Load the order messages document into the database."

import os.path
import sys

import couchdb
import yaml

from orderportal import constants
from orderportal import settings
from orderportal import utils


def load_order_messages(db):
    "Load the order messages document."
    for key in ['ORDER_MESSAGES_FILE', 'INITIAL_ORDER_MESSAGES_FILE']:
        filepath = settings.get(key)
        if filepath: break
    else:
        raise KeyError('no order messages file specified')
    filepath = os.path.join(settings["SITE_DIR"], filepath)
    print('Order messages from', filepath)
    with open(filepath) as infile:
        doc = yaml.safe_load(infile)
    doc['_id'] = 'order_messages'
    doc[constants.DOCTYPE] = constants.META
    print('saving order messages in database')
    db.save(doc)


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Load the order messages document.')
    (options, args) = parser.parse_args()
    utils.load_settings()
    db = utils.get_db()
    load_order_messages(db)
