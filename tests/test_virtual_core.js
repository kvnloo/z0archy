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

const driftGraph=v.mergeEvidence(
  {
    snapshot:{},
    nodes:[
      {id:"z0://component/a",type:"component",attributes:{component_id:"a",repo:"o/a"}},
      {id:"z0://component/b",type:"component",attributes:{component_id:"b",repo:"o/b"}}
    ],
    edges:[]
  },
  {
    "o/a":{
      nodes:[{
        id:"z0://package/o/a:pkg-a",type:"package",label:"pkg-a",
        attributes:{name:"pkg-a",repo:"o/a",dependencies:["pkg-b"]},
        provenance:[{class:"implemented",path:"package.json"}]
      }],
      edges:[],summary:{}
    },
    "o/b":{
      nodes:[{
        id:"z0://package/o/b:pkg-b",type:"package",label:"pkg-b",
        attributes:{name:"pkg-b",repo:"o/b",dependencies:[]},
        provenance:[{class:"implemented",path:"package.json"}]
      }],
      edges:[],summary:{}
    }
  },
  {version:1,repos:{}}
);
const derived=driftGraph.edges.filter(function(edge){
  return edge.type==="package_depends_on"&&edge.attributes&&edge.attributes.derivedCrossRepo;
});
assert.strictEqual(derived.length,1);
assert.strictEqual(derived[0].provenance[0].class,"derived");
const findings=v.driftFindings(driftGraph);
assert(findings.some(function(row){
  return row.code==="drift.cross_repo_package_dependency_undeclared";
}));

const declaredBase={
  snapshot:{},
  nodes:[
    {id:"z0://component/a",type:"component",attributes:{component_id:"a",repo:"o/a"}},
    {id:"z0://component/b",type:"component",attributes:{component_id:"b",repo:"o/b"}}
  ],
  edges:[{
    id:"declared-integration",type:"integrates_with",
    source:"z0://component/a",target:"z0://component/b"
  }]
};
const covered=v.mergeEvidence(declaredBase,{
  "o/a":driftGraph.nodes.filter(function(n){return n.id==="z0://package/o/a:pkg-a";}).length?{
    nodes:[driftGraph.nodes.find(function(n){return n.id==="z0://package/o/a:pkg-a";})],edges:[],summary:{}
  }:{nodes:[],edges:[],summary:{}},
  "o/b":{
    nodes:[driftGraph.nodes.find(function(n){return n.id==="z0://package/o/b:pkg-b";})],edges:[],summary:{}
  }
},{version:1,repos:{}});
assert(!v.driftFindings(covered).some(function(row){
  return row.code==="drift.cross_repo_package_dependency_undeclared";
}));

console.log("ok: browser virtual architecture core");
