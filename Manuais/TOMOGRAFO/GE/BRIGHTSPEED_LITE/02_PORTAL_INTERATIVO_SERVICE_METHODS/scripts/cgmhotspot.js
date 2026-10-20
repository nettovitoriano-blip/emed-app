document.hotspotAreaMap=new Array();
document.cgmActiveHotSpotId=null;
document.cgmActiveHotSpotObjId=null;



function removeContextM(oId){
		document.getElementById(oId).disposeContextMenu();
		document.cgmActiveHotSpotId=null;
		document.cgmActiveHotSpotObjId=null;
}
	
function createContextM(oId,refId){
	removeContextM(oId);
	registerHotspot(oId,refId);
	var url=document.hotspotAreaMap[document.cgmActiveHotSpotObjId][document.cgmActiveHotSpotId];
	if(url!=null){
		document.getElementById(oId).addContextMenuItem( "Follow link", true );
		document.getElementById(oId).createContextMenu();
	}
}

function registerHotspot(oId,refId){
	document.cgmActiveHotSpotObjId=oId;
	document.cgmActiveHotSpotId=refId;
}

function handleRef(){
	var url=document.hotspotAreaMap[document.cgmActiveHotSpotObjId][document.cgmActiveHotSpotId];
	if(url!=null){
		document.location.href=url;
	}
}

function addMap(strId,map){
	document.hotspotAreaMap[strId]=map;
}

