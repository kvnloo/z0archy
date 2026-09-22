"use strict";

let semanticZoomState={key:null,detail:null,receiptKey:null};

function semanticMetaLevel(nodeRuntime){
  const meta=(nodeRuntime.def&&nodeRuntime.def.meta)||{};
  if(meta.semanticLevel!=null) return Number(meta.semanticLevel);
  if(meta.graphType) return z0SemanticZoomCore.semanticLevelForType(meta.graphType);
  return null;
}

function applySemanticZoom(force){
  if(typeof cam==="undefined"||typeof nodes==="undefined"||typeof scenes==="undefined") return;
  const scene=scenes[cur];
  if(!scene) return;
  const focused=!scene.overview;
  const detail=focused?5:z0SemanticZoomCore.detailLevelForScale(cam.s);
  const key=cur+":"+(focused?"focused":detail);
  if(!force&&semanticZoomState.key===key) return;
  semanticZoomState={key:key,detail:detail};

  Object.values(nodes).forEach(function(n){
    const level=semanticMetaLevel(n);
    const show=z0SemanticZoomCore.shouldShow(level,detail,focused);
    n.el.classList.toggle("semhid",!show);
  });

  edgeObjs.forEach(function(edge){
    const a=nodes[edge.a], b=nodes[edge.b];
    const hide=!a||!b||a.el.classList.contains("semhid")||b.el.classList.contains("semhid");
    edge.p.classList.toggle("semhid",hide);
    if(edge.lab) edge.lab.classList.toggle("semhid",hide);
  });

  const badge=document.querySelector("#semanticbadge");
  if(badge){
    badge.textContent=focused
      ?"focus · full detail"
      :"L"+detail+" · "+z0SemanticZoomCore.labelForDetail(detail);
    badge.dataset.level=String(detail);
  }

  if(scene.overview && typeof z0CompressionCore!=="undefined"){
    void emitSemanticZoomReceipt(detail,key);
  }
}

async function emitSemanticZoomReceipt(detail,key){
  if(semanticZoomState.receiptKey===key) return;
  semanticZoomState.receiptKey=key;
  if(typeof graphForCurrentWorld!=="function") return;
  const graph=await graphForCurrentWorld();
  if(!graph) return;
  const graphIds=new Set((graph.nodes||[]).map(function(n){return n.id;}));
  const selectedIds=[];
  Object.values(nodes).forEach(function(n){
    if(n.el.classList.contains("semhid")) return;
    const meta=(n.def&&n.def.meta)||{};
    if(meta.graphId && graphIds.has(meta.graphId)) selectedIds.push(meta.graphId);
  });
  const scores={};
  (graph.nodes||[]).forEach(function(node){
    scores[node.id]=z0SemanticZoomCore.semanticImportanceForType(node.type);
  });
  const receipt=z0CompressionCore.compressionReceipt(graph,[...new Set(selectedIds)],{
    query:"semantic zoom L"+detail+" · "+z0SemanticZoomCore.labelForDetail(detail),
    scores:scores,
    highScoreThreshold:z0SemanticZoomCore.sufficiencyThresholdForDetail(detail)
  });
  window.dispatchEvent(new CustomEvent("z0archy:compression-receipt",{detail:receipt}));
}

function semanticZoomLoop(){
  applySemanticZoom(false);
  requestAnimationFrame(semanticZoomLoop);
}

addEventListener("z0archy:boot",function(){
  semanticZoomState.key=null;
  semanticZoomState.receiptKey=null;
  requestAnimationFrame(function(){applySemanticZoom(true);});
});

requestAnimationFrame(semanticZoomLoop);
