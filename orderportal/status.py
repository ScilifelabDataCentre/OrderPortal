"Order statuses and transitions."

import copy
import logging
import os.path

import couchdb2
import yaml

from orderportal import constants
from orderportal import saver
from orderportal import settings


class StatusSaver(saver.Saver):
    doctype = constants.META


DEFAULT_ORDER_STATUSES = [
    dict(identifier="preparation",
         enabled=True,          # Must be enabled! Hard-wired into the logic!
         description="The order has been created and is being edited by the user.",
         edit=["user", "staff", "admin"],
         attach=["user", "staff", "admin"],
         action="Prepare"
         ),
    dict(identifier="submitted",
         enabled=True,          # Must be enabled! Hard-wired into the logic!
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
    dict(identifier="halted",
         description="The work on the order has been halted.",
         edit=["admin"],
         attach=["admin"],
         action="Halt"
         ),
    dict(identifier="aborted",
         description="The work on the order has been permanently stopped.",
         edit=["admin"],
         attach=["admin"],
         action="Abort"
         ),
    dict(identifier="terminated",
         description="The order has been terminated.",
         edit=["admin"],
         attach=["admin"],
         action="Terminate"
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
    dict(identifier="completed",
         description="The order has been completed.",
         edit=["admin"],
         attach=["admin"],
         action="Complete"
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


# Minimal, since only 'preparation' and 'submitted' are guaranteed to be enabled.

DEFAULT_ORDER_TRANSITIONS = [
    dict(source="preparation",
         targets=["submitted"],
         permission=["user", "admin", "staff"],
         require="valid"
         ),
]


def load_order_statuses(db):
    """Load the order statuses and transitions from the database.
    If not there, get from legacy site YAML files.
    If none, then use default values.
    Save to database, if from default and/or old site setup files.
    Once saved to the database, the legacy site YAML files will no longer
    be used and can be deleted.
    """
    try:
        # From version 6.0.0, the order statuses are in the database.
        doc = db["order_statuses"]
        settings["ORDER_STATUSES"] = doc["statuses"]
        settings["ORDER_TRANSITIONS"] = doc["transitions"]
        logging.info("loaded order statuses from database")

    except couchdb2.NotFoundError:
        # Create the order statuses document in the database.

        # Start with default order statuses setup.
        settings["ORDER_STATUSES"] = copy.deepcopy(DEFAULT_ORDER_STATUSES)
        lookup = dict([(s["identifier"], s) for s in settings["ORDER_STATUSES"]])

        # Load the legacy site order_statuses.yaml file, if any.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_STATUSES_FILE"])
            with open(filepath) as infile:
                legacy_statuses = yaml.safe_load(infile)
            logging.info(f"read legacy order statuses: {filepath}")
        except (KeyError, FileNotFoundError) as error:
            logging.warning(f"defaults used for order statuses; {error}")
        else:
            # Transfer order status data from the legacy setup and flag as enabled.
            lookup = dict([(s["identifier"], s) for s in settings["ORDER_STATUSES"]])
            for status in legacy_statuses:
                try:
                    lookup[status["identifier"]].update(status)
                    lookup[status["identifier"]]["enabled"] = True
                except KeyError:
                    logging.error(f"""unknown legacy order status: '{status["identifier"]}'; skipped""")

        # Start with the default order transitions setup.
        settings["ORDER_TRANSITIONS"] = copy.deepcopy(DEFAULT_ORDER_TRANSITIONS)

        # Load the legacy site order_transitions.yaml file, if any.
        try:
            filepath = os.path.join(settings["SITE_DIR"], settings["ORDER_TRANSITIONS_FILE"])
            with open(filepath) as infile:
                legacy_transitions = yaml.safe_load(infile)
            logging.info(f"loaded legacy order transitions: {filepath}")
        except (KeyError, FileNotFoundError) as error:
            logging.warning(f"defaults used for order transitions; {error}")
        else:
            # Transfer order transitions data from legacy setup.
            for legacy_trans in legacy_transitions:
                # Silently eliminate unknown target statues.
                legacy_trans["targets"] = [t for t in legacy_trans["targets"]
                                           if t in lookup]
                for trans in settings["ORDER_TRANSITIONS"]:
                    if legacy_trans["source"] == trans["source"]:
                        trans.update(legacy_trans)
                        break
                else:
                    settings["ORDER_TRANSITIONS"].append(legacy_trans)

        # Save current setup into database.
        doc = {"_id": "order_statuses",
               constants.DOCTYPE: constants.META,
               "statuses": settings["ORDER_STATUSES"],
               "transitions": settings["ORDER_TRANSITIONS"]}
        with StatusSaver(doc, db=db):
            pass
        logging.info("saved order statuses to database")

    # Lookup for the enabled statuses.
    settings["ORDER_STATUSES_LOOKUP"] = dict([(s["identifier"], s)
                                              for s in settings["ORDER_STATUSES"]
                                              if s.get("enabled")])

    # Find the initial status: Ensure that there is one and only one.
    initial = None
    for status in settings["ORDER_STATUSES_LOOKUP"].values():
        if status.get("initial"):
            if initial:
                status.pop("initial")
            else:
                initial = status

    # No initial state defined; set 'preparation' to be it.
    if initial is None:
        initial = settings["ORDER_STATUSES_LOOKUP"]["preparation"]
        initial["initial"] = True
        # Save modified setup into database.
        # The doc was either retrieved or already saved above.
        with StatusSaver(doc, db=db):
            pass
        logging.info("saved order statuses to database after setting 'preparation' to initial")

    settings["ORDER_STATUS_INITIAL"] = initial
    
