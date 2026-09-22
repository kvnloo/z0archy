"use strict";

let compressionState={receipt:null};

function setCompressionReceipt(receipt){
  compressionState.receipt=receipt||null;
  window.z0CompressionReceipt=compressionState.receipt;
  renderCompressionReceipt();
}

function compressionPercent(value){
  return Math.round((Number(value)||0)*100)+"%";
}

function compressionList(obj,limit){
  return Object.entries(obj||{})
    .sort(function(a,b){return b[1]-a[1]||a[0].localeCompare(b[0]);})
    .slice(0,limit||8)
    .map(function(row){return row[0]+" · "+row[1];});
}

function renderCompressionReceipt(){
  const receipt=compressionState.receipt;
  const btn=document.querySelector("#mocreceipt");
  const panel=document.querySelector("#compressionpanel");
  const rows=document.querySelector("#compressionrows");
  if(btn){
    btn.disabled=!receipt;
    btn.textContent=receipt
      ?"receipt "+receipt.counts.keptNodes+"/"+receipt.counts.sourceNodes
      :"receipt";
  }
  if(!rows) return;
  rows.innerHTML="";
  if(!receipt){
    if(panel) panel.classList.remove("open");
    return;
  }

  const cards=[
    ["compression",
      (receipt.compression.nodeRatio==null?"n/a":receipt.compression.nodeRatio+"×")+" node compression",
      compressionPercent(receipt.compression.retainedNodeFraction)+" nodes · "+
      compressionPercent(receipt.compression.retainedEdgeFraction)+" relations retained"],
    ["sufficiency",
      receipt.assessment.sufficientForQuery?"sufficient at current threshold":"expand before relying",
      receipt.assessment.reason],
    ["cut boundary",
      receipt.counts.boundaryEdges+" crossing relations",
      "Relations crossing from visible concepts into hidden detail."],
    ["reconstructability",
      receipt.provenance.reconstructable?"reconstructable":"provenance incomplete",
      receipt.provenance.reconstructable
        ?"All visible concepts retain provenance back to the source world."
        :receipt.provenance.keptNodesMissingProvenance.length+" visible nodes lack provenance."],
    ["structural entropy",
      receipt.structuralEntropy.sourceNodeTypeBits+" → "+receipt.structuralEntropy.keptNodeTypeBits+" bits",
      "Shannon entropy of node-type distribution only. This is structural diversity, not semantic information."],
    ["hidden epistemic evidence",
      receipt.omitted.epistemicNodes.length+" nodes",
      receipt.omitted.epistemicNodes.slice(0,5).map(function(x){return x.label;}).join(" · ")||"none"],
    ["hidden detail",
      receipt.counts.hiddenNodes+" nodes",
      compressionList(receipt.omitted.byType,8).join(" · ")||"none"],
    ["highest-scoring omissions",
      receipt.omitted.scored.length+" relevant hidden",
      receipt.omitted.scored.slice(0,6).map(function(x){return x.label+" ("+x.score+")";}).join(" · ")||"none"]
  ];

  cards.forEach(function(card){
    const el=document.createElement("div");
    el.className="compression-row";
    el.innerHTML="<div class='compression-k'>"+escapeCompression(card[0])+"</div>"+
      "<div class='compression-v'>"+escapeCompression(card[1])+"</div>"+
      "<div class='compression-d'>"+escapeCompression(card[2])+"</div>";
    rows.appendChild(el);
  });
}

function escapeCompression(value){
  return String(value==null?"":value)
    .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
    .replaceAll('"',"&quot;");
}

function initCompressionUI(){
  const btn=document.querySelector("#mocreceipt");
  const close=document.querySelector("#compressionclose");
  const panel=document.querySelector("#compressionpanel");
  if(btn){
    btn.onclick=function(){
      if(!compressionState.receipt) return;
      panel.classList.toggle("open");
    };
  }
  if(close) close.onclick=function(){panel.classList.remove("open");};
  renderCompressionReceipt();
}

addEventListener("z0archy:compression-receipt",function(event){
  setCompressionReceipt(event.detail||null);
});
addEventListener("z0archy:boot",initCompressionUI);
