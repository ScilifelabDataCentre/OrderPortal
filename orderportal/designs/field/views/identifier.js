/* OrderPortal
   Field documents indexed by identifier.
   Value: null.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'field') return;
    emit(doc.identifier, null);
}
