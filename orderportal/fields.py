"OrderPortal: Fields utility class."

from __future__ import print_function, absolute_import

import logging

from . import constants
from . import settings
from . import utils


class Fields(object):
    "Handle fields in a form."

    def __init__(self, form):
        "Set reference to the form containing the fields, and set up lookup."
        self.form = form
        self.setup()

    def setup(self):
        self._lookup = dict([(f['identifier'], f)
                             for f in self.flatten(self.form['fields'])])

    def flatten(self, fields, depth=0, parent=None):
        "Pre-order traversal to produce a list of all fields."
        result = []
        for field in fields:
            if parent is None:
                field['parent'] = None
            else:
                field['parent'] = parent['identifier']
            field['depth'] = depth
            result.append(field)
            if field['type'] == constants.GROUP:
                result.extend(self.flatten(field['fields'],
                                           depth=depth+1,
                                           parent=field))
        return result

    def get_siblings(self, field, fields):
        "Find the list of fields which this field is part of."
        if field in fields:
            return fields
        for f in fields:
            if f['type'] == constants.GROUP:
                result = self.get_siblings(field, f['fields'])
                if result is not None: return result

    def __iter__(self):
        "Pre-order iteration over all fields."
        return iter(self.flatten(self.form['fields']))

    def __contains__(self, identifier):
        return identifier in self._lookup

    def __getitem__(self, identifier):
        return self._lookup[identifier]

    def add(self, identifier, rqh):
        "Add a field from HTML form data in the RequestHandler instance."
        assert identifier not in self, 'field identifier must be unique in form'
        type = rqh.get_argument('type')
        assert type in constants.TYPES, 'invalid field type'
        new = dict(identifier=identifier,
                   label=rqh.get_argument('label', None),
                   type=rqh.get_argument('type'),
                   required=utils.to_bool(
                       rqh.get_argument('required', False)),
                   restrict_read=utils.to_bool(
                       rqh.get_argument('restrict_read', False)),
                   restrict_write=utils.to_bool(
                       rqh.get_argument('restrict_write', False)),
                   description=rqh.get_argument('description', None))
        if type == constants.GROUP:
            new['fields'] = []
        elif type == constants.SELECT:
            values = rqh.get_argument('select', '').split('\n')
            values = [v.strip() for v in values]
            values = [v for v in values if v]
            new['select'] = values
            new['display'] = rqh.get_argument('display', None) or 'menu'
        group = rqh.get_argument('group', None)
        if group == '': group = None
        for field in self:
            if field['identifier'] == group:
                field['fields'].append(new)
                break
        else:
            self.form['fields'].append(new)
        self.setup()
        return new

    def clone(self, field):
        "Clone the field from another form."
        assert field['identifier'] not in self
        new = field.copy()
        self.form['fields'].append(new)
        self.setup()
        return new

    def update(self, identifier, rqh):
        "Update the field from HTML form data in the RequestHandler instance."
        assert identifier in self, 'field identifier must be defined in form'
        new = dict(label=rqh.get_argument('label', None),
                   required=utils.to_bool(
                       rqh.get_argument('required', False)),
                   restrict_read=utils.to_bool(
                       rqh.get_argument('restrict_read', False)),
                   restrict_write=utils.to_bool(
                       rqh.get_argument('restrict_write', False)),
                   description=rqh.get_argument('description', None))
        field = self._lookup[identifier]
        if field['type'] == constants.SELECT:
            values = rqh.get_argument('select', '').split('\n')
            values = [v.strip() for v in values]
            values = [v for v in values if v]
            new['select'] = values
            new['display'] = rqh.get_argument('display', None) or 'menu'
        identifier = rqh.get_argument('visible_if_field', None)
        if identifier == '': identifier = None
        new['visible_if_field'] = identifier
        value = rqh.get_argument('visible_if_value', None)
        if value:
            value = '|'.join([s.strip() for s in value.split('|') if s.strip()])
        new['visible_if_value'] = value
        old = field.copy()
        field.update(new)
        diff = dict(identifier=field['identifier'])
        for key, value in field.iteritems():
            if key == 'fields': continue
            if old.get(key) != value:
                diff[key] = value
        move = rqh.get_argument('move', '').lower()
        if move:
            siblings = self.get_siblings(field, self.form['fields'])
            if move == 'first':
                siblings.remove(field)
                siblings.insert(0, field)
            elif move == 'previous':
                pos = siblings.index(field)
                if pos > 0:
                    siblings.remove(field)
                    pos -= 1
                    siblings.insert(pos, field)
            elif move == 'next':
                pos = siblings.index(field)
                if pos < len(siblings) - 1:
                    siblings.remove(field)
                    pos += 1
                    siblings.insert(pos, field)
            elif move == 'last':
                siblings.remove(field)
                siblings.append(field)
            else:
                move = None
            if move:
                diff['move'] = move
        return diff

    def delete(self, identifier):
        "Delete the field and its children, if any."
        assert identifier in self, 'field identifier must be defined in form'
        self._delete(self.form['fields'], identifier)
        self.setup()

    def _delete(self, fields, identifier):
        "Search recursively for the field and delete it and its children."
        for i, field in enumerate(fields):
            if field['identifier'] == identifier:
                fields.pop(i)
                return
            if field['type'] == constants.GROUP:
                self._delete(field['fields'], identifier)
