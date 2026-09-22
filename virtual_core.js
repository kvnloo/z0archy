"use strict";

(function(root){
  function clone(value){return JSON.parse(JSON.stringify(value));}

  function branchTarget(repo,branch,index){
    const meta=index&&index.repositories&&index.repositories[repo];
    if(!meta) return null;
    const row=(meta.branches||[]).find(function(b){return b.name===branch;});
    return row&&row.oid?{repo:repo,ref:branch,evidenceKey:row.oid,kind:"branch"}:null;
  }

  function canonicalTarget(repo,canonicalIndex,githubIndex){
    const row=canonicalIndex&&canonicalIndex.repos&&canonicalIndex.repos[repo];
    const pin=row&&(row.pins||[]).find(function(p){return p.resolved&&p.evidenceKey;});
    if(pin){
      return {
        repo:repo,
        ref:pin.branch||pin.ref,
        evidenceKey:pin.evidenceKey,
        canonical:true,
        declared:true,
        component:pin.component
      };
    }
    const meta=githubIndex&&githubIndex.repositories&&githubIndex.repositories[repo];
    if(meta&&meta.defaultHead){
      return {
        repo:repo,
        ref:meta.defaultBranch||"default",
        evidenceKey:meta.defaultHead,
        canonical:false,
        declared:false,
        fallback:true
      };
    }
    return null;
  }

  function mergeEvidence(baseGraph,packs,selection){
    const graph=clone(baseGraph);
    const nodes=new Map((graph.nodes||[]).map(function(n){return [n.id,n];}));
    const edges=new Map((graph.edges||[]).map(function(e){return [e.id,e];}));
    const summaries={};

    Object.keys(packs||{}).sort().forEach(function(repo){
      const pack=packs[repo]||{};
      (pack.nodes||[]).forEach(function(n){nodes.set(n.id,n);});
      (pack.edges||[]).forEach(function(e){edges.set(e.id,e);});
      summaries[repo]=pack.summary||{};
    });

    graph.nodes=[...nodes.values()].sort(function(a,b){return a.id.localeCompare(b.id);});
    graph.edges=[...edges.values()].sort(function(a,b){return a.id.localeCompare(b.id);});
    deriveCrossRepoPackageEdges(graph);
    graph.snapshot={
      generatedAt:new Date().toISOString(),
      truthClass:"derived",
      source:{repo:"z0archy",ref:"browser-virtual"},
      declaredBase:baseGraph.snapshot||null,
      selection:selection
    };
    graph.implementationEvidence=summaries;
    return graph;
  }

  function packageKey(value){
    return String(value||"").trim().toLowerCase().replaceAll("_","-");
  }

  function deriveCrossRepoPackageEdges(graph){
    const packages=(graph.nodes||[]).filter(function(node){return node.type==="package";});
    const byName=new Map();
    packages.forEach(function(node){
      const attrs=node.attributes||{};
      const key=packageKey(attrs.name||node.label);
      if(!key) return;
      if(!byName.has(key)) byName.set(key,[]);
      byName.get(key).push(node);
    });
    const existing=new Set((graph.edges||[]).map(function(edge){return edge.id;}));
    const ambiguous=new Set(),derived=[];
    packages.forEach(function(source){
      const attrs=source.attributes||{},sourceRepo=attrs.repo;
      (attrs.dependencies||[]).forEach(function(dependency){
        const targets=byName.get(packageKey(dependency))||[];
        if(targets.length!==1){
          if(targets.length>1) ambiguous.add(String(dependency));
          return;
        }
        const target=targets[0],targetRepo=(target.attributes||{}).repo;
        if(!sourceRepo||!targetRepo||sourceRepo===targetRepo) return;
        const id="z0://edge/derived:package:"+source.id+"->"+target.id;
        if(existing.has(id)) return;
        const sourceProv=(source.provenance||[{}])[0];
        derived.push({
          id:id,
          type:"package_depends_on",
          source:source.id,
          target:target.id,
          attributes:{
            derivedCrossRepo:true,
            dependencyName:dependency,
            sourceRepo:sourceRepo,
            targetRepo:targetRepo,
            confidence:"manifest-match"
          },
          provenance:[{
            class:"derived",
            source:"z0archy",
            ref:"browser-virtual",
            path:sourceProv.path||attrs.sourcePath||"package-manifest",
            field:"dependency:"+dependency
          }]
        });
        existing.add(id);
      });
    });
    graph.edges=(graph.edges||[]).concat(derived).sort(function(a,b){return a.id.localeCompare(b.id);});
    graph.derivedEvidence=graph.derivedEvidence||{};
    graph.derivedEvidence.crossRepoPackageEdges=derived.length;
    graph.derivedEvidence.ambiguousPackageNames=[...ambiguous].sort();
    return graph;
  }

  function driftFindings(graph){
    const nodes=graph.nodes||[],edges=graph.edges||[];
    const byId=new Map(nodes.map(function(node){return [node.id,node];}));
    const repoComponents=new Map();
    nodes.forEach(function(node){
      if(node.type!=="component") return;
      const repo=node.attributes&&node.attributes.repo;
      if(!repo) return;
      if(!repoComponents.has(repo)) repoComponents.set(repo,new Set());
      repoComponents.get(repo).add(node.id);
    });
    const depends=new Set(),integrates=new Set();
    edges.forEach(function(edge){
      if(edge.type==="depends_on") depends.add(edge.source+"|"+edge.target);
      if(edge.type==="integrates_with"){
        integrates.add([edge.source,edge.target].sort().join("|"));
      }
    });
    const findings=[];
    edges.forEach(function(edge){
      const attrs=edge.attributes||{};
      if(edge.type!=="package_depends_on"||!attrs.derivedCrossRepo) return;
      const source=byId.get(edge.source)||{},target=byId.get(edge.target)||{};
      const sourceRepo=(source.attributes||{}).repo||attrs.sourceRepo;
      const targetRepo=(target.attributes||{}).repo||attrs.targetRepo;
      const sourceComponents=[...(repoComponents.get(sourceRepo)||[])];
      const targetComponents=[...(repoComponents.get(targetRepo)||[])];
      if(!sourceComponents.length||!targetComponents.length){
        findings.push({
          level:"info",
          code:"drift.package_dependency_unmapped",
          subject:edge.id,
          message:"Cross-repo package dependency "+sourceRepo+" -> "+targetRepo+" cannot be mapped to registered components."
        });
        return;
      }
      const declared=sourceComponents.some(function(a){
        return targetComponents.some(function(b){
          return depends.has(a+"|"+b)||integrates.has([a,b].sort().join("|"));
        });
      });
      if(!declared){
        findings.push({
          level:"warning",
          code:"drift.cross_repo_package_dependency_undeclared",
          subject:edge.id,
          message:"Implementation package dependency "+sourceRepo+" -> "+targetRepo+" has no matching z0 depends_on/integrates_with declaration."
        });
      }
    });
    return findings.sort(function(a,b){
      return (a.code+"|"+(a.subject||"")).localeCompare(b.code+"|"+(b.subject||""));
    });
  }

  function conceptualEvidence(pack){
    const out={};
    (pack&&pack.nodes||[]).forEach(function(node){
      const a=node.attributes||{};
      if(node.type==="source_artifact"){
        out["artifact:"+(a.path||node.label)]={
          type:node.type,
          hash:a.sha256||null,
          bytes:a.bytes??null,
          role:a.role||null
        };
      } else if(node.type==="package"){
        out["package:"+(a.name||node.label)]={
          type:node.type,
          ecosystem:a.ecosystem||null,
          version:a.version??null
        };
      } else if(node.type==="implementation_manifest"){
        out["manifest"]={type:node.type,attributes:a};
      }
    });
    return out;
  }

  function evidenceDiff(basePack,headPack){
    const a=conceptualEvidence(basePack), b=conceptualEvidence(headPack);
    const ak=new Set(Object.keys(a)), bk=new Set(Object.keys(b));
    const added=[...bk].filter(function(k){return !ak.has(k);}).sort();
    const removed=[...ak].filter(function(k){return !bk.has(k);}).sort();
    const changed=[...ak].filter(function(k){
      return bk.has(k)&&JSON.stringify(a[k])!==JSON.stringify(b[k]);
    }).sort();
    return {added:added,removed:removed,changed:changed,count:added.length+removed.length+changed.length};
  }

  function selectionManifest(rows){
    const repos={};
    Object.keys(rows||{}).sort().forEach(function(repo){
      const row=rows[repo];
      repos[repo]={
        source:"github",
        ref:row.ref,
        resolvedRef:row.evidenceKey,
        canonical:!!row.canonical,
        declared:!!row.declared
      };
    });
    return {version:1,repos:repos};
  }

  const api={
    branchTarget:branchTarget,
    canonicalTarget:canonicalTarget,
    mergeEvidence:mergeEvidence,
    deriveCrossRepoPackageEdges:deriveCrossRepoPackageEdges,
    driftFindings:driftFindings,
    conceptualEvidence:conceptualEvidence,
    evidenceDiff:evidenceDiff,
    selectionManifest:selectionManifest
  };
  root.z0VirtualCore=api;
  if(typeof module!=="undefined"&&module.exports) module.exports=api;
})(typeof globalThis!=="undefined"?globalThis:this);
