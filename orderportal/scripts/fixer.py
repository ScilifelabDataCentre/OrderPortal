"OrderPortal: Base class for fixing documents in the database."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils


class BaseFixer(object):
    "Base class for fixing a document."

    doctype = None

    def __init__(self):
        (options, args) = self.get_args()
        utils.load_settings(filepath=options.settings)
        self.dry_run = options.dry_run
        self.db = utils.get_db()
        self.args = args
        self.prepare()

    def get_args(self):
        parser = utils.get_command_line_parser(description=
                                               'Fix documents in CouchDB.')
        parser.add_option('-d', '--dry-run',
                          action='store_true', dest='dry_run', default=False,
                          help='do not perform save; for debug')
        return parser.parse_args()
        
    def prepare(self):
        pass

    def fix_documents(self):
        """Go through all documents in the database and
        execute the callable for each.
        If the document needs modification, the callable performs it
        and returns the modified document. Otherwise it returns None.
        This procedure will then save the modified document.
        """
        total = 0
        count = 0
        for docid in self.db:
            doc = self.db[docid]
            if self.doctype:
                if 'orderportal_doctype' not in doc: continue
                if doc['orderportal_doctype'] != self.doctype: continue
            result = self(doc)
            total += 1
            if result:
                count += 1
                if self.dry_run:
                    print('would have saved', docid)
                else:
                    self.db.save(result)
                    print('saved', docid)
            else:
                print('no change', docid)
        print(count, 'modified out of', total)

    def __call__(self, doc):
        """Modify the document if needed.
        Return the doc, if changed. Else return None"""
        raise NotImplementedError
