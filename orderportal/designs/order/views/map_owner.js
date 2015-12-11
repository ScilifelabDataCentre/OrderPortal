/* OrderPortal
   Order documents indexed by owner and modified.
   Value: 1.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.owner, doc.modified], 1);
}
