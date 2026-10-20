//SET NUMBER OF TABS HERE!!! 
var numberOfTabs=1;
// #############################
// IF MORE THAN 9 TABS, TITLES ARRAY MUST BE MODIFIED
Titles = new Array("menu1");
// #############################
var CurrentLayer="info1";
var layerRef="null",styleSwitch="null";
var visibleVar="null";
var isNav4, isIE4;
var pxSwitch="null";
var ver = parseInt(navigator.appVersion, 10); 
if (navigator.appName == "Netscape") {	
	layerRef="document.layers";
        parentRef="document";
	styleSwitch="";		
	visibleVar="show";	
        hiddenVar="hide";
	isNav4 = true;
}else{		
	layerRef="document.all";
        parentRef="";	
	styleSwitch=".style";
	visibleVar="visible";
        hiddenVar="hidden";	
	isIE4 = true;
}

function showLayer(layerName){
        var status;
        status=eval(layerRef+'["'+layerName+'"]'+styleSwitch+'.visibility');
         if(status=="visible"||status=="show")
        {
            	eval(layerRef+'["'+layerName+'"]'+styleSwitch+'.visibility=hiddenVar');
        }
        else
        {
          for(var i=0;i<numberOfTabs;i++)
          {
             if(layerName==Titles[i])
             {
            	eval(layerRef+'["'+layerName+'"]'+styleSwitch+'.visibility=visibleVar');
             }
             else
             {
             	eval(layerRef+'["'+Titles[i]+'"]'+styleSwitch+'.visibility=hiddenVar');
             }
          }
        }
}

//eFundementals Global functions. -- Oct. 2000

function MM_findObj(n, d) { //v3.0
  var p,i,x;  if(!d) d=document; if((p=n.indexOf("?"))>0&&parent.frames.length) {
    d=parent.frames[n.substring(p+1)].document; n=n.substring(0,p);}
  if(!(x=d[n])&&d.all) x=d.all[n]; for (i=0;!x&&i<d.forms.length;i++) x=d.forms[i][n];
  for(i=0;!x&&d.layers&&i<d.layers.length;i++) x=MM_findObj(n,d.layers[i].document); return x;
}

function MM_showHideLayers() { //v3.0
  var i,p,v,obj,args=MM_showHideLayers.arguments;
  for (i=0; i<(args.length-2); i+=3) if ((obj=MM_findObj(args[i]))!=null) { v=args[i+2];
    if (obj.style) { obj=obj.style; v=(v=='show')?'visible':(v='hide')?'hidden':v; }
    obj.visibility=v; }
}

function MM_swapImgRestore() { //v3.0
  var i,x,a=document.MM_sr; for(i=0;a&&i<a.length&&(x=a[i])&&x.oSrc;i++) x.src=x.oSrc;
}

function MM_preloadImages() { //v3.0
  var d=document; if(d.images){ if(!d.MM_p) d.MM_p=new Array();
    var i,j=d.MM_p.length,a=MM_preloadImages.arguments; for(i=0; i<a.length; i++)
    if (a[i].indexOf("#")!=0){ d.MM_p[j]=new Image; d.MM_p[j++].src=a[i];}}
}

function MM_swapImage() { //v3.0
  var i,j=0,x,a=MM_swapImage.arguments; document.MM_sr=new Array; for(i=0;i<(a.length-2);i+=3)
   if ((x=MM_findObj(a[i]))!=null){document.MM_sr[j++]=x; if(!x.oSrc) x.oSrc=x.src; x.src=a[i+2];}
}

function MM_openBrWindow(theURL,winName,features) { //v2.0
  window.open(theURL,winName,features);
}

// extract front part of string prior to searchString
function getFront(mainStr,searchStr){
	foundOffset = mainStr.indexOf(searchStr)
	if (foundOffset == -1) {
		return null
	}
	return mainStr.substring(0,foundOffset)
}

// extract back end of string after searchString
function getEnd(mainStr,searchStr) {
	foundOffset = mainStr.indexOf(searchStr)
	if (foundOffset == -1) {
		return null
	}
	return mainStr.substring(foundOffset+searchStr.length,mainStr.length)
}

// insert insertString immediately before searchString
function insertString(mainStr,searchStr,insertStr) {
	var front = getFront(mainStr,searchStr)
	var end = getEnd(mainStr,searchStr)
	if (front != null && end != null) {
		return front + insertStr + searchStr + end
	}
	return null
}

// remove deleteString
function deleteString(mainStr,deleteStr) {
	return replaceString(mainStr,deleteStr,"")
}

// replace searchString with replaceString
function replaceString(mainStr,searchStr,replaceStr) {
	var front = getFront(mainStr,searchStr)
	var end = getEnd(mainStr,searchStr)
	if (front != null && end != null) {
		return front + replaceStr + end
	}
	return mainStr;
}
function replaceStringAll(mainStr,searchStr,replaceStr) {
    var front="";
    var end="";
    while(front=="" || end==""){
 	front = getFront(mainStr,searchStr)
	end = getEnd(mainStr,searchStr)
	if (front != null && end != null) {
		mainStr= front + replaceStr + end;
                front="";
                end="";
	}
    }
	return mainStr;
}