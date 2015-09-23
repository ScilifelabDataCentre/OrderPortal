/* OrderPortal
   Group documents indexed by owner.
   Value: name.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    emit(doc.owner, doc.name);
}
