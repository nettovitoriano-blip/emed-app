// ###########################################################################
// ## Proteus                                                                   ##
// ## Navigation Control Script Variables and Functions						##
// ## Cookies, Resume function and Copyright insertion function				##
// ## This Script // ## Created May 2001 by Dianna S. Musgrave				##
// ## dianna.musgrave@med.ge.com												##
// ## Learning Solutions @ GE Medical Systems								##
// ###########################################################################
var SiteName = "Proteus";
var CreatedBy = "Learning Solutions @ GE Medical Systems";
var modules = new Array('Features and Operation','Module 2');


  var pageName=WM_readCookie('pageName');
  var arrayName=WM_readCookie('arrayName');
  var num=WM_readCookie('num');
var modNum = "vars" + num + ".js";
var modTitle=eval("modules[" + (num-1)+"]");
var sectionTitle=eval("m"+num+"p0_000_000[pageName.substring(pageName.lastIndexOf(\"p\")+1,pageName.lastIndexOf(\"p\")+2)-1]");
var topicTitle=eval("m"+num+"p"+pageName.substring(pageName.lastIndexOf("p")+1,pageName.lastIndexOf("p")+2)+"_"+pageName.substring(pageName.lastIndexOf("_")-3,pageName.lastIndexOf("_"))+"_000[0]");
var prevPage=eval(pageName.substring(pageName.lastIndexOf("p")-2,pageName.lastIndexOf(".html"))+"[1]");
var prevPageNum=prevPage;
  prevPage=prevPage + ".html";
var nextPage=eval(pageName.substring(pageName.lastIndexOf("p")-2,pageName.lastIndexOf(".html"))+"[2]");
var nextPageNum=nextPage;
  nextPage=nextPage + ".html";

var nextText = "Next Page";
  if(eval(arrayName+"[3]")==2){
    nextText = "End of Section: " + sectionTitle;
  }
  if(eval(arrayName+"[3]")==3){
    nextText = "End of Topic: " + topicTitle;
  }
  if(eval(arrayName+"[3]")==4){
    nextText = "End of Module: " + modTitle;
  }
