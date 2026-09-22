"use strict";

let hierarchyState={data:null,loaded:false};

async function loadHierarchyProposals(){
  if(hierarchyState.loaded) return hierarchyState.data;
  hierarchyState.loaded=true;
  try{
    const response=await fetch("./generated/hierarchy-proposals.json",{cache:"no-store"});
    hierarchyState.data=response.ok?await response.json():null;
  }catch(_){
    hierarchyState.data=null;
  }
  return hierarchyState.data;
}

function hierarchyActionRank(action){
  return {merge:0,split:1,prune:2,keep:3,no_update:4}[action]??9;
}

function hierarchyPct(value){
  return Math.round((Number(value)||0)*100)+"%";
}

function hierarchyEscape(value){
  return String(value==null?"":value)
    .replaceAll("&","&amp;").replaceAll("<","&lt;").replaceAll(">","&gt;")
    .replaceAll('"',"&quot;");
}

function hierarchyEvidenceSummary(evidence){
  const parts=[];
  if(evidence.neighborJaccard!=null) parts.push("neighbor overlap "+hierarchyPct(evidence.neighborJaccard));
  if(evidence.persistence!=null) parts.push("persistence "+hierarchyPct(evidence.persistence));
  if(evidence.degree!=null) parts.push("degree "+evidence.degree);
  if(evidence.edgeTypeEntropyBits!=null) parts.push("edge entropy "+evidence.edgeTypeEntropyBits+" bits");
  if(evidence.group) parts.push("group "+evidence.group);
  if(evidence.declared===true) parts.push("declared");
  if(evidence.declared===false) parts.push("non-declared");
  return parts.join(" · ");
}

function renderHierarchyProposals(data){
  const rows=document.querySelector("#hierarchyrows");
  const summary=document.querySelector("#hierarchysummary");
  const btn=document.querySelector("#hierarchybtn");
  if(!rows||!summary) return;
  rows.innerHTML="";
  if(!data){
    summary.textContent="proposal artifact unavailable";
    if(btn) btn.disabled=true;
    return;
  }
  if(btn) btn.disabled=false;
  const actions=(data.summary&&data.summary.actions)||{};
  summary.textContent=
    (data.summary?data.summary.proposalCount:0)+" proposals · "+
    (data.snapshotCount||0)+" snapshots · "+
    Object.entries(actions).map(function(row){return row[0]+" "+row[1];}).join(" · ");

  const proposals=(data.proposals||[]).slice().sort(function(a,b){
    return hierarchyActionRank(a.action)-hierarchyActionRank(b.action)
      || Number(b.confidence||0)-Number(a.confidence||0)
      || String(a.id).localeCompare(String(b.id));
  });

  proposals.forEach(function(proposal){
    const row=document.createElement("div");
    row.className="hierarchy-row "+proposal.action;
    const subjects=(proposal.subjects||[]).join(" + ");
    row.innerHTML=
      "<div class='hierarchy-top'><span class='hierarchy-action'>"+hierarchyEscape(proposal.action)+"</span>"+
      "<span class='hierarchy-confidence'>"+hierarchyPct(proposal.confidence)+"</span></div>"+
      "<div class='hierarchy-subject'>"+hierarchyEscape(subjects)+"</div>"+
      "<div class='hierarchy-reason'>"+hierarchyEscape(proposal.reason||"")+"</div>"+
      "<div class='hierarchy-evidence'>"+hierarchyEscape(hierarchyEvidenceSummary(proposal.evidence||{}))+"</div>";
    rows.appendChild(row);
  });
}

async function initHierarchyPanel(){
  const btn=document.querySelector("#hierarchybtn");
  const close=document.querySelector("#hierarchyclose");
  const panel=document.querySelector("#hierarchypanel");
  if(!btn||!close||!panel) return;
  const data=await loadHierarchyProposals();
  renderHierarchyProposals(data);
  btn.onclick=function(){panel.classList.toggle("open");};
  close.onclick=function(){panel.classList.remove("open");};
}

addEventListener("z0archy:boot",function(){void initHierarchyPanel();});
