"OrderPortal: Fields utility class."

from __future__ import print_function, absolute_import

import logging

import tornado.web

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
        self._lookup = dict([(f['identifier'], f) for f in self.flatten()])

    def flatten(self, fields=None, depth=0, parent=None):
        """Pre-order traversal to produce a list of all fields.
        Also updates the parents and depths of each field.
        """
        result = []
        if fields is None:
            fields = self.form['fields']
        for field in fields:
            if parent is None:
                field['parent'] = None
            else:
                field['parent'] = parent['identifier']
            field['depth'] = depth
            result.append(field)
            if field['type'] == constants.GROUP:
                result.extend(self.flatten(fields=field['fields'],
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

    def get_alt_parents(self, field, fields=None):
        """Get the group fields which the given field can be
        moved to while keeping a proper hierarchical tree.
        """
        result = []
        if fields is None:
            fields = self.form['fields']
            if field.get('parent') is not None:
                result.append(None)
        for f in fields:
            if f['type'] == constants.GROUP:
                if field['type'] == constants.GROUP:
                    if f['identifier'] == field['identifier']: continue
                if f['identifier'] != field.get('parent'):
                    result.append(f)
                result.extend(self.get_alt_parents(field, f['fields']))
        return result

    def __iter__(self):
        "Pre-order iteration over all fields."
        return iter(self.flatten())

    def __contains__(self, identifier):
        return identifier in self._lookup

    def __getitem__(self, identifier):
        return self._lookup[identifier]

    def add(self, identifier, rqh):
        "Add a form field from data in the RequestHandler instance."
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
                   erase_on_clone=utils.to_bool(
                       rqh.get_argument('erase_on_clone', False)),
                   description=rqh.get_argument('description', None))
        if type == constants.GROUP:
            new['fields'] = []
        # Set the possible values for menu or radiobuttons field.
        elif type == constants.SELECT:
            values = rqh.get_argument('select', '').split('\n')
            values = [v.strip() for v in values]
            values = [v for v in values if v]
            new['select'] = values
            new['display'] = rqh.get_argument('display', None) or 'menu'
        # Set the possible values for a multiselect field.
        elif type == constants.MULTISELECT:
            values = rqh.get_argument('multiselect', '').split('\n')
            values = [v.strip() for v in values]
            values = [v for v in values if v]
            new['multiselect'] = values
        # Set the group which the field is a member of.
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
        """Update the form field from data in the RequestHandler instance.
        This includes moving the field into a different group,
        or within a group."""
        assert identifier in self, 'field identifier must be defined in form'
        new = dict(label=rqh.get_argument('label', None),
                   required=utils.to_bool(
                       rqh.get_argument('required', False)),
                   restrict_read=utils.to_bool(
                       rqh.get_argument('restrict_read', False)),
                   restrict_write=utils.to_bool(
                       rqh.get_argument('restrict_write', False)),
                   erase_on_clone=utils.to_bool(
                       rqh.get_argument('erase_on_clone', False)),
                   description=rqh.get_argument('description', None))
        field = self._lookup[identifier]
        # Conditional field setup
        identifier = rqh.get_argument('visible_if_field', None)
        if identifier == '': identifier = None
        new['visible_if_field'] = identifier
        value = rqh.get_argument('visible_if_value', None)
        if value:
            value = '|'.join([s.strip() for s in value.split('|') if s.strip()])
        new['visible_if_value'] = value
        # Set the possible values for menu or radiobuttons field.
        if field['type'] == constants.SELECT:
            values = rqh.get_argument('select', '').split('\n')
            values = [v.strip() for v in values]
            values = [v for v in values if v]
            new['select'] = values
            new['display'] = rqh.get_argument('display', None) or 'menu'
        # Set the possible values for a multiselect field.
        elif field['type'] == constants.MULTISELECT:
            values = rqh.get_argument('multiselect', '').split('\n')
            values = [v.strip() for v in values]
            values = [v for v in values if v]
            new['multiselect'] = values
        # Represent the boolean by a checkbox or a menu.
        elif field['type'] == constants.BOOLEAN:
            new['checkbox'] = utils.to_bool(rqh.get_argument('checkbox', None))
        # Set the plugin processor a new field value.
        name = rqh.get_argument('processor', None)
        if name and name in settings['PROCESSORS']:
            new['processor'] = name
        else:
            new['processor'] = None
        # Record the changes.
        old = field.copy()
        field.update(new)
        diff = dict(identifier=field['identifier'])
        for key, value in field.iteritems():
            if key == 'fields': continue
            if old.get(key) != value:
                diff[key] = value
        # Set a new parent; change the field's group.
        new_parent = rqh.get_argument('parent', '')
        if new_parent:
            if new_parent == '[top level]':
                new_parent = -1 # Special value that is 'true'
            else:
                for alt_parent in self.get_alt_parents(field):
                    if alt_parent is None: continue
                    if alt_parent['identifier'] == new_parent:
                        new_parent = alt_parent
                        break
                else:
                    new_parent = None
        if new_parent:          # Including special value
            try:
                old_parent = self._lookup[field['parent']]
            except KeyError:
                self.form['fields'].remove(field)
            else:
                old_parent['fields'].remove(field)
            if new_parent == -1:
                self.form['fields'].append(field)
                diff['parent'] = None
            else:
                new_parent['fields'].append(field)
                diff['parent'] = new_parent['identifier']
            # This is required to refresh the parent and depth entries.
            self.flatten()
        # Repositioning a field is relevant only if parent stays the same.
        else:
            try:
                position = rqh.get_argument('position')
                if not position: raise ValueError
            except (tornado.web.MissingArgumentError, ValueError):
                pass
            else:
                siblings = self.get_siblings(field, self.form['fields'])
                siblings.remove(field)
                if position == '__first__':
                    siblings.insert(0, field)
                else:
                    for pos, sib in enumerate(siblings):
                        if sib['identifier'] == position:
                            siblings.insert(pos+1, field)
                            break
                    else:
                        siblings.append(field)
                        position = '__last__'
                diff['position'] = position
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
