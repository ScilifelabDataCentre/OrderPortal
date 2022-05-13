"Message to account email address; store and send."

import email.mime.text
import logging
import smtplib

from orderportal import constants
from orderportal import saver
from orderportal import settings
from orderportal import utils


class MessageSaver(saver.Saver):
    doctype = constants.MESSAGE

    def initialize(self):
        super(MessageSaver, self).initialize()
        self["sender"] = settings["MESSAGE_SENDER_EMAIL"]
        self["sent"] = None

    def create(self, template, **kwargs):
        "Create the message from the template and parameters for it."
        site_url = settings["BASE_URL"]
        if settings["BASE_URL_PATH_PREFIX"]:
            site_url = settings["BASE_URL_PATH_PREFIX"] + site_url
        params = dict(
            site=settings["SITE_NAME"],
            site_url=site_url,
            support=settings.get("SITE_SUPPORT_EMAIL") or "[?]",
            host=settings.get("SITE_HOST_TITLE") or "[?]",
            host_url=settings.get("SITE_HOST_URL") or "[?]",
        )
        params.update(kwargs)
        self["subject"] = str(template["subject"]).format(**params)
        self["text"] = str(template["text"]).format(**params)

    def send(self, recipients):
        "Send the message to the given recipient email addresses."
        try:
            self["recipients"] = recipients
            try:
                host = settings["EMAIL"]["HOST"]
            except KeyError:
                return
            port = settings["EMAIL"].get("PORT", 0)
            if settings["EMAIL"].get("SSL"):
                server = smtplib.SMTP_SSL(host, port=port)
            else:
                server = smtplib.SMTP(host, port=port)
                if settings["EMAIL"].get("TLS"):
                    server.starttls()
            server.ehlo()
            try:
                user = settings["EMAIL"]["USER"]
                password = settings["EMAIL"]["PASSWORD"]
            except KeyError:
                pass
            else:
                server.login(user, password)
            mail = email.mime.text.MIMEText(self["text"], "plain", "utf-8")
            mail["Subject"] = self["subject"]
            mail["From"] = self["sender"]
            for recipient in self["recipients"]:
                mail["To"] = recipient
            server.sendmail(self["sender"], self["recipients"], mail.as_string())
            self["sent"] = utils.timestamp()
        except Exception as msg:
            self["error"] = str(msg)
            logging.error("email failed to %s: %s", self["recipients"], msg)
            raise

    def post_process(self):
        try:
            self.server.quit()
        except AttributeError:
            pass

    def log(self):
        "Do not create any log entry; the message is its own log."
        pass
