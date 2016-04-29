"Enable all pending accounts."

from __future__ import print_function, absolute_import

import csv
import logging
import time

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils

PAUSE = 2.0

def enable_accounts(db, verbose=False):
    view = db.view('account/status',
                   include_docs=True,
                   key=constants.PENDING)
    for row in view:
        doc = row.doc
        doc['status'] = constants.ENABLED
        doc['password'] = None
        doc['code'] = utils.get_iuid()
        doc['modified'] = utils.timestamp()
        db.save(doc)
        utils.log(db, None, doc,
                  changed=dict(password=None, status=constants.ENABLED))
        if verbose:
            print(doc['email'])
        time.sleep(PAUSE)


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        "Enable all pending accounts.")
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    db = utils.get_db()
    enable_accounts(db, verbose=options.verbose)
