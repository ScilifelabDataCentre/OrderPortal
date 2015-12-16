/* OrderPortal
   Text documents indexed by name.
   Value: modified.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'text') return;
    emit(doc.name, doc.modified);
}
