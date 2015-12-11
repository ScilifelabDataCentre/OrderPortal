/* OrderPortal
   Events documents indexed by date.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'event') return;
    emit(doc.date, doc.title);
}
