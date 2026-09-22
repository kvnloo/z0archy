"use strict";

const VIRTUAL_SCENE_ID="virtual-architecture";
let matrixState={
  graph:null,
  github:null,
  canonical:null,
  rows:{},
  active:false,
  initialized:false
};

async function matrixFetchJSON(path){
  try{
    const response=await fetch(path,{cache:"no-store"});
    return response.ok?await response.json():null;
  }catch(_){return null;}
}

function matrixEvidencePath(repo,key){
  const parts=String(repo).split("/");
  if(parts.length!==2||!key) return null;
  return "./generated/ref-evidence/"+
    encodeURIComponent(parts[0])+"/"+encodeURIComponent(parts[1])+"/"+
    encodeURIComponent(key)+".json";
}

async function ensureMatrixData(){
  if(matrixState.graph&&matrixState.github&&matrixState.canonical) return true;
  const values=await Promise.all([
    matrixFetchJSON("./generated/graph.json"),
    matrixFetchJSON("./generated/github-index.json"),
    matrixFetchJSON("./generated/canonical-ref-index.json")
  ]);
  matrixState.graph=values[0];
  matrixState.github=values[1];
  matrixState.canonical=values[2]||{version:1,repos:{}};
  return !!(matrixState.graph&&matrixState.github);
}

function matrixRepos(){
  const set=new Set();
  (matrixState.graph&&matrixState.graph.nodes||[]).forEach(function(node){
    if(node.type==="repository"&&node.attributes&&node.attributes.repo){
      set.add(node.attributes.repo);
    }
  });
  Object.keys(matrixState.github&&matrixState.github.repositories||{}).forEach(function(repo){set.add(repo);});
  return [...set].sort();
}

function shortSha(value){return String(value||"").slice(0,9);}

function optionForTarget(target,label){
  const option=document.createElement("option");
  option.value=(target.declared?"canonical":"ref")+":"+(target.ref||"")+":"+(target.evidenceKey||"");
  option.textContent=label;
  option.dataset.target=JSON.stringify(target);
  return option;
}

function rowTarget(select){
  const option=select.options[select.selectedIndex];
  return option&&option.dataset.target?JSON.parse(option.dataset.target):null;
}

function canonicalForRepo(repo){
  return z0VirtualCore.canonicalTarget(repo,matrixState.canonical,matrixState.github);
}

function buildMatrixPanel(){
  const body=$("#matrixrows");
  if(!body) return;
  body.innerHTML="";
  matrixState.rows={};
  const params=new URLSearchParams(location.search);

  matrixRepos().forEach(function(repo){
    const meta=(matrixState.github.repositories||{})[repo]||{};
    const canonical=canonicalForRepo(repo);
    const row=document.createElement("div");
    row.className="matrix-row";

    const name=document.createElement("div");
    name.className="matrix-name";
    name.innerHTML="<b>"+repo+"</b><span></span>";
    const status=name.querySelector("span");
    if(canonical&&canonical.declared){
      status.textContent="pinned · "+shortSha(canonical.evidenceKey);
      status.className="declared";
    }else{
      status.textContent="un-pinned · default observational";
      status.className="fallback";
    }

    const select=document.createElement("select");
    select.setAttribute("aria-label","ref for "+repo);

    if(canonical){
      const prefix=canonical.declared?"canonical":"default";
      select.appendChild(optionForTarget(
        canonical,
        prefix+" · "+canonical.ref+" @ "+shortSha(canonical.evidenceKey)
      ));
    }

    (meta.branches||[]).forEach(function(branch){
      if(!branch.oid) return;
      const target={
        repo:repo,ref:branch.name,evidenceKey:branch.oid,kind:"branch",
        canonical:!!(canonical&&canonical.evidenceKey===branch.oid&&canonical.declared),
        declared:false
      };
      select.appendChild(optionForTarget(
        target,
        branch.name+" @ "+shortSha(branch.oid)
      ));
    });

    const requested=params.get("v."+repo);
    if(requested){
      for(const option of select.options){
        const target=option.dataset.target?JSON.parse(option.dataset.target):null;
        if(target&&(target.ref===requested||target.evidenceKey===requested)){
          select.value=option.value;
          break;
        }
      }
    }

    const diff=document.createElement("span");
    diff.className="matrix-diff";
    diff.textContent="";

    select.onchange=function(){
      const target=rowTarget(select);
      matrixState.rows[repo]=target;
      diff.textContent=matrixState.active?"pending":"";
    };
    matrixState.rows[repo]=rowTarget(select);

    row.appendChild(name);
    row.appendChild(select);
    row.appendChild(diff);
    body.appendChild(row);
  });
}

function setMatrixMode(mode){
  Object.keys(matrixState.rows).forEach(function(repo){
    const row=[...document.querySelectorAll(".matrix-row")].find(function(el){
      const b=el.querySelector(".matrix-name b");
      return b&&b.textContent===repo;
    });
    if(!row) return;
    const select=row.querySelector("select");
    const canonical=canonicalForRepo(repo);
    const meta=(matrixState.github.repositories||{})[repo]||{};
    let target=null;

    if(mode==="canonical") target=canonical;
    else if(mode==="defaults"&&meta.defaultHead){
      target={
        repo:repo,ref:meta.defaultBranch||"default",
        evidenceKey:meta.defaultHead,kind:"branch",canonical:false,declared:false,fallback:true
      };
    }
    if(!target) return;

    for(const option of select.options){
      const candidate=option.dataset.target?JSON.parse(option.dataset.target):null;
      if(
        candidate &&
        candidate.evidenceKey===target.evidenceKey &&
        (mode!=="defaults" || (candidate.kind==="branch" && candidate.ref===target.ref))
      ){
        select.value=option.value;
        matrixState.rows[repo]=candidate;
        break;
      }
    }
  });
}

async function loadPack(repo,key){
  return key?matrixFetchJSON(matrixEvidencePath(repo,key)):null;
}

async function applyMatrix(){
  if(typeof historyState!=="undefined"&&historyState.active!=="live"){
    toast("return to live architecture before composing refs");
    return;
  }
  const button=$("#matrixapply");
  if(button) button.disabled=true;
  try{
    const selectedPacks={}, baselinePacks={}, diffs={};
    const repos=Object.keys(matrixState.rows).sort();

    await Promise.all(repos.map(async function(repo){
      const target=matrixState.rows[repo];
      if(!target||!target.evidenceKey) return;
      selectedPacks[repo]=await loadPack(repo,target.evidenceKey);
      const canonical=canonicalForRepo(repo);
      if(canonical&&canonical.evidenceKey){
        baselinePacks[repo]=await loadPack(repo,canonical.evidenceKey);
      }
      if(selectedPacks[repo]&&baselinePacks[repo]){
        diffs[repo]=z0VirtualCore.evidenceDiff(baselinePacks[repo],selectedPacks[repo]);
      }
    }));

    if(typeof clearMoc==="function" && typeof mocState!=="undefined" && mocState.query){
      clearMoc();
    }
    const manifest=z0VirtualCore.selectionManifest(matrixState.rows);
    const virtual=z0VirtualCore.mergeEvidence(matrixState.graph,selectedPacks,manifest);
    window.z0VirtualGraph=virtual;
    window.z0VirtualSelection=manifest;
    matrixState.active=true;

    installVirtualScene(selectedPacks,diffs);
    updateMatrixDiffLabels(diffs);
    updateMatrixURL(true);
    $("#matrixpanel").classList.remove("open");
  }finally{
    if(button) button.disabled=false;
  }
}

function componentIdsForRepo(repo){
  if(typeof componentSourceDefs!=="function") return [];
  return componentSourceDefs()
    .filter(function(node){return node.meta&&node.meta.repo===repo;})
    .map(function(node){return node.id;});
}

function installVirtualScene(packs,diffs){
  deck.slides=(deck.slides||[]).filter(function(sl){return sl.id!==VIRTUAL_SCENE_ID;});
  const repos=Object.keys(matrixState.rows).sort();
  const defs=[],edges=[],includes=[];
  repos.forEach(function(repo,index){
    const target=matrixState.rows[repo];
    if(!target) return;
    const diff=diffs[repo];
    const col=index%3,row=Math.floor(index/3);
    const canonical=canonicalForRepo(repo);
    let body="";
    if(!canonical||!canonical.declared){
      body="un-pinned · default is observational baseline";
    }else if(diff&&diff.count){
      body=diff.count+" evidence delta"+(diff.count===1?"":"s")+" vs canonical";
    }else{
      body="matches canonical probed evidence";
    }
    defs.push({
      id:"virtual:"+repo,
      title:repo,
      sub:(target.canonical&&target.declared?"canonical · ":"")+target.ref+" @ "+shortSha(target.evidenceKey),
      body:body,
      pos:[-680+col*680,row*250],
      w:390,
      kind:diff&&diff.count?"hub research":"hub compute",
      tip:virtualTip(repo,target,canonical,diff,packs[repo]),
      meta:{
        graphType:"repo_ref",
        graphId:"z0://repo/"+repo,
        semanticLevel:5,
        truthClass:"derived"
      }
    });
    componentIdsForRepo(repo).forEach(function(componentId){
      if(!includes.includes(componentId)) includes.push(componentId);
      edges.push({from:componentId,to:"virtual:"+repo,kind:"integrates",label:"selected implementation"});
    });
  });

  deck.slides.push({
    id:VIRTUAL_SCENE_ID,
    title:"Virtual Zer0 architecture",
    caption:"One derived world composed from the selected immutable repository refs. Evidence deltas are compared against exact z0 pins when declared; un-pinned repositories remain explicitly observational.",
    anchor:[11000,3500],
    nodes:defs,
    include:includes,
    edges:edges,
    layout:{fitMargin:170,zoomMax:0.82}
  });
  boot(deck);
  const idx=deck.slides.findIndex(function(sl){return sl.id===VIRTUAL_SCENE_ID;});
  if(idx>=0) go(idx);
}

function virtualTip(repo,target,canonical,diff,pack){
  const lines=[
    repo,"",
    "virtual architecture selection",
    "selected: "+target.ref,
    "resolved: "+target.evidenceKey,
    canonical&&canonical.declared
      ?"canonical: "+canonical.ref+" @ "+canonical.evidenceKey
      :"canonical: not pinned in z0"
  ];
  if(pack&&pack.error) lines.push("evidence error: "+pack.error);
  if(diff){
    lines.push("added evidence: "+diff.added.length);
    lines.push("removed evidence: "+diff.removed.length);
    lines.push("changed evidence: "+diff.changed.length);
    [...diff.added,...diff.removed,...diff.changed].slice(0,8).forEach(function(item){
      lines.push("  "+item);
    });
  }
  return lines.join("\n");
}

function updateMatrixDiffLabels(diffs){
  [...document.querySelectorAll(".matrix-row")].forEach(function(row){
    const repo=row.querySelector(".matrix-name b").textContent;
    const label=row.querySelector(".matrix-diff");
    const diff=diffs[repo];
    const canonical=canonicalForRepo(repo);
    if(!canonical||!canonical.declared) label.textContent="un-pinned";
    else if(diff&&diff.count) label.textContent=diff.count+" Δ";
    else label.textContent="0 Δ";
  });
}

async function copyMatrixManifest(){
  const manifest=z0VirtualCore.selectionManifest(matrixState.rows);
  try{
    await navigator.clipboard.writeText(JSON.stringify(manifest,null,2));
    toast("virtual selection manifest copied");
  }catch(_){
    toast("clipboard unavailable");
  }
}

function clearMatrix(){
  if(typeof clearMoc==="function" && typeof mocState!=="undefined" && mocState.query){
    clearMoc();
  }
  matrixState.active=false;
  window.z0VirtualGraph=null;
  window.z0VirtualSelection=null;
  deck.slides=(deck.slides||[]).filter(function(sl){return sl.id!==VIRTUAL_SCENE_ID;});
  updateMatrixURL(false,true);
  boot(deck);
  toast("virtual architecture cleared");
}

function updateMatrixURL(active,clear){
  const params=new URLSearchParams(location.search);
  [...params.keys()].forEach(function(key){
    if(key.startsWith("v.")) params.delete(key);
  });
  if(clear){
    params.delete("virtual");
  }else{
    if(active) params.set("virtual","1");
    else params.delete("virtual");
    Object.keys(matrixState.rows).sort().forEach(function(repo){
      const target=matrixState.rows[repo];
      if(target&&target.ref) params.set("v."+repo,target.ref);
    });
  }
  history.replaceState(null,"",location.pathname+(params.toString()?"?"+params.toString():"")+location.hash);
}

async function initRefMatrix(){
  if(matrixState.initialized) return;
  const button=$("#matrixbtn"),panel=$("#matrixpanel");
  if(!button||!panel) return;
  if(!await ensureMatrixData()) return;
  matrixState.initialized=true;
  buildMatrixPanel();

  button.onclick=function(){panel.classList.toggle("open");};
  $("#matrixclose").onclick=function(){panel.classList.remove("open");};
  $("#matrixcanonical").onclick=function(){setMatrixMode("canonical");};
  $("#matrixdefaults").onclick=function(){setMatrixMode("defaults");};
  $("#matrixapply").onclick=function(){void applyMatrix();};
  $("#matrixcopy").onclick=function(){void copyMatrixManifest();};
  $("#matrixclear").onclick=clearMatrix;

  if(new URLSearchParams(location.search).get("virtual")==="1"){
    void applyMatrix();
  }
}

addEventListener("z0archy:boot",function(){void initRefMatrix();});


if(typeof deck!=="undefined" && deck){
  void initRefMatrix();
}
