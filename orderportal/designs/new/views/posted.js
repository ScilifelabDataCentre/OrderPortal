/* OrderPortal
   News documents indexed by modified timestamp.
   Skip hidden documents.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'new') return; /* Not 'news' ! */
    if (doc.hidden) return;
    emit(doc.modified, doc.title);
}
