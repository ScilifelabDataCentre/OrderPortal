"Create an admin account in the database."

from __future__ import print_function, absolute_import

import sys
import getpass

from orderportal import constants
from orderportal import utils
from orderportal.account import AccountSaver


def get_args():
    parser = utils.get_command_line_parser(description=
        'Create a new admin account account.')
    return parser.parse_args()

def create_admin(email, password, first_name, last_name, university,
                 verbose=False):
    with AccountSaver(db=utils.get_db()) as saver:
        saver.set_email(email)
        saver['first_name'] = first_name
        saver['last_name'] = last_name
        saver['address'] = dict()
        saver['invoice_address'] = dict()
        saver['university'] = university
        saver['department'] = None
        saver['owner'] = email
        saver.set_password(password)
        saver['role'] = constants.ADMIN
        saver['status'] = constants.ENABLED
    if verbose:
        print('Created admin account', email)


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    email = raw_input('Email address (=account name) > ')
    if not email:
        sys.exit('no email address provided')
    password = getpass.getpass('Password > ')
    if not password:
        sys.exit('no password provided')
    first_name = raw_input('First name > ') or 'first'
    last_name = raw_input('Last name > ') or 'last'
    university = raw_input('University > ') or 'university'
    create_admin(email, password, first_name, last_name, university,
                 verbose=options.verbose)
