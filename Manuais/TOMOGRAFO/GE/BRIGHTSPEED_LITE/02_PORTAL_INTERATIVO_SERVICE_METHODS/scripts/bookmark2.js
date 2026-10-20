if (WM_readCookie(ckbk)!= '' )
      						{
      						 document.write("<a href=\"javascript:;\" onClick=\"MM_callJS('setBookmark()')\"><img src='../images/bookmark_button1_on.gif' width='12' height='12' alt='Set Bookmark' border='0' name='bk'/></a>");
						 document.write("<a href=\"somewhere\" onClick=\"openBookmark(); return false\"><img src='../images/bookmark_icon2_on.gif' width='12' height='12' alt='Goto Bookmark' border='0' name='bkm'></a>"); 
     						}
	  					else
      						{
      						document.write("<a href=\"javascript:;\" onClick=\"MM_callJS('setBookmark()')\"><img src='../images/bookmark_button1_off.gif' width='12' height='12' alt='Set Bookmark' border='0' name='bk'/></a>");
      						document.write("<img src='../images/bookmark_icon2_off.gif' width='12' height='12' alt='Goto Bookmark' border='0' name='bkm'/>");
      						}
