"use strict";

const assert=require("node:assert");
const v=require("../virtual_core.js");

const github={repositories:{
  "o/a":{
    defaultBranch:"main",defaultHead:"111",
    branches:[{name:"main",oid:"111"},{name:"feat/x",oid:"222"}]
  },
  "o/b":{
    defaultBranch:"main",defaultHead:"333",
    branches:[{name:"main",oid:"333"}]
  }
}};
const canonical={repos:{
  "o/a":{pins:[{component:"a",branch:"main",ref:"aaa",evidenceKey:"aaa",resolved:true}]},
  "o/b":{pins:[],defaultBranch:"main",defaultHead:"333",canonical:false}
}};

assert.deepStrictEqual(v.canonicalTarget("o/a",canonical,github).evidenceKey,"aaa");
assert.strictEqual(v.canonicalTarget("o/a",canonical,github).declared,true);
assert.strictEqual(v.canonicalTarget("o/b",canonical,github).fallback,true);
assert.strictEqual(v.branchTarget("o/a","feat/x",github).evidenceKey,"222");

const basePack={nodes:[
  {type:"source_artifact",label:"README.md",attributes:{path:"README.md",sha256:"a",bytes:10}},
  {type:"package",label:"pkg",attributes:{name:"pkg",ecosystem:"npm",version:"1"}}
]};
const headPack={nodes:[
  {type:"source_artifact",label:"README.md",attributes:{path:"README.md",sha256:"b",bytes:12}},
  {type:"package",label:"pkg",attributes:{name:"pkg",ecosystem:"npm",version:"1"}},
  {type:"source_artifact",label:"ARCHITECTURE.md",attributes:{path:"ARCHITECTURE.md",sha256:"c",bytes:20}}
]};
const diff=v.evidenceDiff(basePack,headPack);
assert.strictEqual(diff.count,2);
assert.deepStrictEqual(diff.changed,["artifact:README.md"]);
assert.deepStrictEqual(diff.added,["artifact:ARCHITECTURE.md"]);

const graph=v.mergeEvidence(
  {snapshot:{},nodes:[{id:"base",type:"component"}],edges:[]},
  {"o/a":{nodes:[{id:"impl",type:"repo_ref"}],edges:[],summary:{hasReadme:true}}},
  {version:1,repos:{}}
);
assert(graph.nodes.some(function(n){return n.id==="impl";}));
assert.strictEqual(graph.snapshot.truthClass,"derived");

console.log("ok: browser virtual architecture core");
