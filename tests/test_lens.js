"use strict";

const assert=require("node:assert");
const lens=require("../lens_core.js");

const graph={
  nodes:[
    {id:"z0://component/a",type:"component",label:"A",attributes:{component_id:"a"}},
    {id:"z0://component/b",type:"component",label:"B",attributes:{component_id:"b"}},
    {id:"z0://profile/core",type:"profile",label:"core",attributes:{profile_id:"core",components:["a"]}},
    {id:"z0://profile/full",type:"profile",label:"full",attributes:{profile_id:"full",extends:"core",components:["b"]}},
    {id:"z0://interface/x",type:"interface",label:"x",attributes:{}},
    {id:"z0://repository/o/a",type:"repository",label:"o/a",attributes:{}}
  ],
  edges:[
    {source:"z0://component/a",target:"z0://interface/x",type:"provides"},
    {source:"z0://component/a",target:"z0://repository/o/a",type:"implemented_by"},
    {source:"z0://component/b",target:"z0://interface/x",type:"consumes"}
  ]
};

assert.deepStrictEqual(lens.resolveProfileComponents(graph,"core"),["a"]);
assert.deepStrictEqual(lens.resolveProfileComponents(graph,"full"),["a","b"]);
const ids=new Set(lens.relevantNodeIds(graph,"core",2));
assert(ids.has("z0://component/a"));
assert(ids.has("z0://interface/x"));
assert(ids.has("z0://repository/o/a"));
assert(!ids.has("z0://component/b"));
assert.strictEqual(lens.truthClass({provenance:[{class:"implemented"}]}),"implemented");
console.log("ok: profile/truth lens core");
