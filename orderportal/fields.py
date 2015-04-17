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
        self._lookup = dict([(f['identifier'], f)
                             for f in self._flatten(self.fields)])

    def _flatten(self, fields, depth=0):
        result = []
        for field in fields:
            if field['type'] == constants.GROUP:
                result.extend(self._flatten(field['fields'], depth+1))
            else:
                field['depth'] = depth
                result.append(field)
        return result

    def __iter__(self):
        return iter(self._flattened)

    def __contains__(self, identifier):
        return identifier in self._lookup

    def __getitem__(self, identifier):
        return self._lookup[identifier]

    def add(self, identifier, rqh):
        "Add a field from HTML form data in the RequestHandler instance."
        assert identifier not in self, 'field identifier must be unique in form'
        field = dict(identifier=identifier,
                     label=rqh.get_argument('label', None),
                     type=rqh.get_argument('type'),
                     required=utils.to_bool(
                         rqh.get_argument('required', False)),
                     restrict_read=utils.to_bool(
                         rqh.get_argument('restrict_read', False)),
                     restrict_write=utils.to_bool(
                         rqh.get_argument('restrict_write', False)),
                     description=rqh.get_argument('description', None))
        group = rqh.get_argument('group', None)
        if group == '__none__': group = None
        if group:
            # XXX
            pass
        else:
            self.form['fields'].append(field)
        self._lookup[identifier] = field
        return field
