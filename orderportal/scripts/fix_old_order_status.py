"Set the status of old orders from undefined to closed."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts import fixer


class StatusFixer(fixer.BaseFixer):
    "Set the status of old orders from undefined to closed."

    doctype = constants.ORDER

    DATE = '2015-01-01'

    def __call__(self, doc):
        if doc['status'] != 'undefined': return
        if doc['modified'] >= self.DATE: return
        doc['history']['closed'] = doc['modified'][:10] # Only date
        doc['status'] = 'closed'
        return doc


if __name__ == '__main__':
    StatusFixer().fix_documents()
