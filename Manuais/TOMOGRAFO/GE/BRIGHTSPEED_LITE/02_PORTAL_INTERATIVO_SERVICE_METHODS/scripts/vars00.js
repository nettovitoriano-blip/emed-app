// #####################################################
// ## Standard Template
// ## Mod 0
// ## Variable File
// ## Course Overview
// ## Feb. 2002
// ## Zhaohui.Wang@med.ge.com
// #####################################################
// If names have parenthesis, they must be escaped i.e. \(name\)
// m01 = module #;  010_000 = section# then page#;
// The end of each Module gets a 2 in the last variable of the last array.  
// The 1 in the first page of a new topic means that it is included in the site map
// Page Text (Current Page Title, Next Page Code, Previous Page Code, Special Instructions);
// ALWAYS make the first section in a module "010"!!! This is required for the module links to work correctly.
// The first page in a section ALWAYS ends in _000

var m00_sections = new Array('010','020','030','040','050','060','070'); //Put the sections that are navigable here
//var m00_titles = new Array('Welcome','Course Information','Plug-Ins','Optimized Viewing','Icons','Navigation & Features','End of Overview'); //Put the sections that are navigable here

var m00_010_000 = new Array('Welcome','0','m00_020_000','1');

var m00_020_000 = new Array('Course Information','m00_010_000','m00_020_010','1','010','020');
var m00_020_010 = new Array('Course Information','m00_020_000','m00_030_000','');

var m00_030_000 = new Array('Plug-Ins','m00_020_010','m00_040_000','1');

var m00_040_000 = new Array('Optimized Viewing','m00_030_000','m00_050_000','1');

var m00_050_000 = new Array('Icons','m00_040_000','m00_060_000','1');

var m00_060_000 = new Array('Navigation & Features','m00_050_000','m00_070_000','1');

var m00_070_000 = new Array('End of Overview','m00_060_000','0','2');
