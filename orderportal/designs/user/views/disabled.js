/* OrderPortal
   User documents with 'disabled' status indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    if (doc.status === 'disabled') emit(doc.email, null);
}
