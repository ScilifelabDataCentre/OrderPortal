/* OrderPortal
   Group documents indexed by invited.
   Value: name.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.invited.length; i++) {
	emit(doc.invited[i], doc.name);
    };
}
