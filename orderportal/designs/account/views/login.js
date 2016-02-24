/* OrderPortal
   Account documents indexed by login timestamp.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.login) return;
    emit(doc.login, doc.email);
}
