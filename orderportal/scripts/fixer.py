"OrderPortal: Fix the database."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils


class BaseFixer(object):
    "Base class for fixing a document."

    def __init__(self, db):
        self.db = db

    def __call__(self, doc):
        raise NotImplementedError


def fix_documents(db, fixer_class, dry_run=False, verbose=False):
    """Go through all documents in the database, executing the
    callable instance of fixer_class in each.
    If the document needs modification, it performs it and returns
    the modified document. Otherwise it returns None.
    This procedure will then save the modified document.
    """
    total = 0
    count = 0
    fixer = fixer_class(db)
    for docid in db:
        result = fixer(db[docid])
        total += 1
        if result:
            count += 1
            if verbose:
                if dry_run:
                    print('would have saved', docid)
                else:
                    db.save(result)
                    print('saved', docid)
        else:
            if verbose:
                print('no change', docid)
    if verbose:
        print(count, 'modified out of', total)


class EmailFixer(BaseFixer):
    "Ensure all email addresses are lower case."

    def __call__(self, doc):
        if 'orderportal_doctype' not in doc: return
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


def get_args():
    parser = utils.get_command_line_parser(description=
        'Fix documents in CouchDB.')
    parser.add_option('-d', '--dry-run',
                      action='store_true', dest='dry_run', default=False,
                      help='do not perform save; for debug')
    return parser.parse_args()

if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    db = utils.get_db()
    fix_documents(db,
                  EmailFixer,
                  dry_run=options.dry_run,
                  verbose=options.verbose)
