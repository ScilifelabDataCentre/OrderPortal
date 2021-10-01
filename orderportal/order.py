"Orders are the whole point of this app. The user fills in info for facility."

import io
import logging
import os.path
import re
import traceback
import urllib.parse
import zipfile
from collections import OrderedDict as OD

import couchdb
import simplejson as json       # XXX Python 3 kludge
import tornado.web

from . import constants
from . import saver
from . import settings
from . import utils
from .fields import Fields
from .message import MessageSaver
from .requesthandler import RequestHandler, ApiV1Mixin


class OrderSaver(saver.Saver):
    doctype = constants.ORDER

    def initialize(self):
        "Set the initial values for the new order. Create history field."
        super(OrderSaver, self).initialize()
        self['history'] = {}

    def setup(self):
        """Additional setup.
        1) Initialize flag for changed status.
        2) Prepare for attaching files.
        """
        self.changed_status = None
        self.files = []
        self.filenames = set(self.doc.get('_attachments', []))
        try:
            self.fields = Fields(self.rqh.get_form(self.doc['form']))
        except KeyError:
            pass

    def create(self, form, title=None):
        "Create the order from the given form."
        self.fields = Fields(form)
        self['form'] = form['_id']
        self['title'] = title
        self['fields'] = dict([(f['identifier'], None) for f in self.fields])
        self.set_status(settings['ORDER_STATUS_INITIAL']['identifier'])
        # Set the order identifier if its format defined.
        # Allow also for disabled, since admin may clone such orders.
        if form['status'] in (constants.ENABLED, constants.DISABLED):
            try:
                fmt = settings['ORDER_IDENTIFIER_FORMAT']
                if not fmt: raise KeyError
            except KeyError:    # No identifier; sequential counter not used
                pass
            else:               # Identifier; sequential counter is used
                counter = self.rqh.get_next_counter(constants.ORDER)
                self['identifier'] = fmt.format(counter)

    def autopopulate(self):
        "Autopopulate fields if defined."
        # First try to set the value of a field from the corresponding
        # value defined for the account's university.
        autopop = settings.get('ORDER_AUTOPOPULATE')
        if not autopop: return
        try:
            uni_fields = settings['UNIVERSITIES'] \
                         [self.rqh.current_user['university']] \
                         ['fields']
        except KeyError:
            uni_fields = {}
        for target in autopop:
            if target not in self.fields: continue
            value = uni_fields.get(target)
            # Terrible kludge! If it looks like a country field,
            # then attempt to translate from country code to name.
            if 'country' in target:
                try:
                    value = settings['COUNTRIES_LOOKUP'][value]
                except KeyError:
                    pass
            self['fields'][target] = value
        # Next try to set the value of a field from the corresponding
        # value defined for the account. For use with e.g. invoice address.
        # Do this only if not done already from university data.
        for target, source in list(autopop.items()):
            if target not in self.fields: continue
            value = self['fields'].get(target)
            if isinstance(value, str):
                if value: continue
            elif value is not None: # Value 0 (zero) must be possible to set
                continue
            try:
                key1, key2 = source.split('.')
            except ValueError:
                value = self.rqh.current_user.get(source)
            else:
                value = self.rqh.current_user.get(key1, {}).get(key2)
            # Terrible kludge! If it looks like a country field,
            # then attempt to translate from country code to name.
            if 'country' in target:
                try:
                    value = settings['COUNTRIES_LOOKUP'][value]
                except KeyError:
                    pass
            self['fields'][target] = value

    def add_file(self, infile):
        "Add the given file to the files. Return the unique filename."
        filename = os.path.basename(infile.filename)
        if filename in self.filenames:
            count = 1
            while True:
                filename, ext = os.path.splitext(infile.filename)
                filename = "{0}_{1}{2}".format(filename, count, ext)
                if filename not in self.filenames: break
                count += 1
        self.filenames.add(filename)
        self.files.append(dict(filename=filename,
                               body=infile.body,
                               content_type=infile.content_type))
        return filename

    def set_status(self, new):
        "Set the new status of the order."
        if self.get('status') == new: return
        if new not in settings['ORDER_STATUSES_LOOKUP']:
            raise ValueError("invalid status '%s'" % new)
        if 'status' in self.doc:
            targets = self.rqh.get_targets(self.doc)
            if new not in [t['identifier'] for t in targets]:
                raise ValueError('You may not change status of {0} to {1}.'
                                 .format(utils.terminology('order'), new))
        self['status'] = new
        self.doc['history'][new] = utils.today()
        self.changed_status = new

    def set_tags(self, tags):
        """Set the tags of the order from JSON data (list of strings).
        Ordinary user may not add or remove prefixed tags.
        """
        if not isinstance(tags, list):
            raise ValueError('tags data is not a list')
        for s in tags:
            if not isinstance(s, str):
                raise ValueError('tags list item is not a string')
        # Allow staff to add prefixed tags.
        if self.rqh.is_staff():
            for pos, tag in enumerate(tags):
                parts = tag.split(':', 1)
                for part in parts:
                    if not constants.ID_RX.match(part):
                        tags[pos] = None
            tags = [t for t in tags if t]
        # User may use only proper identifier-like tags, no prefixes.
        else:
            tags = [t for t in tags if constants.ID_RX.match(t)]
            # Add back the previously defined prefixed tags.
            tags.extend([t for t in self.get('tags', [])
                         if ':' in t])
        self['tags'] = sorted(set(tags))

    def set_external(self, links):
        """Set the external links of the order from JSON data, 
        a list of dictionaries with items 'href' and 'title',
        or from lines where the first word of each line is the URL,
        and remaining items are used as title.
        """
        if not isinstance(links, list): return
        external = []
        for link in links:
            if isinstance(link, dict):
                try:
                    href = link['href']
                except KeyError:
                    pass
                else:
                    if isinstance(href, str):
                        title = link.get('title') or href
                        external.append({'href': href,
                                         'title': title})
            elif isinstance(link, str):
                link = link.strip()
                if link:
                    parts = link.split()
                    if len(parts) > 1:
                        link = {'href': parts[0], 'title': ' '.join(parts[1:])}
                    else:
                        link = {'href': parts[0], 'title': parts[0]}
                    external.append(link)
        self['links'] = {'external': external}

    def update_fields(self, data=None):
        "Update all fields from JSON data if given, else HTML form input."
        assert self.rqh is not None
        self.removed_files = []       # Due to field update
        # Loop over fields defined in the form document and get values.
        # Do not change values for a field if that argument is missing,
        # except for checkbox: there a missing value means False,
        # and except for multiselect: there a missing value means empty list.
        for field in self.fields:
            # Field not displayed or not writeable must not be changed.
            if not self.rqh.is_staff() and \
                (field['restrict_read'] or field['restrict_write']): continue
            if field['type'] == constants.GROUP: continue
            identifier = field['identifier']

            if field['type'] == constants.FILE:
                # Files are uploaded by the normal form multi-part
                # encoding approach, not by JSON data.
                try:
                    infile = self.rqh.request.files[identifier][0]
                except (KeyError, IndexError):
                    continue
                else:
                    value = self.add_file(infile)
                    self.removed_files.append(self.doc['fields'].get(identifier))
            elif field['type'] == constants.MULTISELECT:
                if data:
                    try:
                        value = data[identifier]
                    except KeyError:
                        continue
                else:
                    # Missing argument implies empty list.
                    # This is a special case for HTML form input.
                    value = self.rqh.get_arguments(identifier)

            elif field['type'] == constants.TABLE:
                coldefs = [utils.parse_field_table_column(c) 
                           for c in field['table']]
                if data:        # JSON data: contains complete table.
                    try:
                        table = data[identifier]
                    except KeyError:
                        continue
                else:           # HTML form data; collect table from fields.
                    try:
                        name = "_table_%s_count" % identifier
                        n_rows = int(self.rqh.get_argument(name, 0))
                    except (ValueError, TypeError):
                        n_rows = 0
                    table = []
                    for i in range(n_rows):
                        row = []
                        for j, coldef in enumerate(coldefs):
                            name = "_table_%s_%i_%i" % (identifier, i, j)
                            row.append(self.rqh.get_argument(name, None))
                        table.append(row)
                # Check validity of table content.
                value = []
                try:
                    for row in table:
                        # Check correct number of items in the row.
                        if len(row) != len(coldefs): continue
                        for j, coldef in enumerate(coldefs):
                            coltype = coldef.get('type')
                            if coltype == constants.SELECT:
                                if row[j] not in coldef['options']:
                                    row[j] = None
                                elif row[j] == '[no value]':
                                    row[j] = None
                            elif coltype == constants.INT:
                                try:
                                    row[j] = int(row[j])
                                except (ValueError, TypeError):
                                    row[j] = None
                            elif not row[j]:
                                row[j] = None
                        # Use row only if first value is not None.
                        if row[0] is not None:
                            value.append(row)
                # Something is badly wrong; just skip it.
                except (ValueError, TypeError, AttributeError, IndexError):
                    value = []

            # All other types of input fields.
            else:
                if data:          # JSON data.
                    try:
                        value = data[identifier]
                    except KeyError:
                        continue
                else:               # HTML form input.
                    try:
                        value = self.rqh.get_argument(identifier)
                        if value == '': value = None
                    except tornado.web.MissingArgumentError:
                        # Missing argument means no change,
                        # which is not the same as value None.
                        # Except for boolean checkbox!
                        if field['type'] == constants.BOOLEAN and \
                           field.get('checkbox'):
                            value = False
                        else:
                            continue
                # Remove all carriage-returns from string.
                if value is not None:
                    value = value.replace('\r', '')
            # Record any change to the value.
            if value != self.doc['fields'].get(identifier):
                changed = self.changed.setdefault('fields', dict())
                changed[identifier] = value
                self.doc['fields'][identifier] = value
        self.check_fields_validity()

    def check_fields_validity(self):
        "Check validity of current field values."
        self.doc['invalid'] = dict()
        for field in self.fields:
            if field['depth'] == 0:
                self.check_validity(field)

    def check_validity(self, field):
        """Check validity of field value.
        Also convert the value for some field types.
        Skip field if not visible, else check recursively in postorder.
        Return True if valid, False otherwise.
        """
        try:
            select_id = field.get('visible_if_field')
            if select_id:
                select_value = self.doc['fields'].get(select_id)
                if select_value is not None:
                    select_value = str(select_value).lower()
                if_value = field.get('visible_if_value')
                if if_value:
                    if_value = if_value.lower()
                if select_value != if_value:
                    return True

            if field['type'] == constants.GROUP:
                failure = False
                for subfield in field['fields']:
                    if not self.check_validity(subfield):
                        failure = True
                if failure:
                    raise ValueError('subfield(s) invalid')
            else:
                value = self.doc['fields'][field['identifier']]
                if value is None:
                    if field['required']:
                        raise ValueError('missing value')
                elif field['type'] == constants.STRING:
                    pass
                elif field['type'] == constants.EMAIL:
                    if not constants.EMAIL_RX.match(value):
                        raise ValueError('not a valid email address')
                elif field['type'] == constants.INT:
                    try:
                        self.doc['fields'][field['identifier']] = int(value)
                    except (TypeError, ValueError):
                        raise ValueError('not an integer value')
                elif field['type'] == constants.FLOAT:
                    try:
                        self.doc['fields'][field['identifier']] = float(value)
                    except (TypeError, ValueError):
                        raise ValueError('not a float value')
                elif field['type'] == constants.BOOLEAN:
                    try:
                        if value is None: raise ValueError
                        self.doc['fields'][field['identifier']] = utils.to_bool(value)
                    except (TypeError, ValueError):
                        raise ValueError('not a boolean value')
                elif field['type'] == constants.URL:
                    parsed = urllib.parse.urlparse(value)
                    if not (parsed.scheme and parsed.netloc):
                        raise ValueError('incomplete URL')
                elif field['type'] == constants.SELECT:
                    if value not in field['select']:
                        raise ValueError('value not among alternatives')
                elif field['type'] == constants.MULTISELECT:
                    if not isinstance(value, list):
                        raise ValueError('value is not a list')
                    if field['required'] and len(value) == 1 and value[0] == '':
                        raise ValueError('missing value')
                    for v in value:
                        if v and v not in field['multiselect']:
                            raise ValueError('value not among alternatives')
                elif field['type'] == constants.TEXT:
                    if not isinstance(value, str):
                        raise ValueError('value is not a text string')
                elif field['type'] == constants.DATE:
                    if not constants.DATE_RX.match(value):
                        raise ValueError('value is not a valid date')
                elif field['type'] == constants.TABLE:
                    if not isinstance(value, list):
                        raise ValueError('table value is not a list')
                    if field['required'] and len(value) == 0:
                        raise ValueError('missing data')
                    for r in value:
                        if not isinstance(r, list):
                            raise ValueError('table value is not a list of lists')
                elif field['type'] == constants.FILE:
                    pass
        except ValueError as msg:
            self.doc['invalid'][field['identifier']] = str(msg)
            return False
        except Exception as msg:
            self.doc['invalid'][field['identifier']] = "System error: %s" % msg
            return False
        else:
            return True

    def set_history(self, history):
        "Set the history the JSON data (dict of status->date)"
        if not isinstance(history, dict):
            raise ValueError('history data is not a dictionary')
        for status, date in list(history.items()):
            if not (date is None or (isinstance(date, str) and
                                     constants.DATE_RX.match(date))):
                raise ValueError('invalid date in history data')
            if not status in settings['ORDER_STATUSES_LOOKUP']:
                raise ValueError('invalid status in history data')
            self['history'][status] = date

    def post_process(self):
        self.modify_attachments()
        if self.changed_status:
            self.send_message()

    def modify_attachments(self):
        "Save or delete the file as an attachment to the document."
        try:                    # Delete the named file.
            self.db.delete_attachment(self.doc, self.delete_filename)
        except AttributeError:
            # Else add any new attached files.
            try:
                # First remove files due to field update
                for filename in self.removed_files:
                    if filename:
                        self.db.delete_attachment(self.doc, filename)
            except AttributeError:
                pass
            for file in self.files:
                self.db.put_attachment(self.doc,
                                       file['body'],
                                       filename=file['filename'],
                                       content_type=file['content_type'])

    def send_message(self):
        "Send a message after status change."
        try:
            template = settings['ORDER_MESSAGES'][self.doc['status']]
        except (couchdb.ResourceNotFound, KeyError):
            return
        recipients = set()
        owner = self.get_account(self.doc['owner'])
        # Owner account may have been deleted.
        if owner:
            email = owner['email'].strip().lower()
            if 'owner' in template['recipients']:
                recipients = set([owner['email']])
            if 'group' in template['recipients']:
                for row in self.db.view('group/member',
                                        include_docs=True,
                                        key=email):
                    for member in row.doc['members']:
                        account = self.get_account(member)
                        if account and account['status'] == constants.ENABLED:
                            recipients.add(account['email'])
        if constants.ADMIN in template['recipients']:
            view = self.db.view('account/role', include_docs=True)
            admins = [r.doc for r in view[constants.ADMIN]]
            for admin in admins:
                if admin['status'] == constants.ENABLED:
                    recipients.add(admin['email'])
        with MessageSaver(rqh=self) as saver:
            saver.create(template,
                         owner=self.doc['owner'],
                         title=self.doc['title'],
                         identifier=self.doc.get('identifier') or self.doc['_id'],
                         url=self.get_order_url(self.doc),
                         tags=', '.join(self.doc.get('tags', [])))
            saver.send(list(recipients))

    def get_order_url(self, order):
        """Member rqh is not available when used from a stand-alone script,
        so self.rqh.order_reverse_url cannot be used.
        The URL has to be synthesized explicitly here. """
        try:
            identifier = order['identifier']
        except KeyError:
            identifier = order['_id']
        path = "/order/{0}".format(identifier)
        if settings['BASE_URL_PATH_PREFIX']:
            path = settings['BASE_URL_PATH_PREFIX'] + path
        return settings['BASE_URL'] + path

    def get_account(self, email):
        "Get the account document for the given email."
        view = self.db.view('account/email', include_docs=True)
        rows = list(view[email])
        if len(rows) == 1:
            return rows[0].doc
        else:
            return None


class OrderMixin(object):
    "Mixin for various useful methods."

    def get_order(self, iuid):
        """Get the order for the identifier or IUID.
        Raise ValueError if no such order."""
        try:
            regexp = settings['ORDER_IDENTIFIER_REGEXP']
            if not regexp: raise KeyError
            match = re.match(regexp, iuid)
            if not match: raise KeyError
        except KeyError:
            try:
                order = self.get_entity(iuid, doctype=constants.ORDER)
            except tornado.web.HTTPError:
                raise ValueError('Sorry, no such order')
        else:
            try:
                order = self.get_entity_view('order/identifier', match.group())
            except tornado.web.HTTPError:
                raise ValueError('Sorry, no such order')
        return order

    def is_readable(self, order):
        "Is the order readable by the current user?"
        if self.is_owner(order): return True
        if self.is_staff(): return True
        if self.is_colleague(order['owner']): return True
        return False

    def check_readable(self, order):
        "Check if current user may read the order."
        if self.is_readable(order): return
        raise ValueError('You may not read the order.')

    def is_editable(self, order):
        "Is the order editable by the current user?"
        if self.is_admin(): return True
        if not self.global_modes['allow_order_editing']: return False
        status = self.get_order_status(order)
        edit = status.get('edit', [])
        if self.is_staff() and constants.STAFF in edit: return True
        if self.is_owner(order) and constants.USER in edit: return True
        return False

    def check_editable(self, order):
        "Check if current user may edit the order."
        if self.is_editable(order): return
        if not self.global_modes['allow_order_editing']:
            msg = '{0} editing is currently disabled.'
        else:
            msg = 'You may not edit the {0}.'
        raise ValueError(msg.format(utils.terminology('order')))

    def is_attachable(self, order):
        "May the current user may attach a file to the order?"
        if self.is_admin(): return True
        status = self.get_order_status(order)
        attach = status.get('attach', [])
        if self.is_staff() and constants.STAFF in attach: return True
        if self.is_owner(order) and constants.USER in attach: return True
        return False

    def check_attachable(self, order):
        "Check if current user may attach a file to the order."
        if self.is_attachable(order): return
        raise tornado.web.HTTPError(
            403,
            reason="You may not attach a file to the {0}."
            .format(utils.terminology('order')))

    def check_creation_enabled(self):
        "If order creation is disabled, raise ValueError."
        if not self.global_modes['allow_order_creation'] \
           and self.current_user['role'] != constants.ADMIN:
            raise ValueError("{0} creation is currently disabled."
                             .format(utils.terminology('Order')))

    def get_form(self, iuid, check=False):
        "Get the form given by its IUID. Optionally check that it is enabled."
        form = self.get_entity(iuid, doctype=constants.FORM)
        if check:
            if form['status'] not in (constants.ENABLED, constants.TESTING):
                raise ValueError('form is not available for creation')
        return form

    def get_fields(self, order, depth=0, fields=None):
        """Return a list of dictionaries, each of which
        for a field that is visible to the current user."""
        if fields is None:
            form = self.get_form(order['form'])
            fields = form['fields']
        result = []
        for field in fields:
            # Check if field may not be viewed by the current user.
            if field['restrict_read'] and not self.is_staff(): continue
            # Is there a visibility condition? If so, check it.
            fid = field.get('visible_if_field')
            if fid:
                value = str(order['fields'].get(fid)).lower()
                opt = str(field.get('visible_if_value')).lower().split('|')
                if value not in opt: continue
            item = OD(identifier=field['identifier'])
            item['label'] = field.get('label') or \
                            field['identifier'].capitalize().replace('_', ' ')
            item['depth'] = depth
            item['type'] = field['type']
            item['value'] = order['fields'].get(field['identifier'])
            item['restrict_read'] = field['restrict_read']
            item['restrict_write'] = field['restrict_write']
            item['invalid'] = order['invalid'].get(field['identifier'])
            item['description'] = field.get('description')
            item._field = field
            result.append(item)
            if field['type'] == constants.GROUP:
                result.extend(self.get_fields(order, depth+1, field['fields']))
        return result

    def get_order_status(self, order):
        "Get the order status lookup item."
        return settings['ORDER_STATUSES_LOOKUP'][order['status']]

    def get_targets(self, order):
        "Get the allowed status transition targets as status lookup items."
        for transition in settings['ORDER_TRANSITIONS']:
            if (transition['source'] == order['status']) and \
               not (transition.get('require') == 'valid' and order['invalid']):
                permission = transition['permission']
                if (self.is_admin() and constants.ADMIN in permission) or \
                   (self.is_staff() and constants.STAFF in permission) or \
                   (self.is_owner(order) and constants.USER in permission):
                    targets = transition['targets']
                    break
        else:
            return []
        result = [settings['ORDER_STATUSES_LOOKUP'][t] for t in targets]
        if not self.global_modes['allow_order_submission']:
            result = [r for r in result
                       if r['identifier'] != constants.SUBMITTED]
        return result

    def is_submittable(self, order, check_valid=True):
        "Is the order submittable? Special hard-wired status."
        targets = self.get_targets(order)
        return constants.SUBMITTED in [t['identifier'] for t in targets]

    def is_clonable(self, order):
        """Can the given order be cloned? Its form must be enabled.
        Special case: Admin can clone an order even if its form is disabled.
        """
        form = self.get_form(order['form'])
        if self.is_admin():
            return form['status'] in (constants.ENABLED,
                                      constants.TESTING,
                                      constants.DISABLED)
        if not self.global_modes['allow_order_creation']: return False
        return form['status'] in (constants.ENABLED, constants.TESTING)


class OrderApiV1Mixin(ApiV1Mixin):
    "Mixin for order JSON data structure."

    def get_order_json(self, order, names={}, forms={}, full=False):
        """Return a dictionary for JSON output for the order.
        Account names or forms title lookup are computed if not given.
        If 'full' then add all fields, else only for orders list.
        NOTE: Only the values of the fields are included, not
        the full definition of the fields. To obtain that,
        one must fetch the JSON for the corresponding form."""
        URL = self.absolute_reverse_url
        if full:
            data = utils.get_json(self.order_reverse_url(order, api=True),
                                  'order')
        else:
            data = OD()
        data['identifier'] = order.get('identifier')
        data['title'] = order.get('title') or '[no title]'
        data['iuid'] = order['_id']
        if full:
            form = self.get_form(order['form'])
            data['form'] = OD(
                [('title', form['title']),
                 ('version', form.get('version')),
                 ('iuid', form['_id']),
                 ('links', dict(api=dict(href=URL('form_api', form['_id'])),
                                display=dict(href=URL('form', form['_id']))))])
        else:
            if not forms:
                forms = self.get_forms_titles(all=True)
            data['form'] = OD(
                [('iuid', order['form']),
                 ('title', forms[order['form']]),
                 ('links', dict(api=dict(href=URL('form', order['form']))))])
        if not names:
            names = self.get_account_names([order['owner']])
        data['owner'] = dict(
            email=order['owner'],
            name=names.get(order['owner']),
            links=dict(api=dict(href=URL('account_api', order['owner'])),
                       display=dict(href=URL('account', order['owner']))))
        data['status'] = order['status']
        data['report'] = OD()
        if order.get('report'):
            data['report']['content_type'] = order['_attachments'][constants.SYSTEM_REPORT]['content_type']
            data['report']['timestamp'] = order['report']['timestamp']
            data['report']['link'] = dict(href=URL('order_report_api',
                                                   order['_id']))
        data['history'] = OD()
        for s in settings['ORDER_STATUSES']:
            key = s['identifier']
            data['history'][key] = order['history'].get(key)
        data['tags'] = order.get('tags', [])
        data['modified'] = order['modified']
        data['created'] = order['created']
        data['links'] = dict(
            api=dict(href=self.order_reverse_url(order, api=True)),
            display=dict(href=self.order_reverse_url(order)))
        if full:
            for status in self.get_targets(order):
                data['links'][status['identifier']] = dict(
                    href=URL('order_transition_api',
                             order['_id'],
                             status['identifier']),
                    name='transition')
            data['links']['external'] = order.get('links', {}).get('external', [])
            data['fields'] = OD()
            # A bit roundabout, but the fields will come out in correct order
            for field in self.get_fields(order):
                data['fields'][field['identifier']] = field['value']
            data['invalid'] = order.get('invalid', {})
            data['files'] = OD()
            for filename in sorted(order.get('_attachments', [])):
                if filename.startswith(constants.SYSTEM): continue
                stub = order['_attachments'][filename]
                data['files'][filename] = dict(
                    size=stub['length'],
                    content_type=stub['content_type'],
                    href=self.absolute_reverse_url('order_file',
                                                   order['_id'],
                                                   filename))
        # XXX Terrible kludge! Converts binary keys and values to string.
        # XXX A Python3 issue, possible due to bad old CouchDB interface.
        return json.loads(json.dumps(data))

def convert_to_strings(doc):
    items = list(doc.items())
    for key, value in items:
        if isinstance(key, bytes):
            print(key)
            doc[key.decode()] = doc.pop(key)
        if isinstance(value, dict):
            convert_to_strings(value)

class Order(OrderMixin, RequestHandler):
    "Order page."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        try:
            self.check_readable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        form = self.get_form(order['form'])
        files = []
        for filename in order.get('_attachments', []):
            if filename.startswith(constants.SYSTEM): continue
            stub = order['_attachments'][filename]
            files.append(dict(filename=filename,
                              size=stub['length'],
                              content_type=stub['content_type']))
            files.sort(key=lambda i: i['filename'].lower())
        self.render('order.html',
                    title="{0} '{1}'".format(utils.terminology('Order'),
                                              order['title']),
                    order=order,
                    account_names=self.get_account_names([order['owner']]),
                    status=self.get_order_status(order),
                    form=form,
                    fields=form['fields'],
                    attached_files=files,
                    is_editable=self.is_admin() or self.is_editable(order),
                    is_clonable=self.is_clonable(order),
                    is_attachable=self.is_attachable(order),
                    targets=self.get_targets(order))

    @tornado.web.authenticated
    def post(self, iuid):
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(
            405, reason='Internal problem; POST only allowed for DELETE.')

    @tornado.web.authenticated
    def delete(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        self.delete_logs(order['_id'])
        self.db.delete(order)
        self.see_other('orders')


class OrderApiV1(OrderApiV1Mixin, OrderMixin, RequestHandler):
    "Order API; JSON output; JSON input for edit."

    def get(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            raise tornado.web.HTTPError(404, reason=str(msg))
        try:
            self.check_readable(order)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        self.write(self.get_order_json(order, full=True))

    def post(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            raise tornado.web.HTTPError(404, reason=str(msg))
        try:
            self.check_editable(order)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        data = self.get_json_body()
        try:
            with OrderSaver(doc=order, rqh=self) as saver:
                try:
                    saver['title'] = data['title']
                except KeyError:
                    pass
                try:
                    tags = data['tags']
                except KeyError:
                    pass
                else:
                    if isinstance(tags, str):
                        tags = [tags]
                    saver.set_tags(tags)
                try:
                    saver.set_external(data['links']['external'])
                except KeyError:
                    pass
                try:
                    saver.update_fields(data=data['fields'])
                except KeyError:
                    pass
                if self.is_admin():
                    try:
                        saver.set_history(data['history'])
                    except KeyError:
                        pass
        except ValueError as msg:
            raise tornado.web.HTTPError(400, reason=str(msg))
        else:
            self.write(self.get_order_json(order, full=True))


class OrderCsv(OrderMixin, RequestHandler):
    "Return a CSV file containing the order data. Contains field definitions."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            raise tornado.web.HTTPError(404, reason=str(msg))
        try:
            self.check_readable(order)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        writer = self.write_order(order)
        self.write(writer.getvalue())
        self.write_finish(order)

    def write_order(self, order, writer=None):
        if writer is None:
            writer = self.get_writer()
        URL = self.absolute_reverse_url
        form = self.get_form(order['form'])
        writer.writerow((settings['SITE_NAME'], utils.today()))
        try:
            writer.writerow(('Identifier', order['identifier']))
        except KeyError:
            pass
        writer.writerow(('Title', order['title'] or '[no title]'))
        writer.writerow(('URL', self.order_reverse_url(order)))
        writer.writerow(('IUID', order['_id']))
        writer.writerow(('Form', 'Title', form['title']))
        writer.writerow(('', 'Version', form.get('version') or '-'))
        writer.writerow(('', 'IUID', form['_id']))
        account = self.get_account(order['owner'])
        writer.writerow(('Owner', 'Name', utils.get_account_name(account)))
        writer.writerow(('', 'URL', URL('account', account['email'])))
        writer.writerow(('', 'Email', order['owner']))
        writer.writerow(('', 'University', account.get('university') or '-'))
        writer.writerow(('', 'Department', account.get('department') or '-'))
        writer.writerow(('', 'PI', account.get('pi') and 'Yes' or 'No'))
        if settings.get('ACCOUNT_FUNDER_INFO') and \
           settings.get('ACCOUNT_FUNDER_INFO_GENDER'):
            writer.writerow(('', 'Gender',
                             account.get('gender', '-').capitalize()))
        writer.writerow(('Status', order['status']))
        for i, s in enumerate(settings['ORDER_STATUSES']):
            key = s['identifier']
            writer.writerow((i == 0 and 'History' or '',
                             key,
                             order['history'].get(key, '-')))
        for t in order.get('tags', []):
            writer.writerow(('Tag', t))
        writer.writerow(('Modified', order['modified']))
        writer.writerow(('Created', order['created']))
        writer.new_worksheet('Fields')
        writer.writerow(('Field', 'Label', 'Depth', 'Type', 'Value',
                         'Restrict read', 'Restrict write', 'Invalid'))
        for field in self.get_fields(order):
            values = list(field.values())[:-1] # Skip help text
            # Special case for table field; spans more than one row
            if field['type'] == constants.TABLE:
                table = values[4] # Column for 'Value'
                values[4] = len(table) # Number of rows in table
                values += [h.split(';')[0] for h in field._field['table']]
                writer.writerow(values)
                prefix = [''] * 8
                for row in table:
                    writer.writerow(prefix + row)
            
            elif field['type'] == constants.MULTISELECT:
                if isinstance(values[4], list):
                    values[4] = '|'.join(values[4])
                writer.writerow(values)
            else:
                writer.writerow(values)
        writer.new_worksheet('Files')
        writer.writerow(('File', 'Size', 'Content type', 'URL'))
        for filename in sorted(order.get('_attachments', [])):
            if filename.startswith(constants.SYSTEM): continue
            stub = order['_attachments'][filename]
            writer.writerow((filename,
                             stub['length'],
                             stub['content_type'],
                             URL('order_file', order['_id'], filename)))
        return writer

    def get_writer(self):
        return utils.CsvWriter('Order')

    def write_finish(self, order):
        self.set_header('Content-Type', constants.CSV_MIME)
        filename = order.get('identifier') or order['_id']
        self.set_header('Content-Disposition',
                        'attachment; filename="%s.csv"' % filename)
        

class OrderXlsx(OrderCsv):
    "Return an XLSX file containing the order data. Contains field definitions."

    def get_writer(self):
        return utils.XlsxWriter('Order')

    def write_finish(self, order):
        self.set_header('Content-Type', constants.XLSX_MIME)
        filename = order.get('identifier') or order['_id']
        self.set_header('Content-Disposition',
                        'attachment; filename="%s.xlsx"' % filename)


class OrderZip(OrderApiV1Mixin, OrderCsv):
    "Return a ZIP file containing CSV, XLSX, JSON and files for the order."

    def get(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            raise tornado.web.HTTPError(404, reason=str(msg))
        try:
            self.check_readable(order)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        zip_io = io.BytesIO()
        with zipfile.ZipFile(zip_io, 'w') as writer:
            name = order.get('identifier') or order['_id']
            csvwriter = self.write_order(order, writer=utils.CsvWriter('Order'))
            writer.writestr(name + '.csv', csvwriter.getvalue())
            xlsxwriter = self.write_order(order,
                                          writer=utils.XlsxWriter('Order'))
            writer.writestr(name + '.xlsx', xlsxwriter.getvalue())
            writer.writestr(name + '.json',
                            json.dumps(self.get_order_json(order, full=True)))
            for filename in sorted(order.get('_attachments', [])):
                outfile = self.db.get_attachment(order, filename)
                writer.writestr(filename, outfile.read())
        self.write(zip_io.getvalue())
        self.set_header('Content-Type', constants.ZIP_MIME)
        filename = order.get('identifier') or order['_id']
        self.set_header('Content-Disposition',
                        'attachment; filename="%s.zip"' % filename)


class Orders(RequestHandler):
    "Orders list page."

    @tornado.web.authenticated
    def get(self):
        # Ordinary users are not allowed to see the overall orders list.
        if not self.is_staff():
            self.see_other('account_orders', self.current_user['email'])
            return
        # Count of all orders
        view = self.db.view('order/status', reduce=True)
        try:
            r = list(view)[0]
        except IndexError:
            all_count = 0
        else:
            all_count = r.value
        # Initial ordering by the 'modified' column.
        order_column = 5 + \
                       int(settings['ORDERS_LIST_TAGS']) + \
                       len(settings['ORDERS_LIST_FIELDS']) + \
                       len(settings['ORDERS_LIST_STATUSES'])
        self.set_filter()
        self.render('orders.html',
                    all_forms=self.get_forms_titles(all=True),
                    form_titles=sorted(self.get_forms_titles().values()),
                    filter=self.filter,
                    orders=self.get_orders(),
                    order_column=order_column,
                    account_names=self.get_account_names(),
                    all_count=all_count)

    def set_filter(self):
        "Set the filter parameters dictionary."
        self.filter = dict()
        for key in ['status', 'form_title'] + \
                   [f['identifier'] for f in settings['ORDERS_LIST_FIELDS']]:
            try:
                value = self.get_argument(key)
                if not value: raise KeyError
                self.filter[key] = value
            except (tornado.web.MissingArgumentError, KeyError):
                pass
        recent = self.get_argument('recent', None)
        if recent is None:
            recent = True
        else:
            try:
                recent = utils.to_bool(recent)
            except ValueError:
                recent = True
        self.filter['recent'] = recent

    def get_orders(self):
        "Get all orders according to current filter."
        forms = self.get_forms_titles(all=True)
        orders = self.filter_by_status(self.filter.get('status'))
        orders = self.filter_by_forms(self.filter.get('form_title'),
                                      forms=forms,
                                      orders=orders)
        for f in settings['ORDERS_LIST_FIELDS']:
            orders = self.filter_by_field(f['identifier'],
                                          self.filter.get(f['identifier']),
                                          orders=orders)
        try:
            limit = settings['DISPLAY_ORDERS_MOST_RECENT']
            if not isinstance(limit, int): raise ValueError
        except (ValueError, KeyError):
            limit = 0
        # No filter; all orders
        if orders is None:
            if limit > 0 and self.filter.get('recent', True):
                view = self.db.view('order/modified',
                                    include_docs=True,
                                    descending=True,
                                    limit=limit)
            else:
                view = self.db.view('order/modified',
                                    include_docs=True,
                                    descending=True)
            orders = [r.doc for r in view]
        elif limit > 0 and self.filter.get('recent', True):
            orders = orders[:limit]
        return orders

    def filter_by_status(self, status, orders=None):
        "Return orders list if any status filter, or None if none."
        if status:
            if orders is None:
                view = self.db.view('order/status',
                                    descending=True,
                                    startkey=[status, constants.CEILING],
                                    endkey=[status],
                                    reduce=False,
                                    include_docs=True)
                orders = [r.doc for r in view]
            else:
                orders = [o for o in orders if o['status'] == status]
        return orders

    def filter_by_forms(self, form_title, forms, orders=None):
        "Return orders list if any form filter, or None if none."
        if form_title:
            forms = set([f[0] for f in list(forms.items()) if f[1] == form_title])
            if orders is None:
                orders = []
                for form in forms:
                    view = self.db.view('order/form',
                                        descending=True,
                                        reduce=False,
                                        include_docs=True)
                    orders.extend([r.doc for r in
                                   view[[form, constants.CEILING]:[form]]])
            else:
                orders = [o for o in orders if o['form'] in forms]
        return orders

    def filter_by_field(self, identifier, value, orders=None):
        "Return orders list if any field filter, or None if none."
        if value:
            if orders is None:
                view = self.db.view('order/modified',
                                    include_docs=True,
                                    descending=True)
                orders = [r.doc for r in view]
            if value == '__none__': value = None
            orders = [o for o in orders if o['fields'].get(identifier) == value]
        return orders


class OrdersApiV1(OrderApiV1Mixin, OrderMixin, Orders):
    "Orders API; JSON output."

    def get(self):
        "JSON output."
        URL = self.absolute_reverse_url
        self.check_staff()
        self.set_filter()
        result = utils.get_json(URL('orders_api', **self.filter), 'orders')
        result['filter'] = self.filter
        result['links'] = dict(api=dict(href=URL('orders_api')),
                               display=dict(href=URL('orders')))
        # Get names and forms lookups once only
        names = self.get_account_names()
        forms = self.get_forms_titles(all=True)
        result['items'] = []
        keys = [f['identifier'] for f in settings['ORDERS_LIST_FIELDS']]
        for order in self.get_orders():
            data = self.get_order_json(order, names, forms)
            data['fields'] = OD()
            for key in keys:
                data['fields'][key] = order['fields'].get(key)
            result['items'].append(data)
            result['invalid'] = order['invalid']
        self.write(result)


class OrdersCsv(Orders):
    "Orders list as CSV file."

    @tornado.web.authenticated
    def get(self):
        # Ordinary users are not allowed to see the overall orders list.
        if not self.is_staff():
            self.see_other('account_orders', self.current_user['email'])
            return
        self.set_filter()
        writer = self.get_writer()
        writer.writerow((settings['SITE_NAME'], utils.today()))
        row = ['Identifier', 'Title', 'IUID', 'URL', 
               'Form', 'Form IUID', 'Form URL',
               'Owner', 'Owner name', 'Owner URL', 'Tags']
        row.extend([f['identifier'] for f in settings['ORDERS_LIST_FIELDS']])
        row.append('Status')
        row.extend([s.capitalize() for s in settings['ORDERS_LIST_STATUSES']])
        row.append('Modified')
        writer.writerow(row)
        names = self.get_account_names()
        forms = self.get_forms_titles(all=True)
        for order in self.get_orders():
            row = [order.get('identifier') or '',
                   order['title'] or '[no title]',
                   order['_id'],
                   self.order_reverse_url(order),
                   forms[order['form']],
                   order['form'],
                   self.absolute_reverse_url('form', order['form']),
                   order['owner'],
                   names[order['owner']],
                   self.absolute_reverse_url('account', order['owner']),
                   ', '.join(order.get('tags', []))]
            for f in settings['ORDERS_LIST_FIELDS']:
                row.append(order['fields'].get(f['identifier']))
            row.append(order['status'])
            for s in settings['ORDERS_LIST_STATUSES']:
                row.append(order['history'].get(s))
            row.append(order['modified'])
            writer.writerow(row)
        self.write(writer.getvalue())
        self.write_finish()

    def get_writer(self):
        return utils.CsvWriter()

    def write_finish(self):
        self.set_header('Content-Type', constants.CSV_MIME)
        self.set_header('Content-Disposition', 
                        'attachment; filename="orders.csv"')
        

class OrdersXlsx(OrdersCsv):
    "Orders list as XLSX."

    def get_writer(self):
        return utils.XlsxWriter()

    def write_finish(self):
        self.set_header('Content-Type', constants.XLSX_MIME)
        self.set_header('Content-Disposition', 
                        'attachment; filename="orders.xlsx"')


class OrderLogs(OrderMixin, RequestHandler):
    "Order log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        try:
            self.check_readable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        title = "Logs for {0} '{1}'".format(utils.terminology('order'),
                                             order['title'] or '[no title]')
        self.render('logs.html',
                    title=title,
                    entity=order,
                    logs=self.get_logs(order['_id']))


class OrderCreate(OrderMixin, RequestHandler):
    "Create a new order."

    # Do not use auth decorator: Instead show error message if not logged in.
    def get(self):
        try:
            if not self.current_user:
                raise ValueError("You need to be logged in to create {0}."
                                 " Register to get an account if you don't have one."
                                 .format(utils.terminology('order')))
            self.check_creation_enabled()
            form = self.get_form(self.get_argument('form'), check=True)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
        else:
            self.render('order_create.html', form=form)

    @tornado.web.authenticated
    def post(self):
        try:
            self.check_creation_enabled()
            form = self.get_form(self.get_argument('form'), check=True)
            with OrderSaver(rqh=self) as saver:
                saver.create(form)
                saver.autopopulate()
                saver.check_fields_validity()
        except ValueError as msg:
            self.see_other('home', error=str(msg))
        else:
            self.see_other('order_edit', saver.doc['_id'])


class OrderCreateApiV1(OrderApiV1Mixin, OrderMixin, RequestHandler):
    "Create a new order by an API call."

    def post(self):
        "Form IUID and title in the JSON body of the request."
        try:
            self.check_login()
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        try:
            self.check_creation_enabled()
            data = self.get_json_body()
            iuid = data.get('form')
            if not iuid: raise ValueError('no form IUID given')
            form = self.get_form(iuid, check=True)
            with OrderSaver(rqh=self) as saver:
                saver.create(form, title=data.get('title'))
                saver.autopopulate()
                saver.check_fields_validity()
        except ValueError as msg:
            raise tornado.web.HTTPError(400, reason=str(msg))
        else:
            self.write(self.get_order_json(saver.doc, full=True))


class OrderEdit(OrderMixin, RequestHandler):
    "Page for editing an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        colleagues = sorted(self.get_account_colleagues(self.current_user['email']))
        form = self.get_form(order['form'])
        fields = Fields(form)
        if self.is_staff():
            tags = order.get('tags', [])
        else:
            tags = [t for t in order.get('tags', []) if not ':' in t]
        links = []
        for link in order.get('links', {}).get('external', []):
            if link['href'] == link['title']:
                links.append(link['href'])
            else:
                links.append("%s %s" % (link['href'], link['title']))
        # XXX Currently, multiselect fields are not handled correctly.
        #     Too much effort; leave as is for the time being.
        hidden_fields = set([f['identifier'] for f in fields.flatten()
                             if f['type'] != 'multiselect'])
        # For each table input field, create code for use in bespoke JavaScript
        tableinputs = {}
        for field in fields.flatten():
            if field['type'] != 'table': continue
            tableinput = ["<tr>"
                          "<td id='rowid__' class='table-input-row-0'></td>"]
            for i, coldef in enumerate(field['table']):
                column = utils.parse_field_table_column(coldef)
                rowid = "rowid_%s" % i
                if column['type'] == constants.SELECT:
                    inp = ["<select class='form-control' name='%s' id='%s'>"
                           % (rowid, rowid)]
                    inp.extend(["<option>%s</option>" % o
                                for o in column['options']])
                    inp = ''.join(inp)
                elif column['type'] == constants.INT:
                    inp = "<input type='number' step='1' class='form-control'"\
                          " name='%s' id='%s'>" % (rowid, rowid)
                elif column['type'] == constants.FLOAT:
                    inp = "<input type='number' step='%s'" \
                          " class='form-control' name='%s' id='%s'>" % \
                          (constants.FLOAT_STEP, rowid, rowid)
                elif column['type'] == constants.DATE:
                    inp = "<input type='text' class='form-control datepicker'" \
                          " name='%s' id='%s'>" % (rowid, rowid)
                else:           # Default type: 'string'
                    inp = "<input type='text' class='form-control'" \
                          " name='%s' id='%s'>" % (rowid, rowid)
                tableinput.append("<td>%s</td>" % inp)
            tableinput.append("</tr>")
            tableinputs[field['identifier']] = ''.join(tableinput)
        self.render('order_edit.html',
                    title="Edit {0} '{1}'".format(
                        utils.terminology('order'),
                        order['title'] or '[no title]'),
                    order=order,
                    tags=tags,
                    links=links,
                    colleagues=colleagues,
                    form=form,
                    fields=form['fields'],
                    hidden_fields=hidden_fields,
                    tableinputs=tableinputs)

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        flag = self.get_argument('__save__', None)
        try:
            message = "{0} saved.".format(utils.terminology('Order'))
            error = None
            with OrderSaver(doc=order, rqh=self) as saver:
                saver['title'] = self.get_argument('__title__', None)
                saver.set_tags(self.get_argument('__tags__', '').\
                               replace(',', ' ').split())
                saver.set_external(self.get_argument('__links__', '').\
                                   split('\n'))
                saver.update_fields()
                if flag == constants.SUBMIT: # Hard-wired status
                    if self.is_submittable(saver.doc):
                        saver.set_status(constants.SUBMITTED)
                        message = "{0} saved and submitted."\
                            .format(utils.terminology('Order'))
                    else:
                        error = "{0} could not be submitted due to" \
                                " invalid or missing values."\
                                .format(utils.terminology('Order'))
            self.set_error_flash(error)
            self.set_message_flash(message)
            if flag == 'continue':
                self.see_other('order_edit', order['_id'])
            else:
                self.redirect(self.order_reverse_url(order))
        except ValueError as msg:
            self.set_error_flash(str(msg))
            self.redirect(self.order_reverse_url(order))


class OrderOwner(OrderMixin, RequestHandler):
    "Change the owner of an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        self.render('order_owner.html',
                    title="Change owner of {0} '{1}'".format(
                        utils.terminology('order'),
                        order['title'] or '[no title]'),
                    order=order)

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        try:
            owner = self.get_argument('owner')
            account = self.get_account(owner)
            if account.get('status') != constants.ENABLED:
                raise ValueError('Owner account is not enabled.')
            with OrderSaver(doc=order, rqh=self) as saver:
                saver['owner'] = account['email']
        except tornado.web.MissingArgumentError:
            pass
        except ValueError as msg:
            self.set_error_flash(str(msg))
        self.set_message_flash("Changed owner of {0}.".format(
            utils.terminology('Order')))
        if self.is_readable(order):
            self.redirect(self.order_reverse_url(order))
        else:
            self.see_other('home')


class OrderClone(OrderMixin, RequestHandler):
    "Create a new order from an existing one."

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        if not self.is_clonable(order):
            raise ValueError("This {0} is outdated; its form has been disabled."
                             .format(utils.terminology('order')))
        form = self.get_form(order['form'])
        erased_files = set()
        with OrderSaver(rqh=self) as saver:
            saver.create(form, title="Clone of {0}".format(
                order['title'] or '[no title]'))
            for field in saver.fields:
                id = field['identifier']
                if field.get('erase_on_clone'):
                    if field['type'] == constants.FILE:
                        erased_files.add(order['fields'][id])
                    saver['fields'][id] = None
                else:
                    saver['fields'][id] = order['fields'][id]
            saver.check_fields_validity()
        # Make copies of attached files.
        #  Must be done after initial save to avoid version mismatches.
        for filename in order.get('_attachments', []):
            if filename.startswith(constants.SYSTEM): continue
            if filename in erased_files: continue
            stub = order['_attachments'][filename]
            outfile = self.db.get_attachment(order, filename)
            self.db.put_attachment(saver.doc,
                                   outfile,
                                   filename=filename,
                                   content_type=stub['content_type'])
        self.redirect(self.order_reverse_url(saver.doc))


class OrderTransition(OrderMixin, RequestHandler):
    "Change the status of an order."

    @tornado.web.authenticated
    def post(self, iuid, targetid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            for target in self.get_targets(order):
                if target['identifier'] == targetid: break
            else:
                raise ValueError('disallowed status transition')
            with OrderSaver(doc=order, rqh=self) as saver:
                saver.set_status(targetid)
        except ValueError as msg:
            self.set_error_flash(msg)
        self.redirect(self.order_reverse_url(order))


class OrderTransitionApiV1(OrderApiV1Mixin, OrderMixin, RequestHandler):
    "Change the status of an order by an API call."

    def post(self, iuid, targetid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
            with OrderSaver(doc=order, rqh=self) as saver:
                saver.set_status(targetid)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        self.write(self.get_order_json(order, full=True))


class OrderFile(OrderMixin, RequestHandler):
    "File attached to an order."

    @tornado.web.authenticated
    def get(self, iuid, filename=None):
        if filename is None:
            raise tornado.web.HTTPError(400)
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError as msg:
            self.see_other('home', error=str(msg))
            return
        outfile = self.db.get_attachment(order, filename)
        if outfile is None:
            self.see_other('order', iuid, error='No such file.')
        else:
            self.write(outfile.read())
            outfile.close()
            self.set_header('Content-Type',
                            order['_attachments'][filename]['content_type'])
            # Try to avoid strange latin-1 encoding issue with tornado.
            b = 'attachment; filename="%s"' % filename
            b = b.encode('utf-8')
            self.set_header('Content-Disposition', b)

    @tornado.web.authenticated
    def post(self, iuid, filename=None):
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(iuid, filename)
            return
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        try:
            infile = self.request.files['file'][0]
        except (KeyError, IndexError):
            pass
        else:
            if infile.filename.startswith(constants.SYSTEM):
                raise tornado.web.HTTPError(400, reason='Reserved filename.')
            with OrderSaver(doc=order, rqh=self) as saver:
                saver.add_file(infile)
        self.redirect(self.order_reverse_url(order))

    @tornado.web.authenticated
    def delete(self, iuid, filename):
        if filename is None:
            raise tornado.web.HTTPError(400)
        if filename.startswith(constants.SYSTEM):
            raise tornado.web.HTTPError(400, reason='Reserved filename.')
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        fields = Fields(self.get_form(order['form']))
        with OrderSaver(doc=order, rqh=self) as saver:
            for key in order['fields']:
                # Remove the field value if it is the filename.
                # XXX Slightly dangerous: may delete a value that happens to
                # be identical to the filename. Shouldn't be too commmon...
                if order['fields'][key] == filename:
                    order['fields'][key] = None
                    if fields[key]['required']:
                        saver.doc['invalid'][key] = 'missing value'
                    else:
                        saver.doc['invalid'].pop(key, None)
                    break
            saver.delete_filename = filename
            saver.changed['file_deleted'] = filename
        self.redirect(self.order_reverse_url(order))


class OrderReport(OrderMixin, RequestHandler):
    "View the report for an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        try:
            report = order['report']
            outfile = self.db.get_attachment(order, constants.SYSTEM_REPORT)
            if outfile is None: raise KeyError
        except KeyError:
            self.see_other('order', iuid, error='No report available.')
            return
        content_type = order['_attachments'][constants.SYSTEM_REPORT]['content_type']
        if report.get('inline'):
            self.render('order_report.html',
                        order=order,
                        content=outfile.read(),
                        content_type=content_type)
        else:
            self.write(outfile.read())
            outfile.close()
            self.set_header('Content-Type', content_type)
            name = order.get('identifier') or order['_id']
            ext = utils.get_filename_extension(content_type)
            filename = "%s_report%s" % (name, ext)
            self.set_header('Content-Disposition',
                            'attachment; filename="%s"' % filename)


class OrderReportEdit(OrderMixin, RequestHandler):
    "Edit the report for an order."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.render('order_report_edit.html', order=order)

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        with OrderSaver(doc=order, rqh=self) as saver:
            try:
                infile = self.request.files['report'][0]
            except (KeyError, IndexError):
                if order.get('report'):
                    saver.delete_filename = constants.SYSTEM_REPORT
                    saver['report'] = dict()
            else:
                saver['report'] = dict(
                    timestamp=utils.timestamp(),
                    inline=infile.content_type in (constants.HTML_MIME,
                                                   constants.TEXT_MIME))
                saver.files.append(dict(filename=constants.SYSTEM_REPORT,
                                        body=infile.body,
                                        content_type=infile.content_type))
        self.redirect(self.order_reverse_url(order))


class OrderReportApiV1(OrderApiV1Mixin, OrderMixin, RequestHandler):
    "Order report API: get or set."

    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        try:
            report = order['report']
            outfile = self.db.get_attachment(order, constants.SYSTEM_REPORT)
            if outfile is None: raise KeyError
        except KeyError:
            raise tornado.web.HTTPError(404)
        self.write(outfile.read())
        outfile.close()
        content_type = order['_attachments'][constants.SYSTEM_REPORT]['content_type']
        self.set_header('Content-Type', content_type)
        name = order.get('identifier') or order['_id']
        ext = utils.get_filename_extension(content_type)
        filename = "%s_report%s" % (name, ext)
        self.set_header('Content-Disposition',
                        'attachment; filename="%s"' % filename)

    def put(self, iuid):
        try:
            self.check_admin()
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        order = self.get_entity(iuid, doctype=constants.ORDER)
        with OrderSaver(doc=order, rqh=self) as saver:
            content_type = self.request.headers.get('content-type') or constants.BIN_MIME
            saver['report'] = dict(timestamp=utils.timestamp(),
                                   inline=content_type in (constants.HTML_MIME,
                                                           constants.TEXT_MIME))
            saver.files.append(dict(filename=constants.SYSTEM_REPORT,
                                    body=self.request.body,
                                    content_type=content_type))
        self.write('')
