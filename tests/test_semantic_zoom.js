"use strict";

const assert=require("node:assert");
const zoom=require("../semantic_zoom_core.js");

assert.strictEqual(zoom.semanticLevelForType("component"),1);
assert.strictEqual(zoom.semanticLevelForType("representation"),2);
assert.strictEqual(zoom.semanticLevelForType("evidence_dependency"),3);
assert.strictEqual(zoom.semanticLevelForType("source_artifact"),5);

assert.strictEqual(zoom.detailLevelForScale(0.1),1);
assert.strictEqual(zoom.detailLevelForScale(0.2),2);
assert.strictEqual(zoom.detailLevelForScale(0.3),3);
assert.strictEqual(zoom.detailLevelForScale(0.5),4);
assert.strictEqual(zoom.detailLevelForScale(1.0),5);

assert.strictEqual(zoom.shouldShow(1,1,false),true);
assert.strictEqual(zoom.shouldShow(2,1,false),false);
assert.strictEqual(zoom.shouldShow(5,1,true),true);
assert.strictEqual(zoom.labelForDetail(3),"important detail");

console.log("ok: semantic zoom core");
