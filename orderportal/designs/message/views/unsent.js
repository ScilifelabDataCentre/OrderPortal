/* OrderPortal
   Message documents that have not been sent.
   Value: subject.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    if (doc.sent) return;
    emit(doc._id, doc.subject);
}
