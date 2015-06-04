"OrderPortal: User and login pages."

from __future__ import unicode_literals, print_function, absolute_import

import tornado.web

import orderportal
from orderportal import constants
from orderportal import settings
from orderportal import utils
from orderportal import saver
from orderportal.requesthandler import RequestHandler


class UserSaver(saver.Saver):
    doctype = constants.USER

    def erase_password(self):
        self['password'] = None

    def set_password(self, new):
        self.check_password(new)
        self['code'] = None
        # Bypass ordinary 'set'; avoid logging password, even if hashed.
        self.doc['password'] = utils.hashed_password(new)

    def check_password(self, password):
        if password is None: return
        if len(password) < constants.MIN_PASSWORD_LENGTH:
            raise tornado.web.HTTPError(400, reason='invalid password')

    def reset_password(self):
        "Invalidate any previous password and set activation code."
        self.erase_password()
        self['code'] = utils.get_iuid()


class Users(RequestHandler):
    "Users list page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view('user/email', include_docs=True)
        users = [self.get_presentable(r.doc) for r in view]
        self.render('users.html', title='Users', users=users)


class User(RequestHandler):
    "User page."

    @tornado.web.authenticated
    def get(self, email):
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        self.render('user.html',
                    title="User {0}".format(user['email']),
                    user=user,
                    logs=self.get_logs(user['_id']))

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        if self.get_argument('_http_method', None) == 'delete':
            self.delete(email)
            return
        raise tornado.web.HTTPError(405, reason='POST only allowed for DELETE')

    @tornado.web.authenticated
    def delete(self, email):
        "Delete a user that is pending; to get rid of spam application."
        user = self.get_user(email)
        self.check_admin()
        if user['status'] != constants.PENDING:
            raise tornado.web.HTTPError(
                403, reason='only pending user can be deleted')
        self.delete_logs(user['_id'])
        self.db.delete(user)
        self.see_other(self.reverse_url('home'))


class UserLogs(RequestHandler):
    "User log entries page."

    @tornado.web.authenticated
    def get(self, email):
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        self.render('logs.html',
                    title="Logs for user '{}'".format(user['email']),
                    entity=user,
                    logs=self.get_logs(user['_id']))


class UserEdit(RequestHandler):
    "Page for editing user information."

    @tornado.web.authenticated
    def get(self, email):
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        self.render('user_edit.html',
                    title="Edit user '{}'".format(user['email']),
                    user=user)

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        user = self.get_user(email)
        self.check_owner_or_staff(user)
        with UserSaver(doc=user, rqh=self) as saver:
            saver['first_name'] = self.get_argument('first_name')
            saver['last_name'] = self.get_argument('last_name')
            saver['university'] = self.get_argument('university')
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = self.get_argument('address', default=None)
            saver['phone'] = self.get_argument('phone', default=None)
        self.see_other(self.reverse_url('user', email))


class Login(RequestHandler):
    "Login to a user account. Set a secure cookie."

    def post(self):
        "Login to a user account. Set a secure cookie."
        self.check_xsrf_cookie()
        try:
            email = self.get_argument('email')
            password = self.get_argument('password')
        except tornado.web.MissingArgumentError:
            raise tornado.web.HTTPError(403, reason='missing email or password')
        try:
            user = self.get_user(email)
        except tornado.web.HTTPError:
            raise tornado.web.HTTPError(404, reason='no such user')
        if not utils.hashed_password(password) == user.get('password'):
            raise tornado.web.HTTPError(400, reason='invalid password')
        if not user.get('status') == constants.ENABLED:
            raise tornado.web.HTTPError(400, reason='disabled user account')
        self.set_secure_cookie(constants.USER_COOKIE, user['email'])
        with UserSaver(doc=user, rqh=self) as saver:
            saver['login'] = utils.timestamp() # Set login timestamp.
        self.redirect(self.reverse_url('home'))


class Logout(RequestHandler):
    "Logout; unset the secure cookie, and invalidate login session."

    @tornado.web.authenticated
    def post(self):
        self.check_xsrf_cookie()
        self.set_secure_cookie(constants.USER_COOKIE, '')
        self.redirect(self.reverse_url('home'))


class Reset(RequestHandler):
    "Reset the password of a user account."

    SUBJECT = "The password for your {} portal account has been reset"
    TEXT = """The password for your account {} in the {} portal has been reset.
Please got to {} to set your password.
The code required to set your password is "{}".
"""

    def get(self):
        email = self.current_user and self.current_user.get('email')
        self.render('reset.html', email=email, title='Reset your password')

    def post(self):
        self.check_xsrf_cookie()
        user = self.get_user(self.get_argument('email'))
        with UserSaver(doc=user, rqh=self) as saver:
            saver.reset_password()
            saver['login'] = None # Invalidate login session.
        url = self.absolute_reverse_url('password',
                                        email=user['email'],
                                        code=user['code'])
        self.send_email(user['email'],
                        self.SUBJECT.format(settings['FACILITY_NAME']),
                        self.TEXT.format(user['email'],
                                         settings['FACILITY_NAME'],
                                         url,
                                         user['code']))
        self.see_other(self.reverse_url('password'))


class Password(RequestHandler):
    "Set the password of a user account; requires a code."

    def get(self):
        self.render('password.html',
                    title='Set your password',
                    email=self.get_argument('email', default=''),
                    code=self.get_argument('code', default=''))

    def post(self):
        self.check_xsrf_cookie()
        user = self.get_user(self.get_argument('email'))
        if user.get('code') != self.get_argument('code'):
            raise tornado.web.HTTPError(400, reason='invalid email or code')
        password = self.get_argument('password')
        if password != self.get_argument('confirm_password'):
            raise tornado.web.HTTPError(400, reason='passwords not the same')
        with UserSaver(doc=user, rqh=self) as saver:
            saver.set_password(password)
            saver['login'] = utils.timestamp() # Set login session.
        self.set_secure_cookie(constants.USER_COOKIE, user['email'])
        self.redirect(self.reverse_url('home'))
            

class Register(RequestHandler):
    "Register a new user account."

    def post(self):
        self.check_xsrf_cookie()
        with UserSaver(rqh=self) as saver:
            try:
                email = self.get_argument('email')
                if not email: raise ValueError
                if not constants.EMAIL_RX.match(email): raise ValueError
                try:
                    self.get_user(email)
                except tornado.web.HTTPError:
                    pass
                else:
                    reason = 'email address already in use'
                    raise tornado.web.HTTPError(409, reason=reason)
                saver['email'] = email
                saver['first_name'] = self.get_argument('first_name')
                saver['last_name'] = self.get_argument('last_name')
                saver['university'] = self.get_argument('university')
            except (tornado.web.MissingArgumentError, ValueError):
                reason = "invalid {} value provided".format(key)
                raise tornado.web.HTTPError(400, reason=reason)
            saver['department'] = self.get_argument('department', default=None)
            saver['address'] = self.get_argument('address', default=None)
            saver['phone'] = self.get_argument('phone', default=None)
            saver['owner'] = email
            saver['role'] = constants.USER
            saver['status'] = constants.PENDING
            saver.erase_password()
        self.see_other(self.reverse_url('password'))


class UserEnable(RequestHandler):
    "Enable the user; from status pending or disabled."

    SUBJECT = "Your {} portal account has been enabled"
    TEXT = """Your account {} in the {} portal has been enabled.
Please got to {} to set your password.
"""

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        user = self.get_user(email)
        self.check_admin()
        with UserSaver(user, rqh=self) as saver:
            saver['code'] = utils.get_iuid()
            saver['status'] = constants.ENABLED
            saver.erase_password()
        url = self.absolute_reverse_url('password',
                                        email=email,
                                        code=user['code'])
        self.send_email(user['email'],
                        self.SUBJECT.format(settings['FACILITY_NAME']),
                        self.TEXT.format(email, settings['FACILITY_NAME'], url))
        self.see_other(self.reverse_url('user', email))


class UserDisable(RequestHandler):
    "Disable the user; from status pending or enabled."

    @tornado.web.authenticated
    def post(self, email):
        self.check_xsrf_cookie()
        user = self.get_user(email)
        self.check_admin()
        with UserSaver(user, rqh=self) as saver:
            saver['status'] = constants.DISABLED
            saver.erase_password()
        self.see_other(self.reverse_url('user', email))
