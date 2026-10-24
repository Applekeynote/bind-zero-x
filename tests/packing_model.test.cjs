const {test}=require('node:test'),assert=require('node:assert/strict');
require('../app/static/packing-model.js');const model=globalThis.BZXModel;
test('binding follows material and operator-reported springback',()=>{
 assert.equal(model.knotPolicy({material:'PAPER',springback:'LOW'}).id,'REEF');
 assert.equal(model.knotPolicy({material:'COTTON',springback:'HIGH'}).firstTurns,2);
 assert.equal(model.knotPolicy({material:'SLICK',springback:'HIGH'}).ready,false);
 assert.throws(()=>model.knotPolicy({material:'unknown'}));
});
test('overview completion sizes remain comparable across bundles and close-up photos',()=>{
 const p=(id,long,short)=>({id,sourceWidth:960,sourceHeight:720,completion:{body_long_px:long,body_short_px:short},flatCapture:{region:{completion:{body_long_px:900,body_short_px:800}}}});
 const big=p(1,300,180),small=p(2,130,120),narrow=p(3,320,90);
 assert.equal(model.dimensions(small).long,130,'a close-up cannot enlarge a small piece');
 const plan=model.plan([big,small,narrow]);assert.equal(plan.bundles.length,2);
 assert.equal(plan.bundles[0].layout.normalizer,plan.bundles[1].layout.normalizer);
 const layers=plan.bundles.flatMap(b=>b.layout.layers);
 assert.ok(Math.abs(layers.find(p=>p.id===2).width/layers.find(p=>p.id===1).width-130/300)<1e-10);
});
test('partial measured input cannot be silently ignored and thickness is optional',()=>{
 const a={id:1,longMm:600,shortMm:400},b={id:2,completion:{body_long_px:300,body_short_px:200}};
 assert.equal(model.dimensions(a).units,'mm');assert.equal(model.dimensions(a).thicknessEstimated,true);
 assert.equal(model.sizePolicy([a,b]).ready,false);assert.throws(()=>model.plan([a,b]),/COMPLETE_ALL_PANEL_DIMENSIONS/);
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
test('base and cap enclose every inner folded panel and incompatible panels split',()=>{
 const p=(id,long,short)=>({id,longMm:long,shortMm:short,thicknessMm:4});
 const plan=model.plan([p(1,600,400),p(2,550,380),p(3,350,220),p(4,900,100)]);
 assert.equal(plan.bundles.length,2);
 assert.deepEqual(plan.bundles[0].pieces.map(p=>p.id),[1,3,2]);
 for(const b of plan.bundles){assert.equal(b.layout.support.ready,true);assert.ok(b.layout.support.minimum_cover>=.98);assert.equal(b.layout.support.lifting_verified,false);}
 const invalid=model.layout([p(1,300,200),p(2,600,400)]);assert.equal(invalid.support.ready,false);
});
test('twine wraps and knot are the same two connected halves in every stage',()=>{
 const l=model.layout([{id:1,longMm:600,shortMm:400,thicknessMm:8}]);
 for(const stage of ['WRAP_LONG','WRAP_CROSS','KNOT_FIRST','KNOT_SECOND','CHECK']){
  const p=model.bindingPaths(l,stage,2);assert.deepEqual(p.a[0],p.b[0]);
  assert.ok(p.a.some(v=>v[1]<0));assert.ok(p.b.some(v=>v[1]<0));
  if(stage.startsWith('KNOT')){
   const first=model.halfKnot(2,1,l.height+.014+.042,-.13);
   assert.deepEqual(p.a[p.knotStartA],first.a[0]);assert.deepEqual(p.b[p.knotStartB],first.b[0]);
  }
  assert.equal(p.continuous.length,p.a.length+p.b.length-1);
 }
 const tied=model.bindingPaths(l,'CHECK',2),knot=model.halfKnot(2,1,l.height+.014+.042,-.13);
 assert.ok(knot.a.every(p=>p[1]-.012>=l.height),'knot must stay above the top panel');
 assert.ok(Math.min(...knot.a.map(p=>p[1]-.012-l.height))<.004,'knot seats at the panel instead of floating');
 assert.ok(tied.a.some(p=>p[1]===-.014)&&tied.a.some(p=>p[1]<-.035),'under-wrap has contact and an over/under crossing');
});
