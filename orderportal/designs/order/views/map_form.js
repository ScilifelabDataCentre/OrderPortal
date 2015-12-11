/* OrderPortal
   Order documents indexed by form and modified.
   Value: 1.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit([doc.form, doc.modified], 1);
}
