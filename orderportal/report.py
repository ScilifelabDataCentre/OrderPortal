"An order may have reports attached, which may go through a workflow for approval."

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

    def set_reviewers(self, reviewers):
        """Set the reviewers of this report. List of email addresses given.
        Accounts that are not enabled or staff or admin are ignored.
        """
        for reviewer in reviewers:
            try:
                account = self.handler.get_account(reviewer)
                if account["status"] != constants.ENABLED:
                    continue
                if account["role"] not in (constants.ADMIN, constants.STAFF):
                    continue
                self["reviewers"][account["email"]] = {"status": constants.REVIEW,
                                                       "review": None,
                                                       "modified": utils.timestamp()}
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


class ReportMixin:
    "Mixin access methods and send email to reviewers."

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

    def send_reviewers_message(self, report, order):
        "Send an email to the reviewers of the report, if any."
        if not report["reviewers"]:
            return
        try:
            text = settings[constants.REPORT]["reviewers"]
            with MessageSaver(handler=self) as saver:
                saver.create(
                    text,
                    name=report["name"],
                    title=order["title"],
                    url=utils.get_order_url(order)
                )
                saver.send(report["reviewers"])
        except (KeyError, ValueError):
            pass

    def send_owner_message(self, report, order):
        "Send an email to the owner of the report."
        try:
            text = settings[constants.REPORT]["owner"]
            with MessageSaver(handler=self) as saver:
                saver.create(
                    text,
                    name=report["name"],
                    title=order["title"],
                    url=utils.get_order_url(order),
                    status=report["status"]
                )
                saver.send(report["owner"])
        except (KeyError, ValueError):
            pass


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
            self.see_other("home", error=f"Sorry, no such { utils.terminology('order') }.")
            return
        try:
            file = self.request.files["report"][0]
        except (KeyError, IndexError):
            self.see_other("order", order["_id"], error="No report file uploaded.")
            return
        try:
            with ReportSaver(handler=self) as saver:
                saver["order"] = order["_id"]
                saver["name"] = self.get_argument("name", None) or file.filename
                saver.set_owner(self.get_argument("owner", ""))
                saver["inline"] = file.content_type in (constants.HTML_MIMETYPE, constants.TEXT_MIMETYPE)
                saver.set_reviewers(self.get_argument("reviewers", "").split())
                saver.set_status(self.get_argument("status", None))
            report = saver.doc
            if file:
                self.db.put_attachment(
                    report,
                    file.body,
                    filename=file.filename,
                    content_type=file.content_type
                )
        except ValueError as error:
            self.see_other("order", order["_id"], error=error)
            return
        self.send_reviewers_message(report, order)
        self.see_other("order", order["_id"])


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
            order=self.get_order(report["order"])
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
            file = self.request.files["report"][0]
        except (KeyError, IndexError):
            pass
        else:
            try:
                # Remove the old report file before adding the new.
                self.db.delete_attachment(report, report["name"])
                with ReportSaver(doc=report, handler=self) as saver:
                    saver["name"] = file.filename
                    saver["inline"] = file.content_type in (constants.HTML_MIMETYPE, constants.TEXT_MIMETYPE)
                report = saver.doc
                self.db.put_attachment(
                    report,
                    file.body,
                    filename=file.filename,
                    content_type=file.content_type
                )
            except ValueError as error:
                self.see_other("order", order["_id"], error=error)
                return
        # If set to "Review", then clear previous reviews and send email again.
        with ReportSaver(doc=report, handler=self) as saver:
            saver["name"] = self.get_argument("name", None) or report["name"]
            status = self.get_argument("status")
            resend = status == constants.REVIEW and status != report["status"]
            saver.set_reviewers(report["reviewers"].keys())
            saver.set_status(status)
        if resend:
            self.send_reviewers_message(report, order)
        self.see_other("order", order["_id"])


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
            "report/review.html",
            report=report,
            order=self.get_order(report["order"])
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
        original_status = report["status"]
        try:
            with ReportSaver(doc=report, handler=self) as saver:
                reviewer = saver["reviewers"][self.current_user["email"]]
                reviewer["review"] = saver.handler.get_argument("review", None)
                status = saver.handler.get_argument("status")
                if status not in constants.REPORT_REVIEW_STATUSES:
                    raise ValueError(f"Invalid status '{status}' for report review.")
                reviewer["status"] = status
                saver.set_status() # Set the status according to all reviews.
            report = saver.doc
        except (KeyError, ValueError) as error:
            self.see_other("order", order["_id"], error=error)
            return
        if report["status"] != constants.REVIEW and report["status"] != original_status and self.current_user["email"] != report["owner"]:
            self.send_owner_message(report, order)
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
        title = f"Logs for report '{report['name'] or '[no name]'}'"
        self.render("logs.html", title=title, logs=self.get_logs(report["_id"]))
