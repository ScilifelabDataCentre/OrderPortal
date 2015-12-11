/* OrderPortal
   Log documents indexed by entity (IUID) and modified.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    emit([doc.entity, doc.modified], null);
}
