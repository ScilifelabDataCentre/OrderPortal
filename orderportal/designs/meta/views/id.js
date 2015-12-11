/* OrderPortal
   Meta documents indexed by id.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'meta') return;
    emit(doc._id, null);
}
