foldersTree = gFld("<b><a href=\"index.html\" target=\"lsmain\" class='mapnav'>Home</a></b>", "");

var Root=modules;
for(var i=0;i<Root.length;i++){
 if(Root[i] != ''){
       if(i<9){
         var tmp2String="0";
       }
       else{
         tmp2String="";
       }
       file2String="mod"+tmp2String+(i+1)+"/m"+tmp2String+(i+1)+"_010_000.html";
       RootString="<a href=\""+file2String+"\" target='lsmain'   class='mapnav'>"+Root[i]+"</a>";
       aux1 = insFld(foldersTree, gFld(RootString, ""));
       var SubRoot="m"+tmp2String+(i+1)+"_sections";
       for(var j=0;j<eval(SubRoot+".length");j++){
            file3String="mod"+tmp2String+(i+1)+"/m"+tmp2String+(i+1)+"_"+eval(SubRoot+"[j]")+"_000.html";
            SubRootString="<a href=\""+file3String+"\"  target='lsmain' class='mapnav'>"+eval("m"+tmp2String+(i+1)+"_titles["+j+"]")+"</a>";
            aux2 = insFld(aux1, gFld(SubRootString, ""));
            ArrayName="m"+tmp2String+(i+1)+"_"+eval(SubRoot+"[j]")+"_000";
            if(eval(ArrayName+"[3]")==1){
               for(k=4;k<eval(ArrayName+".length");k++){
                  if(eval(ArrayName+"[k]")!= ''){
                     docArray="m"+tmp2String+(i+1)+"_"+eval(SubRoot+"[j]")+"_"+eval(ArrayName+"[k]");  
                     docString="<span   class='mapnav'>"+eval(docArray+"[0]")+"</span>";
                     fileString="mod"+tmp2String+(i+1)+"/m"+tmp2String+(i+1)+"_"+eval(SubRoot+"[j]")+"_"+eval(ArrayName+"[k]")+".html";
		     insDoc(aux2, gLnk(2,docString,fileString));
                  }
               }
            }
         
       }
  }
}

