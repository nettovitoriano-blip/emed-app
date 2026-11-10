// ###########################################################################
// ## Standard Template                                                         ##
// ## Navigation Control Script Variables and Functions				##
// ## Cookies, Resume function and Copyright insertion function			##
// ## This Script // ## Created May 2001 by Dianna S. Musgrave			##
// ## dianna.musgrave@med.ge.com						##
// ## Learning Solutions @ GE Medical Systems					##
// ###########################################################################

var SiteName = "Standard Template";
var CreatedBy = "Learning Solutions @ GE Medical Systems";

var sectionArray="m"+num+"_sections";

var prevPage=eval(arrayName+"[1]");
var nextPage=eval(arrayName+"[2]");

function getKey(keyStroke) {
eventChooser = (isNav4) ? keyStroke.which : event.keyCode;
which = String.fromCharCode(eventChooser).toLowerCase();
if(which == 'n'&& nextPage !='0') window.location=nextPage+".html";
else if(which=='p'&& prevPage != '0') window.location=prevPage+".html";
}
document.onkeypress = getKey;