"use strict";

const MOC_SCENE_ID="dynamic-moc";
let mocState={query:null,installing:false,initialApplied:false};

function graphDeckId(node){
  const attrs=node.attributes||{};
  if(node.type==="component") return attrs.component_id||node.id;
  if(node.type==="interface") return "iface:"+(attrs.interface||node.label);
  if(node.type==="profile") return "profile:"+(attrs.profile_id||node.label);
  return node.id;
}

function mocNodeKind(node){
  if(node.type==="component") return "hub runtime";
  if(node.type==="harness") return "hub runtime";
  if(node.type==="mechanism"||node.type==="mechanism_family") return "hub research";
  if(node.type==="representation") return "hub compute";
  if(node.type==="interface") return "tiny contract";
  if(node.type==="evidence_dependency") return "hub research";
  if(node.type==="evidence_reference") return "tiny contract";
  if(node.type==="repository") return "tiny contract";
  if(node.type==="lifecycle"||node.type==="lifecycle_state") return "hub environment";
  return "default";
}

function mocColumn(node){
  return {
    component:-720,harness:-720,repository:-720,
    mechanism:-360,mechanism_family:-360,
    representation:0,profile:0,lifecycle:0,lifecycle_state:0,
    interface:360,
    evidence_dependency:720,evidence_reference:720
  }[node.type]??0;
}

function mocPositions(nodes){
  const counters={};
  const out={};
  nodes.forEach(function(node){
    const x=mocColumn(node);
    counters[x]=(counters[x]||0)+1;
    const index=counters[x]-1;
    out[node.id]=[x,index*210];
  });
  return out;
}

function mocTip(node,result){
  const score=result.scores[node.id]||0;
  const prov=(node.provenance||[])[0]||{};
  return [
    node.label||node.id,
    "",
    "question-conditioned map",
    "type: "+String(node.type||"").replaceAll("_"," "),
    "match score: "+score,
    prov.source?"source: "+prov.source+(prov.ref?"@"+prov.ref:""):"",
    prov.path?"path: "+prov.path:""
  ].filter(Boolean).join("\n");
}

async function graphForCurrentWorld(){
  if(
    typeof historyState!=="undefined" &&
    historyState.active==="live" &&
    window.z0VirtualGraph
  ){
    return window.z0VirtualGraph;
  }
  let path="./generated/graph.json";
  if(typeof historyState!=="undefined" && historyState.active && historyState.active!=="live"){
    path="./generated/history/"+encodeURIComponent(historyState.active)+".json";
  }
  try{
    const response=await fetch(path,{cache:"no-store"});
    return response.ok?await response.json():null;
  }catch(_){
    return null;
  }
}

async function applyMoc(query){
  query=String(query||"").trim();
  if(!query) return;
  const graph=await graphForCurrentWorld();
  if(!graph){
    toast("world graph unavailable");
    return;
  }
  const result=z0MocCore.compileMoc(graph,query,{maxNodes:24,maxSeeds:8,maxDepth:2});
  const receipt=(typeof z0CompressionCore!=="undefined")
    ?z0CompressionCore.compressionReceipt(graph,result.nodeIds,{
        query:query,
        scores:result.scores,
        highScoreThreshold:6
      })
    :null;
  window.dispatchEvent(new CustomEvent("z0archy:compression-receipt",{detail:receipt}));
  if(!result.nodeIds.length){
    toast("no architecture concepts matched");
    return;
  }

  const byId=new Map((graph.nodes||[]).map(function(n){return [n.id,n];}));
  const selected=result.nodeIds.map(function(id){return byId.get(id);}).filter(Boolean);
  const positions=mocPositions(selected);
  const idMap={};
  const defs=selected.map(function(node){
    const id="moc:"+node.id;
    idMap[node.id]=id;
    const attrs=node.attributes||{};
    let body=attrs.summary||attrs.purpose||attrs.repo||attrs.relation||attrs.kind||"";
    body=String(body).replace(/\s+/g," ").trim();
    if(body.length>100) body=body.slice(0,97)+"...";
    return {
      id:id,
      title:node.label||node.id,
      sub:String(node.type||"").replaceAll("_"," "),
      body:body,
      pos:positions[node.id],
      w:310,
      kind:mocNodeKind(node),
      tip:mocTip(node,result),
      meta:{
        graphType:node.type,
        graphId:node.id,
        semanticLevel:(typeof z0SemanticZoomCore!=="undefined"
          ?z0SemanticZoomCore.semanticLevelForType(node.type)
          :3),
        truthClass:((node.provenance||[])[0]||{}).class||"derived"
      }
    };
  });

  const edges=result.edges.map(function(edge){
    return {
      from:idMap[edge.source],
      to:idMap[edge.target],
      kind:(edge.attributes||{}).epistemic?"epistemic":"default",
      label:String(edge.type||"").replaceAll("_"," ")
    };
  }).filter(function(edge){return edge.from&&edge.to;});

  deck.slides=(deck.slides||[]).filter(function(sl){return sl.id!==MOC_SCENE_ID;});
  deck.slides.push({
    id:MOC_SCENE_ID,
    title:"Map · "+query,
    caption:"Question-conditioned Map of Content compiled from the current semantic world. Nearby architecture is included by typed graph proximity rather than keyword match alone.",
    anchor:[9800,6500],
    nodes:defs,
    edges:edges,
    layout:{fitMargin:150,zoomMax:0.95}
  });

  mocState.query=query;
  mocState.installing=true;
  setMocURL(query);
  boot(deck);
  mocState.installing=false;
  const idx=deck.slides.findIndex(function(sl){return sl.id===MOC_SCENE_ID;});
  if(idx>=0) go(idx);
  toast(result.nodeIds.length+" concepts · "+result.edges.length+" relations");
}

function clearMoc(){
  mocState.query=null;
  window.dispatchEvent(new CustomEvent("z0archy:compression-receipt",{detail:null}));
  setMocURL(null);
  const before=(deck.slides||[]).length;
  deck.slides=(deck.slides||[]).filter(function(sl){return sl.id!==MOC_SCENE_ID;});
  if(deck.slides.length!==before) boot(deck);
  const input=$("#mocquery");
  if(input) input.value="";
}

function setMocURL(query){
  const params=new URLSearchParams(location.search);
  if(query) params.set("moc",query);
  else params.delete("moc");
  history.replaceState(null,"",location.pathname+(params.toString()?"?"+params.toString():"")+location.hash);
}

function initMocBar(){
  const input=$("#mocquery"), apply=$("#mocapply"), clear=$("#mocclear");
  if(!input||!apply||!clear) return;
  if(mocState.query) input.value=mocState.query;
  apply.onclick=function(){ void applyMoc(input.value); };
  clear.onclick=clearMoc;
  input.onkeydown=function(event){
    if(event.key==="Enter"){ event.preventDefault(); void applyMoc(input.value); }
  };

  if(!mocState.initialApplied && !mocState.installing){
    mocState.initialApplied=true;
    const query=new URLSearchParams(location.search).get("moc");
    if(query){ input.value=query; void applyMoc(query); }
  }
}

addEventListener("z0archy:boot",initMocBar);
