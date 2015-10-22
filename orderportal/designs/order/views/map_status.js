/* OrderPortal
   Order documents indexed by status and modified timestamp.
   Value: 1.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.status, doc.modified], 1);
}
