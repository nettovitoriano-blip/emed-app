function setBookmark(){
  var theloc = document.location;

// Write it to cookie
  var nextyear = new Date();
  nextyear.setFullYear(nextyear.getFullYear() + 5);
  WM_setCookie(ckbk,theloc,nextyear.toGMTString(),"/");
  MM_swapImage('bk','','../main/bookmark_button1_on.gif',1);
  MM_swapImage('bkm','','../main/bookmark_icon2_on.gif',1);
}
function gotoBookmark(){
    window.location.href="../index.htm";
	var theloc = WM_readCookie(ckbk);
    var lastyear = new Date();
    lastyear.setFullYear(lastyear.getFullYear() - 1);
    WM_setCookie(ckbk,' ',lastyear.toGMTString(),"/");
    MM_swapImage('bk','','../main/bookmark_button1_off.gif',1);
    MM_swapImage('bkm','','../main/bookmark_icon2_off.gif',1);
	alert(theloc);
   mainFrame.location=theloc;
}
function openBookmark() {
    var theloc = WM_readCookie(ckbk);
    var lastyear = new Date();
    lastyear.setFullYear(lastyear.getFullYear() - 1);
    WM_setCookie(ckbk,'',lastyear.toGMTString(),"/");
    window.location=theloc;
}
