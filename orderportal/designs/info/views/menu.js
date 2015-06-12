/* OrderPortal
   Info documents indexed by menu position.
   Value: [name, title].
*/
function(doc) {
    if (doc.orderportal_doctype !== 'info') return;
    if (doc.menu) emit(doc.menu, [doc.name, doc.title]);
}
