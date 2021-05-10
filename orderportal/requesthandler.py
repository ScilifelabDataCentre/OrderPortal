"RequestHandler subclass for all pages."

import base64
import functools
import logging
import traceback
import urllib.request, urllib.parse, urllib.error
import urllib.parse

import couchdb
import markdown
import simplejson as json       # XXX Python 3 kludge
import tornado.web

import orderportal
from . import constants
from . import settings
from . import utils


class RequestHandler(tornado.web.RequestHandler):
    "Base request handler."

    def prepare(self):
        "Get the database connection and global modes."
        self.db = utils.get_db()
        self.global_modes = constants.DEFAULT_GLOBAL_MODES.copy()
        try:
            self.global_modes.update(self.db['global_modes'])
        except couchdb.ResourceNotFound:
            pass

    def get_template_namespace(self):
        "Set the items accessible within the template."
        result = super(RequestHandler, self).get_template_namespace()
        result['version'] = orderportal.__version__
        result['constants'] = constants
        result['settings'] = settings
        result['terminology'] = utils.terminology
        result['get_account_name'] = utils.get_account_name
        result['global_modes'] = self.global_modes
        result['absolute_reverse_url'] = self.absolute_reverse_url
        result['order_reverse_url'] = self.order_reverse_url
        result['is_staff'] = self.is_staff()
        result['is_admin'] = self.is_admin()
        result['error'] = self.get_cookie('error', '').replace('_', ' ')
        self.clear_cookie('error')
        result['message'] = self.get_cookie('message', '').replace('_', ' ')
        self.clear_cookie('message')
        result['infos'] = [r.value for r in self.db.view('info/menu')]
        try:
            doc = self.get_entity_view('text/name', 'alert')
        except tornado.web.HTTPError:
            result['alert'] = None
        else:
            result['alert'] = markdown.markdown(doc['text'], output_format='html5')
        result['reduce'] = functools.reduce
        return result

    def see_other(self, name, *args, **kwargs):
        """Redirect to the absolute URL given by name
        using HTTP status 303 See Other."""
        query = kwargs.copy()
        try:
            self.set_error_flash(query.pop('error'))
        except KeyError:
            pass
        try:
            self.set_message_flash(query.pop('message'))
        except KeyError:
            pass
        url = self.absolute_reverse_url(name, *args, **query)
        self.redirect(url, status=303)

    def absolute_reverse_url(self, name, *args, **query):
        "Get the absolute URL given the handler name, arguments and query."
        if name is None:
            path = settings['BASE_URL_PATH_PREFIX'] or ''
        else:
            path = self.reverse_url(name, *args, **query)
        return settings['BASE_URL'] + path

    def reverse_url(self, name, *args, **query):
        "Allow adding query arguments to the URL."
        url = super(RequestHandler, self).reverse_url(name, *args)
        url = url.rstrip('?')   # tornado bug? left-over '?' sometimes
        if settings['BASE_URL_PATH_PREFIX']:
            url = settings['BASE_URL_PATH_PREFIX'] + url
        if query:
            query = dict([(k, str(v)) for k,v in list(query.items())])
            url += '?' + urllib.parse.urlencode(query)
        return url

    def static_url(self, path, include_host=None, **kwargs):
        "Returns the URL for a static resource."
        url = super(RequestHandler, self).static_url(path,
                                                     include_host=include_host,
                                                     **kwargs)
        if settings['BASE_URL_PATH_PREFIX']:
            parts = urllib.parse.urlparse(url)
            path = settings['BASE_URL_PATH_PREFIX'] + parts.path
            parts = (parts[0], parts[1], path, parts[3], parts[4], parts[5])
            url = urllib.parse.urlunparse(parts)
        return url

    def order_reverse_url(self, order, api=False, **query):
        "URL for order; use identifier variant if available. Always absolute."
        URL = self.absolute_reverse_url
        try:
            identifier = order['identifier']
        except KeyError:
            identifier = order['_id']
        if api:
            return URL('order_id_api', identifier, **query)
        else:
            return URL('order_id', identifier, **query)

    def set_message_flash(self, message):
        "Set message flash cookie."
        if message:
            self.set_flash('message', str(message))

    def set_error_flash(self, message):
        "Set error flash cookie message."
        if message:
            self.set_flash('error', str(message))

    def set_flash(self, name, message):
        message = message.replace(' ', '_')
        message = message.replace(';', '_')
        message = message.replace(',', '_')
        message = message.replace('\n', '_')
        self.set_cookie(name, message)

    def get_current_user(self):
        """Get the currently logged-in user account, or None.
        This overrides a tornado function, otherwise it should have
        been called 'get_current_account', since the term 'account'
        is used in this code rather than 'user'."""
        try:
            account = self.get_current_user_api_key()
        except ValueError:
            try:
                account = self.get_current_user_session()
            except ValueError:
                try:
                    account = self.get_current_user_basic()
                except ValueError:
                    return None
        if account.get('status') == constants.DISABLED:
            logging.info("Account %s DISABLED", account['email'])
            return None
        return account

    def get_current_user_api_key(self):
        """Get the current user by API key authentication.
        Raise ValueError if no or erroneous authentication.
        """
        try:
            api_key = self.request.headers[constants.API_KEY_HEADER]
        except KeyError:
            raise ValueError
        else:
            try:
                account = self.get_entity_view('account/api_key', api_key)
            except tornado.web.HTTPError:
                raise ValueError
            logging.info("API key login: account %s", account['email'])
            return account

    def get_current_user_session(self):
        """Get the current user from a secure login session cookie.
        Raise ValueError if no or erroneous authentication.
        """
        email = self.get_secure_cookie(
            constants.USER_COOKIE,
            max_age_days=settings['LOGIN_MAX_AGE_DAYS'])
        if not email: raise ValueError
        account = self.get_account(email)
        # Check if login session is invalidated.
        if account.get('login') is None: raise ValueError
        logging.info("Session authentication: %s", account['email'])
        return account

    def get_current_user_basic(self):
        """Get the current user by HTTP Basic authentication.
        This should be used only if the site is using TLS (SSL, https).
        Raise ValueError if no or erroneous authentication.
        """
        try:
            auth = self.request.headers['Authorization']
        except KeyError:
            raise ValueError
        try:
            auth = auth.split()
            if auth[0].lower() != 'basic': raise ValueError
            auth = base64.b64decode(auth[1])
            email, password = auth.split(':', 1)
            account = self.get_account(email)
            if utils.hashed_password(password) != account.get('password'):
                raise ValueError
        except (IndexError, ValueError, TypeError):
            raise ValueError
        logging.info("Basic auth login: account %s", account['email'])
        return account

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
            raise tornado.web.HTTPError(403, reason="Role 'admin' is required")

    def check_staff(self):
        "Check if current user is staff or admin."
        if not self.is_staff():
            raise tornado.web.HTTPError(
                403, reason="Role 'admin' or 'staff' is required")

    def check_login(self):
        "Check if logged in."
        if not self.current_user:
            raise tornado.web.HTTPError(403, reason='Must be logged in.')

    def get_admins(self):
        "Get the list of enabled admin accounts."
        view = self.db.view('account/role', include_docs=True)
        admins = [r.doc for r in view[constants.ADMIN]]
        return [a for a in admins if a['status'] == constants.ENABLED]

    def get_colleagues(self, email):
        "Get list of accounts in same groups as the account given by email."
        colleagues = dict()
        for row in self.db.view('group/member',
                                include_docs=True,
                                key=email.strip().lower()):
            for member in row.doc['members']:
                try:
                    account = self.get_account(member)
                except ValueError:
                    pass
                else:
                    if account['status'] == constants.ENABLED:
                        colleagues[account['email']] = account
        return list(colleagues.values())

    def get_next_counter(self, doctype):
        "Get the next counter number for the doctype."
        while True:
            try:
                doc = self.db[doctype] # Doc must be reloaded each iteration
            except couchdb.ResourceNotFound:
                doc = dict(_id=doctype)
                doc[constants.DOCTYPE] = constants.META
            try:
                number = doc['counter'] + 1
            except KeyError:
                number = 1
            doc['counter'] = number
            try:
                self.db.save(doc)
                return number
            except couchdb.ResourceConflict:
                pass

    def get_entity(self, iuid, doctype=None):
        """Get the entity by the IUID. Check the doctype, if given.
        Raise HTTP 404 if no such entity.
        """
        try:
            entity = self.db[iuid]
        except couchdb.ResourceNotFound:
            raise tornado.web.HTTPError(404, reason='Sorry, no such entity.')
        try:
            if doctype is not None and entity[constants.DOCTYPE] != doctype:
                raise KeyError
        except KeyError:
            raise tornado.web.HTTPError(
                404, reason='Internal problem: invalid entity doctype.')
        return entity

    def get_entity_view(self, viewname, key, reason='Sorry, no such entity.'):
        """Get the entity by the view name and the key.
        Raise HTTP 404 if no such entity.
        """
        view = self.db.view(viewname, reduce=False, include_docs=True)
        if isinstance(key, bytes): # Py 2-to-3; ugly, but seems to be working...
            key = key.decode()
        rows = list(view[key])
        if len(rows) == 1:
            return rows[0].doc
        else:
            raise tornado.web.HTTPError(404, reason=reason)

    def get_news(self, limit=None):
        "Get all news items in descending 'modified' order."
        kwargs = dict(include_docs=True, descending=True)
        if limit is not None:
            kwargs['limit'] = limit
        view = self.db.view('news/modified', **kwargs)
        return [r.doc for r in view]

    def get_events(self, upcoming=False):
        "Get all (descending) or upcoming (ascending) events."
        kwargs = dict(include_docs=True)
        if upcoming:
            kwargs['startkey'] = utils.today()
            kwargs['endkey'] = constants.CEILING
        else:
            kwargs['descending'] = True
        view = self.db.view('event/date', **kwargs)
        return [r.doc for r in view]

    def get_entity_attachment_filename(self, entity):
        """Return the filename of the attachment for the given entity.
        Raise KeyError if no attachment.
        """
        return list(entity['_attachments'].keys())[0]

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

    def get_account(self, email):
        """Get the account identified by the email address.
        Raise ValueError if no such account.
        """
        try:
            return self.get_entity_view('account/email', email.strip().lower())
        except tornado.web.HTTPError:
            raise ValueError("Sorry, no such account: '%s'" % email)

    def get_account_order_count(self, email):
        "Get the number of orders for the account."
        email = email.strip().lower()
        view = self.db.view('order/owner',
                            startkey=[email],
                            endkey=[email, constants.CEILING])
        try:
            return list(view)[0].value
        except IndexError:
            return 0

    def get_account_groups(self, email):
        "Get sorted list of all groups which the account is a member of."
        email = email.strip().lower()
        view = self.db.view('group/member', include_docs=True)
        return sorted([r.doc for r in view[email]],
                      key=lambda i: i['name'])

    def get_account_colleagues(self, email):
        """Return the set of all emails for colleagues of the account;
        members of groups which the account is a member of."""
        result = set()
        for group in self.get_account_groups(email):
            result.update(group['members'])
        return result

    def get_invitations(self, email):
        "Get the groups the account with the given email has been invited to."
        view = self.db.view('group/invited', include_docs=True)
        email = email.strip().lower()
        return [r.doc for r in view[email]]

    def is_colleague(self, email):
        """Is the user with the given email address
        in the same group as the current user?"""
        if not self.current_user: return False
        return self.current_user['email'] in self.get_account_colleagues(email)

    def get_account_names(self, emails=[]):
        """Get dictionary with emails as key and names (last, first) as value.
        If emails is None, then for all accounts."""
        result = {}
        view = self.db.view('account/email')
        if emails:
            for email in emails:
                try:
                    value = list(view[email.strip().lower()])[0].value
                except IndexError:
                    name = '[unknown]'
                else:
                    name = utils.get_account_name(value=value)
                result[email] = name
        else:
            for row in view:
                result[row.key] = utils.get_account_name(value=row.value)
        return result

    def get_forms_titles(self, all=False):
        "Get form titles lookup for iuid, all or only the enabled+disabled."
        view = self.db.view('form/modified', include_docs=not all)
        if all:
            return dict([(r.id, r.value) for r in view])
        else:
            return dict([(r.id, r.value) for r in view
                         if r.doc['status'] in 
                         (constants.ENABLED, constants.DISABLED)])

    def get_logs(self, iuid, limit=settings['DISPLAY_DEFAULT_MAX_LOG']+1):
        "Return the event log documents for the given entity iuid."
        kwargs = dict(include_docs=True,
                      startkey=[iuid, constants.CEILING],
                      endkey=[iuid],
                      descending=True)
        if limit > 0:
            kwargs['limit'] = limit
        view = self.db.view('log/entity', **kwargs)
        logs = [r.doc for r in view]
        # Ref to entity in DB is not needed in each log entry.
        for log in logs:
            log['iuid'] = log.pop('_id')
            log.pop('_rev')
            log.pop('orderportal_doctype')
            log.pop('entity')
        return logs

    def delete_logs(self, iuid):
        "Delete the event log documents for the given entity iuid."
        view = self.db.view('log/entity',
                            startkey=[iuid],
                            endkey=[iuid, constants.CEILING])
        for row in view:
            del self.db[row.id]


class ApiV1Mixin(object):
    "Mixin containing some API methods; JSON generation."

    def cleanup(self, doc):
        "Change _id to iuid and remove _id."
        doc['iuid'] = doc.pop('_id')
        del doc['_rev']

    def get_json_body(self):
        "Return the body of the request interpreted as JSON."
        content_type = self.request.headers.get('Content-Type', '')
        if content_type.startswith(constants.JSON_MIME):
            return json.loads(self.request.body)
        else:
            return {}

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when API."
        pass
