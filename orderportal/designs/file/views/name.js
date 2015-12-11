/* OrderPortal
   File documents indexed by name.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'file') return;
    emit(doc.name, null);
}
