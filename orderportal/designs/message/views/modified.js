/* OrderPortal
   Message documents indexed by modified timestamp.
   Value: subject.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    emit(doc.modified, doc.subject);
}
