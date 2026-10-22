const {test}=require('node:test'),assert=require('node:assert/strict');
require('../app/static/packing-model.js');const model=globalThis.BZXModel;
test('binding follows material and operator-reported springback',()=>{
 assert.equal(model.knotPolicy({material:'PAPER',springback:'LOW'}).id,'REEF');
 assert.equal(model.knotPolicy({material:'COTTON',springback:'HIGH'}).firstTurns,2);
 assert.equal(model.knotPolicy({material:'SLICK',springback:'HIGH'}).ready,false);
 assert.throws(()=>model.knotPolicy({material:'unknown'}));
});
test('measured footprints set real thickness and never mix mm with image units',()=>{
 const a={id:1,longMm:600,shortMm:400,thicknessMm:8,orientation:0,bbox:[0,0,.6,.5]},b={id:2,longMm:400,shortMm:300,thicknessMm:4,orientation:90,bbox:[0,0,.3,.2]};
 const result=model.layout([a,b]);assert.equal(result.units,'mm');assert.equal(result.normalizer,600);assert.ok(Math.abs(result.height-12/600*3.2)<1e-10);
 assert.equal(model.layout([a,{...b,longMm:null}]).units,'relative');
 assert.equal(model.dimensions({...a,shortMm:700}).units,'relative');
});
test('support-aware measured orientation changes a layer when it fits better',()=>{
 const result=model.optimize([{id:1,longMm:600,shortMm:400,thicknessMm:4,orientation:90},{id:2,longMm:500,shortMm:300,thicknessMm:4}]);
 assert.deepEqual(result.map(p=>p.id),[1,2]);assert.equal(result[1].orientation,90);
});
test('each twine route goes below the lowest layer and outside both opposite edges',()=>{
 const l=model.layout([{id:1,longMm:600,shortMm:400,thicknessMm:8}]);
 for(const kind of ['LONG','CROSS']){
  const route=model.route(l,kind);assert.ok(route.some(p=>p[1]<0));assert.ok(route.some(p=>p[1]>l.height));
  const axis=kind==='LONG'?2:0,extent=(kind==='LONG'?l.depth:l.width)/2;
  assert.ok(route.some(p=>p[axis]<-extent));assert.ok(route.some(p=>p[axis]>extent));
 }
});
test('knot strands keep their separate over/under depth lanes',()=>{
 for(const turns of [1,2]){
  const {a,b}=model.halfKnot(turns,1,.2,0);let minimum=Infinity;
  for(const p of a)for(const q of b)minimum=Math.min(minimum,Math.hypot(...p.map((n,i)=>n-q[i])));
  assert.ok(minimum>.036,`rope centers must not intersect: ${minimum}`);
 }
});
