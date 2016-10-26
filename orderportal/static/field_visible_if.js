/* field_visible_if.js
   Change visibility of fields according to value of another field.
*/
$(document).ready(function() {
    var set_visible_if_initial = function() {
	var field = $(this);
	var fieldId = $(this).attr('id');
	var fieldType = $(this).attr('type');
	var fieldValue = $(this).val();
	var fieldChecked = $(this).is(':checked');
	$('.visible-if').each(function () {
	    if (fieldId !== $(this).data('if-id')) return;
	    /* Explicit cast to string, since 'true' is interpreted. */
	    var thisValue = String($(this).data('if-val'));
	    var theseValues = thisValue.split('|');
/*
	    console.log("fieldId " + fieldId + " " + fieldValue + "; " + " " + thisValue + " " + theseValues + " checked=" + fieldChecked);
*/
	    if (fieldType === 'checkbox') {
		if (thisValue === 'true') {
		    if (fieldChecked) {
			$(this).show(0);
		    } else {
			$(this).hide(0);
		    };
		} else if (thisValue === 'false') {
		    if (fieldChecked) {
			$(this).hide(0);
		    } else {
			$(this).show(0);
		    };
		};
	    } else if (fieldType === 'radio') {
		if ($(this).hasClass('radio-tested')) {
		    if (fieldChecked && theseValues.indexOf(fieldValue) > -1) {
/*
			console.log("  show 1");
*/
			$(this).show(0);
		    };
		} else if (!fieldChecked) {
		    $(this).addClass('radio-tested')
/*
		    console.log("  hide 1");
*/
		    $(this).hide(0);
		} else {
		    if (theseValues.indexOf(fieldValue) > -1) {
			$(this).addClass('radio-tested')
/*
			console.log("  show 2");
*/
			$(this).show(0);
		    };
		};
	    } else {
		if (theseValues.indexOf(fieldValue) > -1) {
		    $(this).show(0);
		} else {
		    $(this).hide(0);
		};
	    };
	});
    };
    var set_visible_if = function() {
	var field = $(this);
	var fieldId = $(this).attr('id');
	var fieldType = $(this).attr('type');
	var fieldValue = $(this).val();
	var fieldChecked = $(this).is(':checked');
	$('.visible-if').each(function () {
	    if (fieldId !== $(this).data('if-id')) return;
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
		if (theseValues.indexOf(fieldValue) > -1) {
		    $(this).show('slow');
		} else {
		    $(this).hide('slow');
		};
	    };
	});
    };

    /* Set the initial state for source input elements. */
    $('.visible-if-source').each(set_visible_if_initial);

    /* Change-of-state callback for source input element. */
    $('.visible-if-source').change(set_visible_if);
});
