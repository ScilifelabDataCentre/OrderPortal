/* quit_through_submit.js
   Force using submit or cancel to navigate away from page.
*/
$(window).on("beforeunload", function() {
    return "Order data has not been saved! Leave this page only via the Save or Cancel buttons!";
});
        
$(function() {
    $(".allow_leaving_without_question").on("submit", function(e) {
        // Remove the event.
        $(window).off("beforeunload");
        return true;
    });
});
