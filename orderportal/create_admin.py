"Create an admin account."



import sys
import getpass

from orderportal import constants
from orderportal import utils
from orderportal.account import AccountSaver


def create_admin(email, password, first_name, last_name, university):
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
    print('Created admin account', email)


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Create a new admin account.')
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings)
    email = input('Email address (=account name) > ')
    if not email:
        sys.exit('no email address provided')
    password = getpass.getpass('Password > ')
    if not password:
        sys.exit('no password provided')
    try:
        utils.check_password(password)
    except ValueError as msg:
        sys.exit(str(msg))
    again_password = getpass.getpass('Password again > ')
    if password != again_password:
        sys.exit('passwords do not match')
    first_name = input('First name > ') or 'first'
    last_name = input('Last name > ') or 'last'
    university = input('University > ') or 'university'
    create_admin(email, password, first_name, last_name, university)
