/* OrderPortal
   Group documents indexed by modified.
   Value: 1.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.modified, 1);
}
