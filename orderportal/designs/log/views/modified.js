/* OrderPortal
   Log documents indexed by modified.
   Value: entity_type.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'log') return;
    emit(doc.modified, doc.entity_type);
}
