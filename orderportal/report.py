"An order may have reports attached, which may go through a workflow for approval."

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

    def set_inline(self, content_type):
        "Set the 'inline' flag according to explicit argument, or content type."
        try:
            self["inline"] = utils.to_bool(self.handler.get_argument("inline"))
        except (tornado.web.MissingArgumentError, ValueError):
            self["inline"] = content_type in (constants.HTML_MIMETYPE, constants.TEXT_MIMETYPE)

    def set_reviewers(self, reviewers):
        """Set the reviewers of this report. List of email addresses given.
        Only enabled staff accounts are accepted.
        """
        for reviewer in reviewers:
            try:
                account = self.handler.get_account(reviewer)
                if account["status"] != constants.ENABLED: continue
                if account["role"] in (constants.ADMIN, constants.STAFF):
                    self["reviewers"][account["email"]] = {"status": constants.REVIEW}
            except ValueError:
                pass

    def set_status(self, status=None):
        """Set the new status of the report.
        If none specified, set according to the presence of reviewers or not.
        If "published" specified, then set so only if all reviewers have approved.
        """
        if status is None:
            if self["reviewers"]:
                self["status"] = constants.REVIEW
            else:
                self["status"] = constants.PREPARATION
        else:
            if status not in constants.REPORT_STATUSES:
                raise ValueError(f"invalid status '{new}'")
            if status == constants.PUBLISHED:
                for reviewer in self["reviewers"].values():
                    if reviewer["status"] != constants.APPROVED:
                        continue
                else:
                    self["status"] = status
            else:
                self["status"] = status


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

    def send_review_messages(self, report):
        "Send message to reviewers."
        if not report["reviewers"]:
            return
        text_template = dict(subject=f"{settings['SITE_NAME']} report review to be done.",
                             text="Dear {site} staff,\n\nThe report '{name}' for order '{title}' requires your review.\n\nSee {url}"
                             )
        with MessageSaver(handler=self) as saver:
            order = self.get_order(report["order"])
            saver.create(
                text_template,
                name=report["name"],
                title=order["title"],
                url=utils.get_order_url(order)
            )
            saver.send(report["reviewers"])


class ReportAdd(ReportMixin, RequestHandler):
    "Add a new report for an report."

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
            self.see_other("order", order["_id"], error="No file uploaded.")
            return
        try:
            with ReportSaver(handler=self) as saver:
                saver["order"] = order["_id"]
                saver["name"] = file.filename
                saver.set_inline(file.content_type)
                saver.set_reviewers(self.get_argument("reviewers", "").split())
                saver.set_status()
            self.db.put_attachment(
                saver.doc,
                file.body,
                filename=file.filename,
                content_type=file.content_type
            )
            self.send_review_messages(saver.doc)
        except ValueError as error:
            self.see_other("order", order["_id"], error=error)
        else:
            self.see_other("order", order["_id"])


class Report(ReportMixin, RequestHandler):
    "Display or download a report for an report, or delete it."

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
        outfile = self.db.get_attachment(report, report["name"])
        content_type = report["_attachments"][report["name"]]["content_type"]
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
            self.set_header("Content-Type", content_type)
            self.set_header(
                "Content-Disposition", f'''attachment; filename="{report['name']}"'''
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
            self.see_other("order", order["_id"], error="No file to upload given.")
            return
        try:
            with ReportSaver(doc=report, handler=self) as saver:
                saver["name"] = file.filename
                saver.set_inline(file.content_type)
            self.db.put_attachment(
                saver.doc,
                file.body,
                filename=file.filename,
                content_type=file.content_type
            )
        except ValueError as error:
            self.see_other("order", order["_id"], error=error)
        else:
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
        try:
            with ReportSaver(doc=report, handler=self) as saver:
                reviewer = saver["reviewers"][self.current_user["email"]]
                reviewer["review"] = saver.handler.get_argument("review", None)
                status = saver.handler.get_argument("status")
                if status in constants.REPORT_REVIEW_STATUSES:
                    reviewer["status"] = status
                else:
                    reviewer["status"] = constants.REVIEW
                # Has the report been rejected? A single rejection is sufficient.
                for review in saver["reviewers"].values():
                    if review.get("status") == constants.REJECTED:
                        saver["status"] = constants.REJECTED
                        break
                else:
                    # If all reviewers have accepted, then publish.
                    for review in saver["reviewers"].values():
                        if review.get("status") != constants.APPROVED:
                            break
                    else:
                        saver["status"] = constants.PUBLISHED
        except (KeyError, ValueError) as error:
            self.see_other("order", order["_id"], error=error)
        else:
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
