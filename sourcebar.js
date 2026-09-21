"use strict";

let sourceOverlay = {github:null, local:null};
let refSelections = {};

function componentSourceDefs(){
  const out=[];
  (deck.slides||[]).forEach(function(sl){
    (sl.nodes||[]).forEach(function(nd){
      if(nd.meta && nd.meta.component && nd.meta.repo) out.push(nd);
    });
  });
  return out.sort(function(a,b){
    return String(a.title||a.id).localeCompare(String(b.title||b.id));
  });
}

async function hydrateSourceOverlay(){
  const pair = await Promise.all([
    fetchOptionalJSON("./generated/github-index.json"),
    fetchOptionalJSON("./generated/local-state.json")
  ]);
  sourceOverlay.github=pair[0];
  sourceOverlay.local=pair[1];
  initSourceBar();
}

function initSourceBar(){
  const bar=$("#sourcebar"), comp=$("#componentselect"), source=$("#sourcesel");
  if(!bar) return;
  const defs=componentSourceDefs();
  comp.innerHTML="";
  defs.forEach(function(nd){
    const o=document.createElement("option");
    o.value=nd.id; o.textContent=nd.title||nd.id; comp.appendChild(o);
  });
  const params=new URLSearchParams(location.search);
  const requested=params.get("component");
  if(requested && defs.some(function(d){return d.id===requested;})) comp.value=requested;
  source.value=params.get("source")||"canonical";
  if(source.value==="github" && !sourceOverlay.github) source.value="canonical";
  if(source.value==="local" && !sourceOverlay.local) source.value="canonical";
  source.querySelector('option[value="github"]').disabled=!sourceOverlay.github;
  source.querySelector('option[value="local"]').disabled=!sourceOverlay.local;
  source.onchange=populateRefSelector;
  comp.onchange=populateRefSelector;
  $("#refselect").onchange=applyRefSelection;
  populateRefSelector();
}

function selectedSourceDef(){
  const id=$("#componentselect").value;
  return componentSourceDefs().find(function(nd){return nd.id===id;})||null;
}

function populateRefSelector(){
  const nd=selectedSourceDef(); if(!nd) return;
  const source=$("#sourcesel").value, ref=$("#refselect"), state=$("#refstate");
  ref.innerHTML=""; state.textContent="";
  const repo=nd.meta.repo;
  let rows=[];
  if(source==="canonical"){
    rows=[{
      value:nd.meta.canonicalBranch||"canonical",
      label:nd.meta.canonicalBranch||"canonical",
      head:nd.meta.canonicalRef||null,
      kind:"canonical"
    }];
  } else if(source==="github"){
    const r=sourceOverlay.github && sourceOverlay.github.repositories && sourceOverlay.github.repositories[repo];
    rows=((r&&r.branches)||[]).map(function(b){
      return {value:b.name,label:b.name,head:b.oid,committedAt:b.committedAt,kind:"github"};
    });
  } else if(source==="local"){
    const r=sourceOverlay.local && sourceOverlay.local.repositories && sourceOverlay.local.repositories[repo];
    rows=((r&&r.worktrees)||[]).map(function(w){
      return {
        value:w.path,
        label:(w.branch||"detached")+(w.dirtyFiles?" *":"")+" · "+w.path,
        head:w.head, branch:w.branch, dirtyFiles:w.dirtyFiles,
        ahead:w.ahead, behind:w.behind, kind:"local"
      };
    });
  }
  if(!rows.length){
    const o=document.createElement("option");
    o.textContent="no observed refs"; o.value=""; ref.appendChild(o); ref.disabled=true;
    state.textContent=source==="github"?"not in GitHub index":"no local checkout observed";
    applyRefSelection(); return;
  }
  ref.disabled=false;
  rows.forEach(function(row){
    const o=document.createElement("option");
    o.value=row.value; o.textContent=row.label; o.dataset.row=JSON.stringify(row); ref.appendChild(o);
  });
  const saved=refSelections[nd.id];
  const params=new URLSearchParams(location.search);
  const fromUrl=source!=="local"?params.get("ref."+nd.id):null;
  const wanted=(saved&&saved.source===source&&saved.value)||fromUrl;
  if(wanted && rows.some(function(r){return r.value===wanted;})) ref.value=wanted;
  else if(source==="canonical") ref.value=rows[0].value;
  else if(source==="github"){
    const canonical=nd.meta.canonicalBranch;
    if(canonical && rows.some(function(r){return r.value===canonical;})) ref.value=canonical;
  }
  applyRefSelection();
}

function applyRefSelection(){
  const nd=selectedSourceDef(); if(!nd) return;
  const source=$("#sourcesel").value, ref=$("#refselect"), state=$("#refstate");
  const opt=ref.options[ref.selectedIndex];
  const row=opt&&opt.dataset.row?JSON.parse(opt.dataset.row):null;
  refSelections[nd.id]={source:source,value:ref.value,row:row};
  const short=row&&row.head?String(row.head).slice(0,10):"";
  if(row){
    if(source==="local"){
      state.textContent=short+
        (row.dirtyFiles?" · "+row.dirtyFiles+" dirty":"")+
        (row.ahead?" · +"+row.ahead:"")+
        (row.behind?" · -"+row.behind:"");
    } else {
      state.textContent=short+(row.committedAt?" · "+String(row.committedAt).slice(0,10):"");
    }
  } else state.textContent="";

  nd._baseTip=nd._baseTip||nd.tip||"";
  let evidence="";
  if(row){
    const refName=source==="local"?(row.branch||"detached"):(row.value||ref.value);
    evidence="\n\n"+source+" evidence: "+refName+(row.head?" @ "+short:"");
  }
  nd.tip=nd._baseTip+evidence;
  if(nodes[nd.id]) nodes[nd.id].def.tip=nd.tip;
  if(tipFor===nodes[nd.id]) showTip(nodes[nd.id]);

  const params=new URLSearchParams(location.search);
  params.set("source",source);
  params.set("component",nd.id);
  if(source!=="local" && ref.value) params.set("ref."+nd.id,ref.value);
  history.replaceState(null,"",location.pathname+(params.toString()?"?"+params.toString():"")+location.hash);
}

async function fetchOptionalJSON(path){
  try{
    const r=await fetch(path,{cache:"no-store"});
    return r.ok?await r.json():null;
  }catch(_){
    return null;
  }
}

addEventListener("z0archy:boot", hydrateSourceOverlay);
