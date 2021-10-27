" Get the previous version of the document and save it as new. "

import sys

from orderportal import utils


def revert(db, docid):
    revisions = list(db.revisions(docid))
    if len(revisions) < 2:
        sys.exit('no previous version to revert to')
    latest = revisions[0]
    previous = revisions[1]
    new = previous.copy()
    new['_rev'] = latest['_rev']
    db.save(new)


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
         'Get the previous version of the document and save it as new.')
    (options, args) = parser.parse_args()
    utils.load_settings()
    db = utils.get_db()
    for docid in args:
        revert(db, docid)
