/* field_visible_if_select.js
   Change visibility of fields according to select value.
*/
$(document).ready(function() {
    var set_visible_if_select = function() {
	var selectId = $(this).attr('id');
	var selectVal = $(this).val();
	$('.visible-if-select').each(function () {
	    if (selectId === $(this).data('select-id')) {
		/* Cast explicitly to string, since 'true' is interpreted. */
		var thisVal = String($(this).data('select-val'));
		if (selectVal === thisVal) {
		    $(this).show('slow');
		} else {
		    $(this).hide('slow');
		};
	    };
	});
    };

    /* Set the initial state. */
    $('select').each(set_visible_if_select);

    /* Change-of-state callback. */
    $('select').change(set_visible_if_select);
});
