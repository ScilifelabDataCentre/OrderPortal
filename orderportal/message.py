"Message to account email address; store and send."

import email.message
import logging
import smtplib

from orderportal import constants
from orderportal import saver
from orderportal import settings
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
        super(MessageSaver, self).initialize()
        self["sender"] = settings["MESSAGE_SENDER_EMAIL"]
        self["reply-to"] = settings["MESSAGE_REPLY_TO_EMAIL"]
        self["sent"] = None

    def create(self, text, **kwargs):
        "Create the message from the text template and parameters for it."
        site_url = settings["BASE_URL"]
        if settings["BASE_URL_PATH_PREFIX"]:
            site_url = settings["BASE_URL_PATH_PREFIX"] + site_url
        params = SafeDict(
            site=settings["SITE_NAME"],
            site_url=site_url,
            support=settings.get("SITE_SUPPORT_EMAIL") or "[not defined]",
            host=settings.get("SITE_HOST_TITLE") or "[not defined]",
            host_url=settings.get("SITE_HOST_URL") or "[not defined]",
        )
        params.update(kwargs)
        self["subject"] = str(text["subject"]).format_map(params)
        self["text"] = str(text["text"]).format_map(params)

    def send(self, recipients):
        """Send the message to the given recipient email addresses.
        Raises KeyError if no email server defined.
        Raises ValueError if some other error.
        """
        try:
            if not settings["EMAIL"]:
                raise KeyError
            host = settings["EMAIL"]["HOST"]
            if not host:
                raise KeyError
        except KeyError:
            raise KeyError(
                "Could not send email; no email server defined. Contact the admin."
            )
        if not recipients:
            raise ValueError("No recipients specified.")
        try:
            self["recipients"] = recipients
            port = settings["EMAIL"].get("PORT", 0)
            if settings["EMAIL"].get("SSL"):
                server = smtplib.SMTP_SSL(host, port=port)
            else:
                server = smtplib.SMTP(host, port=port)
                if settings["EMAIL"].get("TLS"):
                    # XXX Is this the cause of the Google SMTP problem?
                    # server.ehlo()
                    server.starttls()
            try:
                user = settings["EMAIL"]["USER"]
                if not user:
                    raise KeyError
                password = settings["EMAIL"]["PASSWORD"]
                if not password:
                    raise KeyError
            except KeyError:
                pass
            else:
                server.login(user, password)
            message = email.message.EmailMessage()
            message["From"] = self["sender"]
            message["Subject"] = self["subject"]
            if self["reply-to"]:
                message["Reply-To"] = self["reply-to"]
            message["To"] = ", ".join(set(self["recipients"]))
            message.set_content(self["text"])
            server.send_message(message)
            self["sent"] = utils.timestamp()
            # Additional logging info to help sorting out issue with email server.
            logging.info(
                f"""Email "{self['subject']}" from {self['sender']} to {self['recipients']}"""
            )
        except Exception as error:
            logging.error(
                f"""Email "{self['subject']}" failed to {self['recipients']}: {error}"""
            )
            try:
                if self.rqh.is_admin():
                    msg = str(error)
                else:
                    msg = "Contact the admin."
            except AttributeError: # If rqh is None.
                msg = ""
            raise ValueError(f"The operation succeeded, but no email could be sent; problem connecting to the email server. {msg}")

    def post_process(self):
        try:
            self.server.quit()
        except AttributeError:
            pass

    def log(self):
        "Do not create any log entry; the message is its own log."
        pass
