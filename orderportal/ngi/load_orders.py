""" OrderPortal: Load orders from JSON dump from the old Drupal site.
The order JSON files are in tools:/var/local/ngiportal
Assumes that all old user accounts exist in new system,
with email address as identifier.
NOTE: the order status is, strangely enough, not available in the dump.
"""

from __future__ import print_function, absolute_import

import datetime
import json

import couchdb

from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal.fields import Fields
from orderportal.order import OrderSaver
from orderportal.scripts.load_designs import regenerate_views


class OldOrderSaver(OrderSaver):

    def set_owner(self, record, authors):
        self.doc['owner'] = authors[record['author']['id']]

    def set_created(self, record):
        self.doc['created'] = utils.epoch_to_iso(record['created'])

    def set_modified(self, record):
        self.doc['modified'] = utils.epoch_to_iso(record['changed'])

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
        result[uid] = email.lower()
    if verbose:
        print(len(result), 'accounts')
    return result

def load_orders(db, form_iuid, authors, filename='orders.json', verbose=False):
    """Load the order and use the form given by IUID to transfer field values.
    The order identifier counter has to be updated."""
    meta = db['orders']
    counter = meta.get('counter')
    if counter is None:
        counter = meta['counter'] = 1
    else:
        print('WARNING: Some orders already loaded!')
        answer = raw_input('continue? [y] > ')
        if answer and answer.upper()[0] != 'Y': return
    try:
        form = db[form_iuid]
    except couchdb.ResourceNotFound:
        raise KeyError('given form iuid is invalid or obsolete')
    fields = Fields(form)
    # Get the set of already loaded old orders; integer part of 'identifier'
    already_loaded = set()
    view = db.view('order/form',
                   reduce=False,
                   include_docs=True,
                   startkey=[form_iuid],
                   endkey=[form_iuid, constants.CEILING])
    for row in view:
        try:
            already_loaded.add(int(row.doc['identifier'][3:]))
        except (KeyError, ValueError):
            pass
    with open(filename) as infile:
        data = json.load(infile)
    if verbose:
        print(len(data), 'records in dump file')
    total = 0
    for record in data:
        if int(record['nid']) in already_loaded: continue
        with OldOrderSaver(db=db) as saver:
            saver.doc['owner'] = authors[record['author']['id']]
            saver.set_created(record)
            saver.set_modified(record)
            saver['form'] = form_iuid
            saver['title'] = record['title']
            values = {}
            for field in fields:
                if field['type'] == constants.GROUP: continue
                value = record.get(field['identifier'])
                if isinstance(value, list):
                    value = '\n'.join(value)
                values[field['identifier']] = value
            saver['fields'] = values
            saver['identifier'] = \
                settings['ORDER_IDENTIFIER_FORMAT'].format(int(record['nid']))
            counter = max(counter, int(record['nid']))
            saver['history'] = {}
            saver.set_status('undefined')
            saver.check_fields_validity(fields)
        if verbose:
            print('loaded', saver.doc['identifier'], saver.doc['title'])
        total += 1
    if verbose:
        print(total, 'orders loaded, counter', counter)
    meta['counter'] = counter
    db.save(meta)


if __name__ == '__main__':
    parser = utils.get_command_line_parser(description=
        "Load orders from old Drupal site JSON dump 'orders.json'.")
    (options, args) = parser.parse_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    db = utils.get_db()
    load_orders(db,
                authors=load_users(verbose=options.verbose),
                form_iuid='abc8bd6232ec489d82680172e7054c2f',
                verbose=options.verbose)
    regenerate_views(db, verbose=options.verbose)
