/* OrderPortal
   User documents with 'enabled' status indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    if (doc.status === 'enabled') emit(doc.email, null);
}
