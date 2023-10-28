"An order may have reports attached, which may go through a workflow for approval."

import base64
import json
import os.path

import tornado.web

from orderportal import constants
from orderportal import settings
from orderportal import saver
from orderportal import utils
from orderportal.message import MessageSaver
from orderportal.requesthandler import RequestHandler, ApiV1Mixin


class ReportSaver(saver.Saver):
    doctype = constants.REPORT

    def initialize(self):
        self.doc["reviewers"] = {}

    def setup(self):
        self.original_status = self.get("status")
        self.original_reviewers = set(self.get("reviewers"))  # Keys (email) only.
        self.updated_file = None

    def post_process(self):
        "Add or replace the file content."
        if not self.updated_file:
            return
        try:
            filename = list(self.doc["_attachments"])[0]
        except (KeyError, IndexError):
            pass
        else:
            self.handler.db.delete_attachment(self.doc, filename)
        self.handler.db.put_attachment(
            self.doc,
            self.updated_file["body"],
            filename=self.updated_file["filename"],
            content_type=self.updated_file["content_type"],
        )

    def set_owner(self, owner):
        """Set the owner of the report. Only enabled staff accounts are accepted.
        Raise ValueError if bad value.
        """
        account = self.handler.get_account(owner)
        if account["status"] != constants.ENABLED:
            raise ValueError("Account is not enabled.")
        if account["role"] not in (constants.ADMIN, constants.STAFF):
            raise ValueError("Account is not admin or staff.")
        self["owner"] = account["email"]

    def set_file(self, file):
        """Set the file content; attachment will be handled later.
        Raise ValueError if any of the items 'data', 'filename' or
        'content_type' is missing.
        """
        if "filename" not in file:
            raise ValueError("Given file lacks 'filename' key.")
        if "content_type" not in file:
            raise ValueError("Given file lacks 'content_type' key.")
        try:
            file["body"] = base64.b64decode(file["data"])
        except KeyError:
            if "body" not in file:
                raise ValueError("Given file lacks 'data' or 'body' key.")
        self.updated_file = file
        self["inline"] = file["content_type"] in (
            constants.HTML_MIMETYPE,
            constants.TEXT_MIMETYPE,
        )

    def set_reviewers(self, reviewers):
        """Set the reviewers of this report. Give list of email addresses.
        Accounts that are not enabled or staff or admin are ignored.
        """
        if not reviewers:
            return
        for reviewer in reviewers:
            try:
                account = self.handler.get_account(reviewer)
                if account["status"] != constants.ENABLED:
                    continue
                if account["role"] not in (constants.ADMIN, constants.STAFF):
                    continue
                self["reviewers"][account["email"]] = {
                    "status": constants.REVIEW,
                    "review": None,
                    "modified": utils.timestamp(),
                }
            except ValueError:
                pass

    def set_status(self, status=None):
        """Set the status of the report.
        If there are reviewers, then set to "rejected" if any of them has done so.
        If all reviewers have "approved", then set to "published".
        Else set to the given status, or to "review" if none given.
        If no reviewers, then set to the passed value, or "review" if none given.
        """
        if status and status not in constants.REPORT_STATUSES:
            raise ValueError(f"invalid status '{status}'")
        if self["reviewers"]:
            for reviewer in self["reviewers"].values():
                if reviewer["status"] == constants.REJECTED:
                    self["status"] = constants.REJECTED
                    break
            else:
                for reviewer in self["reviewers"].values():
                    if reviewer["status"] != constants.APPROVED:
                        self["status"] = status or constants.REVIEW
                        break
                else:
                    self["status"] = constants.PUBLISHED
        elif status is None:
            self["status"] = constants.REVIEW
        else:
            self["status"] = status

    def send_reviewers_message(self):
        """Send an email to the reviewers of the report, if any.
        If the status is unchanged "review", then send only to new reviewers.
        If the status has changed to "review", send to all reviewers.
        """
        if self["status"] != constants.REVIEW:
            return
        if self["status"] == self.original_status:
            reviewers = list(set(self["reviewers"]).difference(self.original_reviewers))
        else:
            reviewers = list(set(self["reviewers"]))
        if not reviewers:
            return
        try:
            order = self.handler.get_order(self["order"])
            with MessageSaver(handler=self.handler) as saver:
                saver.create(
                    settings[constants.REPORT]["reviewers"],
                    name=self["name"],
                    title=order["title"],
                    url=utils.get_order_url(order),
                )
                saver.send(reviewers)
        except (KeyError, ValueError):
            pass

    def send_owner_message(self):
        """Send an email to the owner of the report if the status
        has changed from "review".
        """
        if self["status"] == constants.REVIEW:
            return
        if self["status"] == self.original_status:
            return
        # No need to send to the owner if the owner changed the status.
        if self["owner"] == self.handler.current_user["email"]:
            return
        try:
            order = self.handler.get_order(self["order"])
            with MessageSaver(handler=self.handler) as saver:
                saver.create(
                    settings[constants.REPORT]["owner"],
                    name=self["name"],
                    title=order["title"],
                    url=utils.get_order_url(order),
                    status=self["status"],
                )
                saver.send(self["owner"])
        except (KeyError, ValueError):
            pass


class ReportMixin:
    "Mixin access methods."

    def allow_read(self, report):
        "Is the report readable by the current user?"
        if self.am_staff():
            return True
        if report["status"] == constants.PUBLISHED:
            order = self.get_order(report["order"])
            if self.am_owner(order):
                return True
        return False

    def check_readable(self, report):
        "Check if current user may read the report."
        if self.allow_read(report):
            return
        raise ValueError("You may not read the report.")

    def allow_edit(self, report):
        "Is the report editable by the current user?"
        if self.am_staff():
            return True
        return False

    def check_editable(self, report):
        "Check if current user may edit the report."
        if self.allow_edit(report):
            return
        raise ValueError("You may not edit the report.")


class ReportApiV1Mixin(ApiV1Mixin):
    "Mixin for report JSON data structure."

    def get_report_json(self, report, order=None):
        """Return a dictionary for JSON output for the report."""
        if order is None:
            order = self.get_order(report["order"])
        URL = self.absolute_reverse_url
        data = dict(
            id=URL("report", report["_id"]),
            type="report",
            name=report["name"],
            iuid=report["_id"],
            file=dict(href=URL("report", report["_id"])),
            filename=list(report["_attachments"].keys())[0],
            order=dict(
                identifier=order.get("identifier"),
                title=order.get("title") or "[no title]",
                iuid=order["_id"],
                links=dict(
                    api=dict(href=self.order_reverse_url(order, api=True)),
                    display=dict(href=self.order_reverse_url(order)),
                ),
            ),
            owner=dict(
                email=report["owner"],
                name=self.lookup_account_name(report["owner"]),
                links=dict(
                    api=dict(href=URL("account_api", report["owner"])),
                    display=dict(href=URL("account", report["owner"])),
                ),
            ),
            reviewers=report["reviewers"],
            status=report["status"],
            modified=report["modified"],
            links=dict(
                api=dict(href=URL("report_api", report["_id"])),
                display=dict(href=URL("report", report["_id"])),
            ),
        )
        return data


class ReportAdd(ReportMixin, RequestHandler):
    "Add a new report for an order."

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        try:
            order = self.get_order(self.get_argument("order"))
        except ValueError as error:
            self.see_other("home", error=f"Sorry, no such {{ terminology('order') }}.")
        self.render("report/add.html", order=order)

    @tornado.web.authenticated
    def post(self):
        self.check_staff()
        try:
            order = self.get_order(self.get_argument("order"))
        except ValueError as error:
            self.see_other(
                "home", error=f"Sorry, no such { utils.terminology('order') }."
            )
            return
        try:
            file = self.request.files["file"][0]
        except (KeyError, IndexError):
            self.see_other("order", order["_id"], error="No report file uploaded.")
            return
        try:
            with ReportSaver(handler=self) as saver:
                saver["order"] = order["_id"]
                saver["name"] = self.get_argument("name", None) or file.filename
                saver.set_owner(self.get_argument("owner"))
                saver.set_file(
                    dict(
                        body=file.body,
                        filename=file.filename,
                        content_type=file.content_type,
                    )
                )
                saver.set_reviewers(self.get_argument("reviewers", "").split())
                saver.set_status(self.get_argument("status", None))
                saver.send_reviewers_message()
        except ValueError as error:
            self.see_other("order", order["_id"], error=error)
            return
        self.see_other("order", order["_id"])


class ReportAddApiV1(ReportApiV1Mixin, RequestHandler):
    "Add a report to an order."

    def post(self):
        try:
            self.check_staff()
        except ValueError as error:
            raise tornado.web.HTTPError(403, reason=str(error))
        try:
            data = self.get_json_body()
            order = data.get("order")
            if not order:
                raise ValueError("No order IUID given.")
            order = self.get_order(order)
            with ReportSaver(handler=self) as saver:
                saver["order"] = order["_id"]
                saver["name"] = data["name"]
                saver["owner"] = self.current_user["email"]
                try:
                    saver.set_file(data["file"])
                except KeyError:
                    raise ValueError("Missing 'file' item.")
                saver.set_reviewers(data.get("reviewers") or [])
                saver.set_status(data["status"])
                saver.send_reviewers_message()
            report = self.get_report(saver.doc["_id"])  # Get updated '_attachments'.
        except ValueError as error:
            raise tornado.web.HTTPError(400, reason=str(error))
        self.write(self.get_report_json(report, order))


class Report(ReportMixin, RequestHandler):
    "Display or download the file for the report, or delete it."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
        try:
            self.check_readable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        filename = list(report["_attachments"].keys())[0]
        outfile = self.db.get_attachment(report, filename)
        content_type = report["_attachments"][filename]["content_type"]
        if report.get("inline"):
            self.render(
                "report/inline.html",
                order=self.get_order(report["order"]),
                report=report,
                content=outfile.read(),
                content_type=content_type,
            )
        else:
            self.write(outfile.read())
            outfile.close()
            filename = report["name"]
            ext = os.path.splitext(list(report["_attachments"].keys())[0])[1]
            if not filename.endswith(ext):
                filename += ext
            self.set_header("Content-Type", content_type)
            self.set_header(
                "Content-Disposition", f'''attachment; filename="{filename}"'''
            )

    @tornado.web.authenticated
    def post(self, iuid):
        if self.get_argument("_http_method", None) == "delete":
            self.delete(iuid)
            return
        raise tornado.web.HTTPError(405, reason="POST only allowed for DELETE.")

    @tornado.web.authenticated
    def delete(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
            return
        try:
            self.check_editable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        order = self.get_order(report["order"])
        self.delete_logs(report["_id"])
        self.db.delete(report)
        self.see_other("order", order["_id"])


class ReportApiV1(ReportApiV1Mixin, RequestHandler):
    """Report API; JSON output; JSON input for edit.
    NOTE: the name, status and file can be edited, order and owner cannot.
    """

    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            raise tornado.web.HTTPError(404, reason=str(error))
        order = self.get_order(report["order"])
        try:
            if self.am_staff():
                pass
            elif self.am_owner(order):
                if not report["status"] == constants.PUBLISHED:
                    raise tornado.web.HTTPError(
                        403, reason="Report has not been published."
                    )
            else:
                raise tornado.web.HTTPError(
                    403, reason="Role 'admin' or 'staff' is required."
                )
        except ValueError as error:
            raise tornado.web.HTTPError(403, reason=str(error))
        self.write(self.get_report_json(report))

    def post(self, iuid):
        try:
            self.check_staff()
        except ValueError as error:
            raise tornado.web.HTTPError(403, reason=str(error))
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            raise tornado.web.HTTPError(404, reason=str(error))
        try:
            data = self.get_json_body()
            report = self.get_report(iuid)
            with ReportSaver(doc=report, handler=self) as saver:
                try:
                    saver["name"] = data["name"]
                except KeyError:
                    pass
                try:
                    saver.set_file(data["file"])
                except KeyError:
                    pass
                try:
                    saver.set_status(data["status"])
                except KeyError:
                    pass
        except ValueError as error:
            raise tornado.web.HTTPError(400, reason=str(error))
        self.write(self.get_report_json(report, self.get_order(report["order"])))

    def delete(self, iuid):
        try:
            self.check_staff()
        except ValueError as error:
            raise tornado.web.HTTPError(403, reason=str(error))
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            raise tornado.web.HTTPError(404, reason=str(error))
        self.delete_logs(report["_id"])
        self.db.delete(report)
        self.set_status(204)    # Empty content.


class ReportEdit(ReportMixin, RequestHandler):
    "Edit a report for an order."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
        try:
            self.check_editable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        self.render(
            "report/edit.html",
            report=report,
            filename=list(report["_attachments"].keys())[0],
            order=self.get_order(report["order"]),
        )

    @tornado.web.authenticated
    def post(self, iuid):
        report = self.get_report(iuid)
        try:
            self.check_editable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        with ReportSaver(doc=report, handler=self) as saver:
            saver["name"] = self.get_argument("name", None) or report["name"]
            try:
                file = self.request.files["file"][0]
            except (KeyError, IndexError):
                pass
            else:
                saver.set_file(
                    dict(
                        body=file.body,
                        filename=file.filename,
                        content_type=file.content_type,
                    )
                )
            saver.set_reviewers(self.get_argument("reviewers", "").split())
            saver.set_status(self.get_argument("status"))
            saver.send_reviewers_message()
        self.see_other("order", self.get_order(report["order"])["identifier"])


class ReportReview(ReportMixin, RequestHandler):
    "Review a report for an order."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
        try:
            self.check_editable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        self.render(
            "report/review.html", report=report, order=self.get_order(report["order"])
        )

    @tornado.web.authenticated
    def post(self, iuid):
        report = self.get_report(iuid)
        try:
            self.check_editable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        order = self.get_order(report["order"])
        try:
            with ReportSaver(doc=report, handler=self) as saver:
                reviewer = saver["reviewers"][self.current_user["email"]]
                reviewer["review"] = saver.handler.get_argument("review", None)
                status = saver.handler.get_argument("status")
                if status not in constants.REPORT_REVIEW_STATUSES:
                    raise ValueError(f"Invalid status '{status}' for report review.")
                reviewer["status"] = status
                saver.set_status()  # Set the status according to all reviews.
                saver.send_owner_message()  # Send message if changed status.
            report = saver.doc
        except (KeyError, ValueError) as error:
            self.see_other("order", order["_id"], error=error)
            return
        self.see_other("order", order["_id"])


class ReportLogs(ReportMixin, RequestHandler):
    "Report log entries display."

    @tornado.web.authenticated
    def get(self, iuid):
        try:
            report = self.get_report(iuid)
        except ValueError as error:
            self.see_other("home", error="Sorry, no such report.")
        try:
            self.check_readable(report)
        except ValueError as error:
            self.see_other("home", error=error)
            return
        title = f"Logs report '{report['name'] or '[no name]'}'"
        self.render("logs.html", title=title, logs=self.get_logs(report["_id"]))


class Reports(RequestHandler):
    "List of reports."

    @tornado.web.authenticated
    def get(self):
        self.check_staff()
        # Count all reports.
        view = self.db.view("report", "order", reduce=True)
        try:
            r = list(view)[0]
        except IndexError:
            all_count = 0
        else:
            all_count = r.value
        kwargs = dict(descending=True, include_docs=True)
        filter = dict(recent=utils.to_bool(self.get_argument("recent", True)))
        if filter["recent"]:
            kwargs["limit"] = settings["DISPLAY_ORDERS_MOST_RECENT"]
        reports = [row.doc for row in self.db.view("report", "modified", **kwargs)]
        for report in reports:
            report["order"] = self.get_order(report["order"])
        self.render(
            "report/list.html", reports=reports, filter=filter, all_count=all_count
        )
