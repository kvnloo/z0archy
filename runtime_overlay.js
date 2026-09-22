"use strict";

let runtimeOverlayState={
  graph:null,
  fingerprint:null,
  active:false,
  initialized:false,
  timer:null
};
const RUNTIME_SCENE_ID="runtime-evidence";
const RUNTIME_NODE_BUDGET=180;

function runtimeFingerprint(graph){
  if(!graph) return null;
  const snap=graph.snapshot||{};
  const summary=graph.summary||{};
  return JSON.stringify([
    snap.generatedAt,
    summary.nodeCount,
    summary.edgeCount,
    summary.tokenomicsEventCount,
    summary.agenttraceSessionCount,
    summary.aodlWorldCount
  ]);
}

async function fetchRuntimeGraph(){
  try{
    const response=await fetch("./generated/runtime-evidence.json",{cache:"no-store"});
    return response.ok?await response.json():null;
  }catch(_){
    return null;
  }
}

function ensureRuntimeButton(){
  let button=$("#runtimebtn");
  if(button) return button;
  const nav=$("#nav");
  if(!nav) return null;
  button=document.createElement("button");
  button.id="runtimebtn";
  button.className="wide";
  button.textContent="runtime";
  button.disabled=true;
  nav.insertBefore(button,$("#editbtn")||nav.firstChild);
  button.onclick=function(){
    if(!runtimeOverlayState.graph) return;
    runtimeOverlayState.active=true;
    installRuntimeScene(runtimeOverlayState.graph);
  };
  return button;
}

async function refreshRuntimeOverlay(){
  const button=ensureRuntimeButton();
  if(!button) return;
  const graph=await fetchRuntimeGraph();
  if(!graph){
    runtimeOverlayState.graph=null;
    button.disabled=true;
    button.textContent="runtime";
    return;
  }
  const fingerprint=runtimeFingerprint(graph);
  const changed=fingerprint!==runtimeOverlayState.fingerprint;
  runtimeOverlayState.graph=graph;
  runtimeOverlayState.fingerprint=fingerprint;
  button.disabled=false;
  const summary=graph.summary||{};
  const traceCount=(summary.traceCount||0)+(summary.agenttraceSessionCount||0)+(summary.aodlWorldCount||0);
  button.textContent=traceCount?"runtime · "+traceCount:"runtime";
  if(changed&&runtimeOverlayState.active){
    installRuntimeScene(graph);
  }
}

function deckNodeByGraphId(graphId){
  for(const slide of deck.slides||[]){
    if(slide.id===RUNTIME_SCENE_ID) continue;
    for(const node of slide.nodes||[]){
      if(node.meta&&node.meta.graphId===graphId) return node.id;
    }
  }
  return null;
}

function runtimeNodePriority(node){
  return {
    runtime_trace:100,
    runtime_session:95,
    runtime_orchestration:95,
    runtime_intent_topology:90,
    runtime_observed_topology:90,
    runtime_plan:88,
    runtime_topology_node:70,
    runtime_event:50
  }[node.type]||40;
}

function runtimeNodeOrder(a,b){
  const priority=runtimeNodePriority(b)-runtimeNodePriority(a);
  if(priority) return priority;
  const ats=Number((a.attributes||{}).ts||0);
  const bts=Number((b.attributes||{}).ts||0);
  if(ats!==bts) return bts-ats;
  return String(a.id).localeCompare(String(b.id));
}

function installRuntimeScene(graph){
  deck.slides=(deck.slides||[]).filter(function(slide){return slide.id!==RUNTIME_SCENE_ID;});
  const chosen=(graph.nodes||[]).slice().sort(runtimeNodeOrder).slice(0,RUNTIME_NODE_BUDGET);
  const chosenIds=new Set(chosen.map(function(node){return node.id;}));
  const defs=[];
  const canonicalIncludes=new Set();

  chosen.forEach(function(node,index){
    const attrs=node.attributes||{};
    const col=index%5,row=Math.floor(index/5);
    let kind="tiny measurement",width=290;
    if(node.type==="runtime_trace"){kind="hub measurement";width=390;}
    if(node.type==="runtime_session"){kind="hub environment";width=360;}
    if(node.type==="runtime_orchestration"){kind="hub decision";width=390;}
    if(node.type==="runtime_intent_topology"){kind="hub decision";width=350;}
    if(node.type==="runtime_observed_topology"){kind="hub research";width=350;}
    if(node.type==="runtime_plan"){kind="hub compute";width=340;}
    defs.push({
      id:node.id,
      title:node.label||node.type,
      sub:String(node.type||"").replaceAll("_"," "),
      body:runtimeBody(node),
      pos:[-920+col*460,row*225],
      w:width,
      kind:kind,
      tip:runtimeTip(node),
      meta:{
        graphType:node.type,
        graphId:node.id,
        semanticLevel:runtimeSemanticLevel(node.type),
        truthClass:"observed"
      }
    });
  });

  const renderedEdges=[];
  (graph.edges||[]).forEach(function(edge){
    let from=chosenIds.has(edge.source)?edge.source:deckNodeByGraphId(edge.source);
    let to=chosenIds.has(edge.target)?edge.target:deckNodeByGraphId(edge.target);
    if(!from||!to||from===to) return;
    if(!chosenIds.has(edge.source)&&from) canonicalIncludes.add(from);
    if(!chosenIds.has(edge.target)&&to) canonicalIncludes.add(to);
    renderedEdges.push({
      from:from,
      to:to,
      label:runtimeEdgeLabel(edge.type),
      kind:edge.type==="observed_as"||edge.type==="compiled_to"?"depends":"integrates"
    });
  });

  deck.slides.push({
    id:RUNTIME_SCENE_ID,
    title:"Observed runtime world",
    caption:"Metadata-only runtime evidence. Intent, compiled plan, observed topology and measured economics remain separate; missing evidence is not synthesized.",
    anchor:[14500,4200],
    nodes:defs,
    include:[...canonicalIncludes],
    edges:renderedEdges,
    layout:{fitMargin:180,zoomMax:0.72}
  });
  runtimeOverlayState.active=true;
  boot(deck);
  const index=deck.slides.findIndex(function(slide){return slide.id===RUNTIME_SCENE_ID;});
  if(index>=0) go(index);
}

function runtimeSemanticLevel(type){
  if(type==="runtime_trace"||type==="runtime_session"||type==="runtime_orchestration") return 2;
  if(type==="runtime_intent_topology"||type==="runtime_observed_topology"||type==="runtime_plan") return 3;
  if(type==="runtime_topology_node") return 4;
  return 5;
}

function runtimeBody(node){
  const a=node.attributes||{};
  if(node.type==="runtime_trace"){
    const usage=a.usage||{};
    const tokens=(usage.input_tokens||0)+(usage.output_tokens||0);
    const parts=[a.eventCount+" events"];
    if(tokens) parts.push(tokens+" tok");
    if(a.costUsd) parts.push("$"+Number(a.costUsd).toFixed(4));
    if(a.verifiedSuccess===true) parts.push("verified");
    if(a.verifiedSuccess===false) parts.push("negative");
    return parts.join(" · ");
  }
  if(node.type==="runtime_event"){
    const usage=a.usage||{};
    const tokens=(usage.input_tokens||0)+(usage.output_tokens||0);
    return [a.status,tokens?tokens+" tok":null,a.harness||a.service].filter(Boolean).join(" · ");
  }
  if(node.type==="runtime_session"){
    return [a.source||a.source_tool,a.model,a.health_score!=null?"health "+a.health_score:null].filter(Boolean).join(" · ");
  }
  if(node.type==="runtime_orchestration"){
    return "rev "+a.revision+" · "+(a.hasObservedGraph?"observed":"intent only");
  }
  if(node.type==="runtime_intent_topology"||node.type==="runtime_observed_topology"){
    return (a.nodeCount||0)+" nodes · "+(a.edgeCount||0)+" edges";
  }
  if(node.type==="runtime_plan"){
    return a.harness||a.status||"compiled plan";
  }
  if(node.type==="runtime_topology_node"){
    return [a.kind,a.harness,a.lifecycle].filter(Boolean).join(" · ");
  }
  return "";
}

function runtimeTip(node){
  const a=node.attributes||{};
  const lines=[node.label||node.type,"","truth: observed","privacy: metadata-only"];
  if(node.type==="runtime_trace"){
    lines.push("events: "+(a.eventCount||0));
    if(a.costUsd) lines.push("cost USD: "+a.costUsd);
    if(a.wallDurationMs!=null) lines.push("wall ms: "+a.wallDurationMs);
    const usage=a.usage||{};
    Object.keys(usage).sort().forEach(function(key){lines.push(key+": "+usage[key]);});
    const context=a.context||{};
    Object.keys(context).sort().forEach(function(key){lines.push(key+": "+context[key]);});
    if((a.models||[]).length) lines.push("models: "+a.models.join(", "));
    if((a.harnesses||[]).length) lines.push("harnesses: "+a.harnesses.join(", "));
    if(a.verifiedSuccess!=null) lines.push("verified: "+a.verifiedSuccess);
  }else{
    ["status","kind","role","harness","service","model","health_score","duration_ms","cost_usd","sourceHash"].forEach(function(key){
      if(a[key]!=null&&typeof a[key]!=="object") lines.push(key+": "+a[key]);
    });
  }
  return lines.join("\n");
}

function runtimeEdgeLabel(type){
  return String(type||"").replaceAll("_"," ");
}

async function initRuntimeOverlay(){
  ensureRuntimeButton();
  await refreshRuntimeOverlay();
  if(!runtimeOverlayState.timer){
    runtimeOverlayState.timer=setInterval(refreshRuntimeOverlay,2000);
  }
}

addEventListener("z0archy:boot",function(){void initRuntimeOverlay();});
