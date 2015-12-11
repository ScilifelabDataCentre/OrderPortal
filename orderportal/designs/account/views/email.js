/* OrderPortal
   Account documents indexed by email address.
   Value: first and last names.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    emit(doc.email, [doc.first_name, doc.last_name]);
}
