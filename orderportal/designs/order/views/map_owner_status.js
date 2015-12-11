/* OrderPortal
   Order documents indexed by owner, status and modified.
   Value: 1.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.owner, doc.status, doc.modified], 1);
}
