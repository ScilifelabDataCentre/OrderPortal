/* OrderPortal
   Message documents indexed by recipient and modified.
   Value: subject.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    for (var i=0; i<doc.recipients.length; i++) {
	emit([doc.recipients[i], doc.modified], doc.subject);
    };
}
