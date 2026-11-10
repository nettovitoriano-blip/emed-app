// #####################################################
// ## Standard Template
// ## Mod 2
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

var m02_sections = new Array('010'); //Put the sections that are navigable here
var m02_titles = new Array('Section 1 Title'); //Put the sections that are navigable here

var m02_010_000 = new Array('First Page','0','0','1');

