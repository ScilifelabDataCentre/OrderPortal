"Message to account email address; store and send."

import email.message
import smtplib

from orderportal import constants, settings
from orderportal import saver
from orderportal import utils


DESIGN_DOC = {
    "views": {
        "recipient": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    for (var i=0; i<doc.recipients.length; i++) {
	emit([doc.recipients[i], doc.modified], 1);
    };
}"""}
    }
}


class SafeDict(dict):
    def __missing__(self, key):
        return f"[unknown variable {key}]"


class MessageSaver(saver.Saver):
    doctype = constants.MESSAGE

    def initialize(self):
        """Connect to the email server.
        Raises KeyError if email server is badly configured.
        """
        super().initialize()
        try:
            server = settings["MAIL_SERVER"]
            if not server:
                raise KeyError("Email server not configured.")
            sender = settings["MAIL_DEFAULT_SENDER"] or settings["MAIL_USERNAME"]
            if not sender:
                raise KeyError("Email server badly configured.")
            port = int(settings["MAIL_PORT"])
            use_ssl = utils.to_bool(settings["MAIL_USE_SSL"])
            use_tls = utils.to_bool(settings["MAIL_USE_TLS"])
            if use_tls:
                self.server = smtplib.SMTP(server, port=port)
                if settings.get("MAIL_EHLO"):
                    self.server.ehlo(settings["MAIL_EHLO"])
                self.server.starttls()
                if settings.get("MAIL_EHLO"):
                    self.server.ehlo(settings["MAIL_EHLO"])
            elif use_ssl:
                self.server = smtplib.SMTP_SSL(server, port=port)
            else:
                self.server = smtplib.SMTP(server, port=port)
            try:
                username = settings["MAIL_USERNAME"]
                if not username:
                    raise KeyError
                password = settings["MAIL_PASSWORD"]
                if not password:
                    raise KeyError
            except KeyError:
                pass
            else:
                self.server.login(username, password)
            self["sender"] = sender
            self["reply-to"] = settings["MAIL_REPLY_TO"]
        except (ValueError, TypeError, KeyError, smtplib.SMTPException) as error:
            self.handle_error(error)

    def create(self, text, **kwargs):
        "Create the message from the text template and parameters for it."
        site_url = settings["BASE_URL"]
        if settings["BASE_URL_PATH_PREFIX"]:
            site_url = settings["BASE_URL_PATH_PREFIX"] + site_url
        params = SafeDict(
            site=settings["SITE_NAME"],
            site_url=site_url,
            support=settings.get("MAIL_DEFAULT_SENDER") or "[not defined]",
            host=settings.get("SITE_HOST_TITLE") or "[not defined]",
            host_url=settings.get("SITE_HOST_URL") or "[not defined]",
        )
        params.update(kwargs)
        self["subject"] = str(text["subject"]).format_map(params)
        self["text"] = str(text["text"]).format_map(params)

    def send(self, recipients):
        """Send the message to the given recipient email addresses.
        Raises ValueError if some other error.
        """
        if not recipients:
            raise ValueError("No recipients specified.")
        try:
            self["recipients"] = recipients
            message = email.message.EmailMessage()
            message["From"] = self["sender"]
            message["Subject"] = self["subject"]
            if self["reply-to"]:
                message["Reply-To"] = self["reply-to"]
            message["To"] = ", ".join(set(self["recipients"]))
            message.set_content(self["text"])
            self.server.send_message(message)
            self["sent"] = utils.timestamp()
        except smtplib.SMTPException as error:
            self.handle_error(error)

    def handle_error(self, error):
        "Convert into a nicer error message to display."
        try:
            if self.rqh.is_admin():
                msg = str(error)
            else:
                self.rqh.logger.error(f"Email failure: {error}")
                msg = "Contact the admin."
        except AttributeError: # If rqh is None.
            msg = str(error)
        raise ValueError(f"The operation succeeded, but no email could be sent; problem with the email server. {msg}")

    def post_process(self):
        try:
            self.server.quit()
        except (smtplib.SMTPException, AttributeError):
            pass

    def log(self):
        "Do not create any log entry; the message is its own log."
        pass
