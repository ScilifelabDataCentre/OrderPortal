"""OrderPortal: Count attached files for each order."""

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts import fixer


class CountAttached(fixer.BaseFixer):
    "Count attached documents for each order."

    doctype = constants.ORDER

    def __call__(self, doc):
        count = len(doc.get('_attachments', []))
        if count:
            print(doc.get('title') or doc['_id'], count)


if __name__ == '__main__':
    CountAttached().fix_documents()
