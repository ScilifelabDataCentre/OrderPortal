/* OrderPortal
   Account documents indexed by last name.
   Value: email.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'account') return;
    if (doc.last_name) emit(doc.last_name, doc.email);
}
