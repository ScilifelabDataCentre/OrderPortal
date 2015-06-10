/* OrderPortal
   Events documents indexed by date.
   Skip hidden documents.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'event') return;
    if (doc.hidden) return;
    emit(doc.date, doc.title);
}
