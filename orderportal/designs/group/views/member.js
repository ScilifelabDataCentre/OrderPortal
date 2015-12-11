/* OrderPortal
   Group documents indexed by members.
   Value: name.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'group') return;
    for (var i=0; i<doc.members.length; i++) {
	emit(doc.members[i], doc.name);
    };
}
