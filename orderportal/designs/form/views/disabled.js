/* OrderPortal
   Form documents with 'disabled' status indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'disabled') emit(doc.modified, doc.title);
}
