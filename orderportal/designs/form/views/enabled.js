/* OrderPortal
   Form documents with 'enabled' status indexed by email address.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'enabled') emit(doc.modified, doc.title);
}
