/* OrderPortal
   Form documents with 'disabled' status indexed by modified time stamp.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'disabled') emit(doc.modified, doc.title);
}
