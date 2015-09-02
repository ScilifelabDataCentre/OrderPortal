/* refresh_on_change.js
   Refresh the page when a change in the input element of class "refresh".
*/
$(document).ready(function() {
    $('.refresh').change(function () {
	$('#refresh').submit();
    });
});
