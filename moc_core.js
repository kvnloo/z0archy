"use strict";

(function(root){
  const STOP=new Set([
    "the","and","for","with","from","that","this","into","what","where","how",
    "does","are","our","all","why","who","when","which","show","map","about"
  ]);

  function tokenize(query){
    return String(query||"")
      .toLowerCase()
      .split(/[^a-z0-9_.:-]+/)
      .map(function(x){return x.trim();})
      .filter(function(x){return x.length>1 && !STOP.has(x);});
  }

  function nodeText(node){
    const attrs=node.attributes||{};
    return {
      label:String(node.label||"").toLowerCase(),
      type:String(node.type||"").replaceAll("_"," ").toLowerCase(),
      attrs:JSON.stringify(attrs).toLowerCase()
    };
  }

  function scoreNode(node,tokens){
    const text=nodeText(node);
    let score=0;
    tokens.forEach(function(token){
      if(text.label.includes(token)) score+=8;
      if(text.type.includes(token)) score+=4;
      if(text.attrs.includes(token)) score+=2;
    });
    if(score>0 && node.type==="evidence_dependency") score+=1;
    return score;
  }

  function edgeWeight(type){
    return {
      "depends_on":6,
      "provides":6,
      "consumes":6,
      "produces_representation":7,
      "encoded_as":5,
      "implemented_by":5,
      "runtime_surface_of":5,
      "verified_via":6,
      "evidence_subject":5,
      "evidence_object":5,
      "compresses_to":8,
      "compiles_to":8,
      "observed_as":8,
      "measured_as":8,
      "decides_to":8
    }[type]||3;
  }

  function compileMoc(graph,query,options){
    const opts=Object.assign({maxNodes:24,maxSeeds:8,maxDepth:2},options||{});
    const tokens=tokenize(query);
    if(!tokens.length) return {query:query,tokens:tokens,nodeIds:[],edges:[],scores:{}};

    const nodes=graph.nodes||[];
    const edges=graph.edges||[];
    const byId=new Map(nodes.map(function(n){return [n.id,n];}));
    const scores={};
    const seeds=[];
    nodes.forEach(function(node){
      const score=scoreNode(node,tokens);
      if(score>0){
        scores[node.id]=score;
        seeds.push({id:node.id,score:score});
      }
    });
    seeds.sort(function(a,b){return b.score-a.score || a.id.localeCompare(b.id);});
    const chosenSeeds=seeds.slice(0,opts.maxSeeds);

    const adjacency=new Map();
    function addAdj(id,row){
      if(!adjacency.has(id)) adjacency.set(id,[]);
      adjacency.get(id).push(row);
    }
    edges.forEach(function(edge){
      if(!byId.has(edge.source)||!byId.has(edge.target)) return;
      addAdj(edge.source,{id:edge.target,edge:edge});
      addAdj(edge.target,{id:edge.source,edge:edge});
    });

    const selected=new Set(chosenSeeds.map(function(x){return x.id;}));
    const queue=[];
    chosenSeeds.forEach(function(seed){
      queue.push({id:seed.id,depth:0,priority:seed.score*10});
    });
    const epistemicIntent=tokens.some(function(t){
      return ["evidence","verify","verification","why","source","provenance","confidence"].includes(t);
    });

    while(queue.length && selected.size<opts.maxNodes){
      queue.sort(function(a,b){return b.priority-a.priority || a.id.localeCompare(b.id);});
      const current=queue.shift();
      if(current.depth>=opts.maxDepth) continue;
      const rows=(adjacency.get(current.id)||[]).slice().sort(function(a,b){
        return edgeWeight(b.edge.type)-edgeWeight(a.edge.type);
      });
      rows.forEach(function(row){
        if(selected.size>=opts.maxNodes || selected.has(row.id)) return;
        const neighbor=byId.get(row.id);
        if(!neighbor) return;
        if(neighbor.type==="evidence_reference" && !epistemicIntent) return;
        selected.add(row.id);
        scores[row.id]=scores[row.id]||0;
        queue.push({
          id:row.id,
          depth:current.depth+1,
          priority:current.priority-edgeWeight(row.edge.type)-(current.depth+1)*2
        });
      });
    }

    const keptEdges=edges.filter(function(edge){
      return selected.has(edge.source)&&selected.has(edge.target);
    });
    const ordered=[...selected].sort(function(a,b){
      return (scores[b]||0)-(scores[a]||0) || a.localeCompare(b);
    });
    return {query:query,tokens:tokens,nodeIds:ordered,edges:keptEdges,scores:scores};
  }

  const api={tokenize:tokenize,scoreNode:scoreNode,compileMoc:compileMoc};
  root.z0MocCore=api;
  if(typeof module!=="undefined" && module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
