"Forms are templates for orders."

import json
import logging

import tornado.web

from . import constants, settings, parameters
from . import saver
from . import utils
from .fields import Fields
from .requesthandler import RequestHandler, ApiV1Mixin


class FormSaver(saver.Saver):
    doctype = constants.FORM

    def initialize(self):
        super(FormSaver, self).initialize()
        self.doc["fields"] = []
        self.doc["ordinal"] = 0

    def setup(self):
        self.fields = Fields(self.doc)

    def add_field(self):
        identifier = self.rqh.get_argument("identifier")
        if not constants.ID_RX.match(identifier):
            raise ValueError("Invalid identifier.")
        if self.rqh.get_argument("type") not in constants.TYPES:
            raise ValueError("Invalid type.")
        if identifier in self.fields:
            raise ValueError("Identifier already exists.")
        self.changed["fields"] = self.fields.add(identifier, self.rqh)

    def update_field(self, identifier):
        if identifier not in self.fields:
            raise ValueError("No such field.")
        self.changed["fields"] = self.fields.update(identifier, self.rqh)

    def clone_fields(self, form):
        "Clone all fields from the given form."
        for field in form["fields"]:
            self.fields.clone(field)
        self.changed["copied"] = "from {0}".format(form["_id"])

    def delete_field(self, identifier):
        if identifier not in self.fields:
            raise ValueError("No such field.")
        self.fields.delete(identifier)
        self.changed["fields"] = dict(identifier=identifier, action="deleted")


class FormMixin(object):
    "Mixin providing various methods."

    def allow_edit_fields(self, form):
        "Are the form fields editable? Checks status only."
        return form["status"] == constants.PENDING

    def check_edit_fields(self, form):
        "Check if the form fields can be edited. Checks status only."
        if not self.allow_edit_fields(form):
            raise ValueError("Form is not editable.")

    def get_order_count(self, form):
        "Return number of orders for the form."
        view = self.db.view(
            "order",
            "form",
            startkey=[form["_id"]],
            endkey=[form["_id"], constants.CEILING],
        )
        try:
            return list(view)[0].value
        except (TypeError, IndexError):
            return 0


class Forms(FormMixin, RequestHandler):
    "Forms list page."

    @tornado.web.authenticated
    def get(self):
        self.check_admin()
        view = self.db.view("form", "modified", descending=True, include_docs=True)
        title = "Recent forms"
        forms = [r.doc for r in view]
        names = self.get_account_names()
        counts = dict([(f["_id"], self.get_order_count(f)) for f in forms])
        self.render(
            "forms.html",
            title=title,
            forms=forms,
            account_names=names,
            order_counts=counts,
        )


class Form(FormMixin, RequestHandler):
    "Form page."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render(
            "form.html",
            form=form,
            order_count=self.get_order_count(form),
            fields=Fields(form),
            allow_delete=self.allow_delete(form),
            allow_edit_fields=self.allow_edit_fields(form),
            logs=self.get_logs(form["_id"]),
        )

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(
            405, reason="Internal problem; POST only allowed for DELETE."
        )

    @tornado.web.authenticated
    def delete(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if not self.allow_delete(form):
            self.see_other("form", form["_id"], error="Form cannot be deleted.")
            return
        self.delete_logs(form["_id"])
        self.db.delete(form)
        self.see_other("forms")

    def allow_delete(self, form):
        "Can the form be deleted?."
        if settings.get("READONLY"):
            raise False
        if form["status"] == constants.PENDING:
            return True
        if form["status"] == constants.ENABLED:
            return False
        if self.get_order_count(form) == 0:
            return True
        return False


class FormApiV1(ApiV1Mixin, Form):
    "Form API; JSON."

    def render(self, templatefilename, **kwargs):
        URL = self.absolute_reverse_url
        form = kwargs["form"]
        data = dict()
        data["type"] = "form"
        data["iuid"] = form["_id"]
        data["title"] = form["title"]
        data["version"] = form.get("version")
        data["description"] = form.get("description")
        data["instruction"] = form.get("instruction")
        data["disclaimer"] = form.get("disclaimer")
        data["owner"] = dict(
            email=form["owner"],
            links=dict(
                api=dict(href=URL("account_api", form["owner"])),
                display=dict(href=URL("account", form["owner"])),
            ),
        )
        data["status"] = form["status"]
        data["modified"] = form["modified"]
        data["created"] = form["created"]
        data["links"] = dict(
            api=dict(href=URL("form_api", form["_id"])),
            display=dict(href=URL("form", form["_id"])),
        )
        data["orders"] = dict(
            count=self.get_order_count(form),
            # XXX Add API href when available.
            display=dict(href=URL("form_orders", form["_id"])),
        )
        data["fields"] = form["fields"]
        self.write(data)


class FormLogs(RequestHandler):
    "Form log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render(
            "logs.html",
            title="Logs for form '{0}'".format(form["title"]),
            entity=form,
            logs=self.get_logs(form["_id"]),
        )


class FormCreate(RequestHandler):
    "Page for creating an form. Allows for importing fields from form JSON."

    @tornado.web.authenticated
    def get(self):
        if self.readonly():
            return
        self.check_admin()
        self.render("form_create.html")

    @tornado.web.authenticated
    def post(self):
        if self.readonly():
            return
        self.check_admin()
        with FormSaver(rqh=self) as saver:
            saver["title"] = self.get_argument("title") or "[no title]"
            saver["version"] = self.get_argument("version", None)
            saver["description"] = self.get_argument("description", None)
            saver["instruction"] = self.get_argument("instruction", None)
            saver["disclaimer"] = self.get_argument("disclaimer", None)
            saver["status"] = constants.PENDING
            try:
                infile = self.request.files["import"][0]
                # This throws exceptions if not JSON
                data = json.loads(infile.body)
                if (
                    data.get(constants.DOCTYPE) != constants.FORM
                    and data.get("type") != "form"
                ):
                    raise ValueError("Imported JSON is not a form.")
            except (KeyError, IndexError):
                pass
            except Exception as msg:
                self.see_other("home", error="Error importing form: %s" % msg)
                return
            else:
                if not saver["version"]:
                    saver["version"] = data.get("version")
                if not saver["description"]:
                    saver["description"] = data.get("description")
                if not saver["instruction"]:
                    saver["instruction"] = data.get("instruction")
                if not saver["disclaimer"]:
                    saver["disclaimer"] = data.get("disclaimer")
                saver["fields"] = data["fields"]
        self.see_other("form", saver.doc["_id"])


class FormEdit(FormMixin, RequestHandler):
    """Page for editing an form; title, version, description,
    instruction, disclaimer."""

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        self.render(
            "form_edit.html", title="Edit form '{0}'".format(form["title"]), form=form
        )

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(doc=form, rqh=self) as saver:
            saver["title"] = self.get_argument("title") or "[no title]"
            saver["version"] = self.get_argument("version", None)
            saver["description"] = self.get_argument("description", None)
            saver["instruction"] = self.get_argument("instruction", None)
            saver["disclaimer"] = self.get_argument("disclaimer", None)
            try:
                saver["ordinal"] = int(self.get_argument("ordinal", 0))
            except (ValueError, TypeError):
                pass
        self.see_other("form", form["_id"])


class FormFieldCreate(FormMixin, RequestHandler):
    "Page for creating a field in a form."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_edit_fields(form)
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
            return
        # Get existing field identifiers
        identifiers = set()
        for row in self.db.view("form", "enabled", include_docs=True):
            identifiers.update(self._get_identifiers(row.doc["fields"]))
        identifiers.difference_update(self._get_identifiers(form["fields"]))
        self.render(
            "field_create.html",
            title="Create field in form '{0}'".format(form["title"]),
            form=form,
            fields=Fields(form),
            identifiers=identifiers,
        )

    def _get_identifiers(self, fields):
        result = set()
        for field in fields:
            result.add(field["identifier"])
            try:
                result.update(self._get_identifiers(field["fields"]))
            except KeyError:
                pass
        return result

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_edit_fields(form)
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
            return
        try:
            with FormSaver(doc=form, rqh=self) as saver:
                saver.add_field()
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
        else:
            self.see_other("form", form["_id"])


class FormFieldEdit(FormMixin, RequestHandler):
    "Page for editing or deleting a field in a form."

    @tornado.web.authenticated
    def get(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_edit_fields(form)
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
            return
        fields = Fields(form)
        try:
            field = fields[identifier]
        except KeyError:
            self.see_other("form", form["_id"], error="No such field.")
            return
        self.render(
            "field_edit.html",
            form=form,
            field=field,
            fields=fields,
            siblings=fields.get_siblings(field, form["fields"]),
            alt_parents=fields.get_alt_parents(field),
        )

    @tornado.web.authenticated
    def post(self, iuid, identifier):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid, identifier)
            return
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_edit_fields(form)
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
            return
        try:
            with FormSaver(doc=form, rqh=self) as saver:
                saver.update_field(identifier)
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
        else:
            self.see_other("form", form["_id"])

    @tornado.web.authenticated
    def delete(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        try:
            self.check_edit_fields(form)
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
            return
        try:
            with FormSaver(doc=form, rqh=self) as saver:
                saver.delete_field(identifier)
        except ValueError as msg:
            self.see_other("form", form["_id"], error=str(msg))
        else:
            self.see_other("form", form["_id"])


class FormFieldEditDescr(FormMixin, RequestHandler):
    """Edit the label, clone erase, description of a form field.
    This is allowed even for enabled forms.
    """

    @tornado.web.authenticated
    def post(self, iuid, identifier):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(doc=form, rqh=self) as saver:
            name = "{0}/label".format(identifier)
            saver.fields[identifier]["label"] = self.get_argument(name, "")
            name = "{0}/initial_display".format(identifier)
            saver.fields[identifier]["initial_display"] = utils.to_bool(
                self.get_argument(name, False)
            )
            name = "{0}/erase_on_clone".format(identifier)
            saver.fields[identifier]["erase_on_clone"] = utils.to_bool(
                self.get_argument(name, False)
            )
            name = "{0}/auto_tag".format(identifier)
            saver.fields[identifier]["auto_tag"] = utils.to_bool(
                self.get_argument(name, False)
            )
            name = "{0}/descr".format(identifier)
            saver.fields[identifier]["description"] = self.get_argument(name, "")
        self.see_other("form", form["_id"])


class FormClone(RequestHandler):
    "Make a clone of a form."

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        with FormSaver(rqh=self) as saver:
            saver["title"] = "Clone of {0}".format(form["title"])
            saver["version"] = form.get("version")
            saver["description"] = form.get("description")
            saver["instruction"] = form.get("instruction")
            saver["disclaimer"] = form.get("disclaimer")
            saver.clone_fields(form)
            saver["status"] = constants.PENDING
        self.see_other("form_edit", saver.doc["_id"])


class FormPending(RequestHandler):
    """Change status from testing to pending.
    To allow editing after testing.
    All test orders for this form are deleted."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form["status"] != constants.TESTING:
            raise ValueError("Form does not have status testing.")
        with FormSaver(doc=form, rqh=self) as saver:
            saver["status"] = constants.PENDING
        view = self.db.view(
            "order",
            "form",
            include_docs=True,
            startkey=[form["_id"]],
            endkey=[form["_id"], constants.CEILING],
        )
        for row in view:
            self.delete_logs(row.id)
            self.db.delete(row.doc)
        self.see_other("form", iuid)


class FormTesting(RequestHandler):
    """Change status from pending to testing.
    To allow testing making orders from the form."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form["status"] != constants.PENDING:
            raise ValueError("Form does not have status pending.")
        with FormSaver(doc=form, rqh=self) as saver:
            saver["status"] = constants.TESTING
        self.see_other("form", iuid)


class FormEnable(RequestHandler):
    """Change status from pending to enabled.
    Allows users to make orders from the form."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form["status"] == constants.PENDING:
            with FormSaver(doc=form, rqh=self) as saver:
                if not form.get("version"):
                    saver["version"] = utils.today()
                saver["status"] = constants.ENABLED
        self.see_other("form", iuid)


class FormDisable(RequestHandler):
    """Change status from enabled to disabled.
    Disable making orders from the form."""

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        form = self.get_entity(iuid, doctype=constants.FORM)
        if form["status"] == constants.ENABLED:
            with FormSaver(doc=form, rqh=self) as saver:
                saver["status"] = constants.DISABLED
        self.see_other("form", iuid)


class FormOrders(RequestHandler):
    "Page for a list of all orders for a given form."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_staff()
        form = self.get_entity(iuid, doctype=constants.FORM)
        view = self.db.view(
            "order",
            "form",
            reduce=False,
            include_docs=True,
            descending=True,
            startkey=[iuid, constants.CEILING],
            endkey=[iuid],
        )
        orders = [r.doc for r in view]
        account_names = self.get_account_names()
        self.render(
            "form_orders.html", form=form, orders=orders, account_names=account_names
        )


class FormOrdersAggregate(RequestHandler):
    "Aggregate data from all orders for the form into a CSV file."

    TITLES = dict(_id="Order IUID", email="Owner email")

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_staff()
        form = self.get_entity(iuid, doctype=constants.FORM)
        fields = Fields(form).flatten()
        # Remove group fields
        fields = [f for f in fields if f["type"] != constants.GROUP]
        # Split out table fields
        table_fields = [f for f in fields if f["type"] == constants.TABLE]
        fields = [f for f in fields if f["type"] != constants.TABLE]
        self.render(
            "form_orders_aggregate.html",
            form=form,
            fields=fields,
            table_fields=table_fields,
        )

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_staff()
        form = self.get_entity(iuid, doctype=constants.FORM)

        order_fields = self.get_arguments("order")
        if not ("iuid" in order_fields or "identifier" in order_fields):
            self.see_other(
                "form_orders_aggregate",
                form["_id"],
                error="IUID or identifier must be included.",
            )
            return
        history_fields = self.get_arguments("history")
        owner_fields = self.get_arguments("owner")
        data_fields = self.get_arguments("fields")
        table_field = self.get_argument("table_field", None)
        if table_field:
            table_field = Fields(form)[table_field]
            colids = [
                utils.parse_field_table_column(c)["identifier"]
                for c in table_field["table"]
            ]

        file_format = self.get_argument("file_format", "xlsx").lower()
        if file_format == "xlsx":
            writer = utils.XlsxWriter("Aggregate")
        elif file_format == "csv":
            writer = utils.CsvWriter()
        else:
            raise tornado.web.HTTPError(404, reason="unknown file format")
        header = [self.TITLES.get(f, f.capitalize()) for f in order_fields]
        header.extend(history_fields)
        header.extend([self.TITLES.get(f, f.capitalize()) for f in owner_fields])
        header.extend(data_fields)
        if table_field:
            header.extend(["%s: %s" % (table_field["identifier"], ci) for ci in colids])
        writer.writerow(header)

        account_lookup = {}
        # Get all orders for the given form.
        view = self.db.view(
            "order",
            "form",
            reduce=False,
            include_docs=True,
            descending=True,
            startkey=[iuid, constants.CEILING],
            endkey=[iuid],
        )
        orders = [r.doc for r in view]

        # Filter by statuses, if any given
        statuses = self.get_arguments("status")
        if statuses and statuses != [""]:
            statuses = set(statuses)
            orders = [o for o in orders if o["status"] in statuses]

        for order in orders:
            row = [order.get(f) for f in order_fields]
            row.extend([order["history"].get(s) or "" for s in history_fields])
            if owner_fields:
                try:
                    account = account_lookup[order["owner"]]
                except KeyError:
                    account = self.get_account(order["owner"])
                    account_lookup[order["owner"]] = account
                row.extend([account.get(f) for f in owner_fields])
            for data_field in data_fields:
                value = order["fields"].get(data_field)
                if isinstance(value, list):
                    value = "|".join(value)
                row.append(value)
            if table_field:
                table = order["fields"].get(table_field["identifier"]) or []
                for tr in table:
                    writer.writerow(row + tr)
            else:
                writer.writerow(row)

        self.write(writer.getvalue())
        filename = (form["title"] or form["_id"]).replace(" ", "_")
        if table_field:
            filename += "_" + table_field["identifier"]
        if file_format == "xlsx":
            self.set_header("Content-Type", constants.XLSX_MIME)
            filename = filename + ".xlsx"
        elif file_format == "csv":
            self.set_header("Content-Type", constants.CSV_MIME)
            filename = filename + ".csv"
        self.set_header(
            "Content-Disposition", 'attachment; filename="orders_%s"' % filename
        )
