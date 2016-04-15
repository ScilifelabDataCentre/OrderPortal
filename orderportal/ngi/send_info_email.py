# -*- coding: utf-8 -*-
""" OrderPortal: Send an info message to all users.
"""

from __future__ import print_function, absolute_import

import csv
import email.mime.text
import smtplib
import time

from orderportal import settings
from orderportal import utils


SUBJECT = "Information about new order portal for NGI Sweden"
MESSAGE = """Dear user of the National Genomics Infrastructure (NGI) Sweden,

This is to inform you that the current portal for submitting orders to
NGI Sweden will be replaced in about two weeks time.

The new order portal can be viewed at http://ngisweden.scilifelab.se/,
but please wait until the launch before attempting to use it.

The functionality of our new NGI order portal is fairly similar to the
current portal. An important difference is that you need to select the
technology first, and then fill in the order form accordingly. The
visual design has been improved.

Your account and order information will be transferred automatically
to the new order portal. However, you will have to set a new
password. You will receive an email describing how to do this when the
new order portal is launched. Note that your email address will be
used to identify your account; the so-called account name will no
longer be used.

We aim to launch the new order portal on Friday April 29th. You will
receive the email about setting a new password within two working days
from the date of launch.

If you have any questions send an email to support@ngisweden.se

Yours sincerely,

Per Kraulis

-- 
Per Kraulis, Ph.D.
Systems Architect, National Genomics Infrastructure (NGI), SciLifeLab.
Dept Biochemistry and Biophysics, Stockholm University.
+46 (0)70 639 9635   http://kraulis.se/   http://www.scilifelab.se/
Visiting address: Tomtebodavägen 23A, Karolinska Institutet Science Park, Solna
Postal address: SciLifeLab Stockholm, Box 1031, 171 21 Solna, Sweden
"""

def send_info_email(filepath, sender, options):
    "Send the info email to all users in the given CSV file."
    server = get_server()
    recipients = []
    with open(filepath, 'rb') as infile:
        reader = csv.reader(infile)
        reader.next()
        for record in reader:
            recipients.append(record[0])
    for r in [recipients[i:i+20] for i in xrange(0, len(recipients), 20)]:
        send_email(server, sender, recipients, options)
        time.sleep(3.0)
    server.quit()

def send_email(server, sender, recipients, options):
    mail = email.mime.text.MIMEText(MESSAGE)
    mail['Subject'] = SUBJECT
    mail['From'] = sender
    for recipient in recipients:
        mail['To'] = recipient
    if options.verbose:
        print("sent email '{0}' to {1}".format(
                SUBJECT, ', '.join(recipients)))
    if not options.dry_run:
        server.sendmail(sender, recipients, mail.as_string())

def get_server():
    host = settings['EMAIL']['HOST']
    try:
        port = settings['EMAIL']['PORT']
    except KeyError:
        server = smtplib.SMTP(host)
    else:
        server = smtplib.SMTP(host, port=port)
    if settings['EMAIL'].get('TLS'):
        server.starttls()
    try:
        user = settings['EMAIL']['USER']
        password = settings['EMAIL']['PASSWORD']
    except KeyError:
        pass
    else:
        server.login(user, password)
    return server

def get_args():
    parser = utils.get_command_line_parser(description=
        'Send info message to all users.')
    parser.add_option('-d', '--dry-run',
                      action='store_true', dest='dry_run', default=False,
                      help='do not send messages; for debug')
    return parser.parse_args()


if __name__ == '__main__':
    (options, args) = get_args()
    utils.load_settings(filepath=options.settings,
                        verbose=options.verbose)
    send_info_email('accounts.csv',
                    sender='Per Kraulis <per.kraulis@scilifelab.se>',
                    options=options)
