"use strict";

let hierarchyWaveState={
  data:null,
  fingerprint:null,
  timer:null,
  initialized:false
};

function ensureHierarchyUI(){
  let button=$("#hierarchybtn");
  if(!button){
    const nav=$("#nav");
    if(!nav) return null;
    button=document.createElement("button");
    button.id="hierarchybtn";
    button.className="wide";
    button.textContent="hierarchy";
    button.disabled=true;
    nav.insertBefore(button,$("#editbtn")||nav.firstChild);
  }

  let panel=$("#hierarchypanel");
  if(!panel){
    panel=document.createElement("div");
    panel.id="hierarchypanel";
    panel.innerHTML=
      '<div class="hierarchy-head">'+
        '<div><b>slow hierarchy wave</b><span id="hierarchydecision"></span></div>'+
        '<button id="hierarchyclose">×</button>'+
      '</div>'+
      '<div id="hierarchymetrics"></div>'+
      '<div id="hierarchyrows"></div>'+
      '<div class="hierarchy-note">Advisory only. z0 remains canonical; proposals cannot be applied from z0archy.</div>';
    document.body.appendChild(panel);
  }

  if(!$("#hierarchystyle")){
    const style=document.createElement("style");
    style.id="hierarchystyle";
    style.textContent=
      '#hierarchypanel{position:fixed;top:70px;right:20px;z-index:45;width:min(470px,calc(100vw - 40px));max-height:calc(100vh - 110px);overflow:auto;background:rgba(255,255,255,.98);border:1px solid #E7E3D9;border-radius:14px;box-shadow:0 12px 40px rgba(29,31,35,.13);padding:13px;display:none;font-family:ui-monospace,Menlo,Consolas,monospace}'+
      '#hierarchypanel.open{display:block}'+
      '.hierarchy-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;margin-bottom:10px}'+
      '.hierarchy-head b{font:600 14px Helvetica,Arial,sans-serif;color:#1D1F23}'+
      '.hierarchy-head span{display:block;margin-top:3px;font-size:10px;color:#62666F}'+
      '.hierarchy-head button{border:0;background:transparent;font-size:20px;cursor:pointer;color:#62666F}'+
      '#hierarchymetrics{font-size:9.5px;color:#62666F;padding:7px 9px;background:#F8F7F3;border-radius:8px;margin-bottom:9px}'+
      '.hierarchy-row{border:1px solid #E7E3D9;border-radius:9px;padding:9px;margin:7px 0;background:#fff}'+
      '.hierarchy-row.merge,.hierarchy-row.split{border-color:#8B5CF6}'+
      '.hierarchy-row.prune{border-color:#C05684}'+
      '.hierarchy-row.keep{border-color:#5E9430}'+
      '.hierarchy-row.no_update{border-style:dashed}'+
      '.hierarchy-action{display:flex;justify-content:space-between;gap:8px;font-size:10px;text-transform:uppercase;letter-spacing:.05em;color:#62666F}'+
      '.hierarchy-reason{font:12px Helvetica,Arial,sans-serif;line-height:1.4;color:#1D1F23;margin:6px 0}'+
      '.hierarchy-subjects{display:flex;flex-wrap:wrap;gap:5px}'+
      '.hierarchy-subjects button{border:1px solid #E7E3D9;background:#F8F7F3;border-radius:999px;padding:4px 7px;font:9px ui-monospace,Menlo,Consolas,monospace;cursor:pointer;max-width:100%;overflow:hidden;text-overflow:ellipsis}'+
      '.hierarchy-evidence{margin-top:6px;font-size:9px;line-height:1.45;color:#62666F;white-space:pre-wrap}'+
      '.hierarchy-note{font-size:9px;color:#9BA0A8;line-height:1.5;margin-top:10px}';
    document.head.appendChild(style);
  }

  button.onclick=function(){panel.classList.toggle("open");};
  $("#hierarchyclose").onclick=function(){panel.classList.remove("open");};
  hierarchyWaveState.initialized=true;
  return button;
}

async function fetchHierarchyWave(){
  try{
    const response=await fetch("./generated/hierarchy-wave.json",{cache:"no-store"});
    return response.ok?await response.json():null;
  }catch(_){
    return null;
  }
}

function hierarchyWaveFingerprint(data){
  if(!data) return null;
  return JSON.stringify([
    data.decision,
    data.episodeCount,
    data.conceptCount,
    data.metrics,
    (data.proposals||[]).map(function(row){
      return [row.action,row.subjects,row.confidence,row.evidence];
    })
  ]);
}

async function refreshHierarchyWave(){
  const button=ensureHierarchyUI();
  if(!button) return;
  const data=await fetchHierarchyWave();
  if(!data){
    hierarchyWaveState.data=null;
    hierarchyWaveState.fingerprint=null;
    button.disabled=true;
    button.textContent="hierarchy";
    const panel=$("#hierarchypanel");
    if(panel) panel.classList.remove("open");
    return;
  }
  const fingerprint=hierarchyWaveFingerprint(data);
  hierarchyWaveState.data=data;
  button.disabled=false;
  const structural=(data.metrics||{}).mergeProposalCount+
    (data.metrics||{}).splitProposalCount+
    (data.metrics||{}).pruneProposalCount;
  button.textContent=data.decision==="UPDATE"
    ?"hierarchy · "+structural+" Δ"
    :"hierarchy · stable";
  if(fingerprint!==hierarchyWaveState.fingerprint){
    hierarchyWaveState.fingerprint=fingerprint;
    renderHierarchyWave(data);
  }
}

function renderHierarchyWave(data){
  const decision=$("#hierarchydecision"),metrics=$("#hierarchymetrics"),rows=$("#hierarchyrows");
  if(!decision||!metrics||!rows) return;
  decision.textContent=
    (data.decision||"NO UPDATE")+" · "+(data.episodeCount||0)+" episodes · "+
    (data.conceptCount||0)+" concepts";
  const m=data.metrics||{};
  metrics.textContent=[
    "observed "+(m.observedConceptCount||0),
    "entropy "+Number(m.episodeConceptEntropyBits||0).toFixed(2)+" bits",
    "merge "+(m.mergeProposalCount||0),
    "split "+(m.splitProposalCount||0),
    "prune "+(m.pruneProposalCount||0),
    "keep "+(m.keepProposalCount||0)
  ].join(" · ");

  rows.innerHTML="";
  (data.proposals||[]).forEach(function(proposal){
    const row=document.createElement("div");
    row.className="hierarchy-row "+proposal.action;
    const head=document.createElement("div");
    head.className="hierarchy-action";
    head.innerHTML="<b>"+escapeHierarchy(proposal.action)+"</b><span>"+
      Math.round(Number(proposal.confidence||0)*100)+"%</span>";
    row.appendChild(head);

    const reason=document.createElement("div");
    reason.className="hierarchy-reason";
    reason.textContent=proposal.reason||"";
    row.appendChild(reason);

    if((proposal.subjects||[]).length){
      const subjects=document.createElement("div");
      subjects.className="hierarchy-subjects";
      proposal.subjects.forEach(function(subject){
        const button=document.createElement("button");
        button.textContent=shortHierarchyId(subject);
        button.title=subject;
        button.onclick=function(){hierarchyTravel(subject);};
        subjects.appendChild(button);
      });
      row.appendChild(subjects);
    }

    const evidence=document.createElement("div");
    evidence.className="hierarchy-evidence";
    evidence.textContent=hierarchyEvidenceText(proposal.evidence||{});
    if(evidence.textContent) row.appendChild(evidence);
    rows.appendChild(row);
  });
}

function hierarchyEvidenceText(evidence){
  const lines=[];
  [
    ["episode Jaccard","episodeJaccard"],
    ["structural Jaccard","structuralJaccard"],
    ["shared episodes","sharedEpisodeCount"],
    ["episode count","episodeCount"],
    ["degree","degree"],
    ["context entropy bits","contextEntropyBits"],
    ["cross Jaccard","crossJaccard"]
  ].forEach(function(pair){
    if(evidence[pair[1]]!=null) lines.push(pair[0]+": "+evidence[pair[1]]);
  });
  ["clusterA","clusterB"].forEach(function(key){
    const cluster=evidence[key];
    if(!cluster) return;
    lines.push(key+" episodes: "+(cluster.episodeIds||[]).length+
      " · within "+Number(cluster.withinJaccard||0).toFixed(2));
  });
  if((evidence.episodeIds||[]).length){
    lines.push("episodes: "+evidence.episodeIds.slice(0,6).join(", "));
  }
  return lines.join("\n");
}

function hierarchyTravel(graphId){
  if(typeof nodes==="undefined") return;
  const runtime=Object.values(nodes).find(function(node){
    return node.def&&node.def.meta&&node.def.meta.graphId===graphId;
  });
  if(!runtime){
    toast("concept is not in the current deck view");
    return;
  }
  $("#hierarchypanel").classList.remove("open");
  travelTo(runtime.id);
  if(runtime.def.tip) setTimeout(function(){showTip(runtime);},350);
}

function shortHierarchyId(value){
  const raw=String(value||"");
  const slash=raw.lastIndexOf("/");
  return slash>=0?raw.slice(slash+1):raw;
}

function escapeHierarchy(value){
  return String(value||"")
    .replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

async function initHierarchyWave(){
  ensureHierarchyUI();
  await refreshHierarchyWave();
  if(!hierarchyWaveState.timer){
    hierarchyWaveState.timer=setInterval(refreshHierarchyWave,3000);
  }
}

addEventListener("z0archy:boot",function(){void initHierarchyWave();});
