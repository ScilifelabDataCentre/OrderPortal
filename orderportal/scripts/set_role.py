"Set the role for an account."

import sys

from orderportal import constants
from orderportal import utils
from orderportal.account import AccountSaver


def set_role(email, role):
    assert role in constants.ACCOUNT_ROLES
    db = utils.get_db()
    view = db.view('account/email', include_docs=True)
    rows = list(view[email])
    if len(rows) != 1:
        raise ValueError("no such account %s" % email)
    doc = rows[0].doc
    with AccountSaver(doc=doc, db=db) as saver:
        saver['role'] = role


if __name__ == '__main__':
    parser = utils.get_command_line_parser(
        description='Set the role for an account.')
    (options, args) = parser.parse_args()
    utils.load_settings()
    email = input('Email address (=account name) > ')
    if not email:
        sys.exit('no email address provided')
    role = input("role [%s] > " % '|'.join(constants.ACCOUNT_ROLES))
    if not role:
        sys.exit('no role provided')
    if role not in constants.ACCOUNT_ROLES:
        sys.exit("invalid role; must be one of %s" %
                 ', '.join(constants.ACCOUNT_ROLES))
    set_role(email, role)
    print('Set role for', email)
