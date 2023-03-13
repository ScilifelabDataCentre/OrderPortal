/* field_table_edit.js
   Help function for editing the values of an order input field of type 'table'.
*/
function field_table_add_row(event)
{
  var tableid = "_table_" + event.data.tableid;
  var countid = tableid + "_count";
  // Get current number of rows from hidden input field value.
  var count = parseInt($("#" + countid).attr('value'));
  // Edit the HTML code for the row: set the row identifier (number).
  var rowid = tableid + "_" + count;
  $("#" + tableid).append(event.data.tableinput.replace(/rowid/g, rowid));
  count = count + 1;
  //  Update the hidden input value for the current number of rows.
  $("#" + countid).attr('value', count);
  // Display the number of the created row.
  $("#" + rowid + "__").html(count);
  // Attach datepicker, if any.
  $(".datepicker").datepicker();
  // For ease of input, set focus to the first cell of the added row.
  $("#" + rowid + "_0").focus();
}
