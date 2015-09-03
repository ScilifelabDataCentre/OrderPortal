/* OrderPortal
   Account documents indexed by university.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.university, doc.email);
}
