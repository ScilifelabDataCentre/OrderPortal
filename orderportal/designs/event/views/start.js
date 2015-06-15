/* OrderPortal
   Events documents indexed by start date.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'event') return;
    emit(doc.start, doc.title);
}
