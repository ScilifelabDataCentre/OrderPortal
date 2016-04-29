"Enable all pending accounts."

from __future__ import print_function, absolute_import

import csv
import logging
import time
import urllib

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.message import MessageSaver

PAUSE = 2.0

def enable_accounts(db, verbose=False):
    view = db.view('account/status',
                   include_docs=True,
                   key=constants.PENDING)
    for row in view:
        account = row.doc
        account['status'] = constants.ENABLED
        account['password'] = None
        account['code'] = utils.get_iuid()
        account['modified'] = utils.timestamp()
        db.save(account)
        utils.log(db, None, account,
                  changed=dict(password=None, status=constants.ENABLED))
        # Prepare message to send later
        try:
            template = settings['ACCOUNT_MESSAGES']['enabled']
        except KeyError:
            pass
        else:
            with MessageSaver(db=db) as saver:
                saver.set_params(
                    account=account['email'],
                    password_url=absolute_reverse_url('password'),
                    password_code_url=absolute_reverse_url(
                        'password',
                        email=account['email'],
                        code=account['code']),
                    code=account['code'])
                saver.set_template(template)
                saver['recipients'] = [account['email']]
        if verbose:
            print(account['email'])
        time.sleep(PAUSE)

def absolute_reverse_url(path, **kwargs):
    url = "https://ngisweden.scilifelab.se/{0}".format(path)
    if kwargs:
        url += '?' + urllib.urlencode(kwargs)
    return url


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        "Enable all pending accounts.")
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    db = utils.get_db()
    enable_accounts(db, verbose=options.verbose)
