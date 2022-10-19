"Order statuses and transitions."

import copy
import logging

import couchdb2
import yaml

from orderportal import saver
from orderportal import settings


class StatusSaver(saver.Saver):
    doctype = constants.META


DEFAULT_ORDER_STATUSES = [
    dict(identifier="preparation",
         enabled=True,          # This is hard-wired into the logic of the system!
         initial=True,
         description="The order has been created and is being edited by the user.",
         edit=["user", "staff", "admin"],
         attach=["user", "staff", "admin"],
         action="Prepare"
         ),
    dict(identifier="submitted",
         enabled=True,          # This is hard-wired into the logic of the system!
         description="The order has been submitted by the user for consideration.",
         edit=["staff", "admin"],
         attach=["staff", "admin"],
         action="Submit"
         ),
    dict(identifier="review",
         description="The order is under review.",
         edit=["staff", "admin"],
         attach=["staff", "admin"],
         action="Review"
         ),
    dict(identifier="queued",
         description="The order has been queued.",
         edit=["admin"],
         attach=["admin"],
         action="Queue"
         ),
    dict(identifier="waiting",
         description="The order is waiting.",
         edit=["admin"],
         attach=["admin"],
         action="Wait"
         ),
    dict(identifier="accepted",
         description="The order has been checked and accepted.",
         edit=["admin"],
         attach=["admin"],
         action="Accept"
         ),
    dict(identifier="rejected",
         description="The order has been rejected.",
         edit=["admin"],
         attach=["admin"],
         action="Reject"
         ),
    dict(identifier="processing",
         description="The order is being processed in the lab.",
         edit=["admin"],
         attach=["admin"],
         action="Process"
         ),
    dict(identifier="active",
         description="The order is active.",
         edit=["admin"],
         attach=["admin"],
         action="Active"
         ),
    dict(identifier="analysis",
         description="The order results are being analysed.",
         edit=["admin"],
         attach=["admin"],
         action="Analyse"
         ),
    dict(identifier="onhold",
         description="The order is on hold.",
         edit=["admin"],
         attach=["admin"],
         action="On hold"
         ),
    dict(identifier="aborted",
         description="The work on the order has been permanently stopped.",
         edit=["admin"],
         attach=["admin"],
         action="Abort"
         ),
    dict(identifier="cancelled",
         description="The order has cancelled.",
         edit=["admin"],
         attach=["admin"],
         action="Cancel"
         ),
    dict(identifier="finished",
         description="The work on the order has finished.",
         edit=["admin"],
         attach=["admin"],
         action="Finish"
         ),
    dict(identifier="closed",
         description="All work and other actions for the order have been performed.",
         edit=["admin"],
         attach=["admin"],
         action="Closed"
         ),
    dict(identifier="delivered",
         description="The order results have been delivered.",
         edit=["admin"],
         attach=["admin"],
         action="Deliver"
         ),
    dict(identifier="invoiced",
         description="The order has been invoiced.",
         edit=["admin"],
         attach=["admin"],
         action="Invoice"
         ),
    dict(identifier="archived",
         description="The order has been archived.",
         edit=["admin"],
         attach=["admin"],
         action="Archive"
         ),
]


# Bare bones, since only 'preparation' and 'submitted' are guaranteed to exist.

DEFAULT_ORDER_TRANSITIONS = [
    dict(source="preparation",
         targets=["submitted"],
         permission=["user", "admin", "staff"],
         require="valid"
         ),
]


def load_order_statuses(db):
    """Load the order statuses and transitions from the database.
    If not there, get from old site setup files.
    If none, then use default values.
    Save to database, if from default and/or old site setup files.
    """
    legacy_statuses = []
    legacy_transitions = []
    try:
        doc = db["order_statuses"]
        orig_doc = copy.deepcopy(doc)
        settings["ORDER_STATUSES"] = doc["statuses"]
        settings["ORDER_TRANSITIONS"] = doc["transitions"]
        logging.info("loaded order statuses from database")
    except (couchdb2.NotFoundError, KeyError):
        # Get legacy order statuses, or use the defaults.
        settings["ORDER_STATUSES"] = copy.deepcopy(DEFAULT_ORDER_STATUSES)
        # Load the legacy 'site/order_statuses.yaml' file, if any.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_STATUSES_FILE"])
            with open(filepath) as infile:
                legacy_statuses = yaml.safe_load(infile)
            logging.info(f"loaded legacy order statuses: {filepath}")
        except FileNotFoundError as error:
            logging.warning(f"defaults used for order statuses; {error}")

        # Get legacy order transitions, or use defaults.
        settings["ORDER_TRANSITIONS"] = copy.deepcopy(DEFAULT_ORDER_TRANSITIONS)
        # Load the legacy 'site/order_transitions.yaml' file, if any.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_TRANSITIONS_FILE"])
            with open(filepath) as infile:
                legacy_transitions = yaml.safe_load(infile)
            logging.info(f"loaded legacy order transitions: {filepath}")
        except FileNotFoundError as error:
            logging.warning(f"defaults used for order transitions; {error}")

        orig_doc = {}           # Dummy, to trigger save into database.
        doc = dict(statuses=settings["ORDER_STATUSES"],
                   transitions=settings["ORDER_TRANSITIONS"])

    # Order statuses lookup setup.
    settings["ORDER_STATUSES_LOOKUP"] = dict([(s["identifier"], s)
                                              for s in settings["ORDER_STATUSES"]])

    # Handle legacy order statuses, if any.
    for status in legacy_statuses:
        if status["identifier"] in lookup:
            status["enabled"] = True
        else:
            logging.error(f"legacy status {status['identifier']} not in order statuses")
    for status in settings["ORDER_STATUSES"]:
        if status.get("initial"):
            settings["ORDER_STATUS_INITIAL"] = status
            break
    else:
        # Hard-setting initial status to 'preparation', if not set.
        status = settings["ORDER_STATUSES_LOOKUP"]["preparation"]
        status["initial"] = True
        settings["ORDER_STATUS_INITIAL"] = status

    # Handle legacy order transitions, if any.
    try:
        for transition in legacy_transitions:
            if transition["source"] not in lookup:
                raise KeyError(f"no such transition source {transition['source']}")
            for target in transition["targets"]:
                if target not in lookup:
                    raise KeyError(f"no such transition target {target}")
            for permission in transition["permission"]:
                if permission not in constanct.ACCOUNT_ROLES:
                    raise KeyError(f"no such transition permission role {permission}")
            if transition.get("require") and transition["require"] != "valid":
                raise KeyError(f"invalid 'require' value: {transition['require']}")
    except KeyError as error:
        logging.error(f"ignored legacy transitions: {error}")
    else:
        doc["transitions"] = legacy_transitions

    if doc != orig_doc:
        with StatusSaver(doc, db=db):
            pass
        logging.info("saved order statuses to database")
