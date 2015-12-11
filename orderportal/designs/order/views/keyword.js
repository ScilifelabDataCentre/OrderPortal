/* OrderPortal
   Order documents indexed by keywords; title split up.
   Value: title.
*/
function(doc) {
    if (doc.orderportal_doctype !== 'order') return;
    // Keep this in sync with Search.get in search.py
    var cleaned = doc.title.replace(/[:,;']/g, " ").toLowerCase();
    var words = cleaned.split(/\s+/);
    words.forEach(function(word) {
	if (word.length >= 2 && !lint[word]) emit(word, doc.title);
    });
}
// This is hopefully evaluated only once...
var lint = {'an': 1, 'to': 1, 'in': 1, 'on': 1, 'of': 1,
	    'and': 1, 'the': 1, 'was': 1, 'not': 1};
