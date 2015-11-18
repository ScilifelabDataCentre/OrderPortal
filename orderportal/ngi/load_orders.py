""" OrderPortal: Load orders from JSON dump from the old Drupal site.
The order JSON files are in tools:/var/local/ngiportal
Assumes that all old user accounts exist in new system,
with email address as identifier.
NOTE: the order status is, strangely enough, not available in the dump.
"""

from __future__ import print_function, absolute_import

import datetime
import json

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.fields import Fields
from orderportal.order import OrderSaver


def epoch_to_iso(epoch):
    epoch = float(epoch)
    dt = datetime.datetime.fromtimestamp(epoch)
    return dt.isoformat() + 'Z'

class OldOrderSaver(OrderSaver):

    def set_owner(self, record, authors):
        self.doc['owner'] = authors[record['author']['id']]

    def set_created(self, record):
        self.doc['created'] = epoch_to_iso(record['created'])

    def set_modified(self, record):
        self.doc['modified'] = epoch_to_iso(record['changed'])

    def finalize(self):
        "Already set."
        pass


def load_users(filename='users.json', verbose=False):
    "Prepare the lookup from author id (as string) to email."
    with open(filename) as infile:
        data = json.load(infile)
    result = dict()
    for record in data:
        uid = record['uid']
        assert uid
        email = record['mail']
        assert email
        result[uid] = email
    if verbose:
        print(len(result), 'accounts')
    return result

def load_orders(form_iuid, authors, filename='orders.json', verbose=False):
    "Load the order and use the form given by IUID to transfer field values."
    db = utils.get_db()
    form = db[form_iuid]
    fields = Fields(form)
    # Get the set of already loaded old orders; nid values
    already_loaded = set()
    view = db.view('order/form',
                   reduce=False,
                   include_docs=True,
                   startkey=[form_iuid],
                   endkey=[form_iuid, constants.CEILING])
    for row in view:
        already_loaded.add(row.doc['fields']['nid'])
    with open(filename) as infile:
        data = json.load(infile)
    if verbose:
        print(len(data), 'records in dump file')
    count = 0
    for record in data:
        if record['nid'] in already_loaded: continue
        with OldOrderSaver(db=db) as saver:
            saver.doc['owner'] = authors[record['author']['id']]
            saver.set_created(record)
            saver.set_modified(record)
            saver['form'] = form_iuid
            saver['title'] = record['title']
            saver['fields'] = dict([(f['identifier'], record[f['identifier']])
                                    for f in fields if f['type']!='group'])
            saver['milestones'] = {}
            saver.set_status('undefined')
            saver.check_fields_validity(fields)
        if verbose:
            print('loaded order', saver.doc['fields']['nid'], saver.doc['title'])
        count += 1
    if verbose:
        print(count, 'orders loaded')


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        "Load orders from old Drupal site JSON dump 'orders.json'.")
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    load_orders(authors=load_users(verbose=options.verbose),
                form_iuid='667b54c434534d5fa30c231ca9a87ab6',
                verbose=options.verbose)
    
