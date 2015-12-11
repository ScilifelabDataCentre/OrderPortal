/* OrderPortal
   Form documents indexed by modified timestamp.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'form') return;
    emit(doc.modified, doc.title);
}
