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
        logger.info("Updated 'account' design document.")
    if db.put_design("event", EVENT_DESIGN_DOC):
        logger.info("Updated 'event' design document.")
    if db.put_design("file", FILE_DESIGN_DOC):
        logger.info("Updated 'file' design document.")
    if db.put_design("form", FORM_DESIGN_DOC):
        logger.info("Updated 'form' design document.")
    if db.put_design("group", GROUP_DESIGN_DOC):
        logger.info("Updated 'group' design document.")
    if db.put_design("info", INFO_DESIGN_DOC):
        logger.info("Updated 'info' design document.")
    if db.put_design("log", LOG_DESIGN_DOC):
        logger.info("Updated 'log' design document.")
    if db.put_design("message", MESSAGE_DESIGN_DOC):
        logger.info("Updated 'message' design document.")
    if db.put_design("meta", META_DESIGN_DOC):
        logger.info("Updated 'meta' design document.")
    if db.put_design("news", NEWS_DESIGN_DOC):
        logger.info("Updated 'news' design document.")
    # Replace variables in the function body according to constants.
    mapfunc = ORDER_DESIGN_DOC["views"]["keyword"]["map"]
    delims_lint = "".join(constants.ORDERS_SEARCH_DELIMS_LINT)
    lint = "{%s}" % ", ".join(["'%s': 1" % w for w in constants.ORDERS_SEARCH_LINT])
    ORDER_DESIGN_DOC["views"]["keyword"]["map"] = mapfunc.format(
        delims_lint=delims_lint, lint=lint
    )
    if db.put_design("order", ORDER_DESIGN_DOC):
        logger.info("Updated 'order' design document.")
    if db.put_design("report", REPORT_DESIGN_DOC):
        logger.info("Updated 'report' design document.")
    if db.put_design("text", TEXT_DESIGN_DOC):
        logger.info("Updated 'text' design document.")


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
    if not identifier:  # If empty string, database info is returned.
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

EVENT_DESIGN_DOC = {
    "views": {
        "date": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'event') return;
    emit(doc.date, doc.title);
}"""
        }
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

NEWS_DESIGN_DOC = {
    "views": {
        "modified": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'news') return;
    emit(doc.modified, null);
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
        "keyword": {  # order/keyword
            # NOTE: The 'map' function body is modified in 'update_design_documents'.
            "map": """function(doc) {{
    if (doc.orderportal_doctype !== 'order') return;
    var cleaned = doc.title.replace(/[{delims_lint}]/g, " ").toLowerCase();
    var words = cleaned.split(/\s+/);
    words.forEach(function(word) {{
        if (word.length >= 2 && !lint[word]) emit(word, doc.title);
    }});
}};
var lint = {lint};
"""
        },
        "modified": {
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.modified, doc.title);
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
	emit(tag.toLowerCase(), doc.title);
	var parts = tag.split(':');
	if (parts.length === 2) {
	    emit(parts[1].toLowerCase(), doc.title);
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
    }
}

REPORT_DESIGN_DOC = {
    "views": {
        "order": {
            "reduce": "_count",
            "map": """function(doc) {
    if (doc.orderportal_doctype !== 'report') return;
    emit(doc.order, doc.modified);
}"""
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
