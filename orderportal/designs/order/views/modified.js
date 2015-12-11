/* OrderPortal
   Order documents indexed by modified timestamp.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.modified, doc.title);
}
