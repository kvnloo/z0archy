"use strict";

let historyState = {
  index: null,
  liveDeck: null,
  active: "live",
  initialSelectionApplied: false
};

function cloneDeck(value){
  return JSON.parse(JSON.stringify(value));
}

async function initHistoryBar(){
  const select=$("#historyselect");
  if(!select || !deck) return;

  if(!historyState.liveDeck) historyState.liveDeck=cloneDeck(deck);
  if(!historyState.index){
    historyState.index=await fetchHistoryJSON("./generated/history-index.json");
  }

  select.innerHTML="";
  const live=document.createElement("option");
  live.value="live";
  live.textContent="live";
  select.appendChild(live);

  const entries=((historyState.index&&historyState.index.entries)||[]).slice().reverse();
  entries.forEach(function(entry){
    if(!entry.deckPath) return;
    const option=document.createElement("option");
    option.value=entry.hash;
    const date=entry.createdAt?String(entry.createdAt).replace("T"," ").replace("Z",""):"";
    option.textContent=(date?date+" · ":"")+String(entry.hash).slice(0,8);
    option.dataset.entry=JSON.stringify(entry);
    select.appendChild(option);
  });

  const params=new URLSearchParams(location.search);
  const requested=historyState.active!=="live"
    ? historyState.active
    : (params.get("history")||"live");
  if([...select.options].some(function(o){return o.value===requested;})){
    select.value=requested;
  } else {
    select.value="live";
    historyState.active="live";
  }

  select.onchange=function(){ void switchHistory(select.value); };

  if(!historyState.initialSelectionApplied){
    historyState.initialSelectionApplied=true;
    if(select.value!=="live") void switchHistory(select.value);
  }
}

async function switchHistory(value){
  const select=$("#historyselect");
  if(value==="live"){
    if(historyState.active==="live") return;
    historyState.active="live";
    setHistoryURL(null);
    boot(cloneDeck(historyState.liveDeck));
    toast("live architecture");
    return;
  }

  const option=[...select.options].find(function(o){return o.value===value;});
  if(!option || !option.dataset.entry) return;
  const entry=JSON.parse(option.dataset.entry);
  if(!entry.deckPath) return;

  const historical=await fetchHistoryJSON("./"+entry.deckPath);
  if(!historical){
    toast("historical deck unavailable");
    return;
  }

  historyState.active=value;
  setHistoryURL(value);
  boot(historical);
  toast("history · "+String(value).slice(0,8));
}

function setHistoryURL(value){
  const params=new URLSearchParams(location.search);
  if(value) params.set("history",value);
  else params.delete("history");
  history.replaceState(
    null,
    "",
    location.pathname+(params.toString()?"?"+params.toString():"")+location.hash
  );
}

async function fetchHistoryJSON(path){
  try{
    const response=await fetch(path,{cache:"no-store"});
    return response.ok?await response.json():null;
  }catch(_){
    return null;
  }
}

addEventListener("z0archy:boot", function(){ void initHistoryBar(); });
