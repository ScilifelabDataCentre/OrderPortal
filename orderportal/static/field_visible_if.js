/* field_visible_if.js
   Change visibility of fields according to value of another field.
*/
$(document).ready(function() {
    var set_visible_if = function() {
	var fieldId = $(this).attr('id');
	var fieldType = $(this).attr('type');
	var fieldVal = $(this).val();
	var fieldChecked = $(this).is(':checked');
	$('.visible-if').each(function () {
	    if (fieldId === $(this).data('if-id')) {
		/* Explicit cast to string, since 'true' is interpreted. */
		var thisValue = String($(this).data('if-val'));
		var theseValues = thisValue.split('|');
		if (fieldType === 'checkbox') {
		    if (thisValue === 'true') {
			if (fieldChecked) {
			    $(this).show('slow');
			} else {
			    $(this).hide('slow');
			};
		    } else if (thisValue === 'false') {
			if (fieldChecked) {
			    $(this).hide('slow');
			} else {
			    $(this).show('slow');
			};
		    };
		} else {
		    if (theseValues.indexOf(fieldVal) > -1) {
			$(this).show('slow');
		    } else {
			$(this).hide('slow');
		    };
		};
	    };
	});
    };

    /* Set the initial state for source input elements. */
    $('.visible-if-source').each(set_visible_if);

    /* Change-of-state callback for source input element. */
    $('.visible-if-source').change(set_visible_if);
});
