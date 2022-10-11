"Message to account email address; store and send."

import email.message
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
        self["reply-to"] = settings["MESSAGE_REPLY_TO_EMAIL"] or settings["MESSAGE_SENDER_EMAIL"]
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
        """Send the message to the given recipient email addresses.
        Raises KeyError if no email server defined.
        Raises ValueError if some other error.
        """
        try:
            if not settings["EMAIL"]: raise KeyError
            host = settings["EMAIL"]["HOST"]
            if not host: raise KeyError
        except KeyError:
            raise KeyError("Could not send email; no email server defined. Contact the admin.")
        try:
            self["recipients"] = recipients
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
                if not user: raise KeyError
                password = settings["EMAIL"]["PASSWORD"]
                if not password: raise KeyError
            except KeyError:
                pass
            else:
                server.login(user, password)
            message = email.message.EmailMessage()
            message["From"] = self["sender"]
            message["Subject"] = self["subject"]
            message["Reply-To"] = self["reply-to"]
            message["To"] = ", ".join(set(self["recipients"]))
            message.set_content(self["text"])
            server.send_message(message)
            self["sent"] = utils.timestamp()
            # Additional logging info to help sorting out issue with email server.
            logging.info(f"""Email "{message['Subject']}" from {message['From']} to {message['To']}""")
        except Exception as error:
            logging.error(f"""Email "{message['Subject']}" failed to {self['recipients']}: {error}""")
            raise ValueError(str(error))

    def post_process(self):
        try:
            self.server.quit()
        except AttributeError:
            pass

    def log(self):
        "Do not create any log entry; the message is its own log."
        pass
