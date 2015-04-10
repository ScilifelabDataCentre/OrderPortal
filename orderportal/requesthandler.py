"OrderPortal: RequestHandler subclass."

from __future__ import unicode_literals, print_function, absolute_import

import logging
import json
import collections
import urllib
import smtplib
from email.mime.text import MIMEText

import tornado.web
import couchdb

import orderportal
from . import settings
from . import constants
from . import utils


class RequestHandler(tornado.web.RequestHandler):
    "Base request handler."

    def prepare(self):
        "Get the database connection."
        self.db = utils.get_db()

    def get_template_namespace(self):
        "Set the variables accessible within the template."
        result = super(RequestHandler, self).get_template_namespace()
        result['title'] = 'OrderPortal'
        result['version'] = orderportal.__version__
        result['settings'] = settings
        result['constants'] = constants
        result['absolute_reverse_url'] = self.absolute_reverse_url
        result['is_admin'] = self.is_admin()
        return result

    def set_header_allow(self, **kwargs):
        "Set the header 'Allow' in the output, if defined."
        try:
            self.set_header('Allow', ', '.join(self.get_allowed(**kwargs)))
        except NotImplementedError:
            pass

    def set_header_content_type(self, item):
        "Set the header describing the content type of the item."
        assert item
        assert constants.DOCTYPE in item
        assert item[constants.DOCTYPE] == constants.ITEM
        # Rely on the content_type set for the item, rather than
        # the content_type for the attachment in the CouchDB database.
        self.set_header('Content-Type', item['content_type'])

    def set_header_content_disposition(self, item):
        "Set the header describing the filename of the item."
        assert item
        assert constants.DOCTYPE in item
        assert item[constants.DOCTYPE] == constants.ITEM
        try:
            filename = self.get_entity_attachment_filename(item)
        except KeyError:
            logging.debug("set_header_content_type: KeyError")
            pass
        else:
            self.set_header('Content-Disposition',
                            'attachment; filename="{}"'.format(filename))

    def see_other(self, absurl):
        "Redirect to the given absolute URL using HTTP status 303 See Other."
        self.redirect(absurl, status=303)

    def absolute_reverse_url(self, name, *args, **query):
        "Get the absolute URL given the handler name, arguments and query."
        if name is None:
            path = ''
        else:
            path = self.reverse_url(name, *args, **query)
        return settings['BASE_URL'].rstrip('/') + path

    def reverse_url(self, name, *args, **query):
        "Allow adding query arguments to the URL."
        url = super(RequestHandler, self).reverse_url(name, *args)
        url = url.rstrip('?')   # tornado bug? left-over '?' sometimes
        if query:
            url += '?' + urllib.urlencode(query)
        return url

    def get_current_user(self):
        "Get the currently logged-in user, if any."
        email = self.get_secure_cookie(constants.USER_COOKIE)
        logging.debug("secure cookie user: %s", email)
        if not email:
            return None
        try:
            user = self.get_user(email)
        except tornado.web.HTTPError:
            return None
        # Check that user is enabled.
        if user.get('status') != constants.ENABLED:
            logging.debug("user %s not enabled", email)
            return None
        # Check if login session is invalidated.
        if user.get('login') is None:
            logging.debug("user %s has no login session", email)
            return None
        return user

    def is_owner(self, entity):
        "Does the current user own the given entity?"
        return self.current_user and \
            entity['owner'] == self.current_user['email']            

    def is_admin(self):
        "Is the current user admin?"
        # Not a property, since the above is not.
        return self.current_user and \
            self.current_user['role'] == constants.ADMIN

    def is_staff(self):
        "Is the current user staff or admin?"
        # Not a property, since the above is not.
        return self.current_user and \
            self.current_user['role'] in (constants.STAFF, constants.ADMIN)

    def check_admin(self):
        "Check if current user is admin."
        if not self.is_admin():
            raise tornado.web.HTTPError(403,
                                        reason="you do not have role 'admin'")

    def check_staff(self):
        "Check if current user is staff or admin."
        if not self.is_staff():
            raise tornado.web.HTTPError(403,
                                        reason="you do not have role 'staff'")

    def check_owner_or_staff(self, entity):
        "Check if current user is owner of the entity, or is staff or admin."
        if self.is_owner(entity): return
        if self.is_staff(): return
        raise tornado.web.HTTPError(403, reason='you do not own the entity')

    def check_read_order(self, order):
        "Check if current user may read the order."
        if self.is_owner(order): return
        if self.is_staff(): return
        raise tornado.web.HTTPError(403, reason='you may not read the order')

    def check_edit_order(self, order):
        "Check if current user may edit the order."
        if self.is_owner(order): return
        if self.is_staff(): return
        raise tornado.web.HTTPError(403, reason='you may not edit the order')

    def get_entity(self, iuid, doctype=None):
        """Get the entity by the IUID. Check the doctype, if given.
        Raise HTTP 404 if no such entity.
        """
        try:
            entity = self.db[iuid]
        except couchdb.ResourceNotFound:
            raise tornado.web.HTTPError(404, reason='no such entity')
        try:
            if doctype is not None and entity[constants.DOCTYPE] != doctype:
                raise KeyError
        except KeyError:
            raise tornado.web.HTTPError(404, reason='invalid entity doctype')
        return entity

    def get_entity_view(self, viewname, key, reason='no such entity'):
        """Get the entity by the view name and the key.
        Raise HTTP 404 if no such entity.
        """
        view = self.db.view(viewname, include_docs=True)
        rows = list(view[key])
        if len(rows) == 1:
            return rows[0].doc
        else:
            raise tornado.web.HTTPError(404, reason=reason)

    def get_field(self, identifier):
        return self.get_entity_view('field/identifier', identifier)

    def get_all_fields(self):
        "Return all fields in identifier lexical order."
        view = self.db.view('field/identifier', include_docs=True)
        return [self.get_presentable(r.doc) for r in view]

    def get_all_fields_sorted(self):
        "Return the fields sorted in hierarchy, and within levels."
        lookup = dict([(f['identifier'], f) for f in self.get_all_fields()])
        return self._sorted_fields(None, lookup.copy(), lookup)

    def _sorted_fields(self, parent, fields, lookup, level=0):
        result = []
        for field in fields.values():
            if lookup.get(field.get('parent')) is parent:
                field['__level__'] = level
                result.append(field)
                del fields[field['identifier']]
        result.sort(lambda i, j: cmp(i['position'], j['position']))
        for c in result:
            c['__children__'] = self._sorted_fields(c, fields, lookup, level+1)
        return result

    def get_all_fields_flattened(self, exclude=None):
        "Return the fields sorted in a flattened list."
        fields = self.get_all_fields_sorted()
        return self._flatten_fields(fields, exclude=exclude)

    def _flatten_fields(self, fields, exclude=None):
        result = []
        for f in fields:
            if exclude and exclude['identifier'] == f['identifier']: continue
            result.append(f)
            try:
                result.extend(self._flatten_fields(f['__children__'],
                                                   exclude=exclude))
            except AttributeError:
                pass
        return result

    def get_entity_url(self, url):
        "Get the entity given its URL, if it is a local entity, else None."
        if not url: return None
        iuid = url.split('/')[-1]
        if not constants.IUID_RX.match(iuid): return None
        try:
            entity = self.db[iuid]
        except couchdb.http.ResourceNotFound:
            return None
        try:
            if entity[constants.DOCTYPE] in constants.ENTITIES:
                return entity
        except KeyError:
            pass
        return None

    def get_entity_attachment_filename(self, entity):
        """Return the filename of the attachment for the given entity.
        Raise KeyError if no attachment.
        """
        return entity['_attachments'].keys()[0]

    def get_entity_attachment_data(self, entity):
        """Return the data of the attachment for the given entity.
        Return None if attachment has no data, or no attachment.
        """
        try:
            filename = self.get_entity_attachment_filename(entity)
        except KeyError:
            return None
        infile = self.db.get_attachment(entity, filename)
        if infile is None: # When file is empty
            data = None
        else:
            data = infile.read()
            infile.close()
        return data

    def get_user(self, email):
        """Get the user identified by the email address.
        Raise HTTP 404 if no such user.
        """
        return self.get_entity_view('user/email', email, reason='no such user')

    def get_presentable(self, doc):
        """Make the entity document presentable:
        - Convert to sorted dictionary.
        - Remove all entries with value None.
        - Change '_id' key to 'iuid'.
        - Remove '_rev' and 'orderportal_doctype' attributes.
        """
        result = collections.OrderedDict()
        result['iuid'] = doc['_id']
        ignore = set(['_id', '_rev', '_attachments', 'orderportal_doctype'])
        for key in sorted(doc.keys()):
            if key in ignore: continue
            value = doc[key]
            if value is None: continue
            result[key] = value
        try:
            result['filename'] = doc['_attachments'].keys()[0]
        except (KeyError, IndexError):
            pass
        return result

    def get_logs(self, iuid, limit=constants.DEFAULT_MAX_DISPLAY_LOG+1):
        "Return the event log documents for the given entity iuid."
        kwargs = dict(include_docs=True,
                      startkey=[iuid, constants.HIGH_CHAR],
                      endkey=[iuid],
                      descending=True)
        if limit > 0:
            kwargs['limit'] = limit
        view = self.db.view('log/entity', **kwargs)
        logs = [self.get_presentable(r.doc) for r in view]
        # Ref to entity in DB is not needed in each log entry.
        for log in logs:
            del log['entity']
        return logs

    def delete_logs(self, iuid):
        "Delete the event log documents for the given entity iuid."
        view = self.db.view('log/entity',
                            startkey=[iuid],
                            endkey=[iuid, constants.HIGH_CHAR])
        for row in view:
            del self.db[row.id]

    def send_email(self, recipient, subject, text, sender=None):
        "Send an email to the given recipient from the given sender user."
        if sender:
            from_address = sender['email']
        else:
            from_address = settings['EMAIL']['USER']
        mail = MIMEText(text)
        mail['Subject'] = subject
        mail['From'] = from_address
        mail['To'] = recipient
        server = smtplib.SMTP(host=settings['EMAIL']['HOST'],
                              port=settings['EMAIL']['PORT'])
        if settings['EMAIL'].get('TLS'):
            server.starttls()
        try:
            server.login(settings['EMAIL']['USER'],
                         settings['EMAIL']['PASSWORD'])
        except KeyError:
            pass
        logging.debug("sendmail to %s from %s", recipient, from_address)
        server.sendmail(from_address, [recipient], mail.as_string())
        server.quit()
