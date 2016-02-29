/* quit_through_submit.js
   Force using submit or cancel to navigate away from page.
*/
$(window).on("beforeunload", function() {
    return "Form data has not been saved! Leave this page only via the Submit or Cancel buttons!";
});
        
$(document).ready(function() {
    $(".myForm").on("submit", function(e) {
        //remove the ev
        $(window).off("beforeunload");
        return true;
    });
});
