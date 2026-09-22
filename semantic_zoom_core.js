"use strict";

(function(root){
  const LEVELS={
    root:0,
    component:1,
    mechanism_family:1,
    harness:2,
    mechanism:2,
    representation:2,
    lifecycle:2,
    interface:3,
    profile:3,
    repository:3,
    evidence_dependency:3,
    lifecycle_state:4,
    evidence_reference:4,
    repo_structure:4,
    test_surface:4,
    repo_ref:5,
    package:5,
    source_artifact:5,
    implementation_manifest:5,
    derived:5
  };

  function semanticLevelForType(type){
    return Object.prototype.hasOwnProperty.call(LEVELS,type)?LEVELS[type]:3;
  }

  function detailLevelForScale(scale){
    const s=Number(scale)||0;
    if(s<0.16) return 1;
    if(s<0.27) return 2;
    if(s<0.44) return 3;
    if(s<0.72) return 4;
    return 5;
  }

  function labelForDetail(level){
    return [
      "world",
      "logic",
      "concepts",
      "important detail",
      "deep detail",
      "source evidence"
    ][Math.max(0,Math.min(5,Number(level)||0))];
  }

  function shouldShow(semanticLevel,detailLevel,focused){
    if(focused) return true;
    if(semanticLevel==null) return true;
    return Number(semanticLevel)<=Number(detailLevel);
  }

  function semanticImportanceForType(type){
    const level=semanticLevelForType(type);
    return Math.max(0,10-level*2);
  }

  function sufficiencyThresholdForDetail(detailLevel){
    return Math.max(1,10-Number(detailLevel||0)*2);
  }

  const api={
    semanticLevelForType:semanticLevelForType,
    detailLevelForScale:detailLevelForScale,
    labelForDetail:labelForDetail,
    shouldShow:shouldShow,
    semanticImportanceForType:semanticImportanceForType,
    sufficiencyThresholdForDetail:sufficiencyThresholdForDetail
  };
  root.z0SemanticZoomCore=api;
  if(typeof module!=="undefined"&&module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
