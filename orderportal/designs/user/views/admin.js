/* OrderPortal
   User documents with 'admin' role indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    if (doc.role === 'admin') emit(doc.email, null);
}
