"Search orders page."

import urllib.parse

import couchdb2
import tornado.web

from orderportal import constants, settings
from orderportal import saver
from orderportal import utils
from orderportal.fields import Fields
from orderportal.requesthandler import RequestHandler
from functools import reduce


class Search(RequestHandler):
    """Search orders:
    - identifier (exact)
    - tags (exact)
    - title (words)
    """

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
                order = self.get_order(iuid)
            except tornado.web.HTTPError:
                pass
            else:
                orders[order["_id"]] = order
        # Search order identifier; exact match
        id_sets = []
        for part in parts:
            id_sets.append(
                set([r.id for r in self.db.view("order", "identifier", key=part)])
            )
        if id_sets:
            for id in reduce(lambda i, j: i.union(j), id_sets):
                orders[id] = self.get_order(id)
        # Seach order tags; exact match
        term = "".join([c in ",;'" and " " or c for c in orig]).strip().lower()
        parts = term.split()
        id_sets = []
        for part in parts:
            id_sets.append(set([r.id for r in self.db.view("order", "tag", key=part)]))
        if id_sets:
            for id in reduce(lambda i, j: i.union(j), id_sets):
                orders[id] = self.get_order(id)
        term = (
            "".join(
                [c in settings["ORDERS_SEARCH_DELIMS_LINT"] and " " or c for c in orig]
            )
            .strip()
            .lower()
        )
        parts = [
            part
            for part in term.split()
            if part and len(part) >= 2 and part not in settings["ORDERS_SEARCH_LINT"]
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

                orders[id] = self.get_order(id)
        # Convert to list; keep the orders that are readable by the user.
        if self.am_staff():
            orders = list(orders.values())
        else:
            orders = [
                i
                for i in list(orders.values())
                if self.am_owner(i) or self.am_colleague(i["owner"])
            ]
        self.render(
            "search.html",
            term=orig,
            orders=orders,
            account_names=self.get_accounts_name(),
        )
