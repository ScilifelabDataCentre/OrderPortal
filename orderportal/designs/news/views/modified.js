/* OrderPortal
   News documents indexed by 'modified' timestamp.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'news') return;
    emit(doc.modified, null);
}
