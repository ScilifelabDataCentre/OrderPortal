/* OrderPortal
   Page documents indexed by name.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'page') return;
    emit(doc.name, null);
}
