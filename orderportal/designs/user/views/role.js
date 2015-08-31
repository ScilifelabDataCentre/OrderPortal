/* OrderPortal
   User documents indexed by role.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    emit(doc.role, doc.email);
}
