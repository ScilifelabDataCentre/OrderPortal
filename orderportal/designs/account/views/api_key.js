/* OrderPortal
   Account documents indexed by API key.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    if (!doc.api_key) return;
    emit(doc.api_key, doc.email);
}
