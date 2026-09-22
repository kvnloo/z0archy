"use strict";

(function(root){
  function shannonEntropy(counts){
    const values=Object.values(counts||{}).map(Number).filter(function(x){return x>0;});
    const total=values.reduce(function(a,b){return a+b;},0);
    if(!total) return 0;
    let h=0;
    values.forEach(function(count){
      const p=count/total;
      h-=p*Math.log2(p);
    });
    return Math.round(h*1000)/1000;
  }

  function countBy(rows,keyFn){
    const out={};
    (rows||[]).forEach(function(row){
      const key=String(keyFn(row)||"unknown");
      out[key]=(out[key]||0)+1;
    });
    return out;
  }

  function truthClass(node){
    const prov=(node.provenance||[])[0]||{};
    return prov.class||"unknown";
  }

  function compressionReceipt(graph,selectedIds,options){
    const opts=Object.assign({
      query:"",
      scores:{},
      epistemicTypes:new Set(["evidence_dependency","evidence_reference"]),
      highScoreThreshold:6
    },options||{});

    const nodes=graph.nodes||[];
    const edges=graph.edges||[];
    const selected=new Set(selectedIds||[]);
    const keptNodes=nodes.filter(function(n){return selected.has(n.id);});
    const hiddenNodes=nodes.filter(function(n){return !selected.has(n.id);});
    const keptEdges=edges.filter(function(e){return selected.has(e.source)&&selected.has(e.target);});
    const boundaryEdges=edges.filter(function(e){
      return selected.has(e.source)!==selected.has(e.target);
    });
    const hiddenEdges=edges.filter(function(e){
      return !selected.has(e.source)&&!selected.has(e.target);
    });

    const omittedScored=hiddenNodes
      .map(function(node){return {id:node.id,label:node.label||node.id,type:node.type,score:Number(opts.scores[node.id]||0)};})
      .filter(function(row){return row.score>0;})
      .sort(function(a,b){return b.score-a.score||a.id.localeCompare(b.id);});

    const hiddenEpistemic=hiddenNodes.filter(function(node){
      return opts.epistemicTypes.has(node.type);
    });
    const hiddenByType=countBy(hiddenNodes,function(n){return n.type;});
    const keptByType=countBy(keptNodes,function(n){return n.type;});
    const allByType=countBy(nodes,function(n){return n.type;});
    const allEdgeByType=countBy(edges,function(e){return e.type;});
    const keptEdgeByType=countBy(keptEdges,function(e){return e.type;});

    const missingProvenance=keptNodes.filter(function(node){
      return !(node.provenance||[]).length;
    });

    const highScoringOmissions=omittedScored.filter(function(row){
      return row.score>=opts.highScoreThreshold;
    });

    const sufficientForQuery=highScoringOmissions.length===0;
    const ratio=keptNodes.length?nodes.length/keptNodes.length:null;

    return {
      schemaVersion:"0.1.0",
      kind:"semantic-compression-receipt",
      query:String(opts.query||""),
      counts:{
        sourceNodes:nodes.length,
        keptNodes:keptNodes.length,
        hiddenNodes:hiddenNodes.length,
        sourceEdges:edges.length,
        keptEdges:keptEdges.length,
        boundaryEdges:boundaryEdges.length,
        hiddenEdges:hiddenEdges.length
      },
      compression:{
        nodeRatio:ratio==null?null:Math.round(ratio*100)/100,
        retainedNodeFraction:nodes.length?Math.round((keptNodes.length/nodes.length)*1000)/1000:1,
        retainedEdgeFraction:edges.length?Math.round((keptEdges.length/edges.length)*1000)/1000:1
      },
      structuralEntropy:{
        sourceNodeTypeBits:shannonEntropy(allByType),
        keptNodeTypeBits:shannonEntropy(keptByType),
        sourceEdgeTypeBits:shannonEntropy(allEdgeByType),
        keptEdgeTypeBits:shannonEntropy(keptEdgeByType)
      },
      omitted:{
        byType:hiddenByType,
        epistemicNodes:hiddenEpistemic.map(function(n){return {id:n.id,label:n.label||n.id,type:n.type};}),
        scored:omittedScored.slice(0,12),
        highScoring:highScoringOmissions.slice(0,12)
      },
      boundary:{
        count:boundaryEdges.length,
        edges:boundaryEdges.slice(0,20).map(function(e){
          return {id:e.id,type:e.type,source:e.source,target:e.target};
        })
      },
      provenance:{
        keptNodesMissingProvenance:missingProvenance.map(function(n){return n.id;}),
        reconstructable:missingProvenance.length===0
      },
      assessment:{
        sufficientForQuery:sufficientForQuery,
        reason:sufficientForQuery
          ?"No omitted node exceeds the high-relevance threshold; hidden detail remains reconstructable from the source graph."
          :"One or more omitted nodes remain highly relevant to the query; expand the map before treating it as sufficient."
      }
    };
  }

  const api={shannonEntropy:shannonEntropy,compressionReceipt:compressionReceipt};
  root.z0CompressionCore=api;
  if(typeof module!=="undefined"&&module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
