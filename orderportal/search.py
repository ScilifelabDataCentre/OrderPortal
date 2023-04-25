"Search orders page."

import functools
import urllib.parse

import couchdb2
import tornado.web

from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.fields import Fields
from orderportal.requesthandler import RequestHandler


class Search(RequestHandler):
    """Search orders:
    - identifier (exact)
    - tags (exact)
    - title (terms)
    """

    @tornado.web.authenticated
    def get(self):
        orig_term = term = self.get_argument("term", "")
        orders = {}
        parts = term.split()
        parts = [p for p in parts if p]

        # Order IUIDs, lower case.
        for iuid in parts:
            try:
                order = self.get_order(iuid.lower())
            except tornado.web.HTTPError:
                pass
            else:
                orders[order["_id"]] = order

        # Search order identifier; exact match using upper case.
        id_sets = []
        for part in parts:
            id_sets.append(
                set(
                    [
                        row.id
                        for row in self.db.view("order", "identifier", key=part.upper())
                    ]
                )
            )
        if id_sets:
            for id in functools.reduce(lambda i, j: i.union(j), id_sets):
                orders[id] = self.get_order(id)

        # Seach order tags; exact match, using lower case.
        term = "".join([c in ",;'" and " " or c for c in orig_term]).strip().lower()
        parts = term.split()
        id_sets = []
        for part in parts:
            id_sets.append(
                set([row.id for row in self.db.view("order", "tag", key=part)])
            )
        if id_sets:
            for id in functools.reduce(lambda i, j: i.union(j), id_sets):
                orders[id] = self.get_order(id)

        # Search order titles for the parts extracted from search term.
        # Replace delimiters by blanks, make lower case.
        term = (
            "".join(
                [
                    c in constants.ORDERS_SEARCH_DELIMS_LINT and " " or c
                    for c in orig_term
                ]
            )
            .strip()
            .lower()
        )
        parts = [
            part
            for part in term.split()
            if part and len(part) >= 2 and part not in constants.ORDERS_SEARCH_LINT
        ]

        id_sets = []
        for part in parts:
            id_sets.append(
                set(
                    [
                        row.id
                        for row in self.db.view(
                            "order",
                            "term",
                            startkey=part,
                            endkey=part + constants.CEILING,
                        )
                    ]
                )
            )

        # All term parts (=words) must exist in the title.
        if id_sets:
            for id in functools.reduce(lambda i, j: i.intersection(j), id_sets):
                orders[id] = self.get_order(id)

        # Convert to list; keep the orders that the user is allowed to read.
        if self.am_staff():
            orders = list(orders.values())
        else:
            orders = [
                i
                for i in list(orders.values())
                if self.am_owner(i) or self.am_colleague(i["owner"])
            ]
        self.render("search.html", term=orig_term, orders=orders)
