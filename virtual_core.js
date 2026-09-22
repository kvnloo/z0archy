"use strict";

(function(root){
  function clone(value){return JSON.parse(JSON.stringify(value));}

  function branchTarget(repo,branch,index){
    const meta=index&&index.repositories&&index.repositories[repo];
    if(!meta) return null;
    const row=(meta.branches||[]).find(function(b){return b.name===branch;});
    return row&&row.oid?{repo:repo,ref:branch,evidenceKey:row.oid,kind:"branch"}:null;
  }

  function canonicalTarget(repo,canonicalIndex,githubIndex){
    const row=canonicalIndex&&canonicalIndex.repos&&canonicalIndex.repos[repo];
    const pin=row&&(row.pins||[]).find(function(p){return p.resolved&&p.evidenceKey;});
    if(pin){
      return {
        repo:repo,
        ref:pin.branch||pin.ref,
        evidenceKey:pin.evidenceKey,
        canonical:true,
        declared:true,
        component:pin.component
      };
    }
    const meta=githubIndex&&githubIndex.repositories&&githubIndex.repositories[repo];
    if(meta&&meta.defaultHead){
      return {
        repo:repo,
        ref:meta.defaultBranch||"default",
        evidenceKey:meta.defaultHead,
        canonical:false,
        declared:false,
        fallback:true
      };
    }
    return null;
  }

  function mergeEvidence(baseGraph,packs,selection){
    const graph=clone(baseGraph);
    const nodes=new Map((graph.nodes||[]).map(function(n){return [n.id,n];}));
    const edges=new Map((graph.edges||[]).map(function(e){return [e.id,e];}));
    const summaries={};

    Object.keys(packs||{}).sort().forEach(function(repo){
      const pack=packs[repo]||{};
      (pack.nodes||[]).forEach(function(n){nodes.set(n.id,n);});
      (pack.edges||[]).forEach(function(e){edges.set(e.id,e);});
      summaries[repo]=pack.summary||{};
    });

    graph.nodes=[...nodes.values()].sort(function(a,b){return a.id.localeCompare(b.id);});
    graph.edges=[...edges.values()].sort(function(a,b){return a.id.localeCompare(b.id);});
    graph.snapshot={
      generatedAt:new Date().toISOString(),
      truthClass:"derived",
      source:{repo:"z0archy",ref:"browser-virtual"},
      declaredBase:baseGraph.snapshot||null,
      selection:selection
    };
    graph.implementationEvidence=summaries;
    return graph;
  }

  function conceptualEvidence(pack){
    const out={};
    (pack&&pack.nodes||[]).forEach(function(node){
      const a=node.attributes||{};
      if(node.type==="source_artifact"){
        out["artifact:"+(a.path||node.label)]={
          type:node.type,
          hash:a.sha256||null,
          bytes:a.bytes??null,
          role:a.role||null
        };
      } else if(node.type==="package"){
        out["package:"+(a.name||node.label)]={
          type:node.type,
          ecosystem:a.ecosystem||null,
          version:a.version??null
        };
      } else if(node.type==="implementation_manifest"){
        out["manifest"]={type:node.type,attributes:a};
      }
    });
    return out;
  }

  function evidenceDiff(basePack,headPack){
    const a=conceptualEvidence(basePack), b=conceptualEvidence(headPack);
    const ak=new Set(Object.keys(a)), bk=new Set(Object.keys(b));
    const added=[...bk].filter(function(k){return !ak.has(k);}).sort();
    const removed=[...ak].filter(function(k){return !bk.has(k);}).sort();
    const changed=[...ak].filter(function(k){
      return bk.has(k)&&JSON.stringify(a[k])!==JSON.stringify(b[k]);
    }).sort();
    return {added:added,removed:removed,changed:changed,count:added.length+removed.length+changed.length};
  }

  function selectionManifest(rows){
    const repos={};
    Object.keys(rows||{}).sort().forEach(function(repo){
      const row=rows[repo];
      repos[repo]={
        source:"github",
        ref:row.ref,
        resolvedRef:row.evidenceKey,
        canonical:!!row.canonical,
        declared:!!row.declared
      };
    });
    return {version:1,repos:repos};
  }

  const api={
    branchTarget:branchTarget,
    canonicalTarget:canonicalTarget,
    mergeEvidence:mergeEvidence,
    conceptualEvidence:conceptualEvidence,
    evidenceDiff:evidenceDiff,
    selectionManifest:selectionManifest
  };
  root.z0VirtualCore=api;
  if(typeof module!=="undefined"&&module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
