// #####################################################
// ## Standard Template
// ## Mod 1
// ## Variable File
// ## 
// ## Created May 2001 by Dianna S. Musgrave
// ## dianna.musgrave@med.ge.com
// ## Learning Solutions @ GE Medical Systems
// #####################################################
// If names have parenthesis, they must be escaped i.e. \(name\)
// m01 = module #;  010_000 = section# then page#;
// The end of each Module gets a 2 in the last variable of the last array.  
// The 1 in the first page of a new topic means that it is included in the site map
// Page Text (Current Page Title, Next Page Code, Previous Page Code, Special Instructions);
// ALWAYS make the first section in a module "010"!!! This is required for the module links to work correctly.
// The first page in a section ALWAYS ends in _000

var m01_sections = new Array('010','020','030'); //Put the sections that are navigable here
var m01_titles = new Array('Section 1 Title','Section 2 Title','Section 3 Title','Section 4 Title','Section 5 Title'); //Put the sections that are navigable here

var m01_010_000 = new Array('Overview/List of Topics','0','m01_010_010','1','010');
var m01_010_010 = new Array('Objectives','m01_010_000','m01_020_000','');

var m01_020_000 = new Array('Component Overview and this and that and the other etc etc','m01_010_010','m01_030_000','1');

var m01_030_000 = new Array('System Options','m01_020_000','m01_030_010','1','010','020','030','040','050');
var m01_030_010 = new Array('Generator Options','m01_030_000','m01_030_020','');
var m01_030_020 = new Array('Automatic Exposure Control (AEC)','m01_030_010','m01_030_030','');
var m01_030_030 = new Array('TomoLink','m01_030_020','m01_030_040','');
var m01_030_040 = new Array('Table Options','m01_030_030','m01_030_050','');
var m01_030_050 = new Array('Wall Stand Options','m01_030_040','0','2');

