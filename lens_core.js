"use strict";

(function(root){
  function profileNode(graph,profileId){
    return (graph.nodes||[]).find(function(node){
      return node.type==="profile" &&
        node.attributes &&
        (node.attributes.profile_id===profileId || node.label===profileId);
    })||null;
  }

  function resolveProfileComponents(graph,profileId){
    const out=new Set(),seen=new Set();
    function visit(id){
      if(!id||seen.has(id)) return;
      seen.add(id);
      const node=profileNode(graph,id);
      if(!node) return;
      const attrs=node.attributes||{};
      (attrs.components||[]).forEach(function(component){out.add(component);});
      if(attrs.extends) visit(attrs.extends);
    }
    visit(profileId);
    return [...out].sort();
  }

  function relevantNodeIds(graph,profileId,maxDepth){
    const components=new Set(resolveProfileComponents(graph,profileId));
    const nodes=graph.nodes||[], edges=graph.edges||[];
    const byId=new Map(nodes.map(function(node){return [node.id,node];}));
    const selected=new Set();
    components.forEach(function(component){
      selected.add("z0://component/"+component);
    });
    const p=profileNode(graph,profileId);
    if(p) selected.add(p.id);

    const adjacency=new Map();
    function add(id,row){
      if(!adjacency.has(id)) adjacency.set(id,[]);
      adjacency.get(id).push(row);
    }
    edges.forEach(function(edge){
      add(edge.source,{id:edge.target,edge:edge});
      add(edge.target,{id:edge.source,edge:edge});
    });

    let frontier=[...selected].map(function(id){return {id:id,depth:0};});
    const depthLimit=maxDepth==null?2:maxDepth;
    while(frontier.length){
      const current=frontier.shift();
      if(current.depth>=depthLimit) continue;
      (adjacency.get(current.id)||[]).forEach(function(row){
        if(selected.has(row.id)) return;
        const node=byId.get(row.id);
        if(!node) return;
        if(node.type==="component"){
          const cid=node.attributes&&node.attributes.component_id;
          if(!components.has(cid)) return;
        }
        if(node.type==="evidence_reference" && current.depth<1) return;
        selected.add(row.id);
        frontier.push({id:row.id,depth:current.depth+1});
      });
    }
    return [...selected];
  }

  function truthClass(node){
    const prov=node&&node.provenance||[];
    return prov.length?(prov[0].class||null):null;
  }

  const api={
    resolveProfileComponents:resolveProfileComponents,
    relevantNodeIds:relevantNodeIds,
    truthClass:truthClass
  };
  root.z0LensCore=api;
  if(typeof module!=="undefined"&&module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
