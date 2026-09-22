"use strict";

let sourceOverlay = {github:null, local:null};
let refSelections = {};
let uiState = {source:null, component:null};
let activeEvidence = {key:null, fingerprint:null};
let localRefreshTimer = null;
const EVIDENCE_SCENE_ID = "ref-evidence";

function componentSourceDefs(){
  const out=[];
  (deck.slides||[]).forEach(function(sl){
    (sl.nodes||[]).forEach(function(nd){
      if(nd.meta && nd.meta.component && nd.meta.repo) out.push(nd);
    });
  });
  const byId = new Map();
  out.forEach(function(nd){ if(!byId.has(nd.id)) byId.set(nd.id, nd); });
  return [...byId.values()].sort(function(a,b){
    return String(a.title||a.id).localeCompare(String(b.title||b.id));
  });
}

async function hydrateSourceOverlay(){
  if(!sourceOverlay.github && !sourceOverlay.local){
    const pair = await Promise.all([
      fetchOptionalJSON("./generated/github-index.json"),
      fetchOptionalJSON("./generated/local-state.json")
    ]);
    sourceOverlay.github=pair[0];
    sourceOverlay.local=pair[1];
  }
  initSourceBar();
  if(sourceOverlay.local && !localRefreshTimer){
    localRefreshTimer=setInterval(refreshLocalOverlay, 2000);
  }
}

async function refreshLocalOverlay(){
  const next=await fetchOptionalJSON("./generated/local-state.json");
  if(!next) return;
  sourceOverlay.local=next;
  if(uiState.source==="local") populateRefSelector(true);
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
  const requested=uiState.component||params.get("component");
  if(requested && defs.some(function(d){return d.id===requested;})) comp.value=requested;
  uiState.component=comp.value;

  source.value=uiState.source||params.get("source")||"canonical";
  if(source.value==="github" && !sourceOverlay.github) source.value="canonical";
  if(source.value==="local" && !sourceOverlay.local) source.value="canonical";
  uiState.source=source.value;

  source.querySelector('option[value="github"]').disabled=!sourceOverlay.github;
  source.querySelector('option[value="local"]').disabled=!sourceOverlay.local;
  source.onchange=function(){
    uiState.source=source.value;
    populateRefSelector(false);
  };
  comp.onchange=function(){
    uiState.component=comp.value;
    populateRefSelector(false);
  };
  $("#refselect").onchange=function(){ applyRefSelection(false); };
  populateRefSelector(false);
}

function selectedSourceDef(){
  const id=$("#componentselect").value;
  return componentSourceDefs().find(function(nd){return nd.id===id;})||null;
}

function populateRefSelector(forceEvidence){
  const nd=selectedSourceDef(); if(!nd) return;
  const source=$("#sourcesel").value, ref=$("#refselect"), state=$("#refstate");
  uiState.source=source; uiState.component=nd.id;
  ref.innerHTML=""; state.textContent="";
  const repo=nd.meta.repo;
  let rows=[];

  if(source==="canonical"){
    rows=[{
      value:nd.meta.canonicalBranch||"canonical",
      label:nd.meta.canonicalBranch||"canonical",
      head:nd.meta.canonicalRef||null,
      evidenceKey:null,
      kind:"canonical"
    }];
  } else if(source==="github"){
    const r=sourceOverlay.github && sourceOverlay.github.repositories && sourceOverlay.github.repositories[repo];
    rows=((r&&r.branches)||[]).map(function(b){
      return {
        value:b.name, label:b.name, head:b.oid, evidenceKey:b.oid,
        committedAt:b.committedAt, kind:"github"
      };
    });
  } else if(source==="local"){
    const r=sourceOverlay.local && sourceOverlay.local.repositories && sourceOverlay.local.repositories[repo];
    rows=((r&&r.worktrees)||[]).map(function(w){
      return {
        value:w.path,
        label:(w.branch||"detached")+(w.dirtyFiles?" *":"")+" · "+w.path,
        head:w.head, evidenceKey:w.evidenceKey, branch:w.branch,
        dirtyFiles:w.dirtyFiles, ahead:w.ahead, behind:w.behind, kind:"local"
      };
    });
  }

  if(!rows.length){
    const o=document.createElement("option");
    o.textContent="no observed refs"; o.value=""; ref.appendChild(o); ref.disabled=true;
    state.textContent=source==="github"?"not in GitHub index":"no local checkout observed";
    applyRefSelection(forceEvidence); return;
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
  applyRefSelection(forceEvidence);
}

function applyRefSelection(forceEvidence){
  const nd=selectedSourceDef(); if(!nd) return;
  const source=$("#sourcesel").value, ref=$("#refselect"), state=$("#refstate");
  const opt=ref.options[ref.selectedIndex];
  const row=opt&&opt.dataset.row?JSON.parse(opt.dataset.row):null;
  refSelections[nd.id]={source:source,value:ref.value,row:row};
  uiState.source=source; uiState.component=nd.id;

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

  if(source==="canonical" || !row || !row.evidenceKey){
    clearEvidenceScene(nd);
    return;
  }
  void loadEvidenceScene(nd, row, source, forceEvidence);
}

async function loadEvidenceScene(component, row, source, force){
  const repo=component.meta.repo;
  const key=repo+":"+row.evidenceKey;
  const path=evidencePath(repo,row.evidenceKey);
  const pack=await fetchOptionalJSON(path);
  if(!pack){
    $("#refstate").textContent += " · evidence unavailable";
    return;
  }
  if(pack.error){
    $("#refstate").textContent += " · evidence error";
  }
  const fingerprint=evidenceFingerprint(pack);
  if(!force && activeEvidence.key===key && activeEvidence.fingerprint===fingerprint) return;
  if(force && activeEvidence.key===key && activeEvidence.fingerprint===fingerprint) return;

  activeEvidence={key:key,fingerprint:fingerprint};
  installEvidenceScene(component,row,source,pack);
}

function evidencePath(repo,key){
  const parts=repo.split("/");
  if(parts.length!==2) return "";
  return "./generated/ref-evidence/"+
    encodeURIComponent(parts[0])+"/"+encodeURIComponent(parts[1])+"/"+
    encodeURIComponent(key)+".json";
}

function evidenceFingerprint(pack){
  return JSON.stringify((pack.nodes||[]).map(function(n){
    const a=n.attributes||{};
    return [n.id,a.sha256,a.gitBlobOid,a.version,a.bytes,a.resolvedRef,a.fileCount,a.packageCount,a.schemaCount,a.workflowCount,a.testFileCount];
  }));
}

function installEvidenceScene(component,row,source,pack){
  deck.slides=(deck.slides||[]).filter(function(sl){return sl.id!==EVIDENCE_SCENE_ID;});
  const packNodes=pack.nodes||[];
  const defs=[];
  let other=0;
  packNodes.forEach(function(n){
    const a=n.attributes||{};
    let pos, kind="tiny contract", width=310;
    if(n.type==="repo_ref"){
      pos=[0,0]; kind="hub compute"; width=430;
    } else {
      const col=other%3, r=Math.floor(other/3); other++;
      pos=[-420+col*420,300+r*250];
      if(n.type==="package") kind="hub decision";
      if(n.type==="implementation_manifest") kind="hub research";
      if(n.type==="subsystem") kind="hub compute";
      if(n.type==="repo_structure") kind="hub measurement";
      if(n.type==="test_surface") kind="hub research";
    }
    let body="";
    if(n.type==="source_artifact"){
      body=(a.role||"artifact")+" · "+String(a.sha256||a.gitBlobOid||"").slice(0,12);
    } else if(n.type==="package"){
      body=(a.ecosystem||"package")+(a.version?" · "+a.version:"");
    } else if(n.type==="repo_ref"){
      body=source+" · "+String(row.head||a.resolvedRef||"").slice(0,12);
    } else if(n.type==="repo_structure"){
      body=(a.fileCount||0)+" files · "+(a.packageCount||0)+" packages · "+(a.schemaCount||0)+" schemas";
    } else if(n.type==="subsystem"){
      body=(a.kind||"subsystem")+" · "+((a.paths||[]).slice(0,2).join(", ")||"manifest");
    } else if(n.type==="test_surface"){
      body=(a.fileCount||0)+" test files";
    } else {
      body=String(a.path||a.repo||"");
    }
    defs.push({
      id:n.id,
      title:n.label||n.type,
      sub:n.type.replaceAll("_"," "),
      body:body,
      pos:pos,
      w:width,
      kind:kind,
      tip:evidenceTip(n,pack,row,source),
      meta:{
        graphType:n.type,
        graphId:n.id,
        semanticLevel:(typeof z0SemanticZoomCore!=="undefined"
          ?z0SemanticZoomCore.semanticLevelForType(n.type):5),
        truthClass:"implemented"
      }
    });
  });

  const nodeIds=new Set(defs.map(function(n){return n.id;}));
  const edges=(pack.edges||[])
    .filter(function(e){return nodeIds.has(e.source)&&nodeIds.has(e.target);})
    .map(function(e){return {from:e.source,to:e.target,label:e.type};});

  const repoRef=packNodes.find(function(n){return n.type==="repo_ref";});
  if(repoRef){
    edges.push({from:component.id,to:repoRef.id,label:"selected ref",kind:"depends"});
  }

  deck.slides.push({
    id:EVIDENCE_SCENE_ID,
    title:(component.title||component.id)+" · "+(row.branch||row.value||"ref"),
    caption:"Implemented evidence compiled from the exact selected "+source+" source. Declared z0 architecture remains separate.",
    anchor:[8000,4500],
    nodes:defs,
    include:[component.id],
    edges:edges,
    layout:{fitMargin:150,zoomMax:0.95}
  });

  boot(deck);
  const idx=deck.slides.findIndex(function(sl){return sl.id===EVIDENCE_SCENE_ID;});
  if(idx>=0) go(idx);
  const summary=pack.summary||{};
  const count=(pack.nodes||[]).length;
  $("#refstate").textContent += " · "+count+" evidence nodes"+
    (summary.hasArchitecture?" · architecture":"")+
    (summary.hasManifest?" · manifest":"");
}

function evidenceTip(node,pack,row,source){
  const a=node.attributes||{};
  const lines=[
    node.label||node.type,
    "",
    "truth: implemented",
    "source: "+source,
    "repo: "+(pack.repo||""),
    "selected: "+(row.branch||row.value||""),
    "resolved: "+String(pack.resolvedRef||row.head||"").slice(0,16)
  ];
  if(a.path) lines.push("path: "+a.path);
  if(a.sha256) lines.push("sha256: "+a.sha256.slice(0,16));
  if(a.gitBlobOid) lines.push("git blob: "+String(a.gitBlobOid).slice(0,16));
  if(a.bytes!=null) lines.push("bytes: "+a.bytes);
  if(node.type==="repo_structure"){
    lines.push("files: "+(a.fileCount||0));
    lines.push("packages: "+(a.packageCount||0));
    lines.push("schemas: "+(a.schemaCount||0));
    lines.push("workflows: "+(a.workflowCount||0));
    lines.push("tests: "+(a.testFileCount||0));
    lines.push("compression: "+(a.semanticCompressionRatio||0)+" source files / semantic node");
  }
  return lines.join("\n");
}

function clearEvidenceScene(component){
  if(!activeEvidence.key && !(deck.slides||[]).some(function(sl){return sl.id===EVIDENCE_SCENE_ID;})) return;
  activeEvidence={key:null,fingerprint:null};
  const before=(deck.slides||[]).length;
  deck.slides=(deck.slides||[]).filter(function(sl){return sl.id!==EVIDENCE_SCENE_ID;});
  if(deck.slides.length===before) return;
  boot(deck);
  const idx=deck.slides.findIndex(function(sl){
    return (sl.nodes||[]).some(function(n){return n.id===component.id;});
  });
  if(idx>=0) go(idx);
}

async function fetchOptionalJSON(path){
  if(!path) return null;
  try{
    const r=await fetch(path,{cache:"no-store"});
    return r.ok?await r.json():null;
  }catch(_){
    return null;
  }
}

addEventListener("z0archy:boot", hydrateSourceOverlay);
