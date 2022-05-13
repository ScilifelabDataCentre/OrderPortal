"Search orders page."

import logging
import pprint
import urllib.parse

import couchdb2
import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .fields import Fields
from .requesthandler import RequestHandler
from functools import reduce


class Search(RequestHandler):
    """Search orders:
    - identifier (exact)
    - tags (exact)
    - title (words),
    - fields defined in settings
    """

    # Keep this in sync with JS script 'designs/order/views/keyword.js'
    LINT = set(["an", "to", "in", "on", "of", "and", "the", "was", "not"])

    @tornado.web.authenticated
    def get(self):
        orig = term = self.get_argument("term", "")
        orders = {}
        parts = term.split()
        parts = [p for p in parts if p]
        parts.extend([p.upper() for p in parts])
        # Try order IUIDs
        for iuid in parts:
            try:
                order = self.get_entity(iuid, doctype=constants.ORDER)
            except tornado.web.HTTPError as err:
                pass
            else:
                orders[order.get("identifier") or iuid] = order
        # Search order identifier; exact match
        id_sets = []
        for part in parts:
            id_sets.append(
                set([r.id for r in self.db.view("order", "identifier", key=part)])
            )
        if id_sets:
            for id in reduce(lambda i, j: i.union(j), id_sets):
                orders[id] = self.get_entity(id, doctype=constants.ORDER)
        # Seach order tags; exact match
        term = "".join([c in ",;'" and " " or c for c in orig]).strip().lower()
        parts = term.split()
        id_sets = []
        for part in parts:
            id_sets.append(set([r.id for r in self.db.view("order", "tag", key=part)]))
        if id_sets:
            for id in reduce(lambda i, j: i.union(j), id_sets):
                orders[id] = self.get_entity(id, doctype=constants.ORDER)
        # Keep this in sync with JS script 'designs/order/views/keyword.js'
        term = "".join([c in ":,;'" and " " or c for c in orig]).strip().lower()
        parts = [
            part
            for part in term.split()
            if part and len(part) >= 2 and part not in self.LINT
        ]
        # Search order titles for the parts extracted from search term.
        id_sets = []
        for part in parts:
            id_sets.append(
                set(
                    [
                        r.id
                        for r in self.db.view(
                            "order",
                            "keyword",
                            startkey=part,
                            endkey=part + constants.CEILING,
                        )
                    ]
                )
            )
        if id_sets:
            # All words must exist in title
            id_set = reduce(lambda i, j: i.intersection(j), id_sets)
            for id in reduce(lambda i, j: i.intersection(j), id_sets):
                orders[id] = self.get_entity(id, doctype=constants.ORDER)
        # Search settings-defined indexes for order fields.
        parts.append(orig)  # Entire original term.
        try:
            fields = list(self.db["_design/fields"]["views"].keys())
        except (couchdb2.NotFoundError, KeyError):
            fields = []
        for field in fields:
            id_sets = []
            id_sets.append(
                set(
                    [
                        r.id
                        for r in self.db.view(
                            "fields",
                            field,
                            startkey=orig,
                            endkey=orig + constants.CEILING,
                        )
                    ]
                )
            )
            if id_sets:
                for id in reduce(lambda i, j: i.union(j), id_sets):
                    orders[id] = self.get_entity(id, doctype=constants.ORDER)
        # Convert to list; keep orders readable by the user.
        if self.is_admin():
            orders = list(orders.values())
        else:
            orders = [
                i
                for i in list(orders.values())
                if self.is_owner(i) or self.is_colleague(i["owner"])
            ]
        # Go directly to order if exactly one found.
        if len(orders) == 1:
            self.see_other("entity", orders[0]["_id"])
        else:
            account_names = self.get_account_names()
            self.render(
                "search.html", term=orig, orders=orders, account_names=account_names
            )
