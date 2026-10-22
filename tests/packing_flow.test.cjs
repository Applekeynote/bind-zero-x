const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
function harness(){
 const elements=new Map(),exports=[];
 const element=id=>{if(!elements.has(id))elements.set(id,{hidden:false,disabled:false,dataset:{},classList:{toggle(){},remove(){}},getBoundingClientRect(){return {left:0,top:0,width:100,height:100};}});return elements.get(id);};
 const context=vm.createContext({document:{getElementById:element,addEventListener(){}},MutationObserver:class{observe(){}},ui:{photo:null},escapeHTML:s=>s,downloadJSON:value=>exports.push(value)});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/static/packing.js'),'utf8'),context);
 return {context,element,exports,run:code=>vm.runInContext(code,context)};
}
test('open boxes get an explicit fold step before stacking and cross ties',()=>{
 const h=harness();const kinds=h.run(`makePackingSteps([{id:1,pixel_area:100,review:'FLAT'},{id:2,pixel_area:50,review:'OPEN'}]).map(s=>s.kind).join(',')`);
 assert.equal(kinds,'FOLD,STACK,ALIGN,WRAP_LONG,WRAP_CROSS,KNOT_FIRST,KNOT_SECOND,CHECK');
});
test('an unreviewed surface cannot silently become a packing piece',()=>{
 const h=harness();h.run(`packing.pieces=[{id:1,pixel_area:100,selected:true,review:'REVIEW'}]`);
 h.element('packing-build').onclick();assert.equal(h.run('packing.steps.length'),0);
});
test('the largest apparent piece begins at the base and real sizes can override order',()=>{
 const h=harness();h.run(`packing.pieces=[{id:1,pixel_area:100,color:'#61dcb1',selected:true,review:'FLAT'},{id:2,pixel_area:200,color:'#79b7ff',selected:true,review:'FLAT'}]`);
 h.element('packing-build').onclick();assert.equal(h.run('packing.ordered.map(p=>p.id).join()'),'2,1');
 const button={disabled:false,dataset:{packMove:'1',direction:'-1'}};
 h.element('packing-order').onclick({target:{closest:()=>button}});
 assert.equal(h.run('packing.ordered.map(p=>p.id).join()'),'1,2');
 assert.equal(h.element('packing-next').disabled,true);
});
test('animation never advances physical work without a user completion check',()=>{
 const h=harness();h.run(`packing.pieces=[{id:1,pixel_area:100,color:'#61dcb1',selected:true,review:'OPEN'}]`);
 h.element('packing-build').onclick();h.element('packing-next').onclick();
 assert.equal(h.run('packing.step'),0);
 h.element('packing-done').onchange({target:{checked:true}});h.element('packing-next').onclick();
 assert.equal(h.run('packing.steps[packing.step].kind'),'STACK');
 assert.equal(h.element('packing-next').disabled,true);
});
test('a drawn missing region stays unreviewed and uses normalized image coordinates',()=>{
 const h=harness();h.run(`packing.result={width:960,height:720};packing.drawing=true;`);
 h.element('packing-hit-map').onpointerdown({preventDefault(){},clientX:20,clientY:40,currentTarget:{setPointerCapture(){}},pointerId:1});
 h.element('packing-hit-map').onpointerup({clientX:80,clientY:90});
 assert.equal(h.run('packing.pieces[0].review'),'REVIEW');
 assert.equal(h.run('packing.pieces[0].shape_hypothesis'),'USER_SELECTED_REGION');
 assert.equal(h.element('packing-build').disabled,true);
 assert.ok(Math.abs(h.run('packing.pieces[0].bbox[2]')-.6)<1e-10);
});
test('demo confirmations never export as real physical completion',()=>{
 const h=harness();h.run(`packing.result={input_tier:'USER_PROVIDED_DEMO_ONLY',opencv_version:'5.0.0'};packing.ordered=[];packing.steps=[{kind:'FOLD',title:'Fold demo',done:true}];`);
 h.element('packing-export').onclick();
 assert.equal(h.exports[0].physical_action_authorized,false);
 assert.equal(h.exports[0].steps[0].completed_by_user,false);
 assert.equal(h.exports[0].steps[0].completed_in_demo,true);
});
