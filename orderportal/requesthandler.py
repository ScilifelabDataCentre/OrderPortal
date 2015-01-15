"OrderPortal: RequestHandler subclass."

from __future__ import unicode_literals, print_function, absolute_import

import logging
import json
import urllib
import collections
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
        result['title'] = 'Orderportal'
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

    def get_allowed(self, **kwargs):
        "Return list of allowed HTTP methods. To be implemented in subclass!"
        raise NotImplementedError

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
        """Allow adding query arguments to the URL.
        Handle special cases that Tornado cannot deal with.
        """
        if name == 'spec':
            url = "/spec{}".format(args[0])
        elif name == 'specs':
            url = '/specs'
        elif name == 'specs_folder':
            url = "/specs{}".format(args[0])
        else:
            url = super(RequestHandler, self).reverse_url(name, *args)
            url = url.rstrip('?')   # tornado bug? left-over '?' sometimes
        if query:
            url += '?' + urllib.urlencode(query)
        return url

    @property
    def is_input_jsonld(self):
        "Does the request contain JSON-LD input?"
        try:
            return self._is_input_jsonld
        except AttributeError:
            content = self.request.headers.get('Content-Type', '')
            content = [p.strip() for p in content.split(',')]
            self._is_input_jsonld = constants.JSONLD_MIME in content or \
                                    constants.JSON_MIME in content
            return self._is_input_jsonld

    @property
    def is_output_jsonld(self):
        """Does the client accept JSON-LD output?
        Check the '_format' argument, if any, and then the 'Accept' header.
        """
        try:
            return self._is_output_jsonld
        except AttributeError:
            format = self.get_argument('_format', default='')
            if format.lower() in ('jsonld', 'json'):
                return True
            accept = [p.strip() for p
                      in self.request.headers.get('Accept', '').split(',')]
            self._is_output_jsonld = constants.JSONLD_MIME in accept or \
                                     constants.JSON_MIME in accept
            return self._is_output_jsonld

    @property
    def jsonld(self):
        "Return the request data interpreted as JSON-LD. Basic validation."
        try:
            return self._jsonld
        except AttributeError:
            try:
                self._jsonld = json.loads(self.request.body)
                if self._jsonld['@context'] != constants.CONTEXT:
                    raise KeyError
            except (TypeError, ValueError):
                raise tornado.web.HTTPError(400, reason='invalid JSON-LD data')
            except KeyError:
                raise tornado.web.HTTPError(400, reason='invalid context')
            return self._jsonld

    def get_current_user(self):
        "Get the currently logged-in user."
        try:
            return self._user
        except AttributeError:
            self._user = None
            username = self.get_secure_cookie(constants.USER_COOKIE)
            if username:
                logging.debug('authentication using secure cookie')
                try:
                    self._user = self.get_user(username)
                except tornado.web.HTTPError:
                    pass
            else:
                api_key = self.request.headers.get(constants.API_KEY_HEADER)
                if api_key:
                    logging.debug('authentication using API key')
                    try:
                        self._user = self.get_user_api_key(api_key)
                    except tornado.web.HTTPError:
                        pass
            if self._user is None:
                logging.debug('unauthenticated user')
            else:
                logging.debug("authenticated user: %s", self._user['username'])
            return self._user

    def is_owner(self, entity):
        "Does the current user own the given entity?"
        return self.current_user and \
            entity['owner'] == self.current_user['username']            

    def is_admin(self):
        "Is the current user admin?"
        # Not a property, since the above is not.
        return self.current_user and \
            constants.ADMIN in self.current_user['roles']

    def check_admin(self):
        "Check if current user is admin."
        if not self.is_admin():
            raise tornado.web.HTTPError(403, reason='not logged in as admin')

    def may_read(self, entity):
        "May the current user read the entity?"
        if self.is_owner(entity): return True
        category = entity['access'][constants.READ]
        if category == constants.PUBLIC: return True
        if category == constants.KNOWN and self.current_user: return True
        if self.is_admin(): return True
        return False

    def check_read(self, entity):
        "Check if the current user may read the entity."
        if not self.may_read(entity):
            raise tornado.web.HTTPError(403, reason='may not read entity')

    def may_edit(self, entity):
        "May the current user edit the entity?"
        if self.is_owner(entity): return True
        category = entity['access'][constants.EDIT]
        if category == constants.PUBLIC: return True
        if category == constants.KNOWN and self.current_user: return True
        if self.is_admin(): return True
        return False

    def check_edit(self, entity):
        "Check if the current user may edit the entity."
        if not self.may_edit(entity):
            raise tornado.web.HTTPError(403, reason='may not edit entity')

    def may_delete(self, entity):
        "May the current user delete the entity?"
        # No need to check for 'known' or 'public'; never allowed.
        if not self.current_user: return False
        if self.is_owner(entity): return True
        if self.is_admin(): return True
        return False

    def check_delete(self, entity):
        "Check if the current user may delete the entity."
        if not self.may_delete(entity):
            raise tornado.web.HTTPError(403, reason='may not delete entity')

    def get_entity(self, iuid, doctype=None):
        """Get the entity by the IUID.
        Check the doctype, if given.
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

    def get_entity_view(self, viewname, key):
        """Get the entity by the view name and the key.
        Raise HTTP 404 if no such entity.
        """
        view = self.db.view(viewname, include_docs=True)
        rows = list(view[key])
        if len(rows) == 1:
            return rows[0].doc
        else:
            raise tornado.web.HTTPError(404, reason='no such entity')

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

    def get_user(self, username):
        """Get the user identified by the username or email address.
        Raise HTTP 404 if no such user.
        """
        try:
            return self.get_entity_view('user/username', username)
        except tornado.web.HTTPError:
            return self.get_entity_view('user/email', username)

    def get_user_api_key(self, api_key):
        """Get the user identified by the API key.
        Raise HTTP 404 if no such user.
        """
        return self.get_entity_view('user/api_key', api_key)

    def get_user_login_code(self, login_code):
        """Get the user identified by the login code.
        Raise HTTP 404 if no such user.
        """
        return self.get_entity_view('user/login_code', login_code)

    def get_user_count(self, entity, user):
        if entity == 'item':
            view = self.db.view('item/owner_count')
        elif entity == 'task':
            view = self.db.view('task/owner_count')
        else:
            raise ValueError('invalid entity for get_user_count')
        try:
            return view[user['username']].rows[0].value
        except IndexError:
            return 0

    def get_presentable(self, doc):
        """Make the entity document presentable:
        - Convert to ordered dictionary.
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

    def write_jsonld(self, idurl, data):
        "Write the data as JSON-LD, including @context, @id, home and version."
        result = collections.OrderedDict()
        result['@context'] = constants.CONTEXT
        result['@id'] = idurl
        result.update(data)
        result['home'] = self.absolute_reverse_url('home')
        result['orderportal'] = orderportal.__version__
        self.write(result)
        self.set_header('Content-Type', constants.JSONLD_MIME)

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
        ids = [r.id for r in view]
        for id in ids:
            del self.db[id]

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
