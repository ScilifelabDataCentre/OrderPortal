"OrderPortal: Fields utility class."

from __future__ import unicode_literals, print_function, absolute_import

import logging

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils


class Fields(object):
    "Handle fields in an form or an order."

    def __init__(self, form):
        """Set reference to the form containing the fields,
        and set up lookup."""
        self.form = form
        self.fields = form['fields']
        self._flattened = self._flatten(self.fields)
        self._lookup = dict([(f['identifier'], f) for f in self._flattened])

    def _flatten(self, fields, depth=0):
        result = []
        for field in fields:
            if field['type'] == constants.GROUP:
                result.extend(self._flatten(field['fields'], depth+1))
            else:
                field['depth'] = depth
                result.append(field)

    def __iter__(self):
        return iter(self._flattened)
