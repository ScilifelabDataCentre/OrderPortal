/* OrderPortal
   Text documents indexed by name.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'text') return;
    emit(doc.name, null);
}
