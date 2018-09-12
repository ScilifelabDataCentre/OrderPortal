/* table_edit.js
   Edit an input field table.
*/
function table_add_row(event)
{
  var tableid = "_table_" + event.data.tableid;
  var countid = tableid + "_count";
  // Get current number of rows from hidden input value.
  var count = parseInt($("#" + countid).attr('value'));
  // Prepare the HTML code for the row: set the row number.
  var rowid = tableid + "_" + count;
  var rowcode = event.data.rowcode.replace(/rowid/g, rowid);
  $("#" + tableid).append(rowcode);
  count = count + 1;
  //  Update the hidden input value for the current number of rows.
  $("#" + countid).attr('value', count);
  // Display the number of the created row.
  $("#" + rowid + "__").html(count);
  // For ease of input, set focus to the first cell if the added row.
  $("#" + rowid + "_0").focus();
}
