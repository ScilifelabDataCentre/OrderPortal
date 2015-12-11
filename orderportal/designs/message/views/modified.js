/* OrderPortal
   Message documents indexed by modified timestamp.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'message') return;
    emit(doc.modified, doc.title);
}
