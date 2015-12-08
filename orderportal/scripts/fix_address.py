"Fix address and invoice_address for accounts."

from __future__ import print_function, absolute_import

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.scripts import fixer


class AddressFixer(fixer.BaseFixer):
    "Ensure all email addresses are lower case."

    doctype = constants.ACCOUNT

    def __call__(self, doc):
        address = doc.get('address', None)
        invoice_address = doc.get('invoice_address', None)
        if isinstance(address, dict) and isinstance(invoice_address, dict):
            return
        address = dict(address=address or None,
                       postal_code=None,
                       city=None,
                       country=None)
        invoice_address = dict(invoice_address=invoice_address or None,
                               postal_code=None,
                               city=None,
                               country=None)
        doc['address'] = address
        doc['invoice_address'] = invoice_address
        return doc


if __name__ == '__main__':
    AddressFixer().fix_documents()
