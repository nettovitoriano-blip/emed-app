// Get name of this page
  var theloc = document.location;

// Write it to cookie
  var nextyear = new Date();
  nextyear.setFullYear(nextyear.getFullYear() + 5);

    WM_setCookie(ckre,theloc,nextyear.toGMTString(),"/");

