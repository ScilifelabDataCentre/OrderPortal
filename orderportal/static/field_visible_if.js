/* Change visibility of fields according to select value. */
$(document).ready(function() {
    var set_visible_if = function() {
	var selectId = $(this).attr('id');
	var selectVal = $(this).val();
	$('.field-visible-if').each(function () {
	    if (selectId === $(this).data('select-id')) {
		if (selectVal === $(this).data('select-val')) {
		    $(this).show();
		} else {
		    $(this).hide();
		};
	    };
	});
    };

    $('select').each(set_visible_if);
    $('select').change(set_visible_if);
});
