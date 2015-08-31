/* OrderPortal
   User documents indexed by status.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    emit(doc.status, doc.email);
}
