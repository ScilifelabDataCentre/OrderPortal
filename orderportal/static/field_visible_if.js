/* field_visible_if.js
   Change visibility of fields according to value of another field.
*/
$(document).ready(function() {
    var set_visible_if = function() {
	var fieldId = $(this).attr('id');
	var fieldVal = $(this).val();
	$('.visible-if').each(function () {
	    if (fieldId === $(this).data('if-id')) {
		/* Cast explicitly to string, since 'true' is interpreted. */
		var theseValues = String($(this).data('if-val')).split('|');
		if (theseValues.indexOf(fieldVal) > -1) {
		    $(this).show('slow');
		} else {
		    $(this).hide('slow');
		};
	    };
	});
    };

    /* Set the initial state for source input elements. */
    $('.visible-if-source').each(set_visible_if);

    /* Change-of-state callback for source input element. */
    $('.visible-if-source').change(set_visible_if);
});
