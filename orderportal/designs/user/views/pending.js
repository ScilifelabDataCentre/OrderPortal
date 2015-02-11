/* OrderPortal
   User documents with 'pending' status indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    if (doc.status === 'pending') emit(doc.email, null);
}
