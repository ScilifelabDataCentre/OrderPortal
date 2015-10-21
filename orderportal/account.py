"OrderPortal: Account and login pages."

from __future__ import print_function, absolute_import

import logging

import tornado.web

import orderportal
from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils
from orderportal.group import GroupSaver
from orderportal.requesthandler import RequestHandler


class AccountSaver(saver.Saver):
    doctype = constants.ACCOUNT

    def set_email(self, email):
        assert self.get('email') is None
        if not email: raise ValueError('no email given')
        if not constants.EMAIL_RX.match(email):
            raise ValueError('invalid email value')
        if len(list(self.db.view('account/email', key=email))) > 0:
            raise ValueError('email already in use')
        self['email'] = email.lower()

    def erase_password(self):
        self['password'] = None

    def set_password(self, new):
        self.check_password(new)
        self['code'] = None
        # Bypass ordinary 'set'; avoid logging password, even if hashed.
        self.doc['password'] = utils.hashed_password(new)
        self.changed['password'] = '******'

    def check_password(self, password):
        if password is None: return
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            raise tornado.web.HTTPError(400, reason='invalid password')

    def reset_password(self):
        "Invalidate any previous password and set activation code."
        self.erase_password()
        self['code'] = utils.get_iuid()


class Accounts(RequestHandler):
    """Accounts list page.
    Handles filtering by university, role and status.
    Handles sort by email, name and login."""

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        params = dict()
        # Filter list
        university = self.get_argument('university', '')
        if university == '[other]':
            view = self.db.view('account/email', include_docs=True)
            accounts = [r.doc for r in view]
            accounts = [u for u in accounts
                     if u['university'] not in settings['UNIVERSITY_LIST']]
            params['university'] = university
        elif university:
            view = self.db.view('account/university',
                                key=university,
                                include_docs=True)
            accounts = [r.doc for r in view]
            params['university'] = university
        else:
            accounts = None
        role = self.get_argument('role', '')
        if role:
            if accounts is None:
                view = self.db.view('account/role',
                                    key=role,
                                    include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [u for u in accounts if u['role'] == role]
            params['role'] = role
        status = self.get_argument('status', '')
        if status:
            if accounts is None:
                view = self.db.view('account/status',
                                    key=status,
                                    include_docs=True)
                accounts = [r.doc for r in view]
            else:
                accounts = [u for u in accounts if u['status'] == status]
            params['status'] = status
        # No filter; all accounts
        if accounts is None:
            view = self.db.view('account/email', include_docs=True)
            accounts = [r.doc for r in view]
        # Order; different default depending on sort key
        try:
            value = self.get_argument('descending')
            if value == '': raise ValueError
            descending = utils.to_bool(value)
        except (tornado.web.MissingArgumentError, TypeError, ValueError):
            descending = None
        else:
            params['descending'] = str(descending).lower()
        # Sort list
        sort = self.get_argument('sort', '').lower()
        if sort == 'login':
            if descending is None: descending = True
            accounts.sort(lambda i, j: cmp(i.get('login'), j.get('login')),
                       reverse=descending)
        elif sort == 'modified':
            if descending is None: descending = True
            accounts.sort(lambda i, j: cmp(i['modified'], j['modified']),
                       reverse=descending)
        elif sort == 'name':
            if descending is None: descending = False
            accounts.sort(lambda i, j: cmp((i['last_name'], i['first_name']),
                                        (j['last_name'], j['first_name'])),
                       reverse=descending)
        elif sort == 'email':
            if descending is None: descending = False
            accounts.sort(lambda i, j: cmp(i['email'], j['email']),
                       reverse=descending)
        # Default: name
        else:
            if descending is None: descending = False
            accounts.sort(lambda i, j: cmp((i['last_name'], i['first_name']),
                                        (j['last_name'], j['first_name'])),
                       reverse=descending)
        if sort:
            params['sort'] = sort
        # Page
        page_size = self.current_user.get('page_size') or constants.DEFAULT_PAGE_SIZE
        count = len(accounts)
        max_page = (count - 1) / page_size
        try:
            page = int(self.get_argument('page', 0))
            page = max(0, min(page, max_page))
        except (ValueError, TypeError):
            page = 0
        start = page * page_size
        end = min(start + page_size, count)
        accounts = accounts[start : end]
        params['page'] = page
        # Number of orders per account
        view = self.db.view('order/owner_count', group=True)
        for account in accounts:
            try:
                account['order_count'] = list(view[account['email']])[0].value
            except IndexError:
                account['order_count'] = 0
        #
        self.render('accounts.html',
                    accounts=accounts,
                    params=params,
                    start=start+1,
                    end=end,
                    max_page=max_page,
                    count=count)


class AccountMixin(object):
    "Mixin for various useful methods."

    def is_readable(self, account):
        "Is the account readable by the current user?"
        if self.is_owner(account): return True
        if self.is_staff(): return True
        if self.is_colleague(account['email']): return True
        return False

    def check_readable(self, account):
        "Check that the account is readable by the current user."
        if self.is_readable(account): return
        raise tornado.web.HTTPError(403, reason='you may not read the account')

    def is_editable(self, account):
        "Is the account editable by the current user?"
        if self.is_owner(account): return True
        if self.is_staff(): return True
        return False

    def check_editable(self, account):
        "Check that the account is editable by the current user."
        if self.is_readable(account): return
        raise tornado.web.HTTPError(403, reason='you may not edit the account')


class Account(AccountMixin, RequestHandler):
    "Account page."

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        self.check_readable(account)
        view = self.db.view('order/owner_count', group=True)
        try:
            account['order_count'] = list(view[email])[0].value
        except IndexError:
            account['order_count'] = 0
        view = self.db.view('log/account',
                            startkey=[email, constants.HIGH_CHAR],
                            lastkey=[email],
                            descending=True,
                            limit=1)
        try:
            latest_edit = list(view)[0].key[1]
        except IndexError:
            latest_edit = None
        if self.is_staff() or self.current_user['email'] == account['email']:
            invitations = self.get_invitations(account['email'])
        else:
            invitations = []
        self.render('account.html',
                    account=account,
                    groups=self.get_account_groups(email),
                    latest_edit=latest_edit,
                    invitations=invitations,
                    is_deletable=self.is_deletable(account))

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(email)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, email):
        "Delete a account that is pending; to get rid of spam application."
        account = self.get_account(email)
        self.check_admin()
        if not self.is_deletable(account):
            raise tornado.web.HTTPError(403, reason='account cannot be deleted')
        # Delete the groups this account owns.
        view = self.db.view('group/owner',
                            include_docs=True,
                            key=email)
        for row in view:
            group = row.doc
            self.delete_logs(group['_id'])
            self.db.delete(group)
        # Remove this account from groups it is a member of.
        view = self.db.view('group/owner',
                            include_docs=True,
                            key=email)
        for row in view:
            group = row.doc
            with GroupSaver(doc=row, rqh=self) as saver:
                members = set(group['members'])
                members.discard(email)
                saver['members'] = sorted(members)
        # Delete the messages of the account.
        view = self.db.view('message/recipient',
                            include_docs=True,
                            startkey=[email],
                            endkey=[email, constants.HIGH_CHAR])
        for row in view:
            message = row.doc
            self.delete_logs(message['_id'])
            self.db.delete(message)
        # Delete the logs of the account.
        self.delete_logs(account['_id'])
        # Delete the account itself.
        self.db.delete(account)
        self.see_other('accounts')

    def is_deletable(self, account):
        "Can the account be deleted? Pending, or disabled and no orders."
        if account['status'] == constants.PENDING: return True
        if account['status'] == constants.ENABLED: return False
        view = self.db.view('order/owner', key=account['email'], limit=1)
        if len(list(view)) == 0: return True
        return False


class AccountCurrent(RequestHandler):
    "Redirect to the account page for the current user."

    @tornado.web.authenticated
    def get(self):
        self.see_other('account', self.current_user['email'])


class AccountLogs(AccountMixin, RequestHandler):
    "Account log entries page."

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        self.check_readable(account)
        self.render('logs.html',
                    entity=account,
                    logs=self.get_logs(account['_id']))


class AccountMessages(AccountMixin, RequestHandler):
    "Account messages list page."

    @tornado.web.authenticated
    def get(self, email):
        "Show list of messages sent to the account given by email address."
        account = self.get_account(email)
        self.check_readable(account)
        view = self.db.view('message/recipient',
                            include_docs=True,
                            descending=True,
                            startkey=[account['email'], constants.HIGH_CHAR],
                            endkey=[account['email']])
        messages = [r.doc for r in view]
        self.render('account_messages.html',
                    account=account,
                    messages=messages)


class AccountEdit(AccountMixin, RequestHandler):
    "Page for editing account information."

    @tornado.web.authenticated
    def get(self, email):
        account = self.get_account(email)
        self.check_editable(account)
        self.render('account_edit.html', account=account)

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_editable(account)
        with AccountSaver(doc=account, rqh=self) as saver:
            # Only admin may change role of an account.
            if self.is_admin():
                role = self.get_argument('role')
                if role not in constants.ACCOUNT_ROLES:
                    raise tornado.web.HTTPError(404, reason='invalid role')
                saver['role'] = role
            saver['first_name'] = self.get_argument('first_name')
            saver['last_name'] = self.get_argument('last_name')
            university = self.get_argument('university_other', default=None)
            if not university:
                university = self.get_argument('university', default=None)
            saver['university'] = university or 'undefined'
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = self.get_argument('address', default=None)
            saver['invoice_address'] = \
                self.get_argument('invoice_address', default=None)
            if not saver['invoice_address']:
                try:
                    saver['invoice_address'] = \
                        settings['UNIVERSITIES'][saver['university']]['invoice_address']
                except KeyError:
                    pass
            saver['phone'] = self.get_argument('phone', default=None)
            try:
                value = int(self.get_argument('page_size', 0))
                if value <= 1:
                    raise ValueError
            except (ValueError, TypeError):
                saver['page_size'] = None
            else:
                saver['page_size'] = value
            saver['other_data'] = self.get_argument('other_data', default=None)
        self.see_other('account', email)


class Login(RequestHandler):
    "Login to a account account. Set a secure cookie."

    def get(self):
        self.render('login.html', next=self.get_argument('next', None))

    def post(self):
        "Login to a account account. Set a secure cookie."
        self.check_xsrf_cookie()
        try:
            email = self.get_argument('email')
            password = self.get_argument('password')
        except tornado.web.MissingArgumentError:
            raise tornado.web.HTTPError(403, reason='missing email or password')
        try:
            account = self.get_account(email)
        except tornado.web.HTTPError:
            raise tornado.web.HTTPError(404, reason='no such account')
        if not utils.hashed_password(password) == account.get('password'):
            raise tornado.web.HTTPError(400, reason='invalid password')
        if not account.get('status') == constants.ENABLED:
            raise tornado.web.HTTPError(400, reason='disabled account account')
        self.set_secure_cookie(constants.USER_COOKIE, account['email'])
        with AccountSaver(doc=account, rqh=self) as saver:
            saver['login'] = utils.timestamp() # Set login timestamp.
        next = self.get_argument('next', None)
        if next is None:
            self.see_other('home')
        else:
            # Not quite right: should be an absolute URL to redirect.
            # But seems to work anyway.
            self.redirect(next)


class Logout(RequestHandler):
    "Logout; unset the secure cookie, and invalidate login session."

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        self.set_secure_cookie(constants.USER_COOKIE, '')
        self.redirect(self.reverse_url('home'))


class Reset(RequestHandler):
    "Reset the password of a account account."

    def get(self):
        email = self.current_user and self.current_user['email']
        self.render('reset.html', email=email)

    def post(self):
        self.check_xsrf_cookie()
        account = self.get_account(self.get_argument('email'))
        with AccountSaver(doc=account, rqh=self) as saver:
            saver.reset_password()
        self.see_other('password')


class Password(RequestHandler):
    "Set the password of a account account; requires a code."

    def get(self):
        self.render('password.html',
                    title='Set your password',
                    email=self.get_argument('email', default=''),
                    code=self.get_argument('code', default=''))

    def post(self):
        self.check_xsrf_cookie()
        account = self.get_account(self.get_argument('email'))
        if account.get('code') != self.get_argument('code'):
            raise tornado.web.HTTPError(400, reason='invalid email or code')
        password = self.get_argument('password')
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            mgs = "password shorter than {0} characters".format(
                constants.MIN_PASSWORD_LENGTH)
            raise tornado.web.HTTPError(400, reason=msg)
        if password != self.get_argument('confirm_password'):
            msg = 'password not the same! mistyped'
            raise tornado.web.HTTPError(400, reason=msg)
        with AccountSaver(doc=account, rqh=self) as saver:
            saver.set_password(password)
            saver['login'] = utils.timestamp() # Set login session.
        self.set_secure_cookie(constants.USER_COOKIE, account['email'])
        self.redirect(self.reverse_url('home'))
            

class Register(RequestHandler):
    "Register a new account account."

    def get(self):
        self.render('register.html')

    def post(self):
        self.check_xsrf_cookie()
        with AccountSaver(rqh=self) as saver:
            try:
                email = self.get_argument('email', '')
                saver.set_email(email)
            except ValueError, msg:
                raise tornado.web.HTTPError(400, reason=str(msg))
            try:
                saver['first_name'] = self.get_argument('first_name')
                saver['last_name'] = self.get_argument('last_name')
                university = self.get_argument('university_other', default=None)
                if not university:
                    university = self.get_argument('university', default=None)
                    if university == '__none__':
                        university = None
                saver['university'] = university or 'undefined'
            except (tornado.web.MissingArgumentError, ValueError):
                reason = "invalid '{0}' value provided".format(key)
                raise tornado.web.HTTPError(400, reason=reason)
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = self.get_argument('address', default=None)
            saver['invoice_address'] = \
                self.get_argument('invoice_address', default=None)
            if not saver['invoice_address']:
                try:
                    saver['invoice_address'] = \
                        settings['UNIVERSITIES'][saver['university']]['invoice_address']
                except KeyError:
                    pass
            saver['phone'] = self.get_argument('phone', default=None)
            saver['owner'] = email
            saver['role'] = constants.USER
            saver['status'] = constants.PENDING
            saver.erase_password()
        self.see_other('home',
                       message='An activation email will be sent to you'
                       ' from the administrator when your account is enabled.')


class AccountEnable(RequestHandler):
    "Enable the account; from status pending or disabled."


    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.ENABLED
            saver.reset_password()
        self.see_other('account', email)


class AccountDisable(RequestHandler):
    "Disable the account; from status pending or enabled."

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        account = self.get_account(email)
        self.check_admin()
        with AccountSaver(account, rqh=self) as saver:
            saver['status'] = constants.DISABLED
            saver.erase_password()
        self.see_other('account', email)
