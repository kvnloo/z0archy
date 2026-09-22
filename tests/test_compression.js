"use strict";

const assert=require("assert");
const core=require("../compression_core.js");

const graph={
  nodes:[
    {id:"a",type:"component",label:"A",provenance:[{class:"declared"}]},
    {id:"b",type:"mechanism",label:"B",provenance:[{class:"declared"}]},
    {id:"c",type:"evidence_dependency",label:"C",provenance:[{class:"declared"}]},
    {id:"d",type:"repository",label:"D",provenance:[{class:"implemented"}]}
  ],
  edges:[
    {id:"e1",type:"implements",source:"a",target:"b"},
    {id:"e2",type:"verified_via",source:"b",target:"c"},
    {id:"e3",type:"implemented_by",source:"a",target:"d"}
  ]
};

let receipt=core.compressionReceipt(graph,["a","b"],{
  query:"runtime mechanism",
  scores:{a:10,b:8,c:2,d:1},
  highScoreThreshold:6
});
assert.strictEqual(receipt.counts.sourceNodes,4);
assert.strictEqual(receipt.counts.keptNodes,2);
assert.strictEqual(receipt.counts.boundaryEdges,2);
assert.strictEqual(receipt.compression.nodeRatio,2);
assert.strictEqual(receipt.provenance.reconstructable,true);
assert.strictEqual(receipt.assessment.sufficientForQuery,true);
assert.strictEqual(receipt.omitted.epistemicNodes.length,1);
assert(receipt.structuralEntropy.sourceNodeTypeBits>0);

receipt=core.compressionReceipt(graph,["a"],{
  query:"runtime mechanism",
  scores:{a:10,b:9},
  highScoreThreshold:6
});
assert.strictEqual(receipt.assessment.sufficientForQuery,false);
assert.strictEqual(receipt.omitted.highScoring[0].id,"b");

console.log("compression receipt tests: ok");
