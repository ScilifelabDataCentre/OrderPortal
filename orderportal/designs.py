"CouchDB design documents (view index definitions)."

import json
import logging

import couchdb2

from . import constants
from . import settings

DESIGNS = dict(
    account=dict(
        all=dict(
            reduce="_count",  # account/all
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.modified, null);
}""",
        ),
        api_key=dict(
            map="""function(doc) { 
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.api_key) return;
    emit(doc.api_key, doc.email);
}"""  # account/api_key
        ),
        email=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.email, [doc.first_name, doc.last_name]);
}"""  # account/email
        ),
        role=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.role, doc.email);
}"""  # account/role
        ),
        status=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.status, doc.email);
}"""  # account/status
        ),
        university=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.university, doc.email);
}"""  # account/university
        ),
    ),
    event=dict(
        date=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'event') return;
    emit(doc.date, doc.title);
}"""  # event/date
        )
    ),
    file=dict(
        name=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'file') return;
    emit(doc.name, null);
}"""  # file/name
        )
    ),
    form=dict(
        all=dict(
            reduce="_count",  # form/all
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, null);
}""",
        ),
        enabled=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'enabled') emit(doc.modified, doc.title);
}"""  # form/enabled
        ),
        modified=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, doc.title);
}"""  # form/modified
        ),
    ),
    group=dict(
        invited=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.invited.length; i++) {
	emit(doc.invited[i], doc.name);
    };
}"""  # group/invited
        ),
        member=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.members.length; i++) {
	emit(doc.members[i], doc.name);
    };
}"""  # group/member
        ),
        modified=dict(
            reduce="_count",  # group/modified
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.modified, 1);
}""",
        ),
        owner=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.owner, doc.name);
}"""  # group/owner
        ),
    ),
    info=dict(
        menu=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    if (doc.menu) emit(doc.menu, [doc.name, doc.title]);
}"""  # info/menu
        ),
        name=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    emit(doc.name, null);
}"""  # info/name
        ),
    ),
    log=dict(
        account=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.account) return;
    emit([doc.account, doc.modified], null);
}"""  # log/account
        ),
        entity=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    emit([doc.entity, doc.modified], null);
}"""  # log/entity
        ),
        login_failure=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.changed.login_failure) return;
    emit([doc.entity, doc.modified], doc.changed.login_failure);
}"""  # log/login_failure
        ),
    ),
    message=dict(
        recipient=dict(
            reduce="_count",  # message/recipient
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    for (var i=0; i<doc.recipients.length; i++) {
	emit([doc.recipients[i], doc.modified], 1);
    };
}""",
        )
    ),
    meta=dict(
        id=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'meta') return;
    emit(doc._id, null);
}"""  # meta/id
        )
    ),
    news=dict(
        modified=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'news') return;
    emit(doc.modified, null);
}"""  # news/modified
        )
    ),
    order=dict(
        form=dict(
            reduce="_count",  # order/form
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.form, doc.modified], 1);
}""",
        ),
        identifier=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.identifier) return;
    emit(doc.identifier, doc.title);
}"""  # order/identifier
        ),
        keyword=dict(
            map="""function(doc) {{
    if (doc.orderportal_doctype !== 'order') return;
    var cleaned = doc.title.replace(/[{delims_lint}]/g, " ").toLowerCase();
    var words = cleaned.split(/\s+/);
    words.forEach(function(word) {{
        if (word.length >= 2 && !lint[word]) emit(word, doc.title);
    }});
}};
var lint = {lint};
"""  # order/keyword; see 'fix_design_documents'!
        ),
        modified=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.modified, doc.title);
}"""  # order/modified
        ),
        owner=dict(
            reduce="_count",  # order/owner
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.owner, doc.modified], 1);
}""",
        ),
        status=dict(
            reduce="_count",  # order/status
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.status, doc.modified], 1);
}""",
        ),
        tag=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.tags) return;
    doc.tags.forEach(function(tag) {
	emit(tag.toLowerCase(), doc.title);
	var parts = tag.split(':');
	if (parts.length === 2) {
	    emit(parts[1].toLowerCase(), doc.title);
	};
    });
}"""  # order/tag
        ),
    ),
    text=dict(
        name=dict(
            map="""function(doc) {
    if (doc.orderportal_doctype !== 'text') return;
    emit(doc.name, doc.modified);
}"""  # text/map
        )
    ),
)


# This will be added to DESIGNS as 'order/fields'. See 'fix_design_documents'.
# Double {{ and }} are converted to single such by .format.
ORDERS_SEARCH_FIELDS_MAP = """function(doc) {{
  if (doc.orderportal_doctype !== 'order') return;
  var value = doc.fields.{fieldid};
  if (!value) return;
  var type = typeof(value);
  if (type === 'string') {{
    var words = value.replace(/[{delims_lint}]/g, " ").toLowerCase().split(/\s+/);
  }} else if (type === 'number') {{
    var words = [value.toString()];
  }} else {{
    var words = value;
  }};
  if (words.length) {{
    words.forEach(function(word) {{
      if (word.length > 2 && !lint[word]) emit(word, null);
    }});
  }};
}};
var lint = {lint};"""


def load_design_documents(db):
    "Load the design documents (view index definitions)."
    fixup_design_documents()
    for designname, views in DESIGNS.items():
        if db.put_design(designname, {"views": views}, rebuild=True):
            logging.info("loaded design %s", designname)


def fixup_design_documents():
    """Replace 'lint' and 'delims_lint' in design view function 'order/keyword'.
    Add the order search field design views.
    Done on first call to load_design_documents.
    """
    if "fields" in DESIGNS:
        return
    delims_lint = "".join(settings["ORDERS_SEARCH_DELIMS_LINT"])
    lint = "{%s}" % ", ".join(["'%s': 1" % w for w in settings["ORDERS_SEARCH_LINT"]])
    func = DESIGNS["order"]["keyword"]["map"]
    DESIGNS["order"]["keyword"]["map"] = func.format(delims_lint=delims_lint, lint=lint)
    fields = dict()
    for field in settings["ORDERS_SEARCH_FIELDS"]:
        if not constants.ID_RX.match(field):
            raise ValueError(f"Invalid identifier in search field '{field}'.")
        fields[field] = dict(
            map=ORDERS_SEARCH_FIELDS_MAP.format(
                fieldid=field, delims_lint=delims_lint, lint=lint
            )
        )
    DESIGNS["fields"] = fields
