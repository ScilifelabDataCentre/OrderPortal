/* OrderPortal
   Form documents with 'pending' status indexed by modified time stamp.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'pending') emit(doc.modified, doc.title);
}
