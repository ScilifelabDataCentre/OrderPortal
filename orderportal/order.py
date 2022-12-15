"Orders are the whole point of this app. The user fills in info for facility."

import io
import json
import logging
import os.path
import re
import traceback
import urllib.parse
import zipfile

import couchdb2
import tornado.web

from orderportal import constants, settings, parameters
from orderportal import saver
from orderportal import utils
from orderportal.fields import Fields
from orderportal.message import MessageSaver
from orderportal.requesthandler import RequestHandler, ApiV1Mixin


DESIGN_DOC = {
    "views": {
        "form": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.form, doc.modified], 1);
}"""},
        "identifier": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.identifier) return;
    emit(doc.identifier, doc.title);
}"""},
        "keyword": {      # order/keyword
            # NOTE: The 'map' function body is modified in utils.load_design_documents.
            "map": """function(doc) {{
    if (doc.orderportal_doctype !== 'order') return;
    var cleaned = doc.title.replace(/[{delims_lint}]/g, " ").toLowerCase();
    var words = cleaned.split(/\s+/);
    words.forEach(function(word) {{
        if (word.length >= 2 && !lint[word]) emit(word, doc.title);
    }});
}};
var lint = {lint};
"""},
        "modified": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.modified, doc.title);
}"""},
        "owner": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.owner, doc.modified], 1);
}"""},
        "status": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.status, doc.modified], 1);
}"""},
        "tag": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.tags) return;
    doc.tags.forEach(function(tag) {
	emit(tag.toLowerCase(), doc.title);
	var parts = tag.split(':');
	if (parts.length === 2) {
	    emit(parts[1].toLowerCase(), doc.title);
	};
    });
}"""},
        "year_submitted": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.history.submitted) return;
    emit(doc.history.submitted.split('-')[0], 1);
}"""}
    }
}


class OrderSaver(saver.Saver):
    doctype = constants.ORDER

    def initialize(self):
        "Set the initial values for the new order. Create history field."
        super(OrderSaver, self).initialize()
        self["history"] = {}

    def setup(self):
        """Additional setup.
        1) Initialize flag for changed status.
        2) Prepare for attaching files.
        """
        self.changed_status = None
        self.files = []
        self.filenames = set(self.doc.get("_attachments", []))
        try:
            self.fields = Fields(self.rqh.get_form(self.doc["form"]))
        except KeyError:
            pass

    def create(self, form, title=None):
        "Create the order from the given form."
        self.fields = Fields(form)
        self["form"] = form["_id"]
        self["title"] = title
        self["fields"] = dict([(f["identifier"], None) for f in self.fields])
        self.set_status(parameters["ORDER_STATUS_INITIAL"]["identifier"])
        # Set the order identifier if its format defined.
        # Allow also for disabled, since admin may clone such orders.
        if form["status"] in (constants.ENABLED, constants.DISABLED):
            counter = self.rqh.get_next_counter(constants.ORDER)
            self["identifier"] = settings["ORDER_IDENTIFIER_FORMAT"].format(counter)

    def autopopulate(self):
        "Autopopulate fields if defined."
        # First try to set the value of a field from the corresponding
        # value defined for the account's university.
        autopop = settings.get("ORDER_AUTOPOPULATE")
        if not autopop:
            return
        try:
            uni_fields = settings["UNIVERSITIES"][self.rqh.current_user["university"]][
                "fields"
            ]
        except KeyError:
            uni_fields = {}
        for target in autopop:
            if target not in self.fields:
                continue
            value = uni_fields.get(target)
            # Terrible kludge! If it looks like a country field,
            # then attempt to translate from country code to name.
            if "country" in target:
                try:
                    value = settings["COUNTRIES_LOOKUP"][value]
                except KeyError:
                    pass
            self["fields"][target] = value
        # Next try to set the value of a field from the corresponding
        # value defined for the account. For use with e.g. invoice address.
        # Do this only if not done already from university data.
        for target, source in list(autopop.items()):
            if target not in self.fields:
                continue
            value = self["fields"].get(target)
            if isinstance(value, str):
                if value:
                    continue
            elif value is not None:  # Value 0 (zero) must be possible to set
                continue
            try:
                key1, key2 = source.split(".")
            except ValueError:
                value = self.rqh.current_user.get(source)
            else:
                value = self.rqh.current_user.get(key1, {}).get(key2)
            # Terrible kludge! If it looks like a country field,
            # then attempt to translate from country code to name.
            if "country" in target:
                try:
                    value = settings["COUNTRIES_LOOKUP"][value]
                except KeyError:
                    pass
            self["fields"][target] = value

    def add_file(self, infile):
        "Add the given file to the files. Return the unique filename."
        filename = os.path.basename(infile.filename)
        if filename in self.filenames:
            count = 1
            while True:
                filename, ext = os.path.splitext(infile.filename)
                filename = "{0}_{1}{2}".format(filename, count, ext)
                if filename not in self.filenames:
                    break
                count += 1
        self.filenames.add(filename)
        self.files.append(
            dict(filename=filename, body=infile.body, content_type=infile.content_type)
        )
        return filename

    def set_status(self, new):
        "Set the new status of the order."
        if self.get("status") == new:
            return
        if new not in parameters["ORDER_STATUSES_LOOKUP"]:
            raise ValueError(f"invalid status '{new}'")
        if "status" in self.doc:
            targets = self.rqh.get_targets(self.doc)
            if new not in [t["identifier"] for t in targets]:
                raise ValueError(
                    "You may not change status of {0} to {1}.".format(
                        utils.terminology("order"), new
                    )
                )
        self["status"] = new
        self.doc["history"][new] = utils.today()
        self.changed_status = new

    def set_tags(self, tags):
        """Set the tags of the order from JSON data (list of strings).
        Ordinary user may not add or remove prefixed tags.
        """
        if not isinstance(tags, list):
            raise ValueError("tags data is not a list")
        for s in tags:
            if not isinstance(s, str):
                raise ValueError("tags list item is not a string")
        # Allow staff to add prefixed tags.
        if self.rqh.is_staff():
            for pos, tag in enumerate(tags):
                parts = tag.split(":", 1)
                for part in parts:
                    if not constants.ID_RX.match(part):
                        tags[pos] = None
            tags = [t for t in tags if t]
        # User may use only proper identifier-like tags, no prefixes.
        else:
            tags = [t for t in tags if constants.ID_RX.match(t)]
            # Add back the previously defined prefixed tags.
            tags.extend([t for t in self.get("tags", []) if ":" in t])
        self["tags"] = sorted(set(tags))

    def set_external(self, links):
        """Set the external links of the order from JSON data,
        a list of dictionaries with items 'href' and 'title',
        or from lines where the first word of each line is the URL,
        and remaining items are used as title.
        """
        if not isinstance(links, list):
            return
        external = []
        for link in links:
            if isinstance(link, dict):
                try:
                    href = link["href"]
                except KeyError:
                    pass
                else:
                    if isinstance(href, str):
                        title = link.get("title") or href
                        external.append({"href": href, "title": title})
            elif isinstance(link, str):
                link = link.strip()
                if link:
                    parts = link.split()
                    if len(parts) > 1:
                        link = {"href": parts[0], "title": " ".join(parts[1:])}
                    else:
                        link = {"href": parts[0], "title": parts[0]}
                    external.append(link)
        self["links"] = {"external": external}

    def update_fields(self, data=None):
        "Update all fields from JSON data if given, else HTML form input."
        assert self.rqh is not None
        self.removed_files = []  # Names of old files to remove.
        # Loop over fields defined in the form document and get values.
        # Do not change values for a field if that argument is missing,
        # except for checkbox: there a missing value means False,
        # and except for multiselect: there a missing value means empty list.
        for field in self.fields:
            # Field not displayed or not writeable must not be changed.
            if not self.rqh.is_staff() and (
                field["restrict_read"] or field["restrict_write"]
            ):
                continue
            if field["type"] == constants.GROUP:
                continue
            identifier = field["identifier"]

            if field["type"] == constants.FILE:
                value = self.doc["fields"].get(identifier)
                # Files are uploaded by the normal form multi-part
                # encoding approach, not by JSON data.
                try:
                    infile = self.rqh.request.files[identifier][0]
                except (KeyError, IndexError):
                    # No new file given; check if old should be removed.
                    if (
                        utils.to_bool(
                            self.rqh.get_argument(f"{identifier}__remove__", False)
                        )
                        and value
                    ):
                        self.removed_files.append(value)
                        value = None
                else:
                    if value:
                        self.removed_files.append(value)
                    value = self.add_file(infile)

            elif field["type"] == constants.MULTISELECT:
                if data:
                    try:
                        value = data[identifier]
                    except KeyError:
                        continue
                else:
                    # Missing argument implies empty list.
                    # This is a special case for HTML form input.
                    value = self.rqh.get_arguments(identifier)

            elif field["type"] == constants.TABLE:
                coldefs = [utils.parse_field_table_column(c) for c in field["table"]]
                if data:  # JSON data: contains complete table.
                    try:
                        table = data[identifier]
                    except KeyError:
                        continue
                else:  # HTML form data; collect table from fields.
                    try:
                        name = f"_table_{identifier}_count"
                        n_rows = int(self.rqh.get_argument(name, 0))
                    except (ValueError, TypeError):
                        n_rows = 0
                    table = []
                    for i in range(n_rows):
                        row = []
                        for j, coldef in enumerate(coldefs):
                            name = f"_table_{identifier}_{i}_{j}"
                            row.append(self.rqh.get_argument(name, None))
                        table.append(row)
                # Check validity of table content.
                value = []
                try:
                    for row in table:
                        # Check correct number of items in the row.
                        if len(row) != len(coldefs):
                            continue
                        for j, coldef in enumerate(coldefs):
                            coltype = coldef.get("type")
                            if coltype == constants.SELECT:
                                if row[j] not in coldef["options"]:
                                    row[j] = None
                                elif row[j] == "[no value]":
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
                if data:  # JSON data.
                    try:
                        value = data[identifier]
                    except KeyError:
                        continue
                else:  # HTML form input.
                    try:
                        value = self.rqh.get_argument(identifier)
                        if value == "":
                            value = None
                    except tornado.web.MissingArgumentError:
                        # Missing argument means no change,
                        # which is not the same as value None.
                        # Except for boolean checkbox!
                        if field["type"] == constants.BOOLEAN and field.get("checkbox"):
                            value = False
                        else:
                            continue
                # Remove all carriage-returns from string.
                if value is not None:
                    value = value.replace("\r", "")

            # Set tag, if auto_tags for field.
            if (
                settings["ORDER_TAGS"]
                and field["type"] in [constants.STRING, constants.SELECT]
                and field.get("auto_tag")
            ):
                tags = [
                    t
                    for t in self.doc.get("tags", [])
                    if not t.startswith(identifier + ":")
                ]
                if value:
                    tags.append(f"{identifier}:{value}")
                self["tags"] = tags

            # Record any change to the value.
            if value != self.doc["fields"].get(identifier):
                changed = self.changed.setdefault("fields", dict())
                changed[identifier] = value
                self.doc["fields"][identifier] = value
        self.check_fields_validity()

    def check_fields_validity(self):
        "Check validity of current field values."
        self.doc["invalid"] = dict()
        for field in self.fields:
            if field["depth"] == 0:
                self.check_validity(field)

    def check_validity(self, field):
        """Check validity of field value.
        Also convert the value for some field types.
        Skip field if not visible, else check recursively in postorder.
        Return True if valid, False otherwise.
        """
        try:
            select_id = field.get("visible_if_field")
            if select_id:
                select_value = self.doc["fields"].get(select_id)
                if select_value is not None:
                    select_value = str(select_value).lower()
                if_value = field.get("visible_if_value")
                if if_value:
                    if_value = if_value.lower()
                if select_value != if_value:
                    return True

            if field["type"] == constants.GROUP:
                failure = False
                for subfield in field["fields"]:
                    if not self.check_validity(subfield):
                        failure = True
                if failure:
                    raise ValueError("subfield(s) invalid")
            else:
                value = self.doc["fields"][field["identifier"]]
                if value is None:
                    if field["required"]:
                        raise ValueError("missing value")
                elif field["type"] == constants.STRING:
                    pass
                elif field["type"] == constants.EMAIL:
                    if not constants.EMAIL_RX.match(value):
                        raise ValueError("not a valid email address")
                elif field["type"] == constants.INT:
                    try:
                        self.doc["fields"][field["identifier"]] = int(value)
                    except (TypeError, ValueError):
                        raise ValueError("not an integer value")
                elif field["type"] == constants.FLOAT:
                    try:
                        self.doc["fields"][field["identifier"]] = float(value)
                    except (TypeError, ValueError):
                        raise ValueError("not a float value")
                elif field["type"] == constants.BOOLEAN:
                    try:
                        if value is None:
                            raise ValueError
                        self.doc["fields"][field["identifier"]] = utils.to_bool(value)
                    except (TypeError, ValueError):
                        raise ValueError("not a boolean value")
                elif field["type"] == constants.URL:
                    parsed = urllib.parse.urlparse(value)
                    if not (parsed.scheme and parsed.netloc):
                        raise ValueError("incomplete URL")
                elif field["type"] == constants.SELECT:
                    if value not in field["select"]:
                        raise ValueError("value not among alternatives")
                elif field["type"] == constants.MULTISELECT:
                    if not isinstance(value, list):
                        raise ValueError("value is not a list")
                    if field["required"] and len(value) == 1 and value[0] == "":
                        raise ValueError("missing value")
                    for v in value:
                        if v and v not in field["multiselect"]:
                            raise ValueError("value not among alternatives")
                elif field["type"] == constants.TEXT:
                    if not isinstance(value, str):
                        raise ValueError("value is not a text string")
                elif field["type"] == constants.DATE:
                    if not constants.DATE_RX.match(value):
                        raise ValueError("value is not a valid date")
                elif field["type"] == constants.TABLE:
                    if not isinstance(value, list):
                        raise ValueError("table value is not a list")
                    if field["required"] and len(value) == 0:
                        raise ValueError("missing data")
                    for r in value:
                        if not isinstance(r, list):
                            raise ValueError("table value is not a list of lists")
                elif field["type"] == constants.FILE:
                    pass
        except ValueError as msg:
            self.doc["invalid"][field["identifier"]] = str(msg)
            return False
        except Exception as msg:
            self.doc["invalid"][field["identifier"]] = f"System error: {msg}"
            return False
        else:
            return True

    def set_history(self, history):
        "Set the history the JSON data (dict of status->date)"
        if not isinstance(history, dict):
            raise ValueError("history data is not a dictionary")
        for status, date in list(history.items()):
            if not (
                date is None
                or (isinstance(date, str) and constants.DATE_RX.match(date))
            ):
                raise ValueError("invalid date in history data")
            if not status in parameters["ORDER_STATUSES_LOOKUP"]:
                raise ValueError("invalid status in history data")
            self["history"][status] = date

    def post_process(self):
        self.modify_attachments()
        if self.changed_status:
            self.send_message()

    def modify_attachments(self):
        "Save or delete the file as an attachment to the document."
        try:  # Delete the named file.
            self.db.delete_attachment(self.doc, self.delete_filename)
        except AttributeError:
            # Else add any new attached files.
            try:
                # First remove files due to field update.
                for filename in self.removed_files:
                    self.db.delete_attachment(self.doc, filename)
            except AttributeError:
                pass
            for file in self.files:
                self.db.put_attachment(
                    self.doc,
                    file["body"],
                    filename=file["filename"],
                    content_type=file["content_type"],
                )

    def get_order_url(self, order):
        """Member rqh is not available when used from a stand-alone script,
        so self.rqh.order_reverse_url cannot be used.
        The URL has to be synthesized explicitly here."""
        try:
            identifier = order["identifier"]
        except KeyError:
            identifier = order["_id"]
        path = "/order/{0}".format(identifier)
        if settings["BASE_URL_PATH_PREFIX"]:
            path = settings["BASE_URL_PATH_PREFIX"] + path
        return settings["BASE_URL"].rstrip("/") + path

    def get_account(self, email):
        "Get the account document for the given email."
        result = self.db.view("account", "email", key=email, include_docs=True)
        rows = list(result)
        if len(rows) == 1:
            return rows[0].doc
        else:
            return None

    def send_message(self):
        "Send a message after status change."
        try:
            template = settings["ORDER_MESSAGES"][self.doc["status"]]
        except (couchdb2.NotFoundError, KeyError):
            return
        recipients = set()
        owner = self.get_account(self.doc["owner"])
        # Owner account may have been deleted.
        if owner:
            email = owner["email"].strip().lower()
            if "owner" in template["recipients"]:
                recipients = set([owner["email"]])
            if "group" in template["recipients"]:
                for row in self.db.view(
                    "group", "member", include_docs=True, key=email
                ):
                    for member in row.doc["members"]:
                        account = self.get_account(member)
                        if account and account["status"] == constants.ENABLED:
                            recipients.add(account["email"])
        if constants.ADMIN in template["recipients"]:
            # Can't use 'get_admins', not available here.
            result = self.db.view(
                "account", "role", key=constants.ADMIN, include_docs=True
            )
            admins = [r.doc for r in result]
            for admin in admins:
                if admin["status"] == constants.ENABLED:
                    recipients.add(admin["email"])
        try:
            with MessageSaver(rqh=self.rqh) as saver:
                saver.create(
                    template,
                    owner=self.doc["owner"],
                    title=self.doc["title"],
                    identifier=self.doc.get("identifier") or self.doc["_id"],
                    url=self.get_order_url(self.doc),
                    tags=", ".join(self.doc.get("tags", [])),
                )
                saver.send(list(recipients))
        except KeyError as error:
            self.rqh.set_message_flash(str(error))
        except ValueError as error:
            self.rqh.set_error_flash(str(error))


class OrderMixin(object):
    "Mixin for various useful methods."

    def get_order(self, iuid):
        """Get the order for the identifier or IUID.
        Raise ValueError if no such order."""
        try:  # First try order identifier.
            order = self.get_entity_view("order", "identifier", iuid)
        except tornado.web.HTTPError:
            try:  # Next try order doc IUID.
                order = self.get_entity(iuid, doctype=constants.ORDER)
            except tornado.web.HTTPError:
                raise ValueError("Sorry, no such order")
        return order

    def allow_read(self, order):
        "Is the order readable by the current user?"
        if self.is_owner(order):
            return True
        if self.is_staff():
            return True
        if self.is_colleague(order["owner"]):
            return True
        return False

    def check_readable(self, order):
        "Check if current user may read the order."
        if self.allow_read(order):
            return
        raise ValueError("You may not read the order.")

    def allow_edit(self, order):
        "Is the order editable by the current user?"
        if self.is_admin():
            return True
        status = parameters["ORDER_STATUSES_LOOKUP"][order["status"]]
        edit = status.get("edit", [])
        if self.is_staff() and constants.STAFF in edit:
            return True
        if self.is_owner(order) and constants.USER in edit:
            return True
        return False

    def check_editable(self, order):
        "Check if current user may edit the order."
        if self.allow_edit(order):
            return
        raise ValueError("You may not edit the " + utils.terminology("order"))

    def allow_attach(self, order):
        "May the current user may attach a file to the order?"
        if self.is_admin():
            return True
        status = parameters["ORDER_STATUSES_LOOKUP"][order["status"]]
        attach = status.get("attach", [])
        if self.is_staff() and constants.STAFF in attach:
            return True
        if self.is_owner(order) and constants.USER in attach:
            return True
        return False

    def check_attachable(self, order):
        "Check if current user may attach a file to the order."
        if self.allow_attach(order):
            return
        raise tornado.web.HTTPError(
            403,
            reason="You may not attach a file to the {0}.".format(
                utils.terminology("order")
            ),
        )

    def check_creation_enabled(self):
        "If order creation is disabled, raise ValueError."
        term = utils.terminology("Order")
        if (
            self.current_user["role"] == constants.USER
            and not settings["ORDER_CREATE_USER"]
        ):
            raise ValueError(
                f"{term} creation is not allowed for account with role 'user'."
            )

    def get_form(self, iuid, check=False):
        "Get the form given by its IUID. Optionally check that it is enabled."
        form = self.get_entity(iuid, doctype=constants.FORM)
        if check:
            if form["status"] not in (constants.ENABLED, constants.TESTING):
                raise ValueError("form is not available for creation")
        return form

    def get_fields(self, order, depth=0, fields=None):
        """Return a list of dictionaries, each of which
        for a field that is visible to the current user."""
        if fields is None:
            form = self.get_form(order["form"])
            fields = form["fields"]
        result = []
        for field in fields:
            # Check if field may not be viewed by the current user.
            if field["restrict_read"] and not self.is_staff():
                continue
            # Is there a visibility condition? If so, check it.
            fid = field.get("visible_if_field")
            if fid:
                value = str(order["fields"].get(fid)).lower()
                opt = str(field.get("visible_if_value")).lower().split("|")
                if value not in opt:
                    continue
            item = dict(identifier=field["identifier"])
            item["label"] = field.get("label") or field[
                "identifier"
            ].capitalize().replace("_", " ")
            item["depth"] = depth
            item["type"] = field["type"]
            item["value"] = order["fields"].get(field["identifier"])
            item["restrict_read"] = field["restrict_read"]
            item["restrict_write"] = field["restrict_write"]
            item["invalid"] = order["invalid"].get(field["identifier"])
            item["description"] = field.get("description")
            item["__field__"] = field
            result.append(item)
            if field["type"] == constants.GROUP:
                result.extend(self.get_fields(order, depth + 1, field["fields"]))
        return result

    def get_targets(self, order):
        "Get the allowed status transition targets as status lookup items."
        targets = parameters["ORDER_TRANSITIONS"].get(order["status"], dict())
        result = []
        for key, transition in targets.items():
            if transition.get("require_valid") and order["invalid"]: continue
            permission = transition["permission"]
            if ((self.is_admin() and constants.ADMIN in permission)
                or (self.is_staff() and constants.STAFF in permission)
                or (self.is_owner(order) and constants.USER in permission)
            ):
                try:            # Defensive: only allow enabled statuses as targets.
                    result.append(parameters["ORDER_STATUSES_LOOKUP"][key])
                except KeyError:
                    pass
        return result

    def allow_submit(self, order, check_valid=True):
        "Is the order submittable? Special hard-wired status."
        targets = self.get_targets(order)
        return constants.SUBMITTED in [t["identifier"] for t in targets]

    def allow_clone(self, order):
        """Can the given order be cloned? Its form must be enabled.
        Special case: Admin can clone an order even if its form is disabled.
        """
        form = self.get_form(order["form"])
        if self.is_admin():
            return form["status"] in (
                constants.ENABLED,
                constants.TESTING,
                constants.DISABLED,
            )
        return form["status"] in (constants.ENABLED, constants.TESTING)


class OrderApiV1Mixin(ApiV1Mixin):
    "Mixin for order JSON data structure."

    def get_order_json(self, order, account_names=None, forms_lookup=None, full=False):
        """Return a dictionary for JSON output for the order.
        Account names or forms lookup are computed if not given.
        If 'full' then add all fields, else only for orders list.
        NOTE: Only the values of the fields are included, not
        the full definition of the fields. To obtain that,
        one must fetch the JSON for the corresponding form."""
        URL = self.absolute_reverse_url
        if full:
            data = utils.get_json(self.order_reverse_url(order, api=True), "order")
        else:
            data = dict()
        data["identifier"] = order.get("identifier")
        data["title"] = order.get("title") or "[no title]"
        data["iuid"] = order["_id"]
        if full:
            form = self.get_form(order["form"])
            data["form"] = dict(
                [
                    ("title", form["title"]),
                    ("version", form.get("version")),
                    ("iuid", form["_id"]),
                    (
                        "links",
                        dict(
                            api=dict(href=URL("form_api", form["_id"])),
                            display=dict(href=URL("form", form["_id"])),
                        ),
                    ),
                ]
            )
        else:
            if forms_lookup is None:
                forms_lookup = self.get_forms_lookup()
            form = forms_lookup[order["form"]]
            data["form"] = dict(
                [
                    ("iuid", order["form"]),
                    ("title", form["title"]),
                    ("version", form.get("version")),
                    ("links", dict(api=dict(href=URL("form", order["form"])))),
                ]
            )
        if account_names is None:
            account_names = self.get_account_names([order["owner"]])
        data["owner"] = dict(
            email=order["owner"],
            name=account_names.get(order["owner"]),
            links=dict(
                api=dict(href=URL("account_api", order["owner"])),
                display=dict(href=URL("account", order["owner"])),
            ),
        )
        data["status"] = order["status"]
        data["report"] = dict()
        if order.get("report"):
            data["report"]["content_type"] = order["_attachments"][
                constants.SYSTEM_REPORT
            ]["content_type"]
            data["report"]["timestamp"] = order["report"]["timestamp"]
            data["report"]["link"] = dict(href=URL("order_report_api", order["_id"]))
        data["history"] = dict()
        for s in parameters["ORDER_STATUSES"]:
            key = s["identifier"]
            data["history"][key] = order["history"].get(key)
        data["tags"] = order.get("tags", [])
        data["modified"] = order["modified"]
        data["created"] = order["created"]
        data["links"] = dict(
            api=dict(href=self.order_reverse_url(order, api=True)),
            display=dict(href=self.order_reverse_url(order)),
        )
        if full:
            for status in self.get_targets(order):
                data["links"][status["identifier"]] = dict(
                    href=URL(
                        "order_transition_api", order["_id"], status["identifier"]
                    ),
                    name="transition",
                )
            data["links"]["external"] = order.get("links", {}).get("external", [])
            data["fields"] = dict()
            # A bit roundabout, but the fields will come out in correct order
            for field in self.get_fields(order):
                data["fields"][field["identifier"]] = field["value"]
            data["invalid"] = order.get("invalid", {})
            data["files"] = dict()
            for filename in sorted(order.get("_attachments", [])):
                if filename.startswith(constants.SYSTEM):
                    continue
                stub = order["_attachments"][filename]
                data["files"][filename] = dict(
                    size=stub["length"],
                    content_type=stub["content_type"],
                    href=self.absolute_reverse_url(
                        "order_file", order["_id"], filename
                    ),
                )
        # XXX Terrible kludge! Converts binary keys and values to string.
        # XXX A Python3 issue, possible due to bad old CouchDB interface.
        return json.loads(json.dumps(data))


def convert_to_strings(doc):
    items = list(doc.items())
    for key, value in items:
        if isinstance(key, bytes):
            doc[key.decode()] = doc.pop(key)
        if isinstance(value, dict):
            convert_to_strings(value)


class OrderCreate(OrderMixin, RequestHandler):
    "Create a new order."

    # Do not use auth decorator: Instead show error message if not logged in.
    def get(self):
        try:
            if not self.current_user:
                raise ValueError(
                    "You need to be logged in to create {0}."
                    " Register to get an account if you don't have one.".format(
                        utils.terminology("order")
                    )
                )
            self.check_creation_enabled()
            form = self.get_form(self.get_argument("form"), check=True)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
        else:
            self.render("order_create.html", form=form)

    @tornado.web.authenticated
    def post(self):
        try:
            self.check_creation_enabled()
            form = self.get_form(self.get_argument("form"), check=True)
            with OrderSaver(rqh=self) as saver:
                saver.create(form)
                saver.autopopulate()
                saver.check_fields_validity()
        except ValueError as msg:
            self.see_other("home", error=str(msg))
        else:
            self.see_other("order_edit", saver.doc["_id"])


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
            iuid = data.get("form")
            if not iuid:
                raise ValueError("no form IUID given")
            form = self.get_form(iuid, check=True)
            with OrderSaver(rqh=self) as saver:
                saver.create(form, title=data.get("title"))
                saver.autopopulate()
                saver.check_fields_validity()
        except ValueError as msg:
            raise tornado.web.HTTPError(400, reason=str(msg))
        else:
            self.write(self.get_order_json(saver.doc, full=True))


class Order(OrderMixin, RequestHandler):
    "Order page."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        try:
            self.check_readable(order)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        form = self.get_form(order["form"])
        files = []
        for filename in order.get("_attachments", []):
            if filename.startswith(constants.SYSTEM):
                continue
            stub = order["_attachments"][filename]
            files.append(
                dict(
                    filename=filename,
                    size=stub["length"],
                    content_type=stub["content_type"],
                )
            )
            files.sort(key=lambda i: i["filename"].lower())
        self.render(
            "order.html",
            title="{0} '{1}'".format(utils.terminology("Order"), order["title"]),
            order=order,
            account_names=self.get_account_names([order["owner"]]),
            status=parameters["ORDER_STATUSES_LOOKUP"][order["status"]],
            form=form,
            fields=form["fields"],
            attached_files=files,
            allow_edit=self.is_admin() or self.allow_edit(order),
            allow_clone=self.allow_clone(order),
            allow_attach=self.allow_attach(order),
            targets=self.get_targets(order),
        )

    @tornado.web.authenticated
    def post(self, iuid):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(
            405, reason="Internal problem; POST only allowed for DELETE."
        )

    @tornado.web.authenticated
    def delete(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        self.delete_logs(order["_id"])
        self.db.delete(order)
        self.see_other("orders")


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
                    saver["title"] = data["title"]
                except KeyError:
                    pass
                try:
                    tags = data["tags"]
                except KeyError:
                    pass
                else:
                    if isinstance(tags, str):
                        tags = [tags]
                    saver.set_tags(tags)
                try:
                    saver.set_external(data["links"]["external"])
                except KeyError:
                    pass
                try:
                    saver.update_fields(data=data["fields"])
                except KeyError:
                    pass
                if self.is_admin():
                    try:
                        saver.set_history(data["history"])
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
        form = self.get_form(order["form"])
        writer.writerow((settings["SITE_NAME"], utils.today()))
        try:
            writer.writerow(("Identifier", order["identifier"]))
        except KeyError:
            pass
        writer.writerow(("Title", order["title"] or "[no title]"))
        writer.writerow(("URL", self.order_reverse_url(order)))
        writer.writerow(("IUID", order["_id"]))
        writer.writerow(("Form", "Title", form["title"]))
        writer.writerow(("", "Version", form.get("version") or "-"))
        writer.writerow(("", "IUID", form["_id"]))
        account = self.get_account(order["owner"])
        writer.writerow(("Owner", "Name", utils.get_account_name(account)))
        writer.writerow(("", "URL", URL("account", account["email"])))
        writer.writerow(("", "Email", order["owner"]))
        writer.writerow(("", "University", account.get("university") or "-"))
        writer.writerow(("", "Department", account.get("department") or "-"))
        writer.writerow(("", "PI", account.get("pi") and "Yes" or "No"))
        if settings.get("ACCOUNT_FUNDER_INFO") and settings.get(
            "ACCOUNT_FUNDER_INFO_GENDER"
        ):
            writer.writerow(("", "Gender", account.get("gender", "-").capitalize()))
        writer.writerow(("Status", order["status"]))
        for i, s in enumerate(parameters["ORDER_STATUSES"]):
            key = s["identifier"]
            writer.writerow(
                (i == 0 and "History" or "", key, order["history"].get(key, "-"))
            )
        for t in order.get("tags", []):
            writer.writerow(("Tag", t))
        writer.writerow(("Modified", order["modified"]))
        writer.writerow(("Created", order["created"]))
        writer.new_worksheet("Fields")
        column_headers = (
            "Field",
            "Label",
            "Depth",
            "Type",
            "Value",
            "Restrict read",
            "Restrict write",
            "Invalid",
        )
        n_column_headers = len(column_headers)
        writer.writerow(column_headers)
        for field in self.get_fields(order):
            field.pop("description")  # Must not be in the values list.
            field_ref = field.pop("__field__")  # Must not be in the values list.
            values = list(field.values())
            # Special case for table field; spans more than one row
            if field["type"] == constants.TABLE:
                table = values[4]  # Column for 'Value'
                values[4] = len(table)  # Number of rows in table
                values += [h.split(";")[0] for h in field_ref["table"]]
                writer.writerow(values)
                prefix = [""] * n_column_headers
                for row in table:
                    writer.writerow(prefix + row)

            elif field["type"] == constants.MULTISELECT:
                if isinstance(values[4], list):
                    values[4] = "|".join(values[4])
                writer.writerow(values)
            else:
                writer.writerow(values)
        writer.new_worksheet("Files")
        writer.writerow(("File", "Size", "Content type", "URL"))
        for filename in sorted(order.get("_attachments", [])):
            if filename.startswith(constants.SYSTEM):
                continue
            stub = order["_attachments"][filename]
            writer.writerow(
                (
                    filename,
                    stub["length"],
                    stub["content_type"],
                    URL("order_file", order["_id"], filename),
                )
            )
        return writer

    def get_writer(self):
        return utils.CsvWriter("Order")

    def write_finish(self, order):
        self.set_header("Content-Type", constants.CSV_MIME)
        filename = order.get("identifier") or order["_id"]
        self.set_header(f"Content-Disposition", 'attachment; filename="{filename}.csv"')


class OrderXlsx(OrderCsv):
    "Return an XLSX file containing the order data. Contains field definitions."

    def get_writer(self):
        return utils.XlsxWriter("Order")

    def write_finish(self, order):
        self.set_header("Content-Type", constants.XLSX_MIME)
        filename = order.get("identifier") or order["_id"]
        self.set_header("Content-Disposition", f'attachment; filename="{filename}.xlsx"')


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
        with zipfile.ZipFile(zip_io, "w") as writer:
            name = order.get("identifier") or order["_id"]
            csvwriter = self.write_order(order, writer=utils.CsvWriter("Order"))
            writer.writestr(name + ".csv", csvwriter.getvalue())
            xlsxwriter = self.write_order(order, writer=utils.XlsxWriter("Order"))
            writer.writestr(name + ".xlsx", xlsxwriter.getvalue())
            writer.writestr(
                name + ".json", json.dumps(self.get_order_json(order, full=True))
            )
            for filename in sorted(order.get("_attachments", [])):
                outfile = self.db.get_attachment(order, filename)
                writer.writestr(filename, outfile.read())
        self.write(zip_io.getvalue())
        self.set_header("Content-Type", constants.ZIP_MIME)
        filename = order.get("identifier") or order["_id"]
        self.set_header("Content-Disposition", f'attachment; filename="{filename}.zip"')


class OrderLogs(OrderMixin, RequestHandler):
    "Order log entries page."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            order = self.get_order(iuid)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        try:
            self.check_readable(order)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        title = "Logs for {0} '{1}'".format(
            utils.terminology("order"), order["title"] or "[no title]"
        )
        self.render(
            "logs.html", title=title, entity=order, logs=self.get_logs(order["_id"])
        )


class OrderEdit(OrderMixin, RequestHandler):
    "Page for editing an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        colleagues = sorted(self.get_account_colleagues(self.current_user["email"]))
        form = self.get_form(order["form"])
        fields = Fields(form)
        if self.is_staff():
            tags = order.get("tags", [])
        else:
            tags = [t for t in order.get("tags", []) if not ":" in t]
        links = []
        for link in order.get("links", {}).get("external", []):
            if link["href"] == link["title"]:
                links.append(link["href"])
            else:
                links.append(f"{link['href']} {link['title']}")
        # XXX Currently, multiselect fields are not handled correctly.
        #     Too much effort; leave as is for the time being.
        hidden_fields = set(
            [f["identifier"] for f in fields.flatten() if f["type"] != "multiselect"]
        )
        # For each table input field, create code for use in bespoke JavaScript.
        tableinputs = {}
        for field in fields.flatten():
            if field["type"] != "table":
                continue
            tableinput = ["<tr>" "<td id='rowid__' class='table-input-row-0'></td>"]
            for i, coldef in enumerate(field["table"]):
                column = utils.parse_field_table_column(coldef)
                rowid = f"rowid_{i}"
                if column["type"] == constants.SELECT:
                    inp = [f"<select class='form-control' name='{rowid}' id='{rowid}'>"]
                    inp.extend(["<option>%s</option>" % o for o in column["options"]])
                    inp = "".join(inp)
                elif column["type"] == constants.INT:
                    inp = f"<input type='number' step='1' class='form-control' name='{rowid}' id='{rowid}'>"
                elif column["type"] == constants.FLOAT:
                    inp = (
                        f"<input type='number' step='{constants.FLOAT_STEP}'"
                        f" class='form-control' name='{rowid}' id='{rowid}'>"
                    )
                elif column["type"] == constants.DATE:
                    inp = f"<input type='text' class='form-control datepicker' name='{rowid}' id='{rowid}'>"
                else:  # Default type: 'string'
                    inp = f"<input type='text' class='form-control' name='{rowid}' id='{rowid}'>"
                tableinput.append("<td>%s</td>" % inp)
            tableinput.append("</tr>")
            tableinputs[field["identifier"]] = "".join(tableinput)
        self.render(
            "order_edit.html",
            title="Edit {0} '{1}'".format(
                utils.terminology("order"), order["title"] or "[no title]"
            ),
            order=order,
            tags=tags,
            links=links,
            colleagues=colleagues,
            form=form,
            fields=form["fields"],
            hidden_fields=hidden_fields,
            tableinputs=tableinputs,
        )

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        flag = self.get_argument("__save__", None)
        try:
            message = "{0} saved.".format(utils.terminology("Order"))
            error = None
            with OrderSaver(doc=order, rqh=self) as saver:
                saver["title"] = self.get_argument("__title__", None)
                saver.set_tags(
                    self.get_argument("__tags__", "").replace(",", " ").split()
                )
                saver.set_external(self.get_argument("__links__", "").split("\n"))
                saver.update_fields()
            self.set_error_flash(error)
            self.set_message_flash(message)
            if flag == "continue":
                self.see_other("order_edit", order["_id"])
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
            self.see_other("home", error=str(msg))
            return
        self.render(
            "order_owner.html",
            title="Change owner of {0} '{1}'".format(
                utils.terminology("order"), order["title"] or "[no title]"
            ),
            order=order,
        )

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_editable(order)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        try:
            owner = self.get_argument("owner")
            account = self.get_account(owner)
            if account.get("status") != constants.ENABLED:
                raise ValueError("Owner account is not enabled.")
            with OrderSaver(doc=order, rqh=self) as saver:
                saver["owner"] = account["email"]
        except tornado.web.MissingArgumentError:
            pass
        except ValueError as msg:
            self.set_error_flash(str(msg))
        self.set_message_flash(
            "Changed owner of {0}.".format(utils.terminology("Order"))
        )
        if self.allow_read(order):
            self.redirect(self.order_reverse_url(order))
        else:
            self.see_other("home")


class OrderClone(OrderMixin, RequestHandler):
    "Create a new order from an existing one."

    @tornado.web.authenticated
    def post(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError as msg:
            self.see_other("home", error=str(msg))
            return
        if not self.allow_clone(order):
            raise ValueError(
                "This {0} is outdated; its form has been disabled.".format(
                    utils.terminology("order")
                )
            )
        form = self.get_form(order["form"])
        erased_files = set()
        with OrderSaver(rqh=self) as saver:
            saver.create(
                form, title="Clone of {0}".format(order["title"] or "[no title]")
            )
            for field in saver.fields:
                id = field["identifier"]
                if field.get("erase_on_clone"):
                    if field["type"] == constants.FILE:
                        erased_files.add(order["fields"][id])
                    saver["fields"][id] = None
                else:
                    saver["fields"][id] = order["fields"][id]
            saver.check_fields_validity()
        # Make copies of attached files.
        #  Must be done after initial save to avoid version mismatches.
        for filename in order.get("_attachments", []):
            if filename.startswith(constants.SYSTEM):
                continue
            if filename in erased_files:
                continue
            stub = order["_attachments"][filename]
            outfile = self.db.get_attachment(order, filename)
            self.db.put_attachment(
                saver.doc, outfile, filename=filename, content_type=stub["content_type"]
            )
        self.redirect(self.order_reverse_url(saver.doc))


class OrderTransition(OrderMixin, RequestHandler):
    "Change the status of an order."

    @tornado.web.authenticated
    def post(self, iuid, targetid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            for target in self.get_targets(order):
                if target["identifier"] == targetid:
                    break
            else:
                raise ValueError("disallowed status transition")
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
            self.see_other("home", error=str(msg))
            return
        outfile = self.db.get_attachment(order, filename)
        if outfile is None:
            self.see_other("order", iuid, error="No such file.")
        else:
            self.write(outfile.read())
            outfile.close()
            self.set_header(
                "Content-Type", order["_attachments"][filename]["content_type"]
            )
            # Try to avoid strange latin-1 encoding issue with tornado.
            b = f'attachment; filename="{filename}"'
            b = b.encode("utf-8")
            self.set_header("Content-Disposition", b)

    @tornado.web.authenticated
    def post(self, iuid, filename=None):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid, filename)
            return
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        try:
            infile = self.request.files["file"][0]
        except (KeyError, IndexError):
            pass
        else:
            if infile.filename.startswith(constants.SYSTEM):
                raise tornado.web.HTTPError(400, reason="Reserved filename.")
            with OrderSaver(doc=order, rqh=self) as saver:
                saver.add_file(infile)
        self.redirect(self.order_reverse_url(order))

    @tornado.web.authenticated
    def delete(self, iuid, filename):
        if filename is None:
            raise tornado.web.HTTPError(400)
        if filename.startswith(constants.SYSTEM):
            raise tornado.web.HTTPError(400, reason="Reserved filename.")
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_attachable(order)
        fields = Fields(self.get_form(order["form"]))
        with OrderSaver(doc=order, rqh=self) as saver:
            for key in order["fields"]:
                # Remove the field value if it is the filename.
                # XXX Slightly dangerous: may delete a value that happens to
                # be identical to the filename. Shouldn't be too commmon...
                if order["fields"][key] == filename:
                    order["fields"][key] = None
                    if fields[key]["required"]:
                        saver.doc["invalid"][key] = "missing value"
                    else:
                        saver.doc["invalid"].pop(key, None)
                    break
            saver.delete_filename = filename
            saver.changed["file_deleted"] = filename
        self.redirect(self.order_reverse_url(order))


class OrderReport(OrderMixin, RequestHandler):
    "View the report for an order."

    @tornado.web.authenticated
    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.check_readable(order)
        try:
            report = order["report"]
            outfile = self.db.get_attachment(order, constants.SYSTEM_REPORT)
            if outfile is None:
                raise KeyError
        except KeyError:
            self.see_other("order", iuid, error="No report available.")
            return
        content_type = order["_attachments"][constants.SYSTEM_REPORT]["content_type"]
        if report.get("inline"):
            self.render(
                "order_report.html",
                order=order,
                content=outfile.read(),
                content_type=content_type,
            )
        else:
            self.write(outfile.read())
            outfile.close()
            self.set_header("Content-Type", content_type)
            name = order.get("identifier") or order["_id"]
            ext = utils.get_filename_extension(content_type)
            self.set_header(
                "Content-Disposition", f'attachment; filename="{name}_report{ext}"'
            )


class OrderReportApiV1(OrderApiV1Mixin, OrderMixin, RequestHandler):
    "Order report API: get or set."

    def get(self, iuid):
        order = self.get_entity(iuid, doctype=constants.ORDER)
        try:
            self.check_readable(order)
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        try:
            report = order["report"]
            outfile = self.db.get_attachment(order, constants.SYSTEM_REPORT)
            if outfile is None:
                raise KeyError
        except KeyError:
            raise tornado.web.HTTPError(404)
        self.write(outfile.read())
        outfile.close()
        content_type = order["_attachments"][constants.SYSTEM_REPORT]["content_type"]
        self.set_header("Content-Type", content_type)
        name = order.get("identifier") or order["_id"]
        ext = utils.get_filename_extension(content_type)
        self.set_header(
            "Content-Disposition", f'attachment; filename="{name}_report{ext}"'
        )

    def put(self, iuid):
        try:
            self.check_admin()
        except ValueError as msg:
            raise tornado.web.HTTPError(403, reason=str(msg))
        order = self.get_entity(iuid, doctype=constants.ORDER)
        with OrderSaver(doc=order, rqh=self) as saver:
            content_type = (
                self.request.headers.get("content-type") or constants.BIN_MIME
            )
            saver["report"] = dict(
                timestamp=utils.timestamp(),
                inline=content_type in (constants.HTML_MIME, constants.TEXT_MIME),
            )
            saver.files.append(
                dict(
                    filename=constants.SYSTEM_REPORT,
                    body=self.request.body,
                    content_type=content_type,
                )
            )
        self.write("")


class OrderReportEdit(OrderMixin, RequestHandler):
    "Edit the report for an order."

    @tornado.web.authenticated
    def get(self, iuid):
        self.check_admin()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        self.render("order_report_edit.html", order=order)

    @tornado.web.authenticated
    def post(self, iuid):
        self.check_admin()
        order = self.get_entity(iuid, doctype=constants.ORDER)
        with OrderSaver(doc=order, rqh=self) as saver:
            try:
                infile = self.request.files["report"][0]
            except (KeyError, IndexError):
                if order.get("report"):
                    saver.delete_filename = constants.SYSTEM_REPORT
                    saver["report"] = dict()
            else:
                saver["report"] = dict(
                    timestamp=utils.timestamp(),
                    inline=infile.content_type
                    in (constants.HTML_MIME, constants.TEXT_MIME),
                )
                saver.files.append(
                    dict(
                        filename=constants.SYSTEM_REPORT,
                        body=infile.body,
                        content_type=infile.content_type,
                    )
                )
        self.redirect(self.order_reverse_url(order))


class Orders(RequestHandler):
    "Orders list page."

    @tornado.web.authenticated
    def get(self):
        # Ordinary users are not allowed to see the overall orders list.
        if not self.is_staff():
            self.see_other("account_orders", self.current_user["email"])
            return
        # Count orders per year submitted.
        view = self.db.view("order", "year_submitted", reduce=True, group_level=1)
        years = [(r.key, r.value) for r in view]
        years.reverse()
        # Count all orders.
        view = self.db.view("order", "status", reduce=True)
        try:
            r = list(view)[0]
        except IndexError:
            all_count = 0
        else:
            all_count = r.value
        # Default ordering by the 'modified' column.
        if parameters["DEFAULT_ORDER_COLUMN"] == "modified":
            order_column = (
                5
                + int(parameters["ORDERS_LIST_TAGS"]) # boolean
                + len(parameters["ORDERS_LIST_FIELDS"]) # list
                + len(parameters["ORDERS_LIST_STATUSES"]) # list
            )
        # Otherwise default ordering by the identifier column.
        else:
            order_column = 0
        self.set_filter()
        self.render(
            "orders.html",
            forms_lookup=self.get_forms_lookup(),
            years=years,
            filter=self.filter,
            orders=self.get_orders(),
            order_column=order_column,
            account_names=self.get_account_names(),
            all_count=all_count,
        )

    def set_filter(self):
        "Set the filter parameters dictionary."
        self.filter = dict()
        for key in ["status", "form_id", "owner"] + [
                f["identifier"] for f in parameters["ORDERS_FILTER_FIELDS"]
        ]:
            try:
                value = self.get_argument(key)
                if not value:
                    raise KeyError
                self.filter[key] = value
            except (tornado.web.MissingArgumentError, KeyError):
                pass
        self.filter["year"] = self.get_argument("year", None) or "recent"

    def get_orders(self):
        "Get all orders according to current filter."
        orders = self.filter_by_status(self.filter.get("status"))
        orders = self.filter_by_form(self.filter.get("form_id"), orders=orders)
        orders = self.filter_by_owner(self.filter.get("owner"), orders=orders)
        for f in parameters["ORDERS_FILTER_FIELDS"]:
            orders = self.filter_by_field(
                f["identifier"], self.filter.get(f["identifier"]), orders=orders
            )
        orders = self.filter_by_year(self.filter["year"], orders=orders)
        return orders

    def filter_by_status(self, status, orders=None):
        "Return orders list if any status filter, or unchanged input if no such filter."
        if status:
            if orders is None:
                view = self.db.view(
                    "order",
                    "status",
                    descending=True,
                    startkey=[status, constants.CEILING],
                    endkey=[status],
                    include_docs=True,
                )
                orders = [r.doc for r in view]
            else:
                orders = [o for o in orders if o["status"] == status]
        return orders

    def filter_by_form(self, form_id, orders=None):
        """Return orders list after applying any form filter,
        or unchanged input if no such filter.
        """
        if form_id:
            if orders is None:
                view = self.db.view(
                    "order",
                    "form",
                    descending=True,
                    startkey=[form_id, constants.CEILING],
                    endkey=[form_id],
                    include_docs=True,
                )
                orders = [r.doc for r in view]
            else:
                orders = [o for o in orders if o["form"] == form_id]
        return orders

    def filter_by_owner(self, owner, orders=None):
        "Return orders list if any owner filter, or unchanged input if no such filter."
        if owner:
            if orders is None:
                view = self.db.view(
                    "order",
                    "owner",
                    descending=True,
                    startkey=[owner, constants.CEILING],
                    endkey=[owner],
                    include_docs=True,
                )
                orders = [r.doc for r in view]
            else:
                orders = [o for o in orders if o["owner"] == owner]
        return orders

    def filter_by_field(self, identifier, value, orders=None):
        "Return orders list if any field filter, or unchanged input if none."
        if value:
            if orders is None:
                view = self.db.view(
                    "order", "modified", include_docs=True, descending=True
                )
                orders = [r.doc for r in view]
            if value == "__none__":
                value = None
            orders = [o for o in orders if o["fields"].get(identifier) == value]
        return orders

    def filter_by_year(self, year, orders=None):
        "Return orders list by year filter, most recent if none, or all if specified."
        if year == "recent":
            if orders is None:
                view = self.db.view(
                    "order",
                    "modified",
                    include_docs=True,
                    descending=True,
                    limit=parameters["DISPLAY_ORDERS_MOST_RECENT"],
                )
                orders = [r.doc for r in view]
            else:
                orders = orders[: parameters["DISPLAY_ORDERS_MOST_RECENT"]]

        elif year == "all":
            if orders is None:
                view = self.db.view(
                    "order", "modified", include_docs=True, descending=True
                )
                orders = [r.doc for r in view]
            else:
                pass  # "all" means no filter by year.

        else:  # Specific year
            if orders is None:
                view = self.db.view(
                    "order", "year_submitted", include_docs=True, key=year
                )
                orders = [r.doc for r in view]
            else:
                orders = [
                    o
                    for o in orders
                    if o["history"].get(constants.SUBMITTED, "X").split("-")[0] == year
                ]
        return orders


class OrdersApiV1(OrderApiV1Mixin, OrderMixin, Orders):
    "Orders API; JSON output."

    def get(self):
        "JSON output."
        URL = self.absolute_reverse_url
        self.check_staff()
        self.set_filter()
        result = utils.get_json(URL("orders_api", **self.filter), "orders")
        result["filter"] = self.filter
        result["links"] = dict(
            api=dict(href=URL("orders_api")), display=dict(href=URL("orders"))
        )
        # Get account names and forms lookups once only.
        account_names = self.get_account_names()
        forms_lookup = self.get_forms_lookup()
        result["items"] = []
        for order in self.get_orders():
            data = self.get_order_json(
                order, account_names=account_names, forms_lookup=forms_lookup
            )
            data["fields"] = dict()
            for key in parameters["ORDERS_LIST_FIELDS"]:
                data["fields"][key] = order["fields"].get(key)
            result["items"].append(data)
            result["invalid"] = order["invalid"]
        self.write(result)


class OrdersCsv(Orders):
    "Orders list as CSV file."

    @tornado.web.authenticated
    def get(self):
        # Ordinary users are not allowed to see the overall orders list.
        if not self.is_staff():
            self.see_other("account_orders", self.current_user["email"])
            return
        self.set_filter()
        writer = self.get_writer()
        writer.writerow((settings["SITE_NAME"], utils.today()))
        row = [
            "Identifier",
            "Title",
            "IUID",
            "URL",
            "Form",
            "Form IUID",
            "Form URL",
            "Owner",
            "Owner name",
            "Owner URL",
            "Tags",
        ]
        row.extend(parameters["ORDERS_LIST_FIELDS"])
        row.append("Status")
        row.extend([s.capitalize() for s in parameters["ORDERS_LIST_STATUSES"]])
        row.append("Modified")
        writer.writerow(row)
        account_names = self.get_account_names()
        forms_lookup = self.get_forms_lookup()
        for order in self.get_orders():
            form = forms_lookup[order["form"]]
            row = [
                order.get("identifier") or "",
                order["title"] or "[no title]",
                order["_id"],
                self.order_reverse_url(order),
                f"{form['title']} ({form.get('version') or '-'})",
                order["form"],
                self.absolute_reverse_url("form", order["form"]),
                order["owner"],
                account_names[order["owner"]],
                self.absolute_reverse_url("account", order["owner"]),
                ", ".join(order.get("tags", [])),
            ]
            for f in parameters["ORDERS_LIST_FIELDS"]:
                row.append(order["fields"].get(f))
            row.append(order["status"])
            for s in parameters["ORDERS_LIST_STATUSES"]:
                row.append(order["history"].get(s))
            row.append(order["modified"])
            writer.writerow(row)
        self.write(writer.getvalue())
        self.write_finish()

    def get_writer(self):
        return utils.CsvWriter()

    def write_finish(self):
        self.set_header("Content-Type", constants.CSV_MIME)
        self.set_header("Content-Disposition", 'attachment; filename="orders.csv"')


class OrdersXlsx(OrdersCsv):
    "Orders list as XLSX."

    def get_writer(self):
        return utils.XlsxWriter()

    def write_finish(self):
        self.set_header("Content-Type", constants.XLSX_MIME)
        self.set_header("Content-Disposition", 'attachment; filename="orders.xlsx"')
