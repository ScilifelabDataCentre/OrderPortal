/* OrderPortal
   Log login_failure documents by entity (account) IUID and modified.
   Value: login_failure value, which is the account email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    if (!doc.changed.login_failure) return;
    emit([doc.entity, doc.modified], doc.changed.login_failure);
}
