"RequestHandler subclass for all pages."

import base64
import json
import logging
import traceback
import urllib.request
import urllib.error
import urllib.parse

import couchdb2
import tornado.web

from orderportal import constants, settings
from orderportal import utils
import orderportal.database


class RequestHandler(tornado.web.RequestHandler):
    "Base request handler."

    def prepare(self):
        "Get the database connection and logger."
        self.db = orderportal.database.get_db()
        self.logger = logging.getLogger("orderportal")

    def get_template_namespace(self):
        "Set the items accessible within the template."
        result = super().get_template_namespace()
        result["constants"] = constants
        result["settings"] = settings
        result["terminology"] = utils.terminology
        result["absolute_reverse_url"] = self.absolute_reverse_url
        result["order_reverse_url"] = self.order_reverse_url
        result["am_staff"] = self.am_staff()
        result["am_admin"] = self.am_admin()
        result["error"] = urllib.parse.unquote_plus(self.get_cookie("error", ""))
        self.clear_cookie("error")
        result["message"] = urllib.parse.unquote_plus(self.get_cookie("message", ""))
        self.clear_cookie("message")
        result["infos"] = [r.value for r in self.db.view("info", "menu")]
        try:
            doc = self.get_entity_view("text", "name", "alert")
        except tornado.web.HTTPError:
            result["alert"] = None
        else:
            result["alert"] = utils.markdown2html(doc["text"])
        result["action_required"] = []
        if self.current_user:
            if self.current_user.get("update_info"):
                result["action_required"].append(
                    "You have have been requested to review and update your account information.."
                )
            if settings["ACCOUNT_ORCID_INFO"] and settings["ACCOUNT_ORCID_REQUIRED"]:
                if not self.current_user.get("orcid"):
                    result["action_required"].append(
                        "You must provide your ORCID in your account information."
                    )
            if result["am_staff"]:
                if list(
                    self.db.view("report", "review", key=self.current_user["email"])
                ):
                    result["action_required"].append(
                        "You have order report reviews to finish."
                    )
            if self.get_invitations(self.current_user["email"]):
                result["action_required"].append("You have invitations to group(s).")
        return result

    def see_other(self, name, *args, **kwargs):
        "Redirect to the absolute URL given by name using HTTP status 303 See Other."
        query = kwargs.copy()
        try:
            self.set_error_flash(str(query.pop("error")))
        except KeyError:
            pass
        try:
            self.set_message_flash(str(query.pop("message")))
        except KeyError:
            pass
        self.redirect(self.absolute_reverse_url(name, *args, **query), status=303)

    def absolute_reverse_url(self, name, *args, **query):
        "Get the absolute URL given the handler name, arguments and query."
        if name is None:
            path = settings["BASE_URL_PATH_PREFIX"] or ""
        else:
            path = self.reverse_url(name, *args, **query)
        return settings["BASE_URL"].rstrip("/") + path

    def reverse_url(self, name, *args, **query):
        "Allow adding query arguments to the URL."
        url = super().reverse_url(name, *args)
        url = url.rstrip("?")  # tornado bug? left-over '?' sometimes
        if settings["BASE_URL_PATH_PREFIX"]:
            url = settings["BASE_URL_PATH_PREFIX"] + url
        if query:
            query = dict([(k, str(v)) for k, v in list(query.items())])
            url += "?" + urllib.parse.urlencode(query)
        return url

    def static_url(self, path, include_host=None, **kwargs):
        "Returns the URL for a static resource."
        url = super().static_url(path, include_host=include_host, **kwargs)
        if settings["BASE_URL_PATH_PREFIX"]:
            parts = urllib.parse.urlparse(url)
            path = settings["BASE_URL_PATH_PREFIX"] + parts.path
            parts = (parts[0], parts[1], path, parts[3], parts[4], parts[5])
            url = urllib.parse.urlunparse(parts)
        return url

    def order_reverse_url(self, order, api=False, **query):
        "URL for order; use identifier variant if available. Always absolute."
        URL = self.absolute_reverse_url
        try:
            identifier = order["identifier"]
        except KeyError:
            identifier = order["_id"]
        if api:
            return URL("order_api", identifier, **query)
        else:
            return URL("order", identifier, **query)

    def set_message_flash(self, message):
        "Set message flash cookie."
        if message:
            self.set_flash("message", str(message))

    def set_error_flash(self, message):
        "Set error flash cookie message."
        if message:
            self.set_flash("error", str(message))

    def set_flash(self, name, message):
        message = urllib.parse.quote_plus(message)
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
        if account.get("status") == constants.DISABLED:
            self.logger.info("Account %s DISABLED", account["email"])
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
                account = self.get_entity_view("account", "api_key", api_key)
            except tornado.web.HTTPError:
                raise ValueError
            self.logger.info("API key login: account %s", account["email"])
            return account

    def get_current_user_session(self):
        """Get the current user from a secure login session cookie.
        Raise ValueError if no or erroneous authentication.
        """
        email = self.get_secure_cookie(
            constants.USER_COOKIE, max_age_days=settings["LOGIN_MAX_AGE_DAYS"]
        )
        if not email:
            raise ValueError
        email = email.decode("utf-8")
        account = self.get_account(email)
        # Check if login session is invalidated.
        if account.get("login") is None:
            raise ValueError
        self.logger.debug("Session authentication: %s", account["email"])
        return account

    def get_current_user_basic(self):
        """Get the current user by HTTP Basic authentication.
        This should be used only if the site is using TLS (SSL, https).
        Raise ValueError if no or erroneous authentication.
        """
        try:
            auth = self.request.headers["Authorization"]
        except KeyError:
            raise ValueError
        try:
            auth = auth.split()
            if auth[0].lower() != "basic":
                raise ValueError
            auth = base64.b64decode(auth[1])
            email, password = auth.split(":", 1)
            account = self.get_account(email, password=password)
        except (IndexError, ValueError, TypeError):
            raise ValueError
        self.logger.debug("Basic auth login: account %s", account["email"])
        return account

    def am_owner(self, entity):
        "Does the current user own the given entity?"
        return self.current_user and entity["owner"] == self.current_user["email"]

    def am_admin(self):
        "Is the current user admin?"
        # Not a property, since the above is not.
        return self.current_user and self.current_user["role"] == constants.ADMIN

    def am_staff(self):
        "Is the current user staff or admin?"
        # Not a property, since the above is not.
        return self.current_user and self.current_user["role"] in (
            constants.STAFF,
            constants.ADMIN,
        )

    def check_admin(self):
        "Check if current user is admin."
        if not self.am_admin():
            raise tornado.web.HTTPError(403, reason="Role 'admin' is required.")

    def check_staff(self):
        "Check if current user is staff or admin."
        if not self.am_staff():
            raise tornado.web.HTTPError(
                403, reason="Role 'admin' or 'staff' is required."
            )

    def check_login(self):
        "Check if logged in."
        if not self.current_user:
            raise tornado.web.HTTPError(403, reason="Must be logged in.")

    def get_admins(self):
        "Get the list of enabled admin accounts."
        view = self.db.view("account", "role", key=constants.ADMIN, include_docs=True)
        admins = [row.doc for row in view]
        return [a for a in admins if a["status"] == constants.ENABLED]

    def get_next_counter(self, doctype):
        "Get the next counter number for the doctype."
        from orderportal.admin import MetaSaver  # To avoid circular import.

        while True:
            try:
                doc = self.db[doctype]  # Doc must be reloaded each iteration
            except couchdb2.NotFoundError:
                with MetaSaver(handler=self) as saver:
                    saver.set_id(doctype)
                doc = saver.doc
            try:
                number = doc["counter"] + 1
            except KeyError:
                if doctype == constants.ORDER:
                    number = settings["ORDER_IDENTIFIER_FIRST"]
                else:
                    number = 1
            doc["counter"] = number
            self.db.put(doc)
            return number

    def get_entity(self, iuid, doctype=None):
        """Get the entity by the IUID. Check the doctype, if given.
        Raise HTTP 404 if no such entity.
        """
        try:
            entity = self.db[iuid]
            if doctype is not None and entity[constants.DOCTYPE] != doctype:
                raise KeyError
        except (couchdb2.NotFoundError, KeyError):
            raise tornado.web.HTTPError(404, reason="Sorry, no such entity.")
        return entity

    def get_entity_view(
        self, designname, viewname, key, reason="Sorry, no such entity."
    ):
        """Get the entity by the view name and the key.
        Raise HTTP 404 if no such entity.
        """
        view = self.db.view(
            designname, viewname, key=key, reduce=False, include_docs=True
        )
        result = list(view)
        if len(result) == 1:
            return result[0].doc
        else:
            raise tornado.web.HTTPError(404, reason=reason)

    def get_order(self, identifier_iuid):
        "Get the order for the identifier or IUID."
        try:  # First try order identifier.
            order = self.get_entity_view("order", "identifier", identifier_iuid)
        except tornado.web.HTTPError:
            # Next try order doc IUID.
            order = self.get_entity(identifier_iuid, doctype=constants.ORDER)
        return order

    def get_form(self, iuid):
        "Get the form given by its IUID."
        return self.get_entity(iuid, doctype=constants.FORM)

    def lookup_form(self, iuid):
        """Lookup the form by its IUID. When called the first time,
        set up a cached dictionary 'lookup_forms' containing all forms.
        """
        try:
            return self.lookup_forms.get(iuid)
        except AttributeError:
            view = self.db.view("form", "modified", descending=True, include_docs=True)
            self.lookup_forms = dict([(row.id, row.doc) for row in view])
            return self.lookup_forms.get(iuid)

    def get_report(self, iuid):
        "Get the report for the IUID."
        return self.get_entity(iuid, doctype=constants.REPORT)

    def get_text(self, type, name):
        """Get the requested text by type and name.
        Raise KeyError if not found.
        """
        docs = [
            row.doc
            for row in self.db.view(
                "text", "type", key=type, reduce=False, include_docs=True
            )
        ]
        for doc in docs:
            if doc["name"] == name:
                return doc
        raise KeyError

    def get_news(self, limit=None):
        "Get all news items in descending 'modified' order."
        kwargs = dict(include_docs=True, descending=True)
        if limit is not None:
            kwargs["limit"] = limit
        return [row.doc for row in self.db.view("news", "modified", **kwargs)]

    def get_events(self, upcoming=False):
        "Get all (descending) or upcoming (ascending) events."
        kwargs = dict(include_docs=True)
        if upcoming:
            kwargs["startkey"] = utils.today()
            kwargs["endkey"] = constants.CEILING
        else:
            kwargs["descending"] = True
        return [row.doc for row in self.db.view("event", "date", **kwargs)]

    def get_account(self, email, password=None):
        """Get the account identified by the email address.
        Check the password, if given.
        Raise ValueError if no such account or wrong password.
        """
        try:
            account = self.get_entity_view("account", "email", email.strip().lower())
        except tornado.web.HTTPError:
            raise ValueError(f"Sorry, no such account: '{email}'")
        if password:
            from orderportal.account import hashed_password

            if hashed_password(password) != account.get("password"):
                raise ValueError("Sorry, invalid password.")
        return account

    def get_account_order_count(self, email):
        "Get the number of orders for the account."
        email = email.strip().lower()
        view = self.db.view(
            "order", "owner", startkey=[email], endkey=[email, constants.CEILING]
        )
        try:
            return list(view)[0].value
        except IndexError:
            return 0

    def get_account_groups(self, email):
        "Get sorted list of all groups which the account is a member of."
        email = email.strip().lower()
        view = self.db.view("group", "member", key=email, include_docs=True)
        return sorted([row.doc for row in view], key=lambda i: i["name"])

    def get_account_colleagues(self, email):
        """Return the set of all emails for colleagues of the account;
        members of groups which the account is a member of."""
        result = set()
        for group in self.get_account_groups(email):
            result.update(group["members"])
        return result

    def get_invitations(self, email):
        "Get the groups the account with the given email has been invited to."
        email = email.strip().lower()
        return [
            row.doc
            for row in self.db.view("group", "invited", key=email, include_docs=True)
        ]

    def am_colleague(self, email):
        "Is the user with the email address in the same group as the current user?"
        if not self.current_user:
            return False
        return self.current_user["email"] in self.get_account_colleagues(email)

    def lookup_account_name(self, email):
        """Lookup the name "last, first" of the person for the account.
        Sets up a cached dictionary 'lookup_accounts_names' when called the first time.
        """
        try:
            return self.lookup_accounts_names.get(email) or email
        except AttributeError:
            self.lookup_accounts_names = {}
            for row in self.db.view("account", "email"):
                self.lookup_accounts_names[row.key] = ", ".join(reversed(row.value))
            return self.lookup_accounts_names.get(email) or email

    def get_group(self, iuid):
        "Return the group for the IUID."
        return self.get_entity(iuid, doctype=constants.GROUP)

    def get_logs(self, iuid):
        "Return the event log documents for the given entity iuid."
        view = self.db.view("log", "entity",
                            include_docs=True,
                            startkey=[iuid, constants.CEILING],
                            endkey=[iuid],
                            descending=True)
        logs = [row.doc for row in view]
        # Ref to entity in DB is not needed in each log entry.
        for log in logs:
            log["iuid"] = log.pop("_id")
            log.pop("_rev")
            log.pop("orderportal_doctype")
            log.pop("entity")
        return logs

    def delete_logs(self, iuid):
        "Delete the event log documents for the given entity iuid."
        view = self.db.view(
            "log",
            "entity",
            startkey=[iuid],
            endkey=[iuid, constants.CEILING],
            include_docs=True,
        )
        for row in view:
            self.db.delete(row.doc)


class ApiV1Mixin:
    "Mixin containing some API methods; JSON generation."

    def cleanup(self, doc):
        "Change '_id' to 'iuid' and remove '_rev'."
        doc["iuid"] = doc.pop("_id")
        doc.pop("_rev", None)

    def get_json_body(self):
        "Return the body of the request interpreted as JSON."
        content_type = self.request.headers.get("Content-Type", "")
        if content_type.startswith(constants.JSON_MIMETYPE):
            return json.loads(self.request.body)
        else:
            return {}

    def check_xsrf_cookie(self):
        "Do not check for XSRF cookie when API."
        pass
