"CouchDB design documents (view index definitions)."

import logging

import couchdb

from . import constants
from . import settings

DESIGNS = dict(

    account=dict(
        api_key=dict(map=       # account/api_key
"""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.api_key) return;
    emit(doc.api_key, doc.email);
}"""),
        email=dict(map=         # account/email
"""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.email, [doc.first_name, doc.last_name]);
}"""),
        role=dict(map=          # account/role
"""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.role, doc.email);
}"""),
        status=dict(map=        # account/status
"""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.status, doc.email);
}"""),
        university=dict(map=    # account/university
"""function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.university, doc.email);
}""")),

    event=dict(
        date=dict(map=          # event/date
"""function(doc) {
    if (doc.orderportal_doctype !== 'event') return;
    emit(doc.date, doc.title);
}""")),

    file=dict(
        name=dict(map=          # file/name
"""function(doc) {
    if (doc.orderportal_doctype !== 'file') return;
    emit(doc.name, null);
}""")),

    form=dict(
        enabled=dict(map=       # form/enabled
"""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'enabled') emit(doc.modified, doc.title);
}"""),
        modified=dict(map=      # form/modified
"""function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, doc.title);
}""")),

    group=dict(
        invited=dict(map=       # group/invited
"""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.invited.length; i++) {
	emit(doc.invited[i], doc.name);
    };
}"""),
        member=dict(map=        # group/member
"""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.members.length; i++) {
	emit(doc.members[i], doc.name);
    };
}"""),
        modified=dict(reduce="_count", # group/modified
                      map=
"""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.modified, 1);
}"""),
        owner=dict(map=         # group/owner
"""function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.owner, doc.name);
}""")),

    info=dict(
        menu=dict(map=          # info/menu
"""function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    if (doc.menu) emit(doc.menu, [doc.name, doc.title]);
}"""),
        name=dict(map=          # info/name
"""function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    emit(doc.name, null);
}""")),

    log=dict(
        account=dict(map=       # log/account
"""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.account) return;
    emit([doc.account, doc.modified], null);
}"""),
        entity=dict(map=        # log/entity
"""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    emit([doc.entity, doc.modified], null);
}"""),
        login_failure=dict(map= # log/login_failure
"""function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.changed.login_failure) return;
    emit([doc.entity, doc.modified], doc.changed.login_failure);
}""")),

    message=dict(
        recipient=dict(reduce="_count", # message/recipient
                       map=
"""function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    for (var i=0; i<doc.recipients.length; i++) {
	emit([doc.recipients[i], doc.modified], 1);
    };
}""")),

    meta=dict(
        id=dict(map=            # meta/id
"""function(doc) {
    if (doc.orderportal_doctype !== 'meta') return;
    emit(doc._id, null);
}""")),

    news=dict(
        modified=dict(map=      # news/modified
"""function(doc) {
    if (doc.orderportal_doctype !== 'news') return;
    emit(doc.modified, null);
}""")),

    order=dict(
        form=dict(reduce="_count", # order/form
                  map=
"""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.form, doc.modified], 1);
}"""),
        identifier=dict(map=    # order/identifier
"""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.identifier) return;
    emit(doc.identifier, doc.title);
}"""),
        keyword=dict(map=       # order/keyword; Special treatment below !!!
"""function(doc) {{
    if (doc.orderportal_doctype !== 'order') return;
    var cleaned = doc.title.replace(/[{delims_lint}]/g, " ").toLowerCase();
    var words = cleaned.split(/\s+/);
    words.forEach(function(word) {{
	if (word.length >= 2 && !lint[word]) emit(word, doc.title);
    }});
}};
var lint = {lint};
"""),
        modified=dict(map=      # order/modified
"""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.modified, doc.title);
}"""),
        owner=dict(reduce="_count", # order/owner
                   map=
"""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.owner, doc.modified], 1);
}"""),
        status=dict(reduce="_count", # order/status
                    map=
"""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.status, doc.modified], 1);
}"""),
        tag=dict(map=           # order/tag
"""function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.tags) return;
    doc.tags.forEach(function(tag) {
	emit(tag.toLowerCase(), doc.title);
	var parts = tag.split(':');
	if (parts.length === 2) {
	    emit(parts[1].toLowerCase(), doc.title);
	};
    });
}""")),

    text=dict(
        name=dict(map=          # text/map
"""function(doc) {
    if (doc.orderportal_doctype !== 'text') return;
    emit(doc.name, doc.modified);
}""")))


# Double {{ and }} are converted to single such by .format
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
    delims_lint = ''.join(settings['ORDERS_SEARCH_DELIMS_LINT'])
    lint = "{%s}" % ', '.join(["'%s': 1" % w
                               for w in settings['ORDERS_SEARCH_LINT']])
    # Special treatment !!!
    func = DESIGNS['order']['keyword']['map']
    DESIGNS['order']['keyword']['map'] = func.format(delims_lint=delims_lint,
                                                     lint=lint)
    items = DESIGNS.items()
    fields = dict()
    for field in settings['ORDERS_SEARCH_FIELDS']:
        if not constants.ID_RX.match(field):
            logging.debug("IGNORED search field %s invalid identifier.", field)
            continue
        fields[field] = dict(map=ORDERS_SEARCH_FIELDS_MAP.format(
            fieldid=field,
            delims_lint=delims_lint,
            lint=lint))
    items.append(('fields', fields))
    for entity, designs in items:
         updated = update_design_document(db, entity, designs)
         if updated:
            for view in designs:
                name = "%s/%s" % (entity, view)
                logging.info("regenerating index for view %s" % name)
                list(db.view(name, limit=10))

def update_design_document(db, design, views):
    "Update the design document (view index definition)."
    docid = "_design/%s" % design
    try:
        doc = db[docid]
    except couchdb.http.ResourceNotFound:
        logging.info("loading design document %s", docid)
        db.save(dict(_id=docid, views=views))
        return True
    else:
        if doc['views'] != views:
            doc['views'] = views
            logging.info("updating design document %s", docid)
            db.save(doc)
            return True
        return False
