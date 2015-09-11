/* OrderPortal
   Order documents indexed by owner.
   Value: 1.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.owner, 1);
}
