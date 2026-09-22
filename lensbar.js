"use strict";

let lensState={graph:null,worldKey:null,canonicalLint:null,lint:null,profile:"all",truth:"all",initialized:false};

async function lensFetchJSON(path){
  try{
    const response=await fetch(path,{cache:"no-store"});
    return response.ok?await response.json():null;
  }catch(_){return null;}
}

async function currentLensWorld(){
  if(typeof historyState!=="undefined"&&historyState.active&&historyState.active!=="live"){
    return {
      key:"history:"+historyState.active,
      graph:await lensFetchJSON("./generated/history/"+encodeURIComponent(historyState.active)+".json")
    };
  }
  if(window.z0VirtualGraph){
    return {key:"virtual:"+JSON.stringify(window.z0VirtualSelection||{}),graph:window.z0VirtualGraph};
  }
  return {key:"canonical",graph:await lensFetchJSON("./generated/graph.json")};
}

async function ensureLensData(){
  const world=await currentLensWorld();
  if(world.key!==lensState.worldKey || !lensState.graph){
    lensState.worldKey=world.key;
    lensState.graph=world.graph;
  }
  if(!lensState.canonicalLint) lensState.canonicalLint=await lensFetchJSON("./generated/lint.json");
  lensState.lint=lensState.canonicalLint||{summary:{},findings:[]};
  if(world.key.startsWith("virtual:") && typeof z0VirtualCore!=="undefined" && z0VirtualCore.driftFindings){
    const drift=z0VirtualCore.driftFindings(lensState.graph);
    const baseFindings=(lensState.canonicalLint&&lensState.canonicalLint.findings||[]).slice();
    const findings=baseFindings.concat(drift);
    const summary={error:0,warning:0,info:0};
    findings.forEach(function(row){summary[row.level]=(summary[row.level]||0)+1;});
    lensState.lint={summary:summary,findings:findings};
  }
  return !!lensState.graph;
}

function populateProfileLens(){
  const select=$("#profilelens");
  if(!select||!lensState.graph) return;
  const previous=lensState.profile;
  select.innerHTML='<option value="all">all profiles</option>';
  (lensState.graph.nodes||[])
    .filter(function(node){return node.type==="profile";})
    .sort(function(a,b){return String(a.label).localeCompare(String(b.label));})
    .forEach(function(node){
      const attrs=node.attributes||{};
      const id=attrs.profile_id||node.label;
      const option=document.createElement("option");
      option.value=id;
      option.textContent=id;
      select.appendChild(option);
    });
  if([...select.options].some(function(o){return o.value===previous;})) select.value=previous;
}

function currentRelevantIds(){
  if(lensState.profile==="all") return null;
  return new Set(z0LensCore.relevantNodeIds(lensState.graph,lensState.profile,2));
}

function nodeLensVisible(runtimeNode,relevant){
  const meta=runtimeNode.def&&runtimeNode.def.meta||{};
  if(meta.graphType==="root") return true;

  if(relevant && meta.graphId && !relevant.has(meta.graphId)) return false;

  if(lensState.truth!=="all"){
    const truth=meta.truthClass;
    if(truth && truth!==lensState.truth) return false;
  }
  return true;
}

function applyLens(){
  if(!lensState.graph||typeof nodes==="undefined") return;
  const relevant=currentRelevantIds();
  Object.values(nodes).forEach(function(node){
    node.el.classList.toggle("lensdim",!nodeLensVisible(node,relevant));
  });
  edgeObjs.forEach(function(edge){
    const a=nodes[edge.a],b=nodes[edge.b];
    const dim=!a||!b||a.el.classList.contains("lensdim")||b.el.classList.contains("lensdim");
    edge.p.classList.toggle("lensdim",dim);
    if(edge.lab) edge.lab.classList.toggle("lensdim",dim);
  });
  updateLensURL();
}

function updateLensURL(){
  const params=new URLSearchParams(location.search);
  if(lensState.profile!=="all") params.set("profile",lensState.profile);
  else params.delete("profile");
  if(lensState.truth!=="all") params.set("truth",lensState.truth);
  else params.delete("truth");
  history.replaceState(null,"",location.pathname+(params.toString()?"?"+params.toString():"")+location.hash);
}

function renderLint(){
  const button=$("#lintbtn"),body=$("#lintrows");
  if(!button||!body) return;
  const lint=lensState.lint||{summary:{},findings:[]};
  const summary=lint.summary||{};
  const errors=summary.error||0,warnings=summary.warning||0;
  button.textContent="lint "+errors+"E/"+warnings+"W";
  button.classList.toggle("has-errors",errors>0);
  button.classList.toggle("has-warnings",errors===0&&warnings>0);
  body.innerHTML="";
  (lint.findings||[]).forEach(function(row){
    const el=document.createElement("div");
    el.className="lint-row "+row.level;
    const subject=row.subject?'<div class="lint-subject">'+escapeLint(row.subject)+"</div>":"";
    el.innerHTML='<div class="lint-code">'+escapeLint(row.level+" · "+row.code)+'</div>'+
      subject+'<div class="lint-message">'+escapeLint(row.message)+'</div>';
    body.appendChild(el);
  });
  if(!(lint.findings||[]).length){
    body.innerHTML='<div class="lint-empty">No canonical graph lint findings.</div>';
  }
}

function escapeLint(value){
  return String(value||"")
    .replaceAll("&","&amp;").replaceAll("<","&lt;")
    .replaceAll(">","&gt;").replaceAll('"',"&quot;");
}

async function initLensBar(){
  if(!await ensureLensData()) return;
  populateProfileLens();
  if(!lensState.initialized){
    lensState.initialized=true;
    const params=new URLSearchParams(location.search);
    lensState.profile=params.get("profile")||"all";
    lensState.truth=params.get("truth")||"all";

    const p=$("#profilelens"),t=$("#truthlens");
    if(p){
      p.value=[...p.options].some(function(o){return o.value===lensState.profile;})
        ?lensState.profile:"all";
      lensState.profile=p.value;
      p.onchange=function(){lensState.profile=p.value;applyLens();};
    }
    if(t){
      t.value=[...t.options].some(function(o){return o.value===lensState.truth;})
        ?lensState.truth:"all";
      lensState.truth=t.value;
      t.onchange=function(){lensState.truth=t.value;applyLens();};
    }
    const lintButton=$("#lintbtn"),close=$("#lintclose");
    if(lintButton) lintButton.onclick=function(){$("#lintpanel").classList.toggle("open");};
    if(close) close.onclick=function(){$("#lintpanel").classList.remove("open");};
  } else {
    const p=$("#profilelens");
    if(p && ![...p.options].some(function(o){return o.value===lensState.profile;})){
      lensState.profile="all";
      p.value="all";
    }
  }
  renderLint();
  requestAnimationFrame(applyLens);
}

addEventListener("z0archy:boot",function(){void initLensBar();});
if(typeof deck!=="undefined"&&deck) void initLensBar();
