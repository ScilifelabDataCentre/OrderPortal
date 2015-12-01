"Rename 'milestones' field in orders to 'history'."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts import fixer


class HistoryFixer(fixer.BaseFixer):
    "Ensure all email addresses are lower case."

    doctype = constants.ORDER

    def __call__(self, doc):
        try:
            doc['history'] = doc.pop('milestones')
        except KeyError:
            pass
        else:
            return doc


if __name__ == '__main__':
    HistoryFixer().fix_documents()
