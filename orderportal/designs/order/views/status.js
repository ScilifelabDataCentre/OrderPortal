/* OrderPortal
   Order documents indexed by status and modified timestamp.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.status, doc.modified], doc.title);
}
