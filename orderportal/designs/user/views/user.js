/* OrderPortal
   User documents with 'user' role indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    if (doc.role === 'user') emit(doc.email, null);
}
