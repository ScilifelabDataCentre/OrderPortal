/* OrderPortal
   Account documents indexed by role.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.role, doc.email);
}
