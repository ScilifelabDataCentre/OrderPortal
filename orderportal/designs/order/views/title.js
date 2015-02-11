/* OrderPortal
   Order documents indexed by title.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.title, null);
}
