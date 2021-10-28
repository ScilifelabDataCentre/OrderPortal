"Load the account messages document into the database."

import os.path
import sys

import yaml

from orderportal import constants
from orderportal import settings
from orderportal import utils


def load_account_messages(db):
    "Load the account messages document."
    for key in ['ACCOUNT_MESSAGES_FILE', 
                'INITIAL_ACCOUNT_MESSAGES_FILE']:
        filepath = settings.get(key)
        if filepath: break
    else:
        raise KeyError('no account messages file specified')
    filepath = os.path.join(settings["SITE_DIR"], filepath)
    print('Account messages from', filepath)
    with open(filepath) as infile:
        doc = yaml.safe_load(infile)
    doc['_id'] = 'account_messages'
    doc[constants.DOCTYPE] = constants.META
    print('saving account messages in database')
    db.save(doc)


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Load the account messages document.')
    (options, args) = parser.parse_args()
    utils.load_settings()
    db = utils.get_db()
    load_account_messages(db)
