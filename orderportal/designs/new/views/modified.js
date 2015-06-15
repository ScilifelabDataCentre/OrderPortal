/* OrderPortal
   News documents indexed by 'modified' timestamp.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'new') return; /* Not 'news' ! */
    emit(doc.modified, null);
}
