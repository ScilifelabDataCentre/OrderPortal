"OrderPortal: Fix order milestones."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts import fixer


class OrderMilestonesFixer(fixer.BaseFixer):
    "Create and populate milestones field in all orders."

    doctype = constants.ORDER

    def __call__(self, doc):
        milestones = doc.get('milestones') or {}
        try:
            del milestones['status']
        except KeyError:
            pass
        view = self.db.view('log/entity',
                            startkey=[doc['_id']],
                            endkey=[doc['_id'], constants.CEILING],
                            include_docs=True)
        for row in view:
            log = row.doc
            try:
                status = log['changed']['status']
                timestamp = log['modified']
            except KeyError:
                pass
            else:
                if self.verbose:
                    print('-', status, timestamp)
                milestones[status] = timestamp[:timestamp.index('T')]
            doc['milestones'] = milestones
        return doc


if __name__ == '__main__':
    OrderMilestonesFixer().fix_documents()
