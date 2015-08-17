/* field_visible_if_select.js
   Change visibility of fields according to select value.
*/
$(document).ready(function() {
    var set_visible_if_select = function() {
	var selectId = $(this).attr('id');
	var selectVal = $(this).val();
	$('.visible-if-select').each(function () {
	    if (selectId === $(this).data('select-id')) {
		if (selectVal === $(this).data('select-val')) {
		    $(this).show('slow');
		} else {
		    $(this).hide();
		};
	    };
	});
    };

    /* Set the initial state. */
    $('select').each(set_visible_if_select);

    /* Change-of-state callback. */
    $('select').change(set_visible_if_select);
});
