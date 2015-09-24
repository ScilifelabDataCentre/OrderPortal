/* OrderPortal
   Group documents indexed by modified.
   Value: name.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.modified, doc.name);
}
