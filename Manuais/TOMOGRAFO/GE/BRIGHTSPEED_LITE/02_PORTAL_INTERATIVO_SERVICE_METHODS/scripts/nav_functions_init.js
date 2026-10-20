// #######################################################################
// ## Standard Template                                                 ##
// ## Navigation Control Script Variables and Functions			##
// ## Cookies, Resume function and Copyright insertion function		##
// ## This Script // ## Created May 2001 by Dianna S. Musgrave		##
// ## dianna.musgrave@med.ge.com					##
// ## Learning Solutions @ GE Medical Systems				##
// #######################################################################

     var pageName = location.href.substring(location.href.lastIndexOf("/")+1,location.href.lastIndexOf("html")+5);
     var arrayName = location.href.substring(location.href.lastIndexOf("/")+1,location.href.lastIndexOf("html")-1);
     var num = location.href.substring(location.href.lastIndexOf("/")-2,location.href.lastIndexOf("/")) ;
     var modNum = "vars" + num + ".js";
     var sectionNum=location.href.substring(location.href.lastIndexOf("/")+5,location.href.lastIndexOf("/")+8) ;
// Call appropriate Variable file
if (pageName != "index.html") {
      document.write("<script language=\"JavaScript\" src=\"" + "../scripts/" + modNum + "\"></" + "script>");
      }


