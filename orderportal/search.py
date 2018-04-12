"Search page."

from __future__ import print_function, absolute_import

import logging
import pprint
import urlparse

import couchdb
import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .fields import Fields
from .requesthandler import RequestHandler


class Search(RequestHandler):
    "Search. Currently orders and users."

    # Keep this in sync with JS script 'designs/order/views/keyword.js'
    LINT = set(['an', 'to', 'in', 'on', 'of', 'and', 'the', 'was', 'not'])

    @tornado.web.authenticated
    def get(self):
        orig = self.get_argument('term', '')
        items = {}
        # Search order identifier; exact match
        term = orig.strip().upper()
        parts = term.split()
        view = self.db.view('order/identifier')
        id_sets = []
        for part in parts:
            id_sets.append(set([r.id for r in view[part]]))
        if id_sets:
            for id in reduce(lambda i,j: i.union(j), id_sets):
                items[id] = self.get_entity(id, doctype=constants.ORDER)
        # Seach order tags; exact match
        term = ''.join([c in ",;'" and ' ' or c for c in orig]).strip().lower()
        parts = term.split()
        view = self.db.view('order/tag')
        id_sets = []
        for part in parts:
            id_sets.append(set([r.id for r in view[part]]))
        if id_sets:
            for id in reduce(lambda i,j: i.union(j), id_sets):
                items[id] = self.get_entity(id, doctype=constants.ORDER)
        # Keep this in sync with JS script 'designs/order/views/keyword.js'
        term = ''.join([c in ":,;'" and ' ' or c for c in orig]).strip().lower()
        parts = [part for part in term.split()
                 if part and len(part) >= 2 and part not in self.LINT]
        # Search order titles
        view = self.db.view('order/keyword')
        id_sets = []
        for part in parts:
            id_sets.append(set([r.id for r in
                                view[part : part+constants.CEILING]]))
        if id_sets:
            # All words must exist in title
            id_set = reduce(lambda i,j: i.intersection(j), id_sets)
            for id in reduce(lambda i,j: i.intersection(j), id_sets):
                items[id] = self.get_entity(id, doctype=constants.ORDER)
        # Search dynamically defined indexes for order fields
        try:
            fields = self.db['_design/fields']['views'].keys()
        except (couchdb.ResourceNotFound, KeyError):
            fields = []
        for field in fields:
            view = self.db.view("fields/{0}".format(field))
            id_sets = []
            for part in parts:
                id_sets.append(set([r.id for r in
                                    view[part : part+constants.CEILING]]))
            if id_sets:
                for id in reduce(lambda i,j: i.intersection(j), id_sets):
                    items[id] = self.get_entity(id, doctype=constants.ORDER)
        # Only staff may search account (as yet).
        if self.is_staff():
            # Search account email
            view = self.db.view('account/email')
            id_sets = []
            for part in parts:
                part = part.lower()
                id_sets.append(set([r.id for r in
                                    view[part : part+constants.CEILING]]))
            # Only require one hit in email
            if id_sets:
                for id in reduce(lambda i,j: i.union(j), id_sets):
                    items[id] = self.get_entity(id, doctype=constants.ACCOUNT)
            # Search account last names
            view = self.db.view('account/last_name')
            id_sets = []
            for part in parts:
                id_sets.append(set([r.id for r in
                                    view[part : part+constants.CEILING]]))
            # Only require one hit in last name
            if id_sets:
                for id in reduce(lambda i,j: i.union(j), id_sets):
                    items[id] = self.get_entity(id, doctype=constants.ACCOUNT)
            # Search account first names
            view = self.db.view('account/first_name')
            id_sets = []
            for part in parts:
                id_sets.append(set([r.id for r in
                                    view[part : part+constants.CEILING]]))
            # Only require one hit in first name
            if id_sets:
                for id in reduce(lambda i,j: i.union(j), id_sets):
                    items[id] = self.get_entity(id, doctype=constants.ACCOUNT)
        # Remove all orders not readable by the user
            items = items.values()
        else:
            items = [i for i in items.values()
                     if self.is_owner(i) or self.is_colleague(i['owner'])]
        if len(items) == 1:
            self.see_other('entity', items[0]['_id'])
        else:
            account_names = self.get_account_names()
            self.render('search.html',
                        term=orig,
                        items=items,
                        account_names=account_names)
