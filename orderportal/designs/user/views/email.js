/* OrderPortal
   User documents indexed by email address.
   Value: status.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    emit(doc.email, doc.status);
}
