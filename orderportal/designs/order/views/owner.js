/* OrderPortal
   Order documents indexed by owner.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.owner, doc.title);
}
