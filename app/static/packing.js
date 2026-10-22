'use strict';
// The guide never updates the research physical-action authorization gate.
const packing = {result:null,pieces:[],steps:[],step:0,paused:false,source:null,drawing:false,start:null,generation:0};
const packEl = id => document.getElementById(id);
const packColors = ['#61dcb1','#79b7ff','#efb45f','#cb9ef5','#f38c99','#8bd3e1','#c7d76e','#ec9cc7'];
function packMessage(message) { packEl('packing-message').textContent=message; packEl('packing-message').hidden=!message; }
function packingSource() { return ui.photo?.url || ui.selectedImage || (ui.session?.initial_capture_origin==='SERVER_CAPTURED_PNG' ? `/api/console/sessions/${encodeURIComponent(ui.session.session_id)}/frame0` : null); }
function clearPacking() { packing.generation++;packing.result=null;packing.steps=[];packing.pieces=[];packEl('packing-analysis').hidden=true;packEl('packing-player').hidden=true;packMessage(''); }
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
packEl('segment-photo').onclick=async event=>{
  const button=event.currentTarget;button.disabled=true;button.textContent='Coloring surfaces…';packMessage('');
  clearPacking();const generation=packing.generation;
  try {
    const input=await packInput();packing.source=input.source;
    const result=await api('segment',input.body);
    if(generation!==packing.generation || packingSource()!==input.source)return;
    packing.result=result;
    packing.pieces=result.regions.map(region=>({...region,selected:false,review:'REVIEW',folded:false}));
    packEl('packing-overlay').src=result.overlay;
    packEl('packing-analysis').hidden=false;packEl('packing-player').hidden=true;
    renderPackingRegions();
    if(!result.regions.length)packMessage('No clear colored surfaces found. Draw a region around a piece to add it.');
  } catch(error) {packMessage(friendlyError(error));}
  finally {button.disabled=false;button.textContent='Segment & guide →';}
};
function renderPackingRegions() {
  const previousScroll=packEl('packing-regions').scrollTop;
  packEl('packing-count').textContent=`${packing.pieces.length} color regions`;
  packEl('packing-regions').innerHTML=packing.pieces.map(piece=>`<div class="packing-region ${piece.selected?'picked':''}" style="--piece:${piece.color}"><label class="packing-pick"><input type="checkbox" data-pack-select="${piece.id}" ${piece.selected?'checked':''}><span class="packing-swatch">${String(piece.id).padStart(2,'0')}</span><strong>Region ${String(piece.id).padStart(2,'0')}</strong></label><span class="packing-shape ${piece.shape_hypothesis==='OPEN_BOX_CANDIDATE'?'fold-candidate':''}">${piece.shape_hypothesis==='OPEN_BOX_CANDIDATE'?'Fold this box · candidate':'Check flat / open'}</span><label class="packing-review">Shape<select data-pack-review="${piece.id}" aria-label="Shape for region ${piece.id}"><option value="REVIEW" ${piece.review==='REVIEW'?'selected':''}>Choose shape…</option><option value="FLAT" ${piece.review==='FLAT'?'selected':''}>Flat sheet</option><option value="OPEN" ${piece.review==='OPEN'?'selected':''}>Open / assembled box — fold first</option><option value="EXCLUDE" ${piece.review==='EXCLUDE'?'selected':''}>Not cardboard / duplicate face</option></select></label></div>`).join('');
  packEl('packing-regions').scrollTop=previousScroll;
  packEl('packing-hit-map').innerHTML=packing.pieces.map(piece=>`<polygon points="${piece.polygon.map(p=>p.join(',')).join(' ')}" fill="${piece.color}" fill-opacity="${piece.selected?'.35':'.02'}" stroke="${piece.color}" stroke-width="${piece.selected?'.004':'.001'}" data-pack-hit="${piece.id}" tabindex="0" role="button" aria-label="Select region ${piece.id}" aria-pressed="${piece.selected}"/>`).join('');
  const selected=packing.pieces.filter(p=>p.selected && p.review!=='EXCLUDE');
  const ready=selected.length>0&&selected.every(p=>p.review==='FLAT'||p.review==='OPEN');
  packEl('packing-build').disabled=!ready;
  packEl('packing-build').textContent=ready?`Animate ${selected.length} pieces →`:'Select pieces & choose their shape →';
}
packEl('packing-regions').onchange=event=>{
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
function placementStep(piece,index) {
  const orientation=piece.orientation||0,axis=orientation%180===0?'left to right':'front to back';
  const angle=piece.shape_evidence?.image_long_axis_degrees;
  const turn=Number.isFinite(angle)?` Turn approximately ${Math.round((orientation-angle+360)%360)} degrees clockwise from its pictured direction.`:'';
  return {kind:'PLACE',piece,title:`Layer ${index+1}: region ${String(piece.id).padStart(2,'0')}`,
    copy:`${index===0?'Place this sheet at the base.':'Center this sheet on the previous layer.'} Set its long edge ${axis}.${turn} Put the bulky folded edge ${piece.foldEdge||'away from you'}. Keep every corner inside the supporting layer.`,
    confirm:`Region ${piece.id} is centered at layer ${index+1} with its long edge ${axis}.`};
}
function makePackingSteps(pieces,preserveOrder=false) {
  const ordered=preserveOrder?[...pieces]:[...pieces].sort((a,b)=>b.pixel_area-a.pixel_area||a.id-b.id);
  const fold=ordered.filter(p=>p.review==='OPEN').map(p=>({kind:'FOLD',piece:p,title:`Fold region ${String(p.id).padStart(2,'0')} flat`,copy:'Open the top and bottom flaps. Push the opposite corners together along the existing creases, then lay the box flat.',confirm:`I have flattened region ${String(p.id).padStart(2,'0')}.`}));
  return [...fold,
    {kind:'STACK',title:'Build a centered stack',copy:'Start with the largest physical sheet. Center smaller sheets above it, alternating bulky folded edges. Adjust the pictured order to match the real sheet sizes.',confirm:'The largest real sheet is underneath and the layers are centered.'},
    ...ordered.map(placementStep),
    {kind:'ALIGN',title:'Align and flatten the layers',copy:'Bring the stack edges together. Press the folds flat and move overhanging pieces back toward the center.',confirm:'The layers lie flat without loose overhanging pieces.'},
    {kind:'WRAP_LONG',title:'Route 1: under, up, over',copy:'Slide the middle of the twine under ALL layers along the front-to-back centerline. Bring the near end up the FRONT edge and the far end up the BACK edge. Bring both ends over the top to meet at its center. The dotted route is underneath the stack.',confirm:'The first loop passes under every sheet and rises at the front and back edges.'},
    {kind:'WRAP_CROSS',title:'Route 2: turn and cross',copy:'At the top center, cross the ends and turn them 90 degrees. Take one end over the LEFT edge and down, pass it under ALL layers to the RIGHT edge, then bring it up to the top center. Hold the other end at the crossing. Pull out slack to form two perpendicular loops.',confirm:'The second loop passes under all layers from left to right; the loops cross on top.'},
    {kind:'KNOT_FIRST',title:'Tie the first half-knot',copy:'Cross the right end over the left end. Pass it under and through, then draw the ends together.',confirm:'The first half-knot is seated.'},
    {kind:'KNOT_SECOND',title:'Finish a square knot',copy:'Now cross the LEFT end over the RIGHT end, pass it under and through. Pull both ends evenly outward while holding the loops snug. Right over left, then left over right makes a square knot. Seat the knot flat on top of the crossing.',confirm:'The second crossing is opposite to the first, and the square knot lies flat.'},
    {kind:'CHECK',title:'Check your finished bundle',copy:'Check the knot and both loops. Confirm every sheet is retained and the stack stays together when handled.',confirm:'All sheets are retained and the knot stays seated.'}];
}
packEl('packing-build').onclick=()=>{
  const selected=packing.pieces.filter(p=>p.selected&&['FLAT','OPEN'].includes(p.review));
  if(!selected.length||packing.pieces.some(p=>p.selected&&p.review==='REVIEW'))return;
  packing.ordered=[...selected].sort((a,b)=>b.pixel_area-a.pixel_area||a.id-b.id);
  packing.ordered.forEach((p,i)=>{p.orientation??=0;p.foldEdge??=i%2?'toward you':'away from you';});
  packing.steps=makePackingSteps(selected);packing.step=0;packing.paused=false;
  packEl('packing-analysis').hidden=true;packEl('packing-player').hidden=false;renderPackingStep();
};
function packSvg(step) {
  const pieces=packing.ordered, count=pieces.length,gap=Math.min(10,105/count);
  const maxArea=Math.max(...pieces.map(p=>p.pixel_area));
  const layer=(p,i)=>{
    const size=.55+.45*Math.sqrt(p.pixel_area/maxArea),turned=p.orientation===90;
    const u=turned?[130,19]:[235,34],v=turned?[187,-106]:[117,-66];
    const origin=[310-(u[0]+v[0])/2,235-i*gap-(u[1]+v[1])/2];
    const points=[origin,[origin[0]+u[0],origin[1]+u[1]],[origin[0]+u[0]+v[0],origin[1]+u[1]+v[1]],[origin[0]+v[0],origin[1]+v[1]]];
    const path='M'+points.map(p=>p.join(' ')).join('L')+'Z';
    const edge=p.foldEdge==='toward you'?points.slice(0,2):[points[3],points[2]];
    return `<g transform="translate(310 220) scale(${size}) translate(-310 -220)"><g class="pack-layer ${step.kind==='PLACE'&&step.piece.id===p.id?'pack-current-layer':''}" style="--i:${i};--n:${count}"><path d="${path}" transform="translate(0 8)" fill="${p.color}" stroke="#182c36" stroke-width="3"/><path d="${path}" fill="${p.color}" stroke="#182c36" stroke-width="3"/><path d="M${edge.map(p=>p.join(' ')).join('L')}" stroke="#182c36" stroke-width="6"/>${count<=8||i===count-1?`<text x="290" y="${235-i*gap}" fill="#182c36" font-size="18">${String(p.id).padStart(2,'0')}</text>`:''}</g></g>`;
  };
  const visible=step.kind==='PLACE'?pieces.slice(0,pieces.indexOf(step.piece)+1):pieces;
  const stack=visible.map(layer).join('');
  const floor='<path d="M72 300h480M105 318h410M140 336h330" stroke="#779d9130" stroke-width="2"/>';
  let art=stack;
  if(step.kind==='PLACE') {
    const p=step.piece;
    art+=`<rect x="30" y="25" width="215" height="132" fill="#20383d" stroke="#88bca5"/><text x="42" y="47" fill="#c0dfca" font-size="14">TOP VIEW / ${String(p.id).padStart(2,'0')}</text><g transform="translate(138 102) rotate(${p.orientation||0})"><g class="pack-turn"><rect x="-64" y="-29" width="128" height="58" fill="${p.color}" stroke="#182c36" stroke-width="3"/><path d="M-52 0H52" stroke="#182c36" stroke-width="3" marker-end="url(#pack-arrow)"/></g></g><text x="270" y="65" fill="#c0dfca" font-size="16">LAYER ${pieces.indexOf(p)+1} / ${count}</text><text x="275" y="320" fill="#c0dfca" font-size="16">FRONT / YOU</text>`;
  }
  if(step.kind==='FOLD') {
    const color=step.piece.color;
    art=`<g class="pack-fold-box"><path d="M195 135l130 25 85-47-130-25z" fill="${color}" stroke="#263d40" stroke-width="3"/><path d="M195 135v140l130 25V160z" fill="${color}" stroke="#263d40" stroke-width="3"/><path d="M325 160l85-47v140l-85 47z" fill="${color}" opacity=".7" stroke="#263d40" stroke-width="3"/><path class="pack-flap" d="M195 135l-55-54 130 25 55 54M325 160l55-72 85-47-55 72" fill="${color}" stroke="#263d40" stroke-width="3"/></g><g class="pack-fold-flat"><path d="M160 255l235 34 105-60-235-34z" fill="${color}" stroke="#263d40" stroke-width="3"/><path d="M275 212l-3 59" stroke="#263d40" stroke-dasharray="7 5" stroke-width="3"/></g><path d="M450 130q35 40 0 75" fill="none" stroke="#b8e5c5" stroke-width="4" marker-end="url(#pack-arrow)"/>`;
  }
  const long='M255 157L255 243L370 273L370 185L255 157';
  const cross='M165 196L165 248L400 281L452 250L452 199L335 166L165 196';
  if(['WRAP_LONG','WRAP_CROSS','KNOT_FIRST','KNOT_SECOND','CHECK'].includes(step.kind)) art+=`<path class="pack-rope ${step.kind==='WRAP_LONG'?'drawing-rope':''}" d="${long}" fill="none" stroke="#ffd681" stroke-width="6" stroke-linejoin="round"/><path d="M255 243L370 273" stroke="#20383d" stroke-width="7"/><path d="M255 243L370 273" stroke="#ffd681" stroke-width="5" stroke-dasharray="7 7"/><text x="255" y="333" fill="#c0dfca" font-size="16">FRONT / YOU</text><text x="225" y="95" fill="#ffd681" font-size="14">1 UNDER - 2 UP - 3 OVER</text>`;
  if(['WRAP_CROSS','KNOT_FIRST','KNOT_SECOND','CHECK'].includes(step.kind))art+=`<path class="pack-rope ${step.kind==='WRAP_CROSS'?'drawing-rope':''}" d="${cross}" fill="none" stroke="#ffd681" stroke-width="6" stroke-linejoin="round"/>`;
  if(step.kind==='WRAP_CROSS')art+=`<path d="M165 248L400 281L452 250" fill="none" stroke="#20383d" stroke-width="7"/><path d="M165 248L400 281L452 250" fill="none" stroke="#9cd8fc" stroke-width="5" stroke-dasharray="7 7"/><text x="65" y="180" fill="#c0dfca" font-size="16">LEFT</text><text x="470" y="200" fill="#c0dfca" font-size="16">RIGHT</text><path class="drawing-rope" d="M165 248L400 281L452 250L452 199" fill="none" stroke="#9cd8fc" stroke-width="4" marker-end="url(#pack-arrow)"/>`;
  if(step.kind.startsWith('KNOT')) {
    art=`<g opacity=".25">${art}</g><rect x="140" y="70" width="340" height="240" fill="#20383d" stroke="#88bca5"/><text x="165" y="103" fill="#c0dfca" font-size="15">${step.kind==='KNOT_FIRST'?'RIGHT OVER LEFT':'LEFT OVER RIGHT'}</text><g transform="${step.kind==='KNOT_SECOND'?'translate(600 0) scale(-1 1)':''}"><path class="pack-knot-a" d="M175 270C250 230 365 195 420 140M275 210Q330 140 358 190Q375 226 318 229" stroke="#ffd681" stroke-width="9" fill="none"/><path class="pack-knot-b" d="M175 140C240 176 355 230 425 270M275 190Q258 233 308 229" stroke="#9cd8fc" stroke-width="9" fill="none"/></g><path d="M${step.kind==='KNOT_FIRST'?'386 132L346 157':'219 132L266 159'}" stroke="#ecf5dc" stroke-width="4" marker-end="url(#pack-arrow)"/>`;
  }
  if(step.kind==='ALIGN')art+='<path class="pack-align-arrow" d="M75 209h45M520 215h-35" stroke="#b8e5c5" stroke-width="5" marker-end="url(#pack-arrow)"/>';
  if(step.kind==='CHECK')art+='<path d="M290 190l15 17 35-38" fill="none" stroke="#baf4d2" stroke-width="8"/><text x="243" y="110" fill="#c0dfca" font-size="18">CROSS + SQUARE KNOT</text>';
  return `<svg viewBox="0 0 620 370" role="img" aria-label="${escapeHTML(step.title)}"><defs><marker id="pack-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M0 0l10 5-10 5z" fill="#b8e5c5"/></marker></defs>${floor}${art}</svg>`;
}
function renderPackingStep() {
  const step=packing.steps[packing.step];
  const demo=packing.result?.input_tier==='USER_PROVIDED_DEMO_ONLY';
  packEl('packing-step-label').textContent=`${demo?'DEMO · ':''}STEP ${String(packing.step+1).padStart(2,'0')} / ${String(packing.steps.length).padStart(2,'0')}`;
  packEl('packing-step-title').textContent=step.title;packEl('packing-step-copy').textContent=step.copy;
  packEl('packing-stage').innerHTML=packSvg(step);packEl('packing-stage').dataset.kind=step.kind;
  packEl('packing-stage').classList.toggle('is-paused',packing.paused);
  packEl('packing-order').innerHTML='<span class="packing-order-intro">BASE TO TOP<br>Set order, long-edge direction and bulky fold in this planning step. FRONT means the edge nearest you.</span>'+packing.ordered.map((p,i)=>`<span class="packing-order-chip"><span>Layer ${i+1}</span><button data-pack-move="${i}" data-direction="-1" aria-label="Move region ${p.id} toward base" ${step.kind!=='STACK'||i===0?'disabled':''}>‹</button><b style="--piece:${p.color}">${String(p.id).padStart(2,'0')}</b><button data-pack-move="${i}" data-direction="1" aria-label="Move region ${p.id} toward top" ${step.kind!=='STACK'||i===packing.ordered.length-1?'disabled':''}>›</button><label>Long edge<select data-pack-orient="${p.id}" aria-label="Direction for region ${p.id}" ${step.kind!=='STACK'?'disabled':''}>${[0,90].map(a=>`<option value="${a}" ${p.orientation===a?'selected':''}>${a===0?'Left to right':'Front to back'}</option>`).join('')}</select></label><label>Bulky fold<select data-pack-fold="${p.id}" aria-label="Fold edge for region ${p.id}" ${step.kind!=='STACK'?'disabled':''}>${['away from you','toward you'].map(v=>`<option value="${v}" ${p.foldEdge===v?'selected':''}>${v}</option>`).join('')}</select></label></span>`).join('');
  if(step.kind!=='STACK')packEl('packing-order').innerHTML='<span class="packing-order-intro">BASE TO TOP</span>'+packing.ordered.map((p,i)=>`<span class="packing-order-preview" ${step.piece?.id===p.id?'aria-current="step"':''}><b style="--piece:${p.color}">${String(p.id).padStart(2,'0')}</b><span>${i+1}${p.orientation===90?' ↕':' ↔'}</span></span>`).join('');
  packEl('packing-done-label').textContent=demo?'Demo: simulate completion of this step.':step.confirm;packEl('packing-done').checked=!!step.done;
  packEl('packing-next').disabled=!step.done;packEl('packing-next').textContent=packing.step===packing.steps.length-1?'Finish guide ✓':'Next step →';
  packEl('packing-prev').disabled=packing.step===0;packEl('packing-pause').textContent=packing.paused?'Play':'Pause';
  packEl('packing-progress').innerHTML=packing.steps.map((s,i)=>`<span class="${i===packing.step?'current':s.done?'done':''}"></span>`).join('');
}
packEl('packing-done').onchange=event=>{packing.steps[packing.step].done=event.target.checked;packEl('packing-next').disabled=!event.target.checked;};
packEl('packing-next').onclick=()=>{if(!packing.steps[packing.step].done)return;if(packing.step<packing.steps.length-1){packing.step++;renderPackingStep();}else{packMessage('Packing guide complete. Your checked steps are ready to export.');packEl('packing-next').disabled=true;}};
packEl('packing-prev').onclick=()=>{if(packing.step>0){packing.step--;renderPackingStep();}};
function rebuildPackingPlan() {
  const folds=packing.steps.filter(s=>s.kind==='FOLD');
  packing.steps=makePackingSteps(packing.ordered,true);
  packing.steps.filter(s=>s.kind==='FOLD').forEach(s=>{s.done=folds.find(f=>f.piece.id===s.piece.id)?.done;});
  packing.step=packing.steps.findIndex(s=>s.kind==='STACK');renderPackingStep();
}
packEl('packing-order').onclick=event=>{const button=event.target.closest('[data-pack-move]');if(!button||button.disabled||packing.steps[packing.step].kind!=='STACK')return;const from=Number(button.dataset.packMove),to=from+Number(button.dataset.direction);if(to<0||to>=packing.ordered.length)return;[packing.ordered[from],packing.ordered[to]]=[packing.ordered[to],packing.ordered[from]];rebuildPackingPlan();};
packEl('packing-order').onchange=event=>{
  if(packing.steps[packing.step].kind!=='STACK')return;
  const p=packing.ordered.find(p=>p.id===Number(event.target.dataset.packOrient||event.target.dataset.packFold));if(!p)return;
  if(event.target.dataset.packOrient){const angle=Number(event.target.value);if(![0,90].includes(angle))return;p.orientation=angle;}
  else if(['away from you','toward you'].includes(event.target.value))p.foldEdge=event.target.value;
  rebuildPackingPlan();
};
packEl('packing-pause').onclick=()=>{packing.paused=!packing.paused;packEl('packing-stage').classList.toggle('is-paused',packing.paused);packEl('packing-pause').textContent=packing.paused?'Play':'Pause';};
packEl('packing-replay').onclick=renderPackingStep;
packEl('packing-edit').onclick=()=>{packEl('packing-player').hidden=true;packEl('packing-analysis').hidden=false;packing.steps=[];};
packEl('packing-export').onclick=()=>downloadJSON({schema:'BZX-PACKING-GUIDE-V2',source_sha256:packing.result.source_sha256,input_tier:packing.result.input_tier,opencv_version:packing.result.opencv_version,segmentation_scope:packing.result.segmentation_scope,orientation_reference:'TOP_VIEW_FRONT_EDGE_NEAREST_OPERATOR',order_basis:'UNCALIBRATED_IMAGE_AREA_USER_MUST_CHECK_REAL_SIZES',pieces:packing.ordered,steps:packing.steps.map(({kind,title,copy,piece,done})=>({kind,title,instruction:copy,piece_id:piece?.id,completed_by_user:packing.result.input_tier!=='USER_PROVIDED_DEMO_ONLY'&&!!done,completed_in_demo:packing.result.input_tier==='USER_PROVIDED_DEMO_ONLY'&&!!done})),physical_action_authorized:false},'bind-zero-packing-guide.json');

function enablePackingAnalysis() { if(ui.csrf && ui.runtime) packEl('segment-photo').disabled=false; }
document.addEventListener('console-ready',enablePackingAnalysis);
enablePackingAnalysis();
