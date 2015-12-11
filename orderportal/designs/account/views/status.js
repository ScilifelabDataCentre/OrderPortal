/* OrderPortal
   Account documents indexed by status.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.status, doc.email);
}
