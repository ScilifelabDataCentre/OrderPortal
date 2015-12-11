/* OrderPortal
   Order documents indexed by identifier.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    if (!doc.identifier) return;
    emit(doc.identifier, doc.title);
}
