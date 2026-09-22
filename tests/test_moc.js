"use strict";

const assert=require("node:assert");
const moc=require("../moc_core.js");

const graph={
  nodes:[
    {id:"component:runtime",type:"component",label:"Runtime",attributes:{summary:"agent execution"}},
    {id:"mechanism:compress",type:"mechanism",label:"Context compression",attributes:{purpose:"reduce context"}},
    {id:"representation:raw",type:"representation",label:"Raw context",attributes:{scale:"large"}},
    {id:"representation:pack",type:"representation",label:"ObservationPack",attributes:{summary:"compact context"}},
    {id:"component:unrelated",type:"component",label:"Billing",attributes:{summary:"payments"}}
  ],
  edges:[
    {source:"component:runtime",target:"mechanism:compress",type:"implemented_by"},
    {source:"mechanism:compress",target:"representation:pack",type:"produces_representation"},
    {source:"representation:raw",target:"representation:pack",type:"compresses_to"},
    {source:"component:unrelated",target:"component:runtime",type:"integrates_with"}
  ]
};

const result=moc.compileMoc(graph,"context compression",{maxNodes:4,maxSeeds:2,maxDepth:2});
assert(result.nodeIds.includes("mechanism:compress"));
assert(result.nodeIds.includes("representation:raw")||result.nodeIds.includes("representation:pack"));
assert(!result.nodeIds.includes("component:unrelated"),"bounded MOC should prefer relevant local topology");
assert(result.edges.length>0);
console.log("ok: dynamic MOC compiler");
