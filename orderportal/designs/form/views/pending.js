/* OrderPortal
   Form documents with 'pending' status indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'pending') emit(doc.modified, doc.title);
}
