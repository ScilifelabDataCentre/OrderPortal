"Create an admin user in the database."

from __future__ import unicode_literals, print_function, absolute_import

import sys
import getpass

from orderportal import constants
from orderportal import utils
from orderportal.user import UserSaver


def get_args():
    parser = utils.get_command_line_parser(description=
        'Create a new admin user account.')
    return parser.parse_args()

def create_admin(email, password, verbose=False):
    with UserSaver(db=utils.get_db()) as saver:
        saver.set_email(email)
        saver['owner'] = email
        saver.set_password(password)
        saver['role'] = constants.ADMIN
        saver['status'] = constants.ACTIVE
    if verbose:
        print('Created admin user', email)


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    email = raw_input('Give email address (=user name) > ')
    if not email:
        sys.exit('no email address provided')
    password = getpass.getpass('Give password > ')
    if not password:
        sys.exit('no password provided')
    create_admin(email, password)
