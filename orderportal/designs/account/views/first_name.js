/* OrderPortal
   Account documents indexed by first name.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    if (doc.first_name) emit(doc.first_name, doc.email);
}
