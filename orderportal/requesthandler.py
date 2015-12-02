"OrderPortal: RequestHandler subclass."

from __future__ import print_function, absolute_import

import functools
import logging
import urllib

import couchdb
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
        try:
            self.global_modes = self.db['global_modes']
        except couchdb.ResourceNotFound:
            self.global_modes = constants.DEFAULT_GLOBAL_MODES.copy()

    def get_template_namespace(self):
        "Set the variables accessible within the template."
        result = super(RequestHandler, self).get_template_namespace()
        result['version'] = orderportal.__version__
        result['settings'] = settings
        result['constants'] = constants
        result['global_modes'] = self.global_modes
        result['absolute_reverse_url'] = self.absolute_reverse_url
        result['functools'] = functools
        result['is_staff'] = self.is_staff()
        result['is_admin'] = self.is_admin()
        result['error'] = self.get_argument('error', None)
        result['message'] = self.get_argument('message', None)
        result['infos'] = [r.value for r in self.db.view('info/menu')]
        result['files'] = [r.value for r in self.db.view('file/menu')]
        result['texts'] = [r.key for r in self.db.view('text/name')]
        return result

    def see_other(self, name, *args, **query):
        """Redirect to the absolute URL given by name
        using HTTP status 303 See Other."""
        url = self.absolute_reverse_url(name, *args, **query)
        self.redirect(url, status=303)

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
        """Get the currently logged-in user account, if any.
        This overrides a tornado function, otherwise it should have
        been called get_current_account, since terminology 'account'
        is used in this code rather than 'user'."""
        email = self.get_secure_cookie(
            constants.USER_COOKIE,
            max_age_days=settings['LOGIN_MAX_AGE_DAYS'])
        if not email:
            return None
        try:
            account = self.get_account(email)
        except tornado.web.HTTPError:
            return None
        # Check that account is enabled.
        if account.get('status') != constants.ENABLED:
            logging.warning("account %s not enabled", email)
            return None
        # Check if login session is invalidated.
        if account.get('login') is None:
            logging.warning("account %s has no login session", email)
            return None
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
            raise tornado.web.HTTPError(403,
                                        reason="you do not have role 'admin'")

    def check_staff(self):
        "Check if current user is staff or admin."
        if not self.is_staff():
            raise tornado.web.HTTPError(403,
                                        reason="you do not have role 'staff'")

    def get_next_number(self, doctype):
        "Get the next number for the doctype and increment the counter."
        while True:
            doc = self.db[doctype] # Doc must be reloaded each iteration
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

    def get_news(self):
        "Get all news items in descending 'modified' order."
        view = self.db.view('news/modified', include_docs=True)
        news = [r.doc for r in view]
        # Fill in date from modified, if not explicit
        for new in news:
            if not new.get('date'):
                new['date'] = new['modified'].split('T')[0]
        news.sort(lambda i,j:cmp(i['date'],j['date']), reverse=True)
        return news

    def get_events(self):
        "Get all events items in descending 'date' order."
        view = self.db.view('event/date', include_docs=True)
        return [r.doc for r in view]

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

    def get_page(self, view=None, count=0):
        "Return the list paging parameters in a dictionary."
        try:
            count = list(view)[0].value
        except (TypeError, IndexError):
            pass
        result = dict(count=count)
        if self.current_user:
            result['size'] = self.current_user.get('page_size')
        if not result.get('size'):
            result['size'] = constants.DEFAULT_PAGE_SIZE
        result['max_page'] = (count - 1) / result['size']
        try:
            result['current'] = max(0,
                                    min(int(self.get_argument('page', 0)),
                                        result['max_page']))
        except (ValueError, TypeError):
            result['current'] = 0
        result['start'] = result['current'] * result['size']
        result['end'] = min(result['start'] + result['size'], count)
        return result

    def get_account(self, email):
        """Get the account identified by the email address.
        Raise HTTP 404 if no such account.
        """
        return self.get_entity_view('account/email',
                                    email,
                                    reason='no such account')

    def get_account_order_count(self, email):
        "Get the number of orders for the account."
        view = self.db.view('order/owner',
                            startkey=[email],
                            endkey=[email, constants.CEILING])
        try:
            return list(view)[0].value
        except IndexError:
            return 0

    def get_account_groups(self, email):
        "Get sorted list of all groups which the account is a member of."
        view = self.db.view('group/member', include_docs=True)
        return sorted([r.doc for r in view[email]],
                      cmp=lambda i,j: cmp(i['name'], j['name']))

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
        return [r.doc for r in view[email]]

    def is_colleague(self, email):
        """Is the user with the given email address
        in the same group as the current user?"""
        if not self.current_user: return False
        return self.current_user['email'] in self.get_account_colleagues(email)

    def get_account_names(self, emails):
        "Get the names (first + last) of the persons for the emails."
        result = {}
        view = self.db.view('account/email')
        for email in emails:
            try:
                names = list(view[email])[0].value
            except IndexError:
                pass
            else:
                result[email] = ' '.join([n for n in names if n])
        return result

    def get_logs(self, iuid, limit=constants.DEFAULT_MAX_DISPLAY_LOG+1):
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
