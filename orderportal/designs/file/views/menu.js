/* OrderPortal
   File documents indexed by menu position.
   Value: name.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'file') return;
    if (doc.menu) emit(doc.menu, doc.name);
}
