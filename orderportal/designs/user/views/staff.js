/* OrderPortal
   User documents with 'staff' role indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    if (doc.role === 'staff') emit(doc.email, null);
}
