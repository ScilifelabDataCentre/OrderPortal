"Load the account messages document into the database."

from __future__ import print_function, absolute_import

import os
import sys

import couchdb
import yaml

from orderportal import constants
from orderportal import settings
from orderportal import utils


def load_account_messages(db):
    "Load the account messages document."
    for key in ['ACCOUNT_MESSAGES_FILEPATH', 
                'INITIAL_ACCOUNT_MESSAGES_FILEPATH']:
        filepath = settings.get(key)
        if filepath: break
    else:
        raise KeyError('no account messages file specified')
    print('Account messages from', filepath)
    with open(filepath) as infile:
        doc = yaml.safe_load(infile)
    doc['_id'] = 'account_messages'
    doc[constants.DOCTYPE] = constants.META
    print('saving account messages in database')
    db.save(doc)

def get_args():
    parser = utils.get_command_line_parser(description=
        'Load the account messages document.')
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings)
    db = utils.get_db()
    load_account_messages(db)
