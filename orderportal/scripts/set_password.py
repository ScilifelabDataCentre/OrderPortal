"Set the password for an account."



import sys
import getpass

from orderportal import constants
from orderportal import utils
from orderportal.account import AccountSaver


def set_password(email, password):
    db = utils.get_db()
    view = db.view('account/email', include_docs=True)
    rows = list(view[email])
    if len(rows) != 1:
        raise ValueError("no such account %s" % email)
    doc = rows[0].doc
    with AccountSaver(doc=doc, db=db) as saver:
        saver.set_password(password)


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Set the password for an account.')
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
    set_password(email, password)
    print('Set password for', email)
