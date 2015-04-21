/* OrderPortal
   Form documents with 'enabled' status indexed by modified time stamp.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    if (doc.status === 'enabled') emit(doc.modified, doc.title);
}
