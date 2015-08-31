/* OrderPortal
   User documents indexed by university.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'user') return;
    emit(doc.university, doc.email);
}
