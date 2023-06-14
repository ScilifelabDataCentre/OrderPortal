"CouchDB operations."

import logging

import couchdb2

from orderportal import constants, settings


def get_server():
    "Get a connection to the CouchDB server."
    kwargs = dict(href=settings["DATABASE_SERVER"])
    if settings.get("DATABASE_ACCOUNT") and settings.get("DATABASE_PASSWORD"):
        kwargs["username"] = settings["DATABASE_ACCOUNT"]
        kwargs["password"] = settings["DATABASE_PASSWORD"]
    return couchdb2.Server(**kwargs)


def get_db():
    "Return the handle for the CouchDB database."
    return get_server()[settings["DATABASE_NAME"]]


def update_design_documents(db):
    "Ensure that all CouchDB design documents are current."
    logger = logging.getLogger("orderportal")

    if db.put_design("account", ACCOUNT_DESIGN_DOC):
        logger.info("Updated 'account' CouchDB design document.")
    if db.put_design("file", FILE_DESIGN_DOC):
        logger.info("Updated 'file' CouchDB design document.")
    if db.put_design("form", FORM_DESIGN_DOC):
        logger.info("Updated 'form' CouchDB design document.")
    if db.put_design("group", GROUP_DESIGN_DOC):
        logger.info("Updated 'group' CouchDB design document.")
    if db.put_design("info", INFO_DESIGN_DOC):
        logger.info("Updated 'info' CouchDB design document.")
    if db.put_design("log", LOG_DESIGN_DOC):
        logger.info("Updated 'log' CouchDB design document.")
    if db.put_design("message", MESSAGE_DESIGN_DOC):
        logger.info("Updated 'message' CouchDB design document.")
    if db.put_design("meta", META_DESIGN_DOC):
        logger.info("Updated 'meta' CouchDB design document.")
    if db.put_design("order", ORDER_DESIGN_DOC):
        logger.info("Updated 'order' CouchDB design document.")
    if db.put_design("report", REPORT_DESIGN_DOC):
        logger.info("Updated 'report' CouchDB design document.")
    if db.put_design("text", TEXT_DESIGN_DOC):
        logger.info("Updated 'text' CouchDB design document.")

    # As of version 10.2, the entity types news and event have been scrapped.
    # If the indexes still exist, remove the documents, logs and indexes.
    try:
        news = [row.doc for row in db.view("news", "modified", include_docs=True)]
        for doc in news:
            delete_logs(db, doc["_id"])
            db.delete(doc)
        doc = db.get_design("news")
        db.delete(doc)
        logger.info("Removed obsolete 'news' documents, logs and design document.")
    except couchdb2.NotFoundError:
        pass
    try:
        events = [row.doc for row in db.view("event", "date", include_docs=True)]
        for doc in events:
            delete_logs(db, doc["_id"])
            db.delete(doc)
        doc = db.get_design("event")
        db.delete(doc)
        logger.info("Removed obsolete 'event' documents, logs and design document.")
    except couchdb2.NotFoundError:
        pass


def get_count(db, designname, viewname, key=None):
    "Get the reduce value for the name view and the given key."
    if key is None:
        view = db.view(designname, viewname, reduce=True)
    else:
        view = db.view(designname, viewname, key=key, reduce=True)
    try:
        return list(view)[0].value
    except IndexError:
        return 0


def get_counts(db):
    "Get the counts for the most important types of entities in the database."
    return dict(
        n_orders=get_count(db, "order", "status"),
        n_forms=get_count(db, "form", "all"),
        n_accounts=get_count(db, "account", "all"),
        n_reports=get_count(db, "report", "order"),
        n_documents=len(db),
    )


def lookup_document(db, identifier):
    """Lookup the database document by identifier, else None.
    The identifier may be an account email, account API key, file name, info name,
    order identifier, or '_id' of the CouchDB document.
    """
    if not identifier:  # If empty string, database info is returned. Don't do that.
        return None
    for designname, viewname in [
        ("account", "email"),
        ("account", "api_key"),
        ("file", "name"),
        ("info", "name"),
        ("order", "identifier"),
    ]:
        try:
            view = db.view(
                designname, viewname, key=identifier, reduce=False, include_docs=True
            )
            result = list(view)
            if len(result) == 1:
                return result[0].doc
        except KeyError:
            pass
    try:
        return db[identifier]
    except couchdb2.NotFoundError:
        return None


def delete_logs(db, iuid):
    "Delete the log documents for the given entity IUID."
    view = db.view(
        "log",
        "entity",
        startkey=[iuid],
        endkey=[iuid, constants.CEILING],
        include_docs=True,
    )
    for row in view:
        db.delete(row.doc)


ACCOUNT_DESIGN_DOC = {
    "views": {
        "all": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.modified, null);
}""",
        },
        "api_key": {
            "map": """function(doc) { 
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.api_key) return;
    emit(doc.api_key, doc.email);
}"""
        },
        "email": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.email, [doc.first_name, doc.last_name]);
}"""
        },
        "role": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.role, doc.email);
}"""
        },
        "status": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.status, doc.email);
}"""
        },
        "university": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.university, doc.email);
}"""
        },
        "login": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.login) return;
    emit(doc.login, doc.email);
}"""
        },
    }
}

FILE_DESIGN_DOC = {
    "views": {
        "name": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'file') return;
    emit(doc.name, null);
}"""
        }
    }
}

FORM_DESIGN_DOC = {
    "views": {
        "all": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, null);
}""",
        },
        "enabled": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'enabled') emit(doc.modified, doc.title);
}"""
        },
        "modified": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, doc.title);
}"""
        },
    }
}

GROUP_DESIGN_DOC = {
    "views": {
        "invited": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.invited.length; i++) {
	emit(doc.invited[i], doc.name);
    };
}"""
        },
        "member": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.members.length; i++) {
	emit(doc.members[i], doc.name);
    };
}"""
        },
        "modified": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.modified, 1);
}""",
        },
        "owner": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.owner, doc.name);
}"""
        },
    }
}

INFO_DESIGN_DOC = {
    "views": {
        "menu": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    if (doc.menu) emit(doc.menu, [doc.name, doc.title]);
}"""
        },
        "name": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    emit(doc.name, null);
}"""
        },
    }
}

LOG_DESIGN_DOC = {
    "views": {
        "account": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.account) return;
    emit([doc.account, doc.modified], null);
}"""
        },
        "entity": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    emit([doc.entity, doc.modified], null);
}"""
        },
        "login_failure": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.changed.login_failure) return;
    emit([doc.entity, doc.modified], doc.changed.login_failure);
}"""
        },
    }
}

MESSAGE_DESIGN_DOC = {
    "views": {
        "recipient": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    for (var i=0; i<doc.recipients.length; i++) {
	emit([doc.recipients[i], doc.modified], 1);
    };
}""",
        }
    }
}

META_DESIGN_DOC = {
    "views": {
        "id": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'meta') return;
    emit(doc._id, null);
}"""
        }
    }
}

ORDER_DESIGN_DOC = {
    "views": {
        "form": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.form, doc.modified], 1);
}""",
        },
        "identifier": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.identifier) return;
    emit(doc.identifier, doc.title);
}"""
        },
        "modified": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.modified, doc.identifier);
}"""
        },
        "owner": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.owner, doc.modified], 1);
}""",
        },
        "status": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.status, doc.modified], 1);
}""",
        },
        "tag": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.tags) return;
    doc.tags.forEach(function(tag) {
	emit(tag.toLowerCase(), doc.identifier);
	var parts = tag.split(':');
	if (parts.length === 2) {
	    emit(parts[1].toLowerCase(), doc.identifier);
	};
    });
}"""
        },
        "year_submitted": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.history.submitted) return;
    emit(doc.history.submitted.split('-')[0], 1);
}""",
        },
        "term": {  # order/term
            # NOTE: The 'map' function body is modified below.
            # This is why there have to be double curly-braces here.
            "map": """function(doc) {{
    if (doc.orderportal_doctype !== 'order') return;
    var cleaned = doc.title.replace(/[{delims_lint}]/g, " ").toLowerCase();
    var terms = cleaned.split(/\s+/);
    terms.forEach(function(term) {{
        if (term.length >= 2 && !lint[term]) emit(term, null);
    }});
}};
var lint = {lint};
"""
        },
    }
}

# Replace variables in the function body according to constants.
mapfunc = ORDER_DESIGN_DOC["views"]["term"]["map"]
delims_lint = "".join(constants.ORDERS_SEARCH_DELIMS_LINT)
lint = "{%s}" % ", ".join(["'%s': 1" % w for w in constants.ORDERS_SEARCH_LINT])
ORDER_DESIGN_DOC["views"]["term"]["map"] = mapfunc.format(
    delims_lint=delims_lint, lint=lint
)

REPORT_DESIGN_DOC = {
    "views": {
        "order": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'report') return;
    emit(doc.order, doc.name);
}""",
        },
        "review": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'report') return;
    if (doc.status !== 'review') return;
    for (const key in doc.reviewers) {
      if (doc.reviewers.hasOwnProperty(key)) {
        if (doc.reviewers[key].status == 'review') emit(key, doc.order);
      };
    };
}"""
        },
        "modified": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'report') return;
    emit(doc.modified, doc.name);
}""",
        },
    }
}

TEXT_DESIGN_DOC = {
    "views": {
        "name": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'text') return;
    emit(doc.name, doc.modified);
}"""
        },
        "type": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'text') return;
    emit(doc.type, doc.modified);
}"""
        },
    }
}
