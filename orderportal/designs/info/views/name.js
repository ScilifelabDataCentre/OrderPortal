/* OrderPortal
   Info documents indexed by name.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    emit(doc.name, null);
}
