/* OrderPortal
   Order documents indexed by form.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    emit(doc.form, doc.title);
}
