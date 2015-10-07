/* OrderPortal
   Message documents indexed by recipient.
   Value: 1.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    for (var i=0; i<doc.recipients.length; i++) {
	emit(doc.recipients[i], 1);
    };
}
