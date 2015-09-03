/* OrderPortal
   Account documents indexed by email address.
   Value: status.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.email, doc.status);
}
