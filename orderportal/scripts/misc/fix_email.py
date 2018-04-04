"Fix emails to be lower case everywhere."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts import fixer


class EmailFixer(fixer.BaseFixer):
    "Ensure all email addresses are lower case."

    def __call__(self, doc):
        changed = False
        try:
            owner = doc['owner']
            if not owner: raise KeyError
        except KeyError:
            pass
        else:
            if owner.lower() != owner:
                doc['owner'] = owner.lower()
                changed = True
        try:
            email = doc['email']
            if not email: raise KeyError
        except KeyError:
            pass
        else:
            if email.lower() != email:
                doc['email'] = email.lower()
                changed = True
        try:
            account = doc['account']
            if not account: raise KeyError
        except KeyError:
            pass
        else:
            if account.lower() != account:
                doc['account'] = account.lower()
                changed = True
        for pos, invited in enumerate(doc.get('invited', [])):
            if invited.lower() != invited:
                doc['invited'][pos] = invited.lower()
                changed = True
        for pos, member in enumerate(doc.get('member', [])):
            if member.lower() != member:
                doc['member'][pos] = member.lower()
                changed = True
        if changed:
            return doc


if __name__ == '__main__':
    EmailFixer().fix_documents()
