'use strict';
// The guide never updates the research physical-action authorization gate.
const packing = {result:null,pieces:[],steps:[],step:0,paused:false,source:null,drawing:false,start:null,generation:0,condition:{material:'PAPER',springback:'LOW'}};
const packEl = id => document.getElementById(id);
const packColors = ['#61dcb1','#79b7ff','#efb45f','#cb9ef5','#f38c99','#8bd3e1','#c7d76e','#ec9cc7'];
function packMessage(message) { packEl('packing-message').textContent=message; packEl('packing-message').hidden=!message; }
function packingSource() { return ui.photo?.url || ui.selectedImage || (ui.session?.initial_capture_origin==='SERVER_CAPTURED_PNG' ? `/api/console/sessions/${encodeURIComponent(ui.session.session_id)}/frame0` : null); }
function clearPacking() { packing.generation++;globalThis.bzxRealGuide?.hide();packing.result=null;packing.steps=[];packing.pieces=[];packEl('packing-analysis').hidden=true;packEl('packing-player').hidden=true;packMessage(''); }
// Avoid showing a previous photo's masks or plan after the main photo changes.
new MutationObserver(()=>{const source=packingSource();if(packing.source && source!==packing.source)clearPacking();}).observe(packEl('scene-art'),{childList:true});
async function packInput() {
  const source=packingSource();
  if(!source)throw new Error('Choose a photo from the board or add your own photo first.');
  if(ui.photo && !ui.photo.local) return {source,body:{demo_photo:ui.photo.file}};
  const image=new Image();image.src=source;await image.decode();
  const scale=Math.min(1,1280/Math.max(image.naturalWidth,image.naturalHeight));
  const canvas=document.createElement('canvas');canvas.width=Math.round(image.naturalWidth*scale);canvas.height=Math.round(image.naturalHeight*scale);
  canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
  const png=canvas.toDataURL('image/png').split(',')[1];
  if(png.length>6666668)throw new Error('Choose a smaller image.');
  return {source,body:{image_png_b64:png}};
}
async function packingSegment(body,generation,button){
  let result=await api('segment',{...body,async_job:true});
    if(result.job_id){
      const job=result.job_id;let finished=false;
      for(let attempt=0;attempt<120;attempt++){
        if(generation!==packing.generation)return;
        await new Promise(resolve=>setTimeout(resolve,attempt===0?700:Math.min(5000,1500+attempt*1000)));
        const status=await api('segment/jobs/'+encodeURIComponent(job));
        if(status.status==='FAILED')throw Error(status.error);
        if(status.status==='DONE'){result=status.result;finished=true;break;}
        if(button)button.textContent='Separating complete sheets…';
      }
      if(!finished)throw Error('Segmentation is still running. Try again shortly.');
    }
  return result;
}
packEl('segment-photo').onclick=async event=>{
  const button=event.currentTarget;button.disabled=true;button.textContent='Separating complete sheets…';packMessage('');
  clearPacking();const generation=packing.generation;
  try {
    const input=await packInput();packing.source=input.source;
    const result=await packingSegment(input.body,generation,button);if(!result)return;
    if(generation!==packing.generation || packingSource()!==input.source)return;
    packing.result=result;
    packing.pieces=result.regions.map(region=>({...region,selected:false,review:'REVIEW',folded:false,geometryMode:"FULL_OUTLINE",completionMode:"INFERRED",sourceWidth:result.width,sourceHeight:result.height}));
    packEl('packing-overlay').src=result.overlay;packEl('packing-outline-status').textContent='IMAGE DIMENSION RATIOS · NO MEASURING NEEDED';packEl('packing-show-regions').hidden=true;
    packEl('packing-analysis').hidden=false;packEl('packing-player').hidden=true;
    renderPackingRegions();
    if(!result.regions.length)packMessage('No clear sheet outlines found. Draw a region around a piece to add it.');
  } catch(error) {packMessage(friendlyError(error));}
  finally {button.disabled=false;button.textContent='Segment & guide →';}
};
function renderPackingRegions() {
  if(packing.result){packEl('packing-overlay').src=packing.result.overlay;packEl('packing-overlay').alt='Color segmentation of cardboard surfaces';packEl('packing-outline-status').textContent='IMAGE DIMENSION RATIOS · NO MEASURING NEEDED';packEl('packing-show-regions').hidden=true;}
  const previousScroll=packEl('packing-regions').scrollTop;
  packEl('packing-count').textContent=`${packing.pieces.length} piece outlines`;
  packEl('packing-regions').innerHTML=packing.pieces.map(piece=>`<div class="packing-region ${piece.selected?'picked':''}" style="--piece:${piece.color}"><label class="packing-pick"><input type="checkbox" data-pack-select="${piece.id}" ${piece.selected?'checked':''}><span class="packing-swatch">${String(piece.id).padStart(2,'0')}</span><strong>Region ${String(piece.id).padStart(2,'0')}</strong></label><span class="packing-piece-size">${globalThis.BZXModel.sizeLabel(piece)} · ${Math.round(globalThis.BZXModel.dimensions(piece).long/Math.max(...packing.pieces.map(p=>globalThis.BZXModel.dimensions(p).long))*100)}% longest edge</span><button type="button" data-pack-inspect="${piece.id}">Inspect completed outline</button><span class="packing-shape ${piece.shape_hypothesis==='OPEN_BOX_CANDIDATE'?'fold-candidate':''}">${piece.shape_hypothesis==='OPEN_BOX_CANDIDATE'?'Fold this box · candidate':'Check flat / open'}</span><label class="packing-review">Shape<select data-pack-review="${piece.id}" aria-label="Shape for region ${piece.id}"><option value="REVIEW" ${piece.review==='REVIEW'?'selected':''}>Choose shape…</option><option value="FLAT" ${piece.review==='FLAT'?'selected':''}>Flat sheet</option><option value="OPEN" ${piece.review==='OPEN'?'selected':''}>Open / assembled box — fold first</option><option value="EXCLUDE" ${piece.review==='EXCLUDE'?'selected':''}>Not cardboard / duplicate face</option></select></label><label class="packing-review">Panel<select data-pack-geometry="${piece.id}" aria-label="Panel shape for region ${piece.id}"><option value="FULL_OUTLINE" ${piece.geometryMode==='FULL_OUTLINE'?'selected':''}>Keep whole sheet outline</option></select></label>${piece.completion?.inferred_pixels?`<label class="packing-review">Hidden part<select data-pack-completion="${piece.id}" aria-label="Hidden part for region ${piece.id}"><option value="INFERRED" ${piece.completionMode!=='OBSERVED'?'selected':''}>Complete outline · striped estimate</option><option value="OBSERVED" ${piece.completionMode==='OBSERVED'?'selected':''}>Observed pixels only</option></select></label>`:''}<details class="packing-manual-size"><summary>Optional measured size</summary><div class="packing-measurements"><span>Whole flattened sheet / mm</span>${[['longMm','Long edge',20,3000],['shortMm','Short edge',20,3000],['thicknessMm','Thickness',.5,50]].map(([key,label,min,max])=>`<label>${label}<input type="number" inputmode="decimal" step="0.5" min="${min}" max="${max}" value="${piece[key]??''}" data-pack-measure="${piece.id}" data-measure-key="${key}" aria-label="${label} mm for region ${piece.id}"></label>`).join('')}</div></details></div>`).join('');
  packEl('packing-regions').scrollTop=previousScroll;
  packEl('packing-hit-map').innerHTML=packing.pieces.map(piece=>`<polygon points="${piece.polygon.map(p=>p.join(',')).join(' ')}" fill="${piece.color}" fill-opacity="${piece.selected?'.35':'.02'}" stroke="${piece.color}" stroke-width="${piece.selected?'.004':'.001'}" data-pack-hit="${piece.id}" tabindex="0" role="button" aria-label="Select region ${piece.id}" aria-pressed="${piece.selected}"/>`).join('');
  const selected=packing.pieces.filter(p=>p.selected && p.review!=='EXCLUDE');
  const policy=globalThis.BZXModel?.knotPolicy(packing.condition);
  packEl('packing-knot-choice').textContent=policy?policy.name+' / '+policy.reason:'';
  const measuredOk=globalThis.BZXModel.sizePolicy(selected).ready;
  const ready=selected.length>0&&selected.every(p=>p.review==='FLAT'||p.review==='OPEN')&&policy?.ready!==false&&measuredOk;
  packEl('packing-build').disabled=!ready;
  packEl('packing-build').textContent=ready?`Animate ${selected.length} pieces →`:!measuredOk?'Complete each selected panel size →':'Select pieces & choose their shape →';
}
packEl('packing-regions').onchange=event=>{
  if(event.target.dataset.packGeometry||event.target.dataset.packCompletion){const p=packing.pieces.find(p=>p.id===Number(event.target.dataset.packGeometry||event.target.dataset.packCompletion));if(!p)return;if(event.target.dataset.packGeometry)p.geometryMode=event.target.value==='FULL_OUTLINE'?'FULL_OUTLINE':'FOLD_PANEL';else p.completionMode=event.target.value==='OBSERVED'?'OBSERVED':'INFERRED';renderPackingRegions();return;}
  if(event.target.dataset.packMeasure){const piece=packing.pieces.find(p=>p.id===Number(event.target.dataset.packMeasure)),key=event.target.dataset.measureKey;if(!piece||!['longMm','shortMm','thicknessMm'].includes(key))return;piece[key]=event.target.value===''?null:Number(event.target.value);renderPackingRegions();return;}
  const id=Number(event.target.dataset.packSelect||event.target.dataset.packReview);
  const piece=packing.pieces.find(p=>p.id===id);if(!piece)return;
  if(event.target.dataset.packSelect)piece.selected=event.target.checked;
  else {piece.review=event.target.value;piece.selected=piece.review!=='EXCLUDE';}
  piece.folded=false;renderPackingRegions();
};
function hitPacking(event) {const id=Number(event.target.dataset.packHit);const piece=packing.pieces.find(p=>p.id===id);if(piece){piece.selected=!piece.selected;renderPackingRegions();}}
packEl('packing-hit-map').onclick=event=>{if(!packing.drawing)hitPacking(event);};
packEl('packing-hit-map').onkeydown=event=>{if(['Enter',' '].includes(event.key)){event.preventDefault();hitPacking(event);}};
packEl('packing-clear').onclick=()=>{packing.pieces.forEach(p=>p.selected=false);renderPackingRegions();};
packEl('packing-add').onclick=()=>{if(packing.pieces.length>=24)return packMessage('Select up to 24 regions. Start with a closer photo for more pieces.');packing.drawing=!packing.drawing;packEl('packing-image').classList.toggle('drawing',packing.drawing);packEl('packing-add').textContent=packing.drawing?'Drag a rectangle · Cancel':'＋ Draw a missing region';};
function packPoint(event) {const rect=packEl('packing-hit-map').getBoundingClientRect();return [Math.max(0,Math.min(1,(event.clientX-rect.left)/rect.width)),Math.max(0,Math.min(1,(event.clientY-rect.top)/rect.height))];}
packEl('packing-hit-map').onpointerdown=event=>{if(!packing.drawing)return;event.preventDefault();packing.start=packPoint(event);event.currentTarget.setPointerCapture(event.pointerId);};
packEl('packing-hit-map').onpointerup=event=>{
  if(!packing.drawing||!packing.start)return;
  const [ax,ay]=packing.start,[bx,by]=packPoint(event);packing.start=null;
  const x=Math.min(ax,bx),y=Math.min(ay,by),w=Math.abs(ax-bx),h=Math.abs(ay-by);if(w<.02||h<.02)return;
  const id=Math.max(0,...packing.pieces.map(p=>p.id))+1;
  packing.pieces.push({id,color:packColors[(id-1)%packColors.length],selected:true,review:'REVIEW',folded:false,shape_hypothesis:'USER_SELECTED_REGION',bbox:[x,y,w,h],pixel_area:w*h*packing.result.width*packing.result.height,polygon:[[x,y],[x+w,y],[x+w,y+h],[x,y+h]]});
  packing.drawing=false;packEl('packing-image').classList.remove('drawing');packEl('packing-add').textContent='＋ Draw a missing region';renderPackingRegions();
};
function placementStep(piece,index,ordered) {
  const orientation=piece.orientation||0,axis=orientation%180===0?'left to right':'front to back';
  const angle=globalThis.BZXModel.dimensions(piece).imageAxis??piece.shape_evidence?.image_long_axis_degrees;
  const delta=Number.isFinite(angle)?((orientation-angle+540)%360)-180:0;
  const turn=Number.isFinite(angle)?` Turn approximately ${Math.round(Math.abs(delta))} degrees ${delta<0?'counterclockwise':'clockwise'} from its pictured direction.`:'';
  return {kind:'PLACE',piece,title:`Layer ${index+1}: region ${String(piece.id).padStart(2,'0')}`,
    copy:`${index===0?'Place this sheet at the base.':index===ordered.length-1?'Center the broad cap over the inner panels.':'Center this sheet inside the base and cap footprints.'} Size: ${globalThis.BZXModel.sizeLabel(piece)}. Set its long edge ${axis}.${turn} Put the bulky folded edge ${piece.foldEdge||'away from you'}. Keep every corner inside the BASE footprint.`,
    confirm:`Region ${piece.id} is centered at layer ${index+1} with its long edge ${axis}.`};
}
function makePackingSteps(pieces,preserveOrder=false) {
  const ordered=preserveOrder?[...pieces]:[...pieces].sort((a,b)=>b.pixel_area-a.pixel_area||a.id-b.id);
  const fold=ordered.filter(p=>p.review==='OPEN').map(p=>({kind:'FOLD',piece:p,title:`Fold region ${String(p.id).padStart(2,'0')} flat`,copy:'Open the top and bottom flaps. Push the opposite corners together along the existing creases, then lay the box flat.',confirm:`I have flattened region ${String(p.id).padStart(2,'0')}.`}));
  const policy=globalThis.BZXModel?.knotPolicy(packing.condition)||{id:'REEF',firstTurns:1,name:'Square binding knot'};
  const prepare=ordered.filter(p=>p.geometryMode==='FOLD_PANEL'&&(p.flatCapture?.region?.completion||p.completion)).map(p=>({kind:'PREPARE',piece:p,title:`Prepare panel ${String(p.id).padStart(2,'0')}`,copy:'Check the striped inferred edges against the real sheet. Fold every projecting flap inward along its existing crease to make one compact rectangular panel. Keep holes and bulky folds away from the future twine crossing. Correct the finished panel dimensions or add an individual photo if the outline is wrong.',confirm:'I checked the inferred outline and folded all flaps inside the finished panel.'}));
  const steps=[...fold,...prepare,
    {kind:'STACK',title:'Arrange the complete sheets',copy:'Keep each sheet, flap and slot in its original shape. Place the broad sheet at the base and center the smaller sheets over it. Compare projecting flaps in the Top view. Every selected sheet remains in the inventory; incompatible outlines are prepared as separate bundles.',confirm:'The complete outlines are centered and the projecting edges have been checked.'},
    ...ordered.map((p,i)=>placementStep(p,i,ordered)),
    {kind:'ALIGN',title:'Align and flatten the layers',copy:'Bring the stack edges together. Press the folds flat and move overhanging pieces back toward the center.',confirm:'The layers lie flat without loose overhanging pieces.'},
    {kind:'WRAP_LONG',title:'Route 1: under, up, over',copy:'Slide the middle of the twine under ALL layers along the front-to-back centerline. Bring the near end up the FRONT edge and the far end up the BACK edge. Bring both ends over the top to meet at its center. Use the Underneath camera to inspect the continuous route below every layer.',confirm:'The first loop passes under every sheet and rises at the front and back edges.'},
    {kind:'WRAP_CROSS',title:'Route 2: turn and cross',copy:'Follow AMBER end A from the front to the LEFT edge. Take that SAME end down, under ALL layers to the RIGHT edge, then up to the top center. Hold BLUE end B from the back at the center. The amber and blue paths are the two halves of ONE continuous twine; their center joins beneath the stack. Remove slack without bending the panels.',confirm:'The second loop passes under all layers from left to right; the loops cross on top.'},
    {kind:'KNOT_FIRST',title:policy.firstTurns===2?'First crossing: two turns':'First crossing: end A over B',copy:policy.firstTurns===2?'Cross AMBER end A over BLUE end B. Pass it under and through the opening TWICE, keeping the two turns side by side. Pull both ends evenly until the first crossing holds the compressed stack.':'Cross AMBER end A over BLUE end B. Pass it under and through once. Pull both ends evenly on top of the crossed wraps.',confirm:'The first crossing has the required number of turns.'},
    {kind:'KNOT_SECOND',title:'Finish the '+policy.name.toLowerCase(),copy:'Now cross BLUE end B over AMBER end A, pass it under and through. Pull both ends evenly outward while holding the loops snug. Finish with the opposite single crossing; keep both tails on the same sides as their adjacent standing parts. Seat the knot flat on top of the crossing.',confirm:'The second crossing is opposite to the first, and the binding knot lies flat.'},
    {kind:'CHECK',title:'Press, settle and check both loops',copy:'Press the center of the stack, then release. Check that both loops remain snug and the cap still presses every inner panel. Push each accessible sheet gently in both directions. If a sheet moves or a loop loosens, set the bundle down, separate the loose panel or remake the smaller bundle.',confirm:'Both loops stay snug and no panel moves in the hand check.'},
    {kind:'LIFT_CHECK',title:'Check a low supported lift',copy:'Support the bottom panel with BOTH hands and lift only 2 cm over a clear floor. Set it down and check every edge and both loops again. Do not use the twine as a carrying handle. If anything shifts, return to the planning step and split or refold the bundle.',confirm:'I supported the bottom with both hands; the low lift and set-down caused no visible shift.'}];
  return steps;
}
packEl('packing-build').onclick=()=>{
  const selected=packing.pieces.filter(p=>p.selected&&['FLAT','OPEN'].includes(p.review));
  if(!selected.length||packing.pieces.some(p=>p.selected&&p.review==='REVIEW'))return;
  if(!globalThis.BZXModel.sizePolicy(selected).ready)return;
  if(globalThis.BZXModel&&!globalThis.BZXModel.knotPolicy(packing.condition).ready)return;
  const plan=globalThis.BZXModel.plan(selected);packing.bundles=plan.bundles;packing.bundleIndex=0;
  packing.ordered=plan.bundles[0].pieces;
  packing.ordered.forEach((p,i)=>{p.orientation??=0;p.foldEdge??=i%2?'toward you':'away from you';});
  packing.steps=makePackingSteps(packing.ordered,true);packing.step=0;packing.paused=false;packMessage('');
  packEl('packing-analysis').hidden=true;packEl('packing-player').hidden=false;renderPackingStep();
};
function drawRealPackingStep(step){
  if(globalThis.bzxRealGuide)globalThis.bzxRealGuide.show({source:packing.source,width:packing.result.width,height:packing.result.height,labels_png:packing.result.labels_png,pieces:packing.ordered,step,condition:packing.condition,paused:packing.paused});
  else packEl('packing-stage').innerHTML='<span class="real-render-status">Loading photo-based 3D view...</span>';
}
function refreshStepDone(){
  const step=packing.steps[packing.step],needsFlat=(step.kind==='FOLD'&&!step.piece.flatCapture)||packing.capturing;
  const unsupported=step.kind==='STACK'&&!globalThis.BZXModel.layout(packing.ordered).support.ready;
  packEl('packing-done').disabled=needsFlat||unsupported;
  packEl('packing-next').disabled=!step.done||needsFlat||unsupported;
}
function renderPackingStep() {
  const step=packing.steps[packing.step];
  const demo=packing.result?.input_tier==='USER_PROVIDED_DEMO_ONLY';
  packEl('packing-step-label').textContent=`${demo?'DEMO · ':''}STEP ${String(packing.step+1).padStart(2,'0')} / ${String(packing.steps.length).padStart(2,'0')}`;
  packEl('packing-step-title').textContent=step.title;packEl('packing-step-copy').textContent=step.copy;
  const support=globalThis.BZXModel.layout(packing.ordered).support;
  renderPackingInventory();packEl('packing-plan-health').textContent=`${globalThis.BZXModel.layout(packing.ordered).units==='mm'?'MEASURED SIZES':'SHARED PHOTO SCALE'} · BUNDLE ${(packing.bundleIndex||0)+1} / ${packing.bundles?.length||1} · COVER ${Math.round(support.minimum_cover*100)}% · ${support.reason} · HOLD / LIFT CHECK PENDING`;
  drawRealPackingStep(step);packEl('packing-stage').dataset.kind=step.kind;
  packEl('packing-stage').classList.toggle('is-paused',packing.paused);
  packEl('packing-order').innerHTML='<span class="packing-order-intro">BASE TO TOP<br>Set order, long-edge direction and bulky fold in this planning step. FRONT means the edge nearest you.</span>'+packing.ordered.map((p,i)=>`<span class="packing-order-chip"><span>Layer ${i+1} · ${globalThis.BZXModel.sizeLabel(p)}</span><button data-pack-move="${i}" data-direction="-1" aria-label="Move region ${p.id} toward base" ${step.kind!=='STACK'||i===0?'disabled':''}>‹</button><b style="--piece:${p.color}">${String(p.id).padStart(2,'0')}</b><button data-pack-move="${i}" data-direction="1" aria-label="Move region ${p.id} toward top" ${step.kind!=='STACK'||i===packing.ordered.length-1?'disabled':''}>›</button><label>Long edge<select data-pack-orient="${p.id}" aria-label="Direction for region ${p.id}" ${step.kind!=='STACK'?'disabled':''}>${[0,90].map(a=>`<option value="${a}" ${p.orientation===a?'selected':''}>${a===0?'Left to right':'Front to back'}</option>`).join('')}</select></label><label>Bulky fold<select data-pack-fold="${p.id}" aria-label="Fold edge for region ${p.id}" ${step.kind!=='STACK'?'disabled':''}>${['away from you','toward you'].map(v=>`<option value="${v}" ${p.foldEdge===v?'selected':''}>${v}</option>`).join('')}</select></label><button type="button" data-pack-capture="${p.id}" ${step.kind!=='STACK'?'disabled':''}>${p.flatCapture?'Replace individual photo':'Add individual flat photo'}</button></span>`).join('');
  if(step.kind!=='STACK')packEl('packing-order').innerHTML='<span class="packing-order-intro">BASE TO TOP</span>'+packing.ordered.map((p,i)=>`<span class="packing-order-preview" ${step.piece?.id===p.id?'aria-current="step"':''}><b style="--piece:${p.color}">${String(p.id).padStart(2,'0')}</b><span>${i+1}${p.orientation===90?' ↕':' ↔'} · ${globalThis.BZXModel.sizeLabel(p)}</span></span>`).join('');
  if(step.kind==='STACK')packEl('packing-order').innerHTML='<label class="bundle-choice">Bundle<select data-pack-bundle="1" aria-label="Bundle to prepare">'+(packing.bundles||[{pieces:packing.ordered}]).map((b,i)=>`<option value="${i}" ${i===(packing.bundleIndex||0)?'selected':''}>${i+1} / ${b.pieces.map(p=>String(p.id).padStart(2,'0')).join(', ')}</option>`).join('')+'</select></label><button type="button" data-pack-replan="1">Restore supported order</button>'+packEl('packing-order').innerHTML;
  packEl('packing-done-label').textContent=demo?'Demo: simulate completion of this step.':step.confirm;packEl('packing-done').checked=!!step.done;
  packEl('packing-flat-capture').hidden=step.kind!=='FOLD';
  packEl('packing-flat-status').textContent=step.piece?.flatCapture?'Flat capture added. Review the photo before continuing.':'';
  refreshStepDone();packEl('packing-next').textContent=packing.step===packing.steps.length-1?(packing.bundles?.some((b,i)=>i!==packing.bundleIndex&&!b.completed)?'Finish bundle & continue →':'Finish guide ✓'):'Next step →';
  packEl('packing-prev').disabled=packing.step===0;packEl('packing-pause').textContent=packing.paused?'Play':'Pause';
  packEl('packing-progress').innerHTML=packing.steps.map((s,i)=>`<span class="${i===packing.step?'current':s.done?'done':''}"></span>`).join('');
}
packEl('packing-done').onchange=event=>{const step=packing.steps[packing.step];if(step.kind==='FOLD'&&!step.piece.flatCapture)return;step.done=event.target.checked;refreshStepDone();};
packEl('packing-next').onclick=()=>{if(packing.capturing||(packing.steps[packing.step].kind==='STACK'&&!globalThis.BZXModel.layout(packing.ordered).support.ready)||!packing.steps[packing.step].done||(packing.steps[packing.step].kind==='FOLD'&&!packing.steps[packing.step].piece.flatCapture))return;if(packing.step<packing.steps.length-1){packing.step++;renderPackingStep();}else{if(packing.bundles?.length){const bundle=packing.bundles[packing.bundleIndex];bundle.completed=true;bundle.steps=packing.steps;const next=packing.bundles.findIndex(b=>!b.completed);if(next>=0){activatePackingBundle(next);return;}}packMessage('All selected pieces are included. Every bundle guide is complete.');packEl('packing-next').disabled=true;}};
packEl('packing-prev').onclick=()=>{if(packing.step>0){packing.step--;renderPackingStep();}};
function rebuildPackingPlan() {
  const folds=packing.steps.filter(s=>s.kind==='FOLD');
  packing.steps=makePackingSteps(packing.ordered,true);
  packing.steps.filter(s=>s.kind==='FOLD').forEach(s=>{s.done=folds.find(f=>f.piece.id===s.piece.id)?.done;});
  packing.step=packing.steps.findIndex(s=>s.kind==='STACK');renderPackingStep();
}
packEl('packing-order').onclick=event=>{if(event.target.closest('[data-pack-replan]')){packing.ordered=globalThis.BZXModel.optimize(packing.ordered);rebuildPackingPlan();return;}const capture=event.target.closest('[data-pack-capture]');if(capture?.dataset.packCapture&&!capture.disabled&&packing.steps[packing.step].kind==='STACK'){packing.capturePiece=packing.ordered.find(p=>p.id===Number(capture.dataset.packCapture));packEl('packing-flat-photo').click();return;}const button=event.target.closest('[data-pack-move]');if(!button||button.disabled||packing.steps[packing.step].kind!=='STACK')return;const from=Number(button.dataset.packMove),to=from+Number(button.dataset.direction);if(to<0||to>=packing.ordered.length)return;[packing.ordered[from],packing.ordered[to]]=[packing.ordered[to],packing.ordered[from]];rebuildPackingPlan();};
packEl('packing-order').onchange=event=>{
  if(packing.steps[packing.step].kind!=='STACK')return;
  if(event.target.dataset.packBundle){activatePackingBundle(Number(event.target.value));return;}
  const p=packing.ordered.find(p=>p.id===Number(event.target.dataset.packOrient||event.target.dataset.packFold));if(!p)return;
  if(event.target.dataset.packOrient){const angle=Number(event.target.value);if(![0,90].includes(angle))return;p.orientation=angle;}
  else if(['away from you','toward you'].includes(event.target.value))p.foldEdge=event.target.value;
  rebuildPackingPlan();
};
packEl('packing-pause').onclick=()=>{packing.paused=!packing.paused;globalThis.bzxRealGuide?.pause(packing.paused);packEl('packing-stage').classList.toggle('is-paused',packing.paused);packEl('packing-pause').textContent=packing.paused?'Play':'Pause';};
packEl('packing-replay').onclick=()=>{globalThis.bzxRealGuide?.replay();};
packEl('packing-edit').onclick=()=>{globalThis.bzxRealGuide?.hide();packEl('packing-player').hidden=true;packEl('packing-analysis').hidden=false;packing.steps=[];};
packEl('packing-export').onclick=()=>downloadJSON({schema:'BZX-PACKING-GUIDE-V4',bundles:packing.bundles?.map(b=>({piece_ids:b.pieces.map(p=>p.id),completed_in_demo:packing.result.input_tier==='USER_PROVIDED_DEMO_ONLY'&&!!b.completed,layout:globalThis.BZXModel.layout(b.pieces)})),binding_paths:globalThis.BZXModel?.bindingPaths(globalThis.BZXModel.layout(packing.ordered),'CHECK',globalThis.BZXModel.knotPolicy(packing.condition).firstTurns),lifting_verified:false,binding_condition:packing.condition,knot:globalThis.BZXModel?.knotPolicy(packing.condition),layout:globalThis.BZXModel?.layout(packing.ordered),source_sha256:packing.result.source_sha256,input_tier:packing.result.input_tier,opencv_version:packing.result.opencv_version,segmentation_scope:packing.result.segmentation_scope,orientation_reference:'TOP_VIEW_FRONT_EDGE_NEAREST_OPERATOR',order_basis:globalThis.BZXModel?.layout(packing.ordered).units==='mm'?'MEASURED_FOOTPRINT_OPERATOR_EDITABLE':'CREASE_ALIGNED_SHARED_PHOTO_DIMENSION_RATIOS',pieces:(packing.pieces.length?packing.pieces.filter(p=>p.selected&&p.review!=='EXCLUDE'):packing.ordered).map(({flatCapture,...p})=>({...p,flat_capture:flatCapture?{source_sha256:flatCapture.source_sha256,width:flatCapture.width,height:flatCapture.height}:null})),steps:packing.steps.map(({kind,title,copy,piece,done})=>({kind,title,instruction:copy,piece_id:piece?.id,completed_by_user:packing.result.input_tier!=='USER_PROVIDED_DEMO_ONLY'&&!!done,completed_in_demo:packing.result.input_tier==='USER_PROVIDED_DEMO_ONLY'&&!!done})),physical_action_authorized:false},'bind-zero-packing-guide.json');

function enablePackingAnalysis() { if(ui.csrf && ui.runtime) packEl('segment-photo').disabled=false; }
document.addEventListener('console-ready',enablePackingAnalysis);
enablePackingAnalysis();

document.addEventListener('real-guide-ready',()=>{if(packing.steps.length)drawRealPackingStep(packing.steps[packing.step]);});
document.addEventListener('real-guide-paused',()=>{packing.paused=true;packEl('packing-pause').textContent='Play';});
for(const [id,key] of [['packing-material','material'],['packing-springback','springback']])packEl(id).onchange=e=>{packing.condition[key]=e.target.value;renderPackingRegions();};
packEl('packing-flat-photo').onchange=async e=>{
  const file=e.target.files?.[0],step=packing.steps[packing.step],piece=packing.capturePiece||step?.piece;packing.capturePiece=null;if(!file||!step||!piece)return;
  const generation=packing.generation;packing.capturing=true;refreshStepDone();packEl('packing-flat-status').textContent='Reading the flattened photo...';
  try{
    if(file.size>25_000_000)throw Error('Choose a photo up to 25 MB.');
    const original=URL.createObjectURL(file),image=new Image();image.src=original;
    try{await image.decode();const scale=Math.min(1,1280/Math.max(image.naturalWidth,image.naturalHeight));
      const canvas=document.createElement('canvas');canvas.width=Math.round(image.naturalWidth*scale);canvas.height=Math.round(image.naturalHeight*scale);canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
      const png=canvas.toDataURL('image/png'),b64=png.split(',')[1];if(b64.length>6666668)throw Error('Choose a smaller photo.');
      const result=await packingSegment({image_png_b64:b64},generation);if(!result)return;
      if(generation!==packing.generation||packing.steps[packing.step]!==step)return;
      if(!result.regions.length)throw Error('No clear flat surface found. Take a closer photo on a contrasting background.');
      piece.flatCapture={url:png,width:result.width,height:result.height,labels_png:result.labels_png,source_sha256:result.source_sha256,region:result.regions[0]};
      piece.shape_evidence=result.regions[0].shape_evidence;step.done=false;packing.capturing=false;
      if(step.kind==='STACK')rebuildPackingPlan();else renderPackingStep();
    }finally{URL.revokeObjectURL(original);}
  }catch(error){packMessage(friendlyError(error));}
  finally{packing.capturing=false;if(packing.steps.length)refreshStepDone();}
  e.target.value='';
};

packEl('packing-regions').onclick=event=>{
  const button=event.target.closest('[data-pack-inspect]');if(!button)return;
  const piece=packing.pieces.find(p=>p.id===Number(button.dataset.packInspect));if(!piece?.completion)return;
  packEl('packing-overlay').src=piece.completion.texture_png;
  packEl('packing-overlay').alt='Completed outline for region '+piece.id;
  packEl('packing-hit-map').innerHTML='';
  packEl('packing-outline-status').textContent='REGION '+String(piece.id).padStart(2,'0')+' · '+globalThis.BZXModel.sizeLabel(piece)+' · SAME PHOTO SCALE';
  packEl('packing-show-regions').hidden=false;
};
packEl('packing-show-regions').onclick=()=>{
  packEl('packing-overlay').src=packing.result.overlay;packEl('packing-overlay').alt='Color segmentation of cardboard surfaces';
  packEl('packing-outline-status').textContent='IMAGE DIMENSION RATIOS · NO MEASURING NEEDED';
  packEl('packing-show-regions').hidden=true;renderPackingRegions();
};

function activatePackingBundle(index){
  if(!Number.isInteger(index)||!packing.bundles?.[index])return;
  const previous=packing.bundles[packing.bundleIndex];
  if(previous){previous.steps=packing.steps;previous.stepIndex=packing.step;previous.pieces=packing.ordered;}
  packing.bundleIndex=index;const next=packing.bundles[index];packing.ordered=next.pieces;
  packing.steps=next.steps||makePackingSteps(packing.ordered,true);packing.step=next.stepIndex||0;packMessage('');renderPackingStep();
}
function renderPackingInventory(){
  const bundles=packing.bundles||[{pieces:packing.ordered}],all=bundles.flatMap(b=>b.pieces);
  packEl('packing-inventory').innerHTML='<p>ALL '+all.length+' PIECES INCLUDED · '+bundles.length+' BUNDLES</p><div>'+bundles.map((b,index)=>b.pieces.map(p=>{
    const photo=p.completion?.preview_png||p.completion?.texture_png;
    const thumbnail=photo?.startsWith('data:image/png;base64,')?'<img src="'+photo+'" alt="Complete outline of region '+p.id+'">':'';
    return '<button type="button" data-inventory-bundle="'+index+'" aria-label="Show region '+String(p.id).padStart(2,'0')+' in bundle '+(index+1)+'" aria-pressed="'+(index===packing.bundleIndex)+'">'+thumbnail+'<span>REGION '+String(p.id).padStart(2,'0')+'</span><small>'+globalThis.BZXModel.sizeLabel(p)+' · BUNDLE '+(index+1)+(b.completed?' · DONE':'')+'</small></button>';
  }).join('')).join('')+'</div>';
}
packEl('packing-inventory').onclick=event=>{const button=event.target.closest('[data-inventory-bundle]');if(button)activatePackingBundle(Number(button.dataset.inventoryBundle));};
